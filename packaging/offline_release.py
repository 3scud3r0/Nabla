"""Offline wheel plans and source-bound SBOM; no publisher signature is implied.

Install execution is restricted to a dedicated virtual environment. Historical
archives are never overwritten. No shell, dependency resolution or network is used.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile
from email.parser import BytesParser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from verify_wheel import verify_wheel


def wheel_identity(wheel):
    path = Path(wheel).resolve()
    verify_wheel(path)
    with zipfile.ZipFile(path) as archive:
        metadata = [n for n in archive.namelist() if n.endswith('.dist-info/METADATA')]
        message = BytesParser().parsebytes(archive.read(metadata[0]))
    if message['Name'] != 'nablamath':
        raise ValueError('Only nablamath wheels are supported')
    return {'path': str(path), 'name': message['Name'], 'version': message['Version'],
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'requires_python': message['Requires-Python'],
            'requires_dist': message.get_all('Requires-Dist', []),
            'license': message.get('License-Expression', 'NOASSERTION')}


def release_plan(wheel, environment, *, expected_sha256, operation='install'):
    if operation not in {'install', 'upgrade', 'downgrade', 'repair'}:
        raise ValueError('Unknown release operation')
    identity = wheel_identity(wheel)
    if identity['sha256'] != expected_sha256:
        raise ValueError('Expected wheel digest mismatch')
    environment = Path(environment).absolute()
    if environment == Path('/') or environment == Path(sys.prefix) or environment.is_symlink():
        raise ValueError('Dedicated environment required')
    python = environment / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    command = [str(python), '-m', 'pip', 'install', '--no-index', '--no-deps',
               '--force-reinstall', identity['path']]
    return {'schema': 'nabla.offline-release.v1', 'operation': operation,
            'wheel': identity, 'environment': str(environment), 'command': command,
            'network': False, 'dependencies_installed': False,
            'publisher_authenticated': False}


def execute_plan(plan):
    """Rebuild the plan and recheck bytes before any installer invocation."""
    rebuilt = release_plan(plan['wheel']['path'], plan['environment'],
                           expected_sha256=plan['wheel']['sha256'], operation=plan['operation'])
    if rebuilt != plan:
        raise ValueError('Release plan modified')
    environment = Path(plan['environment'])
    if not (environment / 'pyvenv.cfg').is_file():
        raise ValueError('Create an isolated venv before installing')
    subprocess.run(plan['command'], check=True, capture_output=True, text=True, timeout=120)
    python = plan['command'][0]
    result = subprocess.run([python, '-c',
        'import importlib.metadata as m; import nablamath; print(m.version("nablamath"))'],
        check=True, capture_output=True, text=True, timeout=30)
    if result.stdout.strip() != plan['wheel']['version']:
        raise ValueError('Installed version differs from release plan')
    return {'installed_version': result.stdout.strip(), 'wheel_sha256': plan['wheel']['sha256'],
            'platform': sys.platform, 'optional_dependencies_verified': False}


def wheel_sbom(wheel, *, source_commit):
    if len(source_commit) != 40 or any(c not in '0123456789abcdef' for c in source_commit):
        raise ValueError('Full hexadecimal source commit required')
    item = wheel_identity(wheel)
    return {'spdxVersion': 'SPDX-2.3', 'dataLicense': 'CC0-1.0',
            'SPDXID': 'SPDXRef-DOCUMENT', 'name': 'nablamath-wheel-inventory',
            'documentNamespace': 'https://github.com/3scud3r0/Nabla/sbom/' + item['sha256'],
            'creationInfo': {'creators': ['Tool: Nabla offline_release'],
                             'created': '2026-10-15T00:00:00Z',
                             'comment': 'Deterministic inventory date; not an authenticated build timestamp.'},
            'packages': [{'SPDXID': 'SPDXRef-nablamath', 'name': item['name'],
                          'versionInfo': item['version'], 'downloadLocation': 'NOASSERTION',
                          'filesAnalyzed': False, 'licenseConcluded': 'NOASSERTION',
                          'licenseDeclared': item['license'],
                          'checksums': [{'algorithm': 'SHA256', 'checksumValue': item['sha256']}],
                          'sourceInfo': 'Declared source commit: ' + source_commit,
                          'comment': 'Source binding is caller-declared; optional requirements are not installed inventory.'}],
            'relationships': [{'spdxElementId': 'SPDXRef-DOCUMENT', 'relationshipType': 'DESCRIBES',
                               'relatedSpdxElement': 'SPDXRef-nablamath'}],
            'annotations': [],
            'comment': json.dumps({'declared_requirements': item['requires_dist'],
                                   'python': item['requires_python'], 'signed': False}, sort_keys=True)}
