"""Audit every explicit vision1 path without confusing existence with acceptance."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

ROOT = Path(__file__).resolve().parents[1]


def inventory(root=ROOT):
    root = Path(root).resolve()
    rows = []
    seen = set()
    for line in (root / 'vision1.md').read_text(encoding='utf-8').splitlines():
        match = re.match(r'^\| `([^`]+)` \| (.+) \|$', line)
        if not match:
            continue
        name = match.group(1)
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or name in seen:
            raise ValueError('Unsafe or duplicate inventory path: ' + name)
        seen.add(name)
        target = root / name
        if target.is_symlink() or not target.resolve().is_relative_to(root):
            raise ValueError('Inventory cannot follow symlinks: ' + name)
        columns = match.group(2).split(' | ')
        if len(columns) not in (2, 3):
            raise ValueError('Malformed inventory row: ' + name)
        exists = target.is_file()
        rows.append({'path': name, 'exists': exists,
                     'sha256': hashlib.sha256(target.read_bytes()).hexdigest() if exists else None,
                     'bytes': target.stat().st_size if exists else None,
                     'expected_content': columns[-2], 'acceptance': columns[-1],
                     'acceptance_status': 'requires-evidence',
                     'kind': 'generated-proof' if name.startswith('lean/Conformance/') and name.endswith('.lean') else 'product-or-acceptance'})
    if not rows:
        raise ValueError('No explicit paths in vision1.md')
    return {'schema_version': 1, 'files': rows, 'total': len(rows),
            'missing': [row['path'] for row in rows if not row['exists']],
            'release_accepted': False,
            'scope': 'Working-byte inventory; presence and hashes are not acceptance evidence'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    report = inventory()
    raw = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        # Never silently replace a previous evidence snapshot.
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(raw)
    else:
        print(raw, end='')
    return 1 if report['missing'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
