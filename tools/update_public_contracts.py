"""Regenerate public, finite contracts from reviewed declarations and original IDs."""
from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]

# These scopes are authored declarations, not inferred from filenames/test counts.
PROFILES = [
 ('exact-artifact', [25,41,63,68], 'Two exact rational task families with semantic DAG replay',
  ['create_artifact','replay_artifact'], ['arbitrary_code','general_scientific_validation'],
  ['src/nablamath/core/scientific_artifact.py','src/nablamath/pipeline/scientific_cycle.py'],
  ['tests/integration/test_scientific_artifact.py'],'0'),
 ('rational-integration',[3,4,6,94], 'Polynomials and denominators split into rational linear factors',
  ['integrate_rational','verify_derivative_identity'],['general_risch','transcendental_towers'],
  ['src/nablamath/math/calculus/risch.py'],['tests/test_roadmap_integration_mesh.py'],'0'),
 ('tensor-ad',[7], 'Dense scalar/tensor programs under the declared coordinate and shape budgets',
  ['jacobian','hessian','broadcast'],['unbounded_tensors','general_control_flow'],
  ['src/nablamath/autodiff/second_order.py'],['tests/test_remaining_math_compiler.py'],'1/1000000'),
 ('compiled-ir',[13], 'Closed arithmetic tensor instruction set with typed serialization',
  ['compile','execute','roundtrip'],['arbitrary_source','distributed_speedup_claim'],
  ['src/nablamath/compiler/ir.py'],['tests/test_remaining_math_compiler.py'],'1/1000000'),
 ('controlled-proofs',[10,43,106,107,108], 'Controlled rational predicates and closed tactic portfolio',
  ['parse_controlled_statement','plan_proof','repair_tactic'],['free_natural_language','unverified_kernel_success'],
  ['src/nablamath/formal/proof_search_planner.py','lean/Nabla/KernelContracts.lean'],
  ['tests/test_roadmap_formal_workflows.py','tests/test_remaining_math_compiler.py'],'0'),
 ('device-kernels',[12,75,110,111,112,161], 'Optional modular elimination CUDA and parent lookup Triton',
  ['cuda_modular_rref','triton_parent_lookup','profile_wall_time'],['cpu_as_gpu','unmeasured_energy_claim'],
  ['src/nablamath/gpu/kernels/f4_cuda.py','src/nablamath/gpu/kernels/egraph_triton.py'],
  ['tests/benchmark/test_gpu_real_hardware.py','tests/test_remaining_physics_gpu.py'],'0'),
 ('bounded-physics',[14,15,28,73,74,119,163], 'Declared 1D Euler/channel/FLRW ideal models with finite checks',
  ['channel_stokes','flrw_residual','flrw_geodesic'],['general_einstein_solver','experimental_validation_claim'],
  ['src/nablamath/physics/fluids/channel.py','src/nablamath/physics/relativity/einstein_solver.py'],
  ['tests/test_remaining_physics_gpu.py','tests/science/test_observational_validation.py'],'1/1000000'),
 ('audited-train',[23,77,78,128,129,130,162], 'Frozen bounded supervised linear training and declared family transfer',
  ['fit_linear_reasoning','cross_domain_evaluate'],['llm_finetuning_claim','secret_holdout_claim'],
  ['src/nablamath/training/reasoning_finetune.py','src/nablamath/training/cross_domain_eval.py'],
  ['tests/test_remaining_learning.py','tests/benchmark/test_holdout_generalization.py'],'1/1000000'),
 ('curated-literature',[26,76,135,164], 'Queries over source-identified snapshots and declared review records',
  ['search_curated_snapshot','record_review'],['global_novelty_claim','authenticated_human_review_claim'],
  ['src/nablamath/discovery/literature_search.py'],['tests/science/test_independent_discovery.py'],'0'),
 ('consented-product',[16,17,19,38,40,55,58,59,72], 'Local consent-bound experiment, canonical documents and publication dry-run',
  ['local_experiment','replay_experiment','publication_dry_run','accessible_plot'],
  ['remote_publication_without_consent','visual_review_claim'],
  ['src/nablamath/desktop/workflows.py','src/nablamath/publisher/authorization.py','src/nablamath/reports/canonical_bundle.py'],
  ['tests/test_remaining_product.py'],'0'),
 ('federation',[30,31,32,143,144,152,165], 'Pinned-key attestations and durable local provenance/reconciliation',
  ['verify_attestation','reconcile_provenance'],['institutional_identity_without_trust','internet_multihost_claim'],
  ['src/nablamath/knowledge/distributed_provenance.py','src/nablamath/knowledge/institutional_identity.py'],
  ['tests/test_remaining_federation.py'],'0'),
 ('registered-comparison',[39,53], 'Fixed exact cohort and model commitments with one-time result ledger',
  ['register_study','score_paired_models','replay_study'],['posthoc_metric_selection','external_generalization_claim'],
  ['src/nablamath/benchmarks/preregistration.py'],['tests/test_registered_comparison.py'],'0'),
 ('capability-contracts',[64,66,67,68,69,83], 'Finite authored domains and bidirectional original requirement references',
  ['query_capability','validate_traceability'],['infer_scientific_completion'],
  ['src/nablamath/core/capabilities.py','tools/check_public_contracts.py'],
  ['tests/test_public_contracts.py'],'0'),
]


