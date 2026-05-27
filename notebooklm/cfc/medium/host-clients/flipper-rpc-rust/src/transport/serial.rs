//! Implementation for serial communication protocols

use std::time::Duration;

use crate::logging::debug;

pub mod cli;
pub mod helpers;
pub mod rpc;

/// Baud rate for the flipper
pub(crate) const FLIPPER_BAUD: u32 = 115_200;

/// Global timeout for serial operations. Kinda large as large files may take a LONG time to
/// process
pub(crate) const TIMEOUT: Duration = Duration::from_secs(10);

/// A flipper device. Contains port and device name;
#[derive(Debug)]
pub struct FlipperDevice {
    /// Port name. /dev/ttyACMX on linux or COMX on windows.
    pub port_name: String,
    /// Device name: Flipper XXX
    pub device_name: String,
}

/// Lists all flippers connected to the current system
///
/// Scans ports and filters by manufacturer name == "Flipper Devices Inc."
#[cfg_attr(feature = "tracing", tracing::instrument)]
pub fn list_flipper_ports() -> Result<Vec<FlipperDevice>, serialport::Error> {
    debug!("scanning ports");

    let ports = serialport::available_ports()?;

    let ports = ports
        .into_iter()
        .filter_map(|port| {
            debug!("{}", port.port_name);
            if let serialport::SerialPortType::UsbPort(usb_info) = port.port_type {
                if usb_info.manufacturer.as_deref() == Some("Flipper Devices Inc.") {
                    if let Some(product) = usb_info.product {
                        debug!("└── is flipper");
                        return Some(FlipperDevice {
                            port_name: port.port_name,
                            device_name: product,
                        });
                    }
                }
            }
            debug!("└── is not flipper");
            None
        })
        .collect();

    Ok(ports)
}
