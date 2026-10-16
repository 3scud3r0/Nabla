"""Bind a verified wheel, SPDX inventory and local provenance without inventing a signature."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def build(wheel, output, *, acceptance=None):
    spec = importlib.util.spec_from_file_location('release_metadata_offline', ROOT/'packaging/offline_release.py')
    offline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(offline)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip())
    identity = offline.wheel_identity(wheel)
    sbom = offline.wheel_sbom(wheel, source_commit=commit)
    if acceptance is not None:
        spec = importlib.util.spec_from_file_location('metadata_signed_validation', ROOT/'packaging/signed_release.py')
        signed = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = signed
        spec.loader.exec_module(signed)
        with Path(acceptance).open('rb') as stream:
            raw = stream.read(32769)
        statement = signed._load(raw)
        # Metadata assembly time; the tool does not impersonate a human reviewer.
        sbom['annotations'] = [{'annotationType': 'REVIEW', 'annotator': 'Tool: Nabla release metadata',
                                'annotationDate': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                'comment': json.dumps(statement, sort_keys=True)}]
        signed.validate_stable_acceptance(sbom, {'version': identity['version'],
            'source': {'commit': commit}, 'wheel': {'sha256': identity['sha256']}})
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    sbom_raw = (json.dumps(sbom, sort_keys=True, indent=2)+'\n').encode()
    provenance = {'schema': 'nabla.build-provenance.v1', 'source_commit': commit,
                  'source_dirty': dirty, 'source_binding': 'declared-not-reproduced',
                  'wheel': {'filename': Path(wheel).name, 'sha256': identity['sha256']},
                  'sbom': {'filename': 'sbom.spdx.json', 'sha256': hashlib.sha256(sbom_raw).hexdigest()},
                  'publisher_authenticated': False,
                  'scope': 'local artifact consistency; external attestation and publisher trust are separate'}
    (output/'sbom.spdx.json').write_bytes(sbom_raw)
    (output/'provenance.json').write_text(json.dumps(provenance, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    lines = [f"{identity['sha256']}  {Path(wheel).name}"]
    for name in ('sbom.spdx.json', 'provenance.json'):
        lines.append(hashlib.sha256((output/name).read_bytes()).hexdigest()+'  '+name)
    (output/'SHA256SUMS').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return provenance


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('wheel', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--acceptance', type=Path, help='Reviewed gate statement to bind into the signed SBOM')
    args = parser.parse_args(argv)
    print(json.dumps(build(args.wheel, args.output, acceptance=args.acceptance), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
