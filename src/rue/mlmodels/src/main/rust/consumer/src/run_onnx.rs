use std::cell::RefCell;
use std::collections::BTreeMap;

use ort::session::Session;
use ort::value::{DynValue, Tensor};
use serde_json::Value;

type Tensors = BTreeMap<String, Vec<f64>>;
type Predict = Box<dyn Fn(&Tensors) -> Result<Tensors, String>>;

pub fn load_onnx(path: &str, signature_json: &str) -> Result<Predict, String> {
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
    let session = RefCell::new(session);
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
                    i32::try_from(*item)
                        .map(f64::from)
                        .map_err(|error| format!("output out of range [{error}]"))
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
        let mut session = session.borrow_mut();
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
