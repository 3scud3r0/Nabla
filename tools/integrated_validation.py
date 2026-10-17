"""Bounded, fail-closed validation campaign with tamper-evident local evidence.

This records *executed checks*, not scientific correctness, independent review,
or stable-release authorization. Run from a clean repository checkout in CI.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
LOG_LIMIT = 8 * 1024 * 1024
SCHEMA = 'nabla.integrated-validation.v1'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checks(profile):
    python = sys.executable
    base = [
        ('math_bundle', [python, 'tools/build_math_bundle.py', '--check'], 120, False),
        ('source_bundle', [python, 'tools/build_nabla_bundle.py', '--check'], 180, False),
        ('public_contracts', [python, 'tools/check_public_contracts.py'], 120, False),
        ('roadmap', [python, 'tools/check_roadmap.py'], 120, False),
        ('release_inventory', [python, 'tools/release_readiness.py'], 180, False),
        ('integrated_regressions', [python, '-m', 'pytest', '-q',
            'tests/test_integrated_validation_gate.py', 'tests/test_nabla_bundle.py',
            'tests/test_math_bundle.py', 'tests/test_release_contract.py',
            'tests/integration/test_global_scientific_cycle.py',
            'tests/integration/test_scientific_artifact.py'], 480, True),
        ('security_boundaries', [python, '-m', 'pytest', '-q',
            'tests/security/test_supply_chain.py', 'tests/test_roadmap_agent_controls.py',
            'tests/test_roadmap_network_security.py'], 480, True),
    ]
    if profile == 'comprehensive':
        base.append(('full_pytest', [python, '-m', 'pytest', '-q', 'tests'], 1800, True))
    return base


def _junit_counts(path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == 'testsuite' else root.findall('testsuite')
    if not suites:
        raise ValueError('Missing pytest test suite')
    counts = {name: sum(int(item.attrib.get(name, '0')) for item in suites)
              for name in ('tests', 'errors', 'failures', 'skipped')}
    if (counts['tests'] < 1 or counts['errors'] or counts['failures'] or counts['skipped']):
        raise ValueError('Pytest suite is empty, failed or contains skipped tests')
    return counts


def _run(command, cwd, timeout, stdout, stderr):
    with stdout.open('wb') as out, stderr.open('wb') as err:
        proc = subprocess.Popen(command, cwd=cwd, stdout=out, stderr=err,
                                stdin=subprocess.DEVNULL, start_new_session=(os.name != 'nt'))
        try:
            return proc.wait(timeout=timeout), False
        except subprocess.TimeoutExpired:
            if os.name != 'nt':
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
            proc.wait()
            return None, True


def run_step(name, command, timeout, pytest_step, output, *, cwd=ROOT):
    """A process exit of zero is insufficient if evidence is missing or tests skip."""
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', name):
        raise ValueError('Invalid check name')
    if not command or not all(isinstance(part, str) and part for part in command):
        raise ValueError('Command must be a nonempty explicit argv')
    stdout, stderr = output / (name + '.stdout'), output / (name + '.stderr')
    junit = output / (name + '.xml') if pytest_step else None
    argv = command + (['--junitxml=' + str(junit.resolve())] if junit else [])
    started = time.monotonic()
    code, timed_out = _run(argv, cwd, timeout, stdout, stderr)
    evidence = {'stdout': {'file': stdout.name, 'sha256': sha256(stdout), 'bytes': stdout.stat().st_size},
                'stderr': {'file': stderr.name, 'sha256': sha256(stderr), 'bytes': stderr.stat().st_size}}
    row = {'name': name, 'argv': command, 'timeout_seconds': timeout,
           'duration_seconds': round(time.monotonic() - started, 3),
           'exit_code': code, 'timed_out': timed_out, 'evidence': evidence,
           'status': 'passed'}
    if timed_out or code != 0 or any(item['bytes'] > LOG_LIMIT for item in evidence.values()):
        row['status'] = 'failed'
    if junit is not None:
        if not junit.is_file():
            row['status'] = 'failed'
        else:
            row['evidence']['junit'] = {'file': junit.name, 'sha256': sha256(junit),
                                        'bytes': junit.stat().st_size}
            try:
                row['pytest'] = _junit_counts(junit)
            except (ValueError, ET.ParseError, OSError):
                row['status'] = 'failed'
    return row


def verify(directory):
    """Detect absent/modified evidence; never treat unsigned evidence as trusted."""
    directory = Path(directory)
    data = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
    if data.get('schema') != SCHEMA or data.get('profile') not in {'ci', 'comprehensive'}:
        raise ValueError('Unknown evidence schema or profile')
    expected = [name for name, *_ in checks(data['profile'])]
    rows = data.get('checks')
    if not isinstance(rows, list) or [r.get('name') for r in rows] != expected:
        raise ValueError('Incomplete or reordered validation campaign')
    if data.get('passed') is not True or data.get('stable_release_accepted') is not False:
        raise ValueError('Campaign failed or incorrectly claimed stable release')
    for row in rows:
        if row.get('status') != 'passed' or row.get('exit_code') != 0 or row.get('timed_out'):
            raise ValueError('A required check did not pass')
        if not isinstance(row.get('evidence'), dict) or set(row['evidence']) != (
                {'stdout', 'stderr', 'junit'} if 'pytest' in row else {'stdout', 'stderr'}):
            raise ValueError('Missing evidence files')
        for entry in row['evidence'].values():
            name = entry.get('file')
            if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_.-]{0,80}', name):
                raise ValueError('Unsafe evidence filename')
            path = directory / name
            if path.is_symlink() or not path.is_file() or path.stat().st_size != entry['bytes'] or sha256(path) != entry['sha256']:
                raise ValueError('Missing or tampered evidence: ' + name)
        if 'pytest' in row and row['pytest'] != _junit_counts(directory / row['evidence']['junit']['file']):
            raise ValueError('Test counts differ from immutable evidence')
    return data


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.nabla/integrated-validation'))
    parser.add_argument('--profile', choices=('ci', 'comprehensive'), default='ci')
    parser.add_argument('--verify', type=Path, help='Verify an existing campaign; run no commands')
    args = parser.parse_args(argv)
    if args.verify is not None:
        try:
            verify(args.verify)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            print('Validation evidence rejected: ' + str(error), file=sys.stderr)
            return 1
        print('Validation evidence verified (local integrity only)')
        return 0
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    rows = []
    for name, argv, timeout, pytest_step in checks(args.profile):
        rows.append(run_step(name, argv, timeout, pytest_step, root))
    passed = all(row['status'] == 'passed' for row in rows)
    report = {'schema': SCHEMA, 'profile': args.profile, 'source_commit': commit,
              'checks': rows, 'passed': passed, 'stable_release_accepted': False,
              'scope': 'Local checks only: no independent mathematical/security review or publisher acceptance'}
    (root / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'passed': passed, 'checks': {row['name']: row['status'] for row in rows},
                      'report': str(root / 'report.json')}, sort_keys=True))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
