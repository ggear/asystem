use serde::{Deserialize, Serialize};

pub const NAME: &str = "rackmains_ups_battery";
pub const STATE_SLOTS: usize = 6;
pub const INPUT_NAMES: &[&str] = &[
    "rackmains_clock_epoch_seconds",
    "rackmains_output_utilisation_pct",
    "rackmains_ups_on_battery",
    "rackmains_battery_replace",
    "rackmains_model_state_in",
];
pub const OUTPUT_NAMES: &[&str] = &[
    "rackmains_guard_shed_max_seconds",
    "rackmains_guard_halt_max_seconds",
    "rackmains_guard_mains_stable_seconds",
    "rackmains_guard_halt_delay_seconds",
    "rackmains_guard_shed_lead_seconds",
    "rackmains_guard_halt_lead_seconds",
    "rackmains_battery_remaining_pct",
    "rackmains_battery_remaining_seconds",
    "rackmains_model_energy_used_wh",
    "rackmains_model_history_known",
    "rackmains_model_recalibrate",
    "rackmains_model_state_out",
];
pub const REQUIRED_INPUT_NAMES: &[&str] = &[
    "rackmains_clock_epoch_seconds",
    "rackmains_output_utilisation_pct",
    "rackmains_ups_on_battery",
    "rackmains_battery_replace",
];
pub const REQUIRED_OUTPUT_NAMES: &[&str] = &[
    "rackmains_guard_shed_max_seconds",
    "rackmains_guard_halt_max_seconds",
    "rackmains_guard_mains_stable_seconds",
    "rackmains_guard_halt_delay_seconds",
];

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Request {
    pub rackmains_clock_epoch_seconds: f64,
    pub rackmains_output_utilisation_pct: i64,
    pub rackmains_ups_on_battery: i64,
    pub rackmains_battery_replace: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_model_state_in: Option<Vec<f64>>,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Response {
    pub rackmains_guard_shed_max_seconds: i64,
    pub rackmains_guard_halt_max_seconds: i64,
    pub rackmains_guard_mains_stable_seconds: i64,
    pub rackmains_guard_halt_delay_seconds: i64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_guard_shed_lead_seconds: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_guard_halt_lead_seconds: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_battery_remaining_pct: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_battery_remaining_seconds: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_model_energy_used_wh: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_model_history_known: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_model_recalibrate: Option<i64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub rackmains_model_state_out: Option<Vec<f64>>,
}
