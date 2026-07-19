//! DS9097 passive serial 1-Wire adapter — UART bit-banging, reset at 9600 baud, time slots at 115200 baud.
//!
//! - [DigiTemp DS9097 driver](https://github.com/bcl/digitemp/blob/master/userial/ds9097/linuxlnk.c)
//! - [AN214: Using a UART to Implement a 1-Wire Bus Master](https://www.analog.com/en/resources/technical-articles/using-a-uart-to-implement-a-1wire-bus-master.html)
use std::time::Duration;

use log::{debug, info};

use super::onewire::{OneWire, Presence};
use super::uart::{SerialUart, Uart};
use super::{Error, Result};

const BAUD_RESET: u32 = 9_600;
const BAUD_SLOTS: u32 = 115_200;
const RESET_PULSE: u8 = 0xF0;
const RESET_SHORTED: u8 = 0x00;
const SLOT_ONE: u8 = 0xFF;
const SLOT_ZERO: u8 = 0x00;
const UART_FIFO_SIZE: usize = 160;

pub struct Ds9097<U: Uart> {
    pub(crate) uart: U,
}

impl Ds9097<SerialUart> {
    pub fn open(path: &str, timeout: Duration) -> Result<Self> {
        info!("opening ds9097 on [{path}]");
        Ds9097::new(SerialUart::open(path, timeout)?)
    }
}

impl<U: Uart> Ds9097<U> {
    pub fn new(mut uart: U) -> Result<Self> {
        uart.set_baud(BAUD_SLOTS)?;
        Ok(Ds9097 { uart })
    }

    fn touch_slots(&mut self, slots: &mut [u8]) -> Result<()> {
        self.uart.clear()?;
        for chunk in slots.chunks_mut(UART_FIFO_SIZE) {
            self.uart.write_all(chunk)?;
            self.uart.read_exact(chunk)?;
        }
        Ok(())
    }

    fn touch_block(&mut self, data: &[u8]) -> Result<Vec<u8>> {
        let mut slots: Vec<u8> = data
            .iter()
            .flat_map(|&byte| (0..8).map(move |bit| slot((byte >> bit) & 0x01 != 0)))
            .collect();
        self.touch_slots(&mut slots)?;
        Ok(slots
            .chunks(8)
            .map(|echoes| {
                echoes
                    .iter()
                    .enumerate()
                    .fold(0u8, |byte, (bit, &echo)| byte | ((echo & 0x01) << bit))
            })
            .collect())
    }
}

fn slot(bit: bool) -> u8 {
    if bit {
        SLOT_ONE
    } else {
        SLOT_ZERO
    }
}

impl<U: Uart> OneWire for Ds9097<U> {
    fn redetect(&mut self) -> Result<()> {
        self.reset().map(|_| ())
    }

    fn reset(&mut self) -> Result<Presence> {
        self.uart.clear()?;
        self.uart.set_baud(BAUD_RESET)?;
        self.uart.write_all(&[RESET_PULSE])?;
        let mut echo = [0u8; 1];
        let result = self.uart.read_exact(&mut echo);
        self.uart.set_baud(BAUD_SLOTS)?;
        result?;
        let presence = match echo[0] {
            RESET_SHORTED => Presence::Shorted,
            RESET_PULSE => Presence::Absent,
            _ => Presence::Present,
        };
        debug!("reset returned [{presence:?}]");
        Ok(presence)
    }

    fn touch_bit(&mut self, bit: bool) -> Result<bool> {
        let mut slots = [slot(bit)];
        self.touch_slots(&mut slots)?;
        Ok(slots[0] & 0x01 != 0)
    }

    fn write_bytes(&mut self, data: &[u8]) -> Result<()> {
        if self.touch_block(data)? != data {
            return Err(Error::EchoMismatch);
        }
        Ok(())
    }

    fn read_bytes(&mut self, count: usize) -> Result<Vec<u8>> {
        self.touch_block(&vec![SLOT_ONE; count])
    }

