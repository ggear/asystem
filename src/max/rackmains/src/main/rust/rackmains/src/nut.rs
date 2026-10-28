use std::fmt;
use std::io::{BufRead, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::time::Duration;

pub const VARIABLE_STATUS: &str = "ups.status";
pub const COMMAND_DUMP: &str = "DUMPALL";
pub const LINE_DONE: &str = "DUMPDONE";
pub const LINE_OK: &str = "DATAOK";
pub const LINE_STALE: &str = "DATASTALE";

pub struct Sample {
    pub variable: &'static str,
    pub key: &'static str,
}

pub const SAMPLES: [Sample; 7] = [
    Sample {
        variable: "input.voltage",
        key: "rack_mains_input_voltage_volts",
    },
    Sample {
        variable: "input.voltage.fault",
        key: "rack_mains_input_voltage_fault_volts",
    },
    Sample {
        variable: "output.voltage",
        key: "rack_mains_output_voltage_volts",
    },
    Sample {
        variable: "output.frequency",
        key: "rack_mains_output_frequency_hertz",
    },
    Sample {
        variable: "ups.load",
        key: "rack_mains_utilisation_percent",
    },
    Sample {
        variable: "battery.charge",
        key: "rack_battery_charge_percent",
    },
    Sample {
        variable: "battery.voltage",
        key: "rack_battery_voltage_volts",
    },
];

#[derive(Debug)]
pub enum Error {
    Stale,
    Read(String),
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Stale => write!(f, "device data stale"),
            Error::Read(msg) => write!(f, "device read error [{msg}]"),
        }
    }
}

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, Default, PartialEq)]
pub struct Reading {
    pub status: Option<String>,
    pub samples: Vec<(&'static str, f64)>,
}

impl Reading {
    pub fn from_dump(dump: &str) -> Result<Self> {
        let freshness = dump.lines().rev().find(|line| *line == LINE_OK || *line == LINE_STALE);
        if freshness == Some(LINE_STALE) {
            return Err(Error::Stale);
        }
        Ok(Self::from_variables(dump.lines().filter_map(|line| {
            let (name, value) = line.strip_prefix("SETINFO ")?.split_once(' ')?;
            Some((name, value.trim().trim_matches('"')))
        })))
    }

    pub fn from_variables<'a>(variables: impl IntoIterator<Item = (&'a str, &'a str)>) -> Self {
        let variables: Vec<(&str, &str)> = variables.into_iter().collect();
        let lookup = |name: &str| {
            variables
                .iter()
                .find(|(variable, _)| *variable == name)
                .map(|(_, value)| value.trim())
        };
        Reading {
            status: lookup(VARIABLE_STATUS)
                .filter(|value| !value.is_empty())
                .map(str::to_string),
            samples: SAMPLES
                .iter()
                .filter_map(|sample| {
                    let value = lookup(sample.variable)?.parse::<f64>().ok()?;
                    value.is_finite().then_some((sample.key, value))
                })
                .collect(),
        }
    }
}

pub trait Source {
    fn read(&mut self) -> Result<Reading>;
}

pub struct Nut {
    pub socket: PathBuf,
    pub timeout: Duration,
}

impl Nut {
    pub fn new(socket: PathBuf, timeout: Duration) -> Self {
        Nut { socket, timeout }
    }
}

impl Source for Nut {
    fn read(&mut self) -> Result<Reading> {
        let failed = |action: &str, err: std::io::Error| {
            Error::Read(format!("failed to {action} [{}] [{err}]", self.socket.display()))
        };
        let mut stream = UnixStream::connect(&self.socket).map_err(|err| failed("connect", err))?;
        stream
            .set_read_timeout(Some(self.timeout))
            .and_then(|_| stream.set_write_timeout(Some(self.timeout)))
            .map_err(|err| failed("set timeout", err))?;
        writeln!(stream, "{COMMAND_DUMP}").map_err(|err| failed("write", err))?;
        let mut dump = String::new();
        for line in BufReader::new(&stream).lines() {
            let line = line.map_err(|err| failed("read", err))?;
            dump.push_str(&line);
            dump.push('\n');
            if line == LINE_DONE {
                return Reading::from_dump(&dump);
            }
        }
        Err(Error::Read(format!(
            "driver closed before the dump completed [{}]",
            self.socket.display()
        )))
    }
}

#[cfg(test)]
pub mod mock {
    use std::collections::VecDeque;

    use super::{Error, Reading, Result, Source};

