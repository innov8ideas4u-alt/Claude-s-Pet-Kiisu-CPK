//! FsRead module

use std::borrow::Cow;
use std::path::Path;

use crate::logging::debug;

use crate::fs::helpers::os_str_to_str;
use crate::rpc::res::Response;
use crate::transport::Transport;
use crate::transport::serial::rpc::CommandIndex;
use crate::{
    error::{Error, Result},
    proto,
    rpc::req::Request,
    transport::TransportRaw,
};

/// Read traits for flipper filesystem
pub trait FsRead {
    /// Reads a file on the flipper zero from src
    fn fs_read(&mut self, path: impl AsRef<Path>) -> Result<Cow<'static, [u8]>>;

    /// Reads to a string
    fn fs_read_to_string(&mut self, path: impl AsRef<Path>) -> Result<Cow<'static, str>> {
        let bytes = self.fs_read(path)?;

        match bytes {
            Cow::Borrowed(bytes) => std::str::from_utf8(bytes)
                .map(Cow::Borrowed)
                .map_err(|e| e.to_string()),

            Cow::Owned(bytes) => String::from_utf8(bytes)
                .map(Cow::Owned)
                .map_err(|e| e.to_string()),
        }
        .map_err(|error_text| {
            std::io::Error::new(std::io::ErrorKind::InvalidData, error_text).into()
        })
    }

    /// Like [`fs_read_to_string`] but replaces non-utf8 chars with a replacement character
    fn fs_read_to_string_lossy(&mut self, path: impl AsRef<Path>) -> Result<Cow<'static, str>> {
        // Like String::from_utf8_lossy but operates on owned values
        #[inline(always)]
        fn string_from_utf8_lossy(buf: Vec<u8>) -> String {
            match String::from_utf8_lossy(&buf) {
                // buf contained non-utf8 chars than have been patched
                Cow::Owned(s) => s,
                // SAFETY: if Borrowed then the buf only contains utf8 chars,
                // we do this instead of .into_owned() to avoid copying the input buf
                Cow::Borrowed(_) => unsafe { String::from_utf8_unchecked(buf) },
            }
        }

        let bytes = self.fs_read(path)?;
        match bytes {
            Cow::Borrowed(bytes) => Ok(String::from_utf8_lossy(bytes)),
            Cow::Owned(bytes) => Ok(Cow::Owned(string_from_utf8_lossy(bytes))),
        }
    }
}

// NOTE: This API handles chunked responses for reading large files.
// If the response is large enough, it will be split into multiple chunks, which we need to process iteratively.
// To handle this, I re-implemented the command_index system and abstracted it into a trait ([`CommandIndex`]),
// allowing remote calls from user functions to interact with it.
//
// IMPORTANT BEHAVIOR NOTES:
// - For **reading**, you **do not need** a `command_id` or `has_next` flags to manage the operation.
//   The read operation will continue until the `has_next` flag is `false`.
// - However, for **writing**, the `command_id` and `has_next` flags **are required** to track the chunks.
// - A read chain starts with a single request (`send`), and subsequent chunks are received until the `has_next` flag is `false`.
// - This discovery came after some experimentation and insights from the `flipperzero_protobuf_py` library.
//
// TL;DR: Reads are simpler—just send one request and keep reading until `has_next` is `false`. Writes require
// more coordination via `command_id` and `has_next`.
impl<T> FsRead for T
where
    T: TransportRaw<proto::Main, proto::Main, Err = Error> + CommandIndex + std::fmt::Debug,
{
    fn fs_read(&mut self, path: impl AsRef<Path>) -> Result<Cow<'static, [u8]>> {
        // Convert the path to a string
        let path = os_str_to_str(path.as_ref().as_os_str())?;

        // Optionally fetch metadata if the "fs-read-metadata" feature is enabled
        #[cfg(feature = "fs-read-metadata")]
        let size: Option<u32> = self
            .send_and_receive(Request::StorageMetadata(path.to_string()))?
            .try_into()?;

        // Initialize buffer for storing the file contents
        #[cfg(feature = "fs-read-metadata")]
        let mut buf = match size {
            Some(size) => Vec::with_capacity(size as usize), // Pre-allocate buffer if size is known
            None => vec![],
        };

        #[cfg(not(feature = "fs-read-metadata"))]
        let mut buf = vec![]; // Default to an empty buffer if metadata isn't fetched

        debug!("init read chain");
        // Send the initial request to start the read chain
        self.send(Request::StorageRead(path.to_string()))?;

        loop {
            // Receive the next chunk of data (raw response to check for has_next flag)
            let response = self.receive_raw()?;
            debug!("read rpc chunk");

            // Check if there are more chunks to read
            let has_next = response.has_next;

            // Convert the raw response into usable data (Cow<[u8]>)
            let response: Option<Cow<'static, [u8]>> = Response::try_from(response)?.try_into()?;

            match response {
                // If no data was received, return an error
                None => {
                    return Err(std::io::Error::other("Failed to read file").into());
                }
                // Otherwise, add the data to the buffer
                Some(data) => {
                    buf.extend_from_slice(data.as_ref());
                }
            }

            // If this is the last chunk, stop reading
            if !has_next {
                break;
            }
        }

        // Return the entire contents as a Cow<[u8]> (static lifetime)
        Ok(buf.into())
    }
}
