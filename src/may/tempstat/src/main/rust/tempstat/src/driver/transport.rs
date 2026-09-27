//! USB transport for the PL2303 bridge — the seam between the protocol and raw usbfs.
//!
//! - [USB 2.0 specification, section 9.3 USB Device Requests](https://www.usb.org/document-library/usb-20-specification)

use std::time::Duration;

use log::{debug, info};
use nusb::transfer::{Buffer, Bulk, ControlIn, ControlOut, ControlType, In, Out, Recipient, TransferError};
use nusb::{Endpoint, Interface, MaybeFuture};

use super::{Error, Result};
use crate::log_line;

const INTERFACE: u8 = 0;
const ENDPOINT_IN: u8 = 0x83;
const ENDPOINT_OUT: u8 = 0x02;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum UsbRequest {
    Vendor,
    Class,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct UsbSetup {
    pub kind: UsbRequest,
    pub request: u8,
    pub value: u16,
    pub index: u16,
}

pub trait UsbTransport {
    fn control_in(&mut self, setup: UsbSetup, length: u16) -> Result<Vec<u8>>;
    fn control_out(&mut self, setup: UsbSetup, data: &[u8]) -> Result<()>;
    fn bulk_out(&mut self, data: &[u8]) -> Result<()>;
    fn bulk_in(&mut self, length: usize, timeout: Duration) -> Result<Vec<u8>>;
    fn packet_size(&self) -> usize;
    fn max_packet_size_0(&self) -> u8;
}

pub struct NusbTransport {
    interface: Interface,
    reader: Endpoint<Bulk, In>,
    writer: Endpoint<Bulk, Out>,
    packet_size: usize,
    max_packet_size_0: u8,
    timeout: Duration,
}

impl NusbTransport {
    pub fn open(vendor: u16, product: u16, timeout: Duration) -> Result<Self> {
        debug!("opening USB device [{vendor:04X}:{product:04X}]");
        let matched: Vec<_> = nusb::list_devices()
            .wait()?
            .filter(|device| device.vendor_id() == vendor && device.product_id() == product)
            .collect();
        if matched.len() > 1 {
            return Err(Error::UsbAmbiguous {
                vendor,
                product,
                count: matched.len(),
            });
        }
        let info = matched
            .into_iter()
            .next()
            .ok_or(Error::UsbNotFound { vendor, product })?;
        let ports = info
            .port_chain()
            .iter()
            .map(u8::to_string)
            .collect::<Vec<_>>()
            .join(".");
        info!(
            "{}",
            log_line(
                "connected to USB bridge",
                &format!(
                    "{vendor:04X}:{product:04X} at {}-{ports} address {}",
                    info.bus_id(),
                    info.device_address()
                )
            )
        );
        debug!(
            "USB bridge manufacturer [{}] product [{}] serial [{}]",
            info.manufacturer_string().unwrap_or("none"),
            info.product_string().unwrap_or("none"),
            info.serial_number().unwrap_or("none")
        );
        let device = info.open().wait()?;
        let max_packet_size_0 = device.device_descriptor().max_packet_size_0();
        let interface = device.detach_and_claim_interface(INTERFACE).wait()?;
        let reader = interface.endpoint::<Bulk, In>(ENDPOINT_IN)?;
        let writer = interface.endpoint::<Bulk, Out>(ENDPOINT_OUT)?;
        let packet_size = reader.max_packet_size();
        Ok(NusbTransport {
            interface,
            reader,
            writer,
            packet_size,
            max_packet_size_0,
            timeout,
        })
    }
}

fn control_type(kind: UsbRequest) -> (ControlType, Recipient) {
    match kind {
        UsbRequest::Vendor => (ControlType::Vendor, Recipient::Device),
        UsbRequest::Class => (ControlType::Class, Recipient::Interface),
    }
}

impl UsbTransport for NusbTransport {
    fn control_in(&mut self, setup: UsbSetup, length: u16) -> Result<Vec<u8>> {
        let (control_type, recipient) = control_type(setup.kind);
        Ok(self
            .interface
            .control_in(
                ControlIn {
                    control_type,
                    recipient,
                    request: setup.request,
                    value: setup.value,
                    index: setup.index,
                    length,
                },
                self.timeout,
            )
            .wait()?)
    }

    fn control_out(&mut self, setup: UsbSetup, data: &[u8]) -> Result<()> {
        let (control_type, recipient) = control_type(setup.kind);
        self.interface
            .control_out(
                ControlOut {
                    control_type,
                    recipient,
                    request: setup.request,
                    value: setup.value,
                    index: setup.index,
                    data,
                },
                self.timeout,
            )
            .wait()?;
        Ok(())
    }

    fn bulk_out(&mut self, data: &[u8]) -> Result<()> {
        self.writer
            .transfer_blocking(Buffer::from(data.to_vec()), self.timeout)
            .into_result()?;
        Ok(())
    }

    fn bulk_in(&mut self, length: usize, timeout: Duration) -> Result<Vec<u8>> {
        match self
            .reader
            .transfer_blocking(Buffer::new(length), timeout)
            .into_result()
        {
            Ok(data) => Ok(data.to_vec()),
            Err(TransferError::Cancelled) => Ok(Vec::new()),
            Err(err) => Err(err.into()),
        }
    }

    fn packet_size(&self) -> usize {
        self.packet_size
    }

    fn max_packet_size_0(&self) -> u8 {
        self.max_packet_size_0
    }
}

#[cfg(test)]
pub mod mock {
    use std::collections::VecDeque;

    use super::*;

    pub struct MockTransport {
        pub reads: Vec<(UsbSetup, u16)>,
        pub writes: Vec<(UsbSetup, Vec<u8>)>,
        pub written: Vec<u8>,
        pub incoming: VecDeque<Result<Vec<u8>>>,
        pub requested: Vec<usize>,
        pub packet_size: usize,
        pub max_packet_size_0: u8,
    }

    impl MockTransport {
        pub fn new() -> Self {
            MockTransport {
                reads: Vec::new(),
                writes: Vec::new(),
                written: Vec::new(),
                incoming: VecDeque::new(),
                requested: Vec::new(),
                packet_size: 64,
                max_packet_size_0: 64,
            }
        }

        pub fn queue(&mut self, data: Vec<u8>) {
            self.incoming.push_back(Ok(data));
        }

        pub fn queue_error(&mut self) {
            self.incoming.push_back(Err(Error::UsbTransfer(TransferError::Stall)));
        }

        pub fn control_values(&self, request: u8) -> Vec<u16> {
            self.writes
                .iter()
                .filter(|(setup, _)| setup.request == request)
                .map(|(setup, _)| setup.value)
                .collect()
        }
    }

    impl Default for MockTransport {
        fn default() -> Self {
            MockTransport::new()
        }
    }

    impl UsbTransport for MockTransport {
        fn control_in(&mut self, setup: UsbSetup, length: u16) -> Result<Vec<u8>> {
            self.reads.push((setup, length));
            Ok(vec![0])
        }

        fn control_out(&mut self, setup: UsbSetup, data: &[u8]) -> Result<()> {
            self.writes.push((setup, data.to_vec()));
            Ok(())
        }

        fn bulk_out(&mut self, data: &[u8]) -> Result<()> {
            self.written.extend_from_slice(data);
            Ok(())
        }

        fn bulk_in(&mut self, length: usize, _timeout: Duration) -> Result<Vec<u8>> {
            self.requested.push(length);
            match self.incoming.pop_front() {
                Some(result) => result,
                None => Ok(Vec::new()),
            }
        }

        fn packet_size(&self) -> usize {
            self.packet_size
        }

        fn max_packet_size_0(&self) -> u8 {
            self.max_packet_size_0
        }
    }
}
