//! DS18B20 1-Wire temperature sensor.
//!
//! - [DS18B20 Datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ds18b20.pdf)
use std::thread;
use std::time::{Duration, Instant};

use log::{debug, warn};

use super::crc::crc8;
use super::onewire::OneWire;
use super::rom::Rom;
use super::{Error, Result};

const FAMILY_CODE: u8 = 0x28;
const CONVERT_T: u8 = 0x44;
const WRITE_SCRATCHPAD: u8 = 0x4E;
const READ_SCRATCHPAD: u8 = 0xBE;
const COPY_SCRATCHPAD: u8 = 0x48;
const RECALL_EEPROM: u8 = 0xB8;
const READ_POWER_SUPPLY: u8 = 0xB4;
const SCRATCHPAD_LEN: usize = 9;
const READ_ATTEMPTS: usize = 3;
const COMPLETION_POLL_PERIOD: Duration = Duration::from_millis(10);
const COMPLETION_MARGIN: u32 = 2;
const T_CONV: Duration = Duration::from_millis(750);
const T_RW: Duration = Duration::from_millis(10);

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Resolution {
    Bits9,
    Bits10,
    Bits11,
    Bits12,
}

impl Resolution {
    fn code(self) -> u8 {
        match self {
            Resolution::Bits9 => 0,
            Resolution::Bits10 => 1,
            Resolution::Bits11 => 2,
            Resolution::Bits12 => 3,
        }
    }

    fn from_config(config: u8) -> Self {
        match (config >> 5) & 0x03 {
            0 => Resolution::Bits9,
            1 => Resolution::Bits10,
            2 => Resolution::Bits11,
            _ => Resolution::Bits12,
        }
    }

    fn to_config(self) -> u8 {
        (self.code() << 5) | 0x1F
    }
}

pub struct Ds18b20 {
    rom: Option<Rom>,
    parasitic: bool,
    resolution: Resolution,
}

impl Ds18b20 {
    pub fn attach(bus: &mut (impl OneWire + ?Sized), rom: Option<Rom>) -> Result<Self> {
        if let Some(rom) = &rom {
            if rom.family() != FAMILY_CODE {
                return Err(Error::WrongFamily(*rom));
            }
            if !rom.is_valid() {
                return Err(Error::Crc);
            }
        }
        let mut device = Ds18b20 {
            rom,
            parasitic: false,
            resolution: Resolution::Bits12,
        };
        device.parasitic = device.read_power_supply(bus)?;
        if device.parasitic && !bus.supports_strong_pullup() {
            warn!(
                "ds18b20 rom [{}] is parasite powered but the adapter has no strong pullup, conversions may be unreliable",
                device.rom.map(|rom| rom.to_string()).unwrap_or_else(|| "none".into())
            );
        }
        let scratchpad = device.read_scratchpad(bus)?;
        device.resolution = Resolution::from_config(scratchpad[4]);
        debug!(
            "ds18b20 rom [{}] parasitic [{}] resolution [{:?}]",
            device.rom.map(|rom| rom.to_string()).unwrap_or_else(|| "none".into()),
            device.parasitic,
            device.resolution
        );
        Ok(device)
    }

    pub fn rom(&self) -> Option<&Rom> {
        self.rom.as_ref()
    }

    pub fn parasitic(&self) -> bool {
        self.parasitic
    }

    pub fn resolution(&self) -> Resolution {
        self.resolution
    }

    pub fn t_conv(&self) -> Duration {
        T_CONV / (8u32 >> u32::from(self.resolution.code()))
    }

    fn select(&self, bus: &mut (impl OneWire + ?Sized)) -> Result<()> {
        match &self.rom {
            Some(rom) => bus.match_rom(rom),
            None => bus.skip_rom(),
        }
    }

    fn await_completion(&self, bus: &mut (impl OneWire + ?Sized), duration: Duration) -> Result<()> {
        if self.parasitic {
            thread::sleep(duration);
            return Ok(());
        }
        let deadline = Instant::now() + duration * COMPLETION_MARGIN;
        loop {
            if bus.read_bit()? {
                return Ok(());
            }
            if Instant::now() >= deadline {
                return Err(Error::Timeout);
            }
            thread::sleep(COMPLETION_POLL_PERIOD);
        }
    }

