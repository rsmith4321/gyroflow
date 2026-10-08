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
the retained hardware exports did not record their encoder input.

Two bounded debugger attempts produced no frame samples: the first stopped
before FFmpeg loaded and the second timed out before reaching application main.
Both diagnostic children were stopped, and preservation checks passed. This
debugger route is discontinued.

A subsequent private source diagnostic preserves the original 45–49 second
trim, 4K HEVC settings and stabilization. Two rebuilt variants hold source,
Qt/OpenCV/MDK and static codec inputs constant while selecting the previous
Homebrew FFmpeg/OCIO family or the private static FFmpeg/OCIO family. Four
sequential runs capture one frame at each color boundary, then deliberately
stop before encoder initialization or submission. This is test instrumentation,
not a production change or recreation of the retained b9 executable.

Actual loader logs observe the intended OCIO prefix in each variant. The new
executable contains static application FFmpeg definitions but also loads the
Homebrew FFmpeg images later during MDK initialization. These isolated build
targets are not the relocated app bundle, and this diagnostic is not evidence
of a Homebrew-free runtime. Loaded-image lists alone do not establish ownership
of every FFmpeg call.

Both cases capture the same PTS, P010LE input/output, GBRPF32LE intermediate,
color metadata and strides. The YUV boundaries record BT.709 limited range;
the float intermediates record RGB matrix and unspecified range. The Rayon
pool records 16 threads with the production OCIO worker limit of eight. All
input/settings/source/prefix preservation checks pass. Across the complete
first frame:

| Boundary | LUT only | LUT plus all controls |
| --- | --- | --- |
| Stabilized P010 input | Exact bytes | Exact bytes |
| Float input to OCIO | Exact bytes | Exact bytes |
| Float output from OCIO, maximum absolute difference | 1.1920928955078125e-7 | 2.980232238769531e-7 |
| Restored P010, changed 10-bit samples | 59 of 12,441,600 | 79 of 12,441,600 |
| Restored P010, maximum difference | One code value | One code value |

All captured float values are finite. Restored P010 comparisons use the ten
significant bits; their six unused low bits are zero. Input P010 low bits are
often nonzero, and the exact-byte input comparison includes them. The small
restored differences are nearly evenly split in sign. Capturing these inputs
alone does not explain the larger decoded hardware-export differences; the
controlled sensitivity test below supplies first-frame reproduction.

The new GUI/CLI and short software-lossless results do not lift the original
hardware-output hold. No production algorithm or conversion workaround is
justified by the results so far. The captured boundaries establish near
agreement for one rebuilt frame; they do not establish all-frame equality,
encoder determinism, or a cause for the retained outputs. A controlled encoder
comparison with identical input supplies the next bounded result below.

## Identical-input encoder discriminator

Four fresh standalone VideoToolbox sessions use the same captured restored
P010 frame: previous FFmpeg family, private static family, then one repeat of
each. The small consumer mirrors the inspected production bitrate, frame rate,
GOP, color fields and options. All four recorded contexts match, and actual
`allow_sw=0`/`realtime=0` readbacks require the hardware path. Each submits one
frame and drains one packet. Actual encoder/mux API addresses resolve to the
pinned Homebrew libraries in the previous family and the executable in the
static family. These standalone processes load no MDK, Qt or OCIO.

One pinned software HEVC decoder produces one 4K Main 10 YUV420P10LE frame from
each output. All 12,441,600 samples are exact across the four decoded pictures,
with shared SHA-256
`f39418d09faa8e2777962b2eee57b983fcfaf2321fe6ccaa370fff248b0346f2`.
The four encoded packet and file hashes differ; those differences alone are
not decoded-image differences. Independent MP4/NAL byte parsing finds exact
codec configuration and coded-picture NAL bytes across all four; the differing
sample bytes are confined to a prefix SEI NAL. Their meaning was not decoded,
so no timestamp/session explanation is assumed. All fixture/tool/library/source
preservation checks pass. Matrix and primaries tags are BT.709, range is
limited, and the transfer tag is unspecified in these isolated outputs.

This shows no decoded variation for the fixed fixture in these four sessions.
It does not establish general encoder determinism or reproduce the original
242-frame app lifetime. The probe uses direct software P010 with a device-only
VT context; the historical app's upload/context branch was not recorded.
The old dependencies themselves record macOS 26 even though the consumers
record macOS 11, so this is not older-OS acceptance. The remaining concrete
questions at this point are sensitivity to the measured small input changes,
temporal encoding and the actual full-frame sequence/process context.

## Measured-input sensitivity and original first-frame reproduction

Four further standalone sessions use one fixed previous-family encoder binary:
the captured old LUT fixture, new LUT fixture, then one repeat of each. Only
fixture selection changes. The recorded encoder contexts and hardware-option
readbacks match; actual API providers resolve to the same pinned libraries in
all four sessions. Each session submits one frame and drains one packet.

Independent comparison of the complete input confirms exactly 59 of 12,441,600
P010 samples differ by one ten-bit code value. Within each fixture, the two
decoded outputs are exact. Across fixtures, 5,883,985 decoded samples differ,
with mean absolute error 0.9785809702932099, root mean square error
1.8773769013458086 and maximum 41 codes. Every first-frame plane's differing
count, absolute-error sum and maximum exactly match the retained original
b9-versus-candidate LUT comparison.

