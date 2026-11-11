use std::fs;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};

use serde_json::{json, Value};
use sha2::{Digest, Sha256};

use super::loader::{Kind, Model, ModelError, Tensors};

static COUNTER: AtomicUsize = AtomicUsize::new(0);

fn hex(bytes: &[u8]) -> String {
    use std::fmt::Write;
    bytes.iter().fold(String::new(), |mut out, byte| {
        let _ = write!(out, "{byte:02x}");
        out
    })
}

fn signature(datatype: &str) -> Value {
    json!({
        "name": "demo_calc",
        "inputs": [{"name": "demo_in", "datatype": "FP64", "shape": [1], "parameters": {"required": true}}],
        "outputs": [{"name": "demo_out", "datatype": datatype, "shape": [1], "parameters": {"required": true}}],
        "parameters": {}
    })
}

fn project(value: f64, datatype: &str, golden_out: f64) -> PathBuf {
    let directory = std::env::temp_dir().join(format!(
        "loader-test-{}-{}",
        std::process::id(),
        COUNTER.fetch_add(1, Ordering::SeqCst)
    ));
    fs::create_dir_all(&directory).unwrap();
    let signature = signature(datatype).to_string();
    let golden = json!({"sequences": [{"steps": [{
        "request": {"id": "one", "inputs": [{"name": "demo_in", "data": [1.0]}]},
        "response": {"outputs": [{"name": "demo_out", "data": [golden_out]}]}
    }]}]})
    .to_string();
    fs::write(directory.join("signature.json"), &signature).unwrap();
    fs::write(directory.join("golden.json"), &golden).unwrap();
    let manifest = json!({
        "name": "demo_calc", "flavour": "static", "constants": {"demo_out": value},
        "files": {
            "signature.json": hex(&Sha256::digest(signature.as_bytes())),
            "golden.json": hex(&Sha256::digest(golden.as_bytes()))
        }
    });
    fs::write(directory.join("project.json"), manifest.to_string()).unwrap();
    directory
}

fn load_error(directory: &Path) -> ModelError {
    Model::load(directory).err().unwrap()
}

#[test]
fn a_project_loads_predicts_and_verifies() {
    let model = Model::load(&project(3.0, "FP64", 3.0)).unwrap();
    model.verify().unwrap();
    let inputs = Tensors::from([("demo_in".to_string(), vec![1.0])]);
    assert_eq!(vec![3.0], model.predict(&inputs).unwrap()["demo_out"]);
    assert_eq!("static", model.info().flavour);
}

#[test]
fn a_model_is_send_and_sync() {
    fn check<T: Send + Sync>() {}
    check::<Model>();
}

#[test]
fn a_malformed_project_is_a_load_error() {
    let truncated = project(3.0, "FP64", 3.0);
    fs::write(truncated.join("project.json"), "{\"na").unwrap();
    let changed = project(3.0, "FP64", 3.0);
    fs::write(changed.join("golden.json"), " ").unwrap();
    let absent = project(3.0, "FP64", 3.0);
    fs::remove_file(absent.join("signature.json")).unwrap();
    let missing = project(3.0, "FP64", 3.0);
    fs::remove_file(missing.join("project.json")).unwrap();
    let flavour = project(3.0, "FP64", 3.0);
    let mut manifest: Value = serde_json::from_slice(&fs::read(flavour.join("project.json")).unwrap()).unwrap();
    manifest["flavour"] = json!("wasm");
    fs::write(flavour.join("project.json"), manifest.to_string()).unwrap();
    for directory in [truncated, changed, absent, missing, flavour] {
        assert_eq!(Kind::Load, load_error(&directory).kind);
    }
}

#[test]
fn a_missing_required_input_is_a_signature_error() {
    let model = Model::load(&project(3.0, "FP64", 3.0)).unwrap();
    assert_eq!(Kind::Signature, model.predict(&Tensors::new()).unwrap_err().kind);
}

#[test]
fn an_integer_output_that_is_not_an_integer_is_a_runtime_error() {
    let inputs = Tensors::from([("demo_in".to_string(), vec![1.0])]);
    for value in [1.5, f64::NAN, 2.0_f64.powi(60)] {
        let model = Model::load(&project(value, "INT64", 0.0)).unwrap();
        assert_eq!(Kind::Runtime, model.predict(&inputs).unwrap_err().kind);
    }
    let model = Model::load(&project(3.0, "INT64", 3.0)).unwrap();
    assert_eq!(vec![3.0], model.predict(&inputs).unwrap()["demo_out"]);
}

#[test]
fn a_golden_difference_is_a_verify_error() {
    let model = Model::load(&project(3.0, "FP64", 9.0)).unwrap();
    assert_eq!(Kind::Verify, model.verify().unwrap_err().kind);
}
