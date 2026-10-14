"""Absence of a local match is never reported as global scientific novelty."""
from .theorem_search import search_identity


def screen_novelty(hypothesis, corpus, *, query):
    lookup=corpus.search(query)
    matches=[]
    for entry in corpus.entries:
        if entry.expression:
            result=search_identity(hypothesis.expression,entry.expression)
            if result['receipt'].get('equal') is True:
                matches.append({'citation_key':entry.citation.key,'identity':result})
    return {'hypothesis_id':hypothesis.hypothesis_id,'literature_query':lookup,
            'known_local_equivalents':matches,'status':'local_equivalent_found' if matches else 'novelty_not_established',
            'global_novelty_established':False,'corpus_empty':not corpus.entries}
