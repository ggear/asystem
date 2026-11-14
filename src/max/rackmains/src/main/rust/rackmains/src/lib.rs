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

pub fn log_change(label: &str, from: &str, to: &str) -> String {
    let leader = format!("{label} ");
    format!("{leader:.<LOG_LABEL_WIDTH$} [{from}] to [{to}]")
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

    #[test]
    fn a_change_line_keeps_the_value_column_and_brackets_both_values() {
        let line = log_change("ups status changed", "on battery", "on mains");
        assert_eq!(line.find('['), log_line("ups status", "x").find('['));
        assert!(line.ends_with("[on battery] to [on mains]"));
    }

    #[test]
    fn no_log_label_is_long_enough_to_push_the_value_column() {
        let mut checked = 0;
        for entry in std::fs::read_dir(concat!(env!("CARGO_MANIFEST_DIR"), "/src"))
            .unwrap()
            .flatten()
        {
            let path = entry.path();
            if path.extension().is_none_or(|extension| extension != "rs") {
                continue;
            }
            let text = std::fs::read_to_string(&path).unwrap();
            let production = text.split("#[cfg(test)]").next().unwrap_or_default();
            for opener in ["log_line(", "log_change("] {
                for found in production.split(opener).skip(1) {
                    let Some(literal) = found.trim_start().strip_prefix('"') else {
                        continue;
                    };
                    let label = literal.split('"').next().unwrap_or_default();
                    checked += 1;
                    assert!(
                        label.len() + 2 < LOG_LABEL_WIDTH,
                        "label [{label}] in [{}] is too long for the value column",
                        path.display()
                    );
                }
            }
        }
        assert!(checked > 20, "only [{checked}] labels found");
    }
}
