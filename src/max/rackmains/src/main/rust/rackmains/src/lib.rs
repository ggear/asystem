pub mod broker;
pub mod mock;
pub mod nut;
pub mod schema;

use std::io::Write;
use std::path::PathBuf;
use std::sync::LazyLock;
use std::thread;
use std::time::{Duration, Instant, SystemTime};

use clap::builder::{PossibleValuesParser, TypedValueParser};
use clap::Parser;
use log::{debug, error, info, warn, LevelFilter};
use serde_json::{json, Map, Value};

use crate::broker::{MqttPublisher, Publisher};
use crate::nut::{Nut, Reading, Source};
use crate::schema::{AVAILABILITY_ONLINE, KEY_PERIOD_MS, KEY_SAMPLES, KEY_STATUS, KEY_TIMESTAMP};

static LEVEL_NAMES: LazyLock<Vec<String>> =
    LazyLock::new(|| LevelFilter::iter().map(|level| level.as_str().to_lowercase()).collect());

const STATE_TOPIC: &str = "rackmains/data";
const STATUS_TOPIC: &str = "rackmains/status";
const LOG_LABEL_WIDTH: usize = 48;
const MAX_CONSECUTIVE_FAILURES: u32 = 3;
const REINIT_DELAY_MIN: Duration = Duration::from_secs(1);
const REINIT_DELAY_MAX: Duration = Duration::from_secs(60);
pub const DEFAULT_POLL_PERIOD: &str = "0";
pub const DEFAULT_DEVICE: &str = "/run/nut/nutdrv_qx-powershield";

#[derive(Debug, Parser)]
#[command(
    name = "rackmains",
    about = "Run the rackmains mains-supply and battery reader",
    version
)]
pub struct Cli {
    #[arg(short = 'P', long = "poll-period", value_name = "PERIOD", default_value = DEFAULT_POLL_PERIOD)]
    pub poll_period: String,
    #[arg(
        short = 'D',
        long = "device",
        value_name = "SOCKET",
        default_value = DEFAULT_DEVICE
    )]
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
            .format(|buf, record| {
                writeln!(
                    buf,
                    "[{} {:<5}] {}",
                    chrono::Local::now().format("%Y-%m-%dT%H:%M:%S%.3f%:z"),
                    record.level(),
                    record.args()
                )
            })
            .try_init();
        let timeout = parse_duration(&self.timeout)?;
        debug!(
            "timeout [{timeout:?}], poll period [{period:?}], broker [{}:{}]",
            self.broker_host, self.broker_port
        );
        let mut delay = Duration::ZERO;
        loop {
            let mut source = Nut::new(PathBuf::from(&self.device), timeout);
            info!("{}", log_line("starting version", &version));
            info!("{}", log_line("reading device", &self.device));
            let mut publisher =
                match MqttPublisher::new(&self.broker_host, self.broker_port, &self.broker_token, STATUS_TOPIC) {
                    Ok(publisher) => publisher,
                    Err(err) => {
                        if period.is_zero() {
                            return Err(err.to_string());
                        }
                        delay = reinit_delay(delay, period);
                        error!("broker unavailable [{err}], retrying in [{delay:?}]");
                        thread::sleep(delay);
                        continue;
                    }
                };
            let polling = Instant::now();
            let poll_result = poll(period, &mut source, &mut publisher, STATE_TOPIC);
            let close_result = publisher.close(STATUS_TOPIC).map_err(|err| err.to_string());
            drop(publisher);
            let combined = poll_result.and(close_result);
            if period.is_zero() {
                if let Err(ref err) = combined {
                    error!("{err}");
                }
                return combined;
            }
            if polling.elapsed() >= period {
                delay = Duration::ZERO;
            }
            delay = reinit_delay(delay, period);
            if let Err(ref err) = combined {
                error!("[{err}], reinitializing in [{delay:?}]");
            }
            thread::sleep(delay);
        }
    }
}

