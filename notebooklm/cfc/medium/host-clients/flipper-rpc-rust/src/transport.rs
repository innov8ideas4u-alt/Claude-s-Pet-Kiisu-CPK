//! Generic transport traits

#[cfg(feature = "easy-rpc")]
use crate::{error::Error, transport::serial::rpc::CommandIndex};
use crate::{
    proto,
    rpc::{req::Request, res::Response},
};

#[cfg(feature = "transport-serial")]
pub mod serial;

/// Encodes, Decodes, Transports, and Receives data types
pub trait Transport<Send, Recv = Send> {
    /// Error type
    type Err: std::error::Error;

    /// Send a value of type `Send` over the transport.
    /// For a reader based transport, this function must consume the sent data, and must not consume the response.
    fn send(&mut self, value: Send) -> Result<(), Self::Err>;

    /// Receive a value of type `Recv` from the transport.
    /// For a reader based transport, this function must consume stream data.
    fn receive(&mut self) -> Result<Recv, Self::Err>;

    /// Send a value, then immediately wait for and return a response.
    /// For a reader based transport, this function must consume the sent and received data,
    /// returning the latter.
    ///
    /// By default this function just calls send and receive right after one another. This
    /// can be changed.
    fn send_and_receive(&mut self, value: Send) -> Result<Recv, Self::Err> {
        self.send(value)?;
        self.receive()
    }
}

/// Transport with _raw suffixes
pub trait TransportRaw<Send, Recv = Send> {
    /// Error type
    type Err: std::error::Error;

    /// Send a value of type `Send` over the transport.
    /// For a reader based transport, this function must consume the sent data, and must not consume the response.
    fn send_raw(&mut self, value: Send) -> Result<(), Self::Err>;

    /// Receive a value of type `Recv` from the transport.
    /// For a reader based transport, this function must consume stream data.
    fn receive_raw(&mut self) -> Result<Recv, Self::Err>;

    /// Send a value, then immediately wait for and return a response.
    /// For a reader based transport, this function must consume the sent and received data,
    /// returning the latter.
    ///
    /// By default this function just calls send_raw and receive_raw right after one another. This
    /// can be changed.
    fn send_and_receive_raw(&mut self, value: Send) -> Result<Recv, Self::Err> {
        self.send_raw(value)?;
        self.receive_raw()
    }
}

#[cfg(feature = "easy-rpc")]
// Not sure where this should go.. If any type can raw transport proto messages, they can be
// converted into Rpc-style messages and used through the easy API.
impl<T> Transport<Request, Response> for T
where
    T: TransportRaw<proto::Main, proto::Main, Err = Error> + CommandIndex + std::fmt::Debug,
{
    type Err = T::Err;

    /// Sends an easy-rpc Request and auto-increments command_id
    ///
    /// This is what most users will want, unless they are manually dealing with muti-part
    /// messages, this is much easier than any alternative.
    #[cfg_attr(feature = "tracing", tracing::instrument)]
    fn send(&mut self, req: Request) -> Result<(), Self::Err> {
        // Command streams of has_next for chunked data MUST share the same command ID. The entire
        // chain must have it. This will inc after data is sent and the chain will have the same id
        // for all

        let command_id = self.command_index(); // Get current index, guaranteed fresh.

        let proto = req.into_rpc(command_id); // Send the proto with the current index

        self.increment_command_index(1); // Update the index for next use

        self.send_raw(proto)?;

        Ok(())
    }

    /// Receives RPC reponse. Returns None if the response is Empty
    fn receive(&mut self) -> Result<Response, Self::Err> {
        let response = self.receive_raw()?;

        let rpc = Response::try_from(response)?;

        Ok(rpc)
    }
}
