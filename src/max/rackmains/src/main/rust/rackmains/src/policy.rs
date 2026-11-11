use std::path::Path;
use std::time::Duration;

use crate::model::battery::{load, Request, Response};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Policy {
    pub shed_max: Duration,
    pub halt_max: Duration,
    pub mains_stable: Duration,
    pub halt_delay: Duration,
    pub shed_lead: Option<Duration>,
    pub halt_lead: Option<Duration>,
}

impl TryFrom<Response> for Policy {
    type Error = String;

    fn try_from(response: Response) -> Result<Self, Self::Error> {
        let seconds = |name: &str, value: i64| {
            u64::try_from(value)
                .map(Duration::from_secs)
                .map_err(|_| format!("guard threshold [{name}] is negative [{value}]"))
        };
        Ok(Self {
            shed_max: seconds("guard_shed_max_seconds", response.guard_shed_max_seconds)?,
            halt_max: seconds("guard_halt_max_seconds", response.guard_halt_max_seconds)?,
            mains_stable: seconds("guard_mains_stable_seconds", response.guard_mains_stable_seconds)?,
            halt_delay: seconds("guard_halt_delay_seconds", response.guard_halt_delay_seconds)?,
            shed_lead: response
                .guard_shed_lead_seconds
                .map(|value| seconds("guard_shed_lead_seconds", value))
                .transpose()?,
            halt_lead: response
                .guard_halt_lead_seconds
                .map(|value| seconds("guard_halt_lead_seconds", value))
                .transpose()?,
        })
    }
}

pub fn load_policy(directory: &Path) -> Result<Policy, String> {
    let model = load(directory).map_err(|error| error.to_string())?;
    let request = Request {
        clock_epoch_seconds: 0.0,
        output_utilisation_pct: 0,
        ups_on_battery: 0,
        battery_replace: 0,
        model_state_in: None,
    };
    let outputs = model.predict(&request.into()).map_err(|error| error.to_string())?;
    Response::try_from(outputs)
        .map_err(|error| error.to_string())
        .and_then(Policy::try_from)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn embedded() -> std::path::PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../build/resources/model/battery")
    }

    fn response(shed_max: i64) -> Response {
        Response {
            guard_shed_max_seconds: shed_max,
            guard_halt_max_seconds: 2,
            guard_mains_stable_seconds: 3,
            guard_halt_delay_seconds: 4,
            guard_shed_lead_seconds: None,
            guard_halt_lead_seconds: Some(5),
            battery_remaining_pct: None,
            battery_remaining_seconds: None,
            model_energy_used_wh: None,
            model_history_known: None,
            model_recalibrate: None,
            model_state_out: None,
        }
    }

    #[test]
    fn the_embedded_model_replays_its_golden_file() {
        load(&embedded()).unwrap().verify().unwrap();
    }

    #[test]
    fn the_embedded_model_gives_a_policy() {
        let policy = load_policy(&embedded()).unwrap();
        assert!(policy.shed_max <= policy.halt_max);
        assert!(!policy.mains_stable.is_zero());
    }

    #[test]
    fn a_response_converts_each_threshold_to_a_duration() {
        let policy = Policy::try_from(response(1)).unwrap();
        assert_eq!(Duration::from_secs(1), policy.shed_max);
        assert_eq!(None, policy.shed_lead);
        assert_eq!(Some(Duration::from_secs(5)), policy.halt_lead);
    }

    #[test]
    fn a_negative_threshold_is_refused() {
        assert!(Policy::try_from(response(-1)).is_err());
    }

    #[test]
    fn a_missing_model_is_an_error() {
        assert!(load_policy(Path::new("/nonexistent")).is_err());
    }
}
