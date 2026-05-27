//! FsMd5 module. Flipper-side MD5 Hashing

use std::path::Path;

use crate::logging::debug;

use crate::fs::helpers::os_str_to_str;
use crate::transport::Transport;
use crate::transport::serial::rpc::CommandIndex;
use crate::{
    error::{Error, Result},
    proto::{self},
    rpc::req::Request,
    transport::TransportRaw,
};

/// MD5 trait
pub trait FsMd5 {
    /// Unlike what the name says, this function does not calculate any MD5 hashes. It asks the flipper to!
    fn fs_md5(&mut self, path: impl AsRef<Path>) -> Result<String>;
}

impl<T> FsMd5 for T
where
    T: TransportRaw<proto::Main, proto::Main, Err = Error> + CommandIndex + std::fmt::Debug,
{
    fn fs_md5(&mut self, path: impl AsRef<Path>) -> Result<String> {
        let path = os_str_to_str(path.as_ref().as_os_str())?.to_string();

        debug!(path, "MD5 request for");

        let response: String = self
            .send_and_receive(Request::StorageMd5sum(path))?
            .try_into()?;

        debug!(response, "MD5");

        Ok(response)
    }
}
