"""One reproducible local cycle: inverse construction -> independent solve -> checked artifacts."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import shutil
import tempfile

from ..core.semantic_ir import PolynomialSpec, ScientificTask, canonical_json
from ..expression import Binary, Number, Symbol
from ..documents.document_model import Equation, Figure
from ..dataset.scientific import audit_contamination, make_record, validate_record
from ..dataset.alignments import validate_alignment
from ..documents import Document, Section, to_html, to_latex, to_typst
from ..graphics import task_scene, render_svg
from ..graphics.raster_renderer import render_png
from ..verify import solve, verify
from .reverse_builder import generate


def run_cycle(destination: Path, *, count: int, seed: int, license_id: str,
              provenance: str, size: int = 3, pdf_backend: str | None = None) -> dict:
    if type(count) is not int or not 1 <= count <= 1000:
        raise ValueError('Quantidade deve estar entre 1 e 1000')
    if type(seed) is not int or not 0 <= seed <= 2**63 - 1 - count:
        raise ValueError('Semente fora do limite')
    if not license_id.strip() or not provenance.strip():
        raise ValueError('Licenca e procedencia obrigatorias')
    destination = Path(destination).absolute()
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.nabla-cycle-', dir=destination.parent))
    try:
        records = []
        seen = set()
        partitions = {name: [] for name in ('train', 'validation', 'test')}
        sections = []
        (stage / 'figures').mkdir()
        for i in range(count):
            family = ('polynomial_integral', 'linear_system')[i % 2]
            generated = generate(family, seed + i, size)
            task = generated.task
            solution = solve(task)
            if not verify(task, generated.witness).valid or not verify(task, solution).valid:
                raise ArithmeticError('Construtor e solver divergem na verificacao independente')
            if task.content_id in seen:
                continue
            seen.add(task.content_id)
            record = make_record(task, solution, license_id=license_id, provenance=provenance, seed=seed+i)
            records.append(record)
            partitions[record['split']].append(record)
            scene = task_scene(task, solution)
            prefix = stage / 'figures' / task.content_id
            prefix.with_suffix('.svg').write_text(render_svg(scene), encoding='utf-8')
            prefix.with_suffix('.png').write_bytes(render_png(scene))
            prefix.with_suffix('.json').write_text(canonical_json(scene.to_data()) + '\n', encoding='utf-8')
            if family == 'polynomial_integral':
                equations = (Equation(Symbol('integrand'), PolynomialSpec(task.coefficients).to_expr()),
                             Equation(Symbol('primitive'), PolynomialSpec(solution).to_expr()))
                explanation = 'Primitiva escolhida com constante zero. Outras primitivas diferem por constante.'
            else:
                equations_list = []
                for row, target in zip(task.matrix, task.rhs):
                    lhs = Number(0)
                    for j, coefficient in enumerate(row):
                        lhs = Binary('+', lhs, Binary('*', Number(coefficient), Symbol(f'x{j+1}')))
                    equations_list.append(Equation(lhs, Number(target)))
                equations = tuple(equations_list)
                explanation = 'Solucao unica: ' + ', '.join(f'x{j+1}={v}' for j, v in enumerate(solution))
            sections.append(Section(family, explanation + ' Verificacao: ' + record['verification']['method'] + '.',
                (task.content_id,), equations,
                (Figure(f'figures/{task.content_id}.png', scene.label),)))
        audit = audit_contamination(partitions)
        document = Document('Nabla: ciclo cientifico sintetico', tuple(sections))
        for suffix, exporter in [('html', to_html), ('tex', to_latex), ('typ', to_typst)]:
            (stage / f'report.{suffix}').write_text(exporter(document), encoding='utf-8')
        if pdf_backend is not None:
            from ..documents.pdf_builder import build_pdf
            build_pdf(document, stage / 'report.pdf', pdf_backend, asset_root=stage)
        (stage / 'records.jsonl').write_text(''.join(canonical_json(r) + '\n' for r in records), encoding='utf-8')
        for split, subset in partitions.items():
            (stage / f'{split}.jsonl').write_text(''.join(canonical_json(r) + '\n' for r in subset), encoding='utf-8')
        summary = {'schema_version': 1, 'attempted': count, 'accepted': len(records),
                   'duplicates': count-len(records), 'seed': seed, 'size': size,
                   'license_id': license_id, 'provenance': provenance,
                   'families': dict(Counter(r['task']['family'] for r in records)),
                   'splits': {k: len(v) for k, v in partitions.items()}, 'contamination': audit,
                   'difficulty': 'uncalibrated', 'formal_proofs': 0,
                   'limitations': 'Duas familias sinteticas; sem avaliacao externa, utilidade de treino ou maturidade de fase demonstradas.'}
        (stage / 'card.json').write_text(canonical_json(summary) + '\n', encoding='utf-8')
        manifest = {'schema_version': 1, 'files': {p.relative_to(stage).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(stage.rglob('*')) if p.is_file()}}
        (stage / 'manifest.json').write_text(canonical_json(manifest) + '\n', encoding='utf-8')
        if not verify_bundle(stage):
            raise ArithmeticError('Bundle falhou na revalidacao')
        if destination.exists():
            raise FileExistsError(destination)
        stage.rename(destination)
        return summary
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def verify_bundle(directory: Path) -> bool:
    """Hashes detect corruption; independent reexecution checks the scientific records."""
    try:
        root = Path(directory)
        manifest_path = root / 'manifest.json'
        if manifest_path.is_symlink() or manifest_path.stat().st_size > 1024*1024:
            return False
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest['schema_version'] != 1 or not isinstance(manifest['files'], dict):
            return False
        actual_files = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != manifest_path}
        if set(manifest['files']) != actual_files:
            return False
        for name, digest in manifest['files'].items():
            path = root / name
            if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()) or path.stat().st_size > 64*1024*1024:
                return False
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                return False
        records = [json.loads(line) for line in (root / 'records.jsonl').read_text(encoding='utf-8').splitlines()]
        if not records or len(records) > 1000 or not all(validate_record(r) for r in records):
            return False
        if len({r['task_id'] for r in records}) != len(records):
            return False
        if not all(validate_alignment(record, root) for record in records):
            return False
        partitions = {name: [json.loads(line) for line in (root / f'{name}.jsonl').read_text(encoding='utf-8').splitlines()]
                      for name in ('train', 'validation', 'test')}
        if not audit_contamination(partitions)['clean']:
            return False
        card = json.loads((root / 'card.json').read_text(encoding='utf-8'))
        attempted, seed, size = card['attempted'], card['seed'], card['size']
        if type(attempted) is not int or not 1 <= attempted <= 1000:
            return False
        if type(seed) is not int or not 0 <= seed <= 2**63 - 1 - attempted:
            return False
        expected_tasks, seen = [], set()
        for i in range(attempted):
            family = ('polynomial_integral', 'linear_system')[i % 2]
            generated = generate(family, seed + i, size)
            if generated.task.content_id not in seen:
                expected_tasks.append((generated.task.content_id, seed+i))
                seen.add(generated.task.content_id)
        if [(r['task_id'], r['generator']['seed']) for r in records] != expected_tasks:
            return False
        if (card['schema_version'] != 1 or card['accepted'] != len(records)
                or card['duplicates'] != attempted-len(records) or card['formal_proofs'] != 0
                or card['difficulty'] != 'uncalibrated'
                or card['families'] != dict(Counter(r['task']['family'] for r in records))
                or card['splits'] != {k: len(v) for k, v in partitions.items()}
                or card['contamination'] != audit_contamination(partitions)
                or any(r['license_id'] != card['license_id'] or r['provenance'] != card['provenance'] for r in records)):
            return False
        expected = {name: [r for r in records if r['split'] == name] for name in partitions}
        return partitions == expected
    except (OSError, KeyError, ValueError, TypeError, ArithmeticError):
        return False
