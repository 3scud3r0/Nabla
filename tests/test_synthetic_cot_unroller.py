"""Mathematical invariants, export isolation, replay and tamper rejection."""
from copy import deepcopy
from fractions import Fraction as F
import hashlib
import json
import subprocess
import sys

import pytest

from nablamath.superintelligence.synthetic_cot_unroller import (
    FAMILIES, GenerationConfig, SimulatedReasoningTrace, export_dataset,
    verify_dataset, verify_record, coverage_report, TextualReasoningFormatter,
)
from nablamath.superintelligence.synthetic_certificates import reference_certificate


@pytest.mark.parametrize('family',FAMILIES)
def test_every_authored_family_executes_without_accepting_injected_errors(family):
    if family in {'lie.matrix_group','pde.fem'}:pytest.importorskip('scipy')
    if family not in {'matrix_noncommutativity','lorentz_signature','lyapunov','chain_rule','rational_domain'}:
        pytest.importorskip('sympy')
    if family in {'functional.fixed_point'}:pytest.importorskip('numpy')
    if family=='special.precision':pytest.importorskip('mpmath')
    record = SimulatedReasoningTrace(GenerationConfig(depth=1,error_rate=1)).generate(family)
    assert record['steps'] and record['synthetic'] and record['formal_proof'] is False
    for step in record['steps']:
        assert step['error']['detection']['accepted'] is False
        assert step['error']['candidate'] != step['receipt']['result']
    assert record['arithmetic'] in {'numerical_not_enclosed','exact_or_symbolic_bounded'}


def test_reference_checker_catches_forged_solver_result():
    with pytest.raises(ArithmeticError,match='referência'):
        reference_certificate('solve_linear',{'matrix':[[2,1],[1,3]],'rhs':[1,2]},
                              {'status':'unique','particular':['1','1']})
    certificate=reference_certificate('solve_linear',{'matrix':[[2,1],[1,3]],'rhs':[1,2]},
                                      {'status':'unique','particular':['1/5','3/5']})
    assert certificate['independent_of_producing_solver'] is True
    assert set(certificate['residuals'])=={'0'}


def test_lyapunov_solution_satisfies_original_equation_in_fraction_arithmetic():
    r=SimulatedReasoningTrace(GenerationConfig(depth=1,difficulty=2,error_rate=0)).generate('lyapunov')
    n=len(r['answer']['P']);p=[[F(v) for v in row] for row in r['answer']['P']]
    a=[[F(i+1 if i==j else int(j==i+1),8*n) for j in range(n)] for i in range(n)]
    first=r['steps'][0]['receipt'];q=[F(v) for v in first['request']['arguments']['rhs']]
    for i in range(n):
        for j in range(n):
            assert p[i][j]-sum(a[k][i]*p[k][l]*a[l][j] for k in range(n) for l in range(n))==q[i*n+j]
    assert all(s['certificate']['value']=='0' for s in r['steps'] if s.get('certificate',{}).get('kind')=='exact_residual')


def test_determinism_resume_and_record_tampering():
    g=SimulatedReasoningTrace(GenerationConfig(depth=2,error_rate=1))
    record=g.generate('rational_domain',7)
    assert record==g.generate('rational_domain',7)
    assert verify_record(record)
    damaged=deepcopy(record);damaged['answer']['domain']='all real numbers'
    assert not verify_record(damaged)
    all_rows=list(g.stream(4,['rational_domain','matrix_inverse']))
    assert all_rows[2:]==list(g.stream(2,['rational_domain','matrix_inverse'],start_index=2))


def test_family_splits_do_not_leak_and_sft_omits_corrupt_candidates(tmp_path):
    dest=tmp_path/'dataset'
    card=export_dataset(dest,count=4,config=GenerationConfig(depth=2,error_rate=1),families=['matrix_inverse','nt_factorization'])
    assert card['count']==4 and card['rejected_candidates']==8
    assert verify_dataset(dest)
    rows=[json.loads(line) for line in (dest/'dataset.jsonl').read_text().splitlines()]
    assert len({r['task_id'] for r in rows})==4
    for family in card['families']:
        assert len({r['split'] for r in rows if r['family']==family})==1
    sft=[json.loads(line) for line in (dest/'sft.jsonl').read_text().splitlines()]
    assert all('Candidato deliberadamente incorreto' not in r['messages'][1]['content'] for r in sft)
    assert (dest/'amostras.txt').read_text().count('AMOSTRA ')==4
    translated=(dest/'amostras_traduzidas.txt').read_text()
    assert translated.count('AMOSTRA ')==4
    assert 'Requisição: {' not in translated and 'Resultado aceito: {' not in translated
    assert any(phrase in translated for phrase in ('Opa, ', 'Já achei:', 'O que não bate:'))
    assert any(phrase in translated for phrase in ('Vou corrigir isso:', 'Com a correção,', 'O ajuste fica assim:'))
    with pytest.raises(FileExistsError):export_dataset(dest,count=1)


