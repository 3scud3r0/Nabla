"""Check pinned Mathlib sources and compiled entry modules without building them."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
IMPORTS = ('Mathlib.Tactic.Ring', 'Mathlib.Tactic.FieldSimp',
           'Mathlib.Tactic.Linarith', 'Mathlib.Tactic.NormNum', 'Mathlib.Data.Rat.Defs')


def validate(project=ROOT/'lean', *, sources_only=False):
    project = Path(project).resolve()
    manifest = json.loads((project/'lake-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('packagesDir') != '.lake/packages':
        raise ValueError('Unsupported package directory')
    packages = manifest.get('packages')
    if not isinstance(packages, list) or not packages:
        raise ValueError('Pinned dependency manifest required')
    seen = set()
    for package in packages:
        name, revision = package['name'], package['rev']
        if (not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name) or name in seen
                or not re.fullmatch(r'[0-9a-f]{40}', revision)):
            raise ValueError('Unique dependency names and immutable revisions required')
        seen.add(name)
        path = project/'.lake/packages'/name
        for arguments, expected in [(['rev-parse', 'HEAD'], revision),
                                     (['status', '--porcelain', '--untracked-files=normal'], '')]:
            actual = subprocess.check_output(['git', '-C', str(path), *arguments],
                                             text=True, timeout=20).strip()
            if actual != expected:
                raise ValueError('Pinned dependency changed: '+name)
    if 'mathlib' not in seen:
        raise ValueError('Mathlib dependency missing')
    missing = [name for name in IMPORTS if not (
        project/'.lake/packages/mathlib/.lake/build/lib/lean'/Path(name.replace('.', '/')+'.olean')
    ).is_file()]
    if missing and not sources_only:
        raise ValueError('Mathlib prerequisites not built: '+', '.join(missing)+
                         '; run scripts/setup_formal.sh before proof evaluation')
    return {'pinned_dependencies': len(seen), 'compiled_imports': len(IMPORTS)-len(missing),
            'scope': 'source pins and entry-module presence; kernel proof replay remains required'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources-only', action='store_true')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(validate(sources_only=args.sources_only), sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
