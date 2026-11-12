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

fn release(directory: &Path, content_sha256: &str) {
    fs::write(
        directory.join("release.json"),
        json!({"schema": 1, "version": "10.200.2027", "released_at": "2026-11-12T09:05:35Z", "content_sha256": content_sha256}).to_string(),
    )
    .unwrap();
}

fn identified(directory: &Path) -> String {
    let signature = fs::read(directory.join("signature.json")).unwrap();
    let mut signature: Value = serde_json::from_slice(&signature).unwrap();
    signature["signature_version"] = json!(1001);
    let signature = signature.to_string();
    fs::write(directory.join("signature.json"), &signature).unwrap();
    let mut manifest: Value = serde_json::from_slice(&fs::read(directory.join("project.json")).unwrap()).unwrap();
    manifest["model_id"] = json!(1005);
    manifest["files"]["signature.json"] = json!(hex(&Sha256::digest(signature.as_bytes())));
    let manifest = manifest.to_string();
    fs::write(directory.join("project.json"), &manifest).unwrap();
    hex(&Sha256::digest(manifest.as_bytes()))
}

#[test]
fn a_released_project_reports_its_versions_and_hashes() {
    let directory = project(3.5, "FP64", 3.5);
    let content_sha256 = identified(&directory);
    release(&directory, &content_sha256);
    let info = Model::load(&directory).unwrap().info().clone();
    assert_eq!(info.content_sha256, content_sha256);
    assert_eq!(info.model_id, Some(1005));
    assert_eq!(info.signature_version, Some(1001));
    assert_eq!(info.release_version.as_deref(), Some("10.200.2027"));
    assert_eq!(info.released_at.as_deref(), Some("2026-11-12T09:05:35Z"));
    assert_eq!(
        info.files.keys().cloned().collect::<Vec<_>>(),
        ["golden.json", "signature.json"]
    );
}

#[test]
fn an_unreleased_project_reports_no_release() {
    let info = Model::load(&project(3.5, "FP64", 3.5)).unwrap().info().clone();
    assert_eq!((info.model_id, info.signature_version), (None, None));
    assert_eq!((info.release_version, info.released_at), (None, None));
}

#[test]
fn a_release_file_for_another_project_is_a_load_error() {
    let directory = project(3.5, "FP64", 3.5);
    release(&directory, &"0".repeat(64));
    let error = load_error(&directory);
    assert!(matches!(error.kind, Kind::Load));
    assert_eq!(error.gate, "release");
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
