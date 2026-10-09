# Rust dependency notices

## Windows native notice snapshot

The reviewed native snapshot is in
[`resources/notices/native/windows-x64`](../../resources/notices/native/windows-x64).
Its manifest describes the frozen `ab680a27` Windows stage: 120 DLL identities,
verbatim notice texts, provider provenance and explicit remaining gaps. A new
stage must be compared with those identities before reusing the snapshot.

Check content and the 25 reused repository files with the offline standard-library
verifier:

```sh
python3 -I _scripts/notices/verify_native_notices.py \
  resources/notices/native/windows-x64 --repo-root . \
  --manifest-sha256 cbc3bc65e710a1585df9607a8eedf17a9919fb73f29db6d2dbda8f41d6858baa
```

The Qt GPL-2.0-or-later alias is retained as the full upstream target text,
rather than the literal Git symbolic-link target name. Content integrity currently passes. Add `--require-release-complete` to check the
recorded release gaps; it currently returns **3**, because ten blockers or
obligations remain. A normal integrity exit of zero is not distribution approval.
The manifest pin prevents an edited gap classification from silently passing.

For a Windows package, combine the reviewed native tree and the matching Rust
notice output in the prepared directory supplied to `package_plus.py --licenses`.
That option copies the supplied tree; the native snapshot alone does not contain
the Rust notice output. The packager also retains the tracked OpenColorIO notices.
Keep corresponding-source and provider-term records with the release evidence;
this snapshot does not establish license compatibility or satisfy those open
obligations by itself.

## MDK bundled dependency notices

The MDK snapshot includes 23 original notice texts for the bundled FFmpeg and
libass dependencies, plus their source and binary provenance. Seventeen are full
upstream files and six are license comment excerpts with recorded line ranges.
`mdk-0.39.0-e89bc0b/bundled/evidence/NOTICE-SOURCES.json` records each upstream
repository, commit, path, blob identity and whether the DLL build pin is exact
or inferred. All 23 delivered texts were independently compared with those
upstream commits.

An embedded library version does not establish an exact source commit. The
HarfBuzz version is exact, while its source pin and other documented build pins
remain inferred pending provider build records. The two former broad MDK notice
gaps now have narrower records for missing AMF/libva header provenance, source
delivery. The FreeType credit/license choice and OpenCL notice gaps have since
been resolved with retained documentation and exact installed provider files.
Ten recorded blockers or obligations remain across the complete native tree.
The software OpenGL component now retains version-matched Mesa/LLVM notices
and an older Qt-published attribution, with source and excerpt identities in
`unattributed/NOTICE-SOURCES.json`. The version-matched texts have been reviewed;
complete binary copyright-holder coverage remains
open, and the original provider gap remains blocking. Supplementary Gallium and
Unicode notices and explicit regex documentation credits are retained.
These additions do not
change the staged DLL inventory or establish complete corresponding source.

## Qt source artifacts

The Qt snapshot records five official mirror archives in
`qt-6.7.3/source-artifacts.json`: four modules at verified `v6.7.3` commits and
the exact test262 submodule omitted from GitHub's module archives. All 86 selected
Qt notice files match these sources after resolving the upstream license alias.
`qt-6.7.3/source-bundle.sha256` identifies the prepared source bundle.

Keep `Qt-6.7.3-source-bundle.tar` with the release artifacts and deliver it with the
matching package. Its `SOURCE-README.txt` describes extraction into a new empty
directory, including the test-suite submodule placement. The large source archive
is a release artifact, not a Git source file. These retained sources do not close
the recorded source obligation until delivery and provider/build-provenance
checks are complete. No written source offer or release approval is implied.

## Rust collector

This is a release-preparation recipe, separate from application compilation.
It uses the official `cargo-about` 0.9.2 collector. The Python gate checks that
its output covers the selected Cargo graph and copies checksum-pinned extra
upstream notices. A successful gate does not establish license compatibility,
native-library coverage, complete corresponding source, or release approval.

## Supported collector environment

Run the shell collector on Linux with Bash 4.4 or newer, GNU `timeout`, Python 3,
Git, and the appropriate pinned Rust toolchain/cache. macOS's system Bash and
native Windows PowerShell are not supported runner environments. The resulting
notice files can accompany a Mac or Windows package after their receipt's commit,
target, manifest/lock hashes and feature selection are matched to the actual build.
The runner does not install tools or fetch dependencies. Provision the locked
cache separately before running it; all Cargo collection commands use `--frozen`.

