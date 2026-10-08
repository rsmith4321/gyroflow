# OpenColorIO basis and direct library integration

Reviewed 2026-10-07. This describes the current implementation and a possible
replacement; it does not claim the official runtime is integrated.

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
