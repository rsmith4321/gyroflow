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
  --manifest-sha256 ecba5b051c8d9c1df59d8f90f3ad3e8db0b614979d41034173af56e7bf4976b7
```

Content integrity currently passes. Add `--require-release-complete` to check the
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
