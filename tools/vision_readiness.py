"""Run the vision acceptance dashboard: all 213 gaps, current tests and benchmarks.

Engineering success is distinct from full scientific acceptance. This runner
never authenticates a reviewer or invents a percentage of universal readiness.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MATRIX = 'docs/acceptance/evidence_matrix.json'
VERSION = 'vision-readiness-v1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_identity(root):
    """Fingerprint working bytes, including new nonignored files, not just HEAD."""
    names = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=root
    ).decode().split('\0')
    chain = hashlib.sha256()
    count = 0
    for name in sorted(set(names)-{''}):
        path = root/name
        if path.is_symlink():
            value = 'symlink:'+os.readlink(path)
        elif path.is_file():
            value = digest(path)
        else:
            value = 'missing'
        chain.update(json.dumps([name, value], ensure_ascii=True).encode()+b'\n')
        count += 1
    return {'sha256': chain.hexdigest(), 'files': count,
            'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip()}


def run_step(name, arguments, output, *, root=ROOT, timeout=900):
    """Retain failures and timeout output; terminate children as well as parent."""
    log = output/(name+'.log')
    started = time.monotonic()
    result = {'name': name, 'command': arguments, 'log': log.name}
    with log.open('wb') as stream:
        try:
            process = subprocess.Popen(arguments, cwd=root, stdout=stream,
                stderr=subprocess.STDOUT, start_new_session=(os.name == 'posix'))
            try:
                code = process.wait(timeout=timeout)
                status = 'passed' if code == 0 else 'failed'
            except subprocess.TimeoutExpired:
                if os.name == 'posix':
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.wait()
                code, status = None, 'timeout'
        except OSError as exc:
            stream.write(str(exc).encode())
            code, status = None, 'unavailable'
    result.update(exit_code=code, status=status, seconds=round(time.monotonic()-started, 3),
                  log_sha256=digest(log))
    return result


def read_junit(path):
    """Keep skipped tests, collection errors and empty runs distinguishable."""
    if not path.is_file():
        return {'available': False, 'counts': {}, 'cases': [], 'errors': ['JUnit missing']}
    try:
        tree = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        return {'available': False, 'counts': {}, 'cases': [], 'errors': [str(exc)]}
    cases, errors = [], []
    for case in tree.iter('testcase'):
        status, reason = 'passed', ''
        for tag, state in [('failure', 'failed'), ('error', 'error'), ('skipped', 'skipped')]:
            child = case.find(tag)
            if child is not None:
                status = state
                reason = child.get('message', '') or (child.text or '')[:2000]
                break
        cases.append({'classname': case.get('classname', ''), 'name': case.get('name', ''),
                      'status': status, 'reason': reason})
    # Some JUnit producers report errors only on the suite rather than testcase.
    for suite in tree.iter('testsuite'):
        declared = int(suite.get('errors', '0'))
        if declared and not any(c['status'] == 'error' for c in cases):
            errors.append('Suite reported errors: '+str(declared))
    if not cases:
        errors.append('No tests executed')
    return {'available': True, 'sha256': digest(path),
            'counts': dict(Counter(c['status'] for c in cases)), 'cases': cases, 'errors': errors}


def matched_cases(reference, cases):
    """Match pytest module identities, including classes and parametrization."""
    file, *selectors = reference.split('::')
    module = file.removesuffix('.py').replace('/', '.')
    return [case for case in cases
            if (case['classname'] == module or case['classname'].startswith(module+'.'))
            and all(part in case['classname'].split('.') or case['name'] == part
                    or case['name'].startswith(part+'[') for part in selectors)]


def requirement_report(matrix, junit):
    rows = []
    for row in matrix['requirements']:
        references = []
        for name in row['tests']:
            selected = matched_cases(name, junit['cases'])
            references.append({'reference': name, 'counts': dict(Counter(c['status'] for c in selected)),
                               'observed_this_run': bool(selected)})
        gaps = []
        if row['status'] != 'validated':
            gaps.append('Original acceptance not closed: '+row['status'])
        if not row.get('reviewer'):
            gaps.append('Independent reviewer not recorded')
        if not row.get('release'):
            gaps.append('Accepted release not recorded')
        if not row['evidence']:
            gaps.append('Evidence references missing')
        if not references or any(not r['observed_this_run'] for r in references):
            gaps.append('Some referenced tests were not observed in this run')
        counts = Counter()
        for ref in references:
            counts.update(ref['counts'])
        if counts['failed'] or counts['error']:
            gaps.append('Referenced tests failed or errored')
        if counts['skipped']:
            gaps.append('Referenced tests skipped; prerequisites or evidence remain missing')
        # Text comes verbatim from acceptance matrix, never guessed from filenames.
        rows.append({'id': row['id'], 'target': row['target'],
            'priority': 'P0' if '**P0' in row['requirement'] else 'other',
            'acceptance': row['requirement'], 'declared_status': row['status'],
            'remaining': row['remaining'], 'implementation': row['implementation'],
            'tests': references, 'evidence': row['evidence'], 'reviewer': row.get('reviewer'),
            'release': row.get('release'), 'gaps': gaps,
            'independent_evidence_authenticated': False})
    return rows


def benchmark_results(output):
    """Expose measured outcomes, including zero scores, without selecting winners."""
    results = {}
    for name, relative in [('longley', 'longley.json'),
                           ('calibration', 'calibration.json'),
                           ('laboratory', 'laboratory/summary.json'),
                           ('original_workload', 'laboratory/workload/summary.json')]:
        path = output/relative
        if not path.is_file():
            results[name] = {'available': False}
            continue
        try:
            if path.stat().st_size > 4_000_000:
                raise ValueError('Benchmark summary exceeds byte budget')
            results[name] = {'available': True, 'sha256': digest(path),
                             'result': json.loads(path.read_text(encoding='utf-8'))}
        except (OSError, ValueError) as exc:
            results[name] = {'available': False, 'error': str(exc)}
    return results


def markdown(report):
    counts = report['tests']['counts']
    lines = ['# Nabla — o que falta para concluir a visão', '',
        'Execução UTC: '+report['created_utc'], '',
        '**Prontidão científica integral não estabelecida.** Não existe percentual '
        'confiável calculado por linhas de código ou quantidade de testes.', '',
        'Testes observados: '+json.dumps(counts, ensure_ascii=False)+'.',
        'Estados declarados na matriz: '+json.dumps(report['matrix_statuses'])+'.', '',
        '## Execução atual', '', '| Etapa | Resultado | Registro |', '|---|---|---|']
    for step in report['steps']:
        lines.append(f"| {step['name']} | {step['status']} | [{step['log']}]({step['log']}) |")
    lines += ['', '## Benchmarks medidos nesta execução', '']
    for name, result in report.get('benchmarks', {}).items():
        if not result['available']:
            lines += ['- '+name+': não disponível nesta execução.']
            continue
        data = result['result']
        if name == 'original_workload':
            value = data.get('evaluations', {})
        elif name == 'calibration':
            value = {'finite_checks_passed': data.get('finite_checks_passed'),
                     'fully_calibrated_and_ready': data.get('fully_calibrated_and_ready')}
        elif name == 'longley':
            value = {key: data.get(key) for key in ('passed', 'coefficient_relative_errors', 'sse_relative_error')}
        else:
            value = {key: data.get(key) for key in ('all_jobs_passed', 'selected_phase_profiles_passed', 'vision_completion_percent')}
        lines += ['- '+name+': `'+json.dumps(value, ensure_ascii=False)+'`']
    lines += ['', 'Testes pulados não são aprovação. Referências ausentes não são '
              'testes executados. Rótulos de revisão não autenticam identidade.', '',
              '## Todos os 213 critérios e lacunas', '']
    for row in report['requirements']:
        lines += [f"### {row['id']:03d} — {row['target']}", '', row['acceptance'], '',
            '**Estado declarado:** '+row['declared_status']+'.', '',
            '**Escopo restante registrado:** '+row['remaining'], '',
            '**Pendências observadas:**', '']
        lines += ['- '+gap for gap in row['gaps']]
        if not row['gaps']:
            lines += ['- Nenhuma lacuna documental detectada; evidência independente não autenticada por este runner.']
        lines += ['', '**Testes vinculados nesta execução:**', '']
        for ref in row['tests']:
            lines.append('- `'+ref['reference']+'`: '+
                (json.dumps(ref['counts']) if ref['observed_this_run'] else 'não observado'))
        lines += ['', '**Evidências registradas:** '+(', '.join('`'+e+'`' for e in row['evidence']) or 'nenhuma'), '']
    lines += ['## Limites que não desaparecem com pytest verde', '',
        '- Generalização: comparar resultados do laboratório original, sem substituir seu 0/48 por outra campanha.',
        '- Lean/Mathlib: provas e hipóteses precisam do kernel e das dependências reais.',
        '- GPU, múltiplos hosts e plataformas: exigem execução nos ambientes correspondentes.',
        '- Simulação e descoberta: exigem dados experimentais, revisão e reprodução independentes.',
        '- F13 é horizonte de pesquisa aberto; os 213 itens não garantem inteligência geral.', '']
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Fresh directory; defaults to .nabla/vision-readiness/TIMESTAMP')
    parser.add_argument('--inventory-only', action='store_true', help='Fast gap report; explicitly does not execute tests or benchmarks')
    parser.add_argument('--require-complete', action='store_true', help='Return 2 unless full independent acceptance is established')
    args = parser.parse_args(argv)
    output = (args.output or ROOT/'.nabla/vision-readiness'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')).resolve()
    output.mkdir(parents=True, exist_ok=False)
    before = source_identity(ROOT)
    steps = []
    python = sys.executable
    # Independent checks continue after a failure so the report retains all gaps.
    commands = [
        ('roadmap', [python, 'tools/check_roadmap.py']),
        ('contracts', [python, 'tools/check_public_contracts.py']),
        ('preservation', [python, 'tools/preserve_evidence.py']),
        ('bundle', [python, 'tools/build_math_bundle.py', '--check']),
    ]
    if not args.inventory_only:
        commands += [
            ('pytest', [python, '-m', 'pytest', '-q', '--junitxml='+str(output/'pytest.xml')]),
            ('longley', [python, 'tools/validate_longley.py', '--output', str(output/'longley.json')]),
            ('laboratory', [python, 'tools/simulate_frontier_lab.py', str(output/'laboratory'), '--per-family', '24', '--seed', '951017']),
            ('calibration', [python, 'tools/calibrate_readiness.py', '--output', str(output/'calibration.json'),
                '--laboratory-directory', str(output/'laboratory'), '--cases', '10000', '--integration-cases', '512', '--seed', '951017']),
        ]
    for name, command in commands:
        print('Executando '+name+'...', flush=True)
        steps.append(run_step(name, command, output))
    junit = read_junit(output/'pytest.xml')
    matrix = json.loads((ROOT/MATRIX).read_text(encoding='utf-8'))
    # Never use an invalid/reordered matrix to make a reassuring checklist.
    sys.path.insert(0, str(ROOT/'tools'))
    from check_roadmap import validate_matrix
    validate_matrix(matrix, ROOT)
    rows = requirement_report(matrix, junit)
    after = source_identity(ROOT)
    engineering = (not args.inventory_only and all(s['status'] == 'passed' for s in steps)
                   and junit['available'] and not junit['errors']
                   and not any(junit['counts'].get(k, 0) for k in ('failed', 'error')) and before == after)
    report = {'version': VERSION, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_before': before, 'source_after': after, 'source_changed_during_run': before != after,
        'matrix_sha256': digest(ROOT/MATRIX), 'mode': 'inventory-only' if args.inventory_only else 'full',
        'steps': steps, 'tests': junit, 'benchmarks': benchmark_results(output), 'requirements': rows,
        'matrix_statuses': dict(Counter(r['declared_status'] for r in rows)),
        'engineering_checks_passed': engineering, 'full_vision_acceptance_established': False,
        'scope': 'Current local tests and all original gaps; no automatic scientific certification'}
    (output/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    (output/'REPORT.md').write_text(markdown(report), encoding='utf-8')
    print('Relatório: '+str(output/'REPORT.md'), flush=True)
    print('Aceitação integral: NÃO ESTABELECIDA. Estados: '+json.dumps(report['matrix_statuses']))
    if args.require_complete:
        return 2
    return 0 if engineering or (args.inventory_only and all(s['status']=='passed' for s in steps)) else 1


if __name__ == '__main__':
    raise SystemExit(main())