Install the pinned collector in an explicitly chosen tool prefix:

```sh
cargo install cargo-about --version =0.9.2 --locked --features cli --jobs 2 --root "$tool_prefix"
```

The published crate archive SHA-256 is
`0cd19d99696eb83f0a2d6ab7a347b14968d2980416c8cca827ded220e6e9c4bb`.
The `cli` feature is required to install its executable. Place that prefix's `bin`
directory on PATH for collection; the runner checks the reported tool version.

From a clean checkout, with fresh output and work directories:

```sh
bash _scripts/notices/run_rust_notices.sh \
  --no-default-features --features opencv,ocio-runtime,ffmpeg-next/static \
  --absent breakpad-sys \
  "$checkout" "$checkout/_scripts/notices" "$output" "$work" aarch64-apple-darwin
```

For Windows x64, select `opencv,ocio-runtime` and `x86_64-pc-windows-msvc`.
The compile must use the same explicit `--no-default-features` selection. The
existing Windows `just deploy` recipe does not pass that flag; use a separately
reviewed Cargo build plan until its deploy pass-through is implemented and tested.
No Windows build is implied by generating its metadata on Linux.

Each Cargo step has a 300-second timeout by default (`STEP_TIMEOUT` overrides it).
Use an external overall time/output bound as well. Failed runs retain a `.partial`
directory for diagnosis and never rename it to the final output. JSON containing
local cache paths stays in the work directory, outside the shipped notice packet.

## Corresponding Rust source

`vendor_archive.py` makes a deterministic archive from an already populated
`cargo vendor --frozen --versioned-dirs` directory and its generated config.
See its header for invocation. Extract the two archives into this parent/child
layout, matching the source commit and dependency lock recorded by their receipts:

```text
source-bundle/
  .cargo/config.toml       # generated vendor source configuration
  cargo-vendor/            # dependency sources
  src/                    # Git source archive, unchanged
    .cargo/config.toml     # tracked target linker flags
    Cargo.toml
    Cargo.lock
```

Run Cargo from `source-bundle/src/`. Cargo merges the parent vendor-source config
with the repository's target config; the vendor directory resolves relative to
`source-bundle/`. **Never extract the vendor archive over the Git source tree:**
that would replace the tracked config and discard linker flags, including Mac
runtime search paths. This follows Cargo's [configuration hierarchy and relative
path rules](https://doc.rust-lang.org/cargo/reference/config.html).

The `cargo-vendor/` directory is separate from the repo's existing `vendor/` path
crates. Graph resolution with an empty Cargo cache and
`--frozen` is a source-availability check; it is not a successful application build.
Native dependencies and their source/build requirements remain separate.

## Provenance and verification limits

Integrated from the reviewed C2/C3 recipe at public application commit
`0b5ba007bfad303f88c143615a9d2baf384de4cb`. The frozen C3 manifest SHA-256 is
`2b549b1b00c39d620f04600a9b901ebe68889d42a659ddc62ff2561ae77334bc`.
The gate, config and supplements retain the reviewed bytes. The archive helper's
implementation is unchanged; its instructions now require the parent/child layout.
Integration adds an explicit runner environment check, replaces regex-based path
redaction with literal replacement, and corrects the template's overinclusive
"statically linked" label. Earlier C3 outputs retain their original receipt and
template hash; these small integration changes do not retroactively regenerate them.

Reviewed evidence includes refusal of empty/malformed graphs and blank license
text, preservation of Cargo failures, and current selected Mac/Windows graphs
with only `breakpad-sys` removed. The original independent gate checks are retained
in project continuity. The collector and complete app/package were not rerun by
this integration. Malformed supplement/metadata may fail with a traceback; such
failures are nonzero and must never be treated as a completed packet.

Remaining attribution decisions include the upstream objc2 and pulp licensing
statements, nalgebra 0.30.1's declaration/text discrepancy, and native libraries
outside Cargo's view. Keep full upstream texts and supplements; the gate's fallback
allow-list is a recorded review decision, not a general exemption from attribution.