pub fn parse_duration(raw: &str) -> Result<Duration, String> {
    let trimmed = raw.trim();
    if trimmed == "0" {
        return Ok(Duration::ZERO);
    }
    humantime::parse_duration(trimmed).map_err(|err| format!("invalid duration [{trimmed}] [{err}]"))
}

pub(crate) fn log_line(label: &str, value: &str) -> String {
    let leader = format!("{label} ");
    format!("{leader:.<width$} [{value}]", width = LOG_LABEL_WIDTH)
}

fn reinit_delay(previous: Duration, period: Duration) -> Duration {
    let ceiling = REINIT_DELAY_MAX.min(period).max(REINIT_DELAY_MIN);
    if previous.is_zero() {
        REINIT_DELAY_MIN
    } else {
        previous.saturating_mul(2).min(ceiling)
    }
}

fn poll<S: Source + ?Sized, P: Publisher>(
    period: Duration,
    source: &mut S,
    publisher: &mut P,
    state_topic: &str,
) -> Result<(), String> {
    if !period.is_zero() {
        info!(
            "{}",
            log_line(
                "mains sample/publish loop running every",
                &format!("{}s", period.as_secs())
            )
        );
    }
    let mut iteration: u64 = 0;
    let mut failures: u32 = 0;
    let mut last_status: Option<String> = None;
    loop {
        iteration += 1;
        if let Err(err) = publisher.publish(STATUS_TOPIC, AVAILABILITY_ONLINE.as_bytes()) {
            warn!("failed to publish status [{STATUS_TOPIC}] [{err}]");
        }
        match poll_once(source, publisher, state_topic)? {
            Some(reading) => {
                failures = 0;
                if reading.status != last_status {
                    info!(
                        "{}",
                        log_line("mains status", reading.status.as_deref().unwrap_or("unknown"))
                    );
                    last_status = reading.status;
                }
            }
            None => failures += 1,
        }
        if period.is_zero() {
            return if failures == 0 {
                Ok(())
            } else {
                Err("failed to read device".to_string())
            };
        }
        if failures >= MAX_CONSECUTIVE_FAILURES {
            return Err(format!("device read failed on [{failures}] consecutive poll(s)"));
        }
        debug!("sleeping [{period:?}] until iteration [{}]", iteration + 1);
        thread::sleep(period);
    }
}

