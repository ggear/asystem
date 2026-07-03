use std::io::{self, Write};
use std::thread;
use std::time::Duration;

use clap::Parser;

#[derive(Debug, Parser)]
#[command(name = "zeroth", about = "Run the zeroth temperature-probe reader")]
pub struct Cli {
    #[arg(short = 'P', long = "poll-period", value_name = "PERIOD", default_value = "0")]
    pub poll_period: String,
}

impl Cli {
    pub fn run(&self) -> Result<(), String> {
        let period = parse_poll_period(&self.poll_period)?;
        poll(period, &mut io::stdout()).map_err(|err| err.to_string())
    }
}

pub fn parse_poll_period(raw: &str) -> Result<Duration, String> {
    let trimmed = raw.trim();
    if trimmed == "0" {
        return Ok(Duration::ZERO);
    }
    humantime::parse_duration(trimmed).map_err(|err| format!("invalid poll period [{trimmed}]: {err}"))
}

fn poll<W: Write>(period: Duration, out: &mut W) -> io::Result<()> {
    let mut iteration: u64 = 0;
    loop {
        iteration += 1;
        poll_once(iteration, out)?;
        if period.is_zero() {
            return Ok(());
        }
        thread::sleep(period);
    }
}

fn poll_once<W: Write>(iteration: u64, out: &mut W) -> io::Result<()> {
    writeln!(out, "zeroth: poll iteration {iteration}")?;
    out.flush()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_poll_period_zero_is_zero() {
        assert_eq!(parse_poll_period("0").unwrap(), Duration::ZERO);
        assert_eq!(parse_poll_period(" 0 ").unwrap(), Duration::ZERO);
    }

    #[test]
    fn parse_poll_period_accepts_unit_suffixes() {
        assert_eq!(parse_poll_period("3s").unwrap(), Duration::from_secs(3));
        assert_eq!(parse_poll_period("5m").unwrap(), Duration::from_secs(300));
        assert_eq!(parse_poll_period("1h").unwrap(), Duration::from_secs(3600));
    }

    #[test]
    fn parse_poll_period_rejects_garbage() {
        assert!(parse_poll_period("nonsense").is_err());
        assert!(parse_poll_period("").is_err());
    }

    #[test]
    fn poll_zero_period_runs_single_iteration() {
        let mut out = Vec::new();
        poll(Duration::ZERO, &mut out).unwrap();
        assert_eq!(String::from_utf8(out).unwrap(), "zeroth: poll iteration 1\n");
    }

    #[test]
    fn poll_once_writes_numbered_heartbeat() {
        let mut out = Vec::new();
        poll_once(7, &mut out).unwrap();
        assert_eq!(String::from_utf8(out).unwrap(), "zeroth: poll iteration 7\n");
    }

    #[test]
    fn cli_parses_poll_period_flags() {
        assert_eq!(Cli::parse_from(["zeroth", "-P", "10s"]).poll_period, "10s");
        assert_eq!(Cli::parse_from(["zeroth", "--poll-period", "2m"]).poll_period, "2m");
        assert_eq!(Cli::parse_from(["zeroth"]).poll_period, "0");
    }
}
