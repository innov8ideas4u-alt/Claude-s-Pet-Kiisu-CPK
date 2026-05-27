//! A transport that sends RPC messages on a port
//!
//! # Examples
//!
//! ```no_run
//! use flipper_rpc::{rpc::{res::Response, req::Request}, error::Result, transport::serial::rpc::SerialRpcTransport};
//! use flipper_rpc::transport::Transport;
//!
//! # fn main() -> Result<()> {
//! let mut cli = SerialRpcTransport::new("/dev/ttyACM0".to_string())?;
//!
//! let resp = cli.send_and_receive(Request::Ping(vec![1, 2, 3, 4]))?; // or send_raw for raw proto messages!
//!
//! assert_eq!(resp, Response::Ping(vec![1, 2, 3, 4]));
//! # Ok(())
//! # }
//! ```
use crate::error::{Error, Result};
use crate::logging::trace;
use crate::transport::serial::TIMEOUT;
use crate::{
    proto,
    transport::{
        TransportRaw,
        serial::{
            FLIPPER_BAUD,
            helpers::{drain_until, drain_until_str},
        },
    },
};

use crate::proto::CommandStatus;
use prost::Message;
use serialport::SerialPort;

/// A transport that sends RPC messages on a port
///
/// # Examples
///
/// ```no_run
/// use flipper_rpc::transport::serial::rpc::SerialRpcTransport;
/// use flipper_rpc::rpc::{req::Request, res::Response};
/// use flipper_rpc::error::Result;
/// use flipper_rpc::transport::Transport;
///
/// # fn main() -> Result<()> {
/// let mut cli = SerialRpcTransport::new("/dev/ttyACM0".to_string())?;
///
/// let resp = cli.send_and_receive(Request::Ping(vec![1, 2, 3, 4]))?; // or send_raw for raw proto messages!
///
/// assert_eq!(resp, Response::Ping(vec![1, 2, 3, 4]));
/// # Ok(())
/// # }
/// ```
#[derive(Debug)]
pub struct SerialRpcTransport {
    command_index: u32,
    port: Box<dyn SerialPort>,
}

/// Adds a command_index getter/setter. Useful since Transports dont automatically track command
/// index, and these functions can directly interop with the Transport's governing RPC channel.
pub trait CommandIndex {
    /// Changes the command index and returns the new value
    fn increment_command_index(&mut self, by: u32) -> u32;

    /// Gets the current command index
    fn command_index(&mut self) -> u32;
}

impl CommandIndex for SerialRpcTransport {
    fn increment_command_index(&mut self, by: u32) -> u32 {
        self.command_index += by;

        self.command_index
    }

    fn command_index(&mut self) -> u32 {
        self.command_index
    }
}

impl SerialRpcTransport {
    /// Opens a new RPC session on the given serial port path.
    ///
    /// Initialize the serial connection and start an RPC session.
    ///
    /// # Errors
    ///
    /// Returns an error if the port cannot be opened, initialization commands fail, or
    /// the RPC banner prompt is not received.
    ///
    /// # Examples
    ///
    /// ```no_run
    /// use flipper_rpc::{error::Result, transport::serial::rpc::SerialRpcTransport};
    ///
    /// # fn main() -> Result<()> {
    ///
    /// let mut cli = SerialRpcTransport::new("/dev/ttyACM0".to_string())?;
    ///
    /// # Ok(())
    /// # }
    /// ```
    #[cfg_attr(feature = "tracing", tracing::instrument)]
    pub fn new<S: AsRef<str> + std::fmt::Debug>(port: S) -> Result<Self> {
        let mut port = serialport::new(port.as_ref(), FLIPPER_BAUD)
            .timeout(TIMEOUT)
            .open()?;

        trace!("draining(prompt)");
        drain_until_str(&mut port, ">: ", TIMEOUT)?;

        trace!("start_rpc_session");
        port.write_all("start_rpc_session\r".as_bytes())?;
        port.flush()?;

        trace!("draining(start_rpc_session, \\n)");
        drain_until(&mut port, b'\n', TIMEOUT)?;

        Ok(Self {
            command_index: 0,
            port,
        })
    }

