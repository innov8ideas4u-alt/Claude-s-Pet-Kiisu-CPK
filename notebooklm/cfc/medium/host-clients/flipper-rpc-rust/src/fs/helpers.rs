//! Helper functions for dealing with FS protocols

use crate::error::Result;
use std::ffi::OsStr;

#[inline(always)]
/// Converts an &OsStr into a regular &str with a standard error
pub fn os_str_to_str(path: &OsStr) -> Result<&str> {
    path.to_str().ok_or_else(|| {
        std::io::Error::new(std::io::ErrorKind::InvalidData, "Path is not UTF-8").into()
    })
}
