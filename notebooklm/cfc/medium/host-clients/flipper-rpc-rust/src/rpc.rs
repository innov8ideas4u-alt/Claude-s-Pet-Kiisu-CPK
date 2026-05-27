//! This module aims to make a better experience for end users by mapping proto::* classes into
//! a user friendly Rpc{Request, Response}::* enum and have better documentation. Additionally it
//! maps a CommandStatus or a Response into a Result
//!
//! Enabled through easy-rpc feature

pub mod error;
pub mod req;
pub mod res;
