//! Helper functions for serial communication

use core::str;
use std::{
    io::{ErrorKind, Read, Result},
    time::{Duration, Instant},
};

/// Drain a stream until a str + padding chunk
///
/// Returns `Ok(())` if the str is found, or an error if timed out or another I/O issue occurs.
pub(crate) fn drain_until_str<R: Read>(
    reader: &mut R,
    until_str: &str,
    timeout: Duration,
) -> Result<()> {
    assert!(!until_str.is_empty(), "until_str must not be empty");

    const CHUNK_SIZE: usize = 256;

    // INFO: In the worst case scenario, where the string starts @ the last byte in a chunk, it
    // must fit within the second chunk, otherwise it will not be found.
    assert!(until_str.len() <= CHUNK_SIZE + 1);

    let until_bytes = until_str.as_bytes();

    const BUF_LEN: usize = CHUNK_SIZE * 2;

    let mut buf = [0u8; BUF_LEN]; // Two chunk juggle

    let deadline = Instant::now() + timeout;

    let finder = memchr::memmem::Finder::new(until_bytes);

    let mut filled = 0;

    loop {
        if filled > CHUNK_SIZE {
            buf.copy_within(CHUNK_SIZE.., 0);
            filled -= CHUNK_SIZE;
        }

        let now = Instant::now();
        if now >= deadline {
            break;
        }

        match reader.read(&mut buf[filled..filled + CHUNK_SIZE.min(BUF_LEN - filled)]) {
            Ok(0) => {
                std::thread::sleep(Duration::from_millis(10)); // Cooldown
                continue;
            }
            Ok(n) => {
                filled += n;

                if finder.find(&buf).is_some() {
                    return Ok(());
                }
            }
            Err(ref e) if e.kind() == ErrorKind::TimedOut => continue,
            Err(e) => return Err(e),
        }
    }

    Err(std::io::Error::new(
        ErrorKind::TimedOut,
        format!("Timeout searching for '{}'", until_str),
    ))
}

/// Reads to the end of a stream without checking for EOF.
///
/// Loops over 1024 byte chunks (OK; since reading over the won't happen) until the reader reads
/// 0 bytes or an error occurs.
pub(crate) fn read_to_string_no_eof<R: Read>(reader: &mut R) -> Result<String> {
    let mut buffer = Vec::new();
    let mut temp = [0; 1024];

    loop {
        match reader.read(&mut temp) {
            Ok(0) => break,
            Ok(n) => buffer.extend_from_slice(&temp[..n]),
            Err(ref e) if e.kind() == ErrorKind::TimedOut => break,
            Err(e) => return Err(e),
        }
    }

    String::from_utf8(buffer).map_err(|e| std::io::Error::new(ErrorKind::InvalidData, e))
}

/// Drains a stream until a specific byte is found. Will read over by at most 256 bytes.
///
/// Returns `Ok(()` if the byte is found, or an error if an I/O issue occurs.
pub(crate) fn drain_until<R: Read>(reader: &mut R, delim: u8, timeout: Duration) -> Result<()> {
    const CHUNK_SIZE: usize = 256;

    let mut buf = [0u8; CHUNK_SIZE];

    let deadline = Instant::now() + timeout;

    while Instant::now() < deadline {
        match reader.read(&mut buf) {
            Ok(read) => {
                if memchr::memchr(delim, &buf[..read]).is_some() {
                    return Ok(());
                }
            }
            Err(ref e) if e.kind() == ErrorKind::TimedOut => continue,
            Err(e) => return Err(e),
        }
    }

    Err(std::io::Error::new(
        ErrorKind::TimedOut,
        format!("Timeout searching for byte 0x{:02x}", delim),
    ))
}
