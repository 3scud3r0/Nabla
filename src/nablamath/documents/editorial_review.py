"""Revision-specific editorial checklist with evidence resolution and replay."""
from ..core.semantic_ir import fingerprint


def review_document(document, *, reviewer, authors, evidence, visual_review=None):
    authors = tuple(authors)
    if not isinstance(reviewer, str) or not reviewer.strip() or not 1 <= len(authors) <= 1000 or any(not isinstance(x, str) or not x.strip() for x in authors) or reviewer in authors:
        raise ValueError('Declared reviewer must differ from authors')
    if any(key != fingerprint(value) for key, value in evidence.items()):
        raise ValueError('Evidence content digest mismatch')
    referenced = {key for section in document.sections for key in section.evidence_ids}
    referenced.update(key for section in document.sections for table in section.tables for key in table.evidence_ids)
    issues = []
    if referenced - set(evidence):
        issues.append({'kind': 'unresolved_evidence', 'ids': sorted(referenced - set(evidence))})
    if any(not section.evidence_ids and not any(t.evidence_ids for t in section.tables) for section in document.sections):
        issues.append({'kind': 'section_without_evidence'})
    if visual_review is not None:
        if set(visual_review) != {'artifact_id', 'notes', 'defects'} or visual_review['artifact_id'] not in evidence or not isinstance(visual_review['notes'], str) or not visual_review['notes'].strip() or not isinstance(visual_review['defects'], list) or any(not isinstance(x, str) or not x.strip() for x in visual_review['defects']):
            raise ValueError('Visual inspection requires resolved artifact, notes and defect list')
        if visual_review['defects']:
            issues.append({'kind': 'visual_defects', 'defects': visual_review['defects']})
    payload = {'schema_version': 1, 'document_id': document.content_id, 'reviewer': reviewer,
               'authors': list(authors), 'evidence': evidence, 'visual_review': visual_review,
               'issues': issues, 'local_checks_passed': not issues,
               'visual_inspection_declared': visual_review is not None,
               'external_review_authenticated': False, 'scientific_claims_validated': False}
    return {**payload, 'review_id': fingerprint(payload)}


def replay_editorial_review(report, document):
    try:
        return report == review_document(document, **{key: report[key] for key in
            ('reviewer', 'authors', 'evidence', 'visual_review')})
    except (ValueError, TypeError, KeyError):
        return False