Independent MP4 sample-table and HEVC NAL parsing also checks the original
exports themselves. Their full-file hashes match the retained receipts; both
first samples are sync pictures at presentation/decode time zero. The original
old first coded-picture payload equals both old-fixture outputs byte for byte;
the original new first coded-picture payload equals both new-fixture outputs.
All six decoder configurations are exact. Corresponding whole samples differ
only in prefix SEI bytes whose semantics were not parsed.

This establishes that the measured 59 one-code input changes are sufficient
to reproduce the original first LUT coded-picture difference using the same
encoder. It supplies a concrete first-frame explanation without changing
production color algorithms or converting tiny float differences into an
encoder-implementation fault. It does not establish the cause across all 242
frames, temporal rate-control behavior or the historical app upload branch.
This first-frame experiment did not establish full-sequence acceptance; the
later bounded sequence checks below address that separate scope. All source,
fixture, tool, library and settings preservation checks pass.

## Late color failures and CLI completion

Full-sequence instrumentation initially imposed an invalid ordering constraint
on raw AVFrame timestamps. Stabilization reuses its image buffer, and the real
encoder timestamp is assigned later. The observer now orders captures by the
serial color-call ordinal, keeps raw metadata for paired checks, and checks
completed packet timing separately. Production timestamps and stabilization
were not changed.

That failure exposed two error-path issues: the packet loop could suppress a
color-processing error after encoding started, and the CLI could print
completion when its counter reached an estimated total. The failed diagnostic
retained one captured frame and an incomplete temporary output, then reached
its log cap amid repeated completion messages. The precise second-call
timestamp rejection is source-derived; the old error path did not report its
exception text. That run is retained as a failure.

Two narrow source corrections propagate `ExportLut` errors after encoding has
started and require the queue's actual finished signal for CLI completion.
Color operations, decoder-error tolerance and hardware selection are unchanged.
The earlier staged and installed binaries predate these corrections.

A fresh deliberate failure before the second color call completed naturally
in **2.189 seconds**. It reported the injected error and `Rendering failed`,
reported no completion, retained one complete four-stage capture, and produced
no finalized video. Source, settings, project, LUT, original clip and all
**666** pinned inputs were preserved. The CLI's existing handled-error contract
still returns process status **0**; status alone does not establish success.

The diagnostic observes `hevc_videotoolbox`, VideoToolbox/P010, and the actual
encoder options `allow_sw=0` with `require_sw` absent/default zero. Together
with the successful first encoder open/send path, this establishes a
hardware-required session contract. It does not claim a specific AVE encoder
ID, a session-property readback, or a decoded frame from the unfinished fault
output. FFmpeg's [VideoToolbox implementation](https://github.com/FFmpeg/FFmpeg/blob/n9.0.1/libavcodec/videotoolboxenc.c)
requires hardware with these options. Private diagnostic logging is separate
from the production patch and is not timing evidence.

## Bounded full-sequence pipeline acceptance

Four normal exports completed with the corrected error/completion guards:
LUT-only and an eight-control grade, each using the old and new dependency
builds. Every export produced **242 encoded packets and decoded frames** of
3840x2160 HEVC Main10, `yuv420p10le`, BT.709 space/primaries, limited range and
60000/1001 fps. A transfer-function field was not reported by the probe.
The observed encoder options required VideoToolbox hardware, with software
fallback disabled. Finalized files, normal completion, exact selected OCIO
providers and preservation checks passed in all four cases.

Across all 242 ordered color calls, every active input plane before color
conversion and before the CPU processor had an identical paired SHA-256.
Thus the stabilized frame data entering color processing matched. Every
post-processor float plane was fully scanned for finite values and the fixed
min/max/compensated aggregate bounds. Output comparisons used **4,096 pinned
spatial coordinates per call**, including RGB and corresponding YUV components:

| Sampled comparison | LUT only | Eight-control grade |
| --- | ---: | ---: |
| Maximum absolute post-processor float difference | 1.1920928955078125e-7 | 2.384185791015625e-7 |
| Maximum restored 10-bit YUV difference | 1 code | 1 code |
| Differing restored components, out of 2,973,696 sampled components | 72 | 102 |
| Paired output packet PTS/DTS/durations | Exact | Exact |

These pass the preselected **1e-6 float / 1-code restored** bounds. They
establish the bounded sampled-pipeline contract, not exhaustive output-pixel
equality or identical lossy encoded/decoded pictures. Capture identity is the
serial color-call ordinal; raw reusable-frame timestamp metadata is not the
source clock. Output packet timing is checked separately.

This current-Mac check used rebuilt diagnostics with the same frozen color
implementation and two exact production guards. Observer/logging overhead is
not a speed benchmark. The diagnostics can load pinned incidental Homebrew
libraries through MDK; this does not establish portable dependency closure or
ownership of every FFmpeg call. The installed development app and earlier
staged bundle remain unchanged and predate the guards. The retained packet is
`full-sequence-color-diagnostic-v3/sequence-20261008T090459Z` under the private
evidence directory below; the deliberate fault packet is `fault-20261008T090440Z`.

## Remaining acceptance

Original decoded color-output release acceptance, matched candidate timing,
current Windows native
preview/export, complete notices/provenance, clean-machine installation,
older-OS execution and public signing/notarization remain open. The private
bundle must not be offered as a release download on this evidence.

Exact commands, hashes, build/source reviews, stage inventories, native logs,
input-preservation receipts and independent output comparisons are retained
under `_dev/ocio-runtime/portable-app-build/`. Camera media and vendor LUTs are
not redistributed.
