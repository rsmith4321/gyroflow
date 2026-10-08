#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Packaging guards; synthetic fixtures only, no app/video execution."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('package_plus', ROOT / '_scripts/package_plus.py')
stager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stager)


class StagingTests(unittest.TestCase):
    def test_dirty_and_untracked_source_is_refused_before_output_creation(self):
        with tempfile.TemporaryDirectory(prefix='plus-stage-test-') as temporary:
            root = Path(temporary)
            repo = root / 'repo'
            repo.mkdir()
            (repo / 'tracked.rs').write_text('initial source')
            def git(*args):
                subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)
            git('init')
            git('add', '.')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                'commit', '-m', 'Synthetic fixture')
            runtime = root / 'runtime'
            runtime.mkdir()
            binary = root / 'fixture.exe'
            binary.write_bytes(b'packaging fixture; never executed')
            output = root / 'stage'
            command = ['package_plus.py', 'windows', str(runtime), str(output),
                       '--binary', str(binary), '--development-runtime']
            for untracked in (False, True):
                with self.subTest(untracked=untracked):
                    if untracked:
                        (repo / 'tracked.rs').write_text('initial source')
                        (repo / 'new_color.rs').write_text('new source')
                    else:
                        (repo / 'tracked.rs').write_text('modified source')
                    with patch.object(stager, 'ROOT', repo), patch.object(sys, 'argv', command), \
                         contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
                        stager.main()
                    self.assertEqual(failure.exception.code, 2)
                    self.assertFalse(output.exists())


class MacDependencyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='plus-mach-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.app = self.root / 'Gyroflow Plus.app'
        self.app.mkdir()
        self.metadata = {}
        self.stage_app = None
        self.tool_calls = []
        self.mock = patch.object(stager.subprocess, 'run', side_effect=self.run_tool)
        self.mock.start()
        self.addCleanup(self.mock.stop)

    def slice(self, dependencies=(), rpaths=(), minimum='11.0', legacy=False):
        return dict(dependencies=dependencies, rpaths=rpaths, minimum=minimum, legacy=legacy)

    def binary(self, relative, slices):
        path = relative if isinstance(relative, Path) else self.app / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(bytes.fromhex('cffaedfe') + b'synthetic; never executed')
        self.metadata[path.resolve()] = slices
        return path

    def main_binary(self, data=None, architectures=('arm64',)):
        return self.binary('Contents/MacOS/gyroflow',
                           {architecture: data or self.slice() for architecture in architectures})

    def run_tool(self, args, **kwargs):
        self.tool_calls.append(tuple(args))
        if args[0] in ('codesign', 'git'):
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')
        path = Path(args[-1]).resolve()
        slices = self.metadata.get(path)
        if slices is None and self.stage_app and path.is_relative_to(self.stage_app):
            slices = self.metadata.get(self.app / path.relative_to(self.stage_app))
        if slices is None:
            return subprocess.CompletedProcess(args, 1, stdout='', stderr='No synthetic Mach-O')
        if args[:2] == ('lipo', '-archs'):
            return subprocess.CompletedProcess(args, 0, stdout=' '.join(slices) + '\n', stderr='')
        self.assertEqual(args[:2], ('otool', '-arch'))
        self.assertEqual(args[3], '-l')
        architecture = args[2]
        data = slices[architecture]
        # IDs are deliberately external; unlike LC_LOAD_DYLIB they are not loads.
        blocks = ['cmd LC_ID_DYLIB\nname /build/fixture-id.dylib (offset 24)']
        if data['legacy']:
            blocks.append(f'cmd LC_VERSION_MIN_MACOSX\nversion {data["minimum"]}\nsdk 14.0')
        else:
            blocks.append(f'cmd LC_BUILD_VERSION\nplatform 1\nminos {data["minimum"]}\nsdk 27.0')
        blocks += [f'cmd LC_RPATH\npath {value} (offset 12)' for value in data['rpaths']]
        blocks += [f'cmd LC_LOAD_DYLIB\nname {value} (offset 24)' for value in data['dependencies']]
        output = f'{path} (architecture {architecture}):\n' + ''.join(
            f'Load command {index}\n{block}\n' for index, block in enumerate(blocks))
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr='')

    def audit(self):
        return stager.check_mac_dependencies(self.app)

    def stage(self, development=False):
        repo = self.root / 'repo'
        for relative, value in (('Cargo.toml', '[package]\nversion="0.1.0-dev"\n'),
                                ('LICENSE', 'synthetic license fixture'),
                                ('resources/color/OCIO-LICENSE.txt', 'synthetic OCIO notice fixture'),
                                ('docs/PLUS-DISTRIBUTION.md', 'synthetic distribution fixture')):
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        notices = self.root / 'dependency-notices'
        notices.mkdir()
        (notices / 'NOTICE').write_text('Synthetic; does not establish license acceptance')
        plist = self.app / 'Contents/Info.plist'
        with plist.open('wb') as stream:
            plistlib.dump({'LSMinimumSystemVersion': '11.0'}, stream)
        output = self.root / 'stage'
        self.stage_app = output / 'Gyroflow Plus.app'
        command = ['package_plus.py', 'mac', str(self.app), str(output),
                   '--binary', str(self.app / 'Contents/MacOS/gyroflow'), '--licenses', str(notices)]
        if development: command.append('--development-runtime')
        with patch.object(stager, 'ROOT', repo), patch.object(sys, 'argv', command), \
             patch.object(stager, 'git', side_effect=lambda *args: b'' if args[0] == 'status' else b'1234567890abcdef'), \
             contextlib.redirect_stdout(io.StringIO()):
            stager.main()
        return output

    def test_universal_slices_resolve_ocio_and_transitive_imath_symlink(self):
        self.main_binary(self.slice(('@rpath/libOpenColorIO.2.4.dylib',
                                     '/usr/lib/libSystem.B.dylib'),
                                    ('@loader_path/../Frameworks',)), ('x86_64', 'arm64'))
        ocio = self.binary('Contents/Frameworks/libOpenColorIO.2.4.2.dylib', {
            architecture: self.slice(('@loader_path/libImath.dylib',), minimum=minimum)
            for architecture, minimum in (('x86_64', '13.0'), ('arm64', '14.0'))})
        (ocio.parent / 'libOpenColorIO.2.4.dylib').symlink_to(ocio.name)
        self.binary('Contents/Frameworks/libImath.dylib', {
            architecture: self.slice(('/System/Library/Frameworks/CoreFoundation.framework/Versions/A/CoreFoundation',),
                                      minimum='11.0', legacy=True)
            for architecture in ('x86_64', 'arm64')})
        report = self.audit()
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['external_dependencies'], [])
        self.assertEqual(report['maximum_embedded_minimum_macos'], '14.0')
        self.assertEqual(len(report['embedded_minimum_macos']), 6)
        stager.check_mac_minimum(report, {'LSMinimumSystemVersion': '14.0'})
        self.assertEqual(report['errors'], [])

    def test_missing_rpath_ocio_is_rejected(self):
        (self.app / 'Contents/Frameworks').mkdir(parents=True)
        self.main_binary(self.slice(('@rpath/libOpenColorIO.2.4.dylib',),
                                    ('@executable_path/../Frameworks',)))
        self.assertIn('Missing dependency', '\n'.join(self.audit()['errors']))

    def test_unused_external_rpath_is_recorded_even_with_bundled_ocio(self):
        development = self.root / 'SSD/_dev/ocio-runtime/install/lib'
        development.mkdir(parents=True)
        self.main_binary(self.slice(('@rpath/libOpenColorIO.2.4.dylib',),
                                    ('@loader_path/../Frameworks', str(development))))
        self.binary('Contents/Frameworks/libOpenColorIO.2.4.dylib', {'arm64': self.slice()})
        report = self.audit()
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['external_dependencies'], [str(development)])

    def test_development_external_dependency_closure_records_imath(self):
        ocio = self.root / 'SSD/_dev/ocio/libOpenColorIO.2.4.dylib'
        imath = self.root / 'homebrew/lib/libImath.dylib'
        self.binary(imath, {'arm64': self.slice(minimum='26.0')})
        self.binary(ocio, {'arm64': self.slice((str(imath),), minimum='11.0')})
        self.main_binary(self.slice(('@rpath/libOpenColorIO.2.4.dylib',), (str(ocio.parent),)))
        report = self.audit()
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['external_dependencies'], sorted(map(str, (ocio.parent, ocio, imath))))
        self.assertEqual(report['maximum_embedded_minimum_macos'], '11.0')

    def test_inherited_executable_rpath_resolves_a_transitive_dependency(self):
        self.main_binary(self.slice(('@rpath/libOpenColorIO.dylib',), ('@loader_path/../Frameworks',)))
        self.binary('Contents/Frameworks/libOpenColorIO.dylib',
                    {'arm64': self.slice(('@rpath/libImath.dylib',))})
        self.binary('Contents/Frameworks/libImath.dylib', {'arm64': self.slice()})
        self.assertEqual(self.audit()['errors'], [])

    def test_framework_directory_symlink_resolves_inside_bundle(self):
        self.main_binary(self.slice(('@rpath/QtCore.framework/QtCore',), ('@loader_path/../Frameworks',)))
        core = self.binary('Contents/Frameworks/QtCore.framework/Versions/A/QtCore',
                           {'arm64': self.slice()})
        (core.parent.parent / 'Current').symlink_to('A', target_is_directory=True)
        (core.parent.parent.parent / 'QtCore').symlink_to('Versions/Current/QtCore')
        self.assertEqual(self.audit()['errors'], [])
        self.assertEqual(self.audit()['external_dependencies'], [])

    def test_escaping_symlink_cannot_hide_an_external_dependency(self):
        self.main_binary(self.slice(('@loader_path/../Frameworks/libOpenColorIO.dylib',)))
        outside = self.binary(self.root / 'outside/libOpenColorIO.dylib', {'arm64': self.slice()})
        bundled = self.app / 'Contents/Frameworks/libOpenColorIO.dylib'
        bundled.parent.mkdir(parents=True)
        bundled.symlink_to(outside)
        report = self.audit()
        self.assertIn(str(outside), report['external_dependencies'])
        self.assertTrue(any(' -> ' in item for item in report['external_dependencies']))

    def test_rpath_escape_and_missing_directory_are_not_accepted(self):
        self.main_binary(self.slice(rpaths=('@loader_path/../../../outside/missing',)))
        report = self.audit()
        self.assertEqual(report['external_dependencies'], [str(self.root / 'outside/missing')])
        self.assertIn('Missing LC_RPATH directory', '\n'.join(report['errors']))

    def test_missing_universal_dependency_slice_is_rejected(self):
        self.main_binary(self.slice(('@loader_path/../Frameworks/libOpenColorIO.dylib',)),
                         ('x86_64', 'arm64'))
        self.binary('Contents/Frameworks/libOpenColorIO.dylib', {'arm64': self.slice()})
        self.assertIn('Missing x86_64 Mach-O slice', '\n'.join(self.audit()['errors']))

    def test_extra_universal_framework_slice_under_thin_application_is_valid(self):
        self.main_binary(self.slice(('@loader_path/../Frameworks/libOpenColorIO.dylib',)))
        self.binary('Contents/Frameworks/libOpenColorIO.dylib',
                    {architecture: self.slice() for architecture in ('x86_64', 'arm64')})
        self.assertEqual(self.audit()['errors'], [])

    def test_shared_library_is_rechecked_in_both_plugin_loader_contexts(self):
        self.main_binary()
        self.binary('Contents/Frameworks/shared.dylib', {'arm64': self.slice(('@rpath/libImath.dylib',))})
        for name in ('A', 'B'):
            self.binary(f'Contents/PlugIns/{name}/plugin.dylib', {'arm64': self.slice(
                ('@loader_path/../../Frameworks/shared.dylib',), ('@loader_path/Libraries',))})
            (self.app / f'Contents/PlugIns/{name}/Libraries').mkdir()
        self.binary('Contents/PlugIns/A/Libraries/libImath.dylib', {'arm64': self.slice()})
        report = self.audit()
        missing = [value for value in report['errors'] if "Missing dependency '@rpath/libImath.dylib'" in value]
        self.assertEqual(len(missing), 1)
        self.binary('Contents/PlugIns/B/Libraries/libImath.dylib', {'arm64': self.slice()})
        self.assertEqual(self.audit()['errors'], [])

    def test_dynamic_plugin_minimum_is_included_and_false_plist_claim_fails(self):
        self.main_binary()
        self.binary('Contents/PlugIns/platforms/libqcocoa.dylib', {'arm64': self.slice(minimum='27.0')})
        report = self.audit()
        self.assertEqual(report['maximum_embedded_minimum_macos'], '27.0')
        stager.check_mac_minimum(report, {'LSMinimumSystemVersion': '14.0'})
        self.assertIn('below embedded Mach-O minimum 27.0', '\n'.join(report['errors']))

    def test_architecture_specific_plist_claim_is_checked(self):
        self.main_binary(architectures=('x86_64', 'arm64'))
        report = self.audit()
        stager.check_mac_minimum(report, {'LSMinimumSystemVersion': '14.0',
                                       'LSMinimumSystemVersionByArchitecture': {'arm64': '10.15'}})
        self.assertIn('LSMinimumSystemVersionByArchitecture arm64', '\n'.join(report['errors']))

    def test_higher_arm_minimum_override_is_valid_for_universal_runtime(self):
        self.binary('Contents/MacOS/gyroflow', {
            'x86_64': self.slice(minimum='11.0'), 'arm64': self.slice(minimum='14.0')})
        for arm_minimum, valid in (('14.0', True), ('13.0', False)):
            with self.subTest(arm_minimum=arm_minimum):
                report = self.audit()
                stager.check_mac_minimum(report, {'LSMinimumSystemVersion': '11.0',
                                               'LSMinimumSystemVersionByArchitecture': {'arm64': arm_minimum}})
                self.assertEqual(not report['errors'], valid)
        report = self.audit()
        stager.check_mac_minimum(report, {'LSMinimumSystemVersionByArchitecture': {'x86_64': '11.0', 'arm64': '14.0'}})
        self.assertEqual(report['errors'], [])

    def test_missing_or_malformed_minimum_claim_is_rejected(self):
        self.main_binary()
        for info in ({}, {'LSMinimumSystemVersion': 'future'}, {'LSMinimumSystemVersion': 14}):
            with self.subTest(info=info):
                report = self.audit()
                stager.check_mac_minimum(report, info)
                self.assertIn('Invalid macOS minimum version', '\n'.join(report['errors']))

    def test_portable_stage_rejects_missing_ocio_before_signing(self):
        (self.app / 'Contents/Frameworks').mkdir(parents=True)
        self.main_binary(self.slice(('@rpath/libOpenColorIO.2.4.dylib',),
                                    ('@loader_path/../Frameworks',)))
        with self.assertRaisesRegex(RuntimeError, 'Missing dependency'):
            self.stage()
        self.assertFalse(any(call[0] == 'codesign' for call in self.tool_calls))
        self.assertFalse((self.root / 'stage/PACKAGE.json').exists())

    def test_portable_stage_rejects_external_rpath_even_with_bundled_ocio(self):
        development = self.root / 'SSD/_dev/ocio-runtime/install/lib'
        development.mkdir(parents=True)
        self.main_binary(self.slice(('@rpath/libOpenColorIO.2.4.dylib',),
                                    ('@loader_path/../Frameworks', str(development))))
        self.binary('Contents/Frameworks/libOpenColorIO.2.4.dylib', {'arm64': self.slice()})
        with self.assertRaisesRegex(RuntimeError, 'External runtime path:'):
            self.stage()
        self.assertFalse(any(call[0] == 'codesign' for call in self.tool_calls))

    def test_portable_stage_refuses_false_minimum_without_rewriting_claim(self):
        self.main_binary()
        self.binary('Contents/PlugIns/platforms/libqcocoa.dylib', {'arm64': self.slice(minimum='27.0')})
        with self.assertRaisesRegex(RuntimeError, 'below embedded Mach-O minimum 27.0'):
            self.stage()
        with (self.stage_app / 'Contents/Info.plist').open('rb') as stream:
            self.assertEqual(plistlib.load(stream)['LSMinimumSystemVersion'], '11.0')
        self.assertFalse(any(call[0] == 'codesign' for call in self.tool_calls))

    def test_development_stage_records_floor_and_external_paths_in_both_manifests(self):
        outside = self.binary(self.root / 'homebrew/lib/libImath.dylib', {'arm64': self.slice()})
        self.main_binary(self.slice((str(outside),)))
        self.binary('Contents/PlugIns/platforms/libqcocoa.dylib', {'arm64': self.slice(minimum='27.0')})
        output = self.stage(development=True)
        build = json.loads((self.stage_app / 'Contents/Resources/Notices/BUILD.json').read_text())
        receipt = json.loads((output / 'PACKAGE.json').read_text())
        self.assertEqual(build['mac_runtime_audit'], receipt['mac_runtime_audit'])
        self.assertEqual(receipt['mac_runtime_audit']['maximum_embedded_minimum_macos'], '27.0')
        self.assertIn(str(outside), receipt['mac_runtime_audit']['external_dependencies'])
        self.assertIn('below embedded Mach-O minimum 27.0', '\n'.join(receipt['mac_runtime_audit']['errors']))
        self.assertTrue(receipt['development_runtime'])
        self.assertFalse(receipt['public_release_approved'])


if __name__ == '__main__':
    unittest.main()