def write_contracts(root=ROOT):
    root=Path(root)
    matrix=json.loads((root/'docs/acceptance/evidence_matrix.json').read_text())
    profiles=[]
    for identifier,ids,domain,operations,refused,implementation,tests,tolerance in PROFILES:
        profiles.append({'id':identifier,'requirements':ids,'domain':domain,
            'operations':operations,'refused':refused,'absolute_tolerance':tolerance,
            'relative_tolerance':tolerance,'implementation':implementation,'tests':tests,
            'limitations':'Local bounded contract only; independent scientific acceptance is not established. '+
                ('Device execution remains untested on this host.' if identifier=='device-kernels' else '')})
    manifest={'schema_version':1,'owner':'Nabla maintainers; implementation reviewed through repository PR',
        'profiles':profiles,'scope':'Authored finite software contracts, not all mathematics or full-roadmap certification'}
    target=root/'docs/acceptance/scientific_capabilities.yaml'
    target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    rows=[]
    for row in matrix['requirements']:
        text=row['requirement']
        phases={int(x) for x in re.findall(r'F(\d+)',text)}
        for first,last in re.findall(r'F(\d+)[–-]F(\d+)',text):
            phases.update(range(int(first),int(last)+1))
        if not phases:
            # Specific follow-up items inherit the finite implementation profile;
            # F0 denotes contract/governance where no scientific phase was stated.
            phases={0}
        rows.append({'id':row['id'],'target':row['target'],'status':row['status'],
            'phases':['F'+str(n) for n in sorted(phases)],
            'implementation':row['implementation'],'tests':row['tests'],
            'evidence':row['evidence'],'remaining':row['remaining']})
    trace={'schema_version':1,'source':'docs/acceptance/evidence_matrix.json',
        'mapping_scope':'Original phase references expanded; unspecified phases assigned F0 governance, not inferred scientific maturity',
        'phase_policy':{f'F{i}':{'acceptance':'open' if i==13 else 'finite profiles only',
            'scientific_completion_established':False} for i in range(14)},'requirements':rows}
    (root/'docs/acceptance/vision_traceability.json').write_text(json.dumps(trace,ensure_ascii=False,indent=2)+'\n')
    backlog_path=root/'docs/audits/PHASES_1_12_COMPLETION_BACKLOG.json'
    if backlog_path.is_file():
        import hashlib
        source_backlog=json.loads(backlog_path.read_text())
        backlog=list(source_backlog['backlog'])
        text=(root/'docs/audits/PHASES_1_12_COMPLETION_BACKLOG.md').read_text()
        cross=re.findall(r'^\| (T-\d{2}) \| (.*?) \| (.*?) \|$',text,re.M)
        if len(backlog)!=96 or len(cross)!=8:
            raise ValueError('Expected original96 phase items and8 cross-cutting items')
        backlog.extend({'id':key,'phase':0,'paths':paths,'acceptance':acceptance}
                       for key,paths,acceptance in cross)
        normalized=[]
        prefixes=('src/','tests/','benchmarks/','templates/','lean/','docs/','tools/',
                  'scripts/','packaging/','sdk/','protocol/','services/','.github/')
        for item in backlog:
            paths=[]
            for raw in item['paths'].split(';'):
                path=re.sub(r'\s*\[novo\]','',raw).strip().strip('`').strip()
                if not path.startswith(prefixes) and '/' in path:
                    path='src/nablamath/'+path
                paths.append(path)
            associated=[]
            for row in matrix['requirements']:
                target=re.findall(r'`([^`]+)`',row['target'])
                target=target[0].rstrip('/') if target else row['target'].strip().rstrip('/')
                if any(path.rstrip('/')==target or path.startswith(target+'/')
                       or target.startswith(path.rstrip('/')+'/') for path in paths):
                    associated.append(row)
            normalized.append({'id':item['id'],'phase':'F'+str(item['phase']),
                'original_acceptance':item['acceptance'],'declared_paths':paths,
                'paths_not_present':[name for name in paths if not (root/name).exists()],
                'related_requirement_ids':[row['id'] for row in associated],
                'implementation':sorted({name for row in associated for name in row['implementation']}),
                'tests':sorted({name for row in associated for name in row['tests']}),
                'acceptance_status':'pending_completion',
                'mapping_scope':'Path overlap only; linked tests do not establish this entire acceptance criterion'})
        mapped={'schema_version':1,'original_source_sha256':hashlib.sha256(backlog_path.read_bytes()).hexdigest(),
            'count':104,'items':normalized,'all_backlog_acceptance_established':False}
        (root/'docs/acceptance/backlog_traceability.json').write_text(json.dumps(mapped,ensure_ascii=False,indent=2)+'\n')

    documents = ('README.md','description.md','vision.md','docs/PLANO_MESTRE_2026_2056.md',
        'docs/ARCHITECTURE_AND_ACCEPTANCE.md','docs/MATHEMATICS_COMPLETION_AUDIT.md',
        'docs/audits/PHASES_1_12_COMPLETION_BACKLOG.md')
    import os
    counts = {status:sum(row['status']==status for row in matrix['requirements'])
              for status in ('planned','partial','validated')}
    for name in documents:
        path=root/name
        if not path.is_file():
            continue
        link=lambda target: os.path.relpath(root/target,path.parent).replace(os.sep,'/')
        block=('<!-- nabla:contracts:start -->\n'
            '## Contratos executáveis e pendências atuais\n\n'
            f"A matriz registra {counts['partial']} requisitos com perfis parciais, "
            f"{counts['planned']} planejados e {counts['validated']} integralmente validados. "
            'Uma referência de implementação não equivale à aceitação integral.\n\n'
            f"- [Matriz original dos 213 requisitos]({link('docs/acceptance/evidence_matrix.json')}).\n"
            f"- [Rastreabilidade de fases, requisitos, testes e evidências]({link('docs/acceptance/vision_traceability.json')}).\n"
            f"- [Domínios, operações, recusas e tolerâncias]({link('docs/acceptance/scientific_capabilities.yaml')}).\n\n"
            'F0 explicita contratos e infraestrutura; F13 continua horizonte aberto. '
            'Os perfis de software não demonstram autonomia científica geral. '
            'Provas formais exigem kernel e auditoria de hipóteses; GPU exige '
            'execução identificada; observações e revisão externa não são '
            'substituídas por fixtures ou identidade declarada.\n\n'
            'Verificar: `python tools/check_roadmap.py` e '
            '`python tools/check_public_contracts.py`, na raiz do repositório.\n'
            '<!-- nabla:contracts:end -->')
        text=path.read_text()
        pattern=r'<!-- nabla:contracts:start -->.*?<!-- nabla:contracts:end -->'
        text=re.sub(pattern,lambda _:block,text,flags=re.S) if '<!-- nabla:contracts:start -->' in text else text.rstrip()+'\n\n'+block
        path.write_text(text.rstrip()+'\n')



if __name__=='__main__':
    write_contracts()
