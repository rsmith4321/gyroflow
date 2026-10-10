# Private Windows OpenColorIO application acceptance

Checked 2026-10-09 on the connected Windows laptop. The selected application
build uses the official OpenColorIO processor for export. Native Windows
preview and settings interaction remain unverified because the supported
computer-use helper returned `GetCursorPos: Access is denied` before any input
succeeded. This is a private candidate, not an approved public download.

## Exact identities

| Item | Verified identity |
| --- | --- |
| Application source | `427a6ca40670a8ad9902fa7f15fa9677792ccde2` |
| Selected Cargo features | `--no-default-features --features opencv,ocio-runtime` |
| Executable | `Gyroflow.exe`, 43,900,928 bytes |
| Executable SHA-256 | `26c09dccb980811f397457e20c9496bb9cd308b7efcc720ce79486fad1c8763d` |
| Native runtime inventory | 120 DLLs; staged imports resolved, x64 audit passed |
| Notice and supplemental source commit | `6e27b793cea6ee2434caee768c49def0eed5b834` |
| Native notice manifest SHA-256 | `fe2e3e0a457cba28b38f2a9333ca3d3eaef7d72ae79c3c66079c91edc3ed5a25` |
| Private assembly receipt SHA-256 | `62cbbf21f49cb27262533034bea2d5e95aa2e29b07f91f4b6cb18201587ffc6e` |

The locked offline application build completed successfully. The staged
application's isolated `--help` invocation also exited successfully. Its
`qt.conf` points `QmlImports` at the deployed `qml` directory. These startup and
import checks do not establish native preview behavior.

## Hardware export and decoded output

The current executable exported a four-second section of moving DJI footage
with a selected LUT and all eight color controls nonzero. The actual NVIDIA
encoder-session table identified an H.265 3840×2160 session belonging to the
render process, including nonzero frame-rate samples. This is direct hardware
encoding evidence for that run.

| Output check | Result |
| --- | --- |
| Render process | Exit 0; measured render interval 17.215 seconds |
| Output | HEVC Main 10, `yuv420p10le`, BT.709 limited range |
| Frame rate / duration | 60000/1001 fps; 4.037367 seconds |
| Complete independent decode | Exit 0; 242 frames |
| Output bytes | 67,820,243 |
| Output SHA-256 | `2fb159b29cf0f22f4ac29e9b7256b59e6bc7513ef8f53a20968b916cb24f9ac5` |
| Decoded frame-hash file SHA-256 | `44f6c88d52f5140dfbc78402aee457c5aad149bf646b06f7fa640f67a79bafcd` |

Both the output bytes and decoded frame-hash file match the previously accepted
graded export. The export metadata records brightness 0.12, contrast 0.18,
shadows −0.5, highlights 0.5, exposure 0.37, saturation 0.23, warmth 0.41 and
tint −0.27. This confirms preservation of that export case; it does not prove
every camera/codec, Windows GPU preview parity or general performance.

## Complete private notice assembly

An initial deep-path notice copy failed before packaging. A later file-only
assembly used a short destination, with a maximum normal path length of 227
characters. No Windows path policy or security setting was changed.

The new assembly preserves all 627 original stage files, the original build
receipt and source archive, the executable, and all 120 DLL identities. It adds
603 native notice members plus their manifest **inside the application
directory**, and a complete source archive for the supplemental `6e27b793`
commit. The original receipt is retained unchanged; `ASSEMBLY.json` records the
new assembly separately from the older binary build.

Independent acceptance checked all transferred evidence-file hashes, compared
all 1,301 supplemental source files with the committed checkout and all 1,283
original source files with the original Git revision, and verified the notice
member hashes against committed files. All 661 files outside documentation
and notice areas are byte-identical between those source versions. The 25
changed paths contain only documentation and notices.

The assembly has 1,233 files including its receipt. Its canonical final
inventory SHA-256 is
`52d262d178a2925ea6f33e34978b3d5e7b4fbea79006f78c8111cfc19056d7c4`.
The supplemental source archive is 46,899,200 bytes, SHA-256
`99db08c21601dde9b3e68024fc8959c67cf44ae5f1a0116c577f0104aefbd70d`;
the worker's complete archive-member map matches the independently verified
source inventory. Remote package/binary byte hashes are worker observations;
the acceptance host did not execute or transfer those binaries again.

Content integrity passed. **Historical (2026-10-09 `6e27b793` assembly):** strict
provenance checking of that assembly's notice manifest returned the expected
incomplete result for **ten remaining requirements** across Qt, FFmpeg, MDK,
Microsoft CRT, D3D compiler and software OpenGL. That count, and the notice
commit, manifest and receipt identities above, describe only that private
assembly and are not updated here. Complete notice copying is distinct from
establishing every provider's distribution/source obligations. All assembly
jobs ended, including preserved failed helper attempts.

### Current source notice packet

The current native notice snapshot, `resources/notices/native/windows-x64`, is a
separate, later packet. Its `MANIFEST.json` is 559,717 bytes, SHA-256
`41edb624f5aa46aab954d03555b33ba18876d36546df68248b45de1192433530`. It uses schema
`gyroflow-plus/native-notices-manifest/v2`, has status `CANDIDATE`, targets
`x86_64-pc-windows-msvc`, and sets `public_release_approved: false`.

The offline verifier ran pinned to that hash. It found:

- 1,392 listed members (8,209,623 verified bytes), matching 1,392 files plus the manifest
- 25 reused repository paths
- 11 required components
- a staged inventory of 120 DLL entries across 10 components

Content integrity passed with 0 problems. The strict check reported
`RELEASE-PROVENANCE: INCOMPLETE`, with exactly eight blocking gaps across six
components (3 blockers, 5 obligations):

- d3dcompiler: `d3d-terms`
- ffmpeg: `ffmpeg-texts`, `ffmpeg-source`
- mdk: `mdk-ffmpeg9-source`, `mdk-libass-fribidi-source`
- msvc-crt: `crt-terms`
- qt: `qt-source`
- unattributed: `opengl32sw-provider`

The later libass archive-source build/relink qualification and retained draft
source kit are indexed in
`mdk-0.39.0-e89bc0b/bundled/evidence/LIBASS-SOURCE-QUALIFICATION.json`. They do not close
public delivery or remaining corresponding-source/provider requirements.

Fifteen advisories are recorded separately from the eight blocking requirements.
This source check does not establish assembly or installation of the later
packet on Windows; the dated `6e27b793` assembly acceptance above is unchanged.

Private evidence is retained under `_dev/root-windows-427a-acceptance-20261009/`
and `_dev/root-windows-6e27-assembly-acceptance-20261009/`. Source preparation
supplements are retained in an unpublished GitHub draft; they do not establish
complete corresponding source or approve a binary release.

## Remaining acceptance

- Native Windows GPU preview, control reset and project save/reopen checks.
- Remaining exact provider notices, terms and corresponding-source delivery.
- Clean-machine and supported Windows version testing and ordinary trust checks.
- Final release packaging tied to the accepted source and runtime identities.

The [public-release gates](PLUS-DISTRIBUTION.md#public-release-gates) remain in
force. No public release, default runtime switch or website download approval
follows from this private acceptance.