    /// Wraps a SerialPort with a SerialRpcTransport
    /// WARN: Does not reconfigure the port, just passes it into the internal holder, you must make
    /// sure that the port is in an RPC session. To convert a SerialCliTransport into
    /// a SerialRpcTransport, use SerialCliTransport::into_rpc(self) instead.
    #[cfg_attr(feature = "tracing", tracing::instrument)]
    pub fn from_port(port: Box<dyn SerialPort>) -> Result<Self> {
        Ok(Self {
            command_index: 0,
            port,
        })
    }
}

impl proto::Main {
    /// Sets the command id in a proto
    pub fn with_command_id(mut self, command_id: u32) -> Self {
        self.command_id = command_id;

        self
    }

    /// Sets the has_next flag in a proto
    pub fn with_has_next(mut self, has_next: bool) -> Self {
        self.has_next = has_next;

        self
    }
}

impl TransportRaw<proto::Main> for SerialRpcTransport {
    type Err = Error;

    /// Sends a length-delimited Protobuf RPC message to the Flipper.
    ///
    /// NOTE: Does not change command_id, auto incrementing has been moved into the easy api. If
    /// you need to change the command index, use [`CommandIndex::increment_command_index`]
    ///
    /// The internal command counter is used to set `command_id` on the message, whatever value is
    /// set in `value` will be overwritten
    ///
    /// # Errors
    ///
    /// Does NOT produce RPC errors based on command status. All sent commands default to Ok
    /// status.
    ///
    /// Returns an error if the message cannot be encoded or written to the port.
    ///
    /// # Examples
    ///
    /// ```no_run
    /// use flipper_rpc::proto;
    /// use flipper_rpc::proto::CommandStatus;
    /// use flipper_rpc::proto::main::Content;
    /// use flipper_rpc::proto::system;
    /// use flipper_rpc::transport::serial::rpc::SerialRpcTransport;
    /// use flipper_rpc::transport::TransportRaw;
    /// use flipper_rpc::error::Result;
    ///
    /// # fn main() -> Result<()> {
    ///
    /// let mut cli = SerialRpcTransport::new("/dev/ttyACM0")?;
    ///
    /// let ping = proto::Main {
    ///     command_id: 0,
    ///     command_status: proto::CommandStatus::Ok.into(),
    ///     has_next: false,
    ///     content: Some(proto::main::Content::SystemPingRequest(
    ///         system::PingRequest {
    ///             data: vec![0xDE, 0xAD, 0xBE, 0xEF],
    ///         },
    ///     )),
    /// };
    /// cli.send_raw(ping)?;
    ///
    /// # Ok(())
    /// # }
    /// ```
    #[cfg_attr(feature = "tracing", tracing::instrument)]
    fn send_raw(&mut self, value: proto::Main) -> std::result::Result<(), Self::Err> {
        let encoded = value.encode_length_delimited_to_vec();
        self.port.write_all(&encoded)?;

        self.port.flush()?;

        Ok(())
    }