    fn command_with_power(&self, bus: &mut (impl OneWire + ?Sized), byte: u8, duration: Duration) -> Result<()> {
        if self.parasitic {
            bus.write_byte_power(byte)?;
            thread::sleep(duration);
            bus.stop_pulse()
        } else {
            bus.write_byte(byte)?;
            self.await_completion(bus, duration)
        }
    }

    fn read_power_supply(&self, bus: &mut (impl OneWire + ?Sized)) -> Result<bool> {
        self.select(bus)?;
        bus.write_byte(READ_POWER_SUPPLY)?;
        Ok(!bus.read_bit()?)
    }

    pub fn read_scratchpad(&self, bus: &mut (impl OneWire + ?Sized)) -> Result<[u8; SCRATCHPAD_LEN]> {
        self.select(bus)?;
        bus.write_byte(READ_SCRATCHPAD)?;
        let data = bus.read_bytes(SCRATCHPAD_LEN)?;
        let mut scratchpad = [0u8; SCRATCHPAD_LEN];
        scratchpad.copy_from_slice(&data);
        if crc8(&scratchpad[..SCRATCHPAD_LEN - 1]) != scratchpad[SCRATCHPAD_LEN - 1] {
            return Err(Error::Crc);
        }
        Ok(scratchpad)
    }

    fn write_scratchpad(&self, bus: &mut (impl OneWire + ?Sized), high: i8, low: i8, config: u8) -> Result<()> {
        self.select(bus)?;
        bus.write_bytes(&[WRITE_SCRATCHPAD, high as u8, low as u8, config])
    }

    fn copy_scratchpad(&self, bus: &mut (impl OneWire + ?Sized)) -> Result<()> {
        self.select(bus)?;
        self.command_with_power(bus, COPY_SCRATCHPAD, T_RW)
    }

    pub fn recall(&self, bus: &mut (impl OneWire + ?Sized)) -> Result<()> {
        self.select(bus)?;
        bus.write_byte(RECALL_EEPROM)?;
        self.await_completion(bus, T_RW)
    }

    pub fn convert_t(&self, bus: &mut (impl OneWire + ?Sized)) -> Result<()> {
        self.select(bus)?;
        self.command_with_power(bus, CONVERT_T, self.t_conv())
    }

    pub fn get_temperature(&self, bus: &mut (impl OneWire + ?Sized)) -> Result<f32> {
        self.convert_t(bus)?;
        self.read_temperature(bus)
    }

    pub fn read_temperature(&self, bus: &mut (impl OneWire + ?Sized)) -> Result<f32> {
        let mut attempt = 0;
        loop {
            attempt += 1;
            match self.read_scratchpad(bus) {
                Ok(scratchpad) => {
                    let temperature = decode_temperature(&scratchpad);
                    debug!("read temperature [{temperature}]");
                    return Ok(temperature);
                }
                Err(Error::Crc) if attempt < READ_ATTEMPTS => {
                    warn!("scratchpad crc failed, attempt [{attempt}] of [{READ_ATTEMPTS}]");
                }
                Err(err) => return Err(err),
            }
        }
    }

    pub fn get_alarms(&self, bus: &mut (impl OneWire + ?Sized)) -> Result<(i8, i8)> {
        let scratchpad = self.read_scratchpad(bus)?;
        Ok((scratchpad[2] as i8, scratchpad[3] as i8))
    }

    pub fn set_alarms(&self, bus: &mut (impl OneWire + ?Sized), high: Option<i8>, low: Option<i8>) -> Result<()> {
        let scratchpad = self.read_scratchpad(bus)?;
        self.write_scratchpad(
            bus,
            high.unwrap_or(scratchpad[2] as i8),
            low.unwrap_or(scratchpad[3] as i8),
            scratchpad[4],
        )?;
        self.copy_scratchpad(bus)
    }

