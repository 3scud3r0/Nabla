"""Install exact Lake manifest commits without fetching repository history.

Never update a lockfile or overwrite an existing checkout. Interrupted clones may
be preserved explicitly with --preserve-incomplete before installing a new copy.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(command, *, cwd, timeout=180):
    with subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, start_new_session=os.name != 'nt') as process:
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            if os.name != 'nt':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                process.kill()
            process.communicate()
            raise
    if process.returncode:
        raise RuntimeError('Command failed: ' + command[0] + '\n' + (stdout + stderr)[-4000:])
    return stdout.strip()


def packages(project):
    project = Path(project)
    manifest = project / 'lake-manifest.json'
    raw = manifest.read_bytes()
    if len(raw) > 1_000_000:
        raise ValueError('Lake manifest exceeds budget')
    data = json.loads(raw)
    if data.get('packagesDir') != '.lake/packages' or not isinstance(data.get('packages'), list):
        raise ValueError('Unsupported Lake manifest')
    names = set()
    result = []
    for package in data['packages']:
        name, revision, url = package.get('name'), package.get('rev'), package.get('url')
        if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', name)
                or name in names or not isinstance(revision, str) or not re.fullmatch(r'[0-9a-f]{40}', revision)
                or not isinstance(url, str) or not re.fullmatch(r'https://github\.com/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', url)
                or package.get('type') != 'git' or package.get('subDir') is not None):
            raise ValueError('Unsupported or ambiguous pinned dependency')
        names.add(name)
        result.append((name, revision, url))
    if not result or len(result) > 100:
        raise ValueError('Invalid dependency count')
    return raw, result


def install(project, *, preserve_incomplete=False):
    project = Path(project).resolve()
    original, dependencies = packages(project)
    destination = project / '.lake/packages'
    if (project / '.lake').is_symlink() or destination.is_symlink():
        raise ValueError('Dependency directory cannot be a symlink')
    destination.mkdir(parents=True, exist_ok=True)
    results = []
    for name, revision, url in dependencies:
        target = destination / name
        if target.is_symlink():
            raise ValueError('Dependency cannot be a symlink: ' + name)
        if target.exists():
            try:
                actual = run(['git', 'rev-parse', '--verify', 'HEAD^{commit}'], cwd=target, timeout=10)
            except RuntimeError:
                if not preserve_incomplete or not (target / '.git/HEAD').is_file():
                    raise ValueError('Existing dependency is incomplete; preserve it explicitly: ' + name)
                archive = project.parent / '.nabla/formal-incomplete' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                archive.mkdir(parents=True, exist_ok=False)
                target.rename(archive / name)
            else:
                if actual != revision:
                    raise ValueError('Existing dependency differs from manifest; refusing overwrite: ' + name)
                if run(['git', 'status', '--porcelain', '--untracked-files=normal'], cwd=target, timeout=30):
                    raise ValueError('Existing dependency has local changes: ' + name)
                results.append({'name': name, 'revision': revision, 'status': 'reused'})
                print(json.dumps(results[-1]), flush=True)
                continue
        with tempfile.TemporaryDirectory(prefix='.nabla-fetch-', dir=destination) as temporary:
            staging = Path(temporary) / name
            staging.mkdir()
            run(['git', 'init', '--quiet'], cwd=staging)
            run(['git', 'remote', 'add', 'origin', url], cwd=staging)
            run(['git', 'fetch', '--depth=1', '--no-tags', 'origin', revision], cwd=staging)
            actual = run(['git', 'rev-parse', '--verify', 'FETCH_HEAD^{commit}'], cwd=staging)
            if actual != revision:
                raise ValueError('Fetched commit does not match lockfile: ' + name)
            run(['git', '-c', 'core.hooksPath=/dev/null', 'checkout', '--quiet', '--detach', revision], cwd=staging)
            staging.rename(target)
        results.append({'name': name, 'revision': revision, 'status': 'installed'})
        print(json.dumps(results[-1]), flush=True)
    if (project / 'lake-manifest.json').read_bytes() != original:
        raise ValueError('Manifest changed during setup')
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=ROOT / 'lean')
    parser.add_argument('--preserve-incomplete', action='store_true')
    args = parser.parse_args(argv)
    try:
        install(args.project, preserve_incomplete=args.preserve_incomplete)
    except (ValueError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
        parser.exit(1, str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
