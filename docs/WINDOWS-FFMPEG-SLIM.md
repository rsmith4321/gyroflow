# Slim Windows FFmpeg

Gyroflow+ switched the Windows FFmpeg from avbuild's GPL-lite bundle to BtbN's
full `gpl-shared` bundle in `62318d48`, because the export LUT path needs
`lut3d` (and the export tests' reference graph needs `geq`). That bundle also
compiles in about 80 external libraries the app never uses (xvid, libass and
its font stack, librsvg, Blu-ray/DVD, SRT, RIST, ZeroMQ, SSH, SDL, VapourSynth,
frei0r, ...). Each one adds licence texts and corresponding source that a
release has to carry.

The slim bundle is built from the same pins with only what the app uses.

## Pins

`_scripts/ffmpeg-windows/slim.pin`:

- BtbN FFmpeg-Builds `9acad4a9ef15` (the scripts behind the current bundle).
- FFmpeg `46d8f462ee` (n9.0.2-22, the same source as the current bundle).
- BtbN's `base` and `base-win64`/`base-winarm64` toolchain images by digest.
  They were built on 2026-10-04, before the 2026-10-06 autobuild the current
  bundle came from. BtbN deletes untagged images, so if a digest disappears
  the toolchain has to be rebuilt from `images/base-*` at the same commit.

## Kept components

| Stage | Why |
|---|---|
| zlib | PNG and EXR encode/decode |
| x264, x265 | Software H.264/HEVC export; the app treats GPL FFmpeg as present only when both exist |
| rav1e, aom (+ vmaf, used by aom's `tune=vmaf`), SVT-AV1 | The three software AV1 encoders the app offers |
| dav1d | AV1 decoding |
| nv-codec-headers, AMF, oneVPL, Vulkan | NVENC, AMF, QSV and Vulkan encoders and hardware decoding |
| mingw-w64 runtime | Toolchain runtime |

Everything else in FFmpeg the app uses is FFmpeg's own code: ProRes, DNxHD,
CineForm, FFV1, PNG, EXR, AAC, ALAC and PCM encoders, the camera decoders,
the MP4/MOV/MKV/MXF/image muxers, `lut3d`, `geq`, `scale`, `colorspace`, and
D3D11VA, D3D12VA, DXVA2 and Media Foundation, which come from the mingw-w64
headers.

aom and oneVPL are not built for Windows ARM64 by BtbN, in either bundle.

## Build and checks

`.github/workflows/windows-ffmpeg-slim.yml` trims the BtbN checkout with
`_scripts/ffmpeg-windows/slim-btbn.sh`, builds with BtbN's own scripts on the
pinned toolchain images, then on native Windows x64 and ARM64 runners:

1. runs `tests/export-lut/check_windows_ffmpeg.py --app-coverage`, which adds
   every encoder, decoder, muxer, demuxer, filter and hardware device type the
   Windows app can select to the existing build gate;
2. runs the same coverage check on the full bundle as a reference;
3. encodes and decodes every software codec the app offers, plus the
   `lut3d`/`geq` graph (`_scripts/ffmpeg-windows/smoke_encode.py`);
4. records exactly which encoders, decoders, formats, filters, protocols and
   configure flags the slim bundle drops compared with the full one.

Hardware encoders are checked for presence only; hosted runners have no GPUs.

## Status

Candidate. `_scripts/common.just` switches to the slim archive only after the
checks above pass, and the Windows native notices are regenerated for the
smaller component set at the same time.