    fn write_byte_power(&mut self, byte: u8) -> Result<()> {
        self.write_bytes(&[byte])
    }

    fn stop_pulse(&mut self) -> Result<()> {
        Ok(())
    }

    fn supports_strong_pullup(&self) -> bool {
        false
    }

    fn search_pass(&mut self, seed: &[bool]) -> Result<([bool; 64], [bool; 64])> {
        let mut bits = [false; 64];
        let mut discrepancies = [false; 64];
        for i in 0..64 {
            let bit = self.touch_bit(true)?;
            let complement = self.touch_bit(true)?;
            if bit && complement {
                bits[i..].fill(true);
                return Ok((bits, discrepancies));
            }
            let direction = if bit != complement {
                bit
            } else {
                discrepancies[i] = true;
                i < seed.len() && seed[i]
            };
            self.touch_bit(direction)?;
            bits[i] = direction;
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

    fn slots_for(bytes: &[u8]) -> Vec<u8> {
        bytes
            .iter()
            .flat_map(|&byte| (0..8).map(move |bit| slot((byte >> bit) & 0x01 != 0)))
            .collect()
    }

    fn queue_echo(uart: &mut MockUart, bytes: &[u8]) {
        uart.queue_read(&slots_for(bytes));
    }

    fn queue_search_response(uart: &mut MockUart, rom: &Rom) {
        for bit in rom.bits() {
            uart.queue_read(&[slot(bit), slot(!bit), slot(bit)]);
        }
    }

    fn rom_with_serial(serial: [u8; 6]) -> Rom {
        let mut code = [0u8; 8];
        code[0] = 0x28;
        code[1..7].copy_from_slice(&serial);
        code[7] = crc8(&code[..7]);
        Rom(code)
    }

    #[test]
    fn reset_pulses_at_reset_baud_and_restores_slot_baud() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        bus.uart.queue_read(&[0xE0]);
        assert_eq!(bus.reset().unwrap(), Presence::Present);
        assert_eq!(bus.uart.written, [0xF0]);
        assert_eq!(bus.uart.bauds, [115_200, 9_600, 115_200]);
        assert_eq!(bus.uart.clears, 1);
    }

    #[test]
    fn reset_decodes_presence_variants() {
        for (echo, presence) in [
            (0xE0u8, Presence::Present),
            (0x90, Presence::Present),
            (0xF0, Presence::Absent),
            (0x00, Presence::Shorted),
        ] {
            let mut bus = Ds9097::new(MockUart::new()).unwrap();
            bus.uart.queue_read(&[echo]);
            assert_eq!(bus.reset().unwrap(), presence);
        }
    }

    #[test]
    fn reset_restores_slot_baud_when_read_fails() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        assert!(bus.reset().is_err());
        assert_eq!(bus.uart.bauds, [115_200, 9_600, 115_200]);
    }

