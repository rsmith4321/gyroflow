# Official OpenColorIO runtime probe

Development experiment for replacing custom color evaluation with OCIO's public
CPU/GPU processor API. It does not change the installed app or default renderer.
The selected camera LUT still belongs to the existing LUT path in this probe.

`probe.cpp` defines the current eight-slider semantics once using OCIO matrix,
range, video tone and video primary transforms. OCIO executes the CPU operations
and generates the GPU shader. The only mathematical mapping outside OCIO prepares
the existing relative RGB balance/display exposure parameters; there is no custom
per-pixel tone, matrix, saturation or interpolation evaluator in the probe.

The optional `baked` CPU mode generates 4097 samples of the official tone
processor after the preceding bounded Range op, then uses OCIO's own
`Lut1DTransform` to evaluate the result. The GPU path remains the direct generated
tone code. This is a measured approximation; it is not an exact analytic CPU
tone evaluation.

## Reproduce

Build official **OpenColorIO 2.4.2**, with applications, Python and tests disabled,
into a private install prefix. The release archive used here was
`https://codeload.github.com/AcademySoftwareFoundation/OpenColorIO/tar.gz/refs/tags/v2.4.2`,
SHA-256 `2d8f2c47c40476d6e8cea9d878f6601d04f6d5642b47018eaafa9e9f833f3690`.
Use the official source's build instructions and retain its license/dependency
notices. This probe finds the exact version via CMake:

```sh
cmake -S tests/ocio-runtime -B /path/to/probe-build \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH=/path/to/ocio-install
cmake --build /path/to/probe-build
python tests/ocio-runtime/check_probe.py /path/to/probe-build/ocio_probe \
  /path/to/qt/bin/qsb /path/to/qt/bin/qml /path/to/results
```

The Python reference requires `opencolorio==2.4.2`, NumPy and Pillow. The GPU
check is Mac-specific and requires actual Metal, rather than a software fallback.
QSB compilation also generates GLSL, HLSL SM5 and MSL variants; compilation
does not prove execution on Windows.

On this Mac, the bundled old zlib source failed with the current Xcode SDK.
The successful development build used the SDK's system zlib and the already
installed Imath, with missing dependencies built by OCIO. CMake 4 required
`CMAKE_POLICY_VERSION_MINIMUM=3.5` for older external dependency projects.
No upstream processing source was edited. This is a local development dependency
closure, not a portable dependency recipe or finished security/license audit.

## Probe scope

- Compare neutral, each slider's extremes/fractional values and combined grades
  with the existing independent Python reference.
- Compare packed RGBA and padded planar RGBA; preserve alpha and padding.
- Generate a Qt preview shader from the same definition and compare actual
  Metal rendering with the official CPU result.
- Time processor application separately from file I/O and parameter preparation.

Current limitations: no full-application preview plumbing, slider-update shader
cache, selected-camera LUT integration, decoder/encoder integration, persistent
projects, concurrency acceptance, Windows execution or portable package proof.
See [integration boundaries](../../docs/OPENCOLORIO-INTEGRATION.md). The working
application path remains in place until those checks pass.
