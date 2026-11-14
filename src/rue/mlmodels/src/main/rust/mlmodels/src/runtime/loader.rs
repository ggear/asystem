use std::collections::BTreeMap;
use std::fmt;
use std::fs;
use std::path::{Path, PathBuf};

use serde_json::Value;
use sha2::{Digest, Sha256};

pub type Tensors = BTreeMap<String, Vec<f64>>;
pub type Predict = Box<dyn Fn(&Tensors) -> Result<Tensors, String> + Send + Sync>;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Load,
    Signature,
    Runtime,
    Verify,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ModelError {
    pub kind: Kind,
    pub gate: String,
    pub cause: String,
}

impl ModelError {
    fn new(kind: Kind, gate: &str, cause: impl Into<String>) -> Self {
        Self {
            kind,
            gate: gate.to_string(),
            cause: cause.into(),
        }
    }
}

impl fmt::Display for ModelError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{:?} {} [{}]", self.kind, self.gate, self.cause)
    }
}

impl std::error::Error for ModelError {}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Info {
    pub name: String,
    pub flavour: String,
    pub content_sha256: String,
    pub model_id: Option<i64>,
    pub signature_version: Option<i64>,
    pub release_version: Option<String>,
    pub released_at: Option<String>,
    pub files: BTreeMap<String, String>,
}

pub struct Project {
    pub manifest: Value,
    pub signature_json: String,
    pub content_sha256: String,
    pub release: Option<Value>,
}

pub struct Model {
    info: Info,
    signature: Value,
    directory: PathBuf,
    predict: Predict,
}

impl Model {
    pub fn load(directory: &Path) -> Result<Self, ModelError> {
        Self::build(directory, &read_project(directory)?)
    }

    pub fn build(directory: &Path, project: &Project) -> Result<Self, ModelError> {
        let manifest = &project.manifest;
        let flavour = text(&manifest["flavour"]);
        let signature: Value = serde_json::from_str(&project.signature_json)
            .map_err(|error| ModelError::new(Kind::Load, "signature", format!("signature invalid [{error}]")))?;
        let model = directory.join(text(&manifest["model"])).to_string_lossy().into_owned();
        let driver = match flavour.as_str() {
            "static" => load_static(&manifest["constants"].to_string(), &project.signature_json),
            "wasm" => load_wasm(&model, &project.signature_json),
            "onnx" => load_onnx(&model, &project.signature_json),
            other => {
                return Err(ModelError::new(
                    Kind::Load,
                    "flavour",
                    format!("no loader for flavour [{other}]"),
                ));
            }
        }
        .map_err(|cause| ModelError::new(Kind::Load, "driver", cause))?;
        Ok(Self {
            info: Info {
                name: text(&manifest["name"]),
                flavour,
                content_sha256: project.content_sha256.clone(),
                model_id: manifest["model_id"].as_i64(),
                signature_version: signature["signature_version"].as_i64(),
                release_version: project.release.as_ref().map(|release| text(&release["version"])),
                released_at: project.release.as_ref().map(|release| text(&release["released_at"])),
                files: manifest["files"]
                    .as_object()
                    .into_iter()
                    .flatten()
                    .map(|(path, checksum)| (path.clone(), text(checksum)))
                    .collect(),
            },
            signature,
            directory: directory.to_path_buf(),
            predict: driver,
        })
    }

    pub fn info(&self) -> &Info {
        &self.info
    }

    pub fn signature(&self) -> &Value {
        &self.signature
    }

    pub fn predict(&self, inputs: &Tensors) -> Result<Tensors, ModelError> {
        let entries = |section: &str| {
            self.signature[section]
                .as_array()
                .into_iter()
                .flatten()
                .cloned()
                .collect::<Vec<_>>()
        };
        let missing: Vec<String> = entries("inputs")
            .iter()
            .filter(|entry| entry["parameters"]["required"] == Value::Bool(true))
            .map(|entry| text(&entry["name"]))
            .filter(|name| !inputs.contains_key(name))
            .collect();
        if !missing.is_empty() {
            return Err(ModelError::new(
                Kind::Signature,
                "inputs",
                format!("missing required inputs [{missing:?}]"),
            ));
        }
        let slots = self.signature["parameters"]["state"].as_array().map_or(0, Vec::len);
        for entry in entries("inputs").iter().filter(|entry| is_state(entry)) {
            let name = text(&entry["name"]);
            if let Some(data) = inputs.get(&name) {
                if data.len() != slots {
                    return Err(ModelError::new(
                        Kind::Signature,
                        "state",
                        format!(
                            "input [{name}] has [{}] values and the signature has [{slots}] slots",
                            data.len()
                        ),
                    ));
                }
            }
        }
        let outputs = (self.predict)(inputs).map_err(|cause| ModelError::new(Kind::Runtime, "predict", cause))?;
        for entry in entries("outputs").iter().filter(|entry| entry["datatype"] == "INT64") {
            let name = text(&entry["name"]);
            for value in outputs.get(&name).into_iter().flatten() {
                if !value.is_finite() || value.fract() != 0.0 || value.abs() > 9_007_199_254_740_992.0 {
                    return Err(ModelError::new(
                        Kind::Runtime,
                        "datatype",
                        format!("INT64 output [{name}] is not an integer [{value}]"),
                    ));
                }
            }
        }
        Ok(outputs)
    }

