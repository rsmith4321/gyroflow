#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Packaging guards; synthetic fixtures only, no app/video execution."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('package_plus', ROOT / '_scripts/package_plus.py')
stager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stager)
PACKET = 'resources/color/ocio-third-party'


class StagingTests(unittest.TestCase):
    def test_legacy_windows_deploy_receipt_without_platform_passes_preflight(self):
        with tempfile.TemporaryDirectory(prefix='plus-windows-receipt-') as temporary:
            root=Path(temporary);runtime=root/'runtime';runtime.mkdir()
            (root/'Cargo.toml').write_text('[package]\nversion="0.1.0-dev"\n')
            binary=root/'gyroflow.exe';binary.write_bytes(b'synthetic; never executed')
            shutil.copy2(binary,runtime/'Gyroflow.exe')
            receipt=root/'receipt.json';commit='a'*40
            receipt.write_text(json.dumps(dict(commit=commit,dirty=False,features='ocio-runtime',
                exe_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),crt_source='fixture')))
            command=['package_plus.py','windows',str(runtime),str(root/'stage'),
                '--binary',str(binary),'--licenses',str(root/'notices'),
                '--deploy-receipt',str(receipt),'--msvc-redist-floor','14.51.36260.0']
            with patch.object(stager,'ROOT',root),patch.object(sys,'argv',command), \
                 patch.object(stager,'git',side_effect=lambda *args: b'' if args[0]=='status' else commit.encode()), \
                 patch.object(stager.shutil,'copytree',side_effect=RuntimeError('staging reached')), \
                 self.assertRaisesRegex(RuntimeError,'staging reached'):
                stager.main()
            self.assertTrue((root/'stage').exists())

    def test_invalid_binary_source_receipts_are_refused_before_output_creation(self):
        with tempfile.TemporaryDirectory(prefix='plus-receipt-test-') as temporary:
            root=Path(temporary)
            runtime=root/'runtime';runtime.mkdir()
            (root/'Cargo.toml').write_text('[package]\nversion="0.1.0-dev"\n')
            binary=root/'gyroflow';binary.write_bytes(b'not executed')
            commit='a'*40
            valid=dict(platform='mac',commit=commit,dirty=False,
                       exe_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
            invalid=[None, b'{', b'[]', dict(valid,commit='b'*40),
                     dict(valid,dirty=True), dict(valid,dirty=0),
                     dict(valid,exe_sha256='0'*64), dict(valid,platform='windows')]
            for value in invalid:
                with self.subTest(receipt=value):
                    output=root/'stage'
                    command=['package_plus.py','mac',str(runtime),str(output),
                             '--binary',str(binary),'--licenses',str(root/'notices')]
                    if value is not None:
                        path=root/'receipt.json'
                        path.write_bytes(value if isinstance(value,bytes) else json.dumps(value).encode())
                        command+=['--deploy-receipt',str(path)]
                    with patch.object(stager,'ROOT',root),patch.object(sys,'argv',command), \
                         patch.object(stager,'git',side_effect=lambda *args: b'' if args[0]=='status' else commit.encode()), \
                         contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as failure:
                        stager.main()
                    self.assertEqual(failure.exception.code,2)
                    self.assertFalse(output.exists())

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
                                ('docs/PLUS-DISTRIBUTION.md', 'synthetic distribution fixture')):
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value)
        shutil.copytree(ROOT / PACKET, repo / PACKET)
        shutil.copy2(ROOT / 'resources/color/OCIO-LICENSE.txt', repo / 'resources/color')
        shutil.copytree(ROOT / 'resources/lens-profiles-v41', repo / 'resources/lens-profiles-v41')
        lens = b'\x1f\x8bsynthetic lens database'
        lens_sha = hashlib.sha256(lens).hexdigest()
        (repo / 'src/core').mkdir(parents=True, exist_ok=True)
        (repo / 'src/core/lens_profiles.pin').write_text(
            f'tag=v41\nurl=https://github.com/gyroflow/lens_profiles/releases/download/v41/profiles.cbor.gz\nsha256={lens_sha}\n')
        presets = self.app / 'Contents/Resources/camera_presets'
        presets.mkdir(parents=True, exist_ok=True)
        if not (presets / 'profiles.cbor.gz').exists(): (presets / 'profiles.cbor.gz').write_bytes(lens)
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
        else:
            receipt=self.root/'build-receipt.json'
            receipt.write_text(json.dumps(dict(platform='mac',commit='1234567890abcdef',dirty=False,
                exe_sha256=hashlib.sha256((self.app/'Contents/MacOS/gyroflow').read_bytes()).hexdigest(),
                lens_profiles=dict(mode='pinned',sha256=lens_sha,bytes=len(lens)))))
            command+=['--deploy-receipt',str(receipt)]
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

    def test_portable_stage_records_matching_binary_commit_and_input_receipt(self):
        self.main_binary()
        output=self.stage()
        receipt=json.loads((output/'PACKAGE.json').read_text())
        build=json.loads((self.stage_app/'Contents/Resources/Notices/BUILD.json').read_text())
        self.assertTrue(receipt['binary_source_verified'])
        self.assertEqual(receipt['source_commit'],'1234567890abcdef')
        self.assertEqual(build['commit'],receipt['source_commit'])
        with (self.stage_app/'Contents/Info.plist').open('rb') as stream:
            self.assertEqual(plistlib.load(stream)['GyroflowPlusSourceCommit'],receipt['source_commit'])
        self.assertEqual((self.stage_app/'Contents/Resources/Notices/BUILD-INPUT.json').read_bytes(),
                         (self.root/'build-receipt.json').read_bytes())
        self.assertEqual(receipt['lens_profiles']['errors'],[])
        self.assertEqual(receipt['lens_profiles']['staged']['sha256'],build['lens_profiles']['pin']['sha256'])
        self.assertEqual((self.stage_app/'Contents/Resources/Notices/lens-profiles-v41/LICENSE.txt').read_bytes(),
                         (ROOT/'resources/lens-profiles-v41/LICENSE.txt').read_bytes())

    def test_portable_mac_stage_refuses_a_different_lens_database_before_signing(self):
        self.main_binary()
        presets=self.app/'Contents/Resources/camera_presets';presets.mkdir(parents=True)
        (presets/'profiles.cbor.gz').write_bytes(b'\x1f\x8bnewer upstream db')
        with self.assertRaisesRegex(RuntimeError,'Staged lens profile SHA-256'):
            self.stage()
        self.assertFalse(any(call[0]=='codesign' for call in self.tool_calls))
        self.assertFalse((self.root/'stage/PACKAGE.json').exists())

    def test_binary_replaced_during_copy_is_refused_before_signing(self):
        binary=self.main_binary()
        copy=shutil.copy2
        def changed_copy(source,destination,*args,**kwargs):
            result=copy(source,destination,*args,**kwargs)
            if Path(source)==binary:
                with Path(destination).open('ab') as stream: stream.write(b'replaced executable')
            return result
        with patch.object(stager.shutil,'copy2',side_effect=changed_copy), \
             self.assertRaisesRegex(RuntimeError,'Executable changed during staging'):
            self.stage()
        self.assertFalse(any(call[0]=='codesign' for call in self.tool_calls))
        self.assertFalse((self.root/'stage/PACKAGE.json').exists())

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
        self.assertFalse(receipt['binary_source_verified'])
        self.assertIsNone(receipt['source_commit'])
        self.assertIsNone(build['commit'])
        self.assertIsNone(build['source'])
        self.assertEqual(build['checkout_commit'],'1234567890abcdef')
        with (self.stage_app/'Contents/Info.plist').open('rb') as stream:
            info=plistlib.load(stream)
        self.assertNotIn('GyroflowPlusSourceCommit',info)
        self.assertEqual(info['GyroflowPlusCheckoutCommit'],'1234567890abcdef')
        self.assertFalse(receipt['public_release_approved'])
        check = self.stage_app / 'Contents/Resources/Notices/OpenColorIO-third-party/STAGE-CHECK.json'
        self.assertEqual(json.loads(check.read_text())['errors'], [])


class OcioNoticeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='plus-notice-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / 'repo'
        shutil.copytree(ROOT / PACKET, self.repo / PACKET)
        shutil.copy2(ROOT / 'resources/color/OCIO-LICENSE.txt', self.repo / 'resources/color')
        self.app = self.root / 'Gyroflow Plus'
        self.app.mkdir()

    def check(self):
        notices = self.root / f'Notices-{len(list(self.root.iterdir()))}'
        notices.mkdir()
        with patch.object(stager, 'ROOT', self.repo):
            report = stager.copy_ocio_notices(self.app, notices)
        self.assertTrue((notices / 'OpenColorIO-third-party/expat/COPYING').is_file())
        return report

    def test_packet_matches_its_manifest_and_windows_zlib_pin(self):
        (self.app / 'OpenColorIO_2_4.dll').write_bytes(
            b'MZ synthetic; never executed deflate 1.2.13 Copyright 1995-2022 not well-formed (invalid token)')
        report = self.check()
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['libraries']['OpenColorIO_2_4.dll']['embedded_zlib'], '1.2.13')
        self.assertTrue(report['libraries']['OpenColorIO_2_4.dll']['embedded_expat'])

    def test_other_embedded_zlib_and_changed_notice_are_errors(self):
        (self.app / 'OpenColorIO_2_4.dll').write_bytes(b'MZ synthetic deflate 1.3.1 Copyright 1995-2024')
        (self.repo / PACKET / 'zlib/LICENSE').write_text('edited')
        errors = '\n'.join(self.check()['errors'])
        self.assertIn('embeds zlib 1.3.1; notices are for 1.2.13', errors)
        self.assertIn('Notice missing or changed: zlib/LICENSE', errors)


