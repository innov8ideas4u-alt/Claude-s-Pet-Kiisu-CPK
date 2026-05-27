//! FsCreateDir module

use std::path::Path;

use crate::logging::{debug, trace};

use crate::fs::helpers::os_str_to_str;
use crate::transport::Transport;
use crate::transport::serial::rpc::CommandIndex;
use crate::{
    error::{Error, Result},
    proto::{self},
    rpc::req::Request,
    transport::TransportRaw,
};

/// CreateDir traits for flipper filesystem
pub trait FsMetadata {
    /// Stats a **file**. This API is stupid and only returns the file size, and errors with
    /// InvalidName when the path is a directory.
    fn fs_metadata(&mut self, path: impl AsRef<Path>) -> Result<u32>;
}

impl<T> FsMetadata for T
where
    T: TransportRaw<proto::Main, proto::Main, Err = Error> + CommandIndex + std::fmt::Debug,
{
    #[doc(alias = "fs_stat")]
    fn fs_metadata(&mut self, path: impl AsRef<Path>) -> Result<u32> {
        let path = os_str_to_str(path.as_ref().as_os_str())?.to_string();

        debug!("reading metadata for {path}");

        let response: Option<u32> = self
            .send_and_receive(Request::StorageMetadata(path))?
            .try_into()?;

        trace!("response collected");

        let size = response.ok_or_else(|| std::io::Error::other("Failed to read file"))?;

        Ok(size)
    }
}
