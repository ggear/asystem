use std::collections::BTreeMap;

use serde_json::{json, Value};

type Tensors = BTreeMap<String, Vec<f64>>;
type Predict = Box<dyn Fn(&Tensors) -> Result<Tensors, String>>;

pub fn load_served(url: &str, signature_json: &str) -> Result<Predict, String> {
    let url = url.to_string();
    let signature: Value =
        serde_json::from_str(signature_json).map_err(|error| format!("signature invalid [{error}]"))?;
    Ok(Box::new(move |inputs| {
        let request_inputs: Vec<Value> = signature["inputs"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|entry| {
                let name = entry["name"].as_str()?;
                let data = inputs.get(name)?;
                Some(json!({"name": name, "shape": [data.len()], "datatype": entry["datatype"], "data": data}))
            })
            .collect();
        let answer: Value = ureq::post(&url)
            .send_json(json!({"inputs": request_inputs}))
            .map_err(|error| format!("server gave no answer [{error}]"))?
            .body_mut()
            .read_json()
            .map_err(|error| format!("answer invalid [{error}]"))?;
        Ok(answer["outputs"]
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|output| {
                let data = output["data"]
                    .as_array()?
                    .iter()
                    .map(|item| item.as_f64().unwrap_or(f64::NAN))
                    .collect();
                Some((output["name"].as_str()?.to_string(), data))
            })
            .collect())
    }))
}
