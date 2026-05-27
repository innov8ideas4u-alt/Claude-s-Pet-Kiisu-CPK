//! FsTarExtract module. Flipper-side .tar extraction.

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
pub trait FsTarExtract {
    /// Extracts a .tar, NOTE: NOT A TGZ, on the flipper from path -> out
    fn fs_extract_tar(&mut self, path: impl AsRef<Path>, out: impl AsRef<Path>) -> Result<()>;
}

impl<T> FsTarExtract for T
where
    T: TransportRaw<proto::Main, proto::Main, Err = Error> + CommandIndex + std::fmt::Debug,
{
    fn fs_extract_tar(&mut self, path: impl AsRef<Path>, out: impl AsRef<Path>) -> Result<()> {
        let path = os_str_to_str(path.as_ref().as_os_str())?.to_string();
        let out = os_str_to_str(out.as_ref().as_os_str())?.to_string();

        debug!("extracting {path} into {out}");

        self.send_and_receive(Request::StorageTarExtract(path, out))?;

        Ok(())
    }
}
