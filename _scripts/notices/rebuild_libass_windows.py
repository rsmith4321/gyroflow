#!/usr/bin/env python3
"""Hosted-Windows source/relink evidence for pinned libass; never installs an app.

Keep the upstream devpkgs CMake project unchanged. The unrelated dav1d,
libva-loader and lz4 targets are disabled; the ass link graph is checked
against the vendor x64 link line so disabling them cannot weaken it.
No binary download, source patch, NO_ASM substitution or release upload.
Only text evidence (.json/.log) is written to native-source-evidence/.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time

SOURCES = (
    ("devpkgs", "wang-bin/devpkgs", "ce43c819981bb7ca028d08d1baa4847f1136f576"),
    ("devpkgs/cmake/tools", "wang-bin/cmake-tools", "a8a52d31cb5f2ab8916160069cbc7183c5e92a18"),
    ("devpkgs/src/freetype", "freetype/freetype", "0a0221a1347e2f1e07c395263540026e9a0aa7c7"),
    ("devpkgs/src/freetype/subprojects/dlg", "nyorain/dlg", "395ccad2c1e0daae535c4d20bb0a3f2424648e17"),
    ("devpkgs/src/harfbuzz", "harfbuzz/harfbuzz", "863d3f7787c6df18d20e4535c5906bf3eb803bd5"),
    ("devpkgs/src/fribidi", "fribidi/fribidi", "b93119f5fdc7ea47672cc304c1455ffa6dfe7536"),
    ("devpkgs/src/libass", "wang-bin/libass", "af5f116d243f060a708c82f0c6e3102a2270a336"),
    ("devpkgs/src/snappy", "google/snappy", "9c28114a38866f6deeaa826db918293bc28ae410"),
    ("devpkgs/src/glfw", "glfw/glfw", "d9d6f0f1f967807ffade6598ea9a631ebaf37a56"),
    ("devpkgs/src/zlib", "madler/zlib", "da607da739fa6047df13e66a2af6b8bec7c2a498"),
    ("devpkgs/src/oneVPL", "wang-bin/oneVPL", "3a3ca48d176ceb9733c2ea81d4f16a17d6c1702c"),
    ("nasm", "netwide-assembler/nasm", "d41598b3359d39c14e80f56bd8c3749f1d097932"),
)
REPOSITORY = "rsmith4321/gyroflow-plus"
BRANCH = "codex/lut-preview-controls"  # already the repository default branch (root API check 2026-10-10)
WORKFLOW = ".github/workflows/native-libass-source.yml"
# Per-command and whole-run log caps. Checked by polling, so a log can pass a cap by up to one poll
# interval of output before the process tree is stopped; the retained file is then cut to the cap.
MAX_LOG_BYTES = 12 * 1024 * 1024
MAX_TOTAL_LOG_BYTES = 24 * 1024 * 1024
POLL_SECONDS = 0.2
WHOLE_SECONDS = 900
NOT_RUN = ("Hosted VS2022 differs from vendor VS2026; no vendor-identical DLL or version-metadata claim. "
           "No app install/runtime test, complete corresponding-source or release approval.")

# Vendor x64 link of libass.dll (devpkgs job log line 1630), relative to the build directory.
_OBJ = "projects\\libass\\CMakeFiles\\{}.dir\\__\\__\\src\\libass\\libass\\{}.obj"
VENDOR_OBJECTS = tuple(_OBJ.format("ass-objs", n + ".c") for n in (
    "ass", "ass_arabic_charmap", "ass_bitmap", "ass_bitmap_engine", "ass_blur", "ass_cache",
    "ass_directwrite", "ass_drawing", "ass_face", "ass_face_ft", "ass_filesystem", "ass_font",
    "ass_fontselect", "ass_library", "ass_outline", "ass_parse", "ass_rasterizer", "ass_render",
    "ass_render_api", "ass_shaper", "ass_string", "ass_strtod", "ass_utils", "c\\c_be_blur",
    "c\\c_blend_bitmaps", "c\\c_blur", "c\\c_rasterizer"))
ASM_NAMES = ("be_blur", "blend_bitmaps", "blur", "cpuid", "rasterizer", "utils", "x86inc")
VENDOR_OBJECTS += tuple(_OBJ.format("ass_asm", "x86\\" + n + ".asm") for n in ASM_NAMES)
VENDOR_STATIC_LIBRARIES = ("projects\\fribidi\\libfribidi.lib", "src\\freetype\\freetype.lib",
                           "src\\harfbuzz\\harfbuzz.lib")
DLL = "projects\\libass\\libass.dll"
# fribidi-gen.cmake POST_BUILD commands write these into the source tree's gen.tab directory.
FRIBIDI_OUTPUTS = {
    "fribidi-unicode-version.h": "gen-unicode-version", "bidi-type.tab.i": "gen-bidi-type-tab",
    "joining-type.tab.i": "gen-joining-type-tab", "arabic-shaping.tab.i": "gen-arabic-shaping-tab",
    "mirroring.tab.i": "gen-mirroring-tab", "brackets.tab.i": "gen-brackets-tab",
    "brackets-type.tab.i": "gen-brackets-type-tab"}
# NASM Mkfiles/msvc.mak PERLREQ (Perl-generated inputs; absent from the git snapshot except unconfig.h).
NASM_PERLREQ = (
    "config/unconfig.h", "x86/insnsb.c", "x86/insnsa.c", "x86/insnsd.c", "x86/insnsi.h", "x86/insnsn.c",
    "x86/regs.c", "x86/regs.h", "x86/regflags.c", "x86/regdis.c", "x86/regdis.h", "x86/regvals.c",
    "asm/tokhash.c", "asm/tokens.h", "asm/pptok.h", "asm/pptok.c", "x86/iflag.c", "x86/iflaggen.h",
    "macros/macros.c", "asm/pptok.ph", "asm/directbl.c", "asm/directiv.h", "asm/warnings.c",
    "include/warnings.h", "doc/warnings.src", "misc/nasmtok.el", "version.h", "version.mac",
    "version.mak", "nsis/version.nsh")
TOOLS = ("git.exe", "cl.exe", "link.exe", "nmake.exe", "cmake.exe", "ninja.exe", "perl.exe", "dumpbin.exe")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def admission_errors(environ, platform: str) -> list:
    """Names of failed admission checks; empty means admitted."""
    expected = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Windows",
                "GITHUB_REPOSITORY": REPOSITORY, "GITHUB_EVENT_NAME": "workflow_dispatch",
                "GITHUB_REF": "refs/heads/" + BRANCH, "GITHUB_REF_TYPE": "branch", "GITHUB_REF_NAME": BRANCH,
                "GITHUB_WORKFLOW_REF": REPOSITORY + "/" + WORKFLOW + "@refs/heads/" + BRANCH}
    errors = [key for key, value in expected.items() if environ.get(key) != value]
    if platform != "win32":
        errors.append("sys.platform")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        if not re.fullmatch(r"[1-9][0-9]{0,19}", environ.get(key, "")):
            errors.append(key)
    sha = environ.get("GITHUB_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha) or sha == "0" * 40:
        errors.append("GITHUB_SHA")
    for key in ("GITHUB_WORKSPACE", "RUNNER_TEMP"):
        if not environ.get(key):
            errors.append(key)
    return errors


def require_host() -> None:
    errors = admission_errors(os.environ, sys.platform)
    if errors:
        raise SystemExit("Only a manual dispatch on " + BRANCH + " of " + REPOSITORY +
                         " on a GitHub-hosted Windows runner is admitted; failed: " + ", ".join(errors))


def normalize_windows_env(mapping) -> dict:
    """One upper-case key per Windows variable; case-variant keys with different values are refused."""
    result = {}
    for key, value in mapping.items():
        upper = key.upper()
        if upper in result and result[upper] != value:
            raise ValueError("Ambiguous environment variable spelling: " + upper)
        result[upper] = value
    return result


def merge_windows_env(base, captured: str) -> dict:
    """Overlay cmd `set` output on base without leaving stale case variants such as PATH beside Path."""
    merged = normalize_windows_env(base)
    seen = set()
    for line in captured.splitlines():
        key, sep, value = line.partition("=")
        if not sep or not key or key.startswith("="):
            continue
        upper = key.upper()
        if upper in seen:
            raise ValueError("Duplicate variable in developer environment: " + upper)
        seen.add(upper)
        merged[upper] = value
    if "PATH" not in seen:
        raise ValueError("Developer environment did not report PATH.")
    return merged


def parse_symbol_file(text: str) -> list:
    """Every non-empty libass.sym line, as written after EXPORTS into the CMake .def file."""
    names = []
    for number, line in enumerate(text.splitlines(), 1):
        name = line.strip()
        if not name:
            continue
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise ValueError(f"Unsupported libass.sym line {number}.")
        names.append(name)
    if not names or len(set(names)) != len(names):
        raise ValueError("libass.sym is empty or has duplicate names.")
    return names


_EXPORT_HEADER = re.compile(r"\s*ordinal\s+hint\s+RVA\s+name\s*")
_EXPORT_ROW = re.compile(r"\s+([0-9]+)\s+([0-9A-F]+)\s+([0-9A-F]{8})\s+([A-Za-z_][A-Za-z0-9_]*)")


def parse_dumpbin_exports(text: str) -> list:
    """Every named export row of `dumpbin /exports`; forwarded, ordinal-only or odd rows are refused."""
    lines = text.splitlines()
    headers = [i for i, line in enumerate(lines) if _EXPORT_HEADER.fullmatch(line)]
    if len(headers) != 1:
        raise ValueError("Expected exactly one export table.")
    counts = {}
    for line in lines[:headers[0]]:
        match = re.fullmatch(r"\s*([0-9]+) number of (functions|names)\s*", line)
        if match:
            if match[2] in counts:
                raise ValueError("Repeated export count.")
            counts[match[2]] = int(match[1])
    rows = []
    for line in lines[headers[0] + 1:]:
        stripped = line.strip()
        if stripped == "Summary":
            break
        if not stripped:
            continue
        if "forwarded to" in stripped:
            raise ValueError("Forwarded export: " + stripped)
        if "[NONAME]" in stripped:
            raise ValueError("Ordinal-only export: " + stripped)
        match = _EXPORT_ROW.fullmatch(line)
        if not match:
            raise ValueError("Unsupported export row: " + stripped)
        rows.append((int(match[1]), match[4]))
    else:
        raise ValueError("Export table has no Summary terminator.")
    names = [name for _, name in rows]
    if len(set(names)) != len(names) or len({o for o, _ in rows}) != len(rows):
        raise ValueError("Duplicate export name or ordinal.")
    if counts.get("functions") != len(rows) or counts.get("names") != len(rows):
        raise ValueError("Export counts do not match the parsed rows.")
    return names


def compare_exports(expected, actual) -> None:
    missing, extra = sorted(set(expected) - set(actual)), sorted(set(actual) - set(expected))
    if missing or extra or len(actual) != len(expected):
        raise RuntimeError(f"Export set differs from libass.sym; missing {missing[:10]}, extra {extra[:10]}.")


def _tokens(line: str) -> list:
    # Build-relative object and library paths contain no spaces; quotes only wrap absolute tool paths.
    return line.replace('"', " ").split()


def _norm(token: str) -> str:
    """Backslash path separators; a leading / is an MSVC option prefix (/out:, /Fo) and is kept."""
    return token[:1] + token[1:].replace("/", "\\")


def link_line(graph: str) -> str:
    lines = [line for line in graph.splitlines()
             if any(t.lower() == "/out:" + DLL.lower() for t in map(_norm, _tokens(line)))]
    if len(lines) != 1:
        raise RuntimeError("Expected exactly one libass.dll link command.")
    return lines[0]


def link_inputs(line: str, read_response) -> dict:
    tokens = []
    for token in _tokens(line):
        if token.startswith("@"):
            tokens += _tokens(read_response(token[1:]))  # kept by ninja -d keeprsp
        else:
            tokens.append(token)
    tokens = [_norm(t) for t in tokens]
    lower = [t.lower() for t in tokens]
    objects = [t for t in tokens if t.lower().endswith(".obj")]
    libraries = [t for t in tokens if t.lower().endswith(".lib") and not t.startswith("/")]
    implib = [t.split(":", 1)[1] for t in tokens if t.lower().startswith("/implib:")]
    return {"objects": objects, "project_libraries": [t for t in libraries if "\\" in t and not
                                                       re.match(r"[A-Za-z]:", t)],
            "absolute_libraries": [t for t in libraries if re.match(r"[A-Za-z]:", t)],
            "system_libraries": [t for t in libraries if "\\" not in t],
            "implib": implib, "ltcg": any(t.startswith("/ltcg") for t in lower), "machine_x64": "/machine:x64" in lower}


def check_link_graph(inputs: dict) -> None:
    problems = []
    if sorted(inputs["objects"]) != sorted(VENDOR_OBJECTS):
        problems.append("objects " + repr(sorted(set(inputs["objects"]) ^ set(VENDOR_OBJECTS))[:10]))
    if sorted(inputs["project_libraries"]) != sorted(VENDOR_STATIC_LIBRARIES):
        problems.append("static libraries " + repr(inputs["project_libraries"]))
    if inputs["absolute_libraries"]:
        problems.append("absolute libraries " + repr(inputs["absolute_libraries"][:5]))
    if len(inputs["implib"]) != 1 or not inputs["ltcg"] or not inputs["machine_x64"]:
        problems.append("implib/LTCG/x64")
    if problems:
        raise RuntimeError("ass link graph differs from the vendor x64 link: " + "; ".join(problems))


def _writes(line: str, flag: str, path: str) -> bool:
    """True when the command names path as its output, as `-o path` or `/Fopath` (or -Fo)."""
    tokens, path = [_norm(t).lower() for t in _tokens(line)], path.lower()
    if flag == "-o":
        return any(a == "-o" and b == path for a, b in zip(tokens, tokens[1:]))
    return any(t in ("/fo" + path, "-fo" + path) for t in tokens)


def check_assembly(graph: str) -> dict:
    """Every vendor ass_asm object is assembled as win64 with the libass x86-64 definitions."""
    lines = graph.splitlines()
    for name in ASM_NAMES:
        obj = _OBJ.format("ass_asm", "x86\\" + name + ".asm")
        hits = [line for line in lines if _writes(line, "-o", obj) and
                re.search(r"[\\/]libass[\\/]x86[\\/]" + name + r"\.asm(?![.\w])", line)]
        if len(hits) != 1:
            raise RuntimeError("Missing or repeated assembly command: " + name)
        tokens = _tokens(hits[0])
        if not ("-fwin64" in tokens or any(a == "-f" and b == "win64" for a, b in zip(tokens, tokens[1:]))) or \
                not {"-DARCH_X86_64=1", "-Dprivate_prefix=ass", "-DHAVE_ALIGNED_STACK=1"} <= set(tokens):
            raise RuntimeError("Assembly command lacks win64 x86-64 options: " + name)
    compile_c = [line for line in lines if _writes(line, "/Fo", _OBJ.format("ass-objs", "ass.c"))]
    if len(compile_c) != 1 or "CONFIG_ASM=1" not in compile_c[0] or "ARCH_X86_64=1" not in compile_c[0]:
        raise RuntimeError("ass.c is not compiled with CONFIG_ASM=1 and ARCH_X86_64=1.")
    if "NO_ASM" in graph:
        raise RuntimeError("NO_ASM appears in the build graph.")
    version = re.search(r"CONFIG_SOURCEVERSION=(.*?)(?=\s+[-/][A-Za-z]|$)", compile_c[0])
    return {"config_sourceversion_hosted": version[1] if version else None,
            "config_sourceversion_note": "From git describe in a shallow tag-less checkout; the vendor value is "
                                         "not retained and no identical version metadata is claimed."}


def inventory(directory: Path) -> dict:
    if not directory.is_dir():
        return {}
    return {p.name: {"bytes": p.stat().st_size, "sha256": digest(p)} for p in sorted(directory.iterdir())
            if p.is_file()}


def fribidi_proof(before: dict, after: dict, graph: str, build_log: str) -> list:
    """The exact seven generated outputs: absent before, new and non-empty after, with logged commands."""
    proof = []
    for name, generator in FRIBIDI_OUTPUTS.items():
        if name in before:
            raise RuntimeError("Generated FriBidi file existed before the build: " + name)
        if name not in after or after[name]["bytes"] <= 0:
            raise RuntimeError("Missing or empty generated FriBidi output: " + name)
        pattern = re.compile(re.escape(generator) + r"(\.exe)?\b[^\n]*?>\s*" + re.escape(name) + r"\b")
        if not pattern.search(graph) or not pattern.search(build_log):
            raise RuntimeError("Generator command not planned and logged for " + name)
        proof.append({"name": name, "generator": generator, **after[name]})
    other = sorted(set(after) - set(before) - set(FRIBIDI_OUTPUTS))
    if other:
        raise RuntimeError("Unexpected new gen.tab files: " + ", ".join(other[:10]))
    return proof


def check_text_evidence(directory: Path) -> None:
    for path in directory.rglob("*"):
        if path.is_file() and path.suffix.lower() not in (".json", ".log"):
            raise RuntimeError("Non-text evidence file: " + path.name)


class Run:
    def __init__(self, workspace: Path, environ=None, popen=None, run_tool=None, clock=time.monotonic,
                 sleep=time.sleep):
        environ = os.environ if environ is None else environ
        self.clock, self.sleep = clock, sleep
        self.popen = popen or subprocess.Popen
        self.run_tool = run_tool or subprocess.run
        self.start = clock()
        self.deadline = self.start + WHOLE_SECONDS
        self.evidence = workspace / "native-source-evidence"
        self.evidence.mkdir(exist_ok=False)
        self.work = Path(environ["RUNNER_TEMP"]) / (
            "gyroflowplus-libass-" + environ["GITHUB_RUN_ID"] + "-" + environ["GITHUB_RUN_ATTEMPT"])
        self.work.mkdir(exist_ok=False)
        self.private = self.work / "private"  # never uploaded
        self.private.mkdir()
        self.hooks = self.work / "empty-hooks"
        self.hooks.mkdir()
        self.env = normalize_windows_env(environ)
        self.env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
        self.tools = {}
        self.commands = []
        self.sources = []
        self.log_total = 0

    def save(self, name, value):
        (self.evidence / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def stop_tree(self, process) -> list:
        """Stop only the process tree rooted at our own child; our open handle keeps its PID from reuse."""
        notes = []
        try:
            result = self.run_tool(["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, timeout=15, check=False)
            notes.append({"step": "taskkill own PID tree", "exit_code": result.returncode})
        except Exception as exc:
            notes.append({"step": "taskkill own PID tree", "error": type(exc).__name__})
        for step in ("wait", "terminate own handle"):
            try:
                if step != "wait":
                    process.kill()
                process.wait(timeout=15)
                notes.append({"step": step, "exit_code": process.returncode})
                break
            except Exception as exc:
                notes.append({"step": step, "error": type(exc).__name__})
        return notes

    def command(self, args, cwd=None, seconds=300, private=False, cmdline=None):
        """Run one bounded command and keep its receipt whatever happens; private output is never uploaded."""
        args = [str(x) for x in args]
        number = len(self.commands) + 1
        log = (self.private if private else self.evidence) / f"command-{number:03d}.log"
        began = self.clock()
        limit = min(self.deadline, began + seconds)
        cap = MAX_LOG_BYTES if private else min(MAX_LOG_BYTES, MAX_TOTAL_LOG_BYTES - self.log_total)
        if began >= limit or cap <= 0:
            raise RuntimeError("Whole-run deadline or aggregate log bound reached before command.")
        record = {"number": number, "argv": [cmdline] if cmdline else args, "cwd": str(cwd or self.work),
                  "log": None if private else log.name, "private_output": private, "status": "started",
                  "started_utc": utc(), "started_after_seconds": round(began - self.start, 3),
                  "seconds_allowed": round(limit - began, 3), "log_cap_bytes": cap}
        self.commands.append(record)
        self.save("COMMANDS.json", self.commands)
        process, stopped, cleanup = None, None, []
        try:
            with log.open("wb") as output:
                process = self.popen(cmdline or args, cwd=cwd or self.work, env=self.env,
                                     stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                     creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
                record["pid"] = process.pid
                while process.poll() is None:
                    if self.clock() >= limit:
                        stopped = "deadline"
                    elif log.stat().st_size > cap:
                        stopped = "log bound"
                    if stopped:
                        cleanup = self.stop_tree(process)
                        break
                    self.sleep(POLL_SECONDS)
        except BaseException as exc:
            record["runner_error"] = type(exc).__name__ + ": " + str(exc)[:300]
            if process is not None and process.returncode is None and not cleanup:
                cleanup = self.stop_tree(process)
            raise
        finally:
            size = log.stat().st_size if log.exists() else 0
            if size > cap and not stopped:
                stopped = "log bound"  # exited between polls with more output than the cap
            record.update(status=stopped or ("runner error" if "runner_error" in record else "exited"),
                          exit_code=None if process is None else process.returncode, stopped=stopped,
                          cleanup=cleanup, ended_utc=utc(), seconds=round(self.clock() - began, 3), bytes=size)
            if not private and size:
                record["sha256"] = digest(log)
                if size > cap:
                    with log.open("r+b") as handle:
                        handle.truncate(cap)
                    record["retained_bytes"] = cap
            if not private:
                self.log_total += min(size, cap)
            self.save("COMMANDS.json", self.commands)
        data = log.read_bytes()
        if private:
            log.unlink()
        if stopped or process.returncode:
            raise RuntimeError(f"Command {number} failed ({stopped or 'exit ' + str(process.returncode)}).")
        return data if private else data.decode("utf-8", errors="replace")

    def git(self, args, cwd=None):
        return self.command([self.tools["git.exe"], "-c", "credential.helper=", "-c", "core.autocrlf=false",
                             "-c", "core.hooksPath="+str(self.hooks), "-c", "submodule.recurse=false",
                             "-c", "protocol.file.allow=never", "-c", "protocol.ext.allow=never", *args], cwd, 60)

    def acquire(self):
        git = shutil.which("git.exe", path=self.env.get("PATH"))
        if not git:
            raise RuntimeError("Missing required tool: git.exe")
        self.tools["git.exe"] = git
        for location, repository, commit in SOURCES:
            destination = self.work / location
            destination.mkdir(parents=True, exist_ok=True)
            # Parent checkouts contain empty gitlink directories. Never reuse an existing Git checkout.
            if (destination / ".git").exists():
                raise RuntimeError("Source checkout already exists.")
            self.git(["init", str(destination)])
            self.git(["remote", "add", "origin", "https://github.com/"+repository+".git"], destination)
            self.git(["fetch", "--no-tags", "--depth=1", "origin", commit], destination)
            self.git(["checkout", "--detach", "FETCH_HEAD"], destination)
            actual = self.git(["rev-parse", "HEAD"], destination).strip()
            if actual != commit:
                raise RuntimeError("Source commit mismatch.")
            self.git(["fsck", "--strict", "--no-reflogs", "--no-dangling"], destination)
            tree = self.git(["rev-parse", "HEAD^{tree}"], destination).strip()
            self.sources.append({"path":location, "repository":repository, "commit":actual, "tree":tree})
            self.save("SOURCES.json", self.sources)

    def developer_environment(self, developer: Path) -> None:
        text = str(developer)
        if any(c in text for c in '"%^&|<>!\r\n'):
            raise RuntimeError("Unsupported developer script path.")
        # Passed verbatim: a list would be re-quoted with \" which cmd.exe does not understand.
        cmdline = f'cmd.exe /d /s /c ""{text}" -no_logo -arch=x64 -host_arch=x64 >nul && set"'
        captured = self.command([], seconds=120, private=True, cmdline=cmdline)
        self.env = merge_windows_env(self.env, captured.decode("oem" if sys.platform == "win32" else "utf-8"))

    def toolchain(self):
        vswhere = Path(self.env["PROGRAMFILES(X86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
        install = self.command([vswhere, "-latest", "-products", "*", "-requires",
                                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"]).strip()
        developer = Path(install) / "Common7/Tools/VsDevCmd.bat"
        if not developer.is_file():
            raise RuntimeError("MSVC developer environment unavailable.")
        self.developer_environment(developer)
        # Child lookup on Windows uses this process's PATH, not env=; always call tools by resolved path.
        for tool in TOOLS:
            path = shutil.which(tool, path=self.env["PATH"])
            if not path:
                raise RuntimeError("Missing required tool: "+tool)
            self.tools[tool] = path
            self.save(tool+".json", {"tool":tool, "path":path, "sha256":digest(Path(path))})
        self.command([self.tools["cmake.exe"], "--version"])
        self.command([self.tools["ninja.exe"], "--version"])
        self.command([self.tools["perl.exe"], "-e", "print $^V"])

    def build(self):
        nasm = self.work / "nasm"
        before = {p: (nasm / p).is_file() for p in NASM_PERLREQ}
        self.command([self.tools["nmake.exe"], "/f", "Mkfiles/msvc.mak", "perlreq"], nasm, 300)
        missing = [p for p in NASM_PERLREQ if not (nasm / p).is_file() or not (nasm / p).stat().st_size]
        if missing:
            raise RuntimeError("NASM perlreq did not produce: " + ", ".join(missing[:10]))
        self.command([self.tools["nmake.exe"], "/f", "Mkfiles/msvc.mak", "nasm.exe"], nasm, 300)
        version = self.command([nasm / "nasm.exe", "-v"], nasm)
        if not version.startswith("NASM version 2.16.01 "):
            raise RuntimeError("Unexpected NASM version.")
        source = self.work / "devpkgs"
        build = self.work / "build"
        gen_tab = source / "src/fribidi/gen.tab"
        fribidi_before = inventory(gen_tab)
        ninja = [self.tools["ninja.exe"], "-C", build]
        self.command([self.tools["cmake.exe"], "-S", source, "-B", build, "-G", "Ninja",
                      "-DCMAKE_MAKE_PROGRAM="+self.tools["ninja.exe"],
                      "-DCMAKE_BUILD_TYPE=Release", "-DCMAKE_SYSTEM_PROCESSOR=x64",
                      "-DCMAKE_SYSTEM_VERSION=6.0", "-DMIN_SIZE=1", "-DUSE_ARC=0",
                      "-DWITH_LTO_STATIC=1", "-DCMAKE_VERBOSE_MAKEFILE=1", "-DFRIBIDI_GENTAB=1",
                      "-DBUILD_LIBASS=1", "-DBUILD_FT=1", "-DBUILD_HB=1", "-DBUILD_WOLFSSL=0",
                      "-DBUILD_DAV1D=0", "-DBUILD_VALD=0", "-DBUILD_LZ4=0", "-DBUILD_TESTING=0",
                      "-DFETCHCONTENT_FULLY_DISCONNECTED=ON", "-DFETCHCONTENT_UPDATES_DISCONNECTED=ON",
                      "-DCMAKE_ASM_NASM_COMPILER="+str(nasm / "nasm.exe"),
                      "-DCMAKE_INSTALL_PREFIX="+str(self.work / "unused-install")], seconds=300)
        graph = self.command(ninja + ["-t", "commands", "ass"])
        assembly = check_assembly(graph)
        line = link_line(graph)
        first_log = self.command(ninja + ["-j", "2", "-v", "-d", "keeprsp", "ass"], seconds=600)
        inputs = link_inputs(line, lambda p: (build / p).read_text(encoding="utf-8", errors="strict"))
        check_link_graph(inputs)
        dll = build / DLL.replace("\\", "/")
        binary = dll.read_bytes()
        pe = struct.unpack_from("<I", binary, 0x3c)[0]
        if binary[pe:pe+4] != b"PE\0\0" or struct.unpack_from("<H", binary, pe+4)[0] != 0x8664:
            raise RuntimeError("Rebuilt output is not an x64 PE DLL.")
        expected = parse_symbol_file((source / "src/libass/libass/libass.sym").read_text(encoding="utf-8"))
        first_exports = parse_dumpbin_exports(self.command([self.tools["dumpbin.exe"], "/exports", dll]))
        compare_exports(expected, first_exports)
        # The link step itself rewrites the DLL, its import library and .exp; everything else must not change.
        implib = build / inputs["implib"][0].replace("\\", "/")
        link_outputs = {implib.resolve(), implib.with_suffix(".exp").resolve()}
        products = {str(p.relative_to(build)):digest(p) for p in build.rglob("*")
                    if p.is_file() and p.suffix.lower() in (".obj", ".lib") and p.resolve() not in link_outputs}
        if not all(o.replace("\\", os.sep) in products for o in VENDOR_OBJECTS + VENDOR_STATIC_LIBRARIES):
            raise RuntimeError("Missing relink objects or static libraries.")
        first = digest(dll)
        # Only delete our fresh generated DLL. Retain every source/object/static library, then relink.
        dll.unlink()
        relink_log = self.command(ninja + ["-j", "2", "-v", "ass"], seconds=180)
        changed = sorted(p for p, h in products.items() if digest(build / p) != h)
        if changed:
            raise RuntimeError("Relink changed retained object/static-library bytes: " + ", ".join(changed[:5]))
        again = parse_dumpbin_exports(self.command([self.tools["dumpbin.exe"], "/exports", dll]))
        compare_exports(first_exports, again)
        fribidi = fribidi_proof(fribidi_before, inventory(gen_tab), graph, first_log)
        self.save("BUILD-PROOF.json", {
            "assembly_enabled": True, **assembly, "link_graph": inputs, "exports": expected,
            "nasm_perlreq_present_before": before, "first_dll_sha256": first,
            "relinked_dll_sha256": digest(dll), "relink_command_lines": len(relink_log.splitlines()),
            "link_outputs_excluded": sorted(str(p.name) for p in link_outputs),
            "object_and_static_library_sha256": products, "relink_objects_unchanged": True,
            "generated_fribidi_outputs": fribidi, "limits": NOT_RUN})


def main():
    require_host()
    run = Run(Path(os.environ["GITHUB_WORKSPACE"]))
    run.save("RESULT.json", {"status": "started", "started_utc": utc(), "public_release_approved": False})
    try:
        run.acquire()
        run.toolchain()
        run.build()
    except BaseException as exc:
        run.save("RESULT.json", {"status":"failed", "error_type":type(exc).__name__,
                                 "error":str(exc)[:500], "seconds":run.clock()-run.start,
                                 "ended_utc": utc(), "public_release_approved":False})
        raise
    finally:
        check_text_evidence(run.evidence)
    run.save("RESULT.json", {"status":"source build and relink passed", "seconds":run.clock()-run.start,
                             "ended_utc": utc(), "public_release_approved":False,
                             "complete_corresponding_source":False,
                             "app_runtime_or_installed_files_changed":False, "limits": NOT_RUN})


if __name__ == "__main__":
    main()
