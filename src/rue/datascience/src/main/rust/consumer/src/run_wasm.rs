use std::collections::BTreeMap;

use serde_json::{json, Value};
use wasmi::{Config, Engine, Linker, Module, Store, StoreLimits, StoreLimitsBuilder};

type Tensors = BTreeMap<String, Vec<f64>>;
type Predict = Box<dyn Fn(&Tensors) -> Result<Tensors, String>>;

pub fn load_wasm(path: &str, signature_json: &str) -> Result<Predict, String> {
    const FUEL: u64 = 1_000_000;
    const MEMORY_BYTES: usize = 1 << 20;
    const MATH_MODULE: &str = "asystem_math";
    type Unary = fn(f64) -> f64;
    type Binary = fn(f64, f64) -> f64;

    let signature: Value =
        serde_json::from_str(signature_json).map_err(|error| format!("signature invalid [{error}]"))?;
    let bytes = std::fs::read(path).map_err(|error| format!("model unreadable [{path}] [{error}]"))?;
    let mut config = Config::default();
    config.consume_fuel(true);
    let engine = Engine::new(&config);
    let module = Module::new(&engine, &bytes[..]).map_err(|error| format!("module invalid [{error}]"))?;
    let mut linker = <Linker<StoreLimits>>::new(&engine);
    let unary: [(&str, Unary); 13] = [
        ("acos", f64::acos),
        ("asin", f64::asin),
        ("atan", f64::atan),
        ("cos", f64::cos),
        ("cosh", f64::cosh),
        ("exp", f64::exp),
        ("log", f64::ln),
        ("log10", f64::log10),
        ("log2", f64::log2),
        ("sin", f64::sin),
        ("sinh", f64::sinh),
        ("tan", f64::tan),
        ("tanh", f64::tanh),
    ];
    let binary: [(&str, Binary); 2] = [("atan2", f64::atan2), ("pow", f64::powf)];
    for (name, function) in unary {
        linker
            .func_wrap(MATH_MODULE, name, function)
            .map_err(|error| format!("maths function did not link [{name}] [{error}]"))?;
    }
    for (name, function) in binary {
        linker
            .func_wrap(MATH_MODULE, name, function)
            .map_err(|error| format!("maths function did not link [{name}] [{error}]"))?;
    }
    let text = |value: &Value| value.as_str().unwrap_or_default().to_string();
    Ok(Box::new(move |inputs| {
        let state_slots = signature["parameters"]["state"].as_array().map_or(0, Vec::len);
        let is_state = |entry: &Value| entry["shape"] == json!([-1]);
        let mut row: Vec<f64> = Vec::new();
        for entry in signature["inputs"]
            .as_array()
            .into_iter()
            .flatten()
            .filter(|entry| !is_state(entry))
        {
            row.push(
                inputs
                    .get(&text(&entry["name"]))
                    .and_then(|data| data.first().copied())
                    .unwrap_or(f64::NAN),
            );
        }
        for entry in signature["inputs"]
            .as_array()
            .into_iter()
            .flatten()
            .filter(|entry| is_state(entry))
        {
            row.extend(
                inputs
                    .get(&text(&entry["name"]))
                    .cloned()
                    .unwrap_or_else(|| vec![0.0; state_slots]),
            );
        }
        let width: usize = signature["outputs"]
            .as_array()
            .into_iter()
            .flatten()
            .map(|entry| if is_state(entry) { state_slots } else { 1 })
            .sum();

        let mut store: Store<StoreLimits> =
            Store::new(&engine, StoreLimitsBuilder::new().memory_size(MEMORY_BYTES).build());
        store.limiter(|limits| limits);
        store
            .set_fuel(FUEL)
            .map_err(|error| format!("fuel unavailable [{error}]"))?;
        let instance = linker
            .instantiate_and_start(&mut store, &module)
            .map_err(|error| format!("module did not instantiate [{error}]"))?;
        let memory = instance
            .get_memory(&store, "memory")
            .ok_or("module exports no memory")?;
        let function = instance
            .get_typed_func::<(i32, i32, i32), ()>(&store, "predict")
            .map_err(|error| format!("predict missing [{error}]"))?;

        let x: Vec<u8> = row.iter().flat_map(|value| value.to_le_bytes()).collect();
        let y_ptr = x.len();
        memory
            .write(&mut store, 0, &x)
            .map_err(|error| format!("write failed [{error}]"))?;
        function
            .call(
                &mut store,
                (0, 1, i32::try_from(y_ptr).map_err(|error| error.to_string())?),
            )
            .map_err(|error| format!("predict failed [{error}]"))?;
        let mut raw = vec![0u8; width * 8];
        memory
            .read(&store, y_ptr, &mut raw)
            .map_err(|error| format!("read failed [{error}]"))?;
        let values: Vec<f64> = raw
            .as_chunks::<8>()
            .0
            .iter()
            .map(|chunk| f64::from_le_bytes(*chunk))
            .collect();

        let mut result = Tensors::new();
        let mut position = 0;
        for entry in signature["outputs"].as_array().into_iter().flatten() {
            let count = if is_state(entry) { state_slots } else { 1 };
            let integer = entry["datatype"] == "INT64";
            let chunk = values[position..position + count]
                .iter()
                .map(|value| if integer { value.trunc() } else { *value })
                .collect();
            result.insert(text(&entry["name"]), chunk);
            position += count;
        }
        Ok(result)
    }))
}
