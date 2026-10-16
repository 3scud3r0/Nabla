"""Offline preservation and release evidence; hashes establish identity, not truth.

The index pins original bytes and declared origins. Custody is a hash chain of
local records, not a signature or independently authenticated timestamp.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess

ROOTS = ('docs/history', 'legacy', 'benchmarks/fixtures', 'benchmarks/results')
INDEX = 'docs/history/preservation-index.json'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sealed(value):
    return {**value, 'record_id': digest(canonical(value))}


def validate_seal(value):
    body = dict(value)
    observed = body.pop('record_id', None)
    if observed != digest(canonical(body)):
        raise ValueError('Record hash mismatch')
    return body


def safe_path(root, name):
    relative = PurePosixPath(name)
    if (not name or relative.is_absolute() or '..' in relative.parts or '\\' in name
            or ':' in name or relative.as_posix() != name):
        raise ValueError('Unsafe relative path')
    root = Path(root).resolve()
    path = root.joinpath(*relative.parts)
    if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root.parent):
        raise ValueError('Symlink not permitted')
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path escapes root')
    return path


def preserve(root, *, commit, repository, paths=ROOTS):
    root = Path(root)
    if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
        raise ValueError('Full source commit required')
    if not repository.startswith('https://'):
        raise ValueError('Explicit HTTPS source repository required')
    records = []
    for directory in sorted(set(paths)):
        folder = safe_path(root, directory)
        if not folder.is_dir():
            raise ValueError('Preserved directory missing')
        for path in sorted(folder.rglob('*')):
            relative = path.relative_to(root).as_posix()
            if relative == INDEX:
                continue
            safe_path(root, relative)
            if path.is_file():
                content = path.read_bytes()
                role = ('historical-aspiration' if relative.startswith('docs/history/')
                        else 'non-production-legacy' if relative.startswith('legacy/')
                        else 'reference-fixture' if relative.startswith('benchmarks/fixtures/')
                        else 'frozen-result-including-failures')
                records.append({'path': relative, 'sha256': digest(content),
                                'size': len(content), 'role': role,
                                'origin': {'repository': repository, 'commit': commit,
                                           'path': relative}})
    return sealed({'schema': 'nabla.preservation.v1', 'roots': sorted(set(paths)),
                   'records': records,
                   'scope': 'Byte preservation only; historical claims are not implementation evidence.'})


def verify_preservation(root, index, *, require_complete=True):
    body = validate_seal(index)
    if body['schema'] != 'nabla.preservation.v1':
        raise ValueError('Unsupported preservation schema')
    expected = set()
    for row in body['records']:
        name = row['path']
        if name in expected or not any(name.startswith(x + '/') for x in body['roots']):
            raise ValueError('Duplicate or out-of-scope preserved path')
        expected.add(name)
        path = safe_path(root, name)
        data = path.read_bytes()
        if len(data) != row['size'] or digest(data) != row['sha256']:
            raise ValueError('Preserved bytes changed: ' + name)
        origin = row['origin']
        if origin['path'] != name or len(origin['commit']) != 40 or not origin['repository'].startswith('https://'):
            raise ValueError('Invalid source origin')
    if require_complete:
        actual = set()
        for directory in body['roots']:
            for path in safe_path(root, directory).rglob('*'):
                if path.is_file() and path.relative_to(root).as_posix() != INDEX:
                    actual.add(path.relative_to(root).as_posix())
        if expected != actual:
            raise ValueError('Preserved file set changed; create a separate campaign')
    return {'verified_files': len(expected), 'index_id': index['record_id'], 'scientific_validation': False}


def verify_fixture(root, manifest):
    """Check a pinned external mirror fixture; does not contact its publisher."""
    if (len(manifest['commit']) != 40 or not manifest['mirror'].startswith('https://')
            or not manifest.get('license_id') or not manifest.get('license_basis')
            or not manifest.get('original_reference')):
        raise ValueError('Pinned provenance and license declaration required')
    checked = []
    for name, row in sorted(manifest['files'].items()):
        data = safe_path(root, name).read_bytes()
        if digest(data) != row['sha256']:
            raise ValueError('Fixture checksum mismatch')
        if not row.get('path'):
            raise ValueError('Upstream path required')
        checked.append(name)
    if not checked:
        raise ValueError('Empty fixture')
    return {'files': checked, 'commit': manifest['commit'],
            'license_id': manifest['license_id'], 'upstream_independently_checked': False}


def campaign_record(root, *, campaign, protocol, license_id, files, previous=None):
    if not campaign or not protocol or not license_id or not files:
        raise ValueError('Campaign, protocol, license and files required')
    if previous is not None:
        validate_seal(previous)
        if previous['campaign'] == campaign:
            raise ValueError('New results require a distinct campaign')
    artifacts = []
    for name in sorted(set(files)):
        data = safe_path(root, name).read_bytes()
        row = {'path': name, 'sha256': digest(data), 'size': len(data)}
        if name.endswith('.json'):
            # This replays JSON meaning under the documented canonical encoding,
            # not the experiment or a theorem contained in the document.
            row['semantic_json_sha256'] = digest(canonical(json.loads(data)))
        artifacts.append(row)
    return sealed({'schema': 'nabla.custody.v1', 'campaign': campaign,
                   'protocol': protocol, 'license_id': license_id,
                   'previous': previous['record_id'] if previous else None,
                   'artifacts': artifacts, 'authenticated_custodian': False})


def verify_chain(root, records):
    previous = None
    campaigns = set()
    for record in records:
        body = validate_seal(record)
        if body['schema'] != 'nabla.custody.v1' or body['previous'] != previous:
            raise ValueError('Broken custody chain')
        if body['campaign'] in campaigns or not body['protocol'] or not body['license_id']:
            raise ValueError('Campaign reuse or missing declaration')
        campaigns.add(body['campaign'])
        for row in body['artifacts']:
            data = safe_path(root, row['path']).read_bytes()
            if digest(data) != row['sha256'] or len(data) != row['size']:
                raise ValueError('Frozen result changed')
            if 'semantic_json_sha256' in row and digest(canonical(json.loads(data))) != row['semantic_json_sha256']:
                raise ValueError('Semantic JSON mismatch')
        previous = record['record_id']
    return {'campaigns': len(campaigns), 'head': previous, 'experiment_reexecuted': False}


def audit_production_boundary(root):
    """Detect explicit legacy import paths in canonical Python sources."""
    import ast
    findings = []
    for path in sorted((Path(root) / 'src').rglob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            names = ([node.module] if isinstance(node, ast.ImportFrom)
                     else [a.name for a in node.names] if isinstance(node, ast.Import) else [])
            for name in names:
                if name and name.split('.')[0] in {'legacy', 'archive'}:
                    findings.append({'path': path.relative_to(root).as_posix(), 'line': node.lineno, 'module': name})
    if findings:
        raise ValueError('Production imports historical code: ' + repr(findings))
    return {'explicit_legacy_imports': 0, 'dynamic_imports_audited': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--create', action='store_true')
    args = parser.parse_args()
    target = args.root / INDEX
    if args.create:
        if target.exists():
            parser.error('Index already exists; preserve it and use a new campaign')
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.root, text=True).strip()
        result = preserve(args.root, commit=commit, repository='https://github.com/3scud3r0/Nabla')
        target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    index = json.loads(target.read_text())
    print(json.dumps({'preservation': verify_preservation(args.root, index),
                      'boundary': audit_production_boundary(args.root)}, indent=2))


if __name__ == '__main__':
    main()
