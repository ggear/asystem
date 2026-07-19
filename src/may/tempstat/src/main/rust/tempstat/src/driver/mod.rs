//! 1-Wire bus driver — shared error types and protocol primitives.
//!
//! - [Guide to 1-Wire Communication](https://www.analog.com/en/resources/technical-articles/guide-to-1wire-communication.html)

pub mod bus;
pub mod crc;
pub mod mock;
pub mod rom;
pub mod sensor;
pub mod uart;

pub use crc::crc8;
pub use rom::Rom;

use std::fmt;
use std::io;

#[derive(Debug)]
pub enum Error {
    Io(io::Error),
    Serial(serialport::Error),
    NotDetected([u8; 5]),
    InvalidResponse { operation: &'static str, response: u8 },
    EchoMismatch,
    NoDevice,
    Shorted,
    WrongFamily(Rom),
    InvalidRom(String),
    Crc,
    Timeout,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::Io(err) => write!(f, "io error: {err}"),
            Error::Serial(err) => write!(f, "serial error: {err}"),
            Error::NotDetected(response) => write!(f, "ds2480b not detected, response {response:02X?}"),
            Error::InvalidResponse { operation, response } => {
                write!(f, "invalid {operation} response [{response:#04X}]")
            }
            Error::EchoMismatch => write!(f, "echo mismatch"),
            Error::NoDevice => write!(f, "no device present"),
            Error::Shorted => write!(f, "bus shorted"),
            Error::WrongFamily(rom) => write!(f, "not a ds18b20 [{rom}]"),
            Error::InvalidRom(value) => write!(f, "invalid rom code [{value}]"),
            Error::Crc => write!(f, "crc check failed"),
            Error::Timeout => write!(f, "timed out waiting for device"),
        }
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            Error::Io(err) => Some(err),
            Error::Serial(err) => Some(err),
            _ => None,
        }
    }
}

impl From<io::Error> for Error {
    fn from(err: io::Error) -> Self {
        Error::Io(err)
    }
}

impl From<serialport::Error> for Error {
    fn from(err: serialport::Error) -> Self {
        Error::Serial(err)
    }
}

pub type Result<T> = std::result::Result<T, Error>;

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn error_display_is_descriptive() {
        assert_eq!(Error::NoDevice.to_string(), "no device present");
        assert_eq!(Error::Shorted.to_string(), "bus shorted");
        assert_eq!(Error::EchoMismatch.to_string(), "echo mismatch");
        assert_eq!(Error::Crc.to_string(), "crc check failed");
        assert_eq!(Error::Timeout.to_string(), "timed out waiting for device");
        assert_eq!(
            Error::InvalidResponse {
                operation: "reset",
                response: 0xC1
            }
            .to_string(),
            "invalid reset response [0xC1]"
        );
        assert_eq!(
            Error::InvalidRom("nope".to_string()).to_string(),
            "invalid rom code [nope]"
        );
    }

    #[test]
    fn error_chains_io_source() {
        use std::error::Error as _;
        let err: Error = io::Error::new(io::ErrorKind::TimedOut, "timed out").into();
        assert!(matches!(err, Error::Io(_)));
        assert!(err.source().is_some());
        assert!(Error::Crc.source().is_none());
    }
}
