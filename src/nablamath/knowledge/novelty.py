"""Replayable relative novelty screening over a supplied bibliographic snapshot."""
from ..core.semantic_ir import fingerprint
from ..discovery.novelty_screen import screen_novelty


def assess_relative_novelty(hypothesis, corpus, *, query, reviewer, references_consulted):
    references_consulted = tuple(references_consulted)
    known = {entry.citation.key for entry in corpus.entries}
    if not isinstance(reviewer, str) or not reviewer.strip() or len(set(references_consulted)) != len(references_consulted) or not set(references_consulted) <= known:
        raise ValueError('Reviewer and unique references from supplied corpus required')
    payload = {'schema_version': 1, 'screen': screen_novelty(hypothesis, corpus, query=query),
               'reviewer': reviewer, 'references_consulted': list(references_consulted),
               'review_coverage': len(references_consulted) / len(known) if known else None,
               'review_authentication': 'operator_declaration', 'global_novelty_established': False}
    return {**payload, 'assessment_id': fingerprint(payload)}


def replay_novelty(report, hypothesis, corpus):
    try:
        return report == assess_relative_novelty(hypothesis, corpus, query=report['screen']['literature_query']['query'],
            reviewer=report['reviewer'], references_consulted=report['references_consulted'])
    except (ValueError, TypeError, KeyError):
        return False
