# flipper-rpc

`flipper-rpc` is a Rust library for talking to a Flipper Zero over its RPC
serial protocol. It ships generated protobuf bindings, a higher-level
request/response layer, serial transports, and feature-gated filesystem helpers.

The crate tracks the official Flipper protobuf schema published in
[`flipperdevices/flipperzero-protobuf`](https://github.com/flipperdevices/flipperzero-protobuf).
The serial framing uses protobuf length-delimited messages, which means each
`PB.Main` envelope is prefixed with a varint length as described in the
[Protocol Buffers encoding guide](https://protobuf.dev/programming-guides/encoding/).

## Crate layout

- `proto`: generated Rust types for the Flipper RPC schema
- `rpc`: ergonomic `Request` and `Response` enums over `proto::Main`
- `transport`: serial CLI and serial RPC transports
- `fs`: feature-gated filesystem helpers built on top of `easy-rpc`

## Features

| Feature | Purpose |
| --- | --- |
| `default` | Enables `minimal` |
| `minimal` | Generated protobuf types only (`proto`) |
| `proto` | `prost` encoding and decoding support |
| `easy-rpc` | High-level request and response wrappers |
| `fs-all` | Enables all filesystem helper traits |
| `fs-read` | Read files from the device |
| `fs-read-metadata` | Pre-size read buffers by fetching metadata first |
| `fs-write` | Write files to the device |
| `fs-readdir` | List directory contents |
| `fs-remove` | Remove files or directories |
| `fs-createdir` | Create directories |
| `fs-metadata` | Query file size metadata |
| `fs-md5` | Ask the device to calculate an MD5 for a file |
| `fs-tar-extract` | Ask the device to extract a `.tar` archive |
| `transport-serial` | Serial transport support |
| `transport-serial-optimized` | Faster serial response reader |
| `transport-serial-optimized-large-stack-limit` | Larger stack buffer for very large responses |
| `tracing` | Integrate with `tracing` spans and events |

Prefer enabling only the features you actually use.

## Installation

```bash
cargo add flipper-rpc --features easy-rpc,transport-serial-optimized
```

Example `Cargo.toml` entry:

```toml
[dependencies]
flipper-rpc = { version = "0.9.5", features = ["easy-rpc", "transport-serial-optimized"] }
```

## Example

```rust
use flipper_rpc::error::Result;
use flipper_rpc::rpc::{req::Request, res::Response};
use flipper_rpc::transport::serial::{list_flipper_ports, rpc::SerialRpcTransport};
use flipper_rpc::transport::Transport;

fn main() -> Result<()> {
    let port = list_flipper_ports()?
        .into_iter()
        .next()
        .ok_or_else(|| std::io::Error::new(std::io::ErrorKind::NotFound, "no flipper found"))?
        .port_name;

    let mut rpc = SerialRpcTransport::new(port)?;
    let response = rpc.send_and_receive(Request::Ping(vec![1, 2, 3, 4]))?;

    assert_eq!(response, Response::Ping(vec![1, 2, 3, 4]));
    Ok(())
}
```

## Protocol notes

The current transport implementation follows the same structure documented by
the official schema and the existing Flipper client implementations:

1. Open the serial device and drain the text prompt (`">: "`).
2. Enter RPC mode with `start_rpc_session\r`.
3. Encode a `proto::Main` message with `prost` length-delimited framing.
4. Read the length varint, then read and decode the protobuf payload.
5. Check `command_status` before converting the payload into `rpc::Response`.

The official protobuf schema defines the `PB.Main` envelope with these core
fields:

- `command_id`
- `command_status`
- `has_next`
- `content`

That envelope is what this crate reads and writes on the wire.

## Development

`flipper-rpc` includes a Nix dev shell and pinned Rust toolchain:

```bash
nix develop
cargo fmt -- --check
cargo test --features easy-rpc
cargo clippy --all-features -- -D warnings
```

## Related work

- [`flipperdevices/flipperzero-protobuf`](https://github.com/flipperdevices/flipperzero-protobuf)
- [`flipperdevices/flipperzero_protobuf_py`](https://github.com/flipperdevices/flipperzero_protobuf_py)
- [`liamhays/flipwire`](https://github.com/liamhays/flipwire)
