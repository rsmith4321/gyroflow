# OpenColorIO basis and direct library integration

Reviewed 2026-10-07. This describes the current implementation and a possible
replacement. The Cargo default and public renderer remain the accepted lightweight path;
an optional `ocio-runtime` development feature now exercises the official library.
[Mac development acceptance](OCIO-MAC-ACCEPTANCE.md) records matched hardware
timings and full-app preview/save/export checks.

## Current implementation

Gyroflow Plus has a lightweight color implementation based on OpenColorIO.
Highlights/Shadows use sampled curves generated with pinned OCIO 2.4.2.
Exposure, relative RGB balance and saturation use native math independently
tested against OCIO processors. Brightness/contrast retain the existing fork
implementation. Export applies the selected `.cube` LUT with FFmpeg `lut3d`;
preview uses the fork's matching tetrahedral LUT shader.

The [basic grading report](BASIC-GRADING-PLAN.md) records the order, clipping,
precision, performance and platform acceptance. This is a bounded video grade,
not the full OCIO runtime, an OCIO configuration workflow or camera RAW processing.

## Can we directly reuse the upstream code?

Yes. [OpenColorIO's BSD 3-clause license](https://github.com/AcademySoftwareFoundation/OpenColorIO/blob/v2.4.2/LICENSE)
permits redistribution and modification subject to its conditions. Retain
copyright, license and disclaimer text for reused source and binary distributions;
do not imply upstream endorsement. Existing attribution is in
[`resources/color/OCIO-LICENSE.txt`](../resources/color/OCIO-LICENSE.txt).

However, its internal processing files are not standalone drop-in modules:

- [`GradingPrimaryOpCPU.cpp`](https://github.com/AcademySoftwareFoundation/OpenColorIO/blob/v2.4.2/src/OpenColorIO/ops/gradingprimary/GradingPrimaryOpCPU.cpp)
  uses OCIO operation data, dynamic properties, computed parameters and internal
  math/SIMD helpers.
- [`GradingToneOpCPU.cpp`](https://github.com/AcademySoftwareFoundation/OpenColorIO/blob/v2.4.2/src/OpenColorIO/ops/gradingtone/GradingToneOpCPU.cpp)
  also depends on OCIO tone parameter preparation and processor state.

Copying these files and replacing their dependencies would create another
maintained fork of the algorithms. To reduce our custom algorithm code, prefer
a pinned official library and its
[supported CPU/GPU processor API](https://opencolorio.readthedocs.io/en/v2.4.2/api/processors.html).

## Integration boundaries

The CPU API can process float images with explicit layout and stride. The GPU
API can generate shader code, uniforms and textures; Gyroflow Plus must still
bind those resources through Qt's preview renderer. An integration would need:

1. A small C++/Rust bridge using the public API, with exceptions contained on
   the C++ side and validated frame layouts at the boundary.
2. A cached processor for the selected LUT and adjustment values. Avoid creating
   a processor per pixel or frame; each render worker needs appropriate processor
   ownership when dynamic values can change.
3. Matching processing order and slider semantics in CPU export and generated
   GPU preview, using Qt-compatible shaders on Metal, Direct3D and OpenGL.
4. Explicit conversion between decoded YUV formats and the processor's RGB
   working image, preserving color matrix/range, bit depth, alpha and timestamps.
5. Pinned builds and dependency packaging for Mac and Windows, retaining notices
   and source/build provenance.

Official OCIO processors reduce custom color algorithms. They do not decode
video, read gyro metadata, choose the correct camera log profile automatically,
or eliminate application integration work. Broader file support still depends
on the existing decoder and on correctly handling pixel formats and color
metadata. An OCIO configuration would be a separate feature with explicit
input/working/output color-space choices.

## Acceptance before replacing the current path

Prototype the official processor behind a separate development option. Compare
it with the accepted path using neutral/no-LUT, LUT-only and combined grades;
8/10-bit, full/limited range and supported RGB/YUV formats; odd widths/strides;
malformed or unsupported LUTs; and actual Mac/Windows preview and hardware
encoded exports. Measure matched real-clip timings and preview/export agreement.
Do not replace the working path based solely on library maturity or synthetic
CPU results. No production runtime change is made by this documentation update.

## Initial standalone runtime prototype: 2026-10-07

The [standalone probe](../tests/ocio-runtime/README.md) now builds against the
official OCIO 2.4.2 library and generates both CPU processors and Qt preview
shaders from one transform definition. No upstream processing source was edited.

- **144 CPU cases** cover the exact and cached-tone processors in packed and
  padded planar RGBA layouts. Maximum deviation from the independent reference
  was **4.77e-7**; alpha and planar padding were unchanged.
- **12 actual Metal cases** using generated Qt QSB shaders agree with the CPU
  result within **one RGB8 code**. HLSL SM5 compilation also passed; Windows
  execution has not been tested.
- On this Apple M4 Max, three repeats of five applications to a 3840x2160
  float image gave a median **0.514 s/frame** for the exact combined grade in
  planar layout. The same grade with a 4097-sample official tone curve evaluated
  by OCIO's `Lut1DTransform` took **0.0647 s/frame**, about eight times faster.
  These are single-threaded processor-only timings; file I/O, frame conversion,
  stabilization, encoding, and app scheduling are excluded. They are not a
  comparison with the complete existing export pipeline.
- The local OCIO dylib is about **6 MB**. It still links the development Mac's
  Imath library; this is not a portable package.

The cached path has no custom per-pixel curve or interpolation evaluator. OCIO
generates the curve from the exact parameters and evaluates it through its
own LUT processor; the GPU preview uses direct generated grading code. This
reduces maintained algorithm code while retaining a bounded approximation.
These measurements describe the initial standalone probe. The application bridge,
row concurrency, generated preview resource lifecycle and matched real-clip
checks were subsequently implemented and accepted on the development Mac as
recorded below. The tested official-runtime development build is installed on
that Mac; the Cargo default and public release still use the accepted lightweight
implementation pending Windows and portable package acceptance.

## Experimental app integration

The `ocio-runtime` Cargo feature links official OCIO 2.4.2 through a contained
C ABI. Export prepares one immutable LUT-first processor per grade snapshot,
then applies it to validated writable float RGB frames in disjoint row bands.
Decoded RGB/YUV conversion, stabilization and encoding continue through the
existing application and FFmpeg code. The feature no longer uses our custom
per-pixel adjustment loops or FFmpeg's LUT evaluator. The default build is
unchanged pending native preview and platform acceptance.

The bridge checks signed dimensions/strides, alignment, actual FFmpeg buffer
ownership/extents and RGB/alpha nonoverlap before creating descriptors, and
checks again after copy-on-write. Unsupported negative strides return an error.
It preserves alpha, padding, source buffers and frame metadata. C++ exceptions
never cross the ABI. A fresh OCIO configuration is used for every snapshot:
reusing one configuration across different sampled same-size tone LUTs can
reuse an earlier processor in OCIO 2.4.2; the dense fixture guards this lifecycle.
OCIO also retains parsed files globally by filename. Each canonical LUT snapshot
uses a private temporary path, so the bridge calls public `ClearAllCaches()` after
constructing its immutable exact/CPU processors, and on failed reads. This bounds
otherwise retained parsed LUT data during slider updates. The public API preserves
instance-specific processor data; native pixel/resource checks and retained-processor
concurrency exercise that lifetime separately.

Development build requires `OCIO_ROOT` pointing to the pinned install prefix;
`OCIO_LINK_NAME` may select a differently named Windows import library. Desktop
only. A compile-time and runtime version check both require 2.4.2. Qt ShaderTools
is an additional preview dependency when the feature is selected. The existing
[probe recipe](../tests/ocio-runtime/README.md) records source provenance and
local dependency limitations. This is not yet a portable release recipe.

Windows MSVC builds explicitly enable `/EHsc` for both the OCIO C ABI bridge
and the feature's Qt preview adapter, so their caught C++ errors unwind owned
objects and preview locks. Use a shared OCIO prefix with matching import
libraries and runtime DLLs. Existing Qt installs need ShaderTools checked
separately; the inherited default Windows deploy recipe does not enable this
experimental feature or stage its additional DLLs.

Current CPU acceptance:

- 29 Rust tests cover normal export, negative/malformed planes, allocation
  ownership, copy-on-write, alpha, odd widths/unequal strides, shared processor
  concurrency and GPU resource extraction.
- Fourteen sequential 8/10-bit full/limited YUV, matrix and size transitions
  match independent FFmpeg LUT-plus-affine references exactly in the measured
  cases; the test requires at most one output code.
- Forty independent randomized/ramp grade cases with and without the DJI O4
  LUT differ by at most 5.37e-7 in float RGB. Alpha remains exact.
- The independent C ABI fixture covers 800 concurrent calls, errors, resource
  bounds and LUT-first composition. Dense direct-versus-cached tone checks
  cover 98 settings and 65,577 RGB samples per setting, max error 5.37e-7.
- Actual stabilized DJI O4 footage passes all 481 frames at 1280x720 in deliberate
  lossless HEVC Main 10 exports. Neutral decoded frame hashes, every timestamp
  and stream properties match the accepted renderer exactly. Combined DJI LUT
  plus all eight adjustments matches an independent FFmpeg/OCIO reference within
  one ten-bit code across 664,934,400 samples. These lossless software-encoder
  exports prove pixel and stabilization preservation, not hardware speed.

Native preview resource acceptance:

- The exact production bridge and Qt 3D texture provider pass 82 float32 rendered
  cases on Metal / Apple M4 Max, max CPU/GPU RGB difference 2.39e-7. Cases include
  neutral, grading alone, identity/invert/nonlinear and DJI O4 LUTs with and
  without all eight adjustments, and out-of-range input values.
- Seventy native resource swaps cross the 64-source cache purge threshold.
  Public `QQuickWindow::releaseResources()` and hard scenegraph recreation retain
  the active source/LUT/grade result. Live asset leases retain needed files;
  each regenerated pack has a unique path to prevent stale-owner deletion.
- Native stale/current error delivery, unclaimed-token disposal, invalid texture
  size and a separate actual software-renderer rejection process pass.

OCIO's default GPU optimizer can remove a Range before a LUT because it assumes
every sampler axis clamps. Qt's ShaderEffect sampler exposes U/V clamp but uses
Repeat for W. The bridge disables only `OPTIMIZATION_COMP_RANGE` for GPU shader
generation to retain OCIO's explicit 0..1 input Range. CPU optimization is
unchanged; LUT sampling and grading code remain entirely generated by OCIO.
The tests caught a self-callback during QQuickItem base destruction; the adapter
now disconnects it before member teardown. QML clears prior errors before new
shader adoption so a synchronous shader failure remains visible.

Matched end-to-end timings and full-app Mac paused-video/slider/save/export checks
have passed on the development Mac; see [the acceptance report](OCIO-MAC-ACCEPTANCE.md).
Windows execution and portable dependency packaging remain gates. Shader compilation,
synthetic pixel acceptance or these CPU checks alone do not switch the default
engine or establish a public portable release.

The current development dependencies also need rebuilding for portable Mac
distribution: the local Imath and FFmpeg avcodec/avfilter/x265 libraries have a
macOS 26 minimum and QtShaderTools has a macOS 27 minimum, despite OCIO's macOS
11 and QtCore's macOS 14 minima. Merely
copying those Homebrew dependencies into a bundle does not establish support for
older systems. Use a matching Qt distribution and an explicit common deployment
target; audit each Mach-O slice, resolved dependency and runtime search path.

A separately built [private OCIO dependency candidate](OCIO-DEPENDENCY-ACCEPTANCE.md)
now removes the Homebrew Imath dependency and passes the production CPU and Metal
fixtures. Its compiled arm64 deployment metadata is macOS 11.0. This resolves
the OCIO dependency check; it does not yet establish a portable app or execution
on the declared minimum OS.

## Windows standalone runtime checks: 2026-10-08

Isolated laptop fixtures at source `26c5d828` passed with **OCIO 2.4.2** from the
Windows-owned private prefix and **MSVC 19.51**:

- The production C ABI bridge passed 800 concurrent CPU calls, 400 concurrent
  first-access GPU resource extractions, unequal-stride/guard/error contracts,
  and retained-processor checks across failed and repaired LUT reads.
- The Qt fixture executed on **D3D11 / NVIDIA GeForce RTX 5070 Ti Laptop GPU**.
  All **80** synthetic float32 comparisons passed; maximum component error was
  **2.384185791015625e-7**, below the existing `1e-5` gate. Cache swaps, resource
  recreation, ownership/error tokens and software-renderer rejection passed.
  The optional two DJI O4 LUT cases were not supplied in this run.

The Windows-owned evidence is under
`C:\Users\rsmit\.codex\GyroflowBuildTools\OcioWindowsNative-20261008`.
These standalone compiler commands explicitly use `/EHsc`; they do not establish
the application Cargo build's effective flags, real-video preview/exports, or a
portable DLL closure. Those checks remain pending, and the feature default and
installed/public app are unchanged.

### Supplied-LUT Windows follow-through

A separately brokered run on 2026-10-08 reused the retained `26c5d828` fixture
with the selected, transfer-verified cube. All **82 unique** float32 cases passed
on actual **D3D11 / NVIDIA GeForce RTX 5070 Ti Laptop GPU**, including:

| Case | Maximum absolute RGBA error |
| --- | --- |
| `o4_lut` | `5.960464477539063e-8` |
| `o4_lut_grade` | `1.7881393432617188e-7` |
| Entire suite | `2.384185791015625e-7` |

The existing strict `<1e-5` limit, finite checks and cache/recreation/ownership/error
checks were unchanged. The fixture compares every RGBA component but its original
inputs have alpha one; this adds no non-unit-alpha guarantee. One fixture process
ran, exited zero naturally in **13.672 seconds**, and its owned job had zero active
processes afterward. The protected stage, dependency prefix, prior evidence,
settings and retained Easy Eject preview remained unchanged.

Evidence is under
`C:\Users\rsmit\Documents\Codex\2026-10-08\gyroflow-plus-windows-validation\outputs\native-lut-run-20261008T230213`.
The result SHA256 is
`a82321b1742c4dc0c152f1e4635739dac289c39b772368cd235685b7977eb5e6`;
fixture executable SHA256 is
`7931907492847dbcc41e67cbec8aeed41345331370ac6dfea360cc2eb4855c4a`.
The supplied 33³ cube SHA256 is
`b18162854ab47702068410c33afa98a8cb6eef159fc5a04ce0e65fad0fd8947e`.
Its O4 filename and transfer identity identify the selected test input; its internal
Mavic 3 Pro D-Log M comment does not independently establish manufacturer provenance.

The five production color/adapter files are unchanged Git blobs from `26c5d828`
through `956d357b` (Windows archive bytes use CRLF). The current test source also
has the separately tested exception branch, which this retained fixture predates.
This run proves the standalone adapter and selected LUT comparison; it does not
prove a current-head application build, native MDK video preview/export parity,
encoded-video identity, clean-machine portability or a public runtime switch.

Reviewed source `e4db0995` adds the bounded shader-compilation exception recovery
case described in [the preview fixture](../tests/ocio-preview/README.md). The
case passed separately on the Mac with pinned Qt **6.7.3** and OCIO **2.4.2**:
after the caught failure while the cache mutex was owned, valid same-process
shader preparation and pending-token cleanup succeeded. Source and app settings
identities remained exact. The same committed case subsequently passed Windows
CTest in its own 30-second-bounded process. This validates recovery in the
standalone adapter fixture; application Cargo compiler flags and native app
acceptance remain separate checks.

## Windows application build: 2026-10-08

An immutable archive of reviewed source `9fab4b5860762634767aacef2a487d7021f01497`
built the complete x64 MSVC application using `cargo build --release --features
ocio-runtime --locked --offline --jobs 2`. Cargo completed successfully in
**8m 22s**, and the lockfile stayed unchanged. The executable is **46,889,984
bytes**, with SHA-256
`af3fda5e7e4dc11b9fcf43dd8246ceefe9cf182f9415ef9774837204d910d592`.

The Windows-owned packet is
`C:\Users\rsmit\.codex\GyroflowBuildTools\OcioApplication9fab-20261008`.
A private stage reuses the installed test app's dependencies and adds the
matching OCIO and Qt ShaderTools DLLs. This establishes full feature-app
compilation and staging, not real-video/native acceptance, clean-machine DLL
closure, complete distribution notices or a public package. Those checks remain
open; the feature default and installed/public app are unchanged.

The pristine feature executable subsequently completed three private CLI exports
of the same DJI clip: neutral, LUT only, and LUT with all eight adjustments.
Each output contained **857 frames** at **1280×720**, **HEVC Main 10** with
`yuv420p10le`, and **60000/1001** average frame rate, and passed a complete
error-checked decode. Read-only NVIDIA encoder-session observations matched the
owned application PID and output dimensions, with **9 / 15 / 16 samples** for
the three respective cases. The runner completed with exit zero; exact output
identities are retained in the packet's `cli-export-result.json`.

These checks establish completed real CLI exports and observed hardware encoder
sessions. They do not establish numerical preview/export color agreement, native
GUI acceptance, CPU-stabilization fallback absence or whole-export GPU execution.
Later saved-file checks confirmed **H.265 / GPU 0 / 1280×720** for every matching
application-PID encoder-session row. Each output has **857 six-decimal timestamps**;
maximum frame-grid error is **0.333334 µs** and maximum spacing error is
**0.666667 µs**, within the retained decimal-rounding bounds for **60000/1001**.
No stream time-base field was saved, so these readings do not establish an exact
rational timestamp contract. All three probes report limited range (`tv`) and
BT.709 matrix, transfer and primaries. The earlier Windows OCIO export-fixture
log in `OcioE4ExceptionExport-20261008` reports **29 passed / 0 failed**.

The required loaded DLL subset matches the private stage for all three exports.
An **81-image** exact-set/current-hash check belongs to a separate hidden dependency
probe; it does not establish full-app closure. Independent parsing of the complete
quoted compiler commands for the OCIO bridge and generated Qt preview C++ found
exactly one `/EHsc` argument in each, no conflicting exception option and no
response-file argument. Their command hashes match the retained build records.
Compiler environment variables such as `CL` and `_CL_` were not captured; this
establishes the recorded argument lists, not environment-wide effective flags.
The actual logged settings path is
`AppData/Local/Ryan Smith/Gyroflow Plus/settings.json`. No before baseline was
captured for that namespace, so preservation remains unverified. The Windows-owned
saved-read receipt is `Windows-OCIO-final-read-handoff-20261008.json`, SHA-256
`d7493e21bd3d667cae4489ac51add2b6a198e61205b1e5a407bc820196641da2`.
Native preview/control acceptance, numerical color agreement, full-app DLL closure
and the original old/new decoded-output hold remain open.

The subsequent native pass has its own prospective baseline: the actual Plus
settings file was absent before launch at **2026-10-08T16:31:29.3140902Z**. The
full **2,165,305,347-byte** DJI flight, chosen DJI LUT and authored Mac project
were copied directly over the existing authenticated file share, then copied
locally on Windows and independently hash-verified. A separate Windows-derived
project adapts paths and clears the Mac-only `-allow_sw 0` encoder option; the
authored project and source media stay unchanged. This baseline does not
retroactively establish preservation during the earlier CLI tests.

After the laptop restart and a fresh supported desktop-helper session, the native
observer reported reopening the LUT and all eight saved values, then completing
one GUI export. The retained file is **67,820,243 bytes**, SHA-256
`2fb159b29cf0f22f4ac29e9b7256b59e6bc7513ef8f53a20968b916cb24f9ac5`.
Its probe reports **3840×2160 HEVC Main 10**, `yuv420p10le`, limited range and
BT.709 matrix, transfer and primaries. A full decode exited zero. All **242**
integer best-effort timestamps equal `ordinal × 1001` in a `1/60000` time base;
duration is **242242 ticks / 4.037367 seconds**. NVIDIA recorded **11** matching
H.265 / 3840×2160 rows for the owned app PID, ten with positive FPS. The native
observer reported a success dialog; the owned app and temporary awake process
were subsequently reported absent. This establishes a completed native export
and hardware encoder activity, not numerical native preview/export parity.

Two verification commands remain failed and their receipts are retained. The
output check expected 240 frames, matching the duration-based progress estimate,
but the file contains 242. Source review traces the inclusive-start test,
end-after-submission test and final decoder drain to pre-color commit `77b49409`.
Both retained Mac reference and candidate exports also have 240 estimated versus
242 decoded frames. This is agreement with inherited behavior, not acceptance of
an exact four-second cutoff or proof for other clip/decoder boundary alignments.
The separate preservation check failed because the private derived project's
byte hash changed after native saving. Its LUT, eight controls, trim and export
fields remain present, but the complete semantic delta has not been established.
The test created the previously absent Plus settings file, and `windowWidth`
changed between the saved-project and completed-export reads. That file was left
present; exact settings equality/restoration is not established. Recorded checks
found no mismatches in 579 stage files, 577 stable files, three original fixtures
or the old settings file. These are recorded-file checks, not exact directory-set
or full-runtime-closure checks. The native packet is
`C:\Users\rsmit\.codex\GyroflowBuildTools\Native9fab-20261008`.

## Windows retained-stage static audit: 2026-10-08

A later read-only audit checks the retained `9fab4b58` application stage using
the corrected audit module from clean, pushed source
`7b099bfd8d9e557e1890755f02c05b184fe5fc1f`. The module SHA-256 is
`66ab0afb1e123ec462e2285b7149e1edabbadde61bca7ee45384e60a8ac6f26c`.
The actual pinned `pefile` parser and native Windows version API inspect all
**117 x64 PE images**; every parsed/native FileVersion comparison agrees and
the audit reports **zero errors**. The executable's OCIO and ShaderTools imports
are present. This checks import metadata and bundled symbol resolution; it does
not load the application or verify symbols provided by Windows system DLLs.

The original eight-error report remains unchanged. Seven rejections concern
five exact Windows in-box library names, now separately classified without
accepting staged system copies or missing VC140 redistributables. The remaining
failure used `14.51.36260.0` as its declared runtime floor, inferred from the
compiler's version. Read-only provenance collection establishes instead:

| Selected build input | Observed version |
| --- | --- |
| VS toolset directory and default redistributable directory | `14.51.36231` |
| `cl.exe` FileVersion, matching the retained compiler hash | `19.51.36260.0` |
| Selected `crtversion.h` version macros | `14.51.36244.0` |
| Selected official non-debug x64 CRT DLL FileVersions | `14.51.36247.0` |

All six staged CRT DLLs match the corresponding selected Visual Studio
`Microsoft.VC145.CRT` redistributable **byte for byte**, as well as by native
version. The new invocation declares `14.51.36247.0` from that selected official
redistributable evidence. It retains the same full four-component comparison;
the failed report's floor is not edited or silently waived. This evidence applies
to the selected recorded build inputs, not arbitrary toolsets or dependencies.

The bounded audit child completes naturally with exit zero in **4.344 seconds**.
Before/after checks preserve all 581 stage files, 13 OCIO-prefix files, the Plus
settings file, selected redist provenance and 92 prior evidence files. The owned
collection, fetch and audit processes are terminal; the separate Easy Eject
preview process is unchanged. This duration is an audit time, not an export
benchmark.

The private packet is
`C:\Users\rsmit\Documents\Codex\2026-10-08\gyroflow-plus-windows-validation\outputs\corrected-audit-7b099bfd-20261008`.
Its complete `audit-full.json` is 6,345,106 bytes, SHA-256
`8ecdfc57ad26b721e59e59f47c6a08c1b7cafc5458ec91c5bcb60e561d8ed2cb`;
`audit-handback.md` has SHA-256
`a2318989247ce27d5d7d5a435aa636b215957b8afb5bee5d057322a4d59e27c5`.

No application, runtime or settings were replaced. The audited executable
remains the recorded `9fab4b58` build, not a new build of the audit source commit.
Color/encoder/stabilization runtime files are unchanged between those source
commits; two update URLs and a build-time shared-OCIO-prefix check changed.
Current-head compilation, numerical Windows preview/export agreement, native
loading on a clean computer, complete package notices/source provenance and
public distribution remain separate gates. The feature default remains unchanged.

## Complete restored-input diagnostic: 2026-10-08

An isolated LUT-only diagnostic captured all 242 restored P010 inputs from each
of the retained Homebrew and portable/static dependency families. Both use the
official OCIO feature path. Each capture contains **6,021,734,400 bytes**; all
recorded active Y/UV plane identities match the respective retained v3 export.
The complete comparator verified raw-file and plane hashes before and after
comparison, zero low P010 bits, fixed LUT/parameter identities and every active
10-bit sample. Of **2,007,244,800 Y** and **1,003,622,400 UV** codes, **7,120 Y**
and **5,494 UV** differ, with maximum **one code**. The unchanged one-code gate
passed; source, original media, LUT and settings snapshots stayed equal.

The conditional replay then submitted the first family's captured inputs to one
fixed Homebrew HEVC hardware-required encoder. It reproduced the first coded
picture, but **241 of 242** coded pictures differed from that family's historical
export. Configuration (`hvcC`), timestamps, durations and keyframe ordinals
matched. The replay therefore stopped with a failed receipt before the second
family; protected snapshots remained equal and output bounds passed. The direct
P010 replay does not independently certify the historical app upload branch.
It has not established the cause of the compressed-output differences. No repeat,
grade replay, new decoded comparison, tolerance change or release/default switch
was performed. The original exact old/new decoded-output hold remains open.
The private diagnostic is retained under
`_dev/ocio-runtime/portable-app-build/full-restored-input-capture-v1`.

A subsequent comparison of existing files found that the fresh native old-family
capture export matches **all 242 historical VCL payload lists**, hvcC, timing and
key positions. Whole-file hashes differ, with non-VCL differences only at ordinal
zero; no SEI interpretation was made. All consumed input identities matched
before and after this bounded parser-only check. This distinguishes the matching
application output from the failed standalone replay and narrows the unresolved
gap to the consumer/application execution or session contract. It does not
establish encoder nondeterminism or close the old/new decoded-output hold.

## Actual application downstream sufficiency: 2026-10-08

The next isolated diagnostic used the actual old application consumer, with
captured pixels injected only after its ordinary color processing. The natural
old restored pixels and retained frame properties were checked before each
injection; writability, metadata preservation, exact active-plane hashes and
explicit completion of all 242 frames were required. Color, stabilization,
encoder and queue logic remained otherwise unchanged. A failed first build
(a diagnostic `usize`/`u64` comparison) is retained separately; the repaired
private build completed successfully before either native case ran.

The old-pixel control reproduced **242/242 historical old VCL payload lists**,
codec configuration, timing and key positions. Only after that control passed,
the same binary consumed the captured new pixels and reproduced **242/242
historical new VCL payload lists**, with the same configuration/timing/key gates.
Both cases completed the hardware-required HEVC/P010 path, with all protected
source, settings, project, LUT and input snapshots preserved. Non-VCL differences
were confined to ordinal zero; no SEI interpretation was made. Native execution
took 68.58 s for the control and 55.13 s for the new-pixel case; these diagnostic
runs include validation and injection and are not performance benchmarks.

For this LUT-only clip, the captured new restored pixels alone are sufficient
to explain the historical new coded-picture family through the old application
consumer. Together with the full restored-input one-code result above, this
narrows the changed export to the small input-pixel differences rather than
requiring a different downstream application or encoder to reproduce it. It
does not establish general encoder determinism, exact old/new decoded equality,
native preview agreement, Windows parity or release readiness. The original
exact decoded-output hold remains open; no acceptance tolerance, default or
public release was changed.

The private packet is
`_dev/ocio-runtime/portable-app-build/application-restored-input-replay-v2`.
Terminal control receipt SHA-256:
`4e023fc332ce275c18b9f7521486e472685cdc9746c4193c9d1a24394f1b4f20`;
terminal new-pixel receipt SHA-256:
`bcfa7d55449f8583b15680349c50375864d00c2876aa804b25c8ff6615d9401a`.

## Native effect one-frame agreement: 2026-10-08

A private full application build from `479419e9` tested the existing OCIO
ShaderEffect on Qt 6.7.3 / Metal. The diagnostic driver initially waited on a
QML-added `loaded` property unavailable through the native MDKVideoItem
metaobject. A separate private revision uses the native video metadata to
position the declared frame. This repair changes only the diagnostic driver;
the application color processor, shader, stabilization and encoder remain
unchanged.

The metadata preflight settled at frame **2777**, timestamp **46329.616 ms**,
with the selected DJI O4 LUT and all eight controls matching their frozen
processor values. One bounded capture then read the actual native video layer
before and after Qt's offscreen grab of the existing effect. Both inputs were
byte-identical, the refresh probe returned false, and the synchronous bracket
recorded zero notifications. The output and input dimensions were **836×471**;
the observed image was RGBA8, with opaque alpha and no image color space.

The unchanged production OCIO CPU bridge evaluated the captured input once,
using the same LUT and controls. Row mapping, rounding and the fixed outer
one-pixel border were declared before capture. The comparison passed the
unchanged one-code gate: all **1,173,438 interior RGB components** differ by at
most **one code**, with zero larger differences. The full image has the same
one-code maximum; its **7,830 border components** match exactly. CPU output is
finite, with no clipped components in this case. Original media, LUT, retained
project fixture, settings and installed application binaries passed the retained
preservation checks.

This establishes one-frame agreement between the actual native layer input,
the existing effect's offscreen output and the official CPU processor. The
original visible-window numerical and exact old/new decoded-output holds
remain open, as do Windows runtime closure and public packaging gates. It
does not change the installed/default runtime or establish release readiness.

The private packet is
`_dev/ocio-runtime/portable-app-build/mdk-native-effect-capture-v6-native-readiness`.
Capture receipt SHA-256:
`2ebffefc727f24bdbc1b712a8a28b83516b15fb8b36dcd5e5df8ba75f17e0bb1`;
comparison statistics SHA-256:
`a46633a2527de0746b40a01b22d46f62ec056d3455e83b7b5047099679744efb`.
