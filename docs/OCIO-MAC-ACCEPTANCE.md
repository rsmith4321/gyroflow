# Official OpenColorIO Mac development acceptance

Tested 2026-10-07 on Apple M4 Max / macOS 27, official OCIO 2.4.2,
Qt 6.11.2, FFmpeg 9.0.1. Implementation under test is
`b9f744a3e09c38e5ca0a19f933739cbb28277df6` with `ocio-runtime` enabled.
This records development-runtime acceptance on one Mac. It does not approve a
portable public release or establish Windows execution.

## Matched hardware export timing

A byte-identical private SSD copy of an original DJI O4 Pro 4K ten-bit log clip
retained all embedded motion data. Both engines used the same saved stabilization,
45–49 second trim, HEVC GPU encoding, bitrate, dimensions and explicit color values.
All eight controls were explicitly zeroed for neutral/LUT-only and explicitly set
for the combined case. One untimed warmup per engine/condition preceded three
matched pairs, alternating engine order. Wall time includes application startup,
loading, stabilization, color conversion/processing and encoding; independent full
output decoding/validation happens outside that interval.

| Condition | Accepted engine median | Official OCIO median | Geometric mean paired wall-time change |
| --- | ---: | ---: | ---: |
| Neutral, no LUT | 4.609 s | 4.764 s | +2.2% |
| DJI O4 LUT only | 9.824 s | 10.296 s | +5.2% |
| LUT plus all eight controls | 11.609 s | 11.681 s | +5.4% |

The paired column is the appropriate comparison; the ratio of separate medians
obscures engine-order variation. Neutral uses the existing bypass, so its small
variation is not evidence of a changed color operation. Individual paired changes
ranged from -2.8% to +10.9%. Within-engine max/min spread stayed below 12.4%.
No competing compiler, busy backup, or Gyroflow process was detected. Brief ordinary
Codex/Git/search/PHP activity remained; these are bounded measurements, not a
universal performance promise.

All 24 outputs (six warmups, eighteen measured exports) completed with 242 decoded
frames, 3840x2160, HEVC Main 10 / yuv420p10le, 60000/1001 fps, BT.709 limited range.
VideoToolbox `allow_sw=0` was required. The app marks initialized software encoders
with `uses_cpu` and failed CLI completion; both were absent and successful completion
was required. Original video, SSD copy, saved source project and selected LUT hashes
were unchanged after the run.

Executable identities:

- Accepted engine: `2768edc4`, SHA-256 `d8812e9650a9387097626b304c59eb5797af02714cf3628c08d556adc8f84311`.
- Official feature executable: `b9f744a3`, SHA-256 `c598a3d15ceae1866e2d9818617abc17f265bae0c1f28c40e73d2cf49e8070e6`.
- Staged, ad-hoc signed official app executable: SHA-256 `e03e708b6a2746b59454e3e694f129ab3a1f3ff8602ee5895144e2d836f8a40c`.

Private per-run commands, load samples, stream checks, hashes and result receipts
remain under `_dev/ocio-runtime/clean-hardware-b9/20261008T014523Z/`; no camera media
or vendor LUT is redistributed.

## Full native app checks

The same staged feature app loaded the saved DJI project through the ordinary
native file chooser. A separate private project/output was used for mutations.

- Seventy distinct exposure grades while the original video was paused crossed
  the 64-source Qt shader-cache cleanup threshold. Returning to the starting grade
  produced an exactly identical 1900x1060 screenshot region: zero changed RGB8
  components. This checks the actual MDK video source, stabilizer, Qt layer and
  production resource adapter together.
- Preview colors off changed the image; turning it back on restored that exact
  same region. No export-blocking preview error appeared during the swaps.
- Double-click exposure reset it to zero. Reset adjustments cleared all eight
  controls and retained the selected LUT.
- All eight nonzero controls saved to a private .gyroflow project and reloaded
  through the native chooser with the same values and LUT.
- A native GUI export completed with 242 decoded frames, 1280x720, HEVC Main 10,
  yuv420p10le, 60000/1001 fps, BT.709 limited range. Its output metadata recorded
  the selected LUT and every nonzero color setting. This short 720p GUI export
  checks the app workflow; the matched timing above uses 4K.

The independent native harness additionally passed 82 float32 Metal cases, maximum
CPU/GPU difference 2.384185791015625e-7, including live resource eviction, scenegraph
recreation and software-renderer rejection. The CPU and stabilized moving-frame
references are recorded in [the integration report](OPENCOLORIO-INTEGRATION.md).

## Remaining gates

The Cargo default and public release remain the accepted lightweight implementation.
The official runtime is an opt-in development build with real official CPU processing
and generated GPU preview code; the application still supplies validated integration,
parameter mapping, decoding, stabilization, RGB/YUV conversion and encoding.

Current Windows native execution/install, portable dependency closure, honest minimum
OS targets, dependency notices/source provenance, signing/notarization and clean-machine
execution are still open. The development bundle depends on Homebrew and the local
OCIO prefix; it must not be offered as a portable download. Packaging validation
rejects that closure for public use. The inherited DMG retry loop no longer disables
Spotlight globally or terminates XProtect; no machine settings were changed during
these checks.
