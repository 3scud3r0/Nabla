"""Machine structural review, independent from human scientific approval and proof status."""
from dataclasses import dataclass
from ..core.semantic_ir import fingerprint
from .review import TranslationReview  # preserve the original explicit human-review record


@dataclass(frozen=True)
class StructuralReview:
    accepted: bool
    statement_id: str
    source_hash: str
    checks: tuple[str,...]
    errors: tuple[str,...]=()
    human_reviewed: bool=False

    def to_data(self):
        from dataclasses import asdict
        return asdict(self)


def review_translation(translation):
    from .lean_bridge import translate_statement
    expected=translate_statement(translation.statement,translation.strategy)
    errors=[]
    if translation.source!=expected.source:
        errors.append('source_does_not_match_typed_statement')
    checks=('exact_ast_regeneration','variable_bijection','all_domain_obligations_explicit',
            'only_whitelisted_tactics','no_user_lean_source')
    return StructuralReview(not errors,translation.statement.content_id,translation.source_hash,checks,tuple(errors))


def bind_translation(question, statement, *, task_id, reviewer, notes, accepted):
    """Bind a declared human review to exact question/statement/domain versions.

    This is a tamper-evident review record, not identity authentication or a
    machine proof that natural language means the supplied formal statement.
    """
    from .statement import FormalStatement
    if (not isinstance(statement, FormalStatement) or type(accepted) is not bool
            or any(not isinstance(v, str) or not v.strip() for v in (question, task_id, reviewer, notes))
            or len(question) > 100000):
        raise ValueError('Pergunta, tarefa, formalização e revisão explícita obrigatórias')
    payload = {'schema_version': 1, 'question': question, 'question_id': fingerprint(question),
               'task_id': task_id, 'statement': statement.to_data(), 'statement_id': statement.content_id,
               'reviewer': reviewer, 'notes': notes, 'accepted': accepted,
               'reviewer_identity_authenticated': False, 'semantic_equivalence_machine_proved': False}
    return {**payload, 'binding_id': fingerprint(payload)}


def verify_translation_binding(binding, *, question, statement, task_id):
    try:
        expected = bind_translation(question, statement, task_id=task_id, reviewer=binding['reviewer'],
                                    notes=binding['notes'], accepted=binding['accepted'])
        return expected == binding
    except (ValueError, TypeError, KeyError):
        return False


def bind_certificate_review(question,certificate,receipt_id,*,reviewer,notes,accepted):
    from .translate import certificate_statements
    from ..core.semantic_ir import fingerprint
    if type(accepted) is not bool or any(type(v) is not str or not v.strip() for v in (question,reviewer,notes)) or type(receipt_id) is not str or len(receipt_id)!=64 or any(c not in '0123456789abcdef' for c in receipt_id):raise ValueError('Explicit question, review and receipt SHA-256 required')
    statements=certificate_statements(certificate)
    payload={'question_id':fingerprint(question),'certificate_id':fingerprint(certificate),'receipt_id':receipt_id,
             'statement_ids':[s.content_id for s in statements],'reviewer':reviewer,'notes':notes,'accepted':accepted,
             'reviewer_identity_authenticated':False,'semantic_equivalence_machine_proved':False}
    return {**payload,'binding_id':fingerprint(payload)}
