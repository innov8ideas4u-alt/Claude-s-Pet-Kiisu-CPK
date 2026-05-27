use std::sync::mpsc::channel;

use flipper_rpc::{
    error::Result,
    fs::{FsMetadata, FsRead, FsReadDir, FsRemove, FsWrite},
    transport::serial::{list_flipper_ports, rpc::SerialRpcTransport},
};
use std::time::Instant;

fn main() -> Result<()> {
    let ports = list_flipper_ports()?;

    let port = &ports[0].port_name;

    let mut cli = SerialRpcTransport::new(port)?;

    let (tx, rx) = channel();
    let data = (0..512 * 10).map(|i| (i / 512) as u8).collect::<Vec<_>>();
    let len = data.len();

    let handle = std::thread::spawn(move || {
        let start = Instant::now();
        for sent in rx {
            println!("[+{:.2?}] Progress: {}/{}", start.elapsed(), sent, len);
        }
    });

    cli.fs_write("/ext/file2.txt", data, Some(tx))?;

    handle.join().unwrap();

    println!("{:?}", cli.fs_metadata("/ext/file2.txt")?);
    println!("{:?}", cli.fs_read("/ext/file2.txt")?.len());
    println!(
        "{:?}",
        cli.fs_read_dir("/ext/subghz/Customer_Assistance_Buttons/Walgreens", true)?
            .collect::<Vec<_>>()
    );

    cli.fs_remove("/ext/file2.txt", false)?;

    Ok(())
}
