# Post-LUT video tone prototype

Gyroflow Plus adds neutral-by-default Highlights/Shadows (-50% to +50%) after
the selected LUT and existing brightness/contrast. Positive values lift the
named range; negative values darken it. This is a bounded video curve operating
on each RGB channel. It is not RAW highlight recovery, an exposure-in-stops
control, HDR mastering, or automatic color management. Select a LUT that turns
the recording into viewing-ready video when appropriate; arbitrary LUTs carry
no inferred transfer-function/working-space guarantees. No per-frame analysis
or automatic normalization is used.

## Architecture decision

[OpenColorIO 2.4.2 grading transforms](https://opencolorio.readthedocs.io/en/v2.4.2/api/grading_transforms.html)
offer tone-range controls with video, linear and log styles. Primary grading
also supplies style-specific exposure, contrast, gain/gamma/lift and saturation.
Those controls are not interchangeable across encodings, so this prototype uses
only the explicit video-style master Highlights/Shadows with default ranges.

| Approach | Tradeoff / decision |
| --- | --- |
| Native OCIO CPU and generated GPU processors | Most extensible and suitable for a future explicit color-managed pipeline. Requires a new C++ ABI bridge, pinned library and platform dependency packaging, plus a Qt integration for generated shaders/textures. Deferred for the bounded two-control prototype. |
| Shared cached OCIO-derived curve | Chosen prototype: generate reference curves with pinned OCIO, interpolate settings once, compose in OCIO order, and share the exact float curve with native export and Qt. Adds no production dependency or per-pixel interpreter. |
| New hand-designed curve or FFmpeg geq expression | Would invent different control semantics or reintroduce the known interpreter bottleneck. Not chosen. |

`generate_tone_tables.py` samples the independently installed OCIO 2.4.2 CPU
processor at 4097 inputs, for each integer percent -50..50 and each control.
The table provenance, layout and SHA256 are checked in beside the binary data.
Fractional percentages interpolate adjacent parameter curves. Each change
composes **Highlights then Shadows**, matching OCIO, into a 4097-entry float
curve; each sample uses one linear lookup. Preview packs exact IEEE float bytes
into RGB8 texels to avoid half-float quantization and Qt alpha premultiplication.
Both paths use the same table. The bounded table is an approximation of OCIO,
not its full runtime or configurable color-management system.

Processing order: stabilization → float RGB → selected tetrahedral LUT →
existing brightness/contrast and [0,1] clipping → video tone curve → original
encoder pixel format/matrix/range. Both new settings zero bypass the tone stage
completely and keep the previous fast paths. Original recordings are unchanged.
Projects, selected presets and render queues store normalized `shadows` and
`highlights` fields under `output`; absent fields default to zero. Existing LUT
and adjustment export markers are retained; a new explicit video-tone marker
records the applied controls. Older Gyroflow builds can ignore these new fields
and therefore cannot be expected to reproduce nonzero tone settings.

## Current Mac evidence (2026-10-07)

- 16 production parser/filter/curve tests pass, retaining all 13 native/geq
  tests and adding curve bounds, monotonicity, endpoints, neutral bypass and
  invalid settings. No production dependency added.
- Independent OCIO CPU comparison: 28 control combinations, dense ramps,
  fractional parameters, extremes, out-of-range clipping and random RGB;
  maximum float error `1.4901161193847656e-6`. Odd-width/padded shared input,
  alpha, dimensions and timestamps are preserved across repeated filtering.
- Production Qt QSB rendered on Metal matches independent OCIO reference
  exactly in four RGB8 display cases (including tone extremes and fractional
  settings). QSB includes GLSL, HLSL SM5 and Metal outputs, serialization v6.
  Baking HLSL is not Windows runtime proof.
- Newly rendered stabilized eight-second 720p moving-flight exports: all 481
  frames fully decode, timestamps and stream/color properties agree. Against
  independent FFmpeg tetrahedral LUT/geq + OCIO CPU, max error is one ten-bit
  code; 11,771 of 664,934,400 samples differ. This is expected approximation and
  quantization, not bit-identical tone equivalence.
- Three one-second 4K HEVC GPU-option exports fully decode to 62 ten-bit BT.709
  frames. Individual startup-inclusive elapsed times: neutral 1.874s, existing
  LUT/brightness/contrast 3.272s, plus tone 3.392s. Concurrent system work and
  short duration limit these measurements; no full-flight speed claim.

Private source footage, LUTs, generated exports and logs are outside Git under
`_dev/color-tone-prototype/`. Test harnesses and table generator are public.
Native installed UI/persistence, combined LUT/tone GPU comparison, old neutral
project equivalence and original hash recheck are recorded separately as they
are completed. Windows full-app validation and portable public releases remain
open; see [distribution gates](PLUS-DISTRIBUTION.md).
