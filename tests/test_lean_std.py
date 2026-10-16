"""Kernel-backed arithmetic and adversarial receipt tests without Mathlib."""

from copy import deepcopy
from pathlib import Path
import json
import subprocess

import pytest

from nablamath.cli import main
from nablamath.core.semantic_ir import fingerprint
from nablamath.expression import parse_expr
from nablamath.formal.lean_checker import find_lake
from nablamath.formal.lean_std import prove_with_std, std_source, verify_std_receipt
from nablamath.formal.statement import FormalStatement, Predicate
from nablamath.verify.certificate import make_formal_certificate, verify_formal_certificate


PROJECT = Path(__file__).resolve().parents[1]/'lean'
KERNEL = pytest.mark.skipif(find_lake(PROJECT) is None, reason='Pinned Lean compiler absent')


def statement(left='x/x', right='1'):
    return FormalStatement.equality(left, right)


def test_source_is_ast_only_and_retains_domain():
    source = std_source(statement())
    assert 'import Std\n' in source
    assert 'Mathlib' not in source
    assert '(h0 : nabla_x ≠ (0 : Rat))' in source
    assert '#print axioms nabla_std_generated' in source
    assert 'native_decide' not in source
    assert 'sorry' not in source
    assert 'grind' in source
    assert 'decide +kernel' in std_source(statement('1/2+1/3', '5/6'))
    with pytest.raises(ValueError):
        std_source('example : False := by sorry')


def test_missing_project_reports_unavailable(tmp_path):
    receipt = prove_with_std(statement(), tmp_path)
    assert receipt['status'] == 'unavailable'
    assert receipt['formal_proof'] is False
    assert not verify_std_receipt(statement(), receipt, project=tmp_path)


@pytest.mark.parametrize('timeout', [True, 0, 301, 1.5])
def test_timeout_budget_is_strict(timeout):
    with pytest.raises(ValueError):
        prove_with_std(statement(), PROJECT, timeout=timeout)


@KERNEL
@pytest.mark.parametrize('left,right', [
    ('1/2+1/3','5/6'), ('-7/3*9/14','-3/2'),
    ('(x+1)*(x-1)','x*x-1'), ('(x+y)**2','x*x+2*x*y+y*y'),
    ('x/x','1'), ('x/2+x/2','x'), ('x**(-1)*x','1'),
])
def test_actual_kernel_proofs(left, right):
    proposition = statement(left, right)
    receipt = prove_with_std(proposition, PROJECT)
    assert receipt['status'] == 'proved', receipt['diagnostics']
    assert receipt['formal_proof'] is True
    assert 'sorryAx' not in receipt['axioms']
    assert verify_std_receipt(proposition, receipt, project=PROJECT)
    assert verify_formal_certificate(make_formal_certificate(proposition, receipt), project=PROJECT)


@KERNEL
def test_linear_implication_is_kernel_checked():
    proposition = FormalStatement(Predicate(parse_expr('x'), 'le', parse_expr('2*x')),
                                  (Predicate(parse_expr('x'), 'ge', parse_expr('0')),))
    receipt = prove_with_std(proposition, PROJECT)
    assert receipt['status'] == 'proved', receipt['diagnostics']
    assert verify_std_receipt(proposition, receipt, project=PROJECT)


@KERNEL
@pytest.mark.parametrize('left,right', [('1','2'), ('x+1','x'), ('x*x','x')])
def test_false_claims_cannot_be_saved_as_proofs(left, right):
    proposition = statement(left, right)
    receipt = prove_with_std(proposition, PROJECT, timeout=10)
    assert receipt['status'] in ('failed', 'timeout')
    assert receipt['formal_proof'] is False
    assert not verify_formal_certificate(make_formal_certificate(proposition, receipt), project=PROJECT)


