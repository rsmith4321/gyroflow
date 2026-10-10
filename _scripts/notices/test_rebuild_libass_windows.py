#!/usr/bin/env python3
"""Pure standard-library tests of our libass hosted-build glue. Everything external is mocked.

Run: python3 -I _scripts/notices/test_rebuild_libass_windows.py
V13_CANDIDATE_DIR and V13_WORKFLOW_PATH may name isolated reviewed candidate files.
V13_LIBASS_SYM may name the pinned libass.sym for the optional 50-export fixture.

No Windows runner, source build, compiler, assembler, generator, Perl, DLL, network or real
subprocess is used: subprocess.Popen/run are replaced for the whole module and fail if reached.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
CANDIDATE = Path(os.environ.get("V13_CANDIDATE_DIR", HERE))
WORKFLOW_PATH = Path(os.environ.get("V13_WORKFLOW_PATH", HERE.parents[1] / ".github/workflows/native-libass-source.yml"))
STATEMENT = ("NO WINDOWS BUILD OR SOURCE BUILD HAS RUN: no compiler, assembler, generator, Perl, DLL, network "
             "or real subprocess was executed; every external call below is mocked.")


def load():
    spec = importlib.util.spec_from_file_location("rebuild_candidate", CANDIDATE / "rebuild_libass_windows.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # module body defines constants and functions only
    return module


m = load()
_guards = []


def _forbidden(*args, **kwargs):
    raise AssertionError("real subprocess reached: %r" % (args[:1],))


def setUpModule():
    print("\n" + STATEMENT, file=sys.stderr)
    for name in ("Popen", "run", "call", "check_call", "check_output"):
        patcher = mock.patch.object(m.subprocess, name, _forbidden)
        patcher.start()
        _guards.append(patcher)


def tearDownModule():
    for patcher in _guards:
        patcher.stop()
    print(STATEMENT, file=sys.stderr)


BRANCH = "codex/lut-preview-controls"
GOOD_ENV = {
    "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Windows",
    "GITHUB_REPOSITORY": "rsmith4321/gyroflow-plus", "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_REF": "refs/heads/" + BRANCH, "GITHUB_REF_TYPE": "branch", "GITHUB_REF_NAME": BRANCH,
    "GITHUB_WORKFLOW_REF": "rsmith4321/gyroflow-plus/.github/workflows/native-libass-source.yml@refs/heads/" + BRANCH,
    "GITHUB_RUN_ID": "123456789", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40,
    "GITHUB_WORKSPACE": "D:\\a\\gyroflow-plus\\gyroflow-plus", "RUNNER_TEMP": "D:\\a\\_temp"}


class Admission(unittest.TestCase):
    def test_manual_dispatch_on_default_branch_is_admitted(self):
        self.assertEqual(m.admission_errors(GOOD_ENV, "win32"), [])

    def check(self, change, platform="win32", expect=None):
        env = dict(GOOD_ENV, **change)
        errors = m.admission_errors(env, platform)
        self.assertTrue(errors, change)
        if expect:
            self.assertIn(expect, errors)

    def test_wrong_repository_or_fork(self):
        self.check({"GITHUB_REPOSITORY": "someone/gyroflow-plus"}, expect="GITHUB_REPOSITORY")
        self.check({"GITHUB_REPOSITORY": "rsmith4321/Gyroflow-Plus"}, expect="GITHUB_REPOSITORY")

    def test_wrong_event(self):
        for event in ("push", "pull_request", "pull_request_target", "schedule", "release", "repository_dispatch"):
            self.check({"GITHUB_EVENT_NAME": event}, expect="GITHUB_EVENT_NAME")

    def test_wrong_ref(self):
        for ref in ("refs/heads/main", "refs/heads/master", "refs/tags/" + BRANCH,
                    "refs/heads/" + BRANCH + "-x", "refs/pull/1/merge", "refs/heads/qualification/native-libass-source"):
            self.check({"GITHUB_REF": ref}, expect="GITHUB_REF")
        self.check({"GITHUB_REF_TYPE": "tag"}, expect="GITHUB_REF_TYPE")
        self.check({"GITHUB_REF_NAME": "main"}, expect="GITHUB_REF_NAME")
        self.check({"GITHUB_WORKFLOW_REF": GOOD_ENV["GITHUB_WORKFLOW_REF"].replace(BRANCH, "main")},
                   expect="GITHUB_WORKFLOW_REF")

    def test_wrong_runner(self):
        self.check({"RUNNER_ENVIRONMENT": "self-hosted"}, expect="RUNNER_ENVIRONMENT")
        self.check({"RUNNER_OS": "macOS"}, expect="RUNNER_OS")
        self.check({}, platform="darwin", expect="sys.platform")
        self.check({"GITHUB_ACTIONS": ""}, expect="GITHUB_ACTIONS")

    def test_bad_run_identity(self):
        self.check({"GITHUB_RUN_ID": "12a"}, expect="GITHUB_RUN_ID")
        self.check({"GITHUB_RUN_ATTEMPT": ""}, expect="GITHUB_RUN_ATTEMPT")
        self.check({"GITHUB_SHA": "0" * 40}, expect="GITHUB_SHA")
        self.check({"GITHUB_SHA": "A" * 40}, expect="GITHUB_SHA")

    def test_missing_keys(self):
        for key in GOOD_ENV:
            env = dict(GOOD_ENV)
            del env[key]
            self.assertTrue(m.admission_errors(env, "win32"), key)

    def test_require_host_exits_on_this_machine(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                m.require_host()


class WindowsEnvironment(unittest.TestCase):
    def test_mixed_case_path_leaves_one_current_value(self):
        merged = m.merge_windows_env({"PATH": "C:\\old", "SystemRoot": "C:\\Windows"},
                                     "Path=C:\\VC\\bin;C:\\old\r\nINCLUDE=C:\\VC\\include\r\n=C:=C:\\work\r\n")
        self.assertEqual(merged["PATH"], "C:\\VC\\bin;C:\\old")
        self.assertEqual([k for k in merged if k.upper() == "PATH"], ["PATH"])
        self.assertEqual(merged["SYSTEMROOT"], "C:\\Windows")
        self.assertNotIn("=C:", merged)

    def test_lower_case_base_is_replaced_too(self):
        merged = m.merge_windows_env({"Path": "C:\\stale"}, "PATH=C:\\new\n")
        self.assertEqual(merged, {"PATH": "C:\\new"})

    def test_ambiguous_base_is_refused(self):
        with self.assertRaises(ValueError):
            m.normalize_windows_env({"PATH": "a", "Path": "b"})
        self.assertEqual(m.normalize_windows_env({"PATH": "a", "Path": "a"}), {"PATH": "a"})

    def test_duplicate_or_missing_path_in_capture(self):
        with self.assertRaises(ValueError):
            m.merge_windows_env({}, "Path=a\nPATH=b\n")
        with self.assertRaises(ValueError):
            m.merge_windows_env({"PATH": "a"}, "INCLUDE=x\n")

    def test_value_with_equals_sign_kept(self):
        self.assertEqual(m.merge_windows_env({}, "PATH=a\nX=b=c\n")["X"], "b=c")


DUMPBIN = """Microsoft (R) COFF/PE Dumper Version 14.44.35211.0
Copyright (C) Microsoft Corporation.  All rights reserved.


