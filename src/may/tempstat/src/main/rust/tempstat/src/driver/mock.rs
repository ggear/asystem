//! Device emulators for driving the real drivers over a serial link — a DS2480B bridge with an
//! attached DS18B20 (`MockDs2480b`), and a bare DS18B20 as seen through a DS9097 passive adapter
//! (`MockDs9097`).

use std::collections::VecDeque;

use super::crc8;
use super::rom::Rom;

const SCRATCHPAD: [u8; 8] = [0x91, 0x01, 0x4B, 0x46, 0x7F, 0xFF, 0x0C, 0x10];
const ROM: [u8; 7] = [0x28, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC];
const RESET_PULSE: u8 = 0xF0;
const PRESENCE: u8 = 0xE0;

pub trait Emulator {
    fn feed(&mut self, byte: u8, out: &mut Vec<u8>);
}

pub struct MockDs2480b {
    command: bool,
    pending: VecDeque<u8>,
}

impl Default for MockDs2480b {
    fn default() -> Self {
        MockDs2480b::new()
    }
}

impl MockDs2480b {
    pub fn new() -> Self {
        MockDs2480b {
            command: true,
            pending: VecDeque::new(),
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
        if byte == 0xFF {
            if let Some(pending) = self.pending.pop_front() {
                out.push(pending);
                return;
            }
        }
        out.push(byte);
        match byte {
            0xBE => self.pending = scratchpad().into_iter().collect(),
            0x33 => self.pending = rom().into_iter().collect(),
            _ => {}
        }
    }
}

impl Emulator for MockDs2480b {
    fn feed(&mut self, byte: u8, out: &mut Vec<u8>) {
        match byte {
            0xE3 => self.command = true,
            0xE1 => self.command = false,
            _ if self.command => self.command_byte(byte, out),
            _ => self.data_byte(byte, out),
        }
    }
}

#[derive(Clone, Copy)]
enum State {
    Command,
    MatchRom(u8),
    Search { index: u8, step: Step },
    Offline,
}

#[derive(Clone, Copy)]
enum Step {
    Bit,
    Complement,
    Direction,
}

pub struct MockDs9097 {
    state: State,
    output: VecDeque<bool>,
    byte: u8,
    count: u8,
}

impl Default for MockDs9097 {
    fn default() -> Self {
        MockDs9097::new()
    }
}

impl MockDs9097 {
    pub fn new() -> Self {
        MockDs9097 {
            state: State::Command,
            output: VecDeque::new(),
            byte: 0,
            count: 0,
        }
    }

    fn accumulate(&mut self, bit: bool) {
        if bit {
            self.byte |= 1 << self.count;
        }
        self.count += 1;
        if self.count == 8 {
            let command = self.byte;
            self.byte = 0;
            self.count = 0;
            self.dispatch(command);
        }
    }

    fn dispatch(&mut self, command: u8) {
        match command {
            0x55 => self.state = State::MatchRom(64),
            0x33 => self.output = bit_queue(&rom()),
            0xF0 => {
                self.state = State::Search {
                    index: 0,
                    step: Step::Bit,
                }
            }
            0xBE => self.output = bit_queue(&scratchpad()),
            0xB4 => self.output = VecDeque::from([true]),
            _ => {}
        }
    }
}

impl Emulator for MockDs9097 {
    fn feed(&mut self, byte: u8, out: &mut Vec<u8>) {
        if byte == RESET_PULSE {
            self.state = State::Command;
            self.output.clear();
            self.byte = 0;
            self.count = 0;
            out.push(PRESENCE);
            return;
        }
        let bit = byte & 0x01 != 0;
        match self.state {
            State::Offline => out.push(byte),
            State::MatchRom(remaining) => {
                out.push(byte);
                self.state = if remaining > 1 {
                    State::MatchRom(remaining - 1)
                } else {
                    State::Command
                };
            }
            State::Search { index, step } => {
                let rom_bit = Rom(rom()).bits()[index as usize];
                match step {
                    Step::Bit => {
                        out.push(slot(bit && rom_bit));
                        self.state = State::Search {
                            index,
                            step: Step::Complement,
                        };
                    }
                    Step::Complement => {
                        out.push(slot(bit && !rom_bit));
                        self.state = State::Search {
                            index,
                            step: Step::Direction,
                        };
                    }
                    Step::Direction => {
                        out.push(byte);
                        self.state = if bit != rom_bit {
                            State::Offline
                        } else if index == 63 {
                            State::Command
                        } else {
                            State::Search {
                                index: index + 1,
                                step: Step::Bit,
                            }
                        };
                    }
                }
            }
            State::Command => {
                if bit {
                    if let Some(value) = self.output.pop_front() {
                        out.push(slot(value));
                        return;
                    }
                }
                out.push(byte);
                self.accumulate(bit);
            }
        }
    }
}

fn slot(bit: bool) -> u8 {
    if bit {
        0xFF
    } else {
        0x00
    }
}

fn bit_queue(bytes: &[u8]) -> VecDeque<bool> {
    bytes
        .iter()
        .flat_map(|&byte| (0..8).map(move |bit| (byte >> bit) & 0x01 != 0))
        .collect()
}

fn scratchpad() -> [u8; 9] {
    let mut data = [0u8; 9];
    data[..8].copy_from_slice(&SCRATCHPAD);
    data[8] = crc8(&SCRATCHPAD);
    data
}

fn rom() -> [u8; 8] {
    let mut code = [0u8; 8];
    code[..7].copy_from_slice(&ROM);
    code[7] = crc8(&ROM);
    code
}

#[cfg(test)]
pub mod fsm {
    use std::collections::VecDeque;
    use std::io;

