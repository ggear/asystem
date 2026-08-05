use std::io;
use std::path::PathBuf;
use std::process;

use tempstat::config::load_sensors;
use tempstat::schema::{reflect, TempStat, MODULE};
use tempstat::DEFAULT_POLL_PERIOD;

const SENSORS_DEFAULT: &str = "src/main/resources/image/sensors.json";

fn flag(name: &str, fallback: &str) -> String {
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        if arg == name {
            if let Some(value) = args.next() {
                return value;
            }
        }
    }
    fallback.to_string()
}

fn sensors_path() -> PathBuf {
    PathBuf::from(flag("--sensors", SENSORS_DEFAULT))
}

fn main() {
    let path = sensors_path();
    let sensors = match load_sensors(&path) {
        Ok(sensors) => sensors,
        Err(err) => {
            eprintln!("{err}");
            process::exit(1);
        }
    };
    let schema = TempStat::new(sensors, flag("--poll-period", DEFAULT_POLL_PERIOD));
    let mut stdout = io::stdout().lock();
    if let Err(err) = reflect(&mut stdout, MODULE, Some(&schema), Some(&schema)) {
        eprintln!("{err}");
        process::exit(1);
    }
}
