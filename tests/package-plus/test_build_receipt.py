#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Build provenance checks with synthetic Cargo messages; no app compilation."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('build_plus',ROOT/'_scripts/build_plus.py')
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)


class BuildReceiptTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='plus-build-receipt-')
        self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name).resolve()
        self.output=self.root/'_dev/receipt.json'
        self.binary=self.root/'_dev/receipt.json.target/deploy/gyroflow'
        self.commit='a'*40
        self.artifact=dict(reason='compiler-artifact',target=dict(name='gyroflow',kind=['bin']),
                           manifest_path=str(self.root/'Cargo.toml'),executable=str(self.binary))

    def run_build(self, messages=None, status=None, commits=None, failure=None):
        with patch.object(builder,'ROOT',self.root),patch.object(builder.sys,'platform','darwin'), \
             patch.object(builder.subprocess,'check_output',side_effect=[
                 (commits or [self.commit,self.commit])[0].encode(), status or b'',
                 (commits or [self.commit,self.commit])[1].encode(),b'']), \
             patch.object(builder.subprocess,'run') as cargo:
            if failure: cargo.side_effect=failure
            else:
                def compile_fixture(*args,**kwargs):
                    self.binary.parent.mkdir(parents=True,exist_ok=True)
                    self.binary.write_bytes(b'synthetic binary; never executed')
                    return subprocess.CompletedProcess([],0,stdout='\n'.join(json.dumps(value)
                        for value in (messages if messages is not None else [self.artifact])))
                cargo.side_effect=compile_fixture
            receipt=builder.build(self.output,features='ocio-runtime',offline=True)
            command=cargo.call_args.args[0]
        return receipt,command

    def test_success_pins_cargo_reported_executable_and_exact_source(self):
        receipt,command=self.run_build()
        self.assertEqual(receipt['commit'],self.commit)
        self.assertIs(receipt['dirty'],False)
        self.assertEqual(receipt['exe_sha256'],hashlib.sha256(self.binary.read_bytes()).hexdigest())
        self.assertEqual(receipt,json.loads(self.output.read_text()))
        self.assertIn('--locked',command);self.assertIn('--offline',command)
        self.assertEqual(command[command.index('--manifest-path')+1],str(self.root/'Cargo.toml'))
        self.assertEqual(command[command.index('--target-dir')+1],str(self.binary.parents[1]))
        self.assertEqual(receipt['executable'],str(self.binary))

    def test_failed_build_never_writes_receipt(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_build(failure=subprocess.CalledProcessError(101,['cargo']))
        self.assertFalse(self.output.exists())

    def test_dirty_source_never_starts_cargo(self):
        with patch.object(builder.subprocess,'run') as cargo, self.assertRaisesRegex(RuntimeError,'committed source'):
            self.run_build(status=b' M src/main.rs')
        cargo.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_source_change_during_build_never_writes_receipt(self):
        with self.assertRaisesRegex(RuntimeError,'Source commit changed'):
            self.run_build(commits=[self.commit,'b'*40])
        self.assertFalse(self.output.exists())

    def test_wrong_package_or_missing_or_multiple_artifacts_are_refused(self):
        for messages in ([],[dict(self.artifact,manifest_path=str(self.root/'dependency/Cargo.toml'))],
                         [self.artifact,self.artifact]):
            with self.subTest(messages=messages),self.assertRaisesRegex(RuntimeError,'exactly one executable'):
                self.run_build(messages=messages)
            self.assertFalse(self.output.exists())
            shutil.rmtree(self.output.parent/(self.output.name+'.target'))

    def test_shared_target_output_is_never_used_or_overwritten(self):
        self.binary.parent.mkdir(parents=True);self.binary.write_bytes(b'existing build evidence')
        with self.assertRaises(FileExistsError): self.run_build()
        self.assertFalse(self.output.exists())
        self.assertEqual(self.binary.read_bytes(),b'existing build evidence')

    def test_cargo_artifact_outside_owned_directory_is_refused(self):
        outside=self.root/'target/deploy/gyroflow'
        outside.parent.mkdir(parents=True);outside.write_bytes(b'other checkout build')
        with self.assertRaisesRegex(RuntimeError,'outside this build'):
            self.run_build(messages=[dict(self.artifact,executable=str(outside))])
        self.assertFalse(self.output.exists())

    def test_existing_receipt_preserved_without_build(self):
        self.output.parent.mkdir();self.output.write_bytes(b'existing evidence')
        with patch.object(builder.subprocess,'run') as cargo,self.assertRaisesRegex(RuntimeError,'already exists'):
            self.run_build()
        cargo.assert_not_called()
        self.assertEqual(self.output.read_bytes(),b'existing evidence')


if __name__=='__main__': unittest.main()
