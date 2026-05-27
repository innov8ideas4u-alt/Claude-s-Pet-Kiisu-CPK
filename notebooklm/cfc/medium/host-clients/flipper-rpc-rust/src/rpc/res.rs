//! Response type. Maps all Content's ending with "Response"

use std::borrow::Cow;

use crate::proto::{
    self,
    app::{AppStateResponse, GetErrorResponse, LockStatusResponse},
    desktop::Status,
    gpio::{GetOtgModeResponse, GetPinModeResponse, ReadPinResponse},
    gui::ScreenFrame,
    main::Content,
    property::GetResponse,
    storage::{InfoResponse, TimestampResponse, file::FileType},
    system::{
        DateTime, DeviceInfoResponse, PowerInfoResponse, ProtobufVersionResponse, UpdateResponse,
    },
};

macro_rules! define_into_impl {
    ($enum_name:ident $variant:ident $typ:ty) => {
        impl std::convert::TryFrom<$enum_name> for $typ {
            type Error = crate::error::Error;

            fn try_from(value: $enum_name) -> Result<$typ, Self::Error> {
                match value {
                    $enum_name::$variant(x) => Ok(x),
                    other => Err(crate::error::Error::UnexpectedResponse {
                        expected: stringify!($variant),
                        actual: other.kind(),
                    }),
                }
            }
        }
    };
    ($enum_name:ident $variant:ident) => {};
}

