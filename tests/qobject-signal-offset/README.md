# Manual Qt signal-offset reproducer

This standalone executable isolates a failure in the pinned Qt binding. It
does not depend on Gyroflow rendering, FFmpeg, MDK, stabilization or OCIO.
It is a manual diagnostic, **not** part of the ordinary passing test suite.

The exact dependency is AdrianEddy/qmetaobject-rs at
`ff1e23dcdd722a0c335bbd51f7dcfdb722384db2`. Its QObject derive calculates a
signal field offset by forming `&(*null).field`. On the observed arm64 Mac
debug build, connecting one signal aborts with `null reference produced`.
The baseline prints `BEFORE_CONNECT` and does not reach `PASS`.

Use a configured Qt 6.7.3 development environment, including its `QMAKE`,
headers, libraries and runtime search paths, then run:

```sh
cargo run --locked --offline --manifest-path tests/qobject-signal-offset/Cargo.toml
```

The observed baseline uses Rust's debug checks; an optimized run that happens
to finish does not demonstrate that forming a null reference is safe.

## Candidate, not integrated

`candidate.patch` changes only the generated offset calculation to
`std::mem::offset_of!`. Rust documents this macro as stable since 1.77;
Gyroflow's Rust 2024 edition already needs a newer toolchain. This does not
establish compatibility with every upstream qmetaobject consumer's older
toolchain. The patch remains a proposed dependency change.

To test it, copy the pinned upstream `qmetaobject_impl` crate into a private
directory and apply the patch there. Keep the cached/shared dependency source
unchanged. Add a **private** Cargo override for
`patch."https://github.com/AdrianEddy/qmetaobject-rs.git".qmetaobject_impl.path`
pointing to that copy, resolve a private lockfile, and run the same executable.
The expected result is one delivered callback, successful disconnect, no
second callback, and `PASS`. Do not edit the baseline lockfile or treat a
dependency override as a canonical application fix.

The observed private candidate passes that test with the same executable
source. A current OCIO app using that candidate and a settings-directory
test seam also completed the scoped PNG/EXR cases described in
[the integration notes](../../docs/OPENCOLORIO-INTEGRATION.md). The app's
production rendering sources were unchanged. The candidate has not passed
Windows or broader binding acceptance and has not been integrated.

The copied upstream MIT notice is retained in `UPSTREAM-LICENSE`. Source:
[pinned offset implementation](https://github.com/AdrianEddy/qmetaobject-rs/blob/ff1e23dcdd722a0c335bbd51f7dcfdb722384db2/qmetaobject_impl/src/qobject_impl.rs#L901),
[Rust field-offset macro](https://doc.rust-lang.org/std/mem/macro.offset_of.html).
