//! DS2480B UART-to-1-Wire bridge.
//!
//! - [AN192: Using the DS2480B Serial 1-Wire Line Driver](https://www.analog.com/en/resources/technical-articles/using-the-ds2480b-serial-1wire-line-driver.html)
//! - [AN187: 1-Wire Search Algorithm](https://www.analog.com/en/resources/app-notes/1wire-search-algorithm.html)
//! - [DS2480B Datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds2480b.pdf)
use std::thread;
use std::time::Duration;

use log::{debug, info};

use super::onewire::{OneWire, Presence};
use super::uart::{SerialUart, Uart};
use super::{Error, Result};

const MODE_DATA: u8 = 0xE1;
const MODE_COMMAND: u8 = 0xE3;
const MODE_STOP_PULSE: u8 = 0xF1;
const CMD_COMM: u8 = 0x81;
const CMD_CONFIG: u8 = 0x01;
const FUNCTSEL_BIT: u8 = 0x00;
const FUNCTSEL_SEARCHOFF: u8 = 0x20;
const FUNCTSEL_SEARCHON: u8 = 0x30;
const FUNCTSEL_RESET: u8 = 0x40;
const BITPOL_ONE: u8 = 0x10;
const BITPOL_ZERO: u8 = 0x00;
const PRIME5V: u8 = 0x02;
const SPEEDSEL_FLEX: u8 = 0x04;
const PARMSEL_PARMREAD: u8 = 0x00;
const PARMSEL_SLEW: u8 = 0x10;
const PARMSEL_5VPULSE: u8 = 0x30;
const PARMSEL_WRITE1LOW: u8 = 0x40;
const PARMSEL_SAMPLEOFFSET: u8 = 0x50;
const PARMSEL_BAUDRATE: u8 = 0x70;
const PARMSET_SLEW_1P37VUS: u8 = 0x06;
const PARMSET_PULSE_INFINITE: u8 = 0x0E;
const PARMSET_WRITE1LOW_10US: u8 = 0x04;
const PARMSET_SAMPLEOFFSET_8US: u8 = 0x0A;
const PARMSET_BAUD_9600: u8 = 0x00;
const RB_CHIPID_MASK: u8 = 0x1C;
const RB_CHIPID: u8 = 0x0C;
const RB_RESET_MASK: u8 = 0x03;
const RB_RESET_SHORTED: u8 = 0x00;
const RB_RESET_PRESENCE: u8 = 0x01;
const RB_RESET_ALARM: u8 = 0x02;
const RB_BIT_MASK: u8 = 0x03;
const RB_BIT_ONE: u8 = 0x03;
const RB_BIT_PATTERN_MASK: u8 = 0xE0;
const RB_BIT_PATTERN: u8 = 0x80;
const RB_CONFIG_ERROR_MASK: u8 = 0x81;
const RB_CONFIG_BYTE_MASK: u8 = 0xF1;
const RB_CONFIG_BYTE: u8 = 0x00;
const RB_CONFIG_BAUD_MASK: u8 = 0x0E;
const RB_DETECT_BIT_MASK: u8 = 0xF0;
const RB_DETECT_BIT: u8 = 0x90;
const RB_DETECT_BAUD_MASK: u8 = 0x0C;
const RB_STOP_PULSE_MASK: u8 = 0xE0;
const RB_STOP_PULSE: u8 = 0xE0;
const READ_SLOT: u8 = 0xFF;
const SEARCH_BYTES: usize = 16;
const DETECT_ATTEMPTS: usize = 10;
const PROBE_ATTEMPTS: usize = 2;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Mode {
    Command,
    Data,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Level {
    Normal,
    Strong5,
}

pub struct Ds2480b<U: Uart> {
    pub(crate) uart: U,
    mode: Mode,
    level: Level,
}

impl Ds2480b<SerialUart> {
    pub fn open(path: &str, timeout: Duration) -> Result<Self> {
        info!("opening ds2480b on [{path}]");
        Ds2480b::new(SerialUart::open(path, timeout)?)
    }
}

impl<U: Uart> Ds2480b<U> {
    pub fn new(uart: U) -> Result<Self> {
        let mut bus = Ds2480b::from_uart(uart);
        bus.detect()?;
        Ok(bus)
    }

    pub fn from_uart(uart: U) -> Self {
        Ds2480b {
            uart,
            mode: Mode::Command,
            level: Level::Normal,
        }
    }

    pub fn into_uart(self) -> U {
        self.uart
    }

    pub fn probe(&mut self) -> Result<()> {
        self.detect_with(PROBE_ATTEMPTS)
    }

    fn detect(&mut self) -> Result<()> {
        self.detect_with(DETECT_ATTEMPTS)
    }

    fn detect_with(&mut self, attempts: usize) -> Result<()> {
        let mut attempt = 0;
        loop {
            attempt += 1;
            match self.try_detect() {
                Ok(()) => {
                    info!("ds2480b detected on attempt [{attempt}] of [{attempts}]");
                    return Ok(());
                }
                Err(err) if attempt >= attempts => return Err(err),
                Err(err) => {
                    debug!("ds2480b detect attempt [{attempt}] failed: {err}");
                }
            }
        }
    }

    fn try_detect(&mut self) -> Result<()> {
        self.mode = Mode::Command;
        self.level = Level::Normal;
        self.uart.send_break()?;
        thread::sleep(Duration::from_millis(2));
        self.uart.clear()?;
        self.uart.write_all(&[CMD_COMM | FUNCTSEL_RESET])?;
        thread::sleep(Duration::from_millis(4));
        self.uart.clear()?;
        let packet = [
            CMD_CONFIG | PARMSEL_SLEW | PARMSET_SLEW_1P37VUS,
            CMD_CONFIG | PARMSEL_WRITE1LOW | PARMSET_WRITE1LOW_10US,
            CMD_CONFIG | PARMSEL_SAMPLEOFFSET | PARMSET_SAMPLEOFFSET_8US,
            CMD_CONFIG | PARMSEL_PARMREAD | (PARMSEL_BAUDRATE >> 3),
            CMD_COMM | FUNCTSEL_BIT | PARMSET_BAUD_9600 | BITPOL_ONE,
        ];
        self.uart.write_all(&packet)?;
        let mut response = [0u8; 5];
        self.uart.read_exact(&mut response)?;
        if response[3] & RB_CONFIG_BYTE_MASK != RB_CONFIG_BYTE
            || response[3] & RB_CONFIG_BAUD_MASK != PARMSET_BAUD_9600
            || response[4] & RB_DETECT_BIT_MASK != RB_DETECT_BIT
            || response[4] & RB_DETECT_BAUD_MASK != PARMSET_BAUD_9600
        {
            return Err(Error::NotDetected(response));
        }
        Ok(())
    }

    fn set_mode(&mut self, mode: Mode) -> Result<()> {
        if self.mode != mode {
            let switch = match mode {
                Mode::Command => MODE_COMMAND,
                Mode::Data => MODE_DATA,
            };
            self.uart.write_all(&[switch])?;
            self.mode = mode;
        }
        Ok(())
    }

    fn write_data(&mut self, data: &[u8]) -> Result<()> {
        self.stop_pulse()?;
        self.set_mode(Mode::Data)?;
        let mut escaped = Vec::with_capacity(data.len() + 1);
        for &byte in data {
            escaped.push(byte);
            if byte == MODE_COMMAND {
                escaped.push(byte);
            }
        }
        self.uart.write_all(&escaped)
    }
}

impl<U: Uart> OneWire for Ds2480b<U> {
    fn redetect(&mut self) -> Result<()> {
        self.detect()
    }

    fn reset(&mut self) -> Result<Presence> {
        self.stop_pulse()?;
        self.set_mode(Mode::Command)?;
        self.uart.write_all(&[CMD_COMM | FUNCTSEL_RESET | SPEEDSEL_FLEX])?;
        let mut response = [0u8; 1];
        self.uart.read_exact(&mut response)?;
        if response[0] & RB_CHIPID_MASK != RB_CHIPID {
            return Err(Error::InvalidResponse {
                operation: "reset",
                response: response[0],
            });
        }
        let presence = match response[0] & RB_RESET_MASK {
            RB_RESET_SHORTED => Presence::Shorted,
            RB_RESET_PRESENCE => Presence::Present,
            RB_RESET_ALARM => Presence::AlarmingPresent,
            _ => Presence::Absent,
        };
        debug!("reset returned [{presence:?}]");
        Ok(presence)
    }

    fn touch_bit(&mut self, bit: bool) -> Result<bool> {
        self.stop_pulse()?;
        self.set_mode(Mode::Command)?;
        let bitpol = if bit { BITPOL_ONE } else { BITPOL_ZERO };
        self.uart
            .write_all(&[CMD_COMM | FUNCTSEL_BIT | bitpol | SPEEDSEL_FLEX])?;
        let mut response = [0u8; 1];
        self.uart.read_exact(&mut response)?;
        if response[0] & RB_BIT_PATTERN_MASK != RB_BIT_PATTERN {
            return Err(Error::InvalidResponse {
                operation: "bit",
                response: response[0],
            });
        }
        Ok(response[0] & RB_BIT_MASK == RB_BIT_ONE)
    }

    fn write_bytes(&mut self, data: &[u8]) -> Result<()> {
        self.write_data(data)?;
        let mut echo = vec![0u8; data.len()];
        self.uart.read_exact(&mut echo)?;
        if echo != data {
            return Err(Error::EchoMismatch);
        }
        Ok(())
    }

    fn read_bytes(&mut self, count: usize) -> Result<Vec<u8>> {
        self.stop_pulse()?;
        self.set_mode(Mode::Data)?;
        self.uart.write_all(&vec![READ_SLOT; count])?;
        let mut data = vec![0u8; count];
        self.uart.read_exact(&mut data)?;
        Ok(data)
    }

    fn write_byte_power(&mut self, byte: u8) -> Result<()> {
        self.set_mode(Mode::Command)?;
        let mut packet = [0u8; 9];
        packet[0] = CMD_CONFIG | PARMSEL_5VPULSE | PARMSET_PULSE_INFINITE;
        for i in 0..8 {
            let bitpol = if (byte >> i) & 0x01 != 0 {
                BITPOL_ONE
            } else {
                BITPOL_ZERO
            };
            let prime = if i == 7 { PRIME5V } else { 0x00 };
            packet[i + 1] = CMD_COMM | FUNCTSEL_BIT | bitpol | SPEEDSEL_FLEX | prime;
        }
        self.uart.write_all(&packet)?;
        let mut response = [0u8; 9];
        self.uart.read_exact(&mut response)?;
        if response[0] & RB_CONFIG_ERROR_MASK != 0x00 {
            return Err(Error::InvalidResponse {
                operation: "pulse config",
                response: response[0],
            });
        }
        self.level = Level::Strong5;
        let mut echo = 0u8;
        for (i, &bit_response) in response[1..].iter().enumerate() {
            echo |= (bit_response & 0x01) << i;
        }
        if echo != byte {
            self.stop_pulse()?;
            return Err(Error::EchoMismatch);
        }
        debug!("strong pullup armed after byte [{byte:#04X}]");
        Ok(())
    }

    fn supports_strong_pullup(&self) -> bool {
        true
    }

    fn stop_pulse(&mut self) -> Result<()> {
        if self.level != Level::Normal {
            self.set_mode(Mode::Command)?;
            self.uart.write_all(&[MODE_STOP_PULSE])?;
            thread::sleep(Duration::from_millis(4));
            let mut response = [0u8; 1];
            self.uart.read_exact(&mut response)?;
            if response[0] & RB_STOP_PULSE_MASK != RB_STOP_PULSE {
                return Err(Error::InvalidResponse {
                    operation: "stop pulse",
                    response: response[0],
                });
            }
            self.level = Level::Normal;
        }
        Ok(())
    }

    fn search_pass(&mut self, seed: &[bool]) -> Result<([bool; 64], [bool; 64])> {
        self.set_mode(Mode::Command)?;
        self.uart.write_all(&[CMD_COMM | FUNCTSEL_SEARCHON | SPEEDSEL_FLEX])?;
        let mut request = [0u8; SEARCH_BYTES];
        for (i, &bit) in seed.iter().enumerate() {
            if bit {
                request[(2 * i + 1) / 8] |= 1 << ((2 * i + 1) % 8);
            }
        }
        self.write_data(&request)?;
        let mut response = [0u8; SEARCH_BYTES];
        self.uart.read_exact(&mut response)?;
        self.set_mode(Mode::Command)?;
        self.uart.write_all(&[CMD_COMM | FUNCTSEL_SEARCHOFF | SPEEDSEL_FLEX])?;
        let mut bits = [false; 64];
        let mut discrepancies = [false; 64];
        for i in 0..64 {
            discrepancies[i] = (response[(2 * i) / 8] >> ((2 * i) % 8)) & 0x01 != 0;
            bits[i] = (response[(2 * i + 1) / 8] >> ((2 * i + 1) % 8)) & 0x01 != 0;
        }
        Ok((bits, discrepancies))
    }
}

#[cfg(test)]
mod tests {
    use super::super::crc::crc8;
    use super::super::rom::Rom;
    use super::super::uart::mock::MockUart;
    use super::*;

    const DETECT_WRITES: [u8; 6] = [0xC1, 0x17, 0x45, 0x5B, 0x0F, 0x91];
    const DETECT_RESPONSE: [u8; 5] = [0x16, 0x44, 0x5A, 0x00, 0x93];

    fn make_bus() -> Ds2480b<MockUart> {
        let mut uart = MockUart::new();
        uart.queue_read(&DETECT_RESPONSE);
        Ds2480b::new(uart).unwrap()
    }

    fn written(bus: &Ds2480b<MockUart>) -> &[u8] {
        &bus.uart.written[DETECT_WRITES.len()..]
    }

    fn rom_with_serial(serial: [u8; 6]) -> Rom {
        let mut code = [0u8; 8];
        code[0] = 0x28;
        code[1..7].copy_from_slice(&serial);
        code[7] = crc8(&code[..7]);
        Rom(code)
    }

    fn search_response(seed: &[bool], roms: &[Rom]) -> ([u8; 16], [bool; 64]) {
        let mut candidates: Vec<[bool; 64]> = roms.iter().map(|rom| rom.bits()).collect();
        let mut response = [0u8; 16];
        let mut path = [false; 64];
        for i in 0..64 {
            let ones = candidates.iter().filter(|bits| bits[i]).count();
            let zeros = candidates.len() - ones;
            let (bit, discrepancy) = if candidates.is_empty() {
                (true, false)
            } else if ones > 0 && zeros > 0 {
                (i < seed.len() && seed[i], true)
            } else {
                (ones > 0, false)
            };
            candidates.retain(|bits| bits[i] == bit);
            path[i] = bit;
            if discrepancy {
                response[(2 * i) / 8] |= 1 << ((2 * i) % 8);
            }
            if bit {
                response[(2 * i + 1) / 8] |= 1 << ((2 * i + 1) % 8);
            }
        }
        (response, path)
    }

    #[test]
    fn detect_sends_calibration_config_and_test_bit() {
        let bus = make_bus();
        assert_eq!(bus.uart.written, DETECT_WRITES);
        assert_eq!(bus.uart.breaks, 1);
        assert_eq!(bus.uart.clears, 2);
        assert!(bus.uart.reads.is_empty());
    }

    #[test]
    fn detect_ignores_config_write_echoes() {
        let mut uart = MockUart::new();
        uart.queue_read(&[0xAA, 0xBB, 0xCC, 0x00, 0x90]);
        assert!(Ds2480b::new(uart).is_ok());
    }

    #[test]
    fn detect_retries_after_bad_response() {
        let mut uart = MockUart::new();
        uart.queue_read(&[0x16, 0x44, 0x5A, 0x02, 0x93]);
        uart.queue_read(&DETECT_RESPONSE);
        let bus = Ds2480b::new(uart).unwrap();
        assert_eq!(bus.uart.breaks, 2);
        assert_eq!(bus.uart.written.len(), 2 * DETECT_WRITES.len());
    }

    #[test]
    fn detect_fails_after_exhausted_retries() {
        let mut uart = MockUart::new();
        uart.queue_read(&[0x16, 0x44, 0x5A, 0x02, 0x00]);
        assert!(Ds2480b::new(uart).is_err());
    }

    #[test]
    fn probe_gives_up_after_two_attempts() {
        let mut bus = Ds2480b::from_uart(MockUart::new());
        assert!(bus.probe().is_err());
        assert_eq!(bus.uart.breaks, 2);
    }

    #[test]
    fn strong_pullup_is_supported() {
        assert!(make_bus().supports_strong_pullup());
    }

    #[test]
    fn reset_decodes_presence_variants() {
        for (response, presence) in [
            (0xCDu8, Presence::Present),
            (0xCE, Presence::AlarmingPresent),
            (0xCF, Presence::Absent),
            (0xCC, Presence::Shorted),
        ] {
            let mut bus = make_bus();
            bus.uart.queue_read(&[response]);
            assert_eq!(bus.reset().unwrap(), presence);
            assert_eq!(written(&bus), [0xC5]);
        }
    }

    #[test]
    fn reset_rejects_bad_chip_id() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xC1]);
        assert!(matches!(bus.reset(), Err(Error::InvalidResponse { .. })));
    }

    #[test]
    fn bit_commands_encode_polarity_and_decode_response() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0x97, 0x94, 0x97, 0x84]);
        assert!(bus.read_bit().unwrap());
        assert!(!bus.read_bit().unwrap());
        bus.write_bit(true).unwrap();
        bus.write_bit(false).unwrap();
        assert_eq!(written(&bus), [0x95, 0x95, 0x95, 0x85]);
    }

    #[test]
    fn bit_commands_reject_malformed_response() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0x17]);
        assert!(matches!(bus.read_bit(), Err(Error::InvalidResponse { .. })));
    }

    #[test]
    fn write_bit_rejects_echo_mismatch() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0x94]);
        assert!(matches!(bus.write_bit(true), Err(Error::EchoMismatch)));
    }

    #[test]
    fn write_bytes_verifies_echo() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xAA, 0x55]);
        bus.write_bytes(&[0xAA, 0x55]).unwrap();
        assert_eq!(written(&bus), [0xE1, 0xAA, 0x55]);
    }

    #[test]
    fn write_bytes_rejects_echo_mismatch() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xAB]);
        assert!(matches!(bus.write_bytes(&[0xAA]), Err(Error::EchoMismatch)));
    }

    #[test]
    fn write_bytes_escapes_command_mode_byte() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xE3, 0x01]);
        bus.write_bytes(&[0xE3, 0x01]).unwrap();
        assert_eq!(written(&bus), [0xE1, 0xE3, 0xE3, 0x01]);
    }

    #[test]
    fn read_bytes_sends_read_slots() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0x01, 0x02, 0x03]);
        assert_eq!(bus.read_bytes(3).unwrap(), vec![0x01, 0x02, 0x03]);
        assert_eq!(written(&bus), [0xE1, 0xFF, 0xFF, 0xFF]);
    }

    #[test]
    fn mode_switches_only_when_needed() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0x11, 0x22, 0x97]);
        bus.write_bytes(&[0x11]).unwrap();
        bus.write_bytes(&[0x22]).unwrap();
        assert!(bus.read_bit().unwrap());
        assert_eq!(written(&bus), [0xE1, 0x11, 0x22, 0xE3, 0x95]);
    }

    #[test]
    fn write_byte_power_arms_strong_pullup() {
        let mut bus = make_bus();
        bus.uart
            .queue_read(&[0x3E, 0x94, 0x94, 0x97, 0x94, 0x94, 0x94, 0x97, 0x94]);
        bus.write_byte_power(0x44).unwrap();
        assert_eq!(written(&bus), [0x3F, 0x85, 0x85, 0x95, 0x85, 0x85, 0x85, 0x95, 0x87]);
    }

    #[test]
    fn write_byte_power_rejects_bad_config_response() {
        let mut bus = make_bus();
        bus.uart
            .queue_read(&[0x81, 0x94, 0x94, 0x97, 0x94, 0x94, 0x94, 0x97, 0x94]);
        assert!(matches!(bus.write_byte_power(0x44), Err(Error::InvalidResponse { .. })));
    }

    #[test]
    fn write_byte_power_rejects_echo_mismatch_and_stops_pulse() {
        let mut bus = make_bus();
        bus.uart
            .queue_read(&[0x3E, 0x97, 0x94, 0x97, 0x94, 0x94, 0x94, 0x97, 0x94]);
        bus.uart.queue_read(&[0xF1]);
        assert!(matches!(bus.write_byte_power(0x44), Err(Error::EchoMismatch)));
        assert_eq!(*written(&bus).last().unwrap(), 0xF1);
    }

    #[test]
    fn stop_pulse_terminates_before_next_operation() {
        let mut bus = make_bus();
        bus.uart
            .queue_read(&[0x3E, 0x94, 0x94, 0x97, 0x94, 0x94, 0x94, 0x97, 0x94]);
        bus.write_byte_power(0x44).unwrap();
        bus.uart.queue_read(&[0xF1, 0xCD]);
        assert_eq!(bus.reset().unwrap(), Presence::Present);
        let writes = written(&bus);
        assert_eq!(&writes[writes.len() - 2..], [0xF1, 0xC5]);
    }

    #[test]
    fn stop_pulse_rejects_malformed_response() {
        let mut bus = make_bus();
        bus.uart
            .queue_read(&[0x3E, 0x94, 0x94, 0x97, 0x94, 0x94, 0x94, 0x97, 0x94]);
        bus.write_byte_power(0x44).unwrap();
        bus.uart.queue_read(&[0x00]);
        assert!(matches!(bus.stop_pulse(), Err(Error::InvalidResponse { .. })));
    }

    #[test]
    fn read_rom_returns_validated_rom() {
        let rom = rom_with_serial([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC]);
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xCD, 0x33]);
        bus.uart.queue_read(&rom.0);
        assert_eq!(bus.read_rom().unwrap(), rom);
        let mut expected = vec![0xC5, 0xE1, 0x33];
        expected.extend([0xFF; 8]);
        assert_eq!(written(&bus), expected);
    }

    #[test]
    fn read_rom_rejects_bad_crc() {
        let mut rom = rom_with_serial([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC]);
        rom.0[7] = rom.0[7].wrapping_add(1);
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xCD, 0x33]);
        bus.uart.queue_read(&rom.0);
        assert!(matches!(bus.read_rom(), Err(Error::Crc)));
    }

    #[test]
    fn read_rom_requires_presence() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xCF]);
        assert!(matches!(bus.read_rom(), Err(Error::NoDevice)));
    }

    #[test]
    fn match_rom_sends_command_and_rom() {
        let rom = rom_with_serial([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC]);
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xCD]);
        let mut echo = vec![0x55];
        echo.extend(rom.0);
        bus.uart.queue_read(&echo);
        bus.match_rom(&rom).unwrap();
        let mut expected = vec![0xC5, 0xE1, 0x55];
        expected.extend(rom.0);
        assert_eq!(written(&bus), expected);
    }

    #[test]
    fn skip_rom_sends_command() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xCD, 0xCC]);
        bus.skip_rom().unwrap();
        assert_eq!(written(&bus), [0xC5, 0xE1, 0xCC]);
    }

    #[test]
    fn search_finds_single_device() {
        let rom = rom_with_serial([0, 0, 0, 0, 0, 0]);
        let mut bus = make_bus();
        let (response, _) = search_response(&[], &[rom]);
        bus.uart.queue_read(&[0xCD, 0xF0]);
        bus.uart.queue_read(&response);
        assert_eq!(bus.get_connected_roms().unwrap(), vec![rom]);
        let mut expected = vec![0xC5, 0xE1, 0xF0, 0xE3, 0xB5, 0xE1];
        expected.extend([0x00; 16]);
        expected.extend([0xE3, 0xA5]);
        assert_eq!(written(&bus), expected);
    }

    #[test]
    fn search_branches_on_discrepancies() {
        let rom_a = rom_with_serial([0x00, 0, 0, 0, 0, 0]);
        let rom_b = rom_with_serial([0x01, 0, 0, 0, 0, 0]);
        let devices = [rom_a, rom_b];
        let (response_a, path_a) = search_response(&[], &devices);
        let mut branch = path_a[..8].to_vec();
        branch.push(true);
        let (response_b, _) = search_response(&branch, &devices);
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xCD, 0xF0]);
        bus.uart.queue_read(&response_a);
        bus.uart.queue_read(&[0xCD, 0xF0]);
        bus.uart.queue_read(&response_b);
        assert_eq!(bus.get_connected_roms().unwrap(), vec![rom_a, rom_b]);
        assert!(bus.uart.reads.is_empty());
    }

    #[test]
    fn search_ignores_discrepancy_on_taken_one_branch() {
        let rom = rom_with_serial([0, 0, 0, 0, 0, 0]);
        let (mut response, path) = search_response(&[], &[rom]);
        let taken_one = path.iter().position(|&bit| bit).unwrap();
        response[(2 * taken_one) / 8] |= 1 << ((2 * taken_one) % 8);
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xCD, 0xF0]);
        bus.uart.queue_read(&response);
        assert_eq!(bus.get_connected_roms().unwrap(), vec![rom]);
        assert!(bus.uart.reads.is_empty());
    }

    #[test]
    fn search_returns_empty_when_bus_absent() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xCF]);
        assert_eq!(bus.get_connected_roms().unwrap(), vec![]);
        assert_eq!(written(&bus), [0xC5]);
    }

    #[test]
    fn search_errors_when_bus_shorted() {
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xCC]);
        assert!(matches!(bus.get_connected_roms(), Err(Error::Shorted)));
    }

    #[test]
    fn search_rejects_bad_crc() {
        let mut rom = rom_with_serial([0, 0, 0, 0, 0, 0]);
        rom.0[7] = rom.0[7].wrapping_add(1);
        let mut bus = make_bus();
        let (response, _) = search_response(&[], &[rom]);
        bus.uart.queue_read(&[0xCD, 0xF0]);
        bus.uart.queue_read(&response);
        assert!(matches!(bus.get_connected_roms(), Err(Error::Crc)));
    }

    #[test]
    fn alarm_search_uses_alarm_command() {
        let rom = rom_with_serial([0, 0, 0, 0, 0, 0]);
        let mut bus = make_bus();
        let (response, _) = search_response(&[], &[rom]);
        bus.uart.queue_read(&[0xCD, 0xEC]);
        bus.uart.queue_read(&response);
        assert_eq!(bus.alarm_search().unwrap(), vec![rom]);
        assert_eq!(written(&bus)[2], 0xEC);
    }

    #[test]
    fn alarm_search_without_alarming_devices_is_empty() {
        let mut bus = make_bus();
        let (response, _) = search_response(&[], &[]);
        bus.uart.queue_read(&[0xCD, 0xEC]);
        bus.uart.queue_read(&response);
        assert_eq!(bus.alarm_search().unwrap(), vec![]);
    }

    #[test]
    fn is_connected_detects_device() {
        let rom = rom_with_serial([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC]);
        let mut bus = make_bus();
        let (response, _) = search_response(&rom.bits(), &[rom]);
        bus.uart.queue_read(&[0xCD, 0xF0]);
        bus.uart.queue_read(&response);
        assert!(bus.is_connected(&rom).unwrap());
    }

    #[test]
    fn is_connected_detects_missing_device() {
        let rom = rom_with_serial([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC]);
        let other = rom_with_serial([0x00, 0x00, 0x00, 0x00, 0x00, 0x01]);
        let mut bus = make_bus();
        let (response, _) = search_response(&rom.bits(), &[other]);
        bus.uart.queue_read(&[0xCD, 0xF0]);
        bus.uart.queue_read(&response);
        assert!(!bus.is_connected(&rom).unwrap());
    }

    #[test]
    fn is_connected_is_false_when_bus_absent() {
        let rom = rom_with_serial([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC]);
        let mut bus = make_bus();
        bus.uart.queue_read(&[0xCF]);
        assert!(!bus.is_connected(&rom).unwrap());
    }
}