class LensProfileStagingTests(unittest.TestCase):
    """The lens database is untracked; portable stages must tie it to the pin."""
    DB = b'\x1f\x8bsynthetic lens database'

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='plus-lens-stage-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sha = hashlib.sha256(self.DB).hexdigest()
        pin = self.root / 'src/core/lens_profiles.pin'
        pin.parent.mkdir(parents=True)
        pin.write_text('tag=v41\nurl=https://github.com/gyroflow/lens_profiles/releases/download/v41/profiles.cbor.gz\n'
                       f'sha256={self.sha}\n')

    def stage(self, platform, data=DB):
        app = self.root / platform
        path = app / ('Contents/Resources/camera_presets' if platform == 'mac' else 'camera_presets')
        path.mkdir(parents=True)
        if data is not None: (path / 'profiles.cbor.gz').write_bytes(data)
        return app

    def check(self, app, platform, receipt, development=False):
        with patch.object(stager, 'ROOT', self.root):
            return stager.check_lens_profiles(app, platform, receipt, development)

    def receipt(self, **lens):
        return dict(lens_profiles=dict(dict(mode='pinned', sha256=self.sha, bytes=len(self.DB)), **lens))

    def test_pinned_receipt_and_staged_copy_pass_on_both_platforms(self):
        for platform in ('mac', 'windows'):
            with self.subTest(platform=platform):
                report = self.check(self.stage(platform), platform, self.receipt())
                self.assertEqual(report['errors'], [])
                self.assertEqual(report['staged']['sha256'], self.sha)
                self.assertEqual(report['pin']['tag'], 'v41')

    def test_portable_stage_refuses_missing_unpinned_or_changed_database(self):
        cases = [('missing', None, self.receipt(), 'Missing regular lens profile database'),
                 ('legacy', self.DB, dict(commit='a'*40), 'does not record a pinned'),
                 ('latest', self.DB, self.receipt(mode='latest'), 'does not record a pinned'),
                 ('receipt', self.DB, self.receipt(sha256='0'*64), 'Receipt lens profile SHA-256'),
                 ('swapped', b'\x1f\x8bnewer upstream db', self.receipt(), 'Staged lens profile SHA-256')]
        for name, data, receipt, message in cases:
            with self.subTest(case=name), self.assertRaisesRegex(RuntimeError, message):
                self.check(self.stage(name, data), 'windows', receipt)

    def test_symlinked_database_is_not_accepted(self):
        app = self.stage('mac', None)
        target = self.root / 'outside.cbor.gz'; target.write_bytes(self.DB)
        (app / 'Contents/Resources/camera_presets/profiles.cbor.gz').symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, 'Missing regular'):
            self.check(app, 'mac', self.receipt())

    def test_development_stage_records_without_requiring_pin(self):
        report = self.check(self.stage('windows', b'\x1f\x8bdeveloper db'), 'windows', None, development=True)
        self.assertEqual(report['staged']['sha256'], hashlib.sha256(b'\x1f\x8bdeveloper db').hexdigest())
        self.assertIn('Build receipt does not record a pinned lens profile database', report['errors'])


if __name__ == '__main__':
    unittest.main()
