# Repository Guidelines

## Project Structure & Module Organization
`flipper-rpc` is a Rust library crate. Core crate metadata lives in `Cargo.toml`, the pinned toolchain in `rust-toolchain.toml`, and the Nix dev shell in `flake.nix`. Public modules live under `src/`: generated protobuf bindings in `src/proto/`, higher-level request/response wrappers in `src/rpc/`, filesystem helpers in `src/fs/`, and transports in `src/transport/`. Example programs live under `examples/serial/`. Keep generated protobuf modules isolated from handwritten code, and prefer adding new handwritten behavior in focused submodules rather than expanding `lib.rs`.

## Build, Test, and Development Commands
Use the Nix shell so contributors share the same Rust toolchain and utilities:

- `nix develop`: enter the shell with Rust, `clippy`, `rust-analyzer`, `rustfmt`, `protobuf`, and `ripgrep`.
- `cargo build`: compile the crate with default features.
- `cargo test --features easy-rpc`: run the focused unit tests for the easy RPC layer.
- `cargo test --all-features`: exercise the full feature graph.
- `cargo fmt -- --check`: verify standard Rust formatting.
- `cargo clippy --all-features -- -D warnings`: lint the crate across all features.
- `cargo run --example serial-av --features transport-serial-optimized,easy-rpc`: run the alert example against a connected device.

Do not assume a global Rust install. Prefer the flake so feature interactions are tested on the pinned toolchain.

## Coding Style & Naming Conventions
Follow idiomatic Rust defaults: 4-space indentation, `snake_case` for functions and modules, `PascalCase` for types, and `SCREAMING_SNAKE_CASE` for constants. Prefer borrowing over cloning, return `Result` instead of panicking on expected failures, and keep feature-gated APIs clearly grouped. Public library APIs should have concise `///` docs, especially when they depend on protocol-specific behavior such as `command_id` or `has_next`.

## Testing Guidelines
Add small unit tests next to the implementation with `#[cfg(test)]`. Focus tests on protocol mapping, feature-gated helpers, and regressions in error handling rather than hardware access. Hardware examples under `examples/` are useful for manual validation but should not be treated as automated coverage. Treat `cargo test --features easy-rpc`, `cargo test --all-features`, `cargo fmt -- --check`, and `cargo clippy --all-features -- -D warnings` as the minimum pre-PR checks.

## Commit & Pull Request Guidelines
The existing history uses short, imperative commit subjects. Keep commits narrowly scoped and describe the behavior change, not the implementation detail. Pull requests should summarize the affected feature flags, call out any API changes, and include manual validation notes when serial-device behavior is involved.
