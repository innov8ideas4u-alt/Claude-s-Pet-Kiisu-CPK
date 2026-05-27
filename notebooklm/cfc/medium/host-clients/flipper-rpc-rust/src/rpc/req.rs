//! Request type. Covers all Content's ending with "Request"

use crate::proto::StopSession;
use crate::proto::desktop::{
    IsLockedRequest, StatusSubscribeRequest, StatusUnsubscribeRequest, UnlockRequest,
};
use crate::proto::gpio::{
    GetOtgMode, GetPinMode, ReadPin, SetInputPull, SetOtgMode, SetPinMode, WritePin,
};
use crate::proto::gui::{
    SendInputEventRequest, StartScreenStreamRequest, StartVirtualDisplayRequest,
    StopScreenStreamRequest, StopVirtualDisplayRequest,
};
use crate::proto::property::GetRequest;
use crate::proto::storage::{MkdirRequest, StatRequest};
use crate::proto::system::{
    DeviceInfoRequest, FactoryResetRequest, PingRequest, PlayAudiovisualAlertRequest,
    ProtobufVersionRequest, RebootRequest, SetDateTimeRequest,
};
use crate::proto::{
    self, CommandStatus,
    app::{
        AppButtonPressReleaseRequest, AppButtonPressRequest, AppButtonReleaseRequest,
        AppExitRequest, AppLoadFileRequest, DataExchangeRequest, GetErrorRequest,
        LockStatusRequest, StartRequest,
    },
    storage::{
        BackupCreateRequest, BackupRestoreRequest, DeleteRequest, InfoRequest, ListRequest,
        Md5sumRequest, ReadRequest, RenameRequest, TarExtractRequest, TimestampRequest,
        WriteRequest,
    },
    system::{DateTime, UpdateRequest, reboot_request::RebootMode},
};