    pub fn set_resolution(&mut self, bus: &mut (impl OneWire + ?Sized), resolution: Resolution) -> Result<()> {
        let scratchpad = self.read_scratchpad(bus)?;
        self.write_scratchpad(bus, scratchpad[2] as i8, scratchpad[3] as i8, resolution.to_config())?;
        self.copy_scratchpad(bus)?;
        self.resolution = resolution;
        Ok(())
    }
}

fn decode_temperature(scratchpad: &[u8; SCRATCHPAD_LEN]) -> f32 {
    f32::from(i16::from_le_bytes([scratchpad[0], scratchpad[1]])) / 16.0
}

#[cfg(test)]
mod tests {
    use super::super::ds2480b::Ds2480b;
    use super::super::uart::mock::MockUart;
    use super::*;

    const DETECT_WRITES: usize = 6;

    fn make_bus() -> Ds2480b<MockUart> {
        let mut uart = MockUart::new();
        uart.queue_read(&[0x16, 0x44, 0x5A, 0x00, 0x93]);
        Ds2480b::new(uart).unwrap()
    }

    fn written(bus: &Ds2480b<MockUart>) -> &[u8] {
        &bus.uart.written[DETECT_WRITES..]
    }

    fn scratchpad(temperature: [u8; 2], high: u8, low: u8, config: u8) -> [u8; 9] {
        let mut scratchpad = [
            temperature[0],
            temperature[1],
            high,
            low,
            config,
            0xFF,
            0x0C,
            0x10,
            0x00,
        ];
        scratchpad[8] = crc8(&scratchpad[..8]);
        scratchpad
    }

    fn valid_rom(family: u8) -> Rom {
        let mut code = [family, 0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC, 0x00];
        code[7] = crc8(&code[..7]);
        Rom(code)
    }

    fn queue_skip_select(uart: &mut MockUart) {
        uart.queue_read(&[0xCD, 0xCC]);
    }

    fn queue_power(uart: &mut MockUart, parasitic: bool) {
        queue_skip_select(uart);
        uart.queue_read(&[0xB4, if parasitic { 0x94 } else { 0x97 }]);
    }

    fn queue_scratchpad(uart: &mut MockUart, scratchpad: &[u8; 9]) {
        queue_skip_select(uart);
        uart.queue_read(&[0xBE]);
        uart.queue_read(scratchpad);
    }

    fn make_device(bus: &mut Ds2480b<MockUart>) -> Ds18b20 {
        make_device_with_config(bus, 0x7F)
    }

    fn make_device_with_config(bus: &mut Ds2480b<MockUart>, config: u8) -> Ds18b20 {
        queue_power(&mut bus.uart, false);
        queue_scratchpad(&mut bus.uart, &scratchpad([0x91, 0x01], 0x4B, 0x46, config));
        Ds18b20::attach(bus, None).unwrap()
    }

    #[test]
    fn attach_detects_power_and_resolution() {
        let mut bus = make_bus();
        let device = make_device(&mut bus);
        assert!(!device.parasitic());
        assert_eq!(device.resolution(), Resolution::Bits12);
        assert!(device.rom().is_none());
        assert!(bus.uart.reads.is_empty());
    }

    #[test]
    fn attach_detects_parasitic_power() {
        let mut bus = make_bus();
        queue_power(&mut bus.uart, true);
        queue_scratchpad(&mut bus.uart, &scratchpad([0x91, 0x01], 0x4B, 0x46, 0x7F));
        let device = Ds18b20::attach(&mut bus, None).unwrap();
        assert!(device.parasitic());
    }

    #[test]
    fn attach_rejects_wrong_family() {
        let mut bus = make_bus();
        assert!(matches!(
            Ds18b20::attach(&mut bus, Some(valid_rom(0x10))),
            Err(Error::WrongFamily(_))
        ));
    }

    #[test]
    fn attach_rejects_invalid_rom_crc() {
        let mut rom = valid_rom(0x28);
        rom.0[7] = rom.0[7].wrapping_add(1);
        let mut bus = make_bus();
        assert!(matches!(Ds18b20::attach(&mut bus, Some(rom)), Err(Error::Crc)));
    }

