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
| Windows portable executable | `GyroflowPlus.exe`, separate directory |
| Settings | `Gyroflow Plus` user-data directory; Qt organization Ryan Smith |
| Update API/download | `rsmith4321/gyroflow`, stable `plus-v<semver>` tags only |
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
python3 _scripts/package_plus.py mac path/to/prepared/Gyroflow.app path/to/new-stage \
  --binary target/release/gyroflow --licenses path/to/dependency-notices
```

```powershell
python _scripts/package_plus.py windows _deployment/_binaries/win64 path/to/new-stage `
  --binary target/x86_64-pc-windows-msvc/deploy/gyroflow.exe `
  --licenses path/to/dependency-notices
```

The stager requires a clean source checkout for portable candidates, preserves
the runtime's dependency notices, adds GPL/OCIO/fork notices, corresponding app
source archive, source URL, binary SHA256 and commit manifest, and refuses an
existing output. Mac auditing rejects absolute non-system dependencies. It
ad-hoc signs local Mac stages; that does not establish Developer ID signing,
notarization, Windows trust or public-release readiness. Supplying notices does
not establish that every dependency's license/source obligations are satisfied;
that audit remains a release gate.

For a local development build, `--development-runtime` explicitly permits the
prepared runtime's machine dependencies and records them. Such builds may rely
on Homebrew and are not advertised as portable downloads. Staging does not
install, publish, register Windows project associations or create a GitHub release.

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
