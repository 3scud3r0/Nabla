"""Audit every vision1 path and the frozen local CPU release contract.

Presence and matching hashes are inventory evidence, never per-file acceptance.
--wheel additionally installs the exact verified wheel in a fresh offline venv.
This tool cannot authenticate independent reviewers or grant a stable release.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import venv

ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_GATES = (
    'exact_commit_platform_ci', 'windows_install_upgrade_uninstall',
    'independent_security_review', 'mathematical_translation_review',
    'license_and_provenance_review', 'publisher_authority_and_release_acceptance',
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(root=ROOT):
    root = Path(root).resolve()
    source = (root/'vision1.md').read_text(encoding='utf-8')
    entries = []
    section = ''
    for line in source.splitlines():
        if line.startswith('## '):
            section = line[3:]
        match = re.match(r'^\| `([^`]+)` \|', line)
        if not match:
            continue
        name = match[1]
        path = root/name
        if (Path(name).is_absolute() or '..' in Path(name).parts
                or any(p.is_symlink() for p in (path, *path.parents))
                or not path.resolve().is_relative_to(root)):
            raise ValueError('Unsafe release source path: '+name)
        cells = line.split('|')
        entries.append({'path': name, 'section': section,
                        'acceptance': cells[-2].strip(),
                        'present': path.is_file(), 'sha256': digest(path) if path.is_file() else None})
    names = [row['path'] for row in entries]
    if len(names) != 212 or len(set(names)) != len(names):
        raise ValueError('vision1 must preserve its 212 individual path identities')
    return entries


def validate(root=ROOT):
    from nablamath import __version__
    from nablamath.compatibility import support_contract
    from nablamath.stability import public_contract, validate_public_api
    root = Path(root).resolve()
    entries = inventory(root)
    missing = [row['path'] for row in entries if not row['present']]
    if missing:
        raise ValueError('Missing vision1 files: '+', '.join(missing))
    project = (root/'pyproject.toml').read_text(encoding='utf-8')
    declared = re.search(r'^version = "([^"]+)"$', project, re.M)
    if not declared or declared[1] != __version__ or support_contract()['package_version'] != __version__:
        raise ValueError('Package, wheel metadata and compatibility versions disagree')
    for name, expected in public_contract()['schema_sha256'].items():
        if digest(root/name) != expected:
            raise ValueError('Frozen protocol schema changed: '+name)
    contract = validate_public_api()
    return {'schema_version': 1, 'version': __version__, 'profile': contract['profile'],
            'inventory': entries, 'public_api': contract,
            'external_gates': [{'gate': gate, 'status': 'not_established_by_local_checks'}
                               for gate in EXTERNAL_GATES],
            'stable_release_accepted': False}


def verify_wheel_install(wheel):
    spec = importlib.util.spec_from_file_location('release_wheel_integrity', ROOT/'tools/verify_wheel.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    path = Path(wheel).resolve()
    integrity = verifier.verify_wheel(path)
    from nablamath import __version__
    if integrity['name'] != 'nablamath' or integrity['version'] != __version__:
        raise ValueError('Wheel identity differs from checkout')
    with tempfile.TemporaryDirectory(prefix='nabla-release-') as directory:
        target = Path(directory)
        venv.EnvBuilder(with_pip=True).create(target/'venv')
        python = target/'venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
        subprocess.run([str(python), '-I', '-m', 'pip', 'install', '--no-index', '--no-deps', str(path)],
                       cwd=target, capture_output=True, text=True, check=True, timeout=120)
        # -I plus a cwd outside the checkout forbids accidentally testing local sources.
        for script in ['tools/release_smoke.py']:
            result = subprocess.run([str(python), '-I', str(ROOT/script), str(target/'data')],
                                    cwd=target, capture_output=True, text=True, check=True, timeout=120)
        report = json.loads(result.stdout)
        if report['version'] != __version__:
            raise ValueError('Installed package version differs from wheel')
    return {**integrity, 'clean_offline_install': True, 'smoke': report}


def verify_publisher_acceptance(envelope_path, trust_path, artifacts, *, now_unix):
    """Verify an existing authority's signed declaration; never enroll a key."""
    if not Path(trust_path).is_file():
        raise ValueError('An existing, independently configured issuer trust store is required')
    spec = importlib.util.spec_from_file_location('release_readiness_signed', ROOT/'packaging/signed_release.py')
    signed = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = signed
    spec.loader.exec_module(signed)
    receipt = signed.IssuerTrust(trust_path).verify(signed.load_envelope(envelope_path), now_unix=now_unix)
    result = signed.verify_artifacts(receipt, artifacts)
    from nablamath import __version__
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip()
    if (dirty or receipt.body['source']['commit'] != commit or receipt.body['version'] != __version__
            or not result['stable_acceptance']['publisher_attested']):
        raise ValueError('Stable acceptance requires this clean checkout, final version and exact commit')
    return {'manifest_id': receipt.manifest_id, 'publisher_authenticated': True,
            'acceptance': result['stable_acceptance'],
            'scope': 'enrolled publisher declaration; evidence references not independently reexecuted'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--wheel', type=Path)
    parser.add_argument('--require-stable', action='store_true')
    parser.add_argument('--signed-release', type=Path)
    parser.add_argument('--trust-store', type=Path)
    parser.add_argument('--artifacts', type=Path)
    args = parser.parse_args(argv)
    authority = (args.signed_release, args.trust_store, args.artifacts)
    if any(authority) and not all(authority):
        parser.error('--signed-release, --trust-store and --artifacts must be supplied together')
    report = validate()
    report['source_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    if args.wheel:
        report['wheel'] = verify_wheel_install(args.wheel)
    if all(authority):
        report['authority'] = verify_publisher_acceptance(*authority, now_unix=int(time.time()))
        report['stable_release_accepted'] = True
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
    print(json.dumps({'version': report['version'], 'paths': len(report['inventory']),
                      'stable_release_accepted': report['stable_release_accepted'], 'external_gates': report['external_gates']}))
    return 2 if args.require_stable and not report['stable_release_accepted'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