    #[test]
    fn multidrop_selects_with_match_rom() {
        let rom = valid_rom(0x28);
        let mut bus = make_bus();
        let mut select_echo = vec![0x55];
        select_echo.extend(rom.0);
        bus.uart.queue_read(&[0xCD]);
        bus.uart.queue_read(&select_echo);
        bus.uart.queue_read(&[0xB4, 0x97]);
        bus.uart.queue_read(&[0xCD]);
        bus.uart.queue_read(&select_echo);
        bus.uart.queue_read(&[0xBE]);
        bus.uart.queue_read(&scratchpad([0x91, 0x01], 0x4B, 0x46, 0x7F));
        let device = Ds18b20::attach(&mut bus, Some(rom)).unwrap();
        assert_eq!(device.rom(), Some(&rom));
        let expected_select: Vec<u8> = select_echo;
        assert!(written(&bus)
            .windows(expected_select.len())
            .any(|window| window == expected_select));
    }

    #[test]
    fn decode_temperature_matches_datasheet_vectors() {
        assert_eq!(decode_temperature(&scratchpad([0x91, 0x01], 0, 0, 0x7F)), 25.0625);
        assert_eq!(decode_temperature(&scratchpad([0x5E, 0xFF], 0, 0, 0x7F)), -10.125);
        assert_eq!(decode_temperature(&scratchpad([0x50, 0x05], 0, 0, 0x7F)), 85.0);
        assert_eq!(decode_temperature(&scratchpad([0x90, 0xFC], 0, 0, 0x7F)), -55.0);
    }

    #[test]
    fn get_temperature_converts_then_reads() {
        let mut bus = make_bus();
        let device = make_device(&mut bus);
        queue_skip_select(&mut bus.uart);
        bus.uart.queue_read(&[0x44, 0x94, 0x97]);
        queue_scratchpad(&mut bus.uart, &scratchpad([0x91, 0x01], 0x4B, 0x46, 0x7F));
        assert_eq!(device.get_temperature(&mut bus).unwrap(), 25.0625);
        assert!(bus.uart.reads.is_empty());
        let writes = written(&bus);
        assert!(writes.contains(&0x44));
    }

    #[test]
    fn parasitic_convert_uses_strong_pullup() {
        let mut bus = make_bus();
        queue_power(&mut bus.uart, true);
        queue_scratchpad(&mut bus.uart, &scratchpad([0x91, 0x01], 0x4B, 0x46, 0x1F));
        let device = Ds18b20::attach(&mut bus, None).unwrap();
        assert!(device.parasitic());
        queue_skip_select(&mut bus.uart);
        bus.uart
            .queue_read(&[0x3E, 0x94, 0x94, 0x97, 0x94, 0x94, 0x94, 0x97, 0x94]);
        bus.uart.queue_read(&[0xF1]);
        queue_scratchpad(&mut bus.uart, &scratchpad([0x91, 0x01], 0x4B, 0x46, 0x1F));
        assert_eq!(device.get_temperature(&mut bus).unwrap(), 25.0625);
        assert!(bus.uart.reads.is_empty());
        let writes = written(&bus);
        assert!(writes
            .windows(9)
            .any(|window| window == [0x3F, 0x85, 0x85, 0x95, 0x85, 0x85, 0x85, 0x95, 0x87]));
        assert!(writes.contains(&0xF1));
    }

    #[test]
    fn powered_wait_times_out_when_device_stuck() {
        let mut bus = make_bus();
        let device = make_device_with_config(&mut bus, 0x1F);
        queue_skip_select(&mut bus.uart);
        bus.uart.queue_read(&[0x44]);
        bus.uart.queue_read(&[0x94].repeat(1000));
        assert!(matches!(device.convert_t(&mut bus), Err(Error::Timeout)));
    }

