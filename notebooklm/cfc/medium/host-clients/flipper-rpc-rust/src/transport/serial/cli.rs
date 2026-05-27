//! # Flipper Text CLI
//!
//! A `Transport` for communicating with Flipper Zero devices over a serial port using the text-based cli.
//! Only use this for operations that cannot be done with RPC, as this is an innefecient and error-prone wrapper.
//!
//! ## Examples
//!
//! ```no_run
//! use flipper_rpc::{error::Result, transport::{Transport, serial::cli::SerialCliTransport}};
//!
//! # fn main() -> Result<()> {
//!
//! let mut cli = SerialCliTransport::new("/dev/ttyACM0".to_string())?;
//!
//! // Set the LED to green
//!
//! cli.send("led g 255".to_string())?;
//!
//! # Ok(())
//! # }
//! ```

use crate::error::Error;
use crate::transport::serial::{TIMEOUT, helpers::drain_until_str};
use crate::{error::Result, logging::debug};

use crate::logging::trace;
use serialport::SerialPort;

use crate::transport::{Transport, serial::FLIPPER_BAUD};

use super::{
    helpers::{drain_until, read_to_string_no_eof},
    rpc::SerialRpcTransport,
};

/// # Flipper Text CLI
///
/// A `Transport` for communicating with Flipper Zero devices over a serial port using the text-based cli.
///
/// ## Examples
///
/// ```no_run
/// use flipper_rpc::{transport::Transport, error::Result, transport::serial::cli::SerialCliTransport};
///
/// # fn main() -> Result<()> {
///
/// let port = "/dev/ttyACM0";
///
/// let mut cli = SerialCliTransport::new(port.to_string())?;
///
/// // Set the LED to green
///
/// cli.send("led g 255".to_string())?;
///
/// # Ok(())
/// # }
/// ```
#[derive(Debug)]
pub struct SerialCliTransport {
    port: Box<dyn SerialPort>,
}

impl SerialCliTransport {
    /// Creates a new SerialCliTransport from a port name
    ///
    /// # Errors
    ///
    /// Will error if serialport cannot connect to the port or if the flipper shell prompt does not
    /// appear
    ///
    /// The above errors occur after a 2 second timeout
    #[cfg_attr(feature = "tracing", tracing::instrument)]
    pub fn new<S: AsRef<str> + std::fmt::Debug>(port: S) -> Result<Self> {
        let mut port = serialport::new(port.as_ref(), FLIPPER_BAUD)
            .timeout(TIMEOUT)
            .open()?;

        debug!("Draining port until prompt");
        drain_until_str(&mut port, ">: ", TIMEOUT)?;

        Ok(Self { port })
    }

    /// Converts a SerialCliTransport into a SerialRpcTransport
    ///
    /// This function runs the start_rpc_session command, waits for the response, and returns
    /// a SerialRpcTransport made from the internal port
    ///
    /// # Errors
    ///
    /// Will error if the command could not be sent or if the command does not reply with a newline
    #[cfg_attr(feature = "tracing", tracing::instrument)]
    pub fn into_rpc(mut self) -> Result<SerialRpcTransport> {
        self.send("start_rpc_session".to_string())?;
        drain_until(&mut self.port, b'\n', TIMEOUT)?;

        SerialRpcTransport::from_port(self.port)
    }
}

impl Transport<String> for SerialCliTransport {
    type Err = Error;

    #[cfg_attr(feature = "tracing", tracing::instrument)]
    fn send(&mut self, cmd: String) -> std::result::Result<(), Self::Err> {
        trace!("running: {}", cmd);
        self.port.write_all(cmd.as_bytes())?;
        self.port.write_all(b"\r")?;
        self.port.flush()?;

        Ok(())
    }

    #[cfg_attr(feature = "tracing", tracing::instrument)]
    fn receive(&mut self) -> std::result::Result<String, Self::Err> {
        let string = read_to_string_no_eof(&mut self.port)?;

        Ok(string)
    }
}
