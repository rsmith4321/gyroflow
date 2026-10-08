# Gyroflow Plus desktop distribution foundation

Gyroflow Plus is a community fork of Gyroflow, maintained by Ryan Smith. The
working name is provisional. Upstream development is active. Original authors,
copyright headers, GPLv3 source license and third-party notices are retained.
New prototype source is GPL-3.0-or-later. OpenColorIO tone samples include its
BSD 3-clause copyright/license; see `resources/color/OCIO-LICENSE.txt`.

## Independent identities

| Surface | Fork identity |
| --- | --- |
| Application/UI | Gyroflow Plus, explicitly marked Community fork |
| Application version | `0.1.0-dev`; upstream core retains its own version |
| Mac bundle | `com.ryansmith.gyroflow-plus`, `Gyroflow Plus.app` |
| Windows portable executable | `Gyroflow Plus` directory; executable keeps `Gyroflow.exe` for the embedded MDK key |
| Settings | `Gyroflow Plus` user-data directory; Qt organization Ryan Smith |
| Update API/download | `rsmith4321/gyroflow-plus`, stable `plus-v<semver>` tags only |
| Project format | Compatible `.gyroflow`, no default-handler takeover |

Official settings and the earlier LUT Preview settings are not automatically
copied. Import an existing project or chosen preset explicitly. Mac staging
imports the official project UTI and uses handler rank None. Windows staging
is portable and writes no association registry entries. The internal Mac binary
and Rust package name remain `gyroflow` to retain existing build integration;
the installed bundle, product version, settings and updater identities differ.

Inherited release/Store/WinGet automation is guarded to run only in upstream's
repository. This fork must never publish under upstream package IDs or signing
credentials. This prototype does not provide a public packaged release.

## Build and stage

Build with the checked-in Cargo locks. Current dependency recipes are in
`_scripts/common.just`, `macos.just` and `windows.just`. Windows pins the existing
FFmpeg archive/version/SHA256 and Qt version. Record the exact compiler, Qt,
FFmpeg, OpenCV and MDK versions, source revisions and dependency license texts
with each packaged artifact. Source/build reproducibility is the goal; bitwise
reproducible binaries across arbitrary compilers are not established.

The inherited desktop dependency/deploy recipes are a starting point for
preparing a runtime with Qt, QML, FFmpeg, OpenCV, MDK and codecs. On Mac the
recipe needs an explicit target (`just deploy local` or `just deploy universal`);
on Windows it is `just deploy`. Do not use upstream Store/bundle signing recipes
or credentials. These portable recipe paths have not been accepted for this
prototype. Once a runtime is prepared and audited, stage it under the fork identity:

```sh
# After committing source, run in the prepared Mac dependency environment.
# Cargo reports the exact executable path in _dev/mac-build.json.
python3 _scripts/build_plus.py --features ocio-runtime --output _dev/mac-build.json
python3 _scripts/package_plus.py mac path/to/prepared/Gyroflow.app path/to/new-stage \
  --binary _dev/mac-build.json.target/deploy/gyroflow --deploy-receipt _dev/mac-build.json \
  --licenses path/to/dependency-notices
```

The Mac helper runs a locked Cargo build, selects this package's executable from
Cargo's artifact report and records its SHA256 only if source stays clean at the
same commit. Each invocation uses a fresh, exclusively owned Cargo target
directory beside the receipt (`<receipt-name>.target`); it never reuses or
overwrites another build's target directory. Keep that directory exclusive until
staging completes. `--target` and `--profile` support explicit single-architecture builds;
use the reported executable path when it differs from the example. It does not
prepare or modify the runtime bundle. A combined universal executable needs a
separate controlled build-and-combine receipt; the single-target helper does not
attest a later `lipo` output. Build receipts are local provenance, not signatures
or proof that dependency/toolchain inputs meet the remaining release gates.

```powershell
python -m pip install --require-hashes -r _scripts/requirements-package.txt
just deploy ocio-runtime   # requires OCIO_ROOT and an empty _deployment/_binaries/win64
python _scripts/package_plus.py windows _deployment/_binaries/win64 path/to/new-stage `
  --binary target/x86_64-pc-windows-msvc/deploy/gyroflow.exe `
  --deploy-receipt _deployment/_binaries/win64-deploy.json `
  --msvc-redist-floor 14.44.35211.0 `
  --licenses path/to/dependency-notices
```