    /// Reads a length-delimited Protobuf RPC message from the flipper. This must be called
    /// directly after data is sent, and cannot be called after a message is sent before (will
    /// panic)
    ///
    /// Uses a two-shot method of reading: first to get varint length + partial data, then to
    /// fetch remaining bytes if the message exceeds the initial buffer.
    ///
    /// # Errors
    ///
    /// Returns an error if no data is received, decoding fails, or IO operations fail.
    ///
    /// Additionally, this command returns an error if the underlying RPC command fails with
    /// a non-CommandStatus::Ok status code. It will be auto-converted into an Error
    ///
    /// # Examples
    ///
    /// ```no_run
    /// use flipper_rpc::transport::serial::rpc::SerialRpcTransport;
    /// use flipper_rpc::error::Result;
    /// use flipper_rpc::transport::TransportRaw;
    ///
    /// # fn main() -> Result<()> {
    /// let mut cli = SerialRpcTransport::new("/dev/ttyACM0".to_string())?;
    /// let response = cli.receive_raw()?;
    /// # Ok(())
    /// # }
    /// ```
    #[cfg_attr(feature = "tracing", tracing::instrument)]
    #[cfg(feature = "transport-serial-optimized")]
    fn receive_raw(&mut self) -> std::result::Result<proto::Main, Self::Err> {
        use prost::bytes::Buf;

        self.port.flush()?;

        // INFO: Super-overcomplicated but fast and efficent way of reading any length varint + data in exactly two
        // syscalls
        // Tries to use a stack-based approach when possible and does it efficently

        // Hard limit for all stack-based buffers
        // NOTE: Adding 10 as Varint max length is 10

        #[cfg(feature = "transport-serial-optimized-large-stack-limit")]
        const STACK_LIMIT: usize = 10 + 512;
        #[cfg(not(feature = "transport-serial-optimized-large-stack-limit"))]
        const STACK_LIMIT: usize = 10 + 128;

        let mut buf = [0u8; STACK_LIMIT];

        // Yeah that first comment was somewhat of a lie, it should be a MINIMUM of two reads.
        // If the first read fails, we wouldn't know and it would return incomplete data.
        // So we have to have a fail-safe loop. This actually does not cost much, as it will
        // still read only once if it doesn't fail

        // Error-prone code
        // ```no_run
        // let read = self.port.read(&mut buf)?;
        // ```
        //
        // Error-proof code!

        let mut read = 0;

        let mut available_bytes = buf.len();

        trace!("reading varint");
        while read < available_bytes {
            match self.port.read(&mut buf[read..]) {
                Ok(0) => break, // No more data
                Ok(n) => {
                    available_bytes = self.port.bytes_to_read()? as usize;
                    read += n
                }
                Err(ref e) if e.kind() == std::io::ErrorKind::TimedOut => break,
                Err(e) => return Err(e.into()),
            }
        }

        if read == 0 {
            return Err(std::io::Error::new(
                std::io::ErrorKind::UnexpectedEof,
                "no data read, failed to parse varint",
            )
            .into());
        }

        let total_data_length = prost::decode_length_delimiter(&buf[..read])?;
        trace!(total_data_length, "decoded response length");

        // We have the length of the data, however some or all of the actual data is inside of buf,
        // after the varint, it just continues to RPC data.

        // How many bytes does the varint take up?
        let varint_length = prost::length_delimiter_len(total_data_length);
        trace!(varint_length, "varint length");

        // PERF: All the data that is not varint data, this is another main optimization,
        // we skip another read, as we have already read the data.
        // We get all data after the varint until we stopped reading
        let partial_data = &buf[varint_length..read];

        // NOTE: We can skip the math since varint_length is always `1` for numbers 0-9 (varints go
        // above 1 byte when value > 127, since they only use 7 bits, and the MSB is an indicator
        // of weather the varint is done). If we read
        // more data, we would have to do:
        // total_data_length <= 10 - varint_length or total_data_length <= partial_data.len()
        let read_all_data = total_data_length <= partial_data.len();

        trace!("decoding response");
        // PERF: If all of the data was read, the entire message is contained within the 10 byte buffer,
        // so we do not need to perfom another read operation
        let main = if read_all_data {
            // INFO: partial_data is all of the data in the buffer besides the varint and
            // trailing zeros if we read less than the buf's size

            trace!("L3 decode");
            proto::Main::decode(partial_data)?
        } else {
            // WARN: Data did NOT fit inside of the buffer, this means that some of the data is
            // missing from the buffer

            // `partial_data` is the only data that was in the buffer

            // Now we need to get the remaining bytes and join them together with partial_data to
            // get the full data, then we should decode it

            // PERF: Optimization alert! As no one expected, stack buffers are waaay faster than vecs.
            // Capiitalizing on this, all messages with < STACK_LIMIT bytes will be put (partially)
            // into a stack buffer. Then, we can chain them with bytes::buf::Buf and pass that
            // directly to the decoder for a zero-overhead decoding
            //
            // PERF: For messages larger than STACK_LIMIT, we do a vec based processing. Since stack
            // sizes must be known at compile time, this is the only way to do a stack-processing
            // method with data that could be infinitely large.

            // How much data is left
            let remaining_length = total_data_length - partial_data.len();

            if remaining_length <= STACK_LIMIT {
                trace!("L2 decode");
                // Free speed for small messages!
                let mut stack_buf = [0u8; STACK_LIMIT];
                self.port.read_exact(&mut stack_buf[..remaining_length])?;

                let chained = partial_data.chain(&stack_buf[..remaining_length]);

                proto::Main::decode(chained)?
            } else {
                use crate::logging::warn;

                trace!(
                    "L1 decode - WARN: Increase STACK_LIMIT, current: {STACK_LIMIT}, need: {remaining_length}"
                );
                #[cfg(feature = "transport-serial-optimized-large-stack-limit")]
                warn!(remaining_length, "extremely large response");
                #[cfg(not(feature = "transport-serial-optimized-large-stack-limit"))]
                warn!(
                    remaining_length,
                    "large response; consider enabling the 'transport-serial-optimized-large-stack-limit' feature"
                );

                // Uses a slower heap (vec) based decoding for larger messages.
                let mut remaining_data = vec![0u8; remaining_length];
                self.port.read_exact(&mut remaining_data)?;

                let chained = partial_data.chain(remaining_data.as_slice());

                proto::Main::decode(chained)?
            }
        };

        // Should be a valid command status
        decode_command_status(main.command_status)?.into_result(main)
    }

