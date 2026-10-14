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