Dump of file build\\projects\\libass\\libass.dll

File Type: DLL

  Section contains the following exports for libass.dll

    00000000 characteristics
    FFFFFFFF time date stamp
        0.00 version
           1 ordinal base
           {n} number of functions
           {n} number of names

    ordinal hint RVA      name

{rows}
  Summary

        1000 .data
       2D000 .text
"""


def dumpbin(names, extra_rows=(), functions=None, count=None):
    rows = ["%11d %4X %08X %s" % (i + 1, i, 0x1000 + 16 * i, n) for i, n in enumerate(names)]
    rows += list(extra_rows)
    n = len(rows) if count is None else count
    text = DUMPBIN.format(n=n, rows="\n".join(rows))
    if functions is not None:
        text = text.replace("%d number of functions" % n, "%d number of functions" % functions)
    return text


SYM = ["ass_library_init", "ass_library_done", "ass_render_frame", "ass_set_fonts"]


class Exports(unittest.TestCase):
    def test_representative_table_parses_all_names(self):
        self.assertEqual(m.parse_dumpbin_exports(dumpbin(SYM)), SYM)
        m.compare_exports(SYM, m.parse_dumpbin_exports(dumpbin(SYM)))

    def test_extra_export_not_named_ass_is_caught(self):
        names = m.parse_dumpbin_exports(dumpbin(SYM + ["hb_buffer_create"]))
        with self.assertRaises(RuntimeError):
            m.compare_exports(SYM, names)

    def test_missing_export(self):
        with self.assertRaises(RuntimeError):
            m.compare_exports(SYM, m.parse_dumpbin_exports(dumpbin(SYM[:-1])))

    def test_duplicate_name(self):
        with self.assertRaises(ValueError):
            m.parse_dumpbin_exports(dumpbin(SYM + ["ass_set_fonts"]))

    def test_forwarded_ordinal_only_and_decorated_rows(self):
        for row in ("          9    8          ass_x (forwarded to OTHER.ass_x)",
                    "          9      00001000 [NONAME]",
                    "          9    8 00001000 ass_x = ass_x",
                    "          9    8 00001000 ?ass@@YAXXZ",
                    "garbage"):
            with self.assertRaises(ValueError, msg=row):
                m.parse_dumpbin_exports(dumpbin(SYM, extra_rows=[row]))

    def test_count_mismatch_and_layout(self):
        with self.assertRaises(ValueError):
            m.parse_dumpbin_exports(dumpbin(SYM, count=5))
        with self.assertRaises(ValueError):
            m.parse_dumpbin_exports(dumpbin(SYM, functions=9))
        with self.assertRaises(ValueError):
            m.parse_dumpbin_exports("no table here")
        with self.assertRaises(ValueError):
            m.parse_dumpbin_exports(dumpbin(SYM).replace("  Summary", ""))
        text = dumpbin(SYM)
        with self.assertRaises(ValueError):
            m.parse_dumpbin_exports(text + text)

    def test_symbol_file(self):
        self.assertEqual(m.parse_symbol_file("ass_a\r\n\nass_b\n"), ["ass_a", "ass_b"])
        for bad in ("", "\n\n", "ass_a\nass_a\n", "ass_a\n# comment\n", "ass_a ass_b\n"):
            with self.assertRaises(ValueError, msg=bad):
                m.parse_symbol_file(bad)

    def test_real_libass_sym_if_available(self):
        path = os.environ.get("V13_LIBASS_SYM")
        if not path:
            self.skipTest("V13_LIBASS_SYM not set")
        names = m.parse_symbol_file(Path(path).read_text())
        self.assertEqual(len(names), 50)
        self.assertEqual(m.parse_dumpbin_exports(dumpbin(names)), names)


OUTPUTS = m.FRIBIDI_OUTPUTS


def fribidi_commands():
    return "\n".join(
        'cmd.exe /C "cd . && link.exe /out:projects\\fribidi\\%s.exe && cd /D D:\\a\\_temp\\r\\devpkgs\\src\\fribidi\\'
        'gen.tab && D:\\a\\_temp\\r\\build\\projects\\fribidi\\%s.exe 2 unidata/UnicodeData.txt >%s"' % (g, g, n)
        for n, g in OUTPUTS.items())


CHECKED_IN = {n: {"bytes": 10, "sha256": "0" * 64} for n in ("gen-bidi-type-tab.c", "packtab.c", "meson.build")}


def after_with(names, size=100):
    after = dict(CHECKED_IN)
    after.update({n: {"bytes": size, "sha256": hashlib.sha256(n.encode()).hexdigest()} for n in names})
    return after


class FriBidi(unittest.TestCase):
    def test_exact_seven_with_commands(self):
        proof = m.fribidi_proof(CHECKED_IN, after_with(OUTPUTS), fribidi_commands(), fribidi_commands())
        self.assertEqual(sorted(p["name"] for p in proof), sorted(OUTPUTS))
        self.assertEqual(len(proof), 7)
        self.assertTrue(all(p["bytes"] > 0 and len(p["sha256"]) == 64 for p in proof))

    def test_headers_only_is_rejected(self):
        with self.assertRaises(RuntimeError):
            m.fribidi_proof(CHECKED_IN, after_with(["fribidi-unicode-version.h"]), fribidi_commands(),
                            fribidi_commands())

    def test_each_missing_or_empty_output(self):
        for name in OUTPUTS:
            with self.assertRaises(RuntimeError, msg=name):
                m.fribidi_proof(CHECKED_IN, after_with([n for n in OUTPUTS if n != name]), fribidi_commands(),
                                fribidi_commands())
            after = after_with(OUTPUTS)
            after[name] = {"bytes": 0, "sha256": hashlib.sha256(b"").hexdigest()}
            with self.assertRaises(RuntimeError, msg=name):
                m.fribidi_proof(CHECKED_IN, after, fribidi_commands(), fribidi_commands())

    def test_preexisting_file_does_not_prove_generation(self):
        before = dict(CHECKED_IN, **{"mirroring.tab.i": {"bytes": 5, "sha256": "1" * 64}})
        with self.assertRaises(RuntimeError):
            m.fribidi_proof(before, after_with(OUTPUTS), fribidi_commands(), fribidi_commands())

    def test_command_must_be_planned_and_logged(self):
        log = "\n".join(l for l in fribidi_commands().splitlines() if "brackets-type.tab.i" not in l)
        with self.assertRaises(RuntimeError):
            m.fribidi_proof(CHECKED_IN, after_with(OUTPUTS), fribidi_commands(), log)
        with self.assertRaises(RuntimeError):
            m.fribidi_proof(CHECKED_IN, after_with(OUTPUTS), log, fribidi_commands())

    def test_unexpected_new_file(self):
        with self.assertRaises(RuntimeError):
            m.fribidi_proof(CHECKED_IN, after_with(list(OUTPUTS) + ["derived_bidi-type.tab.i"]),
                            fribidi_commands(), fribidi_commands())

    def test_inventory_reads_regular_files(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.tab.i").write_bytes(b"x")
            Path(d, "sub").mkdir()
            self.assertEqual(m.inventory(Path(d)), {"a.tab.i": {"bytes": 1,
                             "sha256": hashlib.sha256(b"x").hexdigest()}})
            self.assertEqual(m.inventory(Path(d, "missing")), {})


def graph(objects=None, libs=None, rsp=True, asm_flags="-f win64 -DHAVE_ALIGNED_STACK=1 -DHAVE_CPUNOP=0 -Dprivate_prefix=ass",
          c_defs="-DCONFIG_ASM=1 -DARCH_X86=1 -DARCH_X86_64=1"):
    objects = list(m.VENDOR_OBJECTS if objects is None else objects)
    libs = list(m.VENDOR_STATIC_LIBRARIES if libs is None else libs)
    lines = []
    for name in m.ASM_NAMES:
        obj = m._OBJ.format("ass_asm", "x86\\" + name + ".asm")
        lines.append('"C:\\a\\_temp\\r\\nasm\\nasm.exe" -DARCH_X86_64=1 -DPIC=1 %s -f win64 -o %s '
                     'D:\\a\\_temp\\r\\devpkgs\\src\\libass\\libass\\x86\\%s.asm' % (asm_flags, obj, name))
    lines.append('"C:\\VC\\cl.exe" /nologo %s -DCONFIG_SOURCEVERSION="\\"commit: af5f116d\\"" /MD /Fo%s '
                 '/Fdprojects\\libass\\CMakeFiles\\ass-objs.dir\\ -c D:\\a\\_temp\\r\\devpkgs\\src\\libass\\libass\\ass.c'
                 % (c_defs, m._OBJ.format("ass-objs", "ass.c")))
    body = " ".join(objects + libs + ["gdi32.lib", "user32.lib", "kernel32.lib"])
    link = ('cmd.exe /C "cd . && "C:\\cmake\\bin\\cmake.exe" -E vs_link_dll --intdir=projects\\libass\\CMakeFiles\\ass.dir '
            '-- "C:\\VC\\link.exe" /nologo %s /out:projects\\libass\\libass.dll /implib:projects\\libass\\ass.lib '
            '/pdb:projects\\libass\\libass.pdb /dll /version:0.0 /machine:x64 /LTCG /INCREMENTAL:NO '
            '/DEF:projects\\libass\\ass.def && cd ."') % ("@CMakeFiles\\ass.rsp" if rsp else body)
    lines.append(link)
    return "\n".join(lines), body


class BuildGraph(unittest.TestCase):
    def test_vendor_graph_with_response_file(self):
        text, body = graph()
        info = m.check_assembly(text)
        self.assertIn("af5f116d", info["config_sourceversion_hosted"])
        inputs = m.link_inputs(m.link_line(text), lambda p: body if p == "CMakeFiles\\ass.rsp" else 1 / 0)
        m.check_link_graph(inputs)
        self.assertEqual(inputs["implib"], ["projects\\libass\\ass.lib"])

    def test_vendor_graph_inline(self):
        text, body = graph(rsp=False)
        m.check_assembly(text)
        m.check_link_graph(m.link_inputs(m.link_line(text), lambda p: 1 / 0))

    def test_missing_assembly_object(self):
        objects = [o for o in m.VENDOR_OBJECTS if "cpuid" not in o]
        text, body = graph(objects=objects, rsp=False)
        with self.assertRaises(RuntimeError):
            m.check_link_graph(m.link_inputs(m.link_line(text), None))

    def test_unrelated_or_missing_static_library(self):
        for libs in (list(m.VENDOR_STATIC_LIBRARIES) + ["src\\lz4\\lz4.lib"], list(m.VENDOR_STATIC_LIBRARIES)[:2],
                     list(m.VENDOR_STATIC_LIBRARIES) + ["C:\\vcpkg\\installed\\x64\\lib\\freetype.lib"]):
            text, body = graph(libs=libs, rsp=False)
            with self.assertRaises(RuntimeError, msg=libs):
                m.check_link_graph(m.link_inputs(m.link_line(text), None))

    def test_assembly_options_required(self):
        with self.assertRaises(RuntimeError):
            m.check_assembly(graph(asm_flags="-DHAVE_CPUNOP=0 -Dprivate_prefix=ass")[0])
        with self.assertRaises(RuntimeError):
            m.check_assembly(graph(c_defs="-DCONFIG_ASM=0 -DARCH_X86_64=0")[0])
        with self.assertRaises(RuntimeError):
            m.check_assembly(graph()[0] + "\nNO_ASM=1")
        text = graph()[0].splitlines()
        with self.assertRaises(RuntimeError):
            m.check_assembly("\n".join(l for l in text if "x86inc.asm.obj" not in l or "link.exe" in l))

    def test_link_line_must_be_unique(self):
        text = graph()[0]
        with self.assertRaises(RuntimeError):
            m.link_line(text + "\n" + text.splitlines()[-1])
        with self.assertRaises(RuntimeError):
            m.link_line(text.replace("/out:projects\\libass\\libass.dll", "/out:projects\\libass\\other.dll"))


class FakeProcess:
    def __init__(self, stdout, pid=4242, exits_after=None, returncode=0, write=b"", wait_errors=0):
        self.pid, self.returncode, self.polls = pid, None, 0
        self.exits_after, self.code, self.wait_errors, self.killed = exits_after, returncode, wait_errors, False
        stdout.write(write)
        stdout.flush()

    def poll(self):
        self.polls += 1
        if self.exits_after is not None and self.polls >= self.exits_after:
            self.returncode = self.code
        return self.returncode

    def wait(self, timeout=None):
        if self.wait_errors:
            self.wait_errors -= 1
            raise subprocess.TimeoutExpired("fake", timeout)
        if self.returncode is None:
            self.returncode = 1
        return self.returncode

    def kill(self):
        self.killed = True


class Clock:
    def __init__(self, step=1.0):
        self.now, self.step = 1000.0, step

    def __call__(self):
        self.now += self.step
        return self.now


class Runner(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "ws").mkdir()
        (root / "temp").mkdir()
        self.environ = {"RUNNER_TEMP": str(root / "temp"), "GITHUB_RUN_ID": "7", "GITHUB_RUN_ATTEMPT": "1",
                        "PATH": "C:\\runner", "Path": "C:\\runner"}
        self.killed = []
        self.popen_args = []

    def tearDown(self):
        self.tmp.cleanup()

    def make(self, process_factory, taskkill=None, clock=None):
        def popen(args, **kwargs):
            commands = json.loads((run.evidence / "COMMANDS.json").read_text())
            self.assertEqual(commands[-1]["status"], "started")  # start diagnostics written first
            self.popen_args.append(args)
            return process_factory(kwargs["stdout"])

        def run_tool(argv, **kwargs):
            self.killed.append(argv)
            if taskkill:
                raise taskkill
            return subprocess.CompletedProcess(argv, 0)

        run = m.Run(Path(self.tmp.name, "ws"), environ=self.environ, popen=popen, run_tool=run_tool,
                    clock=clock or Clock(0.01), sleep=lambda s: None)
        return run

    def receipt(self, run):
        return json.loads((run.evidence / "COMMANDS.json").read_text())[-1]

    def test_success_returns_log_and_receipt(self):
        run = self.make(lambda out: FakeProcess(out, exits_after=1, write=b"cmake version 3.31\n"))
        self.assertIn("cmake version", run.command(["cmake", "--version"]))
        r = self.receipt(run)
        self.assertEqual((r["status"], r["exit_code"], r["bytes"]), ("exited", 0, 19))
        self.assertEqual(r["sha256"], hashlib.sha256(b"cmake version 3.31\n").hexdigest())
        self.assertTrue(r["started_utc"] and r["ended_utc"])
        self.assertEqual(self.killed, [])

    def test_nonzero_exit_fails_with_receipt(self):
        run = self.make(lambda out: FakeProcess(out, exits_after=1, returncode=3))
        with self.assertRaises(RuntimeError):
            run.command(["ninja"])
        self.assertEqual(self.receipt(run)["exit_code"], 3)

    def test_deadline_kills_only_own_pid_tree_and_keeps_receipt_when_cleanup_fails(self):
        processes = []
        run = self.make(lambda out: processes.append(FakeProcess(out, pid=31337, wait_errors=2)) or processes[-1],
                        taskkill=subprocess.TimeoutExpired("taskkill", 15), clock=Clock(100.0))
        with self.assertRaises(RuntimeError):
            run.command(["ninja"], seconds=300)
        r = self.receipt(run)
        self.assertEqual(r["status"], "deadline")
        self.assertEqual(self.killed, [["taskkill.exe", "/PID", "31337", "/T", "/F"]])
        self.assertTrue(processes[0].killed)  # TerminateProcess on our own handle after taskkill/wait failed
        self.assertEqual([c["step"] for c in r["cleanup"]], ["taskkill own PID tree", "wait", "terminate own handle"])
        self.assertTrue(all("error" in c for c in r["cleanup"]))
        (run.evidence / "RESULT.json").write_text("{}")
        m.check_text_evidence(run.evidence)

    def test_no_name_based_or_global_kill_in_source(self):
        source = (CANDIDATE / "rebuild_libass_windows.py").read_text()
        self.assertNotRegex(source, r'"/IM"|/IM |taskkill[^\n]*\*|pkill|killall|os\.kill|shell=True')

    def test_per_command_log_bound_truncates_retained_log(self):
        self.environ = dict(self.environ)
        with mock.patch.object(m, "MAX_LOG_BYTES", 64):
            run = self.make(lambda out: FakeProcess(out, write=b"x" * 200))
            with self.assertRaises(RuntimeError):
                run.command(["ninja", "-v"])
        r = self.receipt(run)
        self.assertEqual((r["status"], r["bytes"], r["retained_bytes"]), ("log bound", 200, 64))
        self.assertEqual(r["sha256"], hashlib.sha256(b"x" * 200).hexdigest())
        self.assertEqual((run.evidence / r["log"]).stat().st_size, 64)

    def test_aggregate_log_bound(self):
        with mock.patch.object(m, "MAX_TOTAL_LOG_BYTES", 150), mock.patch.object(m, "MAX_LOG_BYTES", 100):
            run = self.make(lambda out: FakeProcess(out, exits_after=1, write=b"y" * 90))
            run.command(["a"])
            with self.assertRaises(RuntimeError):
                run.command(["b"])  # only 60 bytes of the aggregate remain
            self.assertEqual(self.receipt(run)["status"], "log bound")
            self.assertEqual(run.log_total, 150)
            calls = len(self.popen_args)
            with self.assertRaises(RuntimeError):
                run.command(["c"])  # nothing left: refused before start
            self.assertEqual(len(self.popen_args), calls)

    def test_launch_failure_keeps_receipt(self):
        def boom(out):
            raise FileNotFoundError("nmake.exe")
        run = self.make(boom)
        with self.assertRaises(FileNotFoundError):
            run.command(["nmake"])
        r = self.receipt(run)
        self.assertEqual(r["status"], "runner error")
        self.assertIn("FileNotFoundError", r["runner_error"])

    def test_whole_deadline_refuses_new_command(self):
        run = self.make(lambda out: FakeProcess(out, exits_after=1))
        run.deadline = run.clock() - 1
        with self.assertRaises(RuntimeError):
            run.command(["git"])
        self.assertEqual(self.popen_args, [])

    def test_mixed_case_runner_environment_is_normalized(self):
        run = self.make(lambda out: FakeProcess(out, exits_after=1))
        self.assertEqual([k for k in run.env if k.upper() == "PATH"], ["PATH"])


class Toolchain(unittest.TestCase):
    """Developer environment bootstrap through the bounded runner, private capture, resolved tool paths."""

    def test_bootstrap(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for sub in ("ws", "temp", "tools", "VS/Common7/Tools"):
                (root / sub).mkdir(parents=True)
            (root / "VS/Common7/Tools/VsDevCmd.bat").write_text("@rem fake\n")
            for tool in m.TOOLS:
                (root / "tools" / tool).write_bytes(tool.encode())
            new_path = "C:\\VC\\bin\\HostX64\\x64;C:\\runner"
            secret = "ghs_notarealtoken0000"
            environ = {"RUNNER_TEMP": str(root / "temp"), "GITHUB_RUN_ID": "7", "GITHUB_RUN_ATTEMPT": "1",
                       "Path": "C:\\runner", "ProgramFiles(x86)": "C:\\Program Files (x86)",
                       "ACTIONS_RUNTIME_TOKEN": secret}
            seen = []

            def popen(args, **kwargs):
                seen.append((args, kwargs["env"]))
                out = kwargs["stdout"]
                if isinstance(args, str):
                    data = ("Path=%s\r\nINCLUDE=C:\\VC\\include\r\nACTIONS_RUNTIME_TOKEN=%s\r\n" % (new_path, secret))
                elif args[0].endswith("vswhere.exe"):
                    data = str(root / "VS") + "\r\n"
                else:
                    data = "ok\n"
                return FakeProcess(out, exits_after=1, write=data.encode())

            def which(tool, path=None):
                return str(root / "tools" / tool) if path == new_path else None

            run = m.Run(root / "ws", environ=environ, popen=popen, run_tool=None, clock=Clock(0.01),
                        sleep=lambda s: None)
            with mock.patch.object(m.shutil, "which", which):
                run.toolchain()
            cmdline = seen[1][0]
            self.assertEqual(cmdline, 'cmd.exe /d /s /c ""%s" -no_logo -arch=x64 -host_arch=x64 >nul && set"'
                             % (root / "VS/Common7/Tools/VsDevCmd.bat"))
            self.assertEqual(run.env["PATH"], new_path)
            self.assertEqual([k for k in run.env if k.upper() == "PATH"], ["PATH"])
            self.assertEqual(seen[2][0][0], str(root / "tools/cmake.exe"))  # resolved path, not a bare name
            self.assertEqual(seen[2][1]["PATH"], new_path)
            evidence = "".join(p.read_text() for p in run.evidence.iterdir())
            self.assertNotIn(secret, evidence)
            self.assertNotIn("INCLUDE=", evidence)
            self.assertEqual(list((run.work / "private").iterdir()), [])
            capture = json.loads((run.evidence / "COMMANDS.json").read_text())[1]
            self.assertEqual((capture["private_output"], capture["log"], capture["status"]), (True, None, "exited"))
            self.assertNotIn("sha256", capture)

    def test_unsafe_developer_path_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "ws").mkdir()
            (root / "temp").mkdir()
            run = m.Run(root / "ws", environ={"RUNNER_TEMP": str(root / "temp"), "GITHUB_RUN_ID": "7",
                        "GITHUB_RUN_ATTEMPT": "1"}, popen=_forbidden, run_tool=_forbidden)
            for bad in ('C:\\a"b\\VsDevCmd.bat', "C:\\%x%\\VsDevCmd.bat", "C:\\a&b\\VsDevCmd.bat"):
                with self.assertRaises(RuntimeError):
                    run.developer_environment(Path(bad))


class Static(unittest.TestCase):
    def test_python_ast(self):
        tree = ast.parse((CANDIDATE / "rebuild_libass_windows.py").read_text())
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.keyword) and n.arg == "shell"]
        self.assertEqual(calls, [])
        strings = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
        self.assertIn("workflow_dispatch", strings)
        self.assertNotIn("push", strings)
        self.assertFalse(any("NO_ASM=1" in s or "-DNO_ASM" in s for s in strings))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        self.assertNotIn("eval", names)
        self.assertNotIn("exec", names)

    def test_workflow_text(self):
        text = WORKFLOW_PATH.read_text()
        body = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
        on = re.search(r"^on:\n((?:  .*\n)+)", body + "\n", re.M)[1]
        self.assertEqual(on, "  workflow_dispatch:\n")  # manual only, no inputs
        self.assertNotRegex(body, r"\bpush\b|pull_request|schedule|branches|tags:|contents: write|release|"
                                  r"secrets\.|\*\*|default_branch")
        self.assertIn("github.repository == '%s'" % m.REPOSITORY, body)
        self.assertIn("github.event_name == 'workflow_dispatch'", body)
        self.assertIn("github.ref == 'refs/heads/%s'" % m.BRANCH, body)
        self.assertRegex(body, r"(?m)^    timeout-minutes: 20$")
        self.assertRegex(body, r"(?m)^permissions:\n  contents: read$")
        self.assertIn("run: python -I _scripts/notices/rebuild_libass_windows.py", body)
        uploads = re.findall(r"(?m)^            (native-source-evidence/\S+)$", body)
        self.assertEqual(uploads, ["native-source-evidence/*.json", "native-source-evidence/*.log"])
        for line in body.splitlines():
            self.assertNotIn("\t", line)
            if "uses:" in line:
                self.assertRegex(line, r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main(verbosity=2)
