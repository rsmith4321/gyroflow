#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Packaging guards; synthetic fixtures only, no app/video execution."""
import contextlib
import importlib.util
import io
from pathlib import Path
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

    def test_universal_headers_are_not_dependencies_but_external_libraries_are(self):
        with tempfile.TemporaryDirectory(prefix='plus-mach-test-') as temporary:
            app = Path(temporary) / 'Gyroflow Plus.app'
            app.mkdir()
            binary = app / 'universal-fixture'
            binary.write_bytes(b'not a real executable')
            output = f'''{binary} (architecture x86_64):
\t@rpath/QtCore.framework/Versions/A/QtCore (compatibility version 6.0.0, current version 6.10.2)
\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1351.0.0)
{binary} (architecture arm64):
\t@rpath/QtCore.framework/Versions/A/QtCore (compatibility version 6.0.0, current version 6.10.2)
\t/opt/homebrew/lib/libexternal.dylib (compatibility version 1.0.0, current version 1.0.0)
'''
            result = subprocess.CompletedProcess(['otool'], 0, stdout=output, stderr='')
            with patch.object(stager.subprocess, 'run', return_value=result):
                self.assertEqual(stager.check_mac_dependencies(app),
                                 ['/opt/homebrew/lib/libexternal.dylib'])


if __name__ == '__main__':
    unittest.main()
