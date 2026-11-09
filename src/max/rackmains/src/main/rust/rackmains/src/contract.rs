use serde::{Deserialize, Serialize};

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