    #[derive(Default)]
    pub struct MockSource {
        pub readings: VecDeque<Result<Reading>>,
    }

    impl MockSource {
        pub fn new() -> Self {
            MockSource {
                readings: VecDeque::new(),
            }
        }
    }

    impl Source for MockSource {
        fn read(&mut self) -> Result<Reading> {
            self.readings
                .pop_front()
                .unwrap_or_else(|| Err(Error::Read("no reading queued".to_string())))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const REPORTED: [(&str, &str); 8] = [
        ("battery.charge", "100"),
        ("battery.voltage", "13.4"),
        ("input.voltage", "241.4"),
        ("input.voltage.fault", "241.4"),
        ("output.frequency", "50.1"),
        ("output.voltage", "241.4"),
        ("ups.load", "13"),
        ("ups.status", "OL"),
    ];

    fn sample(reading: &Reading, key: &str) -> Option<f64> {
        reading
            .samples
            .iter()
            .find(|(name, _)| *name == key)
            .map(|(_, value)| *value)
    }

    #[test]
    fn dump_reads_the_driver_socket_listing() {
        let dump = "SETINFO battery.charge \"100\"\n\
                    SETINFO battery.voltage \"13.3\"\n\
                    SETINFO device.type \"ups\"\n\
                    SETFLAGS driver.debug RW NUMBER\n\
                    SETINFO input.voltage \"241.4\"\n\
                    SETINFO ups.status \"OL\"\n\
                    SETINFO ups.type \"offline / line interactive\"\n\
                    ADDCMD beeper.toggle\n\
                    DATAOK\n\
                    DUMPDONE\n";
        let reading = Reading::from_dump(dump).unwrap();
        assert_eq!(reading.status.as_deref(), Some("OL"));
        assert_eq!(sample(&reading, "rack_battery_charge_percent"), Some(100.0));
        assert_eq!(sample(&reading, "rack_battery_voltage_volts"), Some(13.3));
        assert_eq!(sample(&reading, "rack_mains_input_voltage_volts"), Some(241.4));
        assert_eq!(reading.samples.len(), 3);
    }

    #[test]
    fn dump_without_variables_is_empty() {
        assert_eq!(Reading::from_dump("DATAOK\nDUMPDONE\n").unwrap(), Reading::default());
        assert_eq!(Reading::from_dump("").unwrap(), Reading::default());
    }

    #[test]
    fn dump_marked_stale_is_an_error() {
        let stale = "SETINFO ups.status \"OL\"\nDATASTALE\nDUMPDONE\n";
        assert!(matches!(Reading::from_dump(stale), Err(Error::Stale)));
        let recovered = "DATASTALE\nSETINFO ups.status \"OL\"\nDATAOK\nDUMPDONE\n";
        assert!(Reading::from_dump(recovered).is_ok());
    }

    #[test]
    fn reading_maps_every_reported_variable() {
        let reading = Reading::from_variables(REPORTED);
        assert_eq!(reading.status.as_deref(), Some("OL"));
        assert_eq!(reading.samples.len(), SAMPLES.len());
        assert_eq!(sample(&reading, "rack_battery_charge_percent"), Some(100.0));
        assert_eq!(sample(&reading, "rack_battery_voltage_volts"), Some(13.4));
        assert_eq!(sample(&reading, "rack_mains_input_voltage_volts"), Some(241.4));
        assert_eq!(sample(&reading, "rack_mains_output_voltage_volts"), Some(241.4));
        assert_eq!(sample(&reading, "rack_mains_output_frequency_hertz"), Some(50.1));
        assert_eq!(sample(&reading, "rack_mains_input_voltage_fault_volts"), Some(241.4));
        assert_eq!(sample(&reading, "rack_mains_utilisation_percent"), Some(13.0));
    }

    #[test]
    fn reading_omits_missing_and_unparseable_variables() {
        let reading = Reading::from_variables([
            ("input.voltage", "241.4"),
            ("battery.charge", ""),
            ("battery.voltage", "n/a"),
            ("ups.load", "NaN"),
            ("ups.status", "  "),
        ]);
        assert_eq!(reading.status, None);
        assert_eq!(reading.samples, vec![("rack_mains_input_voltage_volts", 241.4)]);
    }

    #[test]
    fn reading_keeps_the_status_flags_verbatim() {
        let reading = Reading::from_variables([("ups.status", "OB LB")]);
        assert_eq!(reading.status.as_deref(), Some("OB LB"));
        assert!(reading.samples.is_empty());
    }
}
