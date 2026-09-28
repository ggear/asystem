//! PL2303 USB-to-serial bridge protocol, spoken over a [`UsbTransport`] so no kernel driver is in the path.
//!
//! - [Linux pl2303 driver](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/usb/serial/pl2303.c)
//! - [USB CDC PSTN subclass, SetLineCoding](https://www.usb.org/document-library/class-definitions-communication-devices-12)

use std::collections::VecDeque;
use std::thread;
use std::time::{Duration, Instant};

use log::{debug, info, warn};

use super::uart::{Uart, BAUD_OPEN};
use super::usb::{NusbTransport, UsbEndpoints, UsbRequest, UsbSetup, UsbTransport};
use super::{Error, Result};
use crate::log_line;

const ENDPOINTS: UsbEndpoints = UsbEndpoints {
    interface: 0,
    input: 0x83,
    output: 0x02,
};
const BREAK_HOLD: Duration = Duration::from_millis(2);
const DRAIN_TIMEOUT: Duration = Duration::from_millis(10);
const DRAIN_PACKETS_MAX: usize = 16;

const REQUEST_VENDOR: u8 = 0x01;
const REQUEST_SET_LINE: u8 = 0x20;
const REQUEST_SET_CONTROL: u8 = 0x22;
const REQUEST_BREAK: u8 = 0x23;
const CONTROL_DTR_RTS: u16 = 0x0003;
const BREAK_ON: u16 = 0xFFFF;
const BREAK_OFF: u16 = 0x0000;
const RESET_DOWNSTREAM: u16 = 8;
const RESET_UPSTREAM: u16 = 9;
const FLOW_CONTROL_REGISTER: u16 = 0x0002;
const MAX_PACKET_SIZE_0_HX: u8 = 64;
const STARTUP_FLOW_HX: u16 = 0x0044;
const STARTUP_FLOW_LEGACY: u16 = 0x0024;
const VENDOR_READ_LEN: u16 = 1;

const LINE_CODING_LEN: usize = 7;
const LINE_STOP_BITS_ONE: u8 = 0;
const LINE_PARITY_NONE: u8 = 0;
const LINE_DATA_BITS_EIGHT: u8 = 8;

enum Startup {
    Read(u16),
    Write(u16, u16),
}

const STARTUP: [Startup; 10] = [
    Startup::Read(0x8484),
    Startup::Write(0x0404, 0x0000),
    Startup::Read(0x8484),
    Startup::Read(0x8383),
    Startup::Read(0x8484),
    Startup::Write(0x0404, 0x0001),
    Startup::Read(0x8484),
    Startup::Read(0x8383),
    Startup::Write(0x0000, 0x0001),
    Startup::Write(0x0001, 0x0000),
];

pub struct Pl2303Uart<T: UsbTransport> {
    transport: T,
    flow_control: u16,
    timeout: Duration,
    pending: VecDeque<u8>,
}

impl Pl2303Uart<NusbTransport> {
    pub fn open(vendor: u16, product: u16, timeout: Duration) -> Result<Self> {
        Pl2303Uart::new(NusbTransport::open(vendor, product, ENDPOINTS, timeout)?, timeout)
    }
}

impl<T: UsbTransport> Pl2303Uart<T> {
    pub fn new(transport: T, timeout: Duration) -> Result<Self> {
        let (flow_control, variant) = if transport.max_packet_size_0() == MAX_PACKET_SIZE_0_HX {
            (STARTUP_FLOW_HX, "HX")
        } else {
            (STARTUP_FLOW_LEGACY, "legacy")
        };
        info!(
            "{}",
            log_line(
                "detected USB bridge chipset",
                &format!(
                    "PL2303 {variant} packet {} flow {flow_control:#06X}",
                    transport.packet_size()
                )
            )
        );
        let mut uart = Pl2303Uart {
            transport,
            flow_control,
            timeout,
            pending: VecDeque::new(),
        };
        uart.start()?;
        uart.set_baud(BAUD_OPEN)?;
        uart.class_request(REQUEST_SET_CONTROL, CONTROL_DTR_RTS, &[])?;
        debug!("PL2303 asserted DTR and RTS");
        Ok(uart)
    }

    fn start(&mut self) -> Result<()> {
        for step in &STARTUP {
            match step {
                Startup::Read(value) => {
                    let data = self.transport.control_in(vendor_setup(*value, 0), VENDOR_READ_LEN)?;
                    debug!("PL2303 vendor read [{value:#06X}] returned [{data:02X?}]");
                }
                Startup::Write(value, index) => self.vendor_write(*value, *index)?,
            }
        }
        self.vendor_write(FLOW_CONTROL_REGISTER, self.flow_control)?;
        debug!("PL2303 startup complete");
        Ok(())
    }

    fn vendor_write(&mut self, value: u16, index: u16) -> Result<()> {
        debug!("PL2303 vendor write [{value:#06X}] index [{index:#06X}]");
        self.transport.control_out(vendor_setup(value, index), &[])
    }

