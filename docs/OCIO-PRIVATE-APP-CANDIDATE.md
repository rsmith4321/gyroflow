# Private official-runtime Mac app candidate

Checked 2026-10-08 on Apple M4 Max / macOS 27.0.1. The separately built and
staged application uses official OpenColorIO 2.4.2 for CPU color processing and
generated GPU preview. It is a private candidate, not the installed app or a
public download. The Cargo default and public release remain unchanged.

The earlier installed development build remains the one described in
[Mac acceptance](OCIO-MAC-ACCEPTANCE.md). The separately rebuilt dependency
inputs are described in [dependency acceptance](OCIO-DEPENDENCY-ACCEPTANCE.md).

## Build and stage identities

The frozen source snapshot is `a8e5dc1dcbfe361bffd623c0ed61199b5cc1fc83`;
its runtime implementation is `b9f744a3e09c38e5ca0a19f933739cbb28277df6`.
Intervening changes affect documentation and remove privileged Spotlight/XProtect
manipulation from the deployment recipe; the runtime color files are unchanged.
The private deploy build
uses `ocio-runtime,ffmpeg-next/static`, an arm64 target and macOS 11 deployment
metadata. It completed in 3m46s; that is build duration, not an export benchmark.

| Artifact | SHA-256 |
| --- | --- |
| Original deploy executable | `aaac3400ff01abea52cafe44d5198a2f0f871b46110fdc6660e022e3ebabe031` |
| Final staged executable | `63237f564646fdd26e34a170ea0ffcfb33b7edac65c242ec186c3be89c411ee2` |
| Final bundle path/file/symlink manifest | `9e203c3713d957495dfe3f3696258c4242ff5268c784606214480fdf39e3895f` |

The final bundle has 836 regular files, 157 symlinks and 146,870,829 regular-file
bytes. Its local ad hoc CDHash is
`cfc28a75b82b118ec9cdfeba77fbdf4de0711d6d`; deep/strict signature verification
passes. This is not a Developer ID signature or notarization acceptance.

Accepted private inputs are Qt 6.7.3 with matching ShaderTools and SVG,
OpenColorIO 2.4.2, OpenCV/contrib 4.14.0, source-built static FFmpeg with the
recorded codec dependencies, and the identified existing MDK 0.39 SDK. Fresh
bindings, 129 generated native objects and 71 compiled QML/JS units were
independently checked. Every inspected stage Mach-O slice is arm64 and records
macOS 11.0. That metadata does not establish execution on macOS 11.

The only private ffmpeg-sys-next overlay removes obsolete unconditional QTKit
and VideoDecodeAcceleration framework link requests. Their SDK stubs are absent
on the build host, and the accepted static archives import no symbols from them.
The overlay changes no FFmpeg headers or processing code. The private lockfile
changes only that crate's source identity; all other package records match the
frozen main lockfile.

The unchanged core build script fetched a missing lens-profile database through
its mutable `latest` URL despite Cargo `--offline`. The retained bytes match
official lens-profile release v41, asset 492091898, with SHA-256
`5b9136697b75ddf9cda20965f17e786b6c8530e3d59109f87505069602e7f676`.
Reproduction must reuse that retained digest-checked asset. Cargo offline mode
alone is not evidence that arbitrary build-script HTTP is disabled.

## Reviewed runtime closure

All 92 staged Mach-O images were independently audited. Their 1,220 hard
dependency edges resolve to 744 Apple/system and 476 bundled targets. No retained
search path expands outside the bundle or Apple system locations. Optional weak
loads remain separately recorded; unused external RAW runtimes are not supplied
or accepted by this result.

Stage-only corrections preserve the accepted input SDKs:

- Three unused external SQL drivers are retained outside the candidate bundle;
  SQLite, QtSql and QML local storage remain included.
- Seventeen flattened Qt Quick plugins receive corrected bundle-relative search
  paths. MDK codec aliases and wrapper paths resolve to the retained bundled
  libraries.
- Zero-byte source placeholders are retained outside code directories so strict
  signing can succeed.
- The matching SVG image plugin is explicitly included after native testing
  exposed its omission by deployment tooling. The logo and icons then display
  correctly, and actual load samples observe this plugin inside the bundle.

No installed app was replaced. Complete distribution notices/source obligations,
MDK provenance and rights, clean-machine loading and older-OS execution remain
separate release gates.

## Native preview and hardware exports

Three private CLI exports use the same DJI O4 ten-bit source copy, saved
stabilization, 45–49 second trim and explicit settings as the retained b9 cases:
neutral, LUT only, and LUT plus all eight controls. Each succeeds with 242 decoded
frames, 3840x2160, HEVC Main 10, 60000/1001 fps and BT.709 limited range.
VideoToolbox `allow_sw=0` is required; no initialized software-encoder marker or
failed completion appears. Sampled non-system libraries resolve inside the
candidate bundle. Single instrumented export durations are not matched timing
measurements or a performance acceptance.

