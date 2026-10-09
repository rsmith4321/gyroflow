# Windows x64 native dependency notices (candidate v5)

Status: CANDIDATE for `resources/notices/native/windows-x64`. Not a legal review and
not a release approval (`public_release_approved: false`).

v5 adds the owner's exact installed-provider facts to the accepted v4 tree. Every v4
file is kept byte for byte except this README and the per-component PROVENANCE.json
files. Notice texts are verbatim copies of official upstream files at exact pins, or
of original installed provider files. `.gitattributes` keeps those bytes unchanged.

`MANIFEST.json` lists:
- every file with its size and SHA-256
- all 120 staged DLLs from the frozen stage inventory, each assigned to one component
  with the basis for that assignment
- every open gap with a class: `blocker`, `obligation` or `advisory`, plus the gaps
  v5 closed (`resolved` or `duplicate`)

`verify_native_notices.py` (delivered beside this candidate) checks integrity
separately from these gap classes.

## Components

| Directory | Component | Notice text here |
|---|---|---|
| `qt-6.7.3/` | Qt 6.7.3: 30 DLLs and 49 plugins | Module licences and 46 third-party attributions at tag v6.7.3 |
| `ffmpeg/` | FFmpeg n9.0.2 BtbN gpl-shared: 7 DLLs | FFmpeg, BtbN, 106 of 116 build components, 87 Rust crates and the toolchain runtimes |
| `opencv-4.14.0/` | OpenCV 4.14.0: 12 DLLs | The provider's `COPYRIGHT.txt`, identical to the repository copy |
| `ocio-2.4.2/` | OpenColorIO_2_4.dll | None here. The tracked `resources/color` notices are staged by `package_plus.py` |
| `rust-windows-x64-ocio/` | Gyroflow's Rust crates | None here. Include the tracked `resources/notices/rust/windows-x64-ocio` in the same `--licenses` input |
| `msvc-crt-14.51.36247.0/` | Microsoft C/C++ runtime: 10 DLLs | None. The installed `Redist.txt` is kept as provenance |
| `mdk-0.39.0-e89bc0b/` | MDK 0.39.0 git e89bc0b, plus its bundled `ffmpeg-9.dll` and `libass.dll` | The original installed SDK `README.md` |
| `d3dcompiler_47/` | D3Dcompiler_47.dll 6.3.9600.16384 | None. Windows SDK 10.0.26100.0 terms are kept as provenance only, because they cover a different copy |
| `zlib-for-z.dll/` | zlib 1.3.2#2 (z.dll) | The upstream v1.3.2 `LICENSE`, which is byte-identical to the installed `copyright` |
| `opencl/` | OpenCL loader and utilities: 3 DLLs | None supplied |
| `unattributed/` | opengl32sw.dll | None. Its provider is unknown |

**shaderc** is omitted. No `shaderc*.dll` is in the accepted stage.

## Limits

- Identities come from the owner's frozen stage inventory (`f7f930f4...`) and the
  facts supplied with it. The pinned FFmpeg archive and the official MDK archive
  are used for byte comparison only.
- A component's directory does not prove the shipped binaries were built from the
  cited sources. Each PROVENANCE.json says what was compared.
- Corresponding-source routes, acceptance of the MDK and Microsoft terms, and codec
  policy are decisions for root and the owner.
