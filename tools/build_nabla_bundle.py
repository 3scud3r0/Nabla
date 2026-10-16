"""Build a deterministic, lossless text archive of Nabla source and configuration.

NABLA.TXT is a review/distribution artifact, not an executable or a compiler
output. Its indexed files remain the canonical editable sources. Discovery uses
Git's tracked and nonignored untracked files, including legacy code, services,
SDKs, tests and website sources. No installed dependencies or local task data
are included. math.txt and NABLA.TXT are never embedded recursively.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT/'NABLA.TXT'
SOURCE_SUFFIXES = frozenset({
    '.py', '.pyi', '.lean', '.c', '.h', '.cc', '.cpp', '.cxx', '.hpp', '.hxx',
    '.rs', '.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.sh', '.bash',
    '.ps1', '.cmd', '.bat', '.iss', '.html', '.css', '.scss', '.sql', '.proto',
    '.typ', '.tex', '.lua', '.r', '.jl', '.go', '.java', '.kt', '.f90', '.f',
    '.ipynb', '.toml', '.yaml', '.yml',
})
CONFIG_NAMES = frozenset({
    'LICENSE', 'COPYING', 'NOTICE',
    '.gitignore', '.gitattributes', '.gitmodules', 'Makefile', 'Dockerfile',
    'lean-toolchain', 'Cargo.lock', 'package-lock.json', 'yarn.lock', 'uv.lock',
})
EXCLUDED_PARTS = frozenset({'.git', '.venv', '.lake', '__pycache__', 'node_modules', '.nabla'})
EXCLUDED_PREFIXES = ('build/', 'dist/', 'website/dist/', 'sdk/rust/target/')
OUTPUT_NAMES = frozenset({'math.txt', 'NABLA.TXT', 'NABLA.txt'})
MAGIC = b'NABLA SOURCE AND CONFIGURATION ARCHIVE\nFORMAT_VERSION: 1\n'
FILE_MARKER = b'@@NABLA_FILE '
END_MARKER = b'\n@@NABLA_END_FILE\n'


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode('utf-8')


def _selected(name):
    path = Path(name)
    if (name in OUTPUT_NAMES or EXCLUDED_PARTS.intersection(path.parts)
            or name.startswith(EXCLUDED_PREFIXES)):
        return False
    if path.suffix.lower() in SOURCE_SUFFIXES or path.name in CONFIG_NAMES:
        return True
    # Include declarative application/schema resources, not benchmark outputs,
    # private data, credentials or generated conformance inventories.
    if path.suffix == '.json':
        return (name.startswith(('protocol/schema/', 'templates/', 'examples/', 'configs/'))
                or name in {'website/package.json', 'src/nablamath/compatibility.json',
                            'lean/lake-manifest.json'}
                or name.endswith('/package.json'))
    return False


def source_paths(root=ROOT):
    root = Path(root).resolve()
    actual = subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], text=True).strip()
    if Path(actual).resolve() != root:
        raise ValueError('Bundle root must be the actual checkout root')
    listing = subprocess.check_output([
        'git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard',
    ])
    names = sorted(set(name.decode('utf-8') for name in listing.split(b'\0') if name))
    paths = []
    for name in names:
        if not _selected(name):
            continue
        path = root/name
        if path.is_symlink():
            raise ValueError('Source symlinks require an explicit packaging policy: '+name)
        if not path.resolve().is_relative_to(root):
            raise ValueError('Source path escapes checkout: '+name)
        if not path.is_file():
            # A deleted tracked file is not silently represented as present.
            if not path.exists():
                continue
            raise ValueError('Source path is not a regular file: '+name)
        paths.append(path)
    return tuple(paths)


def records(root=ROOT):
    root = Path(root).resolve()
    result = []
    for path in source_paths(root):
        raw = path.read_bytes()
        try:
            text = raw.decode('utf-8')
            encoding = 'utf-8'
            payload = raw
            lines = len(text.splitlines())
        except UnicodeDecodeError:
            encoding = 'base64'
            payload = base64.b64encode(raw)
            lines = None
        metadata = {'path': path.relative_to(root).as_posix(),
                    'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
                    'lines': lines, 'encoding': encoding, 'payload_bytes': len(payload)}
        result.append((metadata, payload))
    return result


def build_bundle(root=ROOT):
    selected = records(root)
    manifest = {
        'format_version': 1, 'file_count': len(selected),
        'source_bytes': sum(metadata['bytes'] for metadata, _ in selected),
        'text_source_lines': sum(metadata['lines'] or 0 for metadata, _ in selected),
        'selection': 'Git tracked and nonignored source/configuration files, including legacy sources',
        'exclusions': ['installed dependencies', 'ignored files', 'local task data',
                       'binary assets', 'documentation prose', 'benchmark result data',
                       'math.txt', 'NABLA.TXT'],
        'payload_contract': 'Read payload_bytes after each marker; source bytes and line endings are preserved',
        'files': [metadata for metadata, _ in selected],
    }
    parts = [MAGIC, b'MANIFEST ', _json(manifest), b'\n\n']
    for metadata, payload in selected:
        parts.extend((FILE_MARKER, _json(metadata), b'\n', payload, END_MARKER))
    return b''.join(parts)


def inspect_bundle(data):
    """Verify internal file hashes and framing without executing archived code."""
    if not isinstance(data, bytes) or not data.startswith(MAGIC+b'MANIFEST '):
        raise ValueError('Invalid Nabla archive header')
    position = len(MAGIC+b'MANIFEST ')
    newline = data.index(b'\n', position)
    manifest = json.loads(data[position:newline])
    if manifest.get('format_version') != 1 or not isinstance(manifest.get('files'), list):
        raise ValueError('Invalid archive manifest')
    position = newline+2
    seen = set()
    for expected in manifest['files']:
        if data[position:position+len(FILE_MARKER)] != FILE_MARKER:
            raise ValueError('Missing file frame')
        position += len(FILE_MARKER)
        newline = data.index(b'\n', position)
        metadata = json.loads(data[position:newline])
        if metadata != expected:
            raise ValueError('File frame differs from index')
        name = metadata['path']
        if (not isinstance(name, str) or name in seen or Path(name).is_absolute()
                or '..' in Path(name).parts):
            raise ValueError('Duplicate or invalid source path')
        seen.add(name)
        size = metadata['payload_bytes']
        if type(size) is not int or not 0 <= size <= len(data):
            raise ValueError('Invalid source payload length')
        start, end = newline+1, newline+1+size
        payload = data[start:end]
        if metadata['encoding'] == 'base64':
            raw = base64.b64decode(payload, validate=True)
        elif metadata['encoding'] == 'utf-8':
            payload.decode('utf-8')
            raw = payload
        else:
            raise ValueError('Unknown payload encoding')
        if len(raw) != metadata['bytes'] or hashlib.sha256(raw).hexdigest() != metadata['sha256']:
            raise ValueError('Source payload hash or size mismatch')
        if data[end:end+len(END_MARKER)] != END_MARKER:
            raise ValueError('Invalid source payload terminator')
        position = end+len(END_MARKER)
    if position != len(data) or manifest['file_count'] != len(seen):
        raise ValueError('Trailing content or incorrect file count')
    if manifest['source_bytes'] != sum(row['bytes'] for row in manifest['files']):
        raise ValueError('Incorrect aggregate source size')
    return manifest


def write_bundle(output, data):
    """Publish a complete archive atomically; interrupted writes retain the old file."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix='.'+output.name+'.', dir=output.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, output)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    data = build_bundle()
    manifest = inspect_bundle(data)
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != data:
            print('NABLA.TXT is missing or stale: '+str(args.output))
            return 1
    else:
        write_bundle(args.output, data)
    print(json.dumps({'output': str(args.output), 'checked': args.check,
                      'files': manifest['file_count'], 'source_lines': manifest['text_source_lines'],
                      'sha256': hashlib.sha256(data).hexdigest()}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
