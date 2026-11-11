////////////////////////////////////////////////////////////////////////////////
// WARNING: This file is written by the build process, any manual edits will be lost!
////////////////////////////////////////////////////////////////////////////////

// project rackmains_ups_battery sha256 c0547c3deec2e6b300444dab3117d7a5e68d9082d021f3ef2670e0f2ee172262

use std::path::Path;

use serde::{Deserialize, Serialize};

use super::loader::{Kind, Model, ModelError, Tensors};

pub const NAME: &str = "rackmains_ups_battery";
pub const STATE_SLOTS: usize = 6;
pub const INPUT_NAMES: &[&str] = &[
    "clock_epoch_seconds",
    "output_utilisation_pct",
    "ups_on_battery",
    "battery_replace",
    "model_state_in",
];
pub const OUTPUT_NAMES: &[&str] = &[
    "guard_shed_max_seconds",
    "guard_halt_max_seconds",
    "guard_mains_stable_seconds",
    "guard_halt_delay_seconds",
    "guard_shed_lead_seconds",
    "guard_halt_lead_seconds",
    "battery_remaining_pct",
    "battery_remaining_seconds",
    "model_energy_used_wh",
    "model_history_known",
    "model_recalibrate",
    "model_state_out",
];
pub const REQUIRED_INPUT_NAMES: &[&str] = &[
    "clock_epoch_seconds",
    "output_utilisation_pct",
    "ups_on_battery",
    "battery_replace",
];
pub const REQUIRED_OUTPUT_NAMES: &[&str] = &[
    "guard_shed_max_seconds",
    "guard_halt_max_seconds",
    "guard_mains_stable_seconds",
    "guard_halt_delay_seconds",
];

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Request {
    pub clock_epoch_seconds: f64,
    pub output_utilisation_pct: i64,
    pub ups_on_battery: i64,
    pub battery_replace: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model_state_in: Option<Vec<f64>>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Response {
    pub guard_shed_max_seconds: i64,
    pub guard_halt_max_seconds: i64,
    pub guard_mains_stable_seconds: i64,
    pub guard_halt_delay_seconds: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub guard_shed_lead_seconds: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub guard_halt_lead_seconds: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub battery_remaining_pct: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub battery_remaining_seconds: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model_energy_used_wh: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model_history_known: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model_recalibrate: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub model_state_out: Option<Vec<f64>>,
}

impl From<Request> for Tensors {
    fn from(request: Request) -> Self {
        let mut tensors = Tensors::new();
        tensors.insert("clock_epoch_seconds".to_string(), vec![request.clock_epoch_seconds]);
        tensors.insert(
            "output_utilisation_pct".to_string(),
            vec![serde_json::Number::from(request.output_utilisation_pct)
                .as_f64()
                .unwrap_or(f64::NAN)],
        );
        tensors.insert(
            "ups_on_battery".to_string(),
            vec![serde_json::Number::from(request.ups_on_battery)
                .as_f64()
                .unwrap_or(f64::NAN)],
        );
        tensors.insert(
            "battery_replace".to_string(),
            vec![serde_json::Number::from(request.battery_replace)
                .as_f64()
                .unwrap_or(f64::NAN)],
        );
        if let Some(value) = request.model_state_in {
            tensors.insert("model_state_in".to_string(), value);
        }
        tensors
    }
}

impl TryFrom<Tensors> for Response {
    type Error = ModelError;

    fn try_from(tensors: Tensors) -> Result<Self, Self::Error> {
        Ok(Self {
            guard_shed_max_seconds: match tensors.get("guard_shed_max_seconds").map(Vec::as_slice) {
                Some([value]) => *value as i64,
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [guard_shed_max_seconds] is absent or not one value".to_string(),
                    })
                }
            },
            guard_halt_max_seconds: match tensors.get("guard_halt_max_seconds").map(Vec::as_slice) {
                Some([value]) => *value as i64,
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [guard_halt_max_seconds] is absent or not one value".to_string(),
                    })
                }
            },
            guard_mains_stable_seconds: match tensors.get("guard_mains_stable_seconds").map(Vec::as_slice) {
                Some([value]) => *value as i64,
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [guard_mains_stable_seconds] is absent or not one value".to_string(),
                    })
                }
            },
            guard_halt_delay_seconds: match tensors.get("guard_halt_delay_seconds").map(Vec::as_slice) {
                Some([value]) => *value as i64,
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [guard_halt_delay_seconds] is absent or not one value".to_string(),
                    })
                }
            },
            guard_shed_lead_seconds: match tensors.get("guard_shed_lead_seconds").map(Vec::as_slice) {
                None => None,
                Some([value]) => Some(*value as i64),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [guard_shed_lead_seconds] is absent or not one value".to_string(),
                    })
                }
            },
            guard_halt_lead_seconds: match tensors.get("guard_halt_lead_seconds").map(Vec::as_slice) {
                None => None,
                Some([value]) => Some(*value as i64),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [guard_halt_lead_seconds] is absent or not one value".to_string(),
                    })
                }
            },
            battery_remaining_pct: match tensors.get("battery_remaining_pct").map(Vec::as_slice) {
                None => None,
                Some([value]) => Some(*value as i64),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [battery_remaining_pct] is absent or not one value".to_string(),
                    })
                }
            },
            battery_remaining_seconds: match tensors.get("battery_remaining_seconds").map(Vec::as_slice) {
                None => None,
                Some([value]) => Some(*value as i64),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [battery_remaining_seconds] is absent or not one value".to_string(),
                    })
                }
            },
            model_energy_used_wh: match tensors.get("model_energy_used_wh").map(Vec::as_slice) {
                None => None,
                Some([value]) => Some(*value),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [model_energy_used_wh] is absent or not one value".to_string(),
                    })
                }
            },
            model_history_known: match tensors.get("model_history_known").map(Vec::as_slice) {
                None => None,
                Some([value]) => Some(*value as i64),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [model_history_known] is absent or not one value".to_string(),
                    })
                }
            },
            model_recalibrate: match tensors.get("model_recalibrate").map(Vec::as_slice) {
                None => None,
                Some([value]) => Some(*value as i64),
                _ => {
                    return Err(ModelError {
                        kind: Kind::Signature,
                        gate: "response".to_string(),
                        cause: "output [model_recalibrate] is absent or not one value".to_string(),
                    })
                }
            },
            model_state_out: tensors.get("model_state_out").cloned(),
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
