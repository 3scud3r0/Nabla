"""Run a local laboratory acceptance rehearsal; never certify frontier adoption."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from fractions import Fraction
import importlib.metadata
import platform

ROOT = Path(__file__).resolve().parents[1]


def save(path, value):
    from nablamath.core.semantic_ir import canonical_json
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(canonical_json(value) + '\n', encoding='utf-8')
    temporary.replace(path)


def assurance(root):
    """Recheck scientific outputs and deliberately misuse trusted-peer credentials."""
    from nablamath.documents.publication import verify_publication
    from nablamath.formal.bundle import verify_formal_bundle
    from nablamath.export.research_bundle import verify_research_bundle
    from nablamath.knowledge.storage import SnapshotStore
    from nablamath.knowledge.identity import PeerKey
    from nablamath.knowledge.provenance_audit import replay_domain
    from nablamath.core.units import Quantity, ONE, METER, SECOND, KILOGRAM, VOLT
    from nablamath.domains.contracts import PASCAL, OHM
    from nablamath.domains.materials import isotropic_elasticity
    from nablamath.domains.circuits import series_rlc, HENRY, FARAD
    from nablamath.domains.chemistry import reversible_first_order, CONCENTRATION
    from nablamath.domains.earth import layered_hydrostatics
    from nablamath.worlds.pde.diffusion import solve_diffusion
    science = root / 'science'
    # Upstream failure must remain explicit, without creating an empty peer DB
    # that could be mistaken for an artifact produced by the science stage.
    prerequisites = ('peer-1.sqlite3', 'summary.json')
    missing = [name for name in prerequisites if not (science / name).is_file()]
    if missing:
        save(root / 'assurance.json', {
            'simulation': True, 'status': 'blocked', 'missing_science_artifacts': missing,
            'checks': {}, 'all_checks_passed': False,
            'experimental_physical_validation': False, 'independent_peer_review': False})
        return False
    checks = {name + '_publication_replayed': verify_publication(science / name)
              for name in ('research_paper', 'engineering_report', 'teaching')}
    checks['formal_backend_replayed'] = verify_formal_bundle(science / 'formal', project=ROOT / 'lean')
    checks['mixed_scientific_dataset_replayed'] = verify_research_bundle(science / 'dataset-release')
    # Use a separate receiver: never revoke the valid upstream evidence repository.
    source = SnapshotStore(science / 'peer-1.sqlite3')
    envelope = source.delta()[0]
    peer = envelope['snapshot']['peer_id']
    key = PeerKey(peer, envelope['public_key'])
    receiver = SnapshotStore(root / 'assurance-peer.sqlite3')
    receiver.pin(key)
    checks['valid_peer_snapshot_accepted'] = receiver.ingest(envelope)['valid']
    bad = copy.deepcopy(envelope)
    bad['signature'] = '00' * 64
    rejected = receiver.ingest(bad)
    checks['forged_signature_quarantined'] = not rejected['valid'] and rejected['quarantined']
    receiver.pin(PeerKey(peer, key.public_key, revoked=True))
    checks['revoked_key_rejected'] = not receiver.ingest(envelope)['valid']
    try:
        receiver.delta()
        checks['revoked_persisted_snapshot_not_exported'] = False
    except ValueError:
        checks['revoked_persisted_snapshot_not_exported'] = True
    models = []
    for scale in (1, 2, 5, 10):
        elastic = isotropic_elasticity(Quantity(1000 * scale, PASCAL), Quantity('1/4', ONE),
                                      [['1/1000', 0, 0], [0, 0, 0], [0, 0, 0]])
        ac = series_rlc(Quantity(10 * scale, OHM), Quantity(1, HENRY), Quantity(1, FARAD),
                        Quantity(5, VOLT), Quantity(1, SECOND**-1))
        kinetics = reversible_first_order(Quantity(scale, CONCENTRATION), Quantity(0, CONCENTRATION),
                                          Quantity(1, SECOND**-1), Quantity(1, SECOND**-1), Quantity(1, SECOND))
        layers = layered_hydrostatics([Quantity(2, METER), Quantity(3, METER)],
                                     [Quantity(1000 * scale, KILOGRAM / METER**3), Quantity(2000 * scale, KILOGRAM / METER**3)],
                                     Quantity(10, METER / SECOND**2), Quantity(0, PASCAL))
        checks[f'elastic_reference_{scale}'] = elastic['outputs']['stress'][0][0] == str(Fraction(6 * scale, 5))
        checks[f'rlc_resonance_reference_{scale}'] = abs(ac['outputs']['current_real'] - .5 / scale) < 1e-12
        checks[f'kinetics_reference_{scale}'] = abs(kinetics['outputs']['final'][0] - scale * (.5 + .5 * math.exp(-2))) < 1e-7
        checks[f'layers_reference_{scale}'] = layers['outputs']['interface_pressures'] == ['0', str(20000 * scale), str(80000 * scale)]
        models.extend((elastic, ac, kinetics, layers))
    checks['sixteen_domain_results_replayed'] = all(replay_domain(model) for model in models)
    checks['wrong_physical_units_rejected'] = False
    try:
        series_rlc(Quantity(10, METER), Quantity(1, HENRY), Quantity(1, FARAD), Quantity(5, VOLT), Quantity(1, SECOND**-1))
    except ValueError:
        checks['wrong_physical_units_rejected'] = True
    try:
        solve_diffusion([0, 1, 1, 1, 0], steps=1, duration=10, method='ftcs')
        checks['unstable_explicit_pde_rejected'] = False
    except ValueError:
        checks['unstable_explicit_pde_rejected'] = True
    save(root / 'domain-results.json', models)
    result = {'simulation': True, 'checks': checks, 'all_checks_passed': all(checks.values()),
              'experimental_physical_validation': False, 'independent_peer_review': False}
    save(root / 'assurance.json', result)
    return result['all_checks_passed']


def worker(args):
    if args.worker == 'workload':
        from nablamath.benchmarks.laboratory import run_laboratory_workload
        summary = run_laboratory_workload(args.destination / 'workload', per_family=args.per_family, seed=args.seed)
        return summary['all_negative_controls_passed'] and all(
            summary['evaluations'][split + '-exact-reference']['accuracy'] == 1.
            for split in ('validation', 'test'))
    if args.worker == 'independent':
        from nablamath.benchmarks.independent import run_benchmark
        from nablamath.benchmarks.analysis import analyze_benchmark
        report = run_benchmark(count=32, seed=args.seed + 17031, sizes=(2, 4, 8), timeout=15)
        save(args.destination / 'independent.json', report)
        save(args.destination / 'independent-analysis.json', analyze_benchmark(report))
        return all(report['summary']['nabla'][status] == 0 for status in ('incorrect', 'error', 'timeout'))
    return assurance(args.destination)


def phase_profiles(root):
    def read(name):
        path = root / name
        return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    from nablamath.stability import public_contract
    expected_catalog = public_contract()['catalog']
    catalog_matches = read('science/calculator-catalog.json') == expected_catalog
    science = read('science/summary.json')
    workload = read('workload/summary.json')
    benchmark = read('independent.json')
    portfolio = read('portfolio/summary.json')
    checks = read('assurance.json').get('checks', {})
    profiles = [
        ('F1', catalog_matches and science.get('calculator_operations') == len(expected_catalog['operations'])
         and science.get('nist_reference_passed') is True,
         'science/calculator-catalog.json: frozen catalog; science/summary.json: replay and NIST reference'),
        ('F2', len(benchmark.get('tasks', [])) == 32 and benchmark.get('summary', {}).get('nabla', {}).get('solved') == 32,
         'independent.json: exact answers on 32 constructor tasks'),
        ('F3', checks.get('formal_backend_replayed') is True,
         'assurance.json: pinned Lean certificate replay, human translation review pending'),
        ('F4', science.get('visual_scenes') == 6,
         'science/summary.json: six model-linked SVG/PNG scenes'),
        ('F5', len(science.get('compiled_publication_profiles', [])) == 3 and all(
            checks.get(name + '_publication_replayed') is True for name in ('research_paper', 'engineering_report', 'teaching')),
         'assurance.json: three compiled publication profiles replayed'),
        ('F6', workload.get('all_negative_controls_passed') is True and checks.get('mixed_scientific_dataset_replayed') is True,
         'workload/summary.json and assurance.json: split isolation, release, adversarial controls'),
        ('F7', science.get('diffusion_reference_max_error', math.inf) < 1e-4 and checks.get('unstable_explicit_pde_rejected') is True,
         'science/summary.json and assurance.json: analytical reference and instability rejection'),
        ('F8', science.get('durable_agent_resume') is True and science.get('multimodal_checkpoint_predictions_verified') is True
         and len(workload.get('evaluations', {})) == 6,
         'science and workload summaries: agents, checkpoint replay and six evaluations, including failures to generalize'),
        ('F9', science.get('rational_basis_holdout_matched') is True,
         'science/basis-discovery.json: recovery of a known synthetic law on reserved points'),
        ('F10', len(portfolio.get('runs', [])) == 2,
         'portfolio/summary.json: two declared baseline comparisons; no general RSI'),
        ('F11', checks.get('sixteen_domain_results_replayed') is True and checks.get('wrong_physical_units_rejected') is True,
         'domain-results.json and assurance.json: 16 ideal-model cases with analytical references'),
        ('F12', checks.get('forged_signature_quarantined') is True and checks.get('revoked_persisted_snapshot_not_exported') is True,
         'assurance.json: signed snapshot corruption, revocation and quarantine'),
    ]
    return {phase: {'selected_profile_passed': bool(passed), 'evidence': evidence,
                    'whole_phase_completion_established': False}
            for phase, passed, evidence in profiles}


def run(args):
    root = args.destination.resolve()
    root.mkdir(parents=True, exist_ok=False)
    # Local role labels describe workflow responsibilities, not real researchers.
    source_files = list((ROOT / 'src/nablamath').rglob('*.py')) + list((ROOT / 'tools').glob('*.py'))
    versions = {}
    for name in ('numpy', 'sympy', 'z3-solver', 'cryptography', 'pyarrow', 'typst'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    protocol = {'schema_version': 1, 'simulation': True, 'target_vision_percent': 95,
                'per_family': args.per_family, 'seed': args.seed, 'job_timeout_seconds': args.timeout,
                'source_sha256': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(source_files)},
                'python_version': platform.python_version(), 'dependency_versions': versions,
                'roles': ['data curator', 'model evaluator', 'scientific computing', 'release reviewer'],
                'roles_are_independent_real_people': False,
                'stopping_rule': 'one fixed run per job; retain every outcome; no retry selected by score',
                'external_actions': 'none; local artifacts only'}
    save(root / 'protocol.json', protocol)
    common = [sys.executable, str(Path(__file__).resolve()), str(root), '--per-family', str(args.per_family), '--seed', str(args.seed)]
    jobs = [
        ('workload', common + ['--worker', 'workload']),
        ('science', [sys.executable, str(ROOT / 'tools/reproduce_maturity.py'), str(root / 'science'),
                     '--learning-directory', str(ROOT / 'benchmarks/results/maturity-expansion/multimodal')]),
        ('independent', common + ['--worker', 'independent']),
        ('portfolio', [sys.executable, str(ROOT / 'tools/reproduce_portfolio.py'), str(root / 'portfolio')]),
        ('assurance', common + ['--worker', 'assurance']),
    ]
    records = []
    for name, command in jobs:
        row = {'job': name, 'status': 'running', 'command': command}
        records.append(row)
        save(root / 'journal.json', records)
        print('Running ' + name, flush=True)
        start = time.monotonic()
        try:
            with (root / (name + '.log')).open('wb') as log:
                outcome = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                         timeout=args.timeout, env={**os.environ, 'OPENBLAS_NUM_THREADS': '1'}, check=False)
            row.update(status='passed' if outcome.returncode == 0 else 'failed', returncode=outcome.returncode)
        except subprocess.TimeoutExpired:
            row.update(status='timeout', returncode=None)
        row['elapsed_seconds'] = time.monotonic() - start
        save(root / 'journal.json', records)
        print(name + ': ' + row['status'], flush=True)
    profiles = phase_profiles(root)
    result = {'schema_version': 1, 'simulation': True, 'jobs': records,
              'all_jobs_passed': all(row['status'] == 'passed' for row in records),
              'phase_profiles': profiles,
              'selected_phase_profiles_passed': sum(row['selected_profile_passed'] for row in profiles.values()),
              'vision_target_percent': 95, 'vision_target_demonstrated': False,
              'vision_completion_percent': None,
              'reason': 'Simulated usage tests finite engineering profiles; it cannot establish external frontier-lab adoption or scientific completion.'}
    save(root / 'summary.json', result)
    save(root / 'manifest.json', {'schema_version': 1, 'files': {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob('*')) if p.is_file()}})
    return result['all_jobs_passed'] and result['selected_phase_profiles_passed'] == 12


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--per-family', type=int, default=24, choices=range(1, 65))
    parser.add_argument('--seed', type=int, default=951017)
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--worker', choices=('workload', 'independent', 'assurance'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 0 <= args.seed <= 2**31 - 1 or not 10 <= args.timeout <= 3600:
        parser.error('Bounded nonnegative seed and timeout 10–3600 seconds required')
    raise SystemExit(0 if (worker(args) if args.worker else run(args)) else 1)