/// Wrapper around proto::Main tailored for requests. Can be turned into a proto::Main by
/// RcpRequest::into_rpc(self)
#[derive(Debug)]
#[non_exhaustive]
pub enum Request {
    /// Stops the current RPC session, returning to a text cli
    StopSession,
    /// Sends a Ping, will return with a RpcResponse::Ping
    Ping(Vec<u8>),
    /// Reboots the flipper into the specified reboot mode
    Reboot(RebootMode),
    /// Requests detailed device info
    SystemDeviceInfo,
    /// Factory resets the device
    SystemFactoryReset,
    /// Asks for the device's current date time
    SystemGetDatetime,
    /// Sets the device's current date time
    SystemSetDatetime(DateTime),
    /// Makes the sound effect in the mobile app when playing an alert. Flashes screen, buzzes, and
    /// makes a few beeps
    PlayAvAlert,
    /// Requests the device's protobuf version
    SystemProtobufVersion,
    /// Updates the device to a newer firmware. DFU, .fuf, resource, etc.
    SystemUpdate(UpdateRequest),
    /// Requests power info
    SystemPowerInfo,
    /// Requests storage info
    StorageInfo(InfoRequest),
    /// Gets the timestamp of a path
    StorageTimestamp(TimestampRequest),
    /// Gets information about a file or directory
    StorageMetadata(String),
    /// Lists files in a directory
    StorageList(ListRequest),
    /// Reads a file
    /// Will error with Storage.InvalidName if the path is a directory
    StorageRead(String),
    /// Writes to a file
    StorageWrite(WriteRequest),
    /// Deletes a file or directory
    StorageDelete(DeleteRequest),
    /// Creates a new directory
    StorageMkdir(String),
    /// Asks the flipper zero to calculate the MD5 sum of a file. Processes on device
    StorageMd5sum(String),
    /// Renames/moves a directory or file. (From, to)
    StorageRename(String, String),
    /// Creates a local backup of the flipper's storage
    StorageBackupCreate(String),
    /// Restores from a local backup
    StorageBackupRestore(String),
    /// Extracts a .tar stored on the flipper (tar, out)
    StorageTarExtract(String, String),
    /// Opens an app
    AppStart(StartRequest),
    /// Checks weather an app is locked
    AppLockStatus(LockStatusRequest),
    /// Exits the current app
    AppExit(AppExitRequest),
    /// Asks an app to load a file
    AppLoadFile(AppLoadFileRequest),
    /// Presses a button in an app
    AppButtonPress(AppButtonPressRequest),
    /// Releases a button in an app
    AppButtonRelease(AppButtonReleaseRequest),
    /// Presses then immediately releases a button in an app
    AppButtonPressRelease(AppButtonPressReleaseRequest),
    /// Asks for the most recent app error
    AppGetError(GetErrorRequest),
    /// Sends data to an app
    AppDataExchange(DataExchangeRequest),
    /// Starts screen sharing
    GuiStartScreenStream(StartScreenStreamRequest),
    /// Stops screen sharing
    GuiStopScreenStream(StopScreenStreamRequest),
    /// Sends a raw input event to the flipper. Unlike app inputs, this emulates a hardware button.
    GuiSendInputEvent(SendInputEventRequest),
    /// Starts a virual display session
    GuiStartVirtualDisplay(StartVirtualDisplayRequest),
    /// Ends a virtual display session
    GuiStopVirtualDisplay(StopVirtualDisplayRequest),
    /// Sets the pin mode of a pin
    GpioSetPinMode(SetPinMode),
    /// Sets a pin to a input and pull mode
    GpioSetInputPull(SetInputPull),
    /// Gets a pins mode
    GpioGetPinMode(GetPinMode),
    /// Reads a value from a pin
    GpioReadPin(ReadPin),
    /// Writes a value to a pin
    GpioWritePin(WritePin),
    /// Checks if the system is in OTG mode / 5V on GPIO
    GpioGetOtgMode(GetOtgMode),
    /// Sets the system's OTG mode
    GpioSetOtgMode(SetOtgMode),
    /// Gets a property
    PropertyGet(GetRequest),
    /// Checks if the desktop is locked
    DesktopIsLocked(IsLockedRequest),
    /// Unlocks the desktop
    DesktopUnlock(UnlockRequest),
    /// Subscribes to a status event on the desktop
    DesktopStatusSubscribe(StatusSubscribeRequest),
    /// Unsubscribed from a status event
    DesktopStatusUnsubscribe(StatusUnsubscribeRequest),
}

