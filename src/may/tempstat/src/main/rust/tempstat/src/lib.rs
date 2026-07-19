//! State topic payload (`tempstat/$HOST/data`, retained, QoS 1):
//! `{ "data_<unique_id>_celsius": <f64>, ..., "run_success": <bool>, "run_milliseconds": <u64>, "run_timestamp": <str> }`
//! Per-sensor `data_*_celsius` fields are absent when a sensor fails; `run_success` is false if any sensor failed.

pub mod broker;
pub mod config;
pub mod driver;

use std::path::PathBuf;
use std::sync::LazyLock;
use std::thread;
use std::time::{Duration, Instant, SystemTime};

use clap::builder::{PossibleValuesParser, TypedValueParser};
use clap::Parser;
use log::{debug, error, info, warn, LevelFilter};
use serde_json::{json, Map, Value};

use crate::broker::{MqttPublisher, Publisher};
use crate::config::{load_sensors, SensorConfig};
use crate::driver::ds2480b::Ds2480b;
use crate::driver::ds9097::Ds9097;
use crate::driver::sensor::Ds18b20;
use crate::driver::uart::SerialUart;
use crate::driver::OneWire;

static LEVEL_NAMES: LazyLock<Vec<String>> =
    LazyLock::new(|| LevelFilter::iter().map(|level| level.as_str().to_lowercase()).collect());

const STATE_TOPIC: &str = "tempstat/$HOST/data";
const STATUS_TOPIC: &str = "tempstat/$HOST/status";

#[derive(Debug, Parser)]
#[command(name = "tempstat", about = "Run the tempstat temperature-probe reader", version)]
pub struct Cli {
    #[arg(short = 'P', long = "poll-period", value_name = "PERIOD", default_value = "0")]
    pub poll_period: String,
    #[arg(short = 'D', long = "device", value_name = "PATH", default_value = "/dev/ttyUSB0")]
    pub device: String,
    #[arg(short = 'T', long = "timeout", value_name = "PERIOD", default_value = "1s")]
    pub timeout: String,
    #[arg(
        short = 'B',
        long = "broker-host",
        value_name = "HOST",
        env = "BROKER_HOST",
        default_value = "localhost"
    )]
    pub broker_host: String,
    #[arg(
        long = "broker-port",
        value_name = "PORT",
        env = "BROKER_PORT",
        default_value = "1883"
    )]
    pub broker_port: u16,
    #[arg(
        long = "broker-token",
        value_name = "TOKEN",
        env = "BROKER_TOKEN",
        default_value = ""
    )]
    pub broker_token: String,
    #[arg(
        short = 'S',
        long = "sensors",
        value_name = "PATH",
        default_value = "/asystem/etc/sensors.json"
    )]
    pub sensors: PathBuf,
    #[arg(
        short = 'L',
        long = "log-level",
        value_name = "LEVEL",
        default_value = "info",
        value_parser = PossibleValuesParser::new(LEVEL_NAMES.iter().map(|name| name.as_str()))
            .map(|name| name.parse::<LevelFilter>().unwrap())
    )]
    pub log_level: LevelFilter,
}

