//! FsRemove module

use std::path::Path;

use crate::logging::debug;

use crate::fs::helpers::os_str_to_str;
use crate::proto::storage::DeleteRequest;
use crate::transport::Transport;
use crate::transport::serial::rpc::CommandIndex;
use crate::{
    error::{Error, Result},
    proto,
    rpc::req::Request,
    transport::TransportRaw,
};

/// ReadDir traits for flipper filesystem
pub trait FsRemove {
    /// Removes a file or directory at path
    fn fs_remove(&mut self, path: impl AsRef<Path>, recursive: bool) -> Result<()>;
}

impl<T> FsRemove for T
where
    T: TransportRaw<proto::Main, proto::Main, Err = Error> + CommandIndex + std::fmt::Debug,
{
    #[doc(alias = "fs_rm")]
    fn fs_remove(&mut self, path: impl AsRef<Path>, recursive: bool) -> Result<()> {
        let path = os_str_to_str(path.as_ref().as_os_str())?.to_string();

        debug!("removing file {path:?}");
        let rm_req = Request::StorageDelete(DeleteRequest { path, recursive });

        self.send_and_receive(rm_req)?;

        Ok(())
    }
}
