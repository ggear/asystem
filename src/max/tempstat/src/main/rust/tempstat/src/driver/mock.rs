//! DS2480B + DS18B20 device emulator for driving the real driver over a serial link.

use std::collections::VecDeque;

use super::crc8;

const SCRATCHPAD: [u8; 8] = [0x91, 0x01, 0x4B, 0x46, 0x7F, 0xFF, 0x0C, 0x10];
const ROM: [u8; 7] = [0x28, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC];

pub struct Mock {
    command: bool,
    pending: VecDeque<u8>,
}

impl Default for Mock {
    fn default() -> Self {
        Mock::new()
    }
}

impl Mock {
    pub fn new() -> Self {
        Mock {
            command: true,
            pending: VecDeque::new(),
        }
    }

    pub fn feed(&mut self, byte: u8, out: &mut Vec<u8>) {
        match byte {
            0xE3 => self.command = true,
            0xE1 => self.command = false,
            _ if self.command => self.command_byte(byte, out),
            _ => self.data_byte(byte, out),
        }
    }

    fn command_byte(&mut self, byte: u8, out: &mut Vec<u8>) {
        if byte == 0x00 {
            return;
        }
        if byte & 0x80 == 0 {
            out.push(0x00);
            return;
        }
        match byte & 0x60 {
            0x40 => {
                if byte & 0x04 != 0 {
                    out.push(0xCD);
                }
            }
            0x00 => out.push(if byte & 0x04 != 0 { 0x97 } else { 0x93 }),
            _ => out.push(0x97),
        }
    }

    fn data_byte(&mut self, byte: u8, out: &mut Vec<u8>) {
        if byte == 0xFF && !self.pending.is_empty() {
            out.push(self.pending.pop_front().unwrap());
            return;
        }
        out.push(byte);
        match byte {
            0xBE => self.pending = scratchpad().into_iter().collect(),
            0x33 => self.pending = rom().into_iter().collect(),
            _ => {}
        }
    }
}

fn scratchpad() -> [u8; 9] {
    let mut sp = [0u8; 9];
    sp[..8].copy_from_slice(&SCRATCHPAD);
    sp[8] = crc8(&SCRATCHPAD);
    sp
}

fn rom() -> [u8; 8] {
    let mut code = [0u8; 8];
    code[..7].copy_from_slice(&ROM);
    code[7] = crc8(&ROM);
    code
}

#[cfg(test)]
mod tests {
    use std::io;

    use super::super::bus::Bus;
    use super::super::sensor::{Ds18b20, Resolution};
    use super::super::uart::Uart;
    use super::super::{Error, Result};
    use super::*;

    struct FsmUart {
        mock: Mock,
        incoming: VecDeque<u8>,
    }

    impl FsmUart {
        fn new() -> Self {
            FsmUart {
                mock: Mock::new(),
                incoming: VecDeque::new(),
            }
        }
    }

    impl Uart for FsmUart {
        fn write_all(&mut self, data: &[u8]) -> Result<()> {
            let mut out = Vec::new();
            for &byte in data {
                out.clear();
                self.mock.feed(byte, &mut out);
                self.incoming.extend(out.iter().copied());
            }
            Ok(())
        }

        fn read_exact(&mut self, buf: &mut [u8]) -> Result<()> {
            for slot in buf.iter_mut() {
                *slot = self
                    .incoming
                    .pop_front()
                    .ok_or_else(|| Error::Io(io::Error::new(io::ErrorKind::UnexpectedEof, "underrun")))?;
            }
            Ok(())
        }

        fn send_break(&mut self) -> Result<()> {
            Ok(())
        }

        fn clear(&mut self) -> Result<()> {
            self.incoming.clear();
            Ok(())
        }
    }

    #[test]
    fn mock_drives_real_driver_end_to_end() {
        let mut bus = Bus::new(FsmUart::new()).unwrap();
        let device = Ds18b20::attach(&mut bus, None).unwrap();
        assert!(!device.parasitic());
        assert_eq!(device.resolution(), Resolution::Bits12);
        let temperature = device.get_temperature(&mut bus).unwrap();
        assert!((temperature - 25.0625).abs() < 0.001);
    }

    #[test]
    fn read_slots_return_scratchpad_only_after_read_command() {
        let mut mock = Mock::new();
        let mut out = Vec::new();
        mock.feed(0xE1, &mut out);
        out.clear();
        mock.feed(0xFF, &mut out);
        assert_eq!(out, vec![0xFF]);
        out.clear();
        mock.feed(0xBE, &mut out);
        assert_eq!(out, vec![0xBE]);
        for expected in scratchpad() {
            out.clear();
            mock.feed(0xFF, &mut out);
            assert_eq!(out, vec![expected]);
        }
    }
}