impl Cli {
    pub fn run(&self) -> Result<(), String> {
        let version = std::env::var("SERVICE_VERSION_ABSOLUTE").unwrap_or_else(|_| "unknown".to_string());
        let period = parse_duration(&self.poll_period)?;
        let log_level = if period.is_zero() {
            self.log_level.max(LevelFilter::Debug)
        } else {
            self.log_level
        };
        let _ = env_logger::Builder::new()
            .filter_level(log_level)
            .format_timestamp_millis()
            .try_init();
        let timeout = parse_duration(&self.timeout)?;
        let sensors = load_sensors(&self.sensors)?;
        let mock = std::env::var("TEMPSTAT_MOCK").as_deref() == Ok("1");
        info!(
            "starting tempstat [{}] with device [{}] ({}), timeout [{timeout:?}], poll period [{period:?}], broker [{}:{}], {} sensor(s)",
            version,
            self.device,
            if mock { "mock" } else { "real" },
            self.broker_host,
            self.broker_port,
            sensors.len()
        );
        let host = resolve_host();
        let state_topic = STATE_TOPIC.replace("$HOST", &host);
        let status_topic = STATUS_TOPIC.replace("$HOST", &host);
        loop {
            let mut publisher =
                match MqttPublisher::new(&self.broker_host, self.broker_port, &self.broker_token, &status_topic) {
                    Ok(publisher) => publisher,
                    Err(err) => {
                        if period.is_zero() {
                            return Err(err.to_string());
                        }
                        error!("broker unavailable: {err}, retrying in {period:?}");
                        thread::sleep(period);
                        continue;
                    }
                };
            let mut bus = match self.open_bus(timeout) {
                Ok(bus) => bus,
                Err(err) => {
                    let _ = publisher.close(&status_topic);
                    if period.is_zero() {
                        return Err(format!("failed to open device [{}]: {err}", self.device));
                    }
                    error!("device unavailable [{}]: {err}, retrying in {period:?}", self.device);
                    thread::sleep(period);
                    continue;
                }
            };
            let poll_result = poll(period, &sensors, &mut publisher, bus.as_mut(), &state_topic);
            let close_result = publisher.close(&status_topic).map_err(|err| err.to_string());
            let combined = poll_result.and(close_result);
            if period.is_zero() {
                if let Err(ref err) = combined {
                    error!("{err}");
                }
                return combined;
            }
            if let Err(ref err) = combined {
                error!("{err}, reinitializing in {period:?}");
            }
            thread::sleep(period);
        }
    }

    fn open_bus(&self, timeout: Duration) -> driver::Result<Box<dyn OneWire>> {
        let mut ds2480b = Ds2480b::from_uart(SerialUart::open(&self.device, timeout)?);
        match ds2480b.probe() {
            Ok(()) => {
                info!("selected adapter [ds2480b]");
                Ok(Box::new(ds2480b))
            }
            Err(err) => {
                info!("ds2480b not detected ({err}), probing for ds9097");
                let mut ds9097 = Ds9097::new(ds2480b.into_uart())?;
                ds9097.redetect()?;
                info!("selected adapter [ds9097]");
                Ok(Box::new(ds9097))
            }
        }
    }
}

pub fn resolve_host() -> String {
    let host = std::env::var("TEMPSTAT_HOST")
        .ok()
        .filter(|host| !host.is_empty())
        .or_else(system_hostname)
        .unwrap_or_else(|| "unknown".to_string());
    info!("host resolved to [{host}]");
    host
}

fn system_hostname() -> Option<String> {
    std::process::Command::new("hostname")
        .output()
        .ok()
        .and_then(|output| String::from_utf8(output.stdout).ok())
        .map(|text| text.trim().to_string())
        .filter(|hostname| !hostname.is_empty())
}

pub fn parse_duration(raw: &str) -> Result<Duration, String> {
    let trimmed = raw.trim();
    if trimmed == "0" {
        return Ok(Duration::ZERO);
    }
    humantime::parse_duration(trimmed).map_err(|err| format!("invalid duration [{trimmed}]: {err}"))
}

fn poll<P: Publisher>(
    period: Duration,
    sensors: &[SensorConfig],
    publisher: &mut P,
    bus: &mut (impl OneWire + ?Sized),
    state_topic: &str,
) -> Result<(), String> {
    let mut iteration: u64 = 0;
    loop {
        iteration += 1;
        let success = poll_once(sensors, publisher, bus, state_topic)?;
        if period.is_zero() {
            return Ok(());
        }
        if !success {
            warn!("poll had failures, attempting bus re-detection before next iteration");
            if let Err(err) = bus.redetect() {
                warn!("bus re-detection failed: {err}");
            }
        }
        debug!("sleeping [{period:?}] until iteration [{}]", iteration + 1);
        thread::sleep(period);
    }
}

