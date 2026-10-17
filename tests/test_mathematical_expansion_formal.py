"""Structured proof obligations and review bindings. Deliberately unexecuted."""
from dataclasses import replace
import pytest


def test_matrix_certificate_produces_independent_scalar_goals():
    from nablamath.formal.translate import certificate_statements,translate_certificate
    certificate={'kind':'matrix_product','left':[[1,2],[0,1]],'right':[[1,0],[3,1]],'result':[[7,2],[3,1]]}
    statements=certificate_statements(certificate)
    assert len(statements)==4 and all(s.goal.evaluate({}) for s in statements)
    translated=translate_certificate(certificate)
    assert len(translated['translations'])==4 and not translated['formal_proof']
    forged={**certificate,'result':[[8,2],[3,1]]}
    assert not all(s.goal.evaluate({}) for s in certificate_statements(forged))


def test_inverse_and_boundary_certificates_do_not_accept_source_snippets():
    from nablamath.formal.translate import certificate_statements
    certificate={'kind':'matrix_inverse','left':[[2,0],[0,3]],'right':[['1/2',0],[0,'1/3']]}
    assert all(s.goal.evaluate({}) for s in certificate_statements(certificate))
    with pytest.raises(ValueError):certificate_statements({'kind':'identity','left':'x','right':'x','source':'by sorry'})


def test_translation_tampering_is_detected():
    from nablamath.formal.statement import FormalStatement
    from nablamath.formal.lean_bridge import translate_statement
    from nablamath.formal.translation_review import review_translation
    original=translate_statement(FormalStatement.equality('x+x','2*x'))
    tampered=replace(original,source=original.source.replace('2 : ℚ','3 : ℚ'))
    assert review_translation(original).accepted
    assert not review_translation(tampered).accepted


def test_certificate_review_is_bound_to_receipt_and_statement():
    from nablamath.formal.translation_review import bind_certificate_review
    certificate={'kind':'identity','left':'x+x','right':'2*x'}
    result=bind_certificate_review('Double a rational value',certificate,'a'*64,reviewer='reviewer',notes='Explicit translation reviewed',accepted=True)
    other=bind_certificate_review('Double a rational value',certificate,'b'*64,reviewer='reviewer',notes='Explicit translation reviewed',accepted=True)
    assert result['binding_id']!=other['binding_id']
    assert not result['reviewer_identity_authenticated'] and not result['semantic_equivalence_machine_proved']


def test_certificate_checker_preserves_unavailable_kernel_status(monkeypatch):
    import nablamath.formal.lean_checker as checker
    calls=[]
    def unavailable(statement,**options):
        calls.append(options)
        return checker.LeanCheck('unavailable',statement.content_id,'a'*64,None,(),'Mathlib missing',{})
    monkeypatch.setattr(checker,'prove_statement',unavailable)
    result=checker.check_exact_certificate({'kind':'identity','left':'1','right':'1'},timeout=5)
    assert result['status']=='unavailable' and result['formal_proof'] is False and len(calls)==1
