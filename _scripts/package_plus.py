#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Stage the community fork from an explicitly prepared desktop runtime.

Does not install, publish, register file associations, or use upstream Store
identities. All staging requires a clean source checkout; portable staging also
requires supplied dependency notices. --development-runtime permits local dependency paths and
records that the result is not a redistributable release.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


MACHO_MAGIC = {bytes.fromhex(value) for value in
               ('feedface', 'cefaedfe', 'feedfacf', 'cffaedfe',
                'cafebabe', 'bebafeca', 'cafebabf', 'bfbafeca')}
DYLIB_COMMANDS = {'LC_LOAD_DYLIB', 'LC_LOAD_WEAK_DYLIB', 'LC_REEXPORT_DYLIB',
                  'LC_LAZY_LOAD_DYLIB', 'LC_LOAD_UPWARD_DYLIB'}


def macos_version(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+(?:\.\d+){0,2}', value):
        raise ValueError(f'Invalid macOS minimum version: {value!r}')
    return tuple((list(map(int, value.split('.'))) + [0, 0])[:3])


def read_macho(path):
    """Read each slice explicitly; architecture headers and dylib IDs are not loads."""
    with path.open('rb') as stream:
        if stream.read(4) not in MACHO_MAGIC:
            return {}
    def run(*args):
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(f'Cannot inspect {path}: {result.stderr.strip()}')
        return result.stdout
    architectures = run('lipo', '-archs', str(path)).split()
    if not architectures:
        raise RuntimeError(f'No Mach-O architectures in {path}')
    slices = {}
    for architecture in architectures:
        loads, rpaths, minimums = [], [], []
        output = run('otool', '-arch', architecture, '-l', str(path))
        for block in re.split(r'\nLoad command \d+\n', output):
            command = re.search(r'^\s*cmd\s+(\S+)\s*$', block, re.M)
            if not command: continue
            command = command.group(1)
            if command in DYLIB_COMMANDS or command == 'LC_RPATH':
                field = 'path' if command == 'LC_RPATH' else 'name'
                value = re.search(r'^\s*' + field + r'\s+(.+?)\s+\(offset \d+\)\s*$', block, re.M)
                if not value: raise RuntimeError(f'Malformed {command} in {path} [{architecture}]')
                (rpaths if command == 'LC_RPATH' else loads).append(value.group(1))
            elif command in ('LC_BUILD_VERSION', 'LC_VERSION_MIN_MACOSX'):
                if command == 'LC_BUILD_VERSION':
                    platform = re.search(r'^\s*platform\s+(\S+)\s*$', block, re.M)
                    if not platform or platform.group(1) not in ('1', 'MACOS'):
                        raise RuntimeError(f'Non-macOS slice in {path} [{architecture}]')
                field = 'minos' if command == 'LC_BUILD_VERSION' else 'version'
                value = re.search(r'^\s*' + field + r'\s+(\S+)\s*$', block, re.M)
                if not value: raise RuntimeError(f'Missing macOS minimum in {path} [{architecture}]')
                macos_version(value.group(1))
                minimums.append(value.group(1))
        if len(minimums) != 1:
            raise RuntimeError(f'Expected one macOS minimum in {path} [{architecture}]')
        slices[architecture] = dict(dependencies=loads, rpaths=rpaths, minimum_macos=minimums[0])
    return slices


def check_mac_dependencies(app):
    """Resolve the bundle and its transitive loads without trusting the host's paths.

    Development-only external loads are inspected but never count toward the
    embedded deployment floor. Apple shared-cache libraries need not be on disk.
    """
    app = app.resolve(strict=True)
    executable = app / 'Contents/MacOS/gyroflow'
    external, errors, inventory, inspected, embedded_minimums = set(), set(), set(), {}, {}
    def contained(path): return path.is_relative_to(app)
    def system(path): return path.is_relative_to('/usr/lib') or path.is_relative_to('/System/Library')
    def expand(value, loader):
        for prefix, base in (('@loader_path', loader.parent), ('@executable_path', executable.parent)):
            if value == prefix or value.startswith(prefix + '/'):
                return (base / value[len(prefix):].lstrip('/')).resolve()
        return Path(value).resolve() if value.startswith('/') else None
    def inspect(path):
        if path not in inspected:
            try: inspected[path] = read_macho(path)
            except (OSError, RuntimeError, ValueError) as failure:
                errors.add(str(failure)); inspected[path] = {}
            if contained(path):
                for architecture, data in inspected[path].items():
                    embedded_minimums[f'{path.relative_to(app)} [{architecture}]'] = data['minimum_macos']
        return inspected[path]
    for path in app.rglob('*'):
        try: resolved = path.resolve()
        except (OSError, RuntimeError) as failure:
            errors.add(f'Invalid bundle path {path}: {failure}'); continue
        if path.is_symlink() and (not contained(resolved) or not path.exists()):
            external.add(str(path) + ' -> ' + str(resolved))
            if not path.exists(): errors.add(f'Broken bundle symlink: {path}')
        if path.is_file() and contained(resolved): inventory.add(resolved)
    for path in sorted(inventory): inspect(path)
    main = inspect(executable)
    if not main: errors.add(f'Missing Mach-O application executable: {executable}')
    def runpaths(path, architecture, inherited):
        result = []
        for value in inspect(path).get(architecture, {}).get('rpaths', []):
            try: resolved = expand(value, path)
            except (OSError, RuntimeError) as failure:
                errors.add(f'Invalid LC_RPATH {value!r} in {path}: {failure}'); continue
            if resolved is None:
                errors.add(f'Unresolvable LC_RPATH {value!r} in {path} [{architecture}]'); continue
            if not contained(resolved) and not system(resolved): external.add(str(resolved))
            if not resolved.is_dir() and not system(resolved):
                errors.add(f'Missing LC_RPATH directory {resolved} in {path} [{architecture}]')
            result.append(resolved)
        return tuple(dict.fromkeys(result + list(inherited)))
    visited, reached = set(), set()
    def visit(path, architecture, inherited):
        data = inspect(path).get(architecture)
        if not data:
            errors.add(f'Missing {architecture} Mach-O slice: {path}'); return
        paths = runpaths(path, architecture, inherited)
        key = (path, architecture, paths)
        if key in visited: return
        if len(visited) >= 4096:
            errors.add('Too many distinct Mach-O loader contexts to audit safely'); return
        visited.add(key)
        reached.add((path, architecture))
        for value in data['dependencies']:
            if value.startswith('@rpath/'):
                candidates = [directory / value[len('@rpath/'):] for directory in paths]
            else:
                candidate = expand(value, path)
                candidates = [candidate] if candidate is not None else []
            resolved = None
            for candidate in candidates:
                try: candidate = candidate.resolve()
                except (OSError, RuntimeError) as failure:
                    errors.add(f'Invalid dependency {value!r} in {path}: {failure}'); continue
                if system(candidate) or candidate.is_file():
                    resolved = candidate; break
            if resolved is None:
                errors.add(f'Missing dependency {value!r} in {path} [{architecture}]'); continue
            if system(resolved): continue
            if not contained(resolved): external.add(str(resolved))
            visit(resolved, architecture, paths)
    for architecture in main:
        visit(executable, architecture, ())
    # Plugins are loaded dynamically. Audit their closure against the same
    # executable run paths even when no LC_LOAD_DYLIB refers to the plugin.
    # Visit plugin entry points before orphan libraries. A shared dependency
    # reached from a plugin must retain that caller's run-path stack, and may
    # be reached again from another plugin with a different stack.
    def plugin_first(path):
        return (not any(part in ('PlugIns', 'plugins', 'qml') for part in path.relative_to(app).parts), path)
    for path in sorted(inventory, key=plugin_first):
        for architecture in inspect(path):
            if (path, architecture) not in reached:
                visit(path, architecture, runpaths(executable, architecture, ()))
    floor = max(embedded_minimums.values(), key=macos_version, default=None)
    return dict(external_dependencies=sorted(external), errors=sorted(errors),
                maximum_embedded_minimum_macos=floor, embedded_minimum_macos=embedded_minimums)


def check_mac_minimum(report, info):
    """Fail an inaccurate deployment claim instead of silently changing support."""
    base = info.get('LSMinimumSystemVersion')
    by_architecture = info.get('LSMinimumSystemVersionByArchitecture', {})
    if not isinstance(by_architecture, dict):
        report['errors'].append('Invalid LSMinimumSystemVersionByArchitecture mapping'); return
    if base is not None:
        try: macos_version(base)
        except ValueError as failure: report['errors'].append(str(failure))
    floors = {}
    for key, minimum in report['embedded_minimum_macos'].items():
        architecture = key.rsplit('[', 1)[1][:-1]
        floors[architecture] = max(floors.get(architecture, minimum), minimum, key=macos_version)
    claims = {}
    for architecture, minimum in sorted(floors.items()):
        value = by_architecture.get(architecture, base)
        try: claimed = macos_version(value)
        except ValueError as failure:
            report['errors'].append(f'{architecture}: {failure}'); continue
        claims[architecture] = value
        if claimed < macos_version(minimum):
            field = 'LSMinimumSystemVersionByArchitecture' if architecture in by_architecture else 'LSMinimumSystemVersion'
            report['errors'].append(f'{field} {architecture} {value} is below embedded Mach-O minimum {minimum}')
    report['claimed_minimum_macos_by_architecture'] = claims


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
    if dirty: parser.error('All staging requires committed source, including newly added files')
    if not args.development_runtime and not args.licenses: parser.error('Supply dependency notices/provenance with --licenses')
    version=tomllib.loads((ROOT/'Cargo.toml').read_text())['package']['version']
    commit=git('rev-parse','HEAD').decode().strip()
    mac_audit = None
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
        mac_audit=check_mac_dependencies(app)
        check_mac_minimum(mac_audit, info)
        external=mac_audit['external_dependencies']
        if not args.development_runtime and (external or mac_audit['errors']):
            raise RuntimeError('Mac runtime audit failed: '+ '; '.join(mac_audit['errors'] +
                ['External runtime path: '+path for path in external]))
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
        input_binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
        source=f'https://github.com/rsmith4321/gyroflow-plus/tree/{commit}',external_mac_dependencies=external,
        public_release_approved=False)
    if mac_audit is not None: manifest['mac_runtime_audit'] = mac_audit
    (notices/'BUILD.json').write_text(json.dumps(manifest,indent=2)+'\n')
    # A complete committed source archive accompanies every stage. Refusing
    # dirty builds avoids omitting untracked source or collecting private files.
    with (output/f'Gyroflow-Plus-source-{commit[:12]}.tar').open('wb') as f:
        subprocess.run(['git','archive','--format=tar',commit],cwd=ROOT,stdout=f,check=True)
    if args.platform=='mac':
        subprocess.run(['codesign','--force','--deep','--sign','-',str(app)],check=True)
        subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
    # Signing changes the Mach-O executable bytes. Keep the final hash outside
    # the signed bundle to avoid a circular manifest/resource-signature hash.
    packaged_binary = app/'Contents/MacOS/gyroflow' if args.platform=='mac' else app/'GyroflowPlus.exe'
    receipt = dict(source_commit=commit, platform=args.platform,
        packaged_binary_sha256=hashlib.sha256(packaged_binary.read_bytes()).hexdigest(),
        input_binary_sha256=manifest['input_binary_sha256'],
        development_runtime=args.development_runtime, public_release_approved=False)
    if mac_audit is not None: receipt['mac_runtime_audit'] = mac_audit
    (output/'PACKAGE.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt,indent=2))


if __name__=='__main__': main()
