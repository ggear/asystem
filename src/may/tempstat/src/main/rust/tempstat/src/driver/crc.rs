//! 1-Wire CRC-8 (polynomial 0x31, reflected).
//!
//! - [Understanding and Using Cyclic Redundancy Checks with Maxim 1-Wire and iButton Products](https://www.analog.com/en/resources/technical-articles/understanding-and-using-cyclic-redundancy-checks-with-maxim-1wire-and-ibutton-products.html)

pub fn crc8(data: &[u8]) -> u8 {
    let mut crc: u8 = 0;
    for &byte in data {
        let mut byte = byte;
        for _ in 0..8 {
            let mix = (crc ^ byte) & 0x01;
            crc >>= 1;
            if mix != 0 {
                crc ^= 0x8C;
            }
            byte >>= 1;
        }
    }
    crc
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crc8_of_empty_is_zero() {
        assert_eq!(crc8(&[]), 0x00);
    }

    #[test]
    fn crc8_of_zero_byte_is_zero() {
        assert_eq!(crc8(&[0x00]), 0x00);
    }

    #[test]
    fn crc8_matches_known_vectors() {
        assert_eq!(crc8(&[0x01]), 0x5E);
        assert_eq!(crc8(&[0xFF]), 0x35);
    }

    #[test]
    fn crc8_over_data_with_appended_crc_is_zero() {
        assert_eq!(crc8(&[0x01, 0x5E]), 0x00);
        let rom = [0x28, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC];
        let mut framed = rom.to_vec();
        framed.push(crc8(&rom));
        assert_eq!(crc8(&framed), 0x00);
    }
}
