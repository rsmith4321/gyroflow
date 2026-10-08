# Build-time lens profile input tests

This standalone crate exercises the actual core build-script module without building or launching Gyroflow. The tests use generated gzip payloads and their own temporary directories. No original lens database, app settings, media or runtime is edited.

```sh
cargo test --locked --manifest-path tests/lens-input/Cargo.toml
```

Use `--offline` when the dependencies are already cached. Coverage includes pinned and supplied inputs, offline refusal, interrupted/truncated/corrupt gzip downloads, decompression bounds, concurrent destination preservation, unsupported hard-link publication and other writers' temporary files. Fresh publication needs a filesystem supporting hard links; unsupported filesystems fail closed. Existing databases are preserved.

This is build-input logic coverage; it does not verify the complete app build, network service, Windows deploy recipe or portable runtime.