fn poll_once<S: Source + ?Sized, P: Publisher>(
    source: &mut S,
    publisher: &mut P,
    state_topic: &str,
) -> Result<Option<Reading>, String> {
    let start = Instant::now();
    let timestamp = humantime::format_rfc3339_seconds(SystemTime::now()).to_string();
    let reading = match source.read() {
        Ok(reading) => reading,
        Err(err) => {
            error!("device read failed [{err}]");
            return Ok(None);
        }
    };
    let mut samples: Map<String, Value> = Map::new();
    for (key, value) in &reading.samples {
        debug!("{}", log_line(&format!("sample [{key}] read at"), &value.to_string()));
        samples.insert((*key).to_string(), json!(value));
    }
    let mut payload: Map<String, Value> = Map::new();
    payload.insert(KEY_TIMESTAMP.to_string(), json!(timestamp));
    payload.insert(KEY_PERIOD_MS.to_string(), json!(start.elapsed().as_millis() as u64));
    if let Some(status) = &reading.status {
        payload.insert(KEY_STATUS.to_string(), json!(status));
    }
    payload.insert(KEY_SAMPLES.to_string(), Value::Object(samples));
    let payload_bytes = serde_json::to_vec(&payload).map_err(|err| format!("failed to serialize payload [{err}]"))?;
    publisher
        .publish(state_topic, &payload_bytes)
        .map_err(|err| format!("failed to publish [{err}]"))?;
    debug!(
        "{}",
        log_line(
            "mains sample/publish loop finished in",
            &format!("{}ms", start.elapsed().as_millis())
        )
    );
    Ok(Some(reading))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::broker::mock::MockPublisher;
    use crate::nut::mock::MockSource;
    use crate::nut::Error;

    fn reading() -> Reading {
        Reading::from_variables([
            ("battery.charge", "100"),
            ("battery.voltage", "13.4"),
            ("input.voltage", "241.4"),
            ("input.voltage.fault", "241.4"),
            ("output.frequency", "50.1"),
            ("output.voltage", "241.4"),
            ("ups.load", "13"),
            ("ups.status", "OL"),
        ])
    }

    fn published(publisher: &MockPublisher, topic: &str) -> usize {
        publisher
            .messages
            .iter()
            .filter(|(published, _)| published == topic)
            .count()
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
    fn reinit_delay_backs_off_to_a_ceiling_bounded_by_the_poll_period() {
        let secs = Duration::from_secs;
        let millis = Duration::from_millis;
        for (previous, period, want) in [
            (Duration::ZERO, secs(900), secs(1)),
            (secs(1), secs(900), secs(2)),
            (secs(32), secs(900), secs(60)),
            (secs(60), secs(900), secs(60)),
            (secs(16), secs(30), secs(30)),
            (Duration::ZERO, millis(1), secs(1)),
            (secs(1), millis(1), secs(1)),
        ] {
            assert_eq!(
                reinit_delay(previous, period),
                want,
                "previous {previous:?} period {period:?}"
            );
        }
    }

    #[test]
    fn cli_parses_poll_period_flags() {
        assert_eq!(Cli::parse_from(["rackmains", "-P", "10s"]).poll_period, "10s");
        assert_eq!(Cli::parse_from(["rackmains", "--poll-period", "2m"]).poll_period, "2m");
        assert_eq!(Cli::parse_from(["rackmains"]).poll_period, "0");
    }

    #[test]
    fn cli_parses_device_and_timeout_flags() {
        assert_eq!(Cli::parse_from(["rackmains"]).device, "/run/nut/nutdrv_qx-powershield");
        assert_eq!(Cli::parse_from(["rackmains"]).timeout, "1s");
        assert_eq!(Cli::parse_from(["rackmains", "-D", "/tmp/other"]).device, "/tmp/other");
        assert_eq!(
            Cli::parse_from(["rackmains", "--device", "/tmp/another"]).device,
            "/tmp/another"
        );
        assert_eq!(Cli::parse_from(["rackmains", "-T", "500ms"]).timeout, "500ms");
        assert_eq!(Cli::parse_from(["rackmains", "--timeout", "2s"]).timeout, "2s");
    }

    #[test]
    fn cli_parses_log_level_flags() {
        assert_eq!(Cli::parse_from(["rackmains"]).log_level, LevelFilter::Info);
        assert_eq!(
            Cli::parse_from(["rackmains", "-L", "debug"]).log_level,
            LevelFilter::Debug
        );
        assert_eq!(
            Cli::parse_from(["rackmains", "--log-level", "warn"]).log_level,
            LevelFilter::Warn
        );
        assert_eq!(
            Cli::parse_from(["rackmains", "--log-level", "trace"]).log_level,
            LevelFilter::Trace
        );
        assert!(Cli::try_parse_from(["rackmains", "-L", "verbose"]).is_err());
    }

    #[test]
    fn cli_parses_broker_flags() {
        let cli = Cli::parse_from([
            "rackmains",
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
        assert_eq!(Cli::parse_from(["rackmains"]).broker_host, "localhost");
        assert_eq!(Cli::parse_from(["rackmains"]).broker_port, 1883);
    }

    #[test]
    fn poll_once_publishes_combined_json_to_state_topic() {
        let mut source = MockSource::new();
        source.readings.push_back(Ok(reading()));
        let mut publisher = MockPublisher::new();
        assert!(poll_once(&mut source, &mut publisher, "state").unwrap().is_some());
        assert_eq!(publisher.messages.len(), 1);
        let (topic, payload) = &publisher.messages[0];
        assert_eq!(topic, "state");
        let payload: Value = serde_json::from_slice(payload).unwrap();
        assert!(payload[KEY_PERIOD_MS].as_u64().is_some());
        assert!(payload[KEY_TIMESTAMP]
            .as_str()
            .is_some_and(|timestamp| timestamp.len() == 20));
        assert_eq!(payload[KEY_STATUS], "OL");
        assert_eq!(payload[KEY_SAMPLES].as_object().unwrap().len(), nut::SAMPLES.len());
        assert_eq!(payload[KEY_SAMPLES]["rack_battery_charge_percent"], 100.0);
        assert_eq!(payload[KEY_SAMPLES]["rack_mains_input_voltage_volts"], 241.4);
        assert_eq!(payload[KEY_SAMPLES]["rack_mains_utilisation_percent"], 13.0);
    }

    #[test]
    fn poll_once_omits_a_status_the_device_did_not_report() {
        let mut source = MockSource::new();
        source
            .readings
            .push_back(Ok(Reading::from_variables([("input.voltage", "241.4")])));
        let mut publisher = MockPublisher::new();
        poll_once(&mut source, &mut publisher, "state").unwrap();
        let payload: Value = serde_json::from_slice(&publisher.messages[0].1).unwrap();
        assert!(payload.get(KEY_STATUS).is_none());
        assert_eq!(payload[KEY_SAMPLES].as_object().unwrap().len(), 1);
    }

    #[test]
    fn poll_once_publishes_nothing_when_the_read_fails() {
        let mut source = MockSource::new();
        source.readings.push_back(Err(Error::Read("refused".to_string())));
        let mut publisher = MockPublisher::new();
        assert!(poll_once(&mut source, &mut publisher, "state").unwrap().is_none());
        assert!(publisher.messages.is_empty());
    }

    #[test]
    fn poll_zero_period_runs_single_iteration() {
        let mut source = MockSource::new();
        source.readings.push_back(Ok(reading()));
        let mut publisher = MockPublisher::new();
        poll(Duration::ZERO, &mut source, &mut publisher, "state").unwrap();
        assert_eq!(published(&publisher, "state"), 1);
        assert_eq!(published(&publisher, STATUS_TOPIC), 1);
        assert_eq!(
            publisher
                .messages
                .iter()
                .find(|(topic, _)| topic == STATUS_TOPIC)
                .map(|(_, payload)| payload.as_slice()),
            Some(AVAILABILITY_ONLINE.as_bytes())
        );
    }

    #[test]
    fn poll_zero_period_fails_when_the_read_fails() {
        let mut source = MockSource::new();
        source.readings.push_back(Err(Error::Read("refused".to_string())));
        let mut publisher = MockPublisher::new();
        assert!(poll(Duration::ZERO, &mut source, &mut publisher, "state").is_err());
        assert_eq!(published(&publisher, "state"), 0);
    }

    #[test]
    fn poll_reinitializes_after_consecutive_failures() {
        let mut source = MockSource::new();
        for _ in 0..MAX_CONSECUTIVE_FAILURES {
            source.readings.push_back(Err(Error::Read("refused".to_string())));
        }
        let mut publisher = MockPublisher::new();
        assert!(poll(Duration::from_millis(1), &mut source, &mut publisher, "state").is_err());
        assert_eq!(published(&publisher, "state"), 0);
        assert_eq!(published(&publisher, STATUS_TOPIC), MAX_CONSECUTIVE_FAILURES as usize);
        assert!(source.readings.is_empty());
    }

    #[test]
    fn poll_recovers_when_a_read_succeeds_before_the_ceiling() {
        let mut source = MockSource::new();
        source.readings.push_back(Err(Error::Read("refused".to_string())));
        source.readings.push_back(Err(Error::Read("refused".to_string())));
        source.readings.push_back(Ok(reading()));
        source.readings.push_back(Err(Error::Read("refused".to_string())));
        source.readings.push_back(Err(Error::Read("refused".to_string())));
        source.readings.push_back(Err(Error::Read("refused".to_string())));
        let mut publisher = MockPublisher::new();
        assert!(poll(Duration::from_millis(1), &mut source, &mut publisher, "state").is_err());
        assert_eq!(published(&publisher, "state"), 1);
        assert!(source.readings.is_empty());
    }
}
