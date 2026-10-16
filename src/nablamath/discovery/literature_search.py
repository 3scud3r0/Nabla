"""Curated external-source snapshots with reproducible queries and review tracing."""
from dataclasses import dataclass
from ..training._bounded import bounded_tuple
from urllib.parse import urlsplit
from ..core.semantic_ir import fingerprint
from ..knowledge.literature import LiteratureCorpus


@dataclass(frozen=True)
class CuratedSource:
    name: str
    url: str
    retrieved_at: str
    curator: str
    corpus: LiteratureCorpus

    def __post_init__(self):
        from datetime import datetime
        if not all(isinstance(x,str) and x.strip() for x in (self.name,self.url,self.retrieved_at,self.curator)):
            raise ValueError('Declared source, retrieval and curator required')
        url=urlsplit(self.url)
        if url.scheme!='https' or not url.hostname or url.username or url.password:
            raise ValueError('HTTPS source URL without credentials required')
        timestamp=datetime.fromisoformat(self.retrieved_at.replace('Z','+00:00'))
        if timestamp.tzinfo is None or not isinstance(self.corpus,LiteratureCorpus):
            raise ValueError('Timestamp timezone and corpus required')

    @property
    def source_id(self):
        return fingerprint({'name':self.name,'url':self.url,'retrieved_at':self.retrieved_at,
                            'curator':self.curator,'corpus_id':self.corpus.corpus_id})


def search_literature(sources, query, *, limit=10):
    sources=bounded_tuple(sources,100,label='curated sources')
    if any(not isinstance(s,CuratedSource) for s in sources):
        raise ValueError('Typed curated sources required')
    if not sources or len(sources)>100 or len({s.source_id for s in sources})!=len(sources):
        raise ValueError('Unique bounded curated sources required')
    searches=[{'source_id':s.source_id,'url':s.url,'retrieved_at':s.retrieved_at,
               'curator':s.curator,'query':s.corpus.search(query,limit=limit)} for s in sources]
    data={'query':query,'sources':searches,'live_network_used':False,
          'global_novelty_established':False,'external_source_authentication':False}
    return {**data,'search_id':fingerprint(data)}


def record_literature_review(search, *, reviewer, author, consulted_citation_keys, false_positive_keys, conclusion):
    if fingerprint({k:v for k,v in search.items() if k!='search_id'})!=search['search_id']:
        raise ValueError('Corrupt search')
    if not isinstance(reviewer,str) or not reviewer.strip() or not isinstance(author,str) or not author.strip() or reviewer==author:
        raise ValueError('Distinct declared reviewer required')
    known={hit['entry']['citation']['key'] for source in search['sources'] for hit in source['query']['hits']}
    consulted=set(bounded_tuple(consulted_citation_keys,10000,label='consulted citations')); false=set(bounded_tuple(false_positive_keys,10000,label='false-positive citations'))
    if not consulted<=known or not false<=consulted or conclusion not in {'antecedent_found','inconclusive','no_match_in_supplied_sources'}:
        raise ValueError('Invalid cited review scope')
    if conclusion=='antecedent_found' and not consulted-false:
        raise ValueError('Antecedent requires a non-dismissed citation')
    data={'search_id':search['search_id'],'reviewer':reviewer,'author':author,
          'consulted_citation_keys':sorted(consulted),'false_positive_keys':sorted(false),
          'conclusion':conclusion,'independence':'operator_declared_only','identity_authenticated':False,
          'global_novelty_established':False}
    return {**data,'review_id':fingerprint(data)}
