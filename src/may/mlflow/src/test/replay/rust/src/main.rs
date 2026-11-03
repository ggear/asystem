use std::collections::BTreeMap;
use std::env::consts::ARCH;
use std::fs;
use std::path::Path;
use std::process::ExitCode;

use serde_json::{json, Value};
use wasmi::{Config, Engine, Linker, Module, Store, StoreLimits, StoreLimitsBuilder};

const FUEL: u64 = 1_000_000;
const MEMORY_BYTES: usize = 1 << 20;
const EXIT_UNSUPPORTED: u8 = 2;

type Tensors = BTreeMap<String, Vec<f64>>;
type Predict = Box<dyn Fn(&Tensors) -> Result<Tensors, String>>;

enum Failure {
    Unsupported(String),
    Broken(String),
}

fn main() -> ExitCode {
    let Some(project_dir) = std::env::args().nth(1) else {
        eprintln!("ERROR usage modelreplay <project dir>");
        return ExitCode::from(EXIT_UNSUPPORTED);
    };
    match replay(Path::new(&project_dir)) {
        Ok(findings) => {
            println!(
                "{}",
                json!({"host": "rust", "arch": ARCH, "passed": findings.is_empty()})
            );
            for finding in &findings {
                eprintln!("ERROR {finding}");
            }
            if findings.is_empty() {
                ExitCode::SUCCESS
            } else {
                ExitCode::FAILURE
            }
        }
        Err(Failure::Unsupported(flavor)) => {
            eprintln!("SKIP flavor not supported [{flavor}]");
            ExitCode::from(EXIT_UNSUPPORTED)
        }
        Err(Failure::Broken(message)) => {
            eprintln!("ERROR {message}");
            ExitCode::FAILURE
        }
    }
}

fn replay(project_dir: &Path) -> Result<Vec<String>, Failure> {
    let manifest = read_json(&project_dir.join("project.json"))?;
    let signature = read_json(&project_dir.join("signature.json"))?;
    let golden = read_json(&project_dir.join("golden.json"))?;
    let flavor = text(&manifest["flavor"]);
    let predict: Predict = match flavor.as_str() {
        "static" => {
            let constants = manifest["constants"].as_object().cloned().unwrap_or_default();
            Box::new(move |_| {
                Ok(constants
                    .iter()
                    .map(|(name, value)| (name.clone(), vec![value.as_f64().unwrap_or(f64::NAN)]))
                    .collect())
            })
        }
        "wasm" => {
            let path = project_dir.join(text(&manifest["files"]["model"]["path"]));
            let bytes = fs::read(&path)
                .map_err(|error| Failure::Broken(format!("model unreadable [{}] [{error}]", path.display())))?;
            let signature = signature.clone();
            Box::new(move |inputs| wasm_predict(&bytes, &signature, inputs))
        }
        other => return Err(Failure::Unsupported(other.to_string())),
    };
    let required: Vec<String> = signature["inputs"]
        .as_array()
        .into_iter()
        .flatten()
        .filter(|entry| entry["parameters"]["required"] == Value::Bool(true))
        .map(|entry| text(&entry["name"]))
        .collect();
    let mut findings = Vec::new();
    for sequence in golden["sequences"].as_array().into_iter().flatten() {
        for step in sequence["steps"].as_array().into_iter().flatten() {
            let step_id = text(&step["request"]["id"]);
            let inputs: Tensors = step["request"]["inputs"]
                .as_array()
                .into_iter()
                .flatten()
                .map(|entry| (text(&entry["name"]), numbers(&entry["data"])))
                .collect();
            let complete = required.iter().all(|name| inputs.contains_key(name));
            if step.get("error").is_some() {
                if complete {
                    findings.push(format!(
                        "RP001 step [{step_id}] expects a signature error but supplies every required input"
                    ));
                }
                continue;
            }
            if !complete {
                findings.push(format!("RP002 step [{step_id}] is missing required inputs"));
                continue;
            }
            let outputs = predict(&inputs).map_err(Failure::Broken)?;
            for entry in step["response"]["outputs"].as_array().into_iter().flatten() {
                let name = text(&entry["name"]);
                let expected = numbers(&entry["data"]);
                if outputs.get(&name) != Some(&expected) {
                    findings.push(format!(
                        "RP003 step [{step_id}] output [{name}] is [{:?}] and the golden is [{expected:?}]",
                        outputs.get(&name)
                    ));
                }
            }
        }
    }
    Ok(findings)
}

fn wasm_predict(bytes: &[u8], signature: &Value, inputs: &Tensors) -> Result<Tensors, String> {
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

    let mut config = Config::default();
    config.consume_fuel(true);
    let engine = Engine::new(&config);
    let module = Module::new(&engine, bytes).map_err(|error| format!("module invalid [{error}]"))?;
    let mut store: Store<StoreLimits> =
        Store::new(&engine, StoreLimitsBuilder::new().memory_size(MEMORY_BYTES).build());
    store.limiter(|limits| limits);
    store
        .set_fuel(FUEL)
        .map_err(|error| format!("fuel unavailable [{error}]"))?;
    let instance = Linker::new(&engine)
        .instantiate_and_start(&mut store, &module)
        .map_err(|error| format!("module did not instantiate [{error}]"))?;
    let memory = instance
        .get_memory(&store, "memory")
        .ok_or("module exports no memory")?;
    let predict = instance
        .get_typed_func::<(i32, i32, i32), ()>(&store, "predict")
        .map_err(|error| format!("predict missing [{error}]"))?;

    let x: Vec<u8> = row.iter().flat_map(|value| value.to_le_bytes()).collect();
    let y_ptr = x.len();
    memory
        .write(&mut store, 0, &x)
        .map_err(|error| format!("write failed [{error}]"))?;
    predict
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
}

fn read_json(path: &Path) -> Result<Value, Failure> {
    let content = fs::read_to_string(path)
        .map_err(|error| Failure::Broken(format!("file unreadable [{}] [{error}]", path.display())))?;
    serde_json::from_str(&content)
        .map_err(|error| Failure::Broken(format!("json invalid [{}] [{error}]", path.display())))
}

fn text(value: &Value) -> String {
    value.as_str().unwrap_or_default().to_string()
}

fn numbers(value: &Value) -> Vec<f64> {
    value
        .as_array()
        .into_iter()
        .flatten()
        .map(|item| item.as_f64().unwrap_or(f64::NAN))
        .collect()
}