impl Request {
    /// Creates a proto::Main from an RpcRequest
    ///
    /// Useful for actually sending the requests, as this is what the API expects. Does not error.
    /// If command_id is None, it auto increments the command index.
    pub fn into_rpc(self, command_id: u32) -> proto::Main {
        use proto::main::Content;
        // Command streams of has_next for chunked data MUST share the same command ID. The entire
        // chain must have it. This will inc after data is sent and the chain will have the same id
        // for all
        proto::Main {
            command_id,
            command_status: CommandStatus::Ok.into(),
            has_next: false,

            // TODO: Implement user-friendly methods for all of these
            content: Some(match self {
                Request::StopSession => Content::StopSession(StopSession {}),
                Request::Ping(data) => Content::SystemPingRequest(PingRequest { data }),
                Request::Reboot(reboot_mode) => Content::SystemRebootRequest(RebootRequest {
                    mode: reboot_mode.into(),
                }),

                Request::SystemDeviceInfo => Content::SystemDeviceInfoRequest(DeviceInfoRequest {}),
                Request::SystemFactoryReset => {
                    Content::SystemFactoryResetRequest(FactoryResetRequest {})
                }
                Request::SystemGetDatetime => {
                    Content::SystemGetDatetimeRequest(crate::proto::system::GetDateTimeRequest {})
                }
                Request::SystemSetDatetime(date_time) => {
                    Content::SystemSetDatetimeRequest(SetDateTimeRequest {
                        datetime: Some(date_time),
                    })
                }
                Request::PlayAvAlert => {
                    Content::SystemPlayAudiovisualAlertRequest(PlayAudiovisualAlertRequest {})
                }
                Request::SystemProtobufVersion => {
                    Content::SystemProtobufVersionRequest(ProtobufVersionRequest {})
                }
                Request::SystemUpdate(update_req) => Content::SystemUpdateRequest(update_req),
                Request::SystemPowerInfo => {
                    Content::SystemPowerInfoRequest(crate::proto::system::PowerInfoRequest {})
                }
                Request::StorageInfo(req) => Content::StorageInfoRequest(req),
                Request::StorageTimestamp(req) => Content::StorageTimestampRequest(req),
                Request::StorageMetadata(path) => Content::StorageStatRequest(StatRequest { path }),
                Request::StorageList(req) => Content::StorageListRequest(req),
                Request::StorageRead(path) => Content::StorageReadRequest(ReadRequest { path }),
                Request::StorageWrite(req) => Content::StorageWriteRequest(req),
                Request::StorageDelete(req) => Content::StorageDeleteRequest(req),
                Request::StorageMkdir(path) => Content::StorageMkdirRequest(MkdirRequest { path }),
                Request::StorageMd5sum(path) => {
                    Content::StorageMd5sumRequest(Md5sumRequest { path })
                }
                Request::StorageRename(from, to) => Content::StorageRenameRequest(RenameRequest {
                    old_path: from,
                    new_path: to,
                }),
                Request::StorageBackupCreate(archive_path) => {
                    Content::StorageBackupCreateRequest(BackupCreateRequest { archive_path })
                }
                Request::StorageBackupRestore(archive_path) => {
                    Content::StorageBackupRestoreRequest(BackupRestoreRequest { archive_path })
                }
                Request::StorageTarExtract(tar, out) => {
                    Content::StorageTarExtractRequest(TarExtractRequest {
                        tar_path: tar,
                        out_path: out,
                    })
                }

                Request::AppStart(req) => Content::AppStartRequest(req),
                Request::AppLockStatus(req) => Content::AppLockStatusRequest(req),
                Request::AppExit(req) => Content::AppExitRequest(req),
                Request::AppLoadFile(req) => Content::AppLoadFileRequest(req),
                Request::AppButtonPress(req) => Content::AppButtonPressRequest(req),
                Request::AppButtonRelease(req) => Content::AppButtonReleaseRequest(req),
                Request::AppButtonPressRelease(req) => Content::AppButtonPressReleaseRequest(req),
                Request::AppDataExchange(req) => Content::AppDataExchangeRequest(req),
                Request::AppGetError(req) => Content::AppGetErrorRequest(req),

                Request::GuiStartScreenStream(req) => Content::GuiStartScreenStreamRequest(req),
                Request::GuiStopScreenStream(req) => Content::GuiStopScreenStreamRequest(req),
                Request::GuiSendInputEvent(req) => Content::GuiSendInputEventRequest(req),
                Request::GuiStartVirtualDisplay(req) => Content::GuiStartVirtualDisplayRequest(req),
                Request::GuiStopVirtualDisplay(req) => Content::GuiStopVirtualDisplayRequest(req),

                Request::GpioSetPinMode(req) => Content::GpioSetPinMode(req),
                Request::GpioSetInputPull(req) => Content::GpioSetInputPull(req),
                Request::GpioGetPinMode(req) => Content::GpioGetPinMode(req),
                Request::GpioReadPin(req) => Content::GpioReadPin(req),
                Request::GpioWritePin(req) => Content::GpioWritePin(req),
                Request::GpioGetOtgMode(req) => Content::GpioGetOtgMode(req),
                Request::GpioSetOtgMode(req) => Content::GpioSetOtgMode(req),

                Request::PropertyGet(req) => Content::PropertyGetRequest(req),
                Request::DesktopIsLocked(req) => Content::DesktopIsLockedRequest(req),
                Request::DesktopUnlock(req) => Content::DesktopUnlockRequest(req),
                Request::DesktopStatusSubscribe(req) => Content::DesktopStatusSubscribeRequest(req),
                Request::DesktopStatusUnsubscribe(req) => {
                    Content::DesktopStatusUnsubscribeRequest(req)
                }
            }),
        }
    }
}
