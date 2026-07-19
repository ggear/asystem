//! 1-Wire bus master interface — ROM commands and the tree search shared by all adapters.
//!
//! - [Guide to 1-Wire Communication](https://www.analog.com/en/resources/technical-articles/guide-to-1wire-communication.html)
//! - [AN187: 1-Wire Search Algorithm](https://www.analog.com/en/resources/app-notes/1wire-search-algorithm.html)

use log::{debug, info};

use super::rom::Rom;
use super::{Error, Result};

const ROM_SEARCH: u8 = 0xF0;
const ROM_SEARCH_ALARM: u8 = 0xEC;
const ROM_READ: u8 = 0x33;
const ROM_MATCH: u8 = 0x55;
const ROM_SKIP: u8 = 0xCC;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Presence {
    Present,
    AlarmingPresent,
    Absent,
    Shorted,
}

pub trait OneWire {
    fn redetect(&mut self) -> Result<()>;
    fn reset(&mut self) -> Result<Presence>;
    fn touch_bit(&mut self, bit: bool) -> Result<bool>;
    fn write_bytes(&mut self, data: &[u8]) -> Result<()>;
    fn read_bytes(&mut self, count: usize) -> Result<Vec<u8>>;
    fn write_byte_power(&mut self, byte: u8) -> Result<()>;
    fn stop_pulse(&mut self) -> Result<()>;
    fn supports_strong_pullup(&self) -> bool;
    fn search_pass(&mut self, seed: &[bool]) -> Result<([bool; 64], [bool; 64])>;

    fn read_bit(&mut self) -> Result<bool> {
        self.touch_bit(true)
    }

    fn write_bit(&mut self, bit: bool) -> Result<()> {
        if self.touch_bit(bit)? != bit {
            return Err(Error::EchoMismatch);
        }
        Ok(())
    }

    fn write_byte(&mut self, byte: u8) -> Result<()> {
        self.write_bytes(&[byte])
    }

    fn read_byte(&mut self) -> Result<u8> {
        Ok(self.read_bytes(1)?[0])
    }

    fn reset_expecting_device(&mut self) -> Result<()> {
        match self.reset()? {
            Presence::Present | Presence::AlarmingPresent => Ok(()),
            Presence::Absent => Err(Error::NoDevice),
            Presence::Shorted => Err(Error::Shorted),
        }
    }

    fn read_rom(&mut self) -> Result<Rom> {
        self.reset_expecting_device()?;
        self.write_byte(ROM_READ)?;
        let data = self.read_bytes(8)?;
        let mut code = [0u8; 8];
        code.copy_from_slice(&data);
        let rom = Rom(code);
        if !rom.is_valid() {
            return Err(Error::Crc);
        }
        debug!("read rom [{rom}]");
        Ok(rom)
    }

    fn match_rom(&mut self, rom: &Rom) -> Result<()> {
        self.reset_expecting_device()?;
        let mut data = [0u8; 9];
        data[0] = ROM_MATCH;
        data[1..].copy_from_slice(&rom.0);
        self.write_bytes(&data)
    }

    fn skip_rom(&mut self) -> Result<()> {
        self.reset_expecting_device()?;
        self.write_byte(ROM_SKIP)
    }

    fn get_connected_roms(&mut self) -> Result<Vec<Rom>> {
        search(self, ROM_SEARCH)
    }

    fn alarm_search(&mut self) -> Result<Vec<Rom>> {
        search(self, ROM_SEARCH_ALARM)
    }

    fn is_connected(&mut self, rom: &Rom) -> Result<bool> {
        match self.reset()? {
            Presence::Present | Presence::AlarmingPresent => {}
            Presence::Absent => return Ok(false),
            Presence::Shorted => return Err(Error::Shorted),
        }
        self.write_byte(ROM_SEARCH)?;
        let seed = rom.bits();
        let (bits, _) = self.search_pass(&seed)?;
        Ok(Rom::from_bits(&bits) == *rom)
    }
}

fn search<B: OneWire + ?Sized>(bus: &mut B, command: u8) -> Result<Vec<Rom>> {
    let mut roms = Vec::new();
    let mut seeds: Vec<Vec<bool>> = vec![Vec::new()];
    while let Some(seed) = seeds.pop() {
        match bus.reset()? {
            Presence::Present | Presence::AlarmingPresent => {}
            Presence::Absent => return Ok(roms),
            Presence::Shorted => return Err(Error::Shorted),
        }
        bus.write_byte(command)?;
        let (bits, discrepancies) = bus.search_pass(&seed)?;
        if bits.iter().all(|&bit| bit) {
            continue;
        }
        for i in seed.len()..64 {
            if discrepancies[i] && !bits[i] {
                let mut branch = bits[..i].to_vec();
                branch.push(true);
                seeds.push(branch);
            }
        }
        let rom = Rom::from_bits(&bits);
        if !rom.is_valid() || rom.0 == [0u8; 8] {
            return Err(Error::Crc);
        }
        debug!("search found [{rom}]");
        roms.push(rom);
    }
    info!("search found {} device(s)", roms.len());
    Ok(roms)
}