The final signed bundle also completes a 4K grading export through the normal
native interface. All 242 decoded GUI frames equal the new CLI grading output
exactly, including packet timestamps. Their shared decoded SHA-256 is
`b978e185c3d7a92b0328f9c8af3c05fe2abc7dde02cc58ab09d79d4d0fa83212`.
Preview color switching changes the paused picture, and double-click exposure
resets it to zero. These actions were checked with normal pointer input.

An earlier startup observation briefly displayed an unloaded-video warning or
incomplete first frame. A later ordinary chooser load and seek displayed the
moving picture and enabled export; the earlier startup boundary has not been
classified as fixed. The original installed app/session was restored after the
private test, with its previous LUT and exact live slider values. The installed
executable, authored project, source media and LUT remain unchanged.

## Hold: color output versus the earlier b9 build

Independent full decoding of all 242 frames establishes:

| New candidate versus retained b9 OCIO | Mean absolute error in 10-bit codes | Maximum error |
| --- | ---: | ---: |
| Neutral | 0, exact | 0 |
| LUT only | 4.09322 | 159 |
| LUT plus all controls | 5.80621 | 237 |

Source/authored-project/LUT hashes, dimensions, range, matrix, timestamps and
keyframe positions match. Generated case projects differ only in output filename
and folder. The color integration source files are byte-identical. Local
positive/negative differences and nearly unchanged plane means do not support
assuming a simple global matrix/range shift. Compressed outputs alone do not
identify the cause.

A bounded old/new OCIO comparison uses the exact production LUT parser,
canonical cube and C++ bridge. For 32,768 RGB pixels, actual O4 LUT-only maximum
float difference is 5.96046448e-8; O4 with the exact export controls is
2.38418579e-7. Alpha is exact and all values are finite. These small sampled
differences do not reproduce the large decoded export difference or establish
full real-frame parity.

The earlier exact 131,072-float prefix comparison used a synthetic LUT plus
matrix. Rust29 uses synthetic fixtures. Metal82 includes actual O4 cases but
compares CPU/GPU within the same new prefix. None of those earlier checks was an
old/new actual-O4 comparison; the production bridge check above supplies that
missing coverage within its bounded sample.

A standalone synthetic conversion probe also found eight supported conversions
exact between retained vendor-static FFmpeg and the new source-static candidate.
The actual b9 app uses Homebrew dynamic FFmpeg; that first probe did not exercise
the b9 conversion runtime. A second bounded probe links against the actual
Homebrew 9.0.1 library family matching b9's declared imports, and observes those
libraries at runtime. Historical b9 loaded-library inodes are not reconstructed.
Its eight
supported default/legacy conversions also match the private static candidate
exactly, with unchanged synthetic inputs. Pure-C backend selection rejects the
four conversions in both builds; no fallback substitutes for those failures.
Neither standalone probe accepts real rendering frames or explains the color
output difference.

A subsequent real-video discriminator exports four frames per case through
software H.264 with explicit ten-bit CQP0. Actual bitstreams establish transform
bypass, zero luma/chroma quantizers and the requested pixel format; this is not
an assumption based on a quality-option name. Old/new neutral output is exact
across 49,766,400 decoded samples. With the O4 LUT and all eight controls,
256 samples differ by one code value, with mean absolute error
5.1440329218107e-6. Independent checks confirm every decoded value is within
0–1023 and the signed differences are evenly split. LUT contents and all
source/settings/project/binary/media preservation checks pass.

This lossless test changes the target to planar YUV420P10LE and shortens the trim
to 45,000–45,040 ms. Both changes can affect the processing route or adaptive
zoom. It establishes near agreement for this software branch, not equivalence
of the original VideoToolbox branch. Existing hardware-export differences
are smaller at keyframes and increase between them, which is compatible with
predictive encoding propagating small differences. That remains a hypothesis;
the original hardware encoder's input was not captured.

Two bounded debugger attempts produced no frame samples: the first stopped
before FFmpeg loaded and the second timed out before reaching application main.
Both diagnostic children were stopped, and preservation checks passed. This
capture route is discontinued. A separately rebuilt diagnostic capture is being
prepared to inspect the original hardware branch before encoder submission.
It is private test instrumentation, not a production change.

The new GUI/CLI and short software-lossless results do not lift the original
hardware-output hold. No production algorithm or conversion workaround is
justified by the results so far. The next discriminator is captured
processor-boundary samples from the original hardware export settings.

## Remaining acceptance

Color-output explanation, matched candidate timing, current Windows native
preview/export, complete notices/provenance, clean-machine installation,
older-OS execution and public signing/notarization remain open. The private
bundle must not be offered as a release download on this evidence.

Exact commands, hashes, build/source reviews, stage inventories, native logs,
input-preservation receipts and independent output comparisons are retained
under `_dev/ocio-runtime/portable-app-build/`. Camera media and vendor LUTs are
not redistributed.
