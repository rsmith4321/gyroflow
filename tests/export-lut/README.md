# Export color regression tests

This standalone crate imports the application color modules directly.
It does not compile or run the native app.

```sh
cargo test --locked --manifest-path tests/export-lut/Cargo.toml
OCIO_ROOT=/path/to/pinned/ocio-2.4.2 cargo test --locked \
  --manifest-path tests/export-lut/Cargo.toml --features ocio-runtime
```

The `camera_format_matrix` tests use synthetic, uniform frames and independent
BT.601/709/2020 YCbCr equations. They cover limited/full range, 8/10-bit planar
and NV12/P010 formats, YUV/RGB output, alpha, out-of-range luma, single LUT
application, neutral controls, and accepted/rejected cube syntax. These
fixtures exercise the production `ExportLut` and `CubeLut` modules.

The unspecified-matrix cases characterize the existing FFmpeg BT.601 default;
they do not establish the correct matrix for any particular camera. Likewise,
these tests do not run `ffmpeg_video.rs`'s encoder-target conversion, MDK
preview, hardware encoding, queue/project persistence or real camera clips.
PNG/EXR and YUV targets' source-matrix consistency remains a separate review
item; a replicated converter is not a production-path regression test.

The reference tolerance is 1.5 codes at 8 bits and 4 codes at 10 bits to allow
conversion rounding. Alpha and P010 storage checks have separate exact
invariants. Passing synthetic fixtures is not a general HDR/RAW or camera
compatibility claim.

## Local acceptance, 2026-10-08

The 10 new tests passed on arm64 macOS with FFmpeg 9.0.1 in both the default
path and the pinned official OpenColorIO 2.4.2 feature path. They ran against
production color source from `39b092a7`; no rendering algorithm was changed
by this test addition.

A separate proposed FFmpeg float-input NaN guard is still a candidate pending
x86 and ownership/stride review; it is not included here.
