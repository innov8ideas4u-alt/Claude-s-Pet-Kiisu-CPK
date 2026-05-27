//! FsReadDir module

use std::path::Path;

use crate::logging::trace;

use crate::fs::helpers::os_str_to_str;
use crate::rpc::res::{ReadDirItem, Response};
use crate::transport::Transport;
use crate::transport::serial::rpc::CommandIndex;
use crate::{
    error::{Error, Result},
    proto::{self, storage::ListRequest},
    rpc::req::Request,
    transport::TransportRaw,
};

/// ReadDir traits for flipper filesystem
pub trait FsReadDir {
    /// Lists the files in a directory at path
    fn fs_read_dir(
        &mut self,
        path: impl AsRef<Path>,
        include_md5: bool,
    ) -> Result<impl Iterator<Item = ReadDirItem>>;
}

impl<T> FsReadDir for T
where
    T: TransportRaw<proto::Main, proto::Main, Err = Error> + CommandIndex + std::fmt::Debug,
{
    fn fs_read_dir(
        &mut self,
        path: impl AsRef<Path>,
        include_md5: bool,
    ) -> Result<impl Iterator<Item = ReadDirItem>> {
        let path = os_str_to_str(path.as_ref().as_os_str())?.to_string();

        let mut items = Vec::new();

        trace!("init readdir chain");
        // Send the initial request to start the chain
        self.send(Request::StorageList(ListRequest {
            path,
            include_md5,
            filter_max_size: 0,
        }))?;

        loop {
            // Receive the next list items
            let response = self.receive_raw()?;
            trace!("readdir chunk");
            let has_next = response.has_next;

            // Convert the raw response into usable data (Vec<ReadDirItem>)
            let chunk: Vec<ReadDirItem> = Response::try_from(response)?.try_into()?;
            items.extend(chunk);

            // If this is the last chunk, stop reading
            if !has_next {
                break;
            }
        }

        Ok(items.into_iter())
    }
}