The floor above is an example; replace it with the full FileVersion required by
the newest toolset used to build the app, OCIO, Qt and OpenCV. Run deploy in a
Visual Studio developer environment. It copies one runtime set from
`VCToolsRedistDir` and writes a build receipt only after all required copies and
archiving succeed. Move prior runtime, receipt and ZIP outputs before deploying.

Derive that minimum from the recorded toolset and its corresponding Microsoft
redistributable, not by changing `19` to `14` in `cl.exe`'s FileVersion: the
compiler, toolset-directory and redistributable build numbers can differ. Keep
the explicit full-version comparison; a wrongly supplied minimum must be
corrected from provenance, rather than silently ignored by the audit. See
[Microsoft's DLL redistribution guidance](https://learn.microsoft.com/en-us/cpp/windows/determining-which-dlls-to-redistribute).

The import audit distinguishes Windows components from app dependencies. It
recognizes the in-box AVICAP32, BCryptPrimitives, DirectSound, ImageHlp and legacy
MSVCRT libraries; staging those system DLLs is rejected. This does not accept
missing `vcruntime140`/`msvcp140` redistributables or verify the symbols supplied
by an arbitrary Windows version. Those still need the native runtime gate.
[BCryptPrimitives requirements](https://learn.microsoft.com/en-us/windows/win32/seccng/processprng),
[AVICAP32 requirements](https://learn.microsoft.com/en-us/windows/win32/api/vfw/nf-vfw-capgetdriverdescriptiona),
[ImageHlp requirements](https://learn.microsoft.com/en-us/windows/win32/api/imagehlp/nf-imagehlp-mapfileandchecksuma).

The stager requires a clean source checkout for every candidate and a matching
build/deploy receipt for portable stages on both platforms. It checks the receipt's
commit, clean-source flag and executable SHA256 before creating the output and
retains its bytes as `Notices/BUILD-INPUT.json`. It preserves
the runtime's dependency notices, adds GPL/OCIO/fork notices, corresponding app
source archive, source URL, input-build binary SHA256 and commit manifest, and refuses an
existing output. Mac auditing rejects absolute non-system dependencies. Windows
auditing (on Windows) rejects unresolved imports or symbols, stale library
versions and an incoherent or too-old C++ runtime; it is not a run on a clean
machine. It
ad-hoc signs local Mac stages; that does not establish Developer ID signing,
notarization, Windows trust or public-release readiness. Supplying notices does
not establish that every dependency's license/source obligations are satisfied;
that audit remains a release gate.

For a local development build, `--development-runtime` explicitly permits the
prepared runtime's machine dependencies and records them. Such builds may rely
on Homebrew and are not advertised as portable downloads. Staging does not
install, publish, register Windows project associations or create a GitHub release.
Commit newly added files and other source changes before staging development
builds too. This keeps the accompanying source archive complete without copying
untracked private files into a package.

Development staging may omit the build receipt. In that case `source_commit`
and the build manifest's `commit`/`source` are null, `binary_source_verified` is
false, and the Mac bundle has no `GyroflowPlusSourceCommit`. The separately named
`checkout_commit` and `GyroflowPlusCheckoutCommit` identify the accompanying
checkout archive, which is not evidence that an unverified binary came from it.
If a receipt is supplied for a development stage, it must pass the same identity
checks. This prevents a stale executable from being labeled with a newer commit.

## Public-release gates

- Latest native brightness/contrast and new tone controls tested in the full
  Windows application, including D3D preview, real moving footage and encoding.
- Portable Mac/Windows runtime dependency closure, license/corresponding-source
  audit, clean-machine install/uninstall and coexistence checks.
- Reproducible build inputs and dependency source/build manifests; signed and
  notarized Mac package as appropriate and ordinary Windows trust checks.
- Project/preset/queue compatibility, native UI and frame/alpha/color references.
- Own tagged release (`plus-v...`) with matching source and acknowledgments;
  final working name/icon approval before a public product launch.

The focused upstream LUT PR remains on `codex/export-lut` and contains neither
this branding nor these additional tone controls.

`Notices/BUILD.json` records `input_binary_sha256` for the pre-signing build
input. `PACKAGE.json`, beside the app, records the final
`packaged_binary_sha256` after signing. These can differ for a Mac Mach-O file;
the final receipt stays outside the signed bundle to avoid a circular resource
hash. Older stages used the ambiguous `binary_sha256` field for the input hash.
