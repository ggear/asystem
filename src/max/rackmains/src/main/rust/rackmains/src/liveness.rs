use std::fs;
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, LazyLock};
use std::thread;
use std::time::{Duration, Instant};

use log::error;
use serde::{Deserialize, Serialize};

use crate::outage::write_replace;

pub const FILE_LIVENESS: &str = "liveness.json";
pub const WATCHDOG_LIMIT: Duration = Duration::from_secs(10);
pub const WATCHDOG_TICK: Duration = Duration::from_secs(1);
const UPTIME: &str = "/proc/uptime";

static PROCESS_START: LazyLock<Instant> = LazyLock::new(Instant::now);

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
pub struct Effective {
    pub guard_live: bool,
    pub model_name: String,
    pub model_version: String,
    pub model_hash: String,
    pub guard_shed_battery_seconds: u64,
    pub guard_restore_mains_seconds: u64,
    pub poll_s: u64,
    pub ssh_timeout_s: u64,
    pub shed_order: Vec<String>,
}

#[derive(Serialize, Deserialize, Clone, Debug, Default, PartialEq)]
pub struct Liveness {
    pub boot_ms: u64,
    pub last_read_boot_ms: u64,
    pub guard_boot_ms: u64,
    pub ups_problem: bool,
    pub effective: Effective,
}

impl Liveness {
    pub fn read(path: &Path) -> Result<Liveness, String> {
        let bytes = fs::read(path).map_err(|err| format!("failed to read [{}] [{err}]", path.display()))?;
        serde_json::from_slice(&bytes).map_err(|err| format!("invalid liveness [{}] [{err}]", path.display()))
    }

    pub fn write(&self, path: &Path) -> Result<(), String> {
        let bytes = serde_json::to_vec(self).map_err(|err| format!("failed to encode liveness [{err}]"))?;
        write_replace(path, &bytes, false)
    }
}

pub fn boot_ms() -> u64 {
    fs::read_to_string(UPTIME)
        .ok()
        .and_then(|text| text.split_whitespace().next()?.parse::<f64>().ok())
        .map_or_else(
            || PROCESS_START.elapsed().as_millis() as u64,
            |seconds| (seconds * 1000.0) as u64,
        )
}

#[derive(Clone, Default)]
pub struct Progress(Arc<AtomicU64>);

impl Progress {
    pub fn tick(&self) {
        self.0.fetch_add(1, Ordering::Relaxed);
    }

    fn count(&self) -> u64 {
        self.0.load(Ordering::Relaxed)
    }
}

pub fn watchdog(name: &'static str, progress: Progress, limit: Duration, tick: Duration, on_stall: fn(&str)) {
    thread::spawn(move || {
        let mut seen = progress.count();
        let mut since = Instant::now();
        loop {
            thread::sleep(tick);
            let now = progress.count();
            if now != seen {
                seen = now;
                since = Instant::now();
            } else if since.elapsed() >= limit {
                on_stall(name);
                since = Instant::now();
            }
        }
    });
}

pub fn abort_on_stall(name: &str) {
    error!("watchdog [{name}] made no progress, aborting");
    std::process::abort();
}

#[cfg(test)]
mod tests {
    use std::sync::atomic::AtomicBool;

    use super::*;

    static STALLED_FIRED: AtomicBool = AtomicBool::new(false);
    static MOVING_FIRED: AtomicBool = AtomicBool::new(false);

    fn record(name: &str) {
        match name {
            "stalled" => STALLED_FIRED.store(true, Ordering::SeqCst),
            _ => MOVING_FIRED.store(true, Ordering::SeqCst),
        }
    }

    #[test]
    fn liveness_round_trips_through_the_file() {
        let path = std::env::temp_dir().join(format!("rackmains-liveness-{}.json", std::process::id()));
        let liveness = Liveness {
            boot_ms: 5,
            last_read_boot_ms: 4,
            guard_boot_ms: 3,
            ups_problem: true,
            effective: Effective {
                shed_order: vec!["a".to_string()],
                ..Effective::default()
            },
        };
        liveness.write(&path).unwrap();
        assert_eq!(Liveness::read(&path).unwrap(), liveness);
        let _ = fs::remove_file(path);
    }

    #[test]
    fn a_missing_or_garbled_file_is_an_error() {
        assert!(Liveness::read(Path::new("/nonexistent/liveness.json")).is_err());
        let path = std::env::temp_dir().join(format!("rackmains-garbled-{}.json", std::process::id()));
        fs::write(&path, "{").unwrap();
        assert!(Liveness::read(&path).is_err());
        let _ = fs::remove_file(path);
    }

    #[test]
    fn the_boot_clock_does_not_go_backwards() {
        let first = boot_ms();
        thread::sleep(Duration::from_millis(20));
        assert!(boot_ms() >= first);
    }

    #[test]
    fn the_watchdog_fires_on_a_stalled_counter_and_not_on_a_moving_one() {
        let moving = Progress::default();
        let stalled = Progress::default();
        let ticker = moving.clone();
        watchdog(
            "moving",
            moving,
            Duration::from_secs(1),
            Duration::from_millis(20),
            record,
        );
        watchdog(
            "stalled",
            stalled,
            Duration::from_secs(1),
            Duration::from_millis(20),
            record,
        );
        let running = thread::spawn(move || {
            for _ in 0..120 {
                ticker.tick();
                thread::sleep(Duration::from_millis(10));
            }
        });
        running.join().unwrap();
        assert!(!MOVING_FIRED.load(Ordering::SeqCst));
        let waiting = Instant::now();
        while !STALLED_FIRED.load(Ordering::SeqCst) && waiting.elapsed() < Duration::from_secs(10) {
            thread::sleep(Duration::from_millis(20));
        }
        assert!(STALLED_FIRED.load(Ordering::SeqCst));
    }
}