    #[test]
    fn redetect_performs_reset() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        bus.uart.queue_read(&[0xF0]);
        bus.redetect().unwrap();
        assert_eq!(bus.uart.written, [0xF0]);
    }

    #[test]
    fn touch_bit_encodes_slots_and_decodes_echo() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        bus.uart.queue_read(&[0xFF, 0xFE, 0x00]);
        assert!(bus.touch_bit(true).unwrap());
        assert!(!bus.touch_bit(true).unwrap());
        assert!(!bus.touch_bit(false).unwrap());
        assert_eq!(bus.uart.written, [0xFF, 0xFF, 0x00]);
    }

    #[test]
    fn write_bit_rejects_echo_mismatch() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        bus.uart.queue_read(&[0xFE]);
        assert!(matches!(bus.write_bit(true), Err(Error::EchoMismatch)));
    }

    #[test]
    fn write_bytes_sends_one_slot_per_bit_lsb_first() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        queue_echo(&mut bus.uart, &[0xBE]);
        bus.write_bytes(&[0xBE]).unwrap();
        assert_eq!(bus.uart.written, [0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0xFF]);
    }

    #[test]
    fn write_bytes_rejects_echo_mismatch() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        queue_echo(&mut bus.uart, &[0xBF]);
        assert!(matches!(bus.write_bytes(&[0xBE]), Err(Error::EchoMismatch)));
    }

    #[test]
    fn read_bytes_sends_read_slots_and_decodes_echo_bits() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        queue_echo(&mut bus.uart, &[0x91, 0x01]);
        assert_eq!(bus.read_bytes(2).unwrap(), vec![0x91, 0x01]);
        assert_eq!(bus.uart.written, [0xFF; 16]);
    }

    #[test]
    fn touch_block_chunks_at_uart_fifo_size() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        let data = [0xA5u8; 21];
        queue_echo(&mut bus.uart, &data);
        bus.write_bytes(&data).unwrap();
        assert_eq!(bus.uart.written.len(), 21 * 8);
        assert!(bus.uart.reads.is_empty());
    }

    #[test]
    fn write_byte_power_writes_plain_slots() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        queue_echo(&mut bus.uart, &[0x44]);
        bus.write_byte_power(0x44).unwrap();
        assert_eq!(bus.uart.written, slots_for(&[0x44]));
    }

    #[test]
    fn strong_pullup_is_unsupported() {
        let bus = Ds9097::new(MockUart::new()).unwrap();
        assert!(!bus.supports_strong_pullup());
    }

    #[test]
    fn stop_pulse_is_a_no_op() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        bus.stop_pulse().unwrap();
        assert!(bus.uart.written.is_empty());
    }

    #[test]
    fn match_rom_resets_then_writes_command_and_rom() {
        let rom = rom_with_serial([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC]);
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        bus.uart.queue_read(&[0xE0]);
        let mut data = vec![0x55];
        data.extend(rom.0);
        queue_echo(&mut bus.uart, &data);
        bus.match_rom(&rom).unwrap();
        let mut expected = vec![0xF0];
        expected.extend(slots_for(&data));
        assert_eq!(bus.uart.written, expected);
    }

    #[test]
    fn skip_rom_requires_presence() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        bus.uart.queue_read(&[0xF0]);
        assert!(matches!(bus.skip_rom(), Err(Error::NoDevice)));
    }

    #[test]
    fn search_finds_single_device() {
        let rom = rom_with_serial([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC]);
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        bus.uart.queue_read(&[0xE0]);
        queue_echo(&mut bus.uart, &[0xF0]);
        queue_search_response(&mut bus.uart, &rom);
        assert_eq!(bus.get_connected_roms().unwrap(), vec![rom]);
        assert!(bus.uart.reads.is_empty());
    }

    #[test]
    fn search_returns_empty_when_bus_absent() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        bus.uart.queue_read(&[0xF0]);
        assert_eq!(bus.get_connected_roms().unwrap(), vec![]);
    }

    #[test]
    fn alarm_search_without_alarming_devices_is_empty() {
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        bus.uart.queue_read(&[0xE0]);
        queue_echo(&mut bus.uart, &[0xEC]);
        bus.uart.queue_read(&[0xFF, 0xFF]);
        assert_eq!(bus.alarm_search().unwrap(), vec![]);
        assert!(bus.uart.reads.is_empty());
    }

    #[test]
    fn is_connected_detects_device() {
        let rom = rom_with_serial([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC]);
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        bus.uart.queue_read(&[0xE0]);
        queue_echo(&mut bus.uart, &[0xF0]);
        queue_search_response(&mut bus.uart, &rom);
        assert!(bus.is_connected(&rom).unwrap());
    }

    #[test]
    fn is_connected_is_false_when_bus_absent() {
        let rom = rom_with_serial([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC]);
        let mut bus = Ds9097::new(MockUart::new()).unwrap();
        bus.uart.queue_read(&[0xF0]);
        assert!(!bus.is_connected(&rom).unwrap());
    }
}
