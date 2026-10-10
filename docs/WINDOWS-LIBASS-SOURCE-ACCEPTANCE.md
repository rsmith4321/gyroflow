# Windows libass source build acceptance

## Accepted result

The manual GitHub-hosted Windows run
[38014071478](https://github.com/rsmith4321/gyroflow-plus/actions/runs/38014071478)
completed successfully on October 10, 2026 UTC, using Gyroflow+ source
`aab1d5f5cd764a3be46ba7fe812a9acbdf4dac31` and job `114100378432`.
It built a separate libass dependency candidate; the installed app was unchanged.

The runner uses twelve exact source commits listed in
[_scripts/notices/rebuild_libass_windows.py](../_scripts/notices/rebuild_libass_windows.py).
The selected libass, FriBidi, FreeType and HarfBuzz revisions match the retained
vendor build log. NASM 2.16.01 is built from official pinned source, with a
recorded NMake recipe adaptation and unchanged official configuration headers.
The library's C, assembly and Perl source algorithms are unchanged.

The successful run provides these checks:

| Check | Evidence |
| --- | --- |
| Source and tools | Twelve exact Git checkout identities; tool paths and hashes retained |
| NASM | Required generation, compile and version check pass; original recipe and official headers remain unchanged |
| libass | Actual 187-step build succeeds, including all seven x64 assembly objects |
| Link inputs | All 34 libass objects, three unique static dependencies, x64 and LTCG retained |
| Exported API | Fifty names match the pinned `libass.sym`, before and after relink |
| Relink | Deleting only the freshly built DLL produces a single link step; runner verifies all 181 retained object/static-library hashes stay unchanged |
| FriBidi generation | Seven expected table/header outputs are generated, with their command lines, sizes and hashes recorded |
| Root inspection | All 98 commands exit successfully; 73 nonempty public log hashes and 24 empty log sizes checked; private environment capture excluded |

The actual original vendor x64 link command also repeats FreeType after HarfBuzz.
The accepted ordered archive sequence is
`FriBidi, FreeType, HarfBuzz, FreeType`. The earlier description of three libraries
referred to three unique dependencies; no CMake-version explanation for the
repeat is established. Pinned HarfBuzz source directly links FreeType.

## Limits

This job fetches exact Git revisions online. It does **not** qualify an offline
build from the source archives intended to accompany a public package, or finish
the corresponding-source delivery obligation for the shipped dependency.

The artifact contains JSON and logs, not binaries or generated table contents.
Root independently verifies the logs, source identities, export rows and link
commands. Retained-product stability and generated-file hashes are runtime
assertions recorded by the reviewed runner; root cannot independently rehash
those absent products from the text artifact.

The first DLL SHA-256 is
`be9a599696f4349470d3e5599b6c0449000025cda67d5d79a4dd82626da199fa`;
the relinked DLL is
`cc9e2991f9c77147c125bac39fec8afc56546a555050d76a4b21162be4d7934b`.
They differ despite identical export rows and retained link inputs. This is
successful relinking, not a reproducible-binary or vendor-identical DLL claim.

The hosted toolchain reports MSVC 19.51.36260 and CMake 4.4.3. Its compiler
identity is not shown to match the vendor's build. The shallow tag-less checkout
also changes libass version metadata. No app installation, decoding, native GUI
test, package promotion, signing or public release is established by this job.

The eight recorded Windows distribution requirements remain open, including
`mdk-libass-fribidi-source`. The source-only draft release and all installed
runtime binaries remain unchanged. This evidence advances that source/relink
work without approving a public download.

Private root acceptance is retained at
`_dev/root-libass-hosted-ci-20261009/CI-RUN-38014071478-ACCEPTANCE.json`, alongside
the text artifact and a data-only independent inspector.
