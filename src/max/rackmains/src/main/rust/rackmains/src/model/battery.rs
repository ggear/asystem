////////////////////////////////////////////////////////////////////////////////
// WARNING: This file is written by the build process, any manual edits will be lost!
////////////////////////////////////////////////////////////////////////////////

// project rackmains_ups_battery sha256 30a4f8a750beff595cef875973be8ad97aeefc898fa7c132005d2804a78716e5

use std::path::Path;

use serde::{Deserialize, Serialize};

use super::loader::{Kind, Model, ModelError, Tensors};

pub const NAME: &str = "rackmains_ups_battery";
pub const STATE_SLOTS: usize = 6;
pub const INPUT_NAMES: &[&str] = &[
    "clock_epoch_seconds",
    "rackmains_output_load_pct",
    "rackmains_mains_present",
    "rackmains_ups_calibrating",
    "rackmains_battery_low",
    "rackmains_battery_volts",
    "rackmains_battery_replace_due",
    "rackmains_battery_age_days",
    "rackmains_read_failures",
    "rackmains_battery_state_in",
];
pub const OUTPUT_NAMES: &[&str] = &[
    "rackmains_guard_shed_battery_seconds",
    "rackmains_guard_restore_mains_seconds",
    "rackmains_guard_shed_runtime_seconds",
    "rackmains_battery_runtime_remaining_seconds",
    "rackmains_battery_energy_remaining_pct",
    "rackmains_battery_energy_used_wh",
    "rackmains_model_refit_due",
    "rackmains_model_refit_reason_code",
    "rackmains_battery_state_out",
];
pub const REQUIRED_INPUT_NAMES: &[&str] = &[
    "clock_epoch_seconds",
    "rackmains_output_load_pct",
    "rackmains_mains_present",
];
pub const REQUIRED_OUTPUT_NAMES: &[&str] = &[
    "rackmains_guard_shed_battery_seconds",
    "rackmains_guard_restore_mains_seconds",
];

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Request {
    pub clock_epoch_seconds: f64,
    pub rackmains_output_load_pct: i64,
    pub rackmains_mains_present: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_ups_calibrating: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_battery_low: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_battery_volts: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_battery_replace_due: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_battery_age_days: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_read_failures: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_battery_state_in: Option<Vec<f64>>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Response {
    pub rackmains_guard_shed_battery_seconds: i64,
    pub rackmains_guard_restore_mains_seconds: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_guard_shed_runtime_seconds: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_battery_runtime_remaining_seconds: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_battery_energy_remaining_pct: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_battery_energy_used_wh: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_model_refit_due: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_model_refit_reason_code: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_battery_state_out: Option<Vec<f64>>,
}

impl From<Request> for Tensors {
    fn from(request: Request) -> Self {
        let mut tensors = Tensors::new();
        tensors.insert("clock_epoch_seconds".to_string(), vec![request.clock_epoch_seconds]);
        tensors.insert(
            "rackmains_output_load_pct".to_string(),
            vec![serde_json::Number::from(request.rackmains_output_load_pct)
                .as_f64()
                .unwrap_or(f64::NAN)],
        );
        tensors.insert(
            "rackmains_mains_present".to_string(),
            vec![serde_json::Number::from(request.rackmains_mains_present)
                .as_f64()
                .unwrap_or(f64::NAN)],
        );
        if let Some(value) = request.rackmains_ups_calibrating {
            tensors.insert(
                "rackmains_ups_calibrating".to_string(),
                vec![serde_json::Number::from(value).as_f64().unwrap_or(f64::NAN)],
            );
        }
        if let Some(value) = request.rackmains_battery_low {
            tensors.insert(
                "rackmains_battery_low".to_string(),
                vec![serde_json::Number::from(value).as_f64().unwrap_or(f64::NAN)],
            );
        }
        if let Some(value) = request.rackmains_battery_volts {
            tensors.insert("rackmains_battery_volts".to_string(), vec![value]);
        }
        if let Some(value) = request.rackmains_battery_replace_due {
            tensors.insert(
                "rackmains_battery_replace_due".to_string(),
                vec![serde_json::Number::from(value).as_f64().unwrap_or(f64::NAN)],
            );
        }
        if let Some(value) = request.rackmains_battery_age_days {
            tensors.insert(
                "rackmains_battery_age_days".to_string(),
                vec![serde_json::Number::from(value).as_f64().unwrap_or(f64::NAN)],
            );
        }
        if let Some(value) = request.rackmains_read_failures {
            tensors.insert(
                "rackmains_read_failures".to_string(),
                vec![serde_json::Number::from(value).as_f64().unwrap_or(f64::NAN)],
            );
        }
        if let Some(value) = request.rackmains_battery_state_in {
            tensors.insert("rackmains_battery_state_in".to_string(), value);
        }
        tensors
    }
}

impl TryFrom<Tensors> for Response {
    type Error = ModelError;

    fn try_from(tensors: Tensors) -> Result<Self, Self::Error> {
        Ok(Self {
            rackmains_guard_shed_battery_seconds: match tensors
                .get("rackmains_guard_shed_battery_seconds")
                .map(Vec::as_slice)
            {
                Some([value]) => *value as i64,
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [rackmains_guard_shed_battery_seconds] is absent or not one value".to_string(),
                    })
                }
            },
            rackmains_guard_restore_mains_seconds: match tensors
                .get("rackmains_guard_restore_mains_seconds")
                .map(Vec::as_slice)
            {
                Some([value]) => *value as i64,
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [rackmains_guard_restore_mains_seconds] is absent or not one value".to_string(),
                    })
                }
            },
            rackmains_guard_shed_runtime_seconds: match tensors
                .get("rackmains_guard_shed_runtime_seconds")
                .map(Vec::as_slice)
            {
                None => None,
                Some([value]) => Some(*value as i64),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [rackmains_guard_shed_runtime_seconds] is absent or not one value".to_string(),
                    })
                }
            },
            rackmains_battery_runtime_remaining_seconds: match tensors
                .get("rackmains_battery_runtime_remaining_seconds")
                .map(Vec::as_slice)
            {
                None => None,
                Some([value]) => Some(*value as i64),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [rackmains_battery_runtime_remaining_seconds] is absent or not one value"
                            .to_string(),
                    })
                }
            },
            rackmains_battery_energy_remaining_pct: match tensors
                .get("rackmains_battery_energy_remaining_pct")
                .map(Vec::as_slice)
            {
                None => None,
                Some([value]) => Some(*value as i64),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [rackmains_battery_energy_remaining_pct] is absent or not one value".to_string(),
                    })
                }
            },
            rackmains_battery_energy_used_wh: match tensors.get("rackmains_battery_energy_used_wh").map(Vec::as_slice) {
                None => None,
                Some([value]) => Some(*value),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [rackmains_battery_energy_used_wh] is absent or not one value".to_string(),
                    })
                }
            },
            rackmains_model_refit_due: match tensors.get("rackmains_model_refit_due").map(Vec::as_slice) {
                None => None,
                Some([value]) => Some(*value as i64),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [rackmains_model_refit_due] is absent or not one value".to_string(),
                    })
                }
            },
            rackmains_model_refit_reason_code: match tensors.get("rackmains_model_refit_reason_code").map(Vec::as_slice)
            {
                None => None,
                Some([value]) => Some(*value as i64),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [rackmains_model_refit_reason_code] is absent or not one value".to_string(),
                    })
                }
            },
            rackmains_battery_state_out: tensors.get("rackmains_battery_state_out").cloned(),
        })
    }
}

pub fn load(directory: &Path) -> Result<Model, ModelError> {
    let model = Model::load(directory)?;
    let signature = model.signature();
    let names = |section: &str, required: bool| -> Vec<&str> {
        signature[section]
            .as_array()
            .into_iter()
            .flatten()
            .filter(|entry| !required || entry["parameters"]["required"] == true)
            .filter_map(|entry| entry["name"].as_str())
            .collect()
    };
    let slots = signature["parameters"]["state"].as_array().map_or(0, Vec::len);
    if model.info().name != NAME
        || slots != STATE_SLOTS
        || names("inputs", false) != INPUT_NAMES
        || names("outputs", false) != OUTPUT_NAMES
        || names("inputs", true) != REQUIRED_INPUT_NAMES
        || names("outputs", true) != REQUIRED_OUTPUT_NAMES
    {
        return Err(ModelError {
            kind: Kind::Signature,
            gate: "contract".to_string(),
            cause: format!("signature differs from the compiled constants [{NAME}]"),
        });
    }
    Ok(model)
}
