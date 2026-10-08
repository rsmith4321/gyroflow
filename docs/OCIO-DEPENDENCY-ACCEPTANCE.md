# Private OpenColorIO dependency acceptance

Verified 2026-10-08 on Apple M4 Max / macOS 27.0.1. This is an official
OpenColorIO **2.4.2 dependency candidate**, independently reviewed and exercised
with production fixtures. It is not a complete portable app or a public download.
The installed development app still uses the OCIO prefix recorded in
[Mac app acceptance](OCIO-MAC-ACCEPTANCE.md); this new prefix has not replaced it.

## Compiled runtime closure

The shared OCIO library includes private static Imath, yaml-cpp, pystring and
minizip-ng, and uses Apple's system Expat/zlib. OCIO applications, Python, Java,
documentation, upstream tests, OpenFX and Nuke were disabled.

| Property | Verified result |
| --- | --- |
| Library | `libOpenColorIO.2.4.2.dylib` |
| Bytes | 6,365,128 |
| SHA-256 | `b1939e6d021afebdabdd22c6748bebc89c73866f51fde3e773d229911f4911f3` |
| Architecture | arm64 |
| Recorded minimum macOS | 11.0, including inspected private static archive members |
| Build SDK | macOS 27.0 / Apple clang 21 |
| Install ID | `@rpath/libOpenColorIO.2.4.dylib` |
| Runtime search path | `@loader_path` only |
| Non-Apple dynamic dependencies | None |

Actual dynamic loads are system Expat, zlib, libc++, libSystem, ColorSync,
CoreFoundation, CoreGraphics and IOKit. Homebrew CMake was a build tool; no
Homebrew library appears in this runtime's load commands. Recorded deployment
metadata does not establish execution on macOS 11. Older-OS execution remains
an acceptance gate.

## Upstream source and SIMD

Independent review compared all 1,938 OCIO files and 337 Imath files with their
official archives: no differences or extra files. The external dependency source
archives also match the compiled private sources. No color algorithm was edited.

An upstream CMake compiler check split an include path containing spaces into
separate shell arguments and disabled SSE2NEON in the earlier development build.
A private override changes only the check's include-directory argument:

```cmake
# Old try_compile argument:
COMPILE_DEFINITIONS "-I${sse2neon_INCLUDE_DIR}"
# Private build override:
CMAKE_FLAGS "-DINCLUDE_DIRECTORIES:STRING=${sse2neon_INCLUDE_DIR}"
```

The intrinsic test source is unchanged. Actual compiler/linker execution succeeds;
both ARM NEON and SSE2NEON checks pass, and the generated arm64 configuration
sets `OCIO_USE_SSE2NEON` to 1. No feature result is forced.

Top-level discovery excludes `/opt/homebrew` and `/usr/local`; the recorded
external subprojects exclude `/opt/homebrew`. Actual link inputs were verified
as private archives or SDK libraries. Future build recipes should propagate
both exclusions into every subproject and recheck the complete inputs.

## Production fixture acceptance

Root independently ran the existing fixtures against this exact stable prefix:

- **29 production Rust tests passed**, including owned-frame validation,
  copy-on-write, unequal strides, alpha/padding preservation, YUV conversion,
  processor concurrency and generated resource extraction.
- **82 actual Metal float32 comparisons passed**, with maximum CPU/GPU difference
  **2.384185791015625e-7** against the 1e-5 bound. These use Qt 6.11.2 and the exact
  production bridge/preview adapter. Cache cleanup, scenegraph recreation,
  ownership/error delivery and separate software-renderer rejection passed.
- A separate synthetic official LUT3D-plus-matrix probe compared **131,072 float
  values** with the previous OCIO prefix: observed maximum difference **0.0**.
  It separately checked populated 1D/3D resources and generated shader text.

In three processor-only measurements, the synthetic probe's median throughput
was 295.207 MP/s for this private build versus 215.113 MP/s for the previous
development build, a ratio of 1.3723. Each run applies 2,000 rounds to 32,768 RGBA
pixels; copies and input preparation are outside the interval. This comparison
covers two complete dependency builds and does not isolate SIMD from dependency
version/linkage differences. It is not a video-export or universal speed claim.