    use super::super::uart::Uart;
    use super::super::{Error, Result};
    use super::Emulator;

    pub struct FsmUart<E: Emulator> {
        pub emulator: E,
        incoming: VecDeque<u8>,
    }

    impl<E: Emulator> FsmUart<E> {
        pub fn new(emulator: E) -> Self {
            FsmUart {
                emulator,
                incoming: VecDeque::new(),
            }
        }
    }

    impl<E: Emulator> Uart for FsmUart<E> {
        fn write_all(&mut self, data: &[u8]) -> Result<()> {
            let mut out = Vec::new();
            for &byte in data {
                out.clear();
                self.emulator.feed(byte, &mut out);
                self.incoming.extend(out.iter().copied());
            }
            Ok(())
        }

        fn read_exact(&mut self, buffer: &mut [u8]) -> Result<()> {
            for slot in buffer.iter_mut() {
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

        fn set_baud(&mut self, _baud: u32) -> Result<()> {
            Ok(())
        }
    }
}

#[cfg(test)]
mod tests {
    use super::super::ds2480b::Ds2480b;
    use super::super::ds9097::Ds9097;
    use super::super::onewire::OneWire;
    use super::super::sensor::{Ds18b20, Resolution};
    use super::fsm::FsmUart;
    use super::*;

    #[test]
    fn mock_drives_real_driver_end_to_end() {
        let mut bus = Ds2480b::new(FsmUart::new(MockDs2480b::new())).unwrap();
        let device = Ds18b20::attach(&mut bus, None).unwrap();
        assert!(!device.parasitic());
        assert_eq!(device.resolution(), Resolution::Bits12);
        let temperature = device.get_temperature(&mut bus).unwrap();
        assert!((temperature - 25.0625).abs() < 0.001);
    }

    #[test]
    fn read_slots_return_scratchpad_only_after_read_command() {
        let mut mock = MockDs2480b::new();
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

    #[test]
    fn mock_drives_ds9097_driver_end_to_end() {
        let mut bus = Ds9097::new(FsmUart::new(MockDs9097::new())).unwrap();
        let device = Ds18b20::attach(&mut bus, None).unwrap();
        assert!(!device.parasitic());
        assert_eq!(device.resolution(), Resolution::Bits12);
        let temperature = device.get_temperature(&mut bus).unwrap();
        assert!((temperature - 25.0625).abs() < 0.001);
    }

    #[test]
    fn mock_ds9097_serves_any_matched_rom() {
        let mut bus = Ds9097::new(FsmUart::new(MockDs9097::new())).unwrap();
        let rom = "28FF641E870006AE".parse().unwrap();
        let device = Ds18b20::attach(&mut bus, Some(rom)).unwrap();
        let temperature = device.get_temperature(&mut bus).unwrap();
        assert!((temperature - 25.0625).abs() < 0.001);
    }

    #[test]
    fn mock_ds9097_answers_rom_search() {
        let mut bus = Ds9097::new(FsmUart::new(MockDs9097::new())).unwrap();
        assert_eq!(bus.get_connected_roms().unwrap(), vec![Rom(rom())]);
    }

    #[test]
    fn mock_ds9097_reports_no_alarms() {
        let mut bus = Ds9097::new(FsmUart::new(MockDs9097::new())).unwrap();
        assert_eq!(bus.alarm_search().unwrap(), vec![]);
    }

    #[test]
    fn mock_ds9097_reads_rom() {
        let mut bus = Ds9097::new(FsmUart::new(MockDs9097::new())).unwrap();
        assert_eq!(bus.read_rom().unwrap(), Rom(rom()));
    }

    #[test]
    fn mock_ds9097_deselects_on_search_direction_mismatch() {
        let mut mock = MockDs9097::new();
        let mut out = Vec::new();
        mock.feed(0xF0, &mut out);
        assert_eq!(out, vec![0xE0]);
        for byte in [0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF] {
            out.clear();
            mock.feed(byte, &mut out);
        }
        out.clear();
        mock.feed(0xFF, &mut out);
        assert_eq!(out, vec![0x00]);
        out.clear();
        mock.feed(0xFF, &mut out);
        assert_eq!(out, vec![0xFF]);
        out.clear();
        mock.feed(0xFF, &mut out);
        assert_eq!(out, vec![0xFF]);
        out.clear();
        mock.feed(0xFF, &mut out);
        assert_eq!(out, vec![0xFF]);
        out.clear();
        mock.feed(0xF0, &mut out);
        assert_eq!(out, vec![0xE0]);
    }

    #[test]
    fn ds2480b_detect_fails_against_passive_mock() {
        assert!(Ds2480b::new(FsmUart::new(MockDs9097::new())).is_err());
    }

    #[test]
    fn auto_fallback_reuses_the_same_uart() {
        let mut ds2480b = Ds2480b::from_uart(FsmUart::new(MockDs9097::new()));
        assert!(ds2480b.probe().is_err());
        let mut bus = Ds9097::new(ds2480b.into_uart()).unwrap();
        let device = Ds18b20::attach(&mut bus, None).unwrap();
        let temperature = device.get_temperature(&mut bus).unwrap();
        assert!((temperature - 25.0625).abs() < 0.001);
    }
}
