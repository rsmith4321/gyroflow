# Basic drone grading expansion

Status: requested and planned 2026-10-07. Not yet implemented by the four-slider
Mac acceptance milestone. See COLOR-TONE-PROTOTYPE.md for that working build.

## Intended controls

- Keep existing brightness/contrast, highlights/shadows and their saved fields.
- Add exposure, saturation, warmth/temperature and tint for a simple grade.
- Keep manual LUT choice, preview comparison, double-click reset and reset-all.
- Avoid importing the full OCIO runtime or exposing a professional color-space
  configuration workflow for this basic version.

## Processing design gates

Use pinned OpenColorIO as an independent development reference for controls it
provides. Evaluate cached sampled channel curves and simple matrices to avoid
per-pixel expression parsing, shader recompilation and new runtime dependencies.
Temperature/tint must be documented as relative video color balance, not RAW
sensor white balance or measured Kelvin. Exposure must have a defined working
transfer function and processing order; do not label arbitrary multiplication
of log code values as physical exposure in stops. Do not assume a selected LUT
contains a reversible camera transform or identify the camera profile by filename.

Preserve old project rendering with neutral added controls. Keep floating point
working samples and avoid needless intermediate quantization. Verify any
headroom-preserving change separately from the old bounded video curve. Changes
to curve domain/clipping cannot silently alter existing saved projects. A LUT
may already clip/mix input values; original-file preservation does not establish
that no information was lost inside the working processing chain.

## Required evidence

Independent CPU references, production shader comparisons, moving stabilized
footage, neutral equivalence, alpha/stride/ten-bit input safety, finite parameter
validation, project/preset/queue save/reload, native Mac UI, and matched 4K timing.
Retain the accepted four-slider app while testing the expanded candidate. Record
exact source/build identities and push reviewed changes to GitHub.

## Product claims

Describe source preservation and reversible project adjustments. DJI O4 Pro
D-Log M is 10-bit log video, not camera RAW. Do not promise Lightroom-style RAW
recovery, unclipped HDR grading, lossless color export or acceleration that has
not been measured. Only list expanded controls as available after acceptance.