Private logs and machine-readable receipts are retained under
`_dev/ocio-runtime/portable-prefix/` and `portable-validation/`. No camera media
or vendor LUT is redistributed. These new fixture results do not substitute for
the previously recorded full-app/stabilized-video checks or a new app candidate
linked against this prefix.

## Source pins and notices

| Dependency | Version | Exact upstream commit |
| --- | --- | --- |
| OpenColorIO | 2.4.2 | `6918fad3f5d22ac3ef2397c754bf4268c2b58dd0` |
| Imath | 3.1.12 | `c0396a055a01bc537d32f435aee11a9b7ed6f0b5` |
| yaml-cpp | 0.7.0 | `0579ae3d976091d7d664aa9d2527e0d0cff25763` |
| pystring | 1.1.3 | `c2de99deb4f0bd13751f8436400b5e8662301769` |
| minizip-ng | 3.0.7 | `241428886216f0f0efd6926efcaaaa13794e51bd` |
| SSE2NEON | OCIO's upstream pin | `227cc413fb2d50b2a10073087be96b59d5364aea` |

The official codeload OCIO archive SHA-256 is
`2d8f2c47c40476d6e8cea9d878f6601d04f6d5642b47018eaafa9e9f833f3690`;
Imath's is `8a1bc258f3149b5729c2f4f8ffd337c0e57f09096e4ba9784329f40c4a9035da`.
The private provenance receipts retain every other archive/content hash, SDK
header/stub hash, exact configuration, command and resolved library input.

The notice collection includes all direct static dependencies and OCIO's
embedded SampleICC/xxHash copyright/license headers. OCIO's root BSD notice
alone is insufficient for redistributing those embedded components. Apple's
Expat/zlib are system dependencies; runtime versions come from the user's OS.
The SDK/current host report Expat 2.7.4 and zlib 1.2.12. No independent security
patch conclusion is inferred from those version strings.

## Remaining app and release gates

### Matching Qt 6.7.3 preview compatibility

A separate official Qt 6.7.3 Mac SDK candidate now passes the same **82 actual
Metal comparisons** and separate software-renderer rejection with this OCIO
prefix; maximum CPU/GPU difference remains **2.384185791015625e-7**. Production
source compiled unchanged against the matching Core/Gui/Quick/Qml/ShaderTools
modules and private headers. This checks the inherited Apple Silicon Qt version;
Intel's separate Qt 6.4.3 recipe remains untested and unchanged.

The three vendor archives were checked against fresh official checksum sidecars
and additionally SHA-256 hashed. Matching official source archives and 151
notice/version files are preserved. All 124 inspected runtime arm64 slices and
the linked QtQmlBuiltins static members record a macOS 11.0 minimum. The required
ten-file framework/Cocoa closure totals 67,805,808 bytes and resolves within the
private Qt SDK or Apple system libraries. The entire SDK also includes unused
SQL drivers with external iODBC, Postgres.app and unresolved Mimer loads; those
remain intact and are excluded from this narrow closure claim. Every plugin
actually shipped by a future app must pass the complete stage audit.

The private dependency inventory originally discarded the first dependency of
bundle plugins by assuming it was a dylib ID. Independent review caught this;
the corrected inventory parses explicit Mach-O IDs and all load commands and
matches independent inspection of all 124 files with zero differences.

On SDK 27, the old Qt CMake OpenGL target adds a direct AGL link requirement
whose SDK stub is absent. A private configuration omits only that redundant
consumer link entry for the Metal harness, which calls no AGL API. Official
QtGui still imports Apple's loadable AGL runtime. SDK binaries and production
source are unchanged. This workaround is scoped to the fixture and is not yet
accepted for a complete application build.

Private reproducibility, archive hashes, notices and corrected inventory are
retained under `_dev/ocio-runtime/portable-qt/`. This is current-host preview
compatibility and a dependency candidate, not old-OS execution or a portable app.

### Full application

Use this prefix only for a separately staged candidate and preserve the `.2.4`
library-name symlink and complete notices. A matching Qt distribution including
ShaderTools, compatible FFmpeg/codecs, OpenCV, MDK/plugins and all other runtime
components still need their own architecture/minimum-OS and closure checks.
Bundle-relative app search paths, full app preview/export acceptance, execution
on the declared minimum OS, Windows, signing/notarization and clean-machine
installation remain open. Cargo defaults, public releases and website engine
claims are unchanged by this dependency acceptance.
