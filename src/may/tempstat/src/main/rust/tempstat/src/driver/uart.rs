//! UART abstraction for the DS2480B serial interface.
//!
//! - [Reading and Writing 1-Wire Devices Through Serial Interfaces](https://www.analog.com/en/resources/app-notes/reading-and-writing-1wirereg-devices-through-serial-interfaces.html)

use std::io::{Read, Write};
use std::thread;
use std::time::Duration;

use log::debug;
use serialport::{ClearBuffer, DataBits, FlowControl, Parity, SerialPort, StopBits};

use super::Result;

pub trait Uart {
    fn write_all(&mut self, data: &[u8]) -> Result<()>;
    fn read_exact(&mut self, buf: &mut [u8]) -> Result<()>;
    fn send_break(&mut self) -> Result<()>;
    fn clear(&mut self) -> Result<()>;
}

pub struct SerialUart {
    port: Box<dyn SerialPort>,
}

impl SerialUart {
    pub fn open(path: &str, timeout: Duration) -> Result<Self> {
        let port = serialport::new(path, 9600)
            .data_bits(DataBits::Eight)
            .parity(Parity::None)
            .stop_bits(StopBits::One)
            .flow_control(FlowControl::None)
            .timeout(timeout)
            .open()?;
        Ok(SerialUart { port })
    }
}

impl Uart for SerialUart {
    fn write_all(&mut self, data: &[u8]) -> Result<()> {
        debug!("uart tx {:02X?}", data);
        self.port.write_all(data)?;
        self.port.flush()?;
        Ok(())
    }

    fn read_exact(&mut self, buf: &mut [u8]) -> Result<()> {
        self.port.read_exact(buf)?;
        debug!("uart rx {:02X?}", buf);
        Ok(())
    }

    fn send_break(&mut self) -> Result<()> {
        debug!("uart break");
        self.port.set_break()?;
        thread::sleep(Duration::from_millis(2));
        self.port.clear_break()?;
        Ok(())
    }

    fn clear(&mut self) -> Result<()> {
        debug!("uart clear");
        self.port.clear(ClearBuffer::All)?;
        Ok(())
    }
}

#[cfg(test)]
pub mod mock {
    use std::collections::VecDeque;
    use std::io;

    use super::super::{Error, Result};
    use super::Uart;

    #[derive(Default)]
    pub struct MockUart {
        pub written: Vec<u8>,
        pub reads: VecDeque<u8>,
        pub breaks: usize,
        pub clears: usize,
    }

    impl MockUart {
        pub fn new() -> Self {
            Self::default()
        }

        pub fn queue_read(&mut self, data: &[u8]) {
            self.reads.extend(data.iter().copied());
        }
    }

    impl Uart for MockUart {
        fn write_all(&mut self, data: &[u8]) -> Result<()> {
            self.written.extend_from_slice(data);
            Ok(())
        }

        fn read_exact(&mut self, buf: &mut [u8]) -> Result<()> {
            for slot in buf.iter_mut() {
                *slot = self
                    .reads
                    .pop_front()
                    .ok_or_else(|| Error::Io(io::Error::new(io::ErrorKind::UnexpectedEof, "read underrun")))?;
            }
            Ok(())
        }

        fn send_break(&mut self) -> Result<()> {
            self.breaks += 1;
            Ok(())
        }

        fn clear(&mut self) -> Result<()> {
            self.clears += 1;
            Ok(())
        }
    }
}
