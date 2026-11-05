mod run_onnx;
mod run_served;
mod run_static;
mod run_wasm;

use std::collections::BTreeMap;
use std::fs;
use std::path::Path;
use std::process::ExitCode;
use std::time::Instant;

use serde_json::Value;
use sha2::{Digest, Sha256};

type Tensors = BTreeMap<String, Vec<f64>>;
type Predict = Box<dyn Fn(&Tensors) -> Result<Tensors, String>>;

fn main() -> ExitCode {
    let arguments: Vec<String> = std::env::args().skip(1).collect();
    if arguments.is_empty() || arguments.len() == 2 || arguments.len() > 3 {
        eprintln!("ERROR usage consumer <project dir> [<server> <name>]");
        return ExitCode::from(2);
    }
    let served = (arguments.len() == 3).then(|| (arguments[1].clone(), arguments[2].clone()));
    match replay(Path::new(&arguments[0]), served) {
        Ok(findings) => {
            for finding in &findings {
                eprintln!("ERROR {finding}");
            }
            if findings.is_empty() {
                ExitCode::SUCCESS
            } else {
                ExitCode::FAILURE
            }
        }
        Err(message) => {
            eprintln!("ERROR {message}");
            ExitCode::FAILURE
        }
    }
}

fn load_project(dir: &Path) -> Result<(Value, String), String> {
    let manifest = read_json(&dir.join("project.json"))?;
    let signature_json = fs::read_to_string(dir.join(text(&manifest["files"]["signature"]["path"])))
        .map_err(|error| format!("signature unreadable [{error}]"))?;
    for (key, entry) in manifest["files"].as_object().into_iter().flatten() {
        let bytes = fs::read(dir.join(text(&entry["path"]))).map_err(|_| format!("PJ003 file absent [{key}]"))?;
        if hex(&Sha256::digest(&bytes)) != text(&entry["sha256"]) {
            return Err(format!("PJ003 file checksum mismatch [{key}]"));
        }
    }
    match manifest["files"].get("evaluation") {
        Some(entry) => {
            if read_json(&dir.join(text(&entry["path"])))?["passed"] != Value::Bool(true) {
                return Err("acceptance not passed".to_string());
            }
        }
        None if text(&manifest["flavour"]) != "static" => {
            return Err(format!(
                "no acceptance evaluation for flavour [{}]",
                text(&manifest["flavour"])
            ));
        }
        None => {}
    }
    Ok((manifest, signature_json))
}

fn replay(dir: &Path, served: Option<(String, String)>) -> Result<Vec<String>, String> {
    let started = Instant::now();
    let (manifest, signature_json) = load_project(dir)?;
    report(
        "verify",
        &format!(
            "{} files",
            manifest["files"].as_object().map_or(0, serde_json::Map::len) + 1
        ),
        started,
    );
    let signature: Value =
        serde_json::from_str(&signature_json).map_err(|error| format!("signature invalid [{error}]"))?;
    let started = Instant::now();
    let (predict, loaded) = match served {
        Some((host, model)) => (
            run_served::load_served(&format!("{host}/v2/models/{model}/infer"), &signature_json)?,
            "served".to_string(),
        ),
        None => (
            new_predictor(dir, &manifest, &signature_json)?,
            text(&manifest["flavour"]),
        ),
    };
    report("load", &loaded, started);
    let started = Instant::now();
    let mut steps = 0;
    let golden = read_json(&dir.join(text(&manifest["files"]["golden"]["path"])))?;
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
            steps += 1;
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
            let outputs = match predict(&inputs) {
                Ok(outputs) => outputs,
                Err(error) => {
                    findings.push(format!("RP005 step [{step_id}] the model gave no answer [{error}]"));
                    continue;
                }
            };
            for entry in step["response"]["outputs"].as_array().into_iter().flatten() {
                let name = text(&entry["name"]);
                let expected = numbers(&entry["data"]);
                if !within(outputs.get(&name), &expected, &golden["tolerance"], &name) {
                    findings.push(format!(
                        "RP003 step [{step_id}] output [{name}] is [{:?}] and the golden is [{expected:?}]",
                        outputs.get(&name)
                    ));
                }
            }
        }
    }
    report("replay", &format!("{steps} steps"), started);
    Ok(findings)
}

fn report(stage: &str, detail: &str, started: Instant) {
    println!(
        "    {stage:<12} ... done [{detail}] ({:.2}s)",
        started.elapsed().as_secs_f64()
    );
}

fn new_predictor(dir: &Path, manifest: &Value, signature_json: &str) -> Result<Predict, String> {
    let model = dir
        .join(text(&manifest["files"]["model"]["path"]))
        .to_string_lossy()
        .into_owned();
    match text(&manifest["flavour"]).as_str() {
        "static" => run_static::load_static(&manifest["constants"].to_string(), signature_json),
        "wasm" => run_wasm::load_wasm(&model, signature_json),
        "onnx" => run_onnx::load_onnx(&model, signature_json),
        other => Err(format!("no consumer for flavour [{other}]")),
    }
}

fn within(actual: Option<&Vec<f64>>, expected: &[f64], tolerance: &Value, name: &str) -> bool {
    let bounds = &tolerance[name];
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

fn read_json(path: &Path) -> Result<Value, String> {
    let content =
        fs::read_to_string(path).map_err(|error| format!("file unreadable [{}] [{error}]", path.display()))?;
    serde_json::from_str(&content).map_err(|error| format!("json invalid [{}] [{error}]", path.display()))
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