def test_translator_explains_chain_rule_mutation_without_raw_json():
    record=SimulatedReasoningTrace(GenerationConfig(depth=3,error_rate=1)).generate('chain_rule')
    translated=TextualReasoningFormatter.translated_solution(record)
    assert 'derivar' in translated
    assert 'omissão da regra da cadeia' in translated
    assert any(phrase in translated for phrase in ('Opa, ', 'Já achei:', 'O que não bate:'))
    assert any(phrase in translated for phrase in ('Vou corrigir isso:', 'Com a correção,', 'O ajuste fica assim:'))
    assert 'eu propus' in translated and 'cálculo registrado dá' in translated
    assert '"arguments"' not in translated and '"operation"' not in translated
    assert 'não é um relato de pensamento espontâneo nem de raciocínio interno de uma rede neural' in translated.lower()


def test_rehashed_corruption_is_rejected_by_regeneration(tmp_path):
    dest=tmp_path/'dataset'
    export_dataset(dest,count=1,config=GenerationConfig(depth=1,error_rate=0),families=['matrix_inverse'])
    path=dest/'dataset.jsonl';r=json.loads(path.read_text());r['answer'][0]['inverse'][0][0]='999'
    path.write_text(json.dumps(r)+'\n')
    manifest_path=dest/'manifest.json';manifest=json.loads(manifest_path.read_text())
    manifest['files'][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n')
    assert not verify_dataset(dest)


def test_failed_export_removes_staging_directory(tmp_path,monkeypatch):
    def broken(*args,**kwargs):raise ArithmeticError('injected failure')
    monkeypatch.setattr(SimulatedReasoningTrace,'generate',broken)
    with pytest.raises(ArithmeticError):export_dataset(tmp_path/'data',count=1)
    assert list(tmp_path.iterdir())==[]


def test_constant_recipe_does_not_pad_depth_with_repeated_calculations():
    pytest.importorskip('sympy')
    r=SimulatedReasoningTrace(GenerationConfig(depth=16,error_rate=0)).generate('lie.roots')
    assert len(r['steps'])==1


def test_long_ito_suite_respects_backend_power_budget():
    pytest.importorskip('sympy')
    r=SimulatedReasoningTrace(GenerationConfig(depth=33,error_rate=0)).generate('ito_stratonovich')
    observables=[s['receipt']['request']['arguments']['parameters']['function'] for s in r['steps']
                 if s['receipt']['request']['operation']=='advanced_math']
    assert len(observables)==34 and len(set(observables))==34


@pytest.mark.parametrize('kwargs',[{'depth':0},{'depth':257},{'difficulty':9},{'seed':-1},{'error_rate':float('nan')},{'error_rate':True}])
def test_resource_configuration_is_closed(kwargs):
    with pytest.raises(ValueError):GenerationConfig(**kwargs)


def test_coverage_keeps_unimplemented_recipe_gaps_visible():
    data=coverage_report(['lyapunov','matrix_inverse'])
    assert data['catalog_operations']['matrix_inverse']['sampled']
    assert data['catalog_operations']['omni_superintelligence']['status']=='no_recipe'
    assert any(r['status']=='no_recipe' for r in data['advanced_actions'].values())


def test_procedural_import_never_loads_torch():
    code='''
import sys
from nablamath.superintelligence import SimulatedReasoningTrace
from nablamath.superintelligence.synthetic_cot_unroller import GenerationConfig
r=SimulatedReasoningTrace(GenerationConfig(depth=1)).generate('matrix_inverse')
assert r['steps']
assert 'torch' not in sys.modules
assert 'nablamath.superintelligence.omni_engine' not in sys.modules
'''
    subprocess.run([sys.executable,'-c',code],check=True)