    fn class_request(&mut self, request: u8, value: u16, data: &[u8]) -> Result<()> {
        self.transport.control_out(
            UsbSetup {
                kind: UsbRequest::Class,
                request,
                value,
                index: 0,
            },
            data,
        )
    }
}

impl<T: UsbTransport> Uart for Pl2303Uart<T> {
    fn write_all(&mut self, data: &[u8]) -> Result<()> {
        debug!("uart tx [{data:02X?}]");
        self.transport.bulk_out(data)
    }

    fn read_exact(&mut self, buffer: &mut [u8]) -> Result<()> {
        let deadline = Instant::now() + self.timeout;
        let packet_size = self.transport.packet_size();
        while self.pending.len() < buffer.len() {
            if Instant::now() >= deadline {
                return Err(Error::Timeout);
            }
            let wanted = (buffer.len() - self.pending.len()).div_ceil(packet_size) * packet_size;
            let received = self.transport.bulk_in(wanted, self.timeout)?;
            self.pending.extend(received.iter().copied());
        }
        for slot in buffer.iter_mut() {
            *slot = self.pending.pop_front().ok_or(Error::Timeout)?;
        }
        debug!("uart rx [{buffer:02X?}]");
        Ok(())
    }

    fn send_break(&mut self) -> Result<()> {
        debug!("uart break");
        self.class_request(REQUEST_BREAK, BREAK_ON, &[])?;
        thread::sleep(BREAK_HOLD);
        self.class_request(REQUEST_BREAK, BREAK_OFF, &[])
    }

    fn clear(&mut self) -> Result<()> {
        self.pending.clear();
        self.vendor_write(RESET_DOWNSTREAM, 0)?;
        self.vendor_write(RESET_UPSTREAM, 0)?;
        let packet_size = self.transport.packet_size();
        let mut discarded = 0usize;
        let mut capped = true;
        for _ in 0..DRAIN_PACKETS_MAX {
            let drained = self.transport.bulk_in(packet_size, DRAIN_TIMEOUT)?;
            if drained.is_empty() {
                capped = false;
                break;
            }
            discarded += drained.len();
        }
        if capped {
            warn!("uart clear drained [{discarded}] byte(s) and hit the packet cap, stream may be desynchronised");
        }
        debug!("uart clear discarded [{discarded}]");
        Ok(())
    }

    fn set_baud(&mut self, baud: u32) -> Result<()> {
        let mut coding = [0u8; LINE_CODING_LEN];
        coding[..4].copy_from_slice(&baud.to_le_bytes());
        coding[4] = LINE_STOP_BITS_ONE;
        coding[5] = LINE_PARITY_NONE;
        coding[6] = LINE_DATA_BITS_EIGHT;
        debug!("uart baud [{baud}] coding [{coding:02X?}]");
        self.class_request(REQUEST_SET_LINE, 0, &coding)
    }
}

fn vendor_setup(value: u16, index: u16) -> UsbSetup {
    UsbSetup {
        kind: UsbRequest::Vendor,
        request: REQUEST_VENDOR,
        value,
        index,
    }
}

#[cfg(test)]
mod tests {
    use super::super::usb::mock::MockTransport;
    use super::*;

    const TIMEOUT: Duration = Duration::from_millis(50);

    fn opened(transport: MockTransport) -> Pl2303Uart<MockTransport> {
        Pl2303Uart::new(transport, TIMEOUT).unwrap()
    }

    #[test]
    fn startup_issues_the_kernel_vendor_sequence_in_order() {
        let uart = opened(MockTransport::new());
        let reads: Vec<u16> = uart.transport.reads.iter().map(|(setup, _)| setup.value).collect();
        assert_eq!(reads, vec![0x8484, 0x8484, 0x8383, 0x8484, 0x8484, 0x8383]);
        let writes: Vec<(u16, u16)> = uart
            .transport
            .writes
            .iter()
            .filter(|(setup, _)| setup.kind == UsbRequest::Vendor)
            .map(|(setup, _)| (setup.value, setup.index))
            .collect();
        assert_eq!(
            writes,
            vec![
                (0x0404, 0x0000),
                (0x0404, 0x0001),
                (0x0000, 0x0001),
                (0x0001, 0x0000),
                (0x0002, 0x0044)
            ]
        );
        assert!(uart
            .transport
            .reads
            .iter()
            .all(|(setup, length)| setup.kind == UsbRequest::Vendor
                && setup.request == REQUEST_VENDOR
                && *length == VENDOR_READ_LEN));
    }

    #[test]
    fn startup_picks_the_flow_control_byte_from_the_control_endpoint_size() {
        let uart = opened(MockTransport::new());
        assert_eq!(uart.flow_control, STARTUP_FLOW_HX);
        let mut legacy = MockTransport::new();
        legacy.max_packet_size_0 = 8;
        assert_eq!(opened(legacy).flow_control, STARTUP_FLOW_LEGACY);
    }