    /// Reads a length-delimited Protobuf RPC message from the flipper. This must be called
    /// directly after data is sent, and cannot be called after a message is sent before (will
    /// panic)
    ///
    /// Reads the next RPC message from the Flipper using a byte-wise varint decoder.
    ///
    /// This method issues up to 11 syscalls but and relies on only heap buffers.
    /// Opt to use read_rpc_proto when possible
    /// NOTE: Optimized method disabled. BAD IDEA UNLESS OPTIMIZED METHOD IS BROKEN FOR USECASE
    ///
    /// **Deprecated**: Prefer the [`serial-optimized-varint-reading`] feature.
    ///
    /// NOTE: Comapred to the one above, this looks stupid and shitty. It makes a maximum of 11
    /// syscalls, with a minimum of 2. 11 for large messages and 2 for messages < 127 bytes.
    /// It also only relies on the heap
    ///
    /// ~~Useful for less-complex and very small transfers. Otherwise use the other version~~
    /// EDIT: Not useful at all, I did many benchmarks and this lost 80% of the time. It only
    /// won (tied) when it had a single byte varint, and that was only due to caching. This is
    /// a bad function.
    ///
    /// Included for compatablity in case the improved function breaks, the user can fallback to
    /// this while they wait for their issue to be resolved through gh
    #[cfg(not(feature = "transport-serial-optimized"))]
    #[cfg_attr(feature = "tracing", tracing::instrument)]
    #[deprecated(
        note = "Use the serial-optimized-varint-reading instead. This function is very slow. Only use when optimized method is broken. Please submit a PR/Issue to GH if it is broken.",
        since = "0.4.0"
    )]
    fn receive_raw(&mut self) -> std::result::Result<proto::Main, Self::Err> {
        use crate::proto::CommandStatus;

        self.port.flush()?;

        let mut buf = [0u8; 10];
        let mut index = 0;

        while index < 10 {
            self.port.read_exact(&mut buf[index..=index])?;

            if buf[index] & 0x80 == 0 {
                break;
            }

            index += 1;
        }

        let len = prost::decode_length_delimiter(buf.as_slice())?;
        let mut msg_buf = vec![0u8; len];
        self.port.read_exact(&mut msg_buf)?;

        let main = proto::Main::decode(msg_buf.as_slice())?;

        // Should be a valid command status
        decode_command_status(main.command_status)?.into_result(main)
    }
}

fn decode_command_status(raw: i32) -> Result<CommandStatus> {
    CommandStatus::try_from(raw).map_err(|_| Error::InvalidCommandStatus(raw))
}
