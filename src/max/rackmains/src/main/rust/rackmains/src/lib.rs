pub mod broker;
pub mod check;
pub mod cli;
pub mod drill;
pub mod guard;
pub mod liveness;
pub mod metrics;
pub mod mock;
pub mod model;
pub mod nut;
pub mod outage;
pub mod policy;
pub mod report;
pub mod schema;
pub mod serve;
pub mod shed;

use std::io::Write;
use std::sync::LazyLock;
use std::time::Duration;

use log::LevelFilter;

pub use crate::cli::Cli;

pub static LEVEL_NAMES: LazyLock<Vec<String>> =
    LazyLock::new(|| LevelFilter::iter().map(|level| level.as_str().to_lowercase()).collect());

pub const STATE_TOPIC: &str = "rackmains/data";
pub const STATUS_TOPIC: &str = "rackmains/status";
pub const DEFAULT_DEVICE: &str = "/run/nut/nutdrv_qx-powershield";
const LOG_LABEL_WIDTH: usize = 48;

pub fn parse_duration(raw: &str) -> Result<Duration, String> {
    let trimmed = raw.trim();
    if trimmed == "0" {
        return Ok(Duration::ZERO);
    }
    humantime::parse_duration(trimmed).map_err(|err| format!("invalid duration [{trimmed}] [{err}]"))
}

pub fn log_line(label: &str, value: &str) -> String {
    let leader = format!("{label} ");
    format!("{leader:.<LOG_LABEL_WIDTH$} [{value}]")
}

pub fn init_logging(level: LevelFilter) {
    let _ = env_logger::Builder::new()
        .filter_level(level)
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
}

#[cfg(test)]
mod tests {
    use super::*;

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
    fn log_lines_lead_with_dots_and_bracket_the_value() {
        let line = log_line("label", "value");
        assert!(line.starts_with("label ."));
        assert!(line.ends_with("[value]"));
    }
}
