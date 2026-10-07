#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage the community fork from an explicitly prepared desktop runtime.

Does not install, publish, register file associations, or use upstream Store
identities. Portable staging requires supplied dependency notices and a clean
source checkout. --development-runtime permits local dependency paths and
records that the result is not a redistributable release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def check_mac_dependencies(app):
    external = set()
    for path in app.rglob('*'):
        if not path.is_file() or path.is_symlink(): continue
        result = subprocess.run(['otool', '-L', str(path)],capture_output=True,text=True)
        if result.returncode: continue
        for line in result.stdout.splitlines()[1:]:
            dependency = line.strip().split(' (compatibility')[0]
            if dependency.startswith('/') and not dependency.startswith(('/usr/lib/', '/System/Library/')):
                external.add(dependency)
    return sorted(external)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('platform',choices=['mac','windows'])
    parser.add_argument('runtime',type=Path,help='prepared .app or portable Windows directory')
    parser.add_argument('output',type=Path,help='new, nonexistent staging directory')
    parser.add_argument('--binary',type=Path,required=True,help='built from this source checkout')
    parser.add_argument('--licenses',type=Path,help='dependency copyright/license texts and source/build provenance')
    parser.add_argument('--development-runtime',action='store_true')
    args=parser.parse_args()
    runtime=args.runtime.resolve(strict=True);binary=args.binary.resolve(strict=True)
    output=args.output.resolve()
    if output.exists(): parser.error('Output already exists; use a fresh staging directory')
    dirty=bool(git('status','--porcelain').strip())
    if not args.development_runtime and dirty: parser.error('Portable staging requires committed source')
    if not args.development_runtime and not args.licenses: parser.error('Supply dependency notices/provenance with --licenses')
    version=tomllib.loads((ROOT/'Cargo.toml').read_text())['package']['version']
    commit=git('rev-parse','HEAD').decode().strip()
    output.mkdir(parents=True)
    if args.platform=='mac':
        app=output/'Gyroflow Plus.app'
        shutil.copytree(runtime,app,symlinks=True)
        shutil.rmtree(app/'Contents/_CodeSignature',ignore_errors=True)
        contents=app/'Contents';resources=contents/'Resources'
        resources.mkdir(exist_ok=True)
        shutil.copy2(binary,contents/'MacOS/gyroflow')
        plist=contents/'Info.plist'
        with plist.open('rb') as f: info=plistlib.load(f)
        info.update(CFBundleDisplayName='Gyroflow Plus',CFBundleName='Gyroflow Plus',
                    CFBundleIdentifier='com.ryansmith.gyroflow-plus',CFBundleExecutable='gyroflow',
                    CFBundleShortVersionString=version.split('-')[0],CFBundleVersion=version.split('-')[0],
                    GyroflowPlusVersion=version,GyroflowPlusSourceCommit=commit,
                    GyroflowPlusDevelopmentRuntime=args.development_runtime,
                    NSHumanReadableCopyright='Gyroflow Plus community fork. Original Gyroflow and third-party copyrights retained.')
        info.pop('GyroflowLUTSourceCommit',None)
        info.pop('UTExportedTypeDeclarations',None)
        # Be available in Open With, without becoming the owner/default handler.
        info['CFBundleDocumentTypes']=[dict(CFBundleTypeName='Gyroflow Project',CFBundleTypeRole='Editor',
            LSHandlerRank='None',LSItemContentTypes=['xyz.gyroflow.project'])]
        info['UTImportedTypeDeclarations']=[dict(UTTypeIdentifier='xyz.gyroflow.project',
            UTTypeDescription='Gyroflow Project',UTTypeConformsTo=['public.json'],
            UTTypeTagSpecification={'public.filename-extension':['gyroflow']})]
        if not args.development_runtime: info.pop('LSEnvironment',None)
        with plist.open('wb') as f: plistlib.dump(info,f)
        notices=resources/'Notices'
        external=check_mac_dependencies(app)
        if external and not args.development_runtime:
            raise RuntimeError('Unbundled runtime dependencies: '+', '.join(external))
    else:
        app=output/'Gyroflow Plus'
        shutil.copytree(runtime,app)
        for name in ['gyroflow.exe','Gyroflow.exe']:
            (app/name).unlink(missing_ok=True)
        shutil.copy2(binary,app/'GyroflowPlus.exe')
        # Portable ZIP only; no Appx, installer identity or association registry.
        if any(p.suffix.lower() in ('.appx','.msix','.pfx') for p in app.rglob('*')):
            raise RuntimeError('Expected a portable Windows runtime, without Store packages or signing keys')
        (app/'qt.conf').write_text('[Paths]\nPrefix=.\nPlugins=.\nQmlImports=.\n')
        notices=app/'Notices';external=[]
    notices.mkdir(exist_ok=True)
    shutil.copy2(ROOT/'LICENSE',notices/'Gyroflow-GPL-3.0.txt')
    shutil.copy2(ROOT/'resources/color/OCIO-LICENSE.txt',notices/'OpenColorIO-BSD-3-Clause.txt')
    shutil.copy2(ROOT/'docs/PLUS-DISTRIBUTION.md',notices/'COMMUNITY-FORK.md')
    if args.licenses: shutil.copytree(args.licenses.resolve(strict=True),notices/'Dependencies')
    manifest=dict(name='Gyroflow Plus',community_fork=True,version=version,commit=commit,
        dirty_source=dirty,development_runtime=args.development_runtime,
        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        source=f'https://github.com/rsmith4321/gyroflow/tree/{commit}',external_mac_dependencies=external,
        public_release_approved=False)
    (notices/'BUILD.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # Source archive for this commit accompanies every stage. Development dirty
    # builds also carry their exact source patch; they remain local prototypes.
    with (output/f'Gyroflow-Plus-source-{commit[:12]}.tar').open('wb') as f:
        subprocess.run(['git','archive','--format=tar',commit],cwd=ROOT,stdout=f,check=True)
    if dirty:
        (output/'development-source.patch').write_bytes(git('diff','HEAD','--binary'))
    if args.platform=='mac':
        subprocess.run(['codesign','--force','--deep','--sign','-',str(app)],check=True)
        subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    print(json.dumps(manifest,indent=2))


if __name__=='__main__': main()
