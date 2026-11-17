mod broker;
mod check;
mod cli;
mod drill;
mod guard;
mod liveness;
mod metrics;
pub mod mock;
pub mod model;
mod nut;
mod outage;
mod policy;
mod report;
pub mod schema;
mod serve;
mod shed;

use std::io::Write;
use std::sync::LazyLock;
use std::time::Duration;

use log::LevelFilter;

pub use crate::cli::Cli;

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

pub fn log_prefix(level: log::Level) -> String {
    format!(
        "[{} {:<5}]",
        chrono::Local::now().format("%Y-%m-%dT%H:%M:%S%.3f%:z"),
        level
    )
}

pub fn log_prefix_at(level: log::Level, epoch_seconds: f64) -> String {
    chrono::DateTime::from_timestamp(epoch_seconds.floor() as i64, (epoch_seconds.fract() * 1e9) as u32).map_or_else(
        || log_prefix(level),
        |time| {
            format!(
                "[{} {:<5}]",
                time.with_timezone(&chrono::Local).format("%Y-%m-%dT%H:%M:%S%.3f%:z"),
                level
            )
        },
    )
}

pub fn say(level: log::Level, line: &str) {
    println!("{} {line}", log_prefix(level));
}

pub fn init_logging(level: LevelFilter) {
    let _ = env_logger::Builder::new()
        .filter_level(level)
        .format(|buf, record| writeln!(buf, "{} {}", log_prefix(record.level()), record.args()))
        .try_init();
}

pub static LEVEL_NAMES: LazyLock<Vec<String>> =
    LazyLock::new(|| LevelFilter::iter().map(|level| level.as_str().to_lowercase()).collect());

pub const STATE_TOPIC: &str = "rackmains/data";

pub const STATUS_TOPIC: &str = "rackmains/status";

pub const DEFAULT_DEVICE: &str = "/run/nut/nutdrv_qx-powershield";

const LOG_LABEL_WIDTH: usize = 48;

#[cfg(test)]
mod tests {
    use super::*;

    fn calls<'a>(source: &'a str, opener: &str) -> Vec<&'a str> {
        let body = source.split("#[cfg(test)]").next().unwrap_or(source);
        let mut found = Vec::new();
        let mut from = 0;
        while let Some(at) = body[from..].find(opener) {
            let start = from + at;
            let (mut depth, mut index, bytes) = (0usize, start + opener.len() - 1, body.as_bytes());
            while index < bytes.len() {
                match bytes[index] {
                    b'(' => depth += 1,
                    b')' => {
                        depth -= 1;
                        if depth == 0 {
                            break;
                        }
                    }
                    b'"' => {
                        index += 1;
                        while bytes[index] != b'"' {
                            index += usize::from(bytes[index] == b'\\') + 1;
                        }
                    }
                    _ => {}
                }
                index += 1;
            }
            found.push(&body[start..=index]);
            from = index;
        }
        found
    }

    #[test]
    fn every_log_line_is_a_label_and_a_bracketed_value_with_no_separators() {
        let sources = [
            ("broker", include_str!("broker.rs")),
            ("check", include_str!("check.rs")),
            ("cli", include_str!("cli.rs")),
            ("drill", include_str!("drill.rs")),
            ("guard", include_str!("guard.rs")),
            ("liveness", include_str!("liveness.rs")),
            ("main", include_str!("main.rs")),
            ("mock", include_str!("mock.rs")),
            ("mockdriver", include_str!("bin/mockdriver.rs")),
            ("nut", include_str!("nut.rs")),
            ("outage", include_str!("outage.rs")),
            ("policy", include_str!("policy.rs")),
            ("report", include_str!("report.rs")),
            ("serve", include_str!("serve.rs")),
            ("shed", include_str!("shed.rs")),
        ];
        let mut checked = 0;
        for (name, source) in sources {
            for opener in ["info!(", "warn!(", "error!(", "debug!(", "trace!(", "eprintln!("] {
                for call in calls(source, opener) {
                    checked += 1;
                    assert!(
                        call.contains("log_line(") || call.contains("log_change("),
                        "[{name}] log call not built by log_line or log_change [{call}]"
                    );
                }
            }
            for opener in ["log_line(", "log_change("] {
                for call in calls(source, opener) {
                    let rest = call[opener.len()..].trim_start().trim_start_matches("&format!(");
                    let Some(literal) = rest.strip_prefix('"').and_then(|rest| rest.split('"').next()) else {
                        continue;
                    };
                    assert!(
                        !literal.contains([':', '\u{2014}', '\u{2013}', '(', ',']),
                        "[{name}] a separator, clause or bracket in a log label [{literal}]"
                    );
                    assert!(
                        !literal.ends_with([' ', '.']),
                        "[{name}] trailing punctuation in a log label [{literal}]"
                    );
                }
            }
        }
        assert!(checked > 60, "the scan found too few log calls [{checked}]");
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