@KERNEL
def test_rehashed_forged_receipts_are_reproved():
    proposition = statement('x+0', 'x')
    receipt = prove_with_std(proposition, PROJECT)
    assert receipt['status'] == 'proved'
    for key, value in [('source_hash','fake'), ('tool_version','fake'),
                       ('axioms',['sorryAx']), ('returncode',False),
                       ('statement_id',statement('x+1','x').content_id)]:
        changed = deepcopy(receipt)
        changed[key] = value
        changed['receipt_id'] = fingerprint({k:v for k,v in changed.items() if k != 'receipt_id'})
        assert not verify_std_receipt(proposition, changed, project=PROJECT)
    assert not verify_std_receipt(statement('x+1','x'), receipt, project=PROJECT)


@KERNEL
def test_cli_proof_and_check(tmp_path, capsys):
    path = tmp_path/'proof.json'
    assert main(['prove','x/x','1','--backend','lean-std','--project',str(PROJECT),'--output',str(path)]) == 0
    assert main(['check-formal',str(path),'--project',str(PROJECT)]) == 0
    assert json.loads(path.read_text())['backend_receipt']['formal_proof'] is True


@KERNEL
def test_certificate_cannot_substitute_unchecked_source():
    proposition = statement('x+0', 'x')
    certificate = make_formal_certificate(proposition, prove_with_std(proposition, PROJECT))
    assert 'import Std' in certificate['translation']['source']
    certificate['translation']['source'] += '\naxiom invented : False\n'
    certificate['certificate_id'] = fingerprint({k:v for k,v in certificate.items() if k != 'certificate_id'})
    assert not verify_formal_certificate(certificate, project=PROJECT)


def test_timeout_is_not_a_proof(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('lean', 1)
    monkeypatch.setattr('nablamath.formal.lean_std.find_lake', lambda project: Path('/tmp/lake'))
    monkeypatch.setattr('nablamath.formal.lean_std.run_lean_process', timeout)
    receipt = prove_with_std(statement(), PROJECT, timeout=1)
    assert receipt['status'] == 'timeout'
    assert receipt['formal_proof'] is False


@pytest.mark.parametrize('output', [
    "'nabla_std_generated' depends on axioms: [sorryAx]",
    "'nabla_std_generated' depends on axioms: [invented]",
    'Compilation succeeded without an axiom audit',
])
def test_untrusted_axioms_or_missing_audit_rejected(monkeypatch, output):
    def process(command, **kwargs):
        text = 'Lean (version 4.34.0, test)' if '--version' in command else output
        return subprocess.CompletedProcess(command, 0, text, '')
    monkeypatch.setattr('nablamath.formal.lean_std.find_lake', lambda project: Path('/tmp/lake'))
    monkeypatch.setattr('nablamath.formal.lean_std.run_lean_process', process)
    receipt = prove_with_std(statement(), PROJECT)
    assert receipt['status'] == 'rejected_axioms'
    assert receipt['formal_proof'] is False


@KERNEL
@pytest.mark.parametrize('family', [
    'difference_squares','affine_square','distributive','guarded_inverse',
    'monotone_affine','nonnegative_square','closed_rational','bounded_square',
    'quadratic_minimum','fraction_sum',
])
def test_structural_corpus_families_with_real_kernel(family):
    from tools.rational_proof_corpus import proposition
    proposition_value = proposition(family,3,7)
    receipt = prove_with_std(proposition_value,PROJECT,timeout=10)
    assert receipt['status'] == 'proved', receipt['diagnostics']
    assert not set(receipt['axioms'])-{'propext','Classical.choice','Quot.sound'}


def test_box_fact_emission_is_deterministic():
    proposition_value = FormalStatement(
        Predicate(parse_expr('x*x+y*y'),'le',parse_expr('5')),
        tuple(Predicate(parse_expr(variable),relation,parse_expr(bound))
              for variable,relation,bound in [('x','ge','-1'),('x','le','1'),
                                               ('y','ge','-2'),('y','le','2')]))
    source = std_source(proposition_value)
    assert source == std_source(proposition_value)
    assert 'Lean.Grind.OrderedRing.mul_nonneg' in source
    assert 'nabla_nonneg_' in source
