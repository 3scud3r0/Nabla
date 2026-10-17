"""Interface de terminal local; nenhuma chamada remota nem dependência de IA."""

from __future__ import annotations

import argparse
from fractions import Fraction
import json
import sqlite3
import sys
from pathlib import Path

from .. import __version__
from ..compatibility import runtime_report
from ..curation import curate
from ..expression import DomainError, render
from ..formal import verify_with_lean
from ..orbit_svg import write_earth_orbit_svg
from ..orbits import earth_circular_orbit
from ..physics.fluids import PipeFlow
from ..report import write_report
from ..research import calculate
from ..storage import export_verified, import_snapshot, load_result, save_result, verify_record
from ..store.backup import backup_database, restore_database


def _assignment(text: str) -> tuple[str, Fraction]:
    name, separator, raw = text.partition("=")
    if not separator or not name.isidentifier() or len(raw) > 256:
        raise argparse.ArgumentTypeError("Use nome=inteiro ou nome=numerador/denominador")
    try:
        return name, Fraction(raw)
    except (ValueError, ZeroDivisionError) as exc:
        raise argparse.ArgumentTypeError("Valor racional inválido") from exc


def _bounded_json_text(path: Path) -> str:
    from ..core.semantic_contracts import MAX_BYTES
    with path.open("rb") as source:
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("JSON exceeds byte budget")
    return raw.decode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nabla", description="NablaMath: núcleo local de cálculo rastreável")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    desktop = commands.add_parser("desktop", help="Abrir painel web local com banco SQLite")
    desktop.add_argument("--data-dir", type=Path, default=Path.home() / "NablaMath")
    desktop.add_argument("--no-browser", action="store_true")
    doctor = commands.add_parser("doctor", help="Mostrar ambiente e integrações opcionais")
    doctor.add_argument("--probe", action="store_true", help="Verificar versões dos executáveis opcionais com timeout")
    capabilities = commands.add_parser("capabilities", help="Consultar domínio e recusas de um perfil científico")
    capabilities.add_argument("manifest", type=Path)
    capabilities.add_argument("--profile", required=True)
    capabilities.add_argument("--operation", required=True)
    run = commands.add_parser("run", help="Executar expressão racional com etapas")
    run.add_argument("expression", help='Exemplo: "(x+x)/x"')
    run.add_argument("--value", action="append", type=_assignment, default=[], metavar="X=3")
    run.add_argument("--db", type=Path, default=Path(".nabla/results.sqlite3"))
    run.add_argument("--tex", type=Path)
    run.add_argument("--pdf", action="store_true", help="Compilar --tex com pdflatex")
    show = commands.add_parser("show", help="Consultar registro pelo identificador")
    show.add_argument("identifier")
    show.add_argument("--db", type=Path, default=Path(".nabla/results.sqlite3"))
    verify = commands.add_parser("verify", help="Reexecutar um registro armazenado")
    verify.add_argument("identifier")
    verify.add_argument("--db", type=Path, default=Path(".nabla/results.sqlite3"))
    export = commands.add_parser("export", help="Exportar registros revalidados em JSONL")
    export.add_argument("destination", type=Path)
    export.add_argument("--db", type=Path, default=Path(".nabla/results.sqlite3"))
    import_cmd = commands.add_parser("import", help="Importar snapshot local após hash e reexecução")
    import_cmd.add_argument("source", type=Path)
    import_cmd.add_argument("--db", type=Path, default=Path(".nabla/results.sqlite3"))
    backup = commands.add_parser("backup", help="Criar backup SQLite consistente e verificável")
    backup.add_argument("destination", type=Path)
    backup.add_argument("--db", type=Path, default=Path(".nabla/results.sqlite3"))
    restore = commands.add_parser("restore", help="Restaurar backup sem sobrescrever banco existente")
    restore.add_argument("source", type=Path)
    restore.add_argument("--db", type=Path, default=Path(".nabla/results.sqlite3"))
    curated = commands.add_parser("curate", help="Criar dataset local com proveniência e divisões")
    curated.add_argument("destination", type=Path)
    curated.add_argument("--db", type=Path, default=Path(".nabla/results.sqlite3"))
    curated.add_argument("--license", required=True, help="Declaração fornecida pelo curador")
    curated.add_argument("--provenance", required=True)
    orbit = commands.add_parser("orbit", help="Órbita terrestre circular ideal em unidades SI")
    orbit.add_argument("--altitude-m", type=float, required=True)
    orbit.add_argument("--svg", type=Path, help="Gravar visualização orbital SVG em escala")
    fluid = commands.add_parser("fluid", help="Perfil analítico laminar em tubo circular (SI)")
    fluid.add_argument("--radius-m", type=float, required=True)
    fluid.add_argument("--length-m", type=float, required=True)
    fluid.add_argument("--pressure-pa", type=float, required=True)
    fluid.add_argument("--viscosity-pa-s", type=float, required=True)
    fluid.add_argument("--density-kg-m3", type=float, required=True)
    formal = commands.add_parser("formal", help="Provar no Lean uma instância racional armazenada")
    formal.add_argument("identifier")
    formal.add_argument("--db", type=Path, default=Path(".nabla/results.sqlite3"))
    formal.add_argument("--project", type=Path, default=Path("lean"),
                        help="Pasta Lake clonada; padrão: ./lean")
    forge = commands.add_parser("forge", help="Gerar ciclo cientifico sintetico verificado")
    forge.add_argument("destination", type=Path)
    forge.add_argument("--count", type=int, default=10)
    forge.add_argument("--seed", type=int, default=42)
    forge.add_argument("--size", type=int, default=3)
    forge.add_argument("--license", required=True, dest="license_id")
    forge.add_argument("--provenance", required=True)
    forge.add_argument("--pdf-backend", choices=("latex", "typst"))
    forge.add_argument("--families", nargs="+", choices=("polynomial_integral","factored_polynomial","linear_system",
                       "prescribed_spectrum","convex_quadratic","stationary_markov","polynomial_identity","counterexample"))
    forge.add_argument("--all-families", action="store_true")
    forge.add_argument("--sizes", type=int, nargs="+")
    forge.add_argument("--calibrate", action="store_true")
    forge.add_argument("--solver-budget", type=int, default=1000000)
    commands.add_parser("catalog", help="Listar operações científicas e contratos em JSON")
    calculator = commands.add_parser("calc", help="Operacao cientifica com parametros JSON e notebook opcional")
    calculator.add_argument("operation")
    calculator.add_argument("--arguments", default="{}", help="Objeto JSON de argumentos")
    calculator.add_argument("--notebook", type=Path)
    replay = commands.add_parser("replay-notebook", help="Reexecutar todas as celulas de notebook")
    replay.add_argument("path", type=Path)
    check_bundle = commands.add_parser("check-bundle", help="Revalidar hashes e matematica de ciclo Forge")
    check_bundle.add_argument("directory", type=Path)
    artifact = commands.add_parser("artifact", help="Gerar artefato integrado racional com replay")
    artifact.add_argument("destination", type=Path)
    artifact.add_argument("--family", choices=("linear_system", "polynomial_integral"), default="linear_system")
    artifact.add_argument("--seed", type=int, default=42)
    artifact.add_argument("--size", type=int, default=3)
    artifact.add_argument("--license", required=True, dest="license_id")
    artifact.add_argument("--provenance", required=True)
    check_artifact = commands.add_parser("check-artifact", help="Reexecutar cada vínculo de artefato integrado")
    check_artifact.add_argument("path", type=Path)
    freeze_eval = commands.add_parser("freeze-evaluation", help="Fixar protocolo, tarefas e baseline declarativos")
    freeze_eval.add_argument("source", type=Path)
    freeze_eval.add_argument("destination", type=Path)
    evaluate_frozen = commands.add_parser("evaluate-frozen", help="Pontuar respostas contra protocolo previamente fixado")
    evaluate_frozen.add_argument("protocol", type=Path)
    evaluate_frozen.add_argument("submission", type=Path)
    evaluate_frozen.add_argument("--expected-id", required=True)
    evaluate_frozen.add_argument("--output", required=True, type=Path)
    check_eval = commands.add_parser("check-evaluation", help="Reexecutar relatório de avaliação congelada")
    check_eval.add_argument("protocol", type=Path)
    check_eval.add_argument("submission", type=Path)
    check_eval.add_argument("report", type=Path)
    check_eval.add_argument("--expected-id", required=True)
    falsify = commands.add_parser("falsify", help="Buscar contraexemplo em dominio inteiro finito")
    falsify.add_argument("left")
    falsify.add_argument("right")
    falsify.add_argument("--radius", type=int, default=3)
    falsify.add_argument("--budget", type=int, default=1000)
    simulation = commands.add_parser("simulate", help="Estudo de convergencia de EDO com referencia analitica")
    simulation.add_argument("model", choices=("exponential_decay", "harmonic_oscillator"))
    simulation.add_argument("--initial", type=float, nargs="+", required=True)
    simulation.add_argument("--rate", type=float, default=1.0)
    simulation.add_argument("--duration", type=float, default=1.0)
    simulation.add_argument("--steps", type=int, default=20)
    simulation.add_argument("--method", choices=("euler", "rk4"), default="rk4")
    simulation.add_argument("--tolerance", type=float, default=1e-5)
    prove = commands.add_parser("prove", help="Provar/refutar proposicao racional em Lean ou SMT")
    prove.add_argument("left")
    prove.add_argument("right")
    prove.add_argument("--relation", choices=("eq","ne","le","lt","ge","gt"), default="eq")
    prove.add_argument("--assumption", action="append", default=[], help="Ex.: x >= 0")
    prove.add_argument("--backend", choices=("lean","lean-std","smt"), default="lean")
    prove.add_argument("--strategy", choices=("auto","ring","field","linarith","nlinarith","norm_num"), default="auto")
    prove.add_argument("--project", type=Path, default=Path("lean"))
    prove.add_argument("--timeout", type=int, default=30)
    prove.add_argument("--output", type=Path)
    formal_check = commands.add_parser("check-formal", help="Reexecutar certificado formal salvo")
    formal_check.add_argument("path", type=Path)
    formal_check.add_argument("--project", type=Path, default=Path("lean"))
    shrink = commands.add_parser("shrink", help="Reduzir contraexemplo inteiro preservando o tipo de falha")
    shrink.add_argument("left");shrink.add_argument("right")
    shrink.add_argument("--assignment", required=True, help="Objeto JSON com o testemunho")
    shrink.add_argument("--budget", type=int, default=10000)
    shrink.add_argument("--output", type=Path)
    falsify.add_argument("--shrink", action="store_true")
    falsify.add_argument("--output", type=Path)
    diagram = commands.add_parser("diagram", help="Gerar cena cientifica editavel, SVG e PNG verificados")
    diagram.add_argument("destination", type=Path)
    diagram.add_argument("--kind", choices=("right_triangle","parallelogram","circumcircle","function","vector_field","phase_portrait"),default="right_triangle")
    diagram.add_argument("--seed", type=int, default=42)
    diagram.add_argument("--size", type=int, default=3)
    diagram.add_argument("--function", default="x*x")
    diagram.add_argument("--dx", default="y");diagram.add_argument("--dy", default="-x")
    diagram.add_argument("--steps", type=int, default=300)
    diagram.add_argument("--duration", default="6")
    diagram.add_argument("--initials", default="[[1,0],[0,1]]")
    diagram.add_argument("--width", type=int, default=800);diagram.add_argument("--height",type=int,default=600)
    check_diagram = commands.add_parser("check-diagram", help="Reconstruir e revalidar bundle de cena")
    check_diagram.add_argument("directory", type=Path)
    studio = commands.add_parser('studio', help='Publicar AST de documento em HTML, LaTeX, Typst e PDF')
    studio.add_argument('source', type=Path); studio.add_argument('destination', type=Path)
    studio.add_argument('--assets', type=Path)
    studio.add_argument('--evidence', type=Path, help='Mapa JSON SHA-256 -> arquivo, relativo ao mapa')
    studio.add_argument('--require-evidence', action='store_true')
    studio.add_argument('--pdf-backend', choices=('latex','typst'))
    dataset_build = commands.add_parser('dataset-build', help='Curar e exportar dataset v3 com partições reservadas')
    dataset_build.add_argument('destination', type=Path)
    dataset_build.add_argument('--count', type=int, default=32); dataset_build.add_argument('--seed', type=int, default=42)
    dataset_build.add_argument('--license', required=True); dataset_build.add_argument('--provenance', required=True)
    dataset_build.add_argument('--parquet', action='store_true')
    dataset_check = commands.add_parser('dataset-check', help='Reexecutar verificações e auditar um bundle v3')
    dataset_check.add_argument('directory', type=Path)
    heat = commands.add_parser('world-heat', help='EDP do calor 1D, solução analítica e estabilidade FTCS')
    heat.add_argument('destination', type=Path)
    heat.add_argument('--cells', type=int, default=20); heat.add_argument('--steps', type=int, default=200)
    heat.add_argument('--diffusivity', type=float, default=.1); heat.add_argument('--duration', type=float, default=.1)
    agent = commands.add_parser('agent', help='Executar proposta com ferramentas registradas e limites explícitos')
    agent.add_argument('source', type=Path); agent.add_argument('destination', type=Path)
    agent.add_argument('--allow', action='append', required=True, choices=('solve','simulate','verify'))
    agent.add_argument('--max-calls', type=int, default=8); agent.add_argument('--timeout', type=float, default=10.)
    learning = commands.add_parser('evaluate-dataset', help='Treinar baseline e medir correção/ablações em holdout')
    learning.add_argument('directory', type=Path); learning.add_argument('destination', type=Path)
    learning.add_argument('--benchmark', required=True)
    laboratory = commands.add_parser('laboratory', help='Executar ciclo integrado das fases 5–8 sem publicação remota')
    laboratory.add_argument('destination', type=Path)
    laboratory.add_argument('--count', type=int, default=32); laboratory.add_argument('--seed', type=int, default=42)
    laboratory.add_argument('--parquet', action='store_true')
    discovery = commands.add_parser('discover', help='Investigar hipótese polinomial com holdout e corpus identificado')
    discovery.add_argument('destination', type=Path)
    evolution = commands.add_parser('evolve', help='Demonstrar políticas declarativas, holdouts únicos e rollback')
    evolution.add_argument('destination', type=Path); evolution.add_argument('--generations', type=int, default=2)
    domains = commands.add_parser('domain-suite', help='Executar modelos SI delimitados de várias disciplinas')
    domains.add_argument('destination', type=Path)
    knowledge = commands.add_parser('knowledge-audit', help='Conferir referências e reexecutar evidências de um snapshot')
    knowledge.add_argument('source', type=Path); knowledge.add_argument('--allow-unsigned', action='store_true')
    research = commands.add_parser('research-laboratory', help='Ciclo integrado das fases 9–12')
    research.add_argument('destination', type=Path)
    independent = commands.add_parser('independent-benchmark', help='Medir Nabla, SymPy e Z3 sob orçamento isolado')
    independent.add_argument('destination', type=Path)
    independent.add_argument('--count', type=int, default=24); independent.add_argument('--seed', type=int, default=103)
    independent.add_argument('--timeout', type=float, default=15.)
    learning = commands.add_parser('learning-experiment', help='Comparar modelo neural aberto com/sem dados Nabla em holdout externo')
    learning.add_argument('dataset', type=Path); learning.add_argument('destination', type=Path)
    learning.add_argument('--train-count', type=int, default=256); learning.add_argument('--test-count', type=int, default=128)
    learning.add_argument('--steps', type=int, default=500)
    living = commands.add_parser("living-paper", help="Compilar ou inspecionar uma publicação auditável")
    living_commands = living.add_subparsers(dest="living_command", required=True)
    living_build = living_commands.add_parser("build")
    living_build.add_argument("template", type=Path)
    living_build.add_argument("--artifact", type=Path, required=True)
    living_build.add_argument("--output", type=Path, required=True)
    living_build.add_argument("--bindings", default="{}", help="Objeto JSON: nome -> JSON Pointer")
    living_build.add_argument("--timeout", type=float, default=60)
    living_build.add_argument("--watch", action="store_true")
    living_build.add_argument("--delay", type=float, default=.2)
    living_build.add_argument("--latex-fallback", type=Path)
    living_inspect = living_commands.add_parser("inspect")
    living_inspect.add_argument("pdf", type=Path)
    living_inspect.add_argument("--extract", type=Path)
    args = parser.parse_args(argv)
    def save_json(path,payload):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8') as output:
            json.dump(payload,output,ensure_ascii=False,sort_keys=True)
            output.write('\n')
    try:
        if args.command == "capabilities":
            from ..core.capabilities import ScientificCapabilities
            manifest = ScientificCapabilities.load(args.manifest)
            print(json.dumps({"manifest_id": manifest.content_id,
                              "contract": manifest.query(args.profile, args.operation),
                              "scientific_completion_established": False}, ensure_ascii=False))
            return 0
        if args.command in {"freeze-evaluation", "evaluate-frozen", "check-evaluation"}:
            from ..core.semantic_contracts import load_json
            from ..evaluation.frozen import FrozenEvaluation
            if args.command == "freeze-evaluation":
                evaluation = FrozenEvaluation(_bounded_json_text(args.source))
                save_json(args.destination, load_json(evaluation.to_json()))
                print(json.dumps({"protocol_id": evaluation.protocol_id}))
                return 0
            evaluation = FrozenEvaluation.from_json(_bounded_json_text(args.protocol), expected_id=args.expected_id)
            submission = load_json(_bounded_json_text(args.submission))
            if args.command == "check-evaluation":
                valid = evaluation.verify_report(load_json(_bounded_json_text(args.report)), submission)
                print(json.dumps({"valid": valid, "protocol_id": evaluation.protocol_id}))
                return 0 if valid else 1
            report = evaluation.evaluate(submission)
            save_json(args.output, report)
            print(json.dumps(report, ensure_ascii=False))
            return 0
        if args.command == "artifact":
            from ..pipeline.scientific_cycle import build_scientific_artifact, replay_scientific_artifact
            artifact = build_scientific_artifact(family=args.family, seed=args.seed, size=args.size,
                                                 license_id=args.license_id, provenance=args.provenance)
            report = replay_scientific_artifact(artifact)
            args.destination.parent.mkdir(parents=True, exist_ok=True)
            with args.destination.open("x", encoding="utf-8") as output:
                output.write(artifact.to_json())
            print(json.dumps(report, ensure_ascii=False))
            return 0
        if args.command == "check-artifact":
            from ..core.scientific_artifact import ScientificArtifact
            from ..pipeline.scientific_cycle import replay_scientific_artifact
            artifact = ScientificArtifact.from_json(_bounded_json_text(args.path))
            print(json.dumps(replay_scientific_artifact(artifact), ensure_ascii=False))
            return 0
        if args.command in {'discover','evolve','domain-suite','knowledge-audit','research-laboratory','independent-benchmark','learning-experiment'}:
            from ..scientific_workflows import write_json
            from ..research_workflows import discovery_demo,evolution_demo,domain_suite,run_research_laboratory
            if args.command == 'discover':
                result = discovery_demo(); write_json(args.destination,result)
            elif args.command == 'evolve':
                result = evolution_demo(args.destination,generations=args.generations)
            elif args.command == 'domain-suite':
                result = domain_suite(); write_json(args.destination,result)
            elif args.command == 'knowledge-audit':
                from ..knowledge.federation import verify_snapshot
                result = verify_snapshot(json.loads(args.source.read_text(encoding='utf-8')),allow_unsigned=args.allow_unsigned)
                print(json.dumps(result,sort_keys=True)); return 0 if result['valid'] else 1
            elif args.command == 'research-laboratory':
                result = run_research_laboratory(args.destination)
            elif args.command == 'independent-benchmark':
                from ..benchmarks.independent import run_benchmark
                result = run_benchmark(count=args.count,seed=args.seed,timeout=args.timeout); write_json(args.destination,result)
            else:
                from ..training.controlled_experiment import load_gsm8k,nabla_augmentation,controlled_experiment
                if args.destination.exists(): raise FileExistsError(args.destination)
                training,test,source = load_gsm8k(args.dataset,train_count=args.train_count,test_count=args.test_count)
                result = controlled_experiment(training,test,nabla_augmentation(args.train_count),steps=args.steps,
                                               source_manifest=source,output_directory=args.destination)
                write_json(args.destination/'report.json',result)
            print(json.dumps(result,ensure_ascii=True,sort_keys=True)); return 0
        if args.command in {'studio','dataset-build','dataset-check','world-heat','agent','evaluate-dataset','laboratory'}:
            from ..scientific_workflows import build_dataset, evaluate_dataset, run_laboratory, write_json
            if args.command == 'studio':
                from ..documents.document_model import Document
                from ..documents.publication import publish
                result = publish(Document.from_data(json.loads(args.source.read_text(encoding='utf-8'))),
                                 args.destination, asset_root=args.assets, pdf_backend=args.pdf_backend,
                                 evidence_sources={k:args.evidence.parent/v for k,v in json.loads(args.evidence.read_text(encoding='utf-8')).items()} if args.evidence else None,
                                 require_evidence=args.require_evidence)
            elif args.command == 'dataset-build':
                result = build_dataset(args.destination, count=args.count, seed=args.seed,
                                       license_id=args.license, provenance=args.provenance, parquet=args.parquet)
            elif args.command == 'dataset-check':
                from ..export.bundle import verify_bundle
                valid = verify_bundle(args.directory)
                print(json.dumps({'valid':valid}))
                return 0 if valid else 1
            elif args.command == 'world-heat':
                from ..worlds.model_spec import HeatModelSpec
                from ..worlds.pde import solve_heat
                result = solve_heat(HeatModelSpec(diffusivity=args.diffusivity,duration=args.duration),
                                    cells=args.cells,steps=args.steps)
                write_json(args.destination,result)
            elif args.command == 'agent':
                from ..agents import Planner, ScientificProposal as Proposal, Permissions, scientific_registry
                result = Planner(scientific_registry(), Permissions(frozenset(args.allow),args.max_calls,args.timeout)).run(
                    Proposal.from_data(json.loads(args.source.read_text(encoding='utf-8'))))
                write_json(args.destination,result)
                print(json.dumps({'completed':result['completed'],'final_receipt':result['final_receipt']}))
                return 0 if result['completed'] else 1
            elif args.command == 'evaluate-dataset':
                result = evaluate_dataset(args.directory,benchmark_name=args.benchmark)
                write_json(args.destination,result)
            else:
                result = run_laboratory(args.destination,seed=args.seed,count=args.count,parquet=args.parquet)
            print(json.dumps(result,ensure_ascii=False,sort_keys=True))
            return 0
        if args.command == "prove":
            import re
            from ..formal import FormalStatement,Predicate,translate_statement,check_lean,solve_statement
            from ..expression import parse_expr
            from ..verify.certificate import make_formal_certificate
            hypotheses=[]
            relations={'=':'eq','==':'eq','!=':'ne','<=':'le','<':'lt','>=':'ge','>':'gt'}
            for text in args.assumption:
                match=re.fullmatch(r'(.+?)\s*(==|!=|<=|>=|=|<|>)\s*(.+)',text)
                if match is None:raise ValueError('Hipotese requer duas expressoes e relacao')
                hypotheses.append(Predicate(parse_expr(match[1]),relations[match[2]],parse_expr(match[3])))
            statement=FormalStatement(Predicate(parse_expr(args.left),args.relation,parse_expr(args.right)),tuple(hypotheses))
            if args.backend=='lean':
                translation=translate_statement(statement,args.strategy)
                receipt=check_lean(translation,args.project,args.timeout).to_data()
                success=receipt['status']=='proved'
            elif args.backend=='lean-std':
                from ..formal.lean_std import prove_with_std
                if args.strategy != 'auto':
                    raise ValueError('Backend lean-std seleciona a estratégia automaticamente')
                receipt=prove_with_std(statement,args.project,timeout=args.timeout)
                success=receipt['status']=='proved'
            else:
                receipt=solve_statement(statement,timeout_ms=args.timeout*1000)
                success=receipt['status']=='unsat'
            certificate=make_formal_certificate(statement,receipt)
            if args.output:save_json(args.output,certificate)
            print(json.dumps(certificate,ensure_ascii=False,indent=2))
            return 0 if success else 1
        if args.command == "check-formal":
            from ..verify.certificate import verify_formal_certificate
            certificate=json.loads(args.path.read_text(encoding='utf-8'))
            valid=verify_formal_certificate(certificate,project=args.project)
            receipt=certificate.get('backend_receipt',{})
            print(json.dumps({'valid':valid,'status':receipt.get('status'),'goal_proved':valid and receipt.get('status') in ('proved','unsat'),
                              'formal_proof':valid and receipt.get('formal_proof') is True}))
            return 0 if valid else 1
        if args.command == "shrink":
            from ..falsifier.shrink import shrink_counterexample
            result=shrink_counterexample(args.left,args.right,json.loads(args.assignment),budget=args.budget).to_data()
            if args.output:save_json(args.output,result)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0
        if args.command == "diagram":
            from ..graphics.artifacts import export_scene
            if args.kind in ('right_triangle','parallelogram','circumcircle'):
                from ..forge.constructors.geometry import construct
                scene=construct(args.seed,args.size,args.kind)
            elif args.kind=='function':
                from ..graphics.sampling import function_scene
                scene=function_scene(args.function)
            elif args.kind=='vector_field':
                from ..graphics.sampling import vector_field_scene
                scene=vector_field_scene(args.dx,args.dy)
            else:
                from ..graphics.sampling import phase_portrait_scene
                scene=phase_portrait_scene(args.dx,args.dy,initials=tuple(tuple(v) for v in json.loads(args.initials)),duration=args.duration,steps=args.steps)
            result=export_scene(scene,args.destination,width=args.width,height=args.height)
            print(json.dumps(result,ensure_ascii=False,indent=2))
            return 0
        if args.command == "check-diagram":
            from ..graphics.artifacts import verify_scene_bundle
            valid=verify_scene_bundle(args.directory)
            print(json.dumps({'valid':valid}))
            return 0 if valid else 1
        if args.command == "living-paper":
            from ..publishing.living_papers_compiler import LivingPaperCompiler
            if args.living_command == "inspect":
                inspected = LivingPaperCompiler.inspect(args.pdf)
                if args.extract is not None:
                    with args.extract.open("x", encoding="utf-8") as stream:
                        from ..core.semantic_ir import canonical_json
                        stream.write(canonical_json(inspected["bundle"])+"\n")
                print(json.dumps(inspected, ensure_ascii=True, sort_keys=True))
                return 0
            compiler = LivingPaperCompiler(args.template, args.artifact, args.output,
                bindings=json.loads(args.bindings), timeout=args.timeout,
                latex_fallback=args.latex_fallback)
            if args.watch:
                import time
                with compiler.watch(args.delay) as handle:
                    try:
                        while handle.thread.is_alive():
                            time.sleep(.2)
                        if handle.error is not None:
                            raise handle.error
                    except KeyboardInterrupt:
                        pass
                return 0
            built = compiler.build()
            print(json.dumps({"pdf":str(built.pdf),"artifact":str(built.artifact),
                "manifest":str(built.manifest),"experiment_hash":built.experiment_hash,
                "revision":built.revision,"changed":built.changed}, sort_keys=True))
            return 0
        if args.command == "catalog":
            from ..calc.catalog import catalog
            print(json.dumps(catalog(), ensure_ascii=False, indent=2))
            return 0
        if args.command == "calc":
            from ..calc import CalculationSession,Notebook
            arguments=json.loads(args.arguments)
            if not isinstance(arguments,dict):
                raise ValueError("Argumentos precisam ser objeto JSON")
            calculation=CalculationSession().execute(args.operation,**arguments)
            if args.notebook:
                notebook=Notebook()
                notebook.append(calculation)
                notebook.save(args.notebook)
            print(json.dumps(calculation.to_data(),ensure_ascii=False,indent=2))
            return 0
        if args.command == "replay-notebook":
            from ..calc import Notebook
            notebook=Notebook.load(args.path)
            print(json.dumps({"valid":True,"cells":notebook.replay()}))
            return 0
        if args.command == "forge":
            if args.families or args.all_families:
                if args.pdf_backend:
                    raise ValueError("Exportacao Forge v2 emite dados/rastros; PDF continua no ciclo v1")
                if args.families and args.all_families:
                    raise ValueError("Escolha --families ou --all-families")
                from ..forge.factory import run_factory
                from ..forge.task_spec import FAMILIES
                result=run_factory(args.destination,count=args.count,seed=args.seed,
                    families=tuple(args.families or FAMILIES),sizes=tuple(args.sizes or (args.size,)),
                    license_id=args.license_id,provenance=args.provenance,calibration=args.calibrate,budget=args.solver_budget)
                print(json.dumps(result,ensure_ascii=False,indent=2))
                return 0
            if args.calibrate or args.sizes:
                raise ValueError("--calibrate/--sizes requer --families ou --all-families")
            from ..forge.pipeline import run_cycle
            result = run_cycle(args.destination, count=args.count, seed=args.seed, size=args.size,
                               license_id=args.license_id, provenance=args.provenance, pdf_backend=args.pdf_backend)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "check-bundle":
            from ..forge.pipeline import verify_bundle
            from ..forge.factory import verify_factory
            manifest_path=args.directory/"manifest.json"
            manifest=json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
            valid=verify_factory(args.directory) if manifest.get("schema_version")==2 else verify_bundle(args.directory)
            print(json.dumps({"valid": valid}))
            return 0 if valid else 1
        if args.command == "falsify":
            from ..falsifier import search_equivalence
            if args.shrink:
                from ..falsifier.search import investigate
                payload=investigate(args.left,args.right,radius=args.radius,budget=args.budget)
            else:
                payload=search_equivalence(args.left,args.right,radius=args.radius,budget=args.budget).to_data()
            if args.output:save_json(args.output,payload)
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if args.command == "simulate":
            from ..worlds import ModelSpec, convergence_study
            model = ModelSpec(args.model, tuple(args.initial), args.rate, args.duration)
            result = convergence_study(model, steps=args.steps, method=args.method, tolerance=args.tolerance)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["within_tolerance"] else 1
        if args.command == "desktop":
            from ..desktop.app import main as desktop_main
            desktop_args = ["--data-dir", str(args.data_dir)]
            if args.no_browser:
                desktop_args.append("--no-browser")
            desktop_main(desktop_args)
            return 0
        if args.command == "doctor":
            report = runtime_report(probe=args.probe)
            print(json.dumps(report.to_data(), ensure_ascii=False))
            return 0 if report.compatible else 1
        if args.command == "orbit":
            object_orbit = earth_circular_orbit(args.altitude_m)
            print(json.dumps(object_orbit.summary(), ensure_ascii=False, indent=2))
            if args.svg:
                print("SVG:", write_earth_orbit_svg(object_orbit, args.svg))
            return 0
        if args.command == "fluid":
            flow = PipeFlow(args.radius_m, args.length_m, args.pressure_pa,
                            args.viscosity_pa_s, args.density_kg_m3)
            print(json.dumps(flow.solve().__dict__, ensure_ascii=False, indent=2))
            return 0
        if args.command == "curate":
            print(json.dumps(curate(args.db, args.destination, license_id=args.license,
                                    provenance=args.provenance), ensure_ascii=False, indent=2))
            return 0
        if args.command == "backup":
            print(json.dumps(backup_database(args.db, args.destination).to_data(), ensure_ascii=False))
            return 0
        if args.command == "restore":
            print(json.dumps(restore_database(args.source, args.db).to_data(), ensure_ascii=False))
            return 0
        if args.command == "import":
            inserted, repeated = import_snapshot(args.db, args.source)
            print(f"Importados: {inserted}; duplicados idênticos: {repeated}")
            return 0
        if args.command == "formal":
            payload = load_result(args.db, args.identifier)
            if payload is None or not verify_record(payload):
                raise ValueError("Registro inexistente ou inválido")
            result = calculate(payload["source"], payload["values"])
            check = verify_with_lean(result, args.project)
            print(json.dumps(check.__dict__, ensure_ascii=False))
            return 0 if check.verified else 1
        if args.command == "show":
            payload = load_result(args.db, args.identifier)
            if payload is None:
                print("Registro não encontrado", file=sys.stderr)
                return 1
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        if args.command == "verify":
            payload = load_result(args.db, args.identifier)
            valid = payload is not None and verify_record(payload)
            print("Reexecução exata:", "válida" if valid else "inválida ou ausente")
            return 0 if valid else 1
        if args.command == "export":
            count, digest = export_verified(args.db, args.destination)
            print("Snapshot local:", args.destination, "registros:", count, "sha256:", digest)
            return 0
        if args.pdf and args.tex is None:
            parser.error("--pdf requer --tex")
        values = dict(args.value)
        if len(values) != len(args.value):
            parser.error("Cada símbolo deve ter um valor único")
        result = calculate(args.expression, values)
        created = save_result(args.db, result)
        print("ID:", result.content_id)
        print("Inicial:", render(result.original))
        for step in result.steps:
            print(f"{step.rule}: {render(step.before)} -> {render(step.after)}")
        for assumption in result.to_data()["assumptions"]:
            print("Hipótese:", assumption)
        print("Resultado exato:", result.value)
        print("Banco:", args.db, "(novo)" if created else "(já registrado)")
        if args.tex is not None:
            tex, pdf = write_report(result, args.tex, args.pdf)
            print("LaTeX:", tex)
            if pdf:
                print("PDF:", pdf)
        return 0
    except (ValueError, KeyError, TypeError, ArithmeticError, RuntimeError, ImportError, OSError, sqlite3.Error, DomainError) as exc:
        print("Erro:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