fn poll_once<P: Publisher>(
    sensors: &[SensorConfig],
    publisher: &mut P,
    bus: &mut (impl OneWire + ?Sized),
    state_topic: &str,
) -> Result<bool, String> {
    let start = Instant::now();
    let timestamp = humantime::format_rfc3339_seconds(SystemTime::now()).to_string();
    let mut fields: Map<String, Value> = Map::new();
    let mut succeeded: u32 = 0;
    let mut failed: u32 = 0;

    for sensor in sensors {
        debug!("reading sensor [{}] rom [{}]", sensor.unique_id, sensor.rom);
        match Ds18b20::attach(bus, Some(sensor.rom)).and_then(|device| device.get_temperature(bus)) {
            Ok(temp) => {
                info!("sensor [{}] rom [{}] = {temp}°C", sensor.unique_id, sensor.rom);
                fields.insert(format!("data_{}_celsius", sensor.unique_id), json!(f64::from(temp)));
                succeeded += 1;
            }
            Err(err) => {
                warn!("sensor [{}] rom [{}] failed: {err}", sensor.unique_id, sensor.rom);
                failed += 1;
            }
        }
    }

    let run_milliseconds = start.elapsed().as_millis() as u64;
    let run_success = failed == 0;
    fields.insert("run_success".into(), json!(run_success));
    fields.insert("run_milliseconds".into(), json!(run_milliseconds));
    fields.insert("run_timestamp".into(), json!(timestamp));

    let payload = Value::Object(fields);
    let payload_bytes = serde_json::to_vec(&payload).map_err(|err| format!("failed to serialize payload: {err}"))?;

    info!("poll complete: {succeeded} ok, {failed} failed, {run_milliseconds}ms");

    publisher
        .publish(state_topic, &payload_bytes)
        .map_err(|err| format!("failed to publish: {err}"))?;

    Ok(run_success)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::broker::mock::MockPublisher;
    use crate::driver::crc8;
    use crate::driver::mock::fsm::FsmUart;
    use crate::driver::mock::MockDs9097;
    use crate::driver::rom::Rom;
    use crate::driver::uart::mock::MockUart;

    const DETECT_READS: [u8; 5] = [0x16, 0x44, 0x5A, 0x00, 0x93];

    fn test_rom() -> Rom {
        "28FF641E870006AE".parse().unwrap()
    }

    fn scratchpad_for(temp: [u8; 2]) -> [u8; 9] {
        let mut scratchpad = [temp[0], temp[1], 0x4B, 0x46, 0x7F, 0xFF, 0x0C, 0x10, 0x00];
        scratchpad[8] = crc8(&scratchpad[..8]);
        scratchpad
    }

    fn queue_match_select(uart: &mut MockUart, rom: &Rom) {
        uart.queue_read(&[0xCD]);
        let mut echo = vec![0x55u8];
        echo.extend_from_slice(&rom.0);
        uart.queue_read(&echo);
    }

    fn queue_sensor_read(uart: &mut MockUart, rom: &Rom, temp: [u8; 2]) {
        let scratchpad = scratchpad_for(temp);
        queue_match_select(uart, rom);
        uart.queue_read(&[0xB4]);
        uart.queue_read(&[0x97]);
        queue_match_select(uart, rom);
        uart.queue_read(&[0xBE]);
        uart.queue_read(&scratchpad);
        queue_match_select(uart, rom);
        uart.queue_read(&[0x44]);
        uart.queue_read(&[0x97]);
        queue_match_select(uart, rom);
        uart.queue_read(&[0xBE]);
        uart.queue_read(&scratchpad);
    }

    fn make_bus() -> Ds2480b<MockUart> {
        let mut uart = MockUart::new();
        uart.queue_read(&DETECT_READS);
        Ds2480b::new(uart).unwrap()
    }

    #[test]
    fn parse_duration_zero_is_zero() {
        assert_eq!(parse_duration("0").unwrap(), Duration::ZERO);
        assert_eq!(parse_duration(" 0 ").unwrap(), Duration::ZERO);
    }

    #[test]
    fn parse_duration_accepts_unit_suffixes() {
        assert_eq!(parse_duration("3s").unwrap(), Duration::from_secs(3));
        assert_eq!(parse_duration("5m").unwrap(), Duration::from_secs(300));
        assert_eq!(parse_duration("1h").unwrap(), Duration::from_secs(3600));
    }

    #[test]
    fn parse_duration_rejects_garbage() {
        assert!(parse_duration("nonsense").is_err());
        assert!(parse_duration("").is_err());
    }

    #[test]
    fn cli_parses_poll_period_flags() {
        assert_eq!(Cli::parse_from(["tempstat", "-P", "10s"]).poll_period, "10s");
        assert_eq!(Cli::parse_from(["tempstat", "--poll-period", "2m"]).poll_period, "2m");
        assert_eq!(Cli::parse_from(["tempstat"]).poll_period, "0");
    }

    #[test]
    fn cli_parses_device_and_timeout_flags() {
        assert_eq!(Cli::parse_from(["tempstat"]).device, "/dev/ttyUSB0");
        assert_eq!(Cli::parse_from(["tempstat"]).timeout, "1s");
        assert_eq!(
            Cli::parse_from(["tempstat", "-D", "/dev/ttyAMA0"]).device,
            "/dev/ttyAMA0"
        );
        assert_eq!(
            Cli::parse_from(["tempstat", "--device", "/dev/ttyS0"]).device,
            "/dev/ttyS0"
        );
        assert_eq!(Cli::parse_from(["tempstat", "-T", "500ms"]).timeout, "500ms");
        assert_eq!(Cli::parse_from(["tempstat", "--timeout", "2s"]).timeout, "2s");
    }

    #[test]
    fn cli_parses_log_level_flags() {
        assert_eq!(Cli::parse_from(["tempstat"]).log_level, LevelFilter::Info);
        assert_eq!(
            Cli::parse_from(["tempstat", "-L", "debug"]).log_level,
            LevelFilter::Debug
        );
        assert_eq!(
            Cli::parse_from(["tempstat", "--log-level", "warn"]).log_level,
            LevelFilter::Warn
        );
        assert_eq!(
            Cli::parse_from(["tempstat", "--log-level", "trace"]).log_level,
            LevelFilter::Trace
        );
        assert!(Cli::try_parse_from(["tempstat", "-L", "verbose"]).is_err());
    }

    #[test]
    fn cli_parses_broker_flags() {
        let cli = Cli::parse_from([
            "tempstat",
            "-B",
            "mqtt.local",
            "--broker-port",
            "8883",
            "--broker-token",
            "secret",
        ]);
        assert_eq!(cli.broker_host, "mqtt.local");
        assert_eq!(cli.broker_port, 8883);
        assert_eq!(cli.broker_token, "secret");
        assert_eq!(Cli::parse_from(["tempstat"]).broker_host, "localhost");
        assert_eq!(Cli::parse_from(["tempstat"]).broker_port, 1883);
    }

    #[test]
    fn cli_parses_sensors_flag() {
        assert_eq!(
            Cli::parse_from(["tempstat", "-S", "/tmp/s.json"]).sensors,
            PathBuf::from("/tmp/s.json")
        );
        assert_eq!(
            Cli::parse_from(["tempstat"]).sensors,
            PathBuf::from("/asystem/etc/sensors.json")
        );
    }

    #[test]
    fn resolve_host_uses_tempstat_host_env() {
        unsafe { std::env::set_var("TEMPSTAT_HOST", "env-host") };
        assert_eq!(resolve_host(), "env-host");
        unsafe { std::env::remove_var("TEMPSTAT_HOST") };
    }

    #[test]
    fn resolve_host_falls_back_to_nonempty() {
        unsafe { std::env::remove_var("TEMPSTAT_HOST") };
        assert!(!resolve_host().is_empty());
    }

    #[test]
    fn poll_once_publishes_combined_json_to_state_topic() {
        let rom = test_rom();
        let mut bus = make_bus();
        queue_sensor_read(&mut bus.uart, &rom, [0x91, 0x01]);
        let sensors = vec![SensorConfig {
            unique_id: "utility_temperature".into(),
            rom,
        }];
        let mut publisher = MockPublisher::new();
        assert!(poll_once(&sensors, &mut publisher, &mut bus, "state").unwrap());
        assert_eq!(publisher.messages.len(), 1);
        let (topic, payload) = &publisher.messages[0];
        assert_eq!(topic, "state");
        let payload: Value = serde_json::from_slice(payload).unwrap();
        assert!((payload["data_utility_temperature_celsius"].as_f64().unwrap() - 25.0625).abs() < 0.001);
        assert_eq!(payload["run_success"], true);
        assert!(payload["run_milliseconds"].as_u64().is_some());
        assert!(payload["run_timestamp"]
            .as_str()
            .is_some_and(|timestamp| timestamp.len() == 20));
    }

    #[test]
    fn poll_once_skips_failed_sensor_and_still_publishes() {
        let rom = test_rom();
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xCF]);
        let sensors = vec![SensorConfig {
            unique_id: "utility_temperature".into(),
            rom,
        }];
        let mut publisher = MockPublisher::new();
        assert!(!poll_once(&sensors, &mut publisher, &mut bus, "state").unwrap());
        assert_eq!(publisher.messages.len(), 1);
        let payload: Value = serde_json::from_slice(&publisher.messages[0].1).unwrap();
        assert!(payload.get("data_utility_temperature_celsius").is_none());
        assert_eq!(payload["run_success"], false);
    }

    #[test]
    fn poll_redetects_on_failure_and_recovers() {
        let rom = test_rom();
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xCF]);
        bus.uart.queue_read(&DETECT_READS);
        queue_sensor_read(&mut bus.uart, &rom, [0x91, 0x01]);
        let sensors = vec![SensorConfig {
            unique_id: "utility_temperature".into(),
            rom,
        }];
        let mut publisher = MockPublisher::new();
        assert!(!poll_once(&sensors, &mut publisher, &mut bus, "state").unwrap());
        bus.redetect().unwrap();
        assert!(poll_once(&sensors, &mut publisher, &mut bus, "state").unwrap());
        assert_eq!(publisher.messages.len(), 2);
        let first: Value = serde_json::from_slice(&publisher.messages[0].1).unwrap();
        assert_eq!(first["run_success"], false);
        assert!(first.get("data_utility_temperature_celsius").is_none());
        let second: Value = serde_json::from_slice(&publisher.messages[1].1).unwrap();
        assert_eq!(second["run_success"], true);
        assert!((second["data_utility_temperature_celsius"].as_f64().unwrap() - 25.0625).abs() < 0.001);
    }

    #[test]
    fn poll_once_reads_sensors_through_dyn_ds9097_bus() {
        let mut bus: Box<dyn OneWire> = Box::new(Ds9097::new(FsmUart::new(MockDs9097::new())).unwrap());
        let sensors = vec![
            SensorConfig {
                unique_id: "rack_top_temperature".into(),
                rom: test_rom(),
            },
            SensorConfig {
                unique_id: "rack_bottom_temperature".into(),
                rom: test_rom(),
            },
        ];
        let mut publisher = MockPublisher::new();
        assert!(poll_once(&sensors, &mut publisher, bus.as_mut(), "state").unwrap());
        let payload: Value = serde_json::from_slice(&publisher.messages[0].1).unwrap();
        assert!((payload["data_rack_top_temperature_celsius"].as_f64().unwrap() - 25.0625).abs() < 0.001);
        assert!((payload["data_rack_bottom_temperature_celsius"].as_f64().unwrap() - 25.0625).abs() < 0.001);
        assert_eq!(payload["run_success"], true);
    }

    #[test]
    fn poll_zero_period_runs_single_iteration() {
        let rom = test_rom();
        let mut bus = make_bus();
        queue_sensor_read(&mut bus.uart, &rom, [0x00, 0x00]);
        let sensors = vec![SensorConfig {
            unique_id: "t".into(),
            rom,
        }];
        let mut publisher = MockPublisher::new();
        poll(Duration::ZERO, &sensors, &mut publisher, &mut bus, "state").unwrap();
        assert_eq!(publisher.messages.len(), 1);
    }
}
