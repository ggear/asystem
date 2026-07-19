use std::fs;
use std::path::Path;

use log::info;
use serde::Deserialize;

use crate::driver::Rom;

#[derive(Debug, Clone)]
pub struct SensorConfig {
    pub unique_id: String,
    pub rom: Rom,
}

#[derive(Deserialize)]
struct RawSensor {
    unique_id: String,
    #[serde(alias = "connection_mac")]
    rom: String,
}

pub fn load_sensors(path: &Path) -> Result<Vec<SensorConfig>, String> {
    let data =
        fs::read_to_string(path).map_err(|err| format!("failed to read sensors file [{}]: {err}", path.display()))?;
    let raw: Vec<RawSensor> = serde_json::from_str(&data)
        .map_err(|err| format!("failed to parse sensors file [{}]: {err}", path.display()))?;
    let sensors: Result<Vec<SensorConfig>, String> = raw
        .into_iter()
        .map(|sensor| {
            let code = sensor.rom.trim_start_matches("0x").trim_start_matches("0X");
            code.parse::<Rom>()
                .map_err(|err| format!("invalid rom [{code}] for sensor [{}]: {err}", sensor.unique_id))
                .map(|rom| SensorConfig {
                    unique_id: sensor.unique_id,
                    rom,
                })
        })
        .collect();
    if let Ok(ref list) = sensors {
        info!("loaded {} sensor(s) from [{}]", list.len(), path.display());
        for sensor in list {
            info!("  sensor [{}] rom [{}]", sensor.unique_id, sensor.rom);
        }
    }
    sensors
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    fn write_json(json: &str) -> NamedTempFile {
        let mut file = NamedTempFile::new().unwrap();
        file.write_all(json.as_bytes()).unwrap();
        file
    }

    #[test]
    fn load_sensors_parses_valid_file() {
        let file = write_json(
            r#"[
            {"unique_id": "utility_temperature", "rom": "28FF641E870006AE"}
        ]"#,
        );
        let sensors = load_sensors(file.path()).unwrap();
        assert_eq!(sensors.len(), 1);
        assert_eq!(sensors[0].unique_id, "utility_temperature");
        assert_eq!(sensors[0].rom.to_string(), "28FF641E870006AE");
    }

    #[test]
    fn load_sensors_accepts_0x_prefix() {
        let file = write_json(
            r#"[
            {"unique_id": "foo", "rom": "0x28FF641E870006AE"}
        ]"#,
        );
        let sensors = load_sensors(file.path()).unwrap();
        assert_eq!(sensors[0].rom.to_string(), "28FF641E870006AE");
    }

    #[test]
    fn load_sensors_accepts_connection_mac_alias() {
        let file = write_json(
            r#"[
            {"unique_id": "foo", "connection_mac": "28FF641E870006AE"}
        ]"#,
        );
        let sensors = load_sensors(file.path()).unwrap();
        assert_eq!(sensors[0].unique_id, "foo");
    }

    #[test]
    fn load_sensors_accepts_lowercase_hex() {
        let file = write_json(
            r#"[
            {"unique_id": "foo", "rom": "28ff641e870006ae"}
        ]"#,
        );
        let sensors = load_sensors(file.path()).unwrap();
        assert_eq!(sensors[0].rom.to_string(), "28FF641E870006AE");
    }

    #[test]
    fn load_sensors_errors_on_missing_file() {
        let err = load_sensors(Path::new("/nonexistent/sensors.json")).unwrap_err();
        assert!(err.contains("failed to read"));
    }

    #[test]
    fn load_sensors_errors_on_invalid_json() {
        let file = write_json("not json");
        let err = load_sensors(file.path()).unwrap_err();
        assert!(err.contains("failed to parse"));
    }

    #[test]
    fn load_sensors_errors_on_invalid_rom() {
        let file = write_json(r#"[{"unique_id": "foo", "rom": "ZZZZ"}]"#);
        let err = load_sensors(file.path()).unwrap_err();
        assert!(err.contains("invalid rom"));
    }
}
