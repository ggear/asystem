use std::collections::BTreeMap;

use serde_json::Value;

type Tensors = BTreeMap<String, Vec<f64>>;
type Predict = Box<dyn Fn(&Tensors) -> Result<Tensors, String>>;

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
