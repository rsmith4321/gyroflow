#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Run a locked Mac Cargo build and record its reported executable identity.

This local build receipt is provenance, not a signature or a public-release
approval. Windows uses the receipt produced by its existing deploy recipe.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def source_identity():
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip())
    if dirty:
        raise RuntimeError('Build receipts require committed source, including newly added files')
    return commit


def build(output, profile='deploy', features='', target=None, jobs=4, offline=False):
    if sys.platform != 'darwin':
        raise RuntimeError('Use this build receipt helper on Mac; Windows uses just deploy')
    output = output.resolve()
    if output.exists():
        raise RuntimeError('Build receipt already exists; use a fresh output')
    # Create the directory before checking Git so a new non-ignored output
    # directory cannot silently become part of the supposedly clean source.
    output.parent.mkdir(parents=True, exist_ok=True)
    commit = source_identity()
    # A different clean checkout may share Cargo's normal target directory.
    # Its build can replace the executable after Cargo releases its lock but
    # before we hash it. Keep this invocation's artifacts exclusively owned.
    target_dir = output.parent/(output.name+'.target')
    target_dir.mkdir(exist_ok=False)
    command = ['cargo', 'build', '--locked', '--manifest-path', str(ROOT/'Cargo.toml'),
               '--bin', 'gyroflow', '--profile', profile, '--jobs', str(jobs),
               '--target-dir', str(target_dir),
               '--message-format', 'json-render-diagnostics']
    if features: command += ['--features', features]
    if target: command += ['--target', target]
    if offline: command.append('--offline')
    # Cargo emits diagnostics to stderr. Select the executable from its
    # compiler-artifact message rather than guessing a target-directory path.
    result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, text=True, check=True)
    artifacts = []
    for line in result.stdout.splitlines():
        message = json.loads(line)
        if (message.get('reason') == 'compiler-artifact'
                and message.get('target', {}).get('name') == 'gyroflow'
                and 'bin' in message.get('target', {}).get('kind', [])
                and Path(message.get('manifest_path', '')).resolve() == ROOT/'Cargo.toml'
                and message.get('executable')):
            artifacts.append(Path(message['executable']).resolve(strict=True))
    if len(artifacts) != 1:
        raise RuntimeError('Cargo did not report exactly one executable from this package')
    binary = artifacts[0]
    if not binary.is_relative_to(target_dir):
        raise RuntimeError('Cargo reported an executable outside this build\'s owned target directory')
    binary_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
    if source_identity() != commit:
        raise RuntimeError('Source commit changed during the build; no receipt written')
    receipt = dict(platform='mac', commit=commit, dirty=False,
                   features=features, target=target, profile=profile,
                   target_directory=str(target_dir),
                   command=command, executable=str(binary), exe_sha256=binary_hash,
                   public_release_approved=False)
    # Exclusive creation also refuses a receipt created by another build
    # while this one was running.
    with output.open('x') as stream:
        stream.write(json.dumps(receipt, indent=2)+'\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='new build receipt, preferably under ignored _dev/')
    parser.add_argument('--profile', default='deploy')
    parser.add_argument('--features', default='')
    parser.add_argument('--target')
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--offline', action='store_true')
    args = parser.parse_args()
    if args.jobs < 1: parser.error('--jobs must be positive')
    print(json.dumps(build(args.output, args.profile, args.features, args.target, args.jobs, args.offline), indent=2))


if __name__ == '__main__': main()