    #[test]
    fn read_temperature_retries_on_crc_failure() {
        let mut bus = make_bus();
        let device = make_device(&mut bus);
        let mut corrupted = scratchpad([0x91, 0x01], 0x4B, 0x46, 0x7F);
        corrupted[8] = corrupted[8].wrapping_add(1);
        queue_scratchpad(&mut bus.uart, &corrupted);
        queue_scratchpad(&mut bus.uart, &corrupted);
        queue_scratchpad(&mut bus.uart, &scratchpad([0x91, 0x01], 0x4B, 0x46, 0x7F));
        assert_eq!(device.read_temperature(&mut bus).unwrap(), 25.0625);
    }

    #[test]
    fn read_temperature_fails_after_exhausted_retries() {
        let mut bus = make_bus();
        let device = make_device(&mut bus);
        let mut corrupted = scratchpad([0x91, 0x01], 0x4B, 0x46, 0x7F);
        corrupted[8] = corrupted[8].wrapping_add(1);
        for _ in 0..3 {
            queue_scratchpad(&mut bus.uart, &corrupted);
        }
        assert!(matches!(device.read_temperature(&mut bus), Err(Error::Crc)));
    }

    #[test]
    fn resolution_maps_config_register() {
        assert_eq!(Resolution::from_config(0x1F), Resolution::Bits9);
        assert_eq!(Resolution::from_config(0x3F), Resolution::Bits10);
        assert_eq!(Resolution::from_config(0x5F), Resolution::Bits11);
        assert_eq!(Resolution::from_config(0x7F), Resolution::Bits12);
        assert_eq!(Resolution::Bits9.to_config(), 0x1F);
        assert_eq!(Resolution::Bits12.to_config(), 0x7F);
    }

    #[test]
    fn t_conv_scales_with_resolution() {
        let mut bus = make_bus();
        assert_eq!(
            make_device_with_config(&mut bus, 0x1F).t_conv(),
            Duration::from_micros(93_750)
        );
        assert_eq!(
            make_device_with_config(&mut bus, 0x3F).t_conv(),
            Duration::from_micros(187_500)
        );
        assert_eq!(
            make_device_with_config(&mut bus, 0x5F).t_conv(),
            Duration::from_micros(375_000)
        );
        assert_eq!(
            make_device_with_config(&mut bus, 0x7F).t_conv(),
            Duration::from_millis(750)
        );
    }

    #[test]
    fn get_alarms_reads_signed_thresholds() {
        let mut bus = make_bus();
        let device = make_device(&mut bus);
        queue_scratchpad(&mut bus.uart, &scratchpad([0x91, 0x01], 0x4B, 0xC0, 0x7F));
        assert_eq!(device.get_alarms(&mut bus).unwrap(), (75, -64));
    }

    #[test]
    fn set_alarms_preserves_unspecified_values() {
        let mut bus = make_bus();
        let device = make_device(&mut bus);
        queue_scratchpad(&mut bus.uart, &scratchpad([0x91, 0x01], 0x4B, 0x46, 0x7F));
        queue_skip_select(&mut bus.uart);
        bus.uart.queue_read(&[0x4E, 50, 0x46, 0x7F]);
        queue_skip_select(&mut bus.uart);
        bus.uart.queue_read(&[0x48, 0x97]);
        device.set_alarms(&mut bus, Some(50), None).unwrap();
        assert!(written(&bus).windows(4).any(|window| window == [0x4E, 50, 0x46, 0x7F]));
    }

    #[test]
    fn set_resolution_writes_config_and_updates_state() {
        let mut bus = make_bus();
        let mut device = make_device(&mut bus);
        queue_scratchpad(&mut bus.uart, &scratchpad([0x91, 0x01], 0x4B, 0x46, 0x7F));
        queue_skip_select(&mut bus.uart);
        bus.uart.queue_read(&[0x4E, 0x4B, 0x46, 0x1F]);
        queue_skip_select(&mut bus.uart);
        bus.uart.queue_read(&[0x48, 0x97]);
        device.set_resolution(&mut bus, Resolution::Bits9).unwrap();
        assert_eq!(device.resolution(), Resolution::Bits9);
        assert!(written(&bus)
            .windows(4)
            .any(|window| window == [0x4E, 0x4B, 0x46, 0x1F]));
    }
}