macro_rules! define_into_enum {
     (
        $(#[$enum_meta:meta])*
        $vis:vis enum $enum_name:ident {
            $(
                $(#[$variant_meta:meta])*
                $variant:ident $( ( $typ:ty ) )?
            ),* $(,)?
        }
    ) => {
        $(#[$enum_meta])*
        $vis enum $enum_name {
            $(
                $(#[$variant_meta])*
                #[doc = stringify!($enum_name::$variant)]
                $variant $( ( $typ ) )?,
            )*
        }

        $(
            define_into_impl!($enum_name $variant $( $typ)?);
        )*
    };
}

// bootleg proc-macros but i dont wanna make any
define_into_enum! {
    /// Wrapper around proto::Main tailored for responses. Can be made from a proto::Main by
    /// Into/From
#[derive(Debug, PartialEq)]
#[non_exhaustive]
pub enum Response {
    Empty,
    Ping(Vec<u8>),
    SystemDeviceInfo(DeviceInfoResponse),
    SystemGetDatetime(Option<DateTime>),
    SystemProtobufVersion(ProtobufVersionResponse),
    SystemUpdate(UpdateResponse),
    SystemPowerInfo(PowerInfoResponse),
    StorageInfo(InfoResponse),
    StorageTimestamp(TimestampResponse),
    StorageStat(Option<u32>),
    StorageList(Vec<ReadDirItem>),
    StorageRead(Option<Cow<'static, [u8]>>),
    StorageMd5sum(String),
    AppLockStatus(LockStatusResponse),
    AppGetError(GetErrorResponse),
    GuiScreenFrame(ScreenFrame),
    GpioGetPinMode(GetPinModeResponse),
    GpioReadPin(ReadPinResponse),
    GpioGetOtgMode(GetOtgModeResponse),
    AppState(AppStateResponse),
    PropertyGet(GetResponse),
    DesktopStatus(Status),
}
}

/// Item read using fs_read_dir / Request::StorageList
#[derive(Debug, PartialEq)]
pub enum ReadDirItem {
    /// Directory + Name
    Dir(String),
    /// Name, File size, MD5 Hash
    File(String, u32, Option<String>),
}

impl Response {
    fn kind(&self) -> &'static str {
        match self {
            Self::Empty => "Empty",
            Self::Ping(_) => "Ping",
            Self::SystemDeviceInfo(_) => "SystemDeviceInfo",
            Self::SystemGetDatetime(_) => "SystemGetDatetime",
            Self::SystemProtobufVersion(_) => "SystemProtobufVersion",
            Self::SystemUpdate(_) => "SystemUpdate",
            Self::SystemPowerInfo(_) => "SystemPowerInfo",
            Self::StorageInfo(_) => "StorageInfo",
            Self::StorageTimestamp(_) => "StorageTimestamp",
            Self::StorageStat(_) => "StorageStat",
            Self::StorageList(_) => "StorageList",
            Self::StorageRead(_) => "StorageRead",
            Self::StorageMd5sum(_) => "StorageMd5sum",
            Self::AppLockStatus(_) => "AppLockStatus",
            Self::AppGetError(_) => "AppGetError",
            Self::GuiScreenFrame(_) => "GuiScreenFrame",
            Self::GpioGetPinMode(_) => "GpioGetPinMode",
            Self::GpioReadPin(_) => "GpioReadPin",
            Self::GpioGetOtgMode(_) => "GpioGetOtgMode",
            Self::AppState(_) => "AppState",
            Self::PropertyGet(_) => "PropertyGet",
            Self::DesktopStatus(_) => "DesktopStatus",
        }
    }
}

fn decode_storage_file_type(raw: i32) -> Result<FileType, crate::error::Error> {
    FileType::try_from(raw).map_err(|_| crate::error::Error::InvalidStorageFileType(raw))
}

impl TryFrom<proto::Main> for Response {
    type Error = crate::error::Error;

    fn try_from(value: proto::Main) -> Result<Self, Self::Error> {
        use Response::*;
        let content = value.content;

        match content {
            None | Some(Content::Empty(_)) => Ok(Empty),
            Some(x) => match x {
                Content::SystemPingResponse(r) => Ok(Ping(r.data)),
                Content::SystemDeviceInfoResponse(r) => Ok(SystemDeviceInfo(r)),
                Content::SystemGetDatetimeResponse(r) => Ok(SystemGetDatetime(r.datetime)),
                Content::SystemProtobufVersionResponse(r) => Ok(SystemProtobufVersion(r)),
                Content::SystemUpdateResponse(r) => Ok(SystemUpdate(r)),
                Content::SystemPowerInfoResponse(r) => Ok(SystemPowerInfo(r)),
                Content::StorageInfoResponse(r) => Ok(StorageInfo(r)),
                Content::StorageTimestampResponse(r) => Ok(StorageTimestamp(r)),
                Content::StorageStatResponse(r) => Ok(StorageStat(r.file.map(|x| x.size))),
                Content::StorageListResponse(r) => {
                    let items = r
                        .file
                        .into_iter()
                        .map(|file| {
                            Ok(match decode_storage_file_type(file.r#type)? {
                                FileType::File => ReadDirItem::File(
                                    file.name,
                                    file.size,
                                    if file.md5sum.is_empty() {
                                        None
                                    } else {
                                        Some(file.md5sum)
                                    },
                                ),
                                FileType::Dir => ReadDirItem::Dir(file.name),
                            })
                        })
                        .collect::<Result<Vec<_>, crate::error::Error>>()?;

                    Ok(StorageList(items))
                }
                Content::StorageReadResponse(r) => {
                    // Response would have returned an error if the requested path was a dir
                    // As of now, reading does not return any data about the file besides the data.
                    // No name/hash/size etc.
                    let data = match r.file {
                        None => None,
                        Some(file) => match decode_storage_file_type(file.r#type)? {
                            FileType::File => Some(file.data.into()),
                            FileType::Dir => {
                                return Err(crate::error::Error::InvalidRpcPayload(
                                    "storage read response contained a directory entry",
                                ));
                            }
                        },
                    };

                    Ok(StorageRead(data))
                }
                Content::StorageMd5sumResponse(r) => Ok(StorageMd5sum(r.md5sum)),
                Content::AppLockStatusResponse(r) => Ok(AppLockStatus(r)),
                Content::AppGetErrorResponse(r) => Ok(AppGetError(r)),
                Content::GuiScreenFrame(r) => Ok(GuiScreenFrame(r)),
                Content::GpioGetPinModeResponse(r) => Ok(GpioGetPinMode(r)),
                Content::GpioReadPinResponse(r) => Ok(GpioReadPin(r)),
                Content::GpioGetOtgModeResponse(r) => Ok(GpioGetOtgMode(r)),
                Content::AppStateResponse(r) => Ok(AppState(r)),
                Content::PropertyGetResponse(r) => Ok(PropertyGet(r)),
                Content::DesktopStatus(r) => Ok(DesktopStatus(r)),

                _ => Err(crate::error::Error::UnsupportedRpcContent),
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::proto::{
        self,
        main::Content,
        storage::{self, file::FileType},
        system,
    };

    #[test]
    fn converts_ping_response() {
        let message = proto::Main {
            command_id: 1,
            command_status: proto::CommandStatus::Ok.into(),
            has_next: false,
            content: Some(Content::SystemPingResponse(system::PingResponse {
                data: vec![1, 2, 3, 4],
            })),
        };

        let response = Response::try_from(message).expect("ping response should decode");

        assert_eq!(response, Response::Ping(vec![1, 2, 3, 4]));
    }

    #[test]
    fn rejects_request_messages() {
        let message = proto::Main {
            command_id: 1,
            command_status: proto::CommandStatus::Ok.into(),
            has_next: false,
            content: Some(Content::SystemPingRequest(system::PingRequest {
                data: vec![1, 2, 3, 4],
            })),
        };

        let error = Response::try_from(message).expect_err("request variants are not responses");

        assert!(matches!(error, crate::error::Error::UnsupportedRpcContent));
    }

    #[test]
    fn rejects_unknown_storage_file_types() {
        let message = proto::Main {
            command_id: 1,
            command_status: proto::CommandStatus::Ok.into(),
            has_next: false,
            content: Some(Content::StorageListResponse(storage::ListResponse {
                file: vec![storage::File {
                    r#type: 99,
                    name: "bad".to_string(),
                    size: 1,
                    data: Vec::new(),
                    md5sum: String::new(),
                }],
            })),
        };

        let error = Response::try_from(message).expect_err("unknown file types should fail");

        assert!(matches!(
            error,
            crate::error::Error::InvalidStorageFileType(99)
        ));
    }

    #[test]
    fn typed_conversions_report_variant_mismatches() {
        let error = Vec::<u8>::try_from(Response::StorageMd5sum("abc".to_string()))
            .expect_err("mismatched conversions should fail");

        assert!(matches!(
            error,
            crate::error::Error::UnexpectedResponse {
                expected: "Ping",
                actual: "StorageMd5sum",
            }
        ));
    }

    #[test]
    fn reads_file_payloads() {
        let message = proto::Main {
            command_id: 1,
            command_status: proto::CommandStatus::Ok.into(),
            has_next: false,
            content: Some(Content::StorageReadResponse(storage::ReadResponse {
                file: Some(storage::File {
                    r#type: FileType::File.into(),
                    name: "note.txt".to_string(),
                    size: 4,
                    data: b"test".to_vec(),
                    md5sum: String::new(),
                }),
            })),
        };

        let response = Response::try_from(message).expect("storage read should decode");

        assert_eq!(
            response,
            Response::StorageRead(Some(Cow::Owned(b"test".to_vec())))
        );
    }
}
