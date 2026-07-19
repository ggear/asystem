//! 1-Wire 64-bit ROM code — family byte, 48-bit serial, CRC-8.
//!
//! - [1-Wire Search Algorithm (AN187)](https://www.analog.com/en/resources/app-notes/1wire-search-algorithm.html)

use std::fmt;
use std::str::FromStr;

use super::crc::crc8;
use super::Error;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct Rom(pub [u8; 8]);

impl Rom {
    pub fn family(&self) -> u8 {
        self.0[0]
    }

    pub fn is_valid(&self) -> bool {
        crc8(&self.0[..7]) == self.0[7]
    }

    pub fn bits(&self) -> [bool; 64] {
        let mut bits = [false; 64];
        for (i, bit) in bits.iter_mut().enumerate() {
            *bit = (self.0[i / 8] >> (i % 8)) & 0x01 != 0;
        }
        bits
    }

    pub fn from_bits(bits: &[bool; 64]) -> Self {
        let mut rom = [0u8; 8];
        for (i, &bit) in bits.iter().enumerate() {
            if bit {
                rom[i / 8] |= 1 << (i % 8);
            }
        }
        Rom(rom)
    }
}

impl fmt::Display for Rom {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        for byte in self.0 {
            write!(f, "{byte:02X}")?;
        }
        Ok(())
    }
}

impl FromStr for Rom {
    type Err = Error;

    fn from_str(s: &str) -> Result<Self, Error> {
        if s.len() != 16 || !s.bytes().all(|byte| byte.is_ascii_hexdigit()) {
            return Err(Error::InvalidRom(s.to_string()));
        }
        let mut rom = [0u8; 8];
        for (i, byte) in rom.iter_mut().enumerate() {
            *byte = u8::from_str_radix(&s[2 * i..2 * i + 2], 16).map_err(|_| Error::InvalidRom(s.to_string()))?;
        }
        Ok(Rom(rom))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn valid_rom() -> Rom {
        let mut rom = [0x28, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0x00];
        rom[7] = crc8(&rom[..7]);
        Rom(rom)
    }

    #[test]
    fn family_is_first_byte() {
        assert_eq!(valid_rom().family(), 0x28);
    }

    #[test]
    fn crc_validity() {
        let rom = valid_rom();
        assert!(rom.is_valid());
        let mut corrupted = rom.0;
        corrupted[7] = corrupted[7].wrapping_add(1);
        assert!(!Rom(corrupted).is_valid());
    }

    #[test]
    fn display_is_uppercase_hex() {
        assert_eq!(
            Rom([0x28, 0xFF, 0x4B, 0x71, 0x61, 0x15, 0x03, 0x0A]).to_string(),
            "28FF4B716115030A"
        );
    }

    #[test]
    fn from_str_round_trips() {
        let rom = valid_rom();
        assert_eq!(rom.to_string().parse::<Rom>().unwrap(), rom);
        assert_eq!(
            "28ff4b716115030a".parse::<Rom>().unwrap().to_string(),
            "28FF4B716115030A"
        );
    }

    #[test]
    fn from_str_rejects_bad_input() {
        assert!(matches!("28FF4B".parse::<Rom>(), Err(Error::InvalidRom(_))));
        assert!(matches!("28FF4B716115030G".parse::<Rom>(), Err(Error::InvalidRom(_))));
        assert!(matches!("28FF4B71611503αα".parse::<Rom>(), Err(Error::InvalidRom(_))));
        assert!(matches!("+8FF4B716115030A".parse::<Rom>(), Err(Error::InvalidRom(_))));
    }

    #[test]
    fn bits_round_trip_lsb_first() {
        let rom = valid_rom();
        let bits = rom.bits();
        assert!(!bits[0]);
        assert!(!bits[1]);
        assert!(!bits[2]);
        assert!(bits[3]);
        assert!(!bits[4]);
        assert!(bits[5]);
        assert_eq!(Rom::from_bits(&bits), rom);
    }
}
