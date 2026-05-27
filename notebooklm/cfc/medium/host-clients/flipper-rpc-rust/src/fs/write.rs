//! FsWrite module

use std::path::Path;
#[cfg(feature = "fs-write-progress-mpsc")]
use std::sync::mpsc::Sender;

use crate::logging::debug;

use crate::{
    error::{Error, Result},
    fs::{CHUNK_SIZE, helpers::os_str_to_str},
    proto::{
        self,
        storage::{File, WriteRequest, file::FileType},
    },
    rpc::req::Request,
    transport::{TransportRaw, serial::rpc::CommandIndex},
};

/// Write traits for flipper filesystem
pub trait FsWrite {
    /// Writes a &[u8] to a file on the flipper zero to dst, wrapper of fs_write_reader.
    fn fs_write(
        &mut self,
        path: impl AsRef<Path>,
        data: impl AsRef<[u8]>,
        #[cfg(feature = "fs-write-progress-mpsc")] tx: Option<Sender<usize>>,
    ) -> Result<()>;
}

/// I did a few tests and this number came out to ~67.2 KiB/s for my machine, rounding down to 50
/// for most machines
pub(crate) const THROUGHPUT_KIB: usize = 50;

/// How many chunks in a second?
pub(crate) const CHUNKS_PER_SECOND: usize = (THROUGHPUT_KIB * 1024) / CHUNK_SIZE;

/// How many seconds between pings
pub(crate) const PING_INTERVAL_SECONDS: usize = 5; // 5 Seconds per ping

/// How many chunks between pings?
pub(crate) const CHUNKS_PER_PING: usize = PING_INTERVAL_SECONDS * CHUNKS_PER_SECOND;

impl<T> FsWrite for T
where
    T: TransportRaw<proto::Main, proto::Main, Err = Error> + CommandIndex + std::fmt::Debug,
{
    fn fs_write(
        &mut self,
        path: impl AsRef<Path>,
        data: impl AsRef<[u8]>,
        #[cfg(feature = "fs-write-progress-mpsc")] tx: Option<Sender<usize>>,
    ) -> Result<()> {
        let path = path.as_ref();

        let path_str = os_str_to_str(path.as_os_str())?;

        let file = path
            .file_name()
            .and_then(std::ffi::OsStr::to_str)
            .ok_or_else(|| {
                std::io::Error::new(
                    std::io::ErrorKind::InvalidInput,
                    "path must include a UTF-8 file name; use fs_mkdir for directories",
                )
            })?;

        let data = data.as_ref();

        let chunks = chunks_or_empty(data, CHUNK_SIZE);
        let total_chunks = chunks.len();

        #[cfg(feature = "fs-write-progress-mpsc")]
        let mut sent = 0;

        #[cfg(feature = "fs-write-progress-mpsc")]
        if let Some(ref tx) = tx {
            tx.send(sent)?;
        }

        let command_id = self.command_index();

        debug!("writing {} bytes to {path:?}", data.len());

        // UPDATE: Files must be sent with occasional PINGS! This tells the flipper to not close
        // the connection, since we have not read anything for a while. Inserts a ping every
        // CHUNKS_PER_PING chunks.

        for (i, chunk) in chunks.enumerate() {
            if i > CHUNKS_PER_PING && i % CHUNKS_PER_PING == 0 {
                self.send_and_receive_raw(Request::Ping(vec![0]).into_rpc(command_id + 1))?;
            }
            let has_next = i != total_chunks - 1; // If this is not the last chunk, it has another.

            let write_req = Request::StorageWrite(WriteRequest {
                path: path_str.to_string(),
                file: Some(File {
                    r#type: FileType::File.into(),
                    name: file.to_string(),
                    data: chunk.to_vec(),
                    size: chunk.len() as u32,
                    md5sum: hex::encode(*md5::compute(chunk)),
                }),
            })
            .into_rpc(command_id)
            .with_has_next(has_next);

            self.send_raw(write_req)?;

            #[cfg(feature = "fs-write-progress-mpsc")]
            if let Some(ref tx) = tx {
                sent += chunk.len();
                tx.send(sent)?;
            }
        }

        self.receive_raw()?;
        self.increment_command_index(2);

        Ok(())
    }
}

#[inline(always)]
fn chunks_or_empty<'a>(
    data: &'a [u8],
    chunk_size: usize,
) -> Box<dyn ExactSizeIterator<Item = &'a [u8]> + 'a> {
    if data.is_empty() {
        Box::new(std::iter::once(&[][..]))
    } else {
        Box::new(data.chunks(chunk_size))
    }
}
