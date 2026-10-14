"""Public orchestration for Studio, datasets, Worlds and held-out learning reports."""
from pathlib import Path
import json
from .core.semantic_ir import canonical_json


def build_dataset(destination, *, count=32, seed=42, license_id, provenance, parquet=False):
    from .forge.sampling import sampling_plan
    from .forge.task_spec import FAMILIES
    from .forge.reverse_builder import generate_task
    from .forge.solvers import solve_task
    from .datasets.schema import make_record
    from .datasets.curation import curate
    from .export.bundle import export_bundle
    candidates = []
    for family, derived, size in sampling_plan(count, seed, FAMILIES, (2,3)):
        generated = generate_task(family, derived, size)
        candidates.append(make_record(generated.task, solve_task(generated.task),
            license_id=license_id, provenance=provenance+f'; inverse-v2 seed={derived}',
            scope='Eight bounded rational task families',
            limitations='Synthetic exact tasks; no demonstrated general training utility',
            attempts=(generated.witness,)))
    records, report = curate(candidates)
    if not report['accepted']:
        raise ValueError(str(report))
    export_bundle(records, destination, parquet=parquet)
    return report


def evaluate_dataset(directory, *, benchmark_name, ablations=True):
    from .export.bundle import verify_bundle
    from .export.jsonl import read_jsonl
    from .datasets.multimodal import build_sample
    from .training.curriculum import curriculum
    from .training.baselines import fit_nearest_neighbor
    from .training.evaluation import evaluate
    from .training.ablation import run_ablations
    directory = Path(directory)
    if not verify_bundle(directory):
        raise ValueError('Dataset inválido')
    records = read_jsonl(directory/'records.jsonl')
    samples = tuple(build_sample(r, include_simulation=r.task.family=='polynomial_integral') for r in records)
    training = curriculum(s for s in samples if s.record.to_data()['split']=='train')
    test = tuple(s for s in samples if s.record.to_data()['split']=='test')
    if not training or not test:
        raise ValueError('Benchmark requer treino e teste não vazios')
    model = fit_nearest_neighbor(training)
    report = {'model': model.to_data(), 'evaluation': evaluate(model, test, training_samples=training, benchmark_name=benchmark_name)}
    if ablations:
        report['ablations'] = run_ablations(training, test, benchmark_name=benchmark_name)
    return report


def write_json(destination, data):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x', encoding='utf-8') as output:
        output.write(canonical_json(data)+'\n')
    return destination