    #[test]
    fn open_sets_the_line_coding_then_asserts_dtr_and_rts() {
        let uart = opened(MockTransport::new());
        let class: Vec<(u8, u16, Vec<u8>)> = uart
            .transport
            .writes
            .iter()
            .filter(|(setup, _)| setup.kind == UsbRequest::Class)
            .map(|(setup, data)| (setup.request, setup.value, data.clone()))
            .collect();
        assert_eq!(
            class,
            vec![
                (REQUEST_SET_LINE, 0, vec![0x80, 0x25, 0x00, 0x00, 0, 0, 8]),
                (REQUEST_SET_CONTROL, CONTROL_DTR_RTS, vec![])
            ]
        );
    }

    #[test]
    fn set_baud_encodes_the_rate_little_endian() {
        let mut uart = opened(MockTransport::new());
        uart.set_baud(115_200).unwrap();
        let (_, coding) = uart.transport.writes.last().unwrap();
        assert_eq!(coding, &vec![0x00, 0xC2, 0x01, 0x00, 0, 0, 8]);
    }

    #[test]
    fn read_exact_rounds_the_request_up_to_a_packet_multiple() {
        let mut transport = MockTransport::new();
        transport.queue(vec![0xAA; 128]);
        let mut uart = opened(transport);
        let mut buffer = [0u8; 72];
        uart.read_exact(&mut buffer).unwrap();
        assert_eq!(uart.transport.requested, vec![128]);
        assert!(buffer.iter().all(|byte| *byte == 0xAA));
    }

    #[test]
    fn read_exact_buffers_the_surplus_for_the_next_read() {
        let mut transport = MockTransport::new();
        transport.queue((0..64).collect());
        let mut uart = opened(transport);
        let mut first = [0u8; 1];
        uart.read_exact(&mut first).unwrap();
        let mut second = [0u8; 3];
        uart.read_exact(&mut second).unwrap();
        assert_eq!(first, [0]);
        assert_eq!(second, [1, 2, 3]);
        assert_eq!(uart.transport.requested.len(), 1, "surplus should not re-read");
    }

    #[test]
    fn read_exact_times_out_when_nothing_arrives() {
        let mut uart = opened(MockTransport::new());
        let mut buffer = [0u8; 1];
        assert!(matches!(uart.read_exact(&mut buffer), Err(Error::Timeout)));
    }

    #[test]
    fn clear_resets_both_pipes_then_drains_until_empty() {
        let mut transport = MockTransport::new();
        transport.queue(vec![0x01; 64]);
        transport.queue(vec![0x02; 12]);
        let mut uart = opened(transport);
        uart.clear().unwrap();
        let pipes: Vec<u16> = uart
            .transport
            .writes
            .iter()
            .filter(|(setup, _)| setup.kind == UsbRequest::Vendor)
            .map(|(setup, _)| setup.value)
            .skip_while(|value| *value != RESET_DOWNSTREAM)
            .collect();
        assert_eq!(pipes, vec![RESET_DOWNSTREAM, RESET_UPSTREAM]);
        assert_eq!(uart.transport.requested, vec![64, 64, 64]);
    }

    #[test]
    fn clear_discards_buffered_bytes_from_an_earlier_read() {
        let mut transport = MockTransport::new();
        transport.queue(vec![0xFF; 64]);
        let mut uart = opened(transport);
        let mut buffer = [0u8; 1];
        uart.read_exact(&mut buffer).unwrap();
        assert_eq!(uart.pending.len(), 63);
        uart.clear().unwrap();
        assert!(uart.pending.is_empty());
    }

    #[test]
    fn clear_propagates_a_transport_error_rather_than_reporting_success() {
        let mut transport = MockTransport::new();
        transport.queue_error();
        let mut uart = opened(transport);
        assert!(matches!(uart.clear(), Err(Error::UsbTransfer(_))));
    }

    #[test]
    fn clear_stops_at_the_packet_cap_when_the_device_never_drains() {
        let mut transport = MockTransport::new();
        for _ in 0..DRAIN_PACKETS_MAX + 4 {
            transport.queue(vec![0x5A; 64]);
        }
        let mut uart = opened(transport);
        uart.clear().unwrap();
        assert_eq!(uart.transport.requested.len(), DRAIN_PACKETS_MAX);
    }

    #[test]
    fn send_break_toggles_the_break_request() {
        let mut uart = opened(MockTransport::new());
        uart.send_break().unwrap();
        assert_eq!(uart.transport.control_values(REQUEST_BREAK), vec![BREAK_ON, BREAK_OFF]);
    }

    #[test]
    fn write_all_reaches_the_bulk_endpoint() {
        let mut uart = opened(MockTransport::new());
        uart.write_all(&[0xF0, 0x0F]).unwrap();
        assert_eq!(uart.transport.written, vec![0xF0, 0x0F]);
    }
}