    pub fn verify(&self) -> Result<(), ModelError> {
        let findings = replay(&self.directory, &self.signature, &|inputs| {
            self.predict(inputs).map_err(|error| error.to_string())
        })?;
        if findings.is_empty() {
            return Ok(());
        }
        let cause: Vec<String> = findings
            .iter()
            .map(|(rule, message)| format!("{rule} {message}"))
            .collect();
        Err(ModelError::new(Kind::Verify, "replay", cause.join("; ")))
    }
}

pub fn read_project(directory: &Path) -> Result<Project, ModelError> {
    let manifest_bytes = read_bytes(&directory.join("project.json"))?;
    let manifest: Value = serde_json::from_slice(&manifest_bytes)
        .map_err(|error| ModelError::new(Kind::Load, "manifest", format!("manifest unreadable [{error}]")))?;
    for (path, checksum) in manifest["files"].as_object().into_iter().flatten() {
        let bytes = fs::read(directory.join(path))
            .map_err(|_| ModelError::new(Kind::Load, "PJ003", format!("file absent [{path}]")))?;
        if hex(&Sha256::digest(&bytes)) != text(checksum) {
            return Err(ModelError::new(
                Kind::Load,
                "PJ003",
                format!("file checksum mismatch [{path}]"),
            ));
        }
    }
    let flavour = text(&manifest["flavour"]);
    if manifest["files"].get("evaluation.json").is_some() {
        if read_json(&directory.join("evaluation.json"))?["passed"] != Value::Bool(true) {
            return Err(ModelError::new(Kind::Load, "acceptance", "acceptance not passed"));
        }
    } else if flavour != "static" {
        return Err(ModelError::new(
            Kind::Load,
            "acceptance",
            format!("no acceptance evaluation for flavour [{flavour}]"),
        ));
    }
    let signature_json = String::from_utf8(read_bytes(&directory.join("signature.json"))?)
        .map_err(|error| ModelError::new(Kind::Load, "signature", format!("signature invalid [{error}]")))?;
    let content_sha256 = hex(&Sha256::digest(&manifest_bytes));
    let release_path = directory.join("release.json");
    let release = if release_path.is_file() {
        let release = read_json(&release_path)?;
        if text(&release["content_sha256"]) != content_sha256
            || !release["version"].is_string()
            || !release["released_at"].is_string()
        {
            return Err(ModelError::new(
                Kind::Load,
                "release",
                format!(
                    "release file differs from the project [{}]",
                    text(&release["content_sha256"])
                ),
            ));
        }
        Some(release)
    } else {
        None
    };
    Ok(Project {
        manifest,
        signature_json,
        content_sha256,
        release,
    })
}

pub fn replay(
    directory: &Path,
    signature: &Value,
    predict: &dyn Fn(&Tensors) -> Result<Tensors, String>,
) -> Result<Vec<(String, String)>, ModelError> {
    let golden = read_json(&directory.join("golden.json"))?;
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
            let missing: Vec<&String> = required.iter().filter(|name| !inputs.contains_key(*name)).collect();
            let complete = missing.is_empty();
            if step.get("error").is_some() {
                if complete {
                    findings.push((
                        "RP001".to_string(),
                        format!("step [{step_id}] expects a signature error but supplies every required input"),
                    ));
                }
                continue;
            }
            if !complete {
                findings.push((
                    "RP002".to_string(),
                    format!("step [{step_id}] is missing required inputs [{missing:?}]"),
                ));
                continue;
            }
            let outputs = match predict(&inputs) {
                Ok(outputs) => outputs,
                Err(error) => {
                    findings.push((
                        "RP005".to_string(),
                        format!("step [{step_id}] the model gave no answer [{error}]"),
                    ));
                    continue;
                }
            };
            for entry in step["response"]["outputs"].as_array().into_iter().flatten() {
                let name = text(&entry["name"]);
                let expected = numbers(&entry["data"]);
                if !within(outputs.get(&name), &expected, &golden["tolerance"][name.as_str()]) {
                    findings.push((
                        "RP003".to_string(),
                        format!(
                            "step [{step_id}] output [{name}] is [{:?}] and the golden is [{expected:?}]",
                            outputs.get(&name)
                        ),
                    ));
                }
            }
        }
    }
    Ok(findings)
}

pub fn read_json(path: &Path) -> Result<Value, ModelError> {
    serde_json::from_slice(&read_bytes(path)?).map_err(|error| {
        ModelError::new(
            Kind::Load,
            "json",
            format!("file unreadable [{}] [{error}]", path.display()),
        )
    })
}

fn read_bytes(path: &Path) -> Result<Vec<u8>, ModelError> {
    fs::read(path).map_err(|error| {
        ModelError::new(
            Kind::Load,
            "read",
            format!("file unreadable [{}] [{error}]", path.display()),
        )
    })
}