def run_laboratory(destination, *, seed=42, count=32, parquet=False):
    """Produce inspectable artifacts for all four phases, without remote publication."""
    import hashlib
    import shutil
    import tempfile
    from .documents.publication import research_document, publish
    from .documents.figures import ingest_figure
    from .worlds.model_spec import HeatModelSpec
    from .worlds.pde import solve_heat
    from .worlds.convergence import heat_convergence
    from .worlds.conservation import check_conservation
    from .worlds.animation import export_animation
    from .agents import Planner, ScientificProposal as Proposal, Action, Permissions, scientific_registry
    from .forge.reverse_builder import generate_task
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.laboratory-', dir=destination.parent))
    try:
        quality = build_dataset(stage/'dataset', seed=seed, count=count, license_id='CC0-1.0',
                                provenance='Nabla reproducible synthetic laboratory', parquet=parquet)
        learning = evaluate_dataset(stage/'dataset', benchmark_name=f'generated-family-holdout-seed-{seed}')
        write_json(stage/'learning.json', learning)
        model = HeatModelSpec()
        simulation = solve_heat(model, cells=20, steps=200, snapshot_stride=2)
        convergence = heat_convergence(model)
        conservation = check_conservation(simulation)
        write_json(stage/'simulation.json', simulation)
        write_json(stage/'convergence.json', convergence)
        write_json(stage/'conservation.json', conservation)
        export_animation(simulation, stage/'heat.svg')
        generated = generate_task('linear_system', seed, 2)
        plan = Proposal('Solve an exact linear system',
                        (Action('exact', 'solve', canonical_json({'task': generated.task.to_data()})),),
                        'Registered exact solver; no autonomous research or experimental validation.')
        agent = Planner(scientific_registry(), Permissions(frozenset({'solve'}))).run(plan)
        if not agent['completed']:
            raise RuntimeError('Plano científico falhou: '+str(agent))
        write_json(stage/'agent.json', agent)
        figures = ()
        try:
            from PIL import Image, ImageDraw, ImageFont, PngImagePlugin
        except ImportError:
            pass
        else:
            image = Image.new('RGB', (1600,800), 'white')
            draw = ImageDraw.Draw(image)
            try:
                font = ImageFont.truetype('DejaVuSans.ttf', 24)
            except OSError:
                font = ImageFont.load_default(size=24)
            draw.text((80,20), 'Heat equation: final temperature perturbation', fill='black', font=font)
            for values, color in [(simulation['reference'],'gray'), (simulation['final'],'blue')]:
                points = [(120+1380*x/model.length,640-500*v) for x,v in zip(simulation['positions'],values)]
                draw.line(points, fill=color, width=5)
            draw.line([(120,100),(120,640),(1500,640)], fill='black', width=2)
            for value in (0,.5,1):
                x,y = 120+1380*value,640-500*value
                draw.line([(x,640),(x,650)],fill='black',width=2)
                draw.text((x-15,660),str(value),fill='black',font=font)
                draw.line([(110,y),(120,y)],fill='black',width=2)
                draw.text((45,y-12),str(value),fill='black',font=font)
            draw.text((10,75),'K',fill='black',font=font)
            draw.text((1450,700),'x (m)',fill='black',font=font)
            draw.text((80,750), 'Blue: FTCS | Gray: analytic | Synthetic; no experimental validation', fill='black',font=font)
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text('model_id', model.content_id)
            image.save(stage/'heat.png', pnginfo=metadata)
            figures = (ingest_figure(stage/'heat.png', stage/'assets', 'FTCS and independent analytic solution, SI units'),)
        evidence_sources = {hashlib.sha256((stage/name).read_bytes()).hexdigest(): stage/name
                            for name in ('convergence.json','learning.json','simulation.json')}
        doc = research_document('Nabla: reproducible scientific laboratory',
                hypothesis='Stable FTCS converges to the analytic sine-mode solution of the ideal heat equation.',
                method='Zero Dirichlet boundaries; dx refined by 2 and dt by 4; independent exact grading on family-held-out tasks.',
                results=(f'Observed convergence order: {convergence["observed_order"]:.4f}. '
                         f'Coarse maximum error: {convergence["coarse_error"]:.6g} K; '
                         f'refined maximum error: {convergence["fine_error"]:.6g} K. '
                         f'Tolerance: {convergence["tolerance"]:.6g} K. '
                         f'Learning exact accuracy: {learning["evaluation"]["accuracy"]:.1%} '
                         f'({learning["evaluation"]["successes"]}/{learning["evaluation"]["total"]} held-out tasks).'),
                discussion='A numerical reference comparison is distinct from experimental evidence. Learning scores are reported even when zero.',
                limitations='Synthetic bounded problems. No external corpus, instrument authentication or general scientific capability demonstrated.',
                evidence_ids=tuple(evidence_sources), figures=figures)
        publish(doc, stage/'article', asset_root=stage/'assets', pdf_backend='typst',
                evidence_sources=evidence_sources, require_evidence=True)
        summary = {'seed':seed, 'dataset_quality': quality, 'learning_evaluation_id': learning['evaluation']['evaluation_id'],
                   'document_id': doc.content_id, 'model_id': model.content_id, 'agent_completed':agent['completed'],
                   'external_evaluation_performed':False, 'remote_publication_performed':False}
        write_json(stage/'summary.json', summary)
        write_json(stage/'manifest.json', {'schema_version':1, 'files': {
            p.relative_to(stage).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(stage.rglob('*')) if p.is_file()}})
        stage.rename(destination)
        return summary
    finally:
        if stage.exists():
            shutil.rmtree(stage)
