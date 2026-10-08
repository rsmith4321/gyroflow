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