fn within(actual: Option<&Vec<f64>>, expected: &[f64], bounds: &Value) -> bool {
    let Some(actual) = actual else { return false };
    if actual.len() != expected.len() {
        return false;
    }
    if bounds.is_null() {
        return actual == expected;
    }
    let absolute = bounds["absolute"].as_f64().unwrap_or(0.0);
    let relative = bounds["relative"].as_f64().unwrap_or(0.0);
    actual
        .iter()
        .zip(expected)
        .all(|(value, truth)| (value - truth).abs() <= absolute + relative * truth.abs())
}

fn is_state(entry: &Value) -> bool {
    entry["shape"] == serde_json::json!([-1])
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

fn hex(bytes: &[u8]) -> String {
    use std::fmt::Write;
    bytes.iter().fold(String::new(), |mut out, byte| {
        let _ = write!(out, "{byte:02x}");
        out
    })
}

pub fn load_static(constants_json: &str, _signature_json: &str) -> Result<Predict, String> {
    let constants: Value =
        serde_json::from_str(constants_json).map_err(|error| format!("constants invalid [{error}]"))?;
    let constants = constants.as_object().cloned().unwrap_or_default();
    Ok(Box::new(move |_| {
        Ok(constants
            .iter()
            .map(|(name, value)| (name.clone(), vec![value.as_f64().unwrap_or(f64::NAN)]))
            .collect())
    }))
}

#[cfg(not(feature = "model-wasm"))]
pub fn load_wasm(_path: &str, _signature_json: &str) -> Result<Predict, String> {
    Err("flavour [wasm] needs feature [model-wasm]".to_string())
}

#[cfg(feature = "model-wasm")]
pub fn load_wasm(path: &str, signature_json: &str) -> Result<Predict, String> {
    use serde_json::json;
    use wasmi::{Config, Engine, Linker, Module, Store, StoreLimits, StoreLimitsBuilder};

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
            result.insert(text(&entry["name"]), values[position..position + count].to_vec());
            position += count;
        }
        Ok(result)
    }))
}

#[cfg(not(feature = "model-onnx"))]
pub fn load_onnx(_path: &str, _signature_json: &str) -> Result<Predict, String> {
    Err("flavour [onnx] needs feature [model-onnx]".to_string())
}

#[cfg(feature = "model-onnx")]
pub fn load_onnx(path: &str, signature_json: &str) -> Result<Predict, String> {
    use std::sync::Mutex;

    use ort::session::Session;
    use ort::value::{DynValue, Tensor};

    const EXACT_INTEGER: i64 = 1 << 53;

    let signature: Value =
        serde_json::from_str(signature_json).map_err(|error| format!("signature invalid [{error}]"))?;
    let library = std::env::var("ONNXRUNTIME_LIB").map_err(|error| format!("onnxruntime unavailable [{error}]"))?;
    let environment = ort::init_from(library)
        .map_err(|error| format!("onnxruntime unavailable [{error}]"))?
        .build()
        .map_err(|error| format!("onnxruntime unavailable [{error}]"))?;
    let session = Session::builder(&environment)
        .and_then(|mut builder| builder.commit_from_file(path))
        .map_err(|error| format!("model did not load [{error}]"))?;
    let session = Mutex::new(session);
    let text = |value: &Value| value.as_str().unwrap_or_default().to_string();
    let values = |value: &DynValue| -> Result<Vec<f64>, String> {
        if let Ok((_, data)) = value.try_extract_tensor::<f64>() {
            return Ok(data.to_vec());
        }
        if let Ok((_, data)) = value.try_extract_tensor::<f32>() {
            return Ok(data.iter().map(|item| f64::from(*item)).collect());
        }
        if let Ok((_, data)) = value.try_extract_tensor::<i64>() {
            return data
                .iter()
                .map(|item| {
                    if item.abs() > EXACT_INTEGER {
                        return Err(format!("output out of range [{item}]"));
                    }
                    serde_json::Number::from(*item)
                        .as_f64()
                        .ok_or_else(|| format!("output out of range [{item}]"))
                })
                .collect();
        }
        Err("output type unsupported".to_string())
    };
    Ok(Box::new(move |inputs| {
        let _environment = &environment;
        let mut feeds = Vec::new();
        for entry in signature["inputs"].as_array().into_iter().flatten() {
            let name = text(&entry["name"]);
            if let Some(data) = inputs.get(&name) {
                let tensor = Tensor::from_array(([1, data.len()], data.clone()))
                    .map_err(|error| format!("input invalid [{name}] [{error}]"))?;
                feeds.push((name, tensor));
            }
        }
        let mut session = session
            .lock()
            .map_err(|error| format!("session unavailable [{error}]"))?;
        let results = session
            .run(feeds)
            .map_err(|error| format!("predict failed [{error}]"))?;
        let mut outputs = Tensors::new();
        for entry in signature["outputs"].as_array().into_iter().flatten() {
            let name = text(&entry["name"]);
            outputs.insert(name.clone(), values(&results[name.as_str()])?);
        }
        Ok(outputs)
    }))
}
