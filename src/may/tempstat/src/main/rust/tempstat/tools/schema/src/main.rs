use std::io;
use std::path::PathBuf;
use std::process;

use tempstat::config::load_sensors;
use tempstat::schema::{reflect, TempStat, MODULE};

fn main() {
    let path = config_path();
    let sensors = match load_sensors(&path) {
        Ok(sensors) => sensors,
        Err(err) => {
            eprintln!("{err}");
            process::exit(1);
        }
    };
    let schema = TempStat::new(sensors);
    let mut stdout = io::stdout().lock();
    if let Err(err) = reflect(&mut stdout, MODULE, Some(&schema)) {
        eprintln!("{err}");
        process::exit(1);
    }
}

fn config_path() -> PathBuf {
    PathBuf::from(flag("--config", CONFIG_DEFAULT))
}

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

const CONFIG_DEFAULT: &str = "src/main/resources/image/sensors.json";
