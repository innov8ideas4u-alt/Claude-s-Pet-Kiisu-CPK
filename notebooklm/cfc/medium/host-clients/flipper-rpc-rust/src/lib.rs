#![cfg_attr(
    all(docsrs, feature = "document-features"),
    doc = ::document_features::document_features!()
)]
#![cfg_attr(
    all(docsrs, feature = "document-features"),
    feature(doc_cfg, doc_auto_cfg)
)]
#![deny(missing_docs)]
#![deny(unused_must_use)]
#![deny(clippy::all)]

//! `flipper-rpc` provides Rust access to the Flipper Zero RPC protocol.
//!
//! The crate is split into three layers:
//!
//! - [`proto`] exposes generated protobuf bindings for the official Flipper schema.
//! - [`rpc`] adds higher-level request and response enums over [`proto::Main`].
//! - [`transport`] contains serial transports for CLI and RPC sessions.
//!
//! Filesystem helpers live under [`fs`] and are enabled feature-by-feature so downstream crates can
//! keep compile times and dependency surface small.

// I don't have the time to write docs for auto-generated things
#[cfg(feature = "proto")]
#[allow(missing_docs)]
pub mod proto;

pub mod error;
pub mod logging;

#[cfg(feature = "easy-rpc")]
pub mod rpc;

#[cfg(feature = "fs-any")]
pub mod fs;

#[cfg(feature = "transport-any")]
pub mod transport;
