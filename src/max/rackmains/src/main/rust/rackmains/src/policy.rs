use std::path::Path;
use std::time::Duration;

use serde_json::{Map, Value};

use crate::model::battery::{load, Request, Response};
use crate::model::loader::{Info, Model};

pub const SHED_BATTERY_FLOOR: Duration = Duration::from_secs(30);
pub const SHED_BATTERY_CEILING: Duration = Duration::from_secs(3600);
pub const RESTORE_MAINS_FLOOR: Duration = Duration::from_secs(60);
pub const RESTORE_MAINS_CEILING: Duration = Duration::from_hours(24);
pub const RUNTIME_REMAINING_CEILING: Duration = Duration::from_hours(24);

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Policy {
    pub shed_battery: Duration,
    pub restore_mains: Duration,
    pub shed_runtime: Option<Duration>,
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Estimate {
    pub runtime_remaining: Option<Duration>,
    pub energy_remaining_pct: Option<i64>,
}

impl Policy {
    pub fn fields(&self) -> Vec<(&'static str, String)> {
        vec![
            ("shed_battery", format!("{}s", self.shed_battery.as_secs())),
            ("restore_mains", format!("{}s", self.restore_mains.as_secs())),
            (
                "shed_runtime",
                self.shed_runtime
                    .map_or_else(|| "none".to_string(), |runtime| format!("{}s", runtime.as_secs())),
            ),
        ]
    }
}

impl TryFrom<&Response> for Policy {
    type Error = String;

    fn try_from(response: &Response) -> Result<Self, Self::Error> {
        let seconds = |name: &str, value: i64, floor: Duration, ceiling: Duration| {
            let duration = u64::try_from(value)
                .map(Duration::from_secs)
                .map_err(|_| format!("guard threshold [{name}] is negative [{value}]"))?;
            if duration < floor || duration > ceiling {
                return Err(format!(
                    "guard threshold [{name}] [{value}] outside [{}] to [{}]",
                    floor.as_secs(),
                    ceiling.as_secs()
                ));
            }
            Ok(duration)
        };
        let shed_battery = seconds(
            crate::metrics::GUARD_SHED_BATTERY,
            response.rackmains_guard_shed_battery_seconds,
            SHED_BATTERY_FLOOR,
            SHED_BATTERY_CEILING,
        )?;
        let restore_mains = seconds(
            crate::metrics::GUARD_RESTORE_MAINS,
            response.rackmains_guard_restore_mains_seconds,
            RESTORE_MAINS_FLOOR,
            RESTORE_MAINS_CEILING,
        )?;
        let shed_runtime = response
            .rackmains_guard_shed_runtime_seconds
            .map(|value| seconds(crate::metrics::GUARD_SHED_RUNTIME, value, Duration::ZERO, shed_battery))
            .transpose()?;
        Ok(Self {
            shed_battery,
            restore_mains,
            shed_runtime,
        })
    }
}

impl TryFrom<&Response> for Estimate {
    type Error = String;

    fn try_from(response: &Response) -> Result<Self, Self::Error> {
        let runtime_remaining = response
            .rackmains_battery_runtime_remaining_seconds
            .map(|value| {
                u64::try_from(value)
                    .map(Duration::from_secs)
                    .ok()
                    .filter(|duration| *duration <= RUNTIME_REMAINING_CEILING)
                    .ok_or_else(|| {
                        format!(
                            "estimate [rackmains_battery_runtime_remaining_seconds] [{value}] outside [0] to [{}]",
                            RUNTIME_REMAINING_CEILING.as_secs()
                        )
                    })
            })
            .transpose()?;
        let energy_remaining_pct = response
            .rackmains_battery_energy_remaining_pct
            .map(|value| {
                if (0..=100).contains(&value) {
                    Ok(value)
                } else {
                    Err(format!(
                        "estimate [rackmains_battery_energy_remaining_pct] [{value}] outside [0] to [100]"
                    ))
                }
            })
            .transpose()?;
        Ok(Self {
            runtime_remaining,
            energy_remaining_pct,
        })
    }
}

pub struct Answer {
    pub policy: Policy,
    pub estimate: Estimate,
    pub response: Response,
}

pub struct Loaded {
    model: Model,
}

impl Loaded {
    pub fn info(&self) -> &Info {
        self.model.info()
    }

    pub fn state_names(&self) -> Vec<String> {
        self.model.signature()["parameters"]["state"]
            .as_array()
            .map(|slots| {
                slots
                    .iter()
                    .filter_map(|slot| slot["name"].as_str().map(str::to_string))
                    .collect()
            })
            .unwrap_or_default()
    }

    pub fn call(&self, request: Request) -> Result<Answer, String> {
        let outputs = self.model.predict(&request.into()).map_err(|error| error.to_string())?;
        let response = Response::try_from(outputs).map_err(|error| error.to_string())?;
        let policy = Policy::try_from(&response)?;
        let estimate = Estimate::try_from(&response)?;
        Ok(Answer {
            policy,
            estimate,
            response,
        })
    }
}

pub fn state_to_object(names: &[String], state: &[f64]) -> Value {
    if names.len() != state.len() {
        return Value::from(state.to_vec());
    }
    Value::Object(
        names
            .iter()
            .zip(state)
            .map(|(name, value)| (name.clone(), Value::from(*value)))
            .collect::<Map<String, Value>>(),
    )
}

pub fn object_to_state(names: &[String], value: &Value) -> Option<Vec<f64>> {
    if names.is_empty() {
        return None;
    }
    names.iter().map(|name| value.get(name)?.as_f64()).collect()
}

pub fn load_model(directory: &Path) -> Result<(Loaded, Policy), String> {
    let loaded = Loaded {
        model: load(directory).map_err(|error| error.to_string())?,
    };
    let initial = loaded.call(Request {
        clock_epoch_seconds: 0.0,
        rackmains_output_load_pct: 0,
        rackmains_mains_failed: 0,
        rackmains_ups_calibrating: None,
        rackmains_battery_low: None,
        rackmains_battery_volts: None,
        rackmains_battery_replace_due: None,
        rackmains_battery_age_days: None,
        rackmains_read_failures: None,
        rackmains_battery_state_in: None,
    })?;
    Ok((loaded, initial.policy))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::loader::Kind;

    fn embedded() -> std::path::PathBuf {
        Path::new(env!("CARGO_MANIFEST_DIR")).join("../../../build/resources/model/battery")
    }

    fn response(shed_battery: i64) -> Response {
        Response {
            rackmains_guard_shed_battery_seconds: shed_battery,
            rackmains_guard_restore_mains_seconds: 300,
            rackmains_guard_shed_runtime_seconds: None,
            rackmains_battery_runtime_remaining_seconds: None,
            rackmains_battery_energy_remaining_pct: None,
            rackmains_battery_energy_used_wh: None,
            rackmains_model_refit_due: None,
            rackmains_model_refit_reason_code: None,
            rackmains_battery_state_out: None,
        }
    }

    #[test]
    fn the_embedded_model_replays_its_golden_file() {
        load(&embedded()).unwrap().verify().unwrap();
    }

    #[test]
    fn the_embedded_model_gives_a_policy() {
        let (_, policy) = load_model(&embedded()).unwrap();
        assert!(!policy.shed_battery.is_zero());
        assert!(!policy.restore_mains.is_zero());
    }

    fn with(mutate: impl FnOnce(&mut Response)) -> Response {
        let mut response = response(120);
        mutate(&mut response);
        response
    }

    #[test]
    fn a_response_converts_each_threshold_to_a_duration() {
        let policy = Policy::try_from(&with(|response| {
            response.rackmains_guard_shed_runtime_seconds = Some(45);
        }))
        .unwrap();
        assert_eq!(Duration::from_secs(120), policy.shed_battery);
        assert_eq!(Duration::from_secs(300), policy.restore_mains);
        assert_eq!(Some(Duration::from_secs(45)), policy.shed_runtime);
    }

    #[test]
    fn a_threshold_outside_its_bounds_is_refused_and_one_on_a_bound_is_not() {
        let shed = |value: i64| Policy::try_from(&response(value));
        let restore =
            |value: i64| Policy::try_from(&with(|response| response.rackmains_guard_restore_mains_seconds = value));
        let runtime = |value: i64| {
            Policy::try_from(&with(|response| {
                response.rackmains_guard_shed_runtime_seconds = Some(value);
            }))
        };
        let seconds = |duration: Duration| i64::try_from(duration.as_secs()).unwrap();
        assert!(shed(seconds(SHED_BATTERY_FLOOR)).is_ok());
        assert!(shed(seconds(SHED_BATTERY_FLOOR) - 1).is_err());
        assert!(shed(seconds(SHED_BATTERY_CEILING)).is_ok());
        assert!(shed(seconds(SHED_BATTERY_CEILING) + 1).is_err());
        assert!(restore(seconds(RESTORE_MAINS_FLOOR)).is_ok());
        assert!(restore(seconds(RESTORE_MAINS_FLOOR) - 1).is_err());
        assert!(restore(seconds(RESTORE_MAINS_CEILING)).is_ok());
        assert!(restore(seconds(RESTORE_MAINS_CEILING) + 1).is_err());
        assert!(runtime(0).is_ok());
        assert!(runtime(120).is_ok());
        assert!(runtime(121).is_err());
        assert!(shed(-1).is_err());
        assert!(runtime(-1).is_err());
    }

    #[test]
    fn an_estimate_is_validated_and_absent_when_the_model_gives_none() {
        assert_eq!(Estimate::default(), Estimate::try_from(&response(120)).unwrap());
        let estimate = Estimate::try_from(&with(|response| {
            response.rackmains_battery_runtime_remaining_seconds = Some(600);
            response.rackmains_battery_energy_remaining_pct = Some(40);
        }))
        .unwrap();
        assert_eq!(Some(Duration::from_secs(600)), estimate.runtime_remaining);
        assert_eq!(Some(40), estimate.energy_remaining_pct);
        for bad in [
            with(|response| response.rackmains_battery_runtime_remaining_seconds = Some(-1)),
            with(|response| {
                response.rackmains_battery_runtime_remaining_seconds =
                    Some(i64::try_from(RUNTIME_REMAINING_CEILING.as_secs()).unwrap() + 1);
            }),
            with(|response| response.rackmains_battery_energy_remaining_pct = Some(101)),
            with(|response| response.rackmains_battery_energy_remaining_pct = Some(-1)),
        ] {
            assert!(Estimate::try_from(&bad).is_err());
        }
    }

    #[test]
    fn state_round_trips_through_its_named_object_in_slot_order() {
        let names: Vec<String> = ["a", "b", "c"].iter().map(|name| (*name).to_string()).collect();
        let object = state_to_object(&names, &[1.5, 0.0, 1_793_355_329.0]);
        assert_eq!(object.to_string(), r#"{"a":1.5,"b":0.0,"c":1793355329.0}"#);
        assert_eq!(object_to_state(&names, &object), Some(vec![1.5, 0.0, 1_793_355_329.0]));
        assert_eq!(object_to_state(&names, &serde_json::json!({"a": 1.0})), None);
        assert_eq!(object_to_state(&[], &object), None);
        assert_eq!(state_to_object(&names, &[1.0]), serde_json::json!([1.0]));
    }

    #[test]
    fn the_embedded_model_names_its_six_state_slots() {
        let (loaded, _) = load_model(&embedded()).unwrap();
        let names = loaded.state_names();
        assert_eq!(names.len(), crate::model::battery::STATE_SLOTS);
        assert_eq!(names[4], "history_known");
    }

    #[test]
    fn a_loaded_model_answers_a_request() {
        let (loaded, _) = load_model(&embedded()).unwrap();
        let answer = loaded
            .call(Request {
                clock_epoch_seconds: 1.0,
                rackmains_output_load_pct: 13,
                rackmains_mains_failed: 1,
                rackmains_ups_calibrating: None,
                rackmains_battery_low: None,
                rackmains_battery_volts: None,
                rackmains_battery_replace_due: None,
                rackmains_battery_age_days: None,
                rackmains_read_failures: None,
                rackmains_battery_state_in: None,
            })
            .unwrap();
        assert!(!answer.policy.shed_battery.is_zero());
        assert!(!loaded.info().name.is_empty());
    }

    #[test]
    fn a_signature_that_differs_from_the_compiled_constants_is_refused() {
        use serde_json::Value;
        use sha2::{Digest, Sha256};
        use std::fmt::Write;

        let directory = std::env::temp_dir().join(format!("rackmains-signature-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&directory);
        std::fs::create_dir_all(&directory).unwrap();
        for entry in std::fs::read_dir(embedded()).unwrap() {
            let path = entry.unwrap().path();
            std::fs::copy(&path, directory.join(path.file_name().unwrap())).unwrap();
        }
        let mut signature: Value =
            serde_json::from_slice(&std::fs::read(directory.join("signature.json")).unwrap()).unwrap();
        let mut extra = signature["inputs"][0].clone();
        extra["name"] = Value::from("extra_in");
        signature["inputs"].as_array_mut().unwrap().push(extra);
        let bytes = serde_json::to_vec(&signature).unwrap();
        std::fs::write(directory.join("signature.json"), &bytes).unwrap();
        let mut manifest: Value =
            serde_json::from_slice(&std::fs::read(directory.join("project.json")).unwrap()).unwrap();
        let digest = Sha256::digest(&bytes).iter().fold(String::new(), |mut out, byte| {
            let _ = write!(out, "{byte:02x}");
            out
        });
        manifest["files"]["signature.json"] = Value::from(digest);
        let manifest_bytes = serde_json::to_vec(&manifest).unwrap();
        std::fs::write(directory.join("project.json"), &manifest_bytes).unwrap();
        let mut release: Value =
            serde_json::from_slice(&std::fs::read(directory.join("release.json")).unwrap()).unwrap();
        release["content_sha256"] = Value::from(Sha256::digest(&manifest_bytes).iter().fold(
            String::new(),
            |mut out, byte| {
                let _ = write!(out, "{byte:02x}");
                out
            },
        ));
        std::fs::write(directory.join("release.json"), serde_json::to_vec(&release).unwrap()).unwrap();
        let error = load(&directory).err().unwrap();
        std::fs::remove_dir_all(&directory).unwrap();
        assert_eq!((Kind::Signature, "contract"), (error.kind, error.gate.as_str()));
    }

    #[test]
    fn a_missing_model_is_an_error() {
        assert!(load_model(Path::new("/nonexistent")).is_err());
    }
}
