"""Local bibliographic snapshots with explicit scope, sources and query receipts."""
from dataclasses import dataclass, asdict
import re
from ..core.semantic_ir import fingerprint
from ..documents.citations import Citation


@dataclass(frozen=True)
class LiteratureEntry:
    citation: Citation
    summary: str
    keywords: tuple[str,...]
    source: str
    license_id: str
    expression: str = ''

    def __post_init__(self):
        object.__setattr__(self,'keywords',tuple(self.keywords))
        if not self.source.strip() or not self.license_id.strip() or not self.summary.strip():
            raise ValueError('Procedência, licença e resumo obrigatórios')
        if self.expression:
            from ..expression import parse_expr
            parse_expr(self.expression)

    def to_data(self):
        return asdict(self)


class LiteratureCorpus:
    def __init__(self, entries, *, provenance):
        self.entries=tuple(entries)
        if len(self.entries)>10000 or not provenance.strip() or len({e.citation.key for e in self.entries})!=len(self.entries):
            raise ValueError('Corpus ou procedência inválidos')
        self.provenance=provenance

    def to_data(self):
        return {'entries':[e.to_data() for e in self.entries],'provenance':self.provenance}

    @property
    def corpus_id(self):
        return fingerprint(self.to_data())

    @classmethod
    def from_data(cls,data):
        entries=[]
        for row in data['entries']:
            row=dict(row); row['citation']=Citation(**row['citation'])
            entries.append(LiteratureEntry(**row))
        return cls(entries,provenance=data['provenance'])

    def search(self, query, *, limit=10):
        if not query.strip() or len(query)>1024 or type(limit) is not int or not 1<=limit<=100:
            raise ValueError('Consulta ou limite inválido')
        terms=set(re.findall(r'\w+',query.casefold()))
        hits=[]
        for entry in self.entries:
            text=' '.join((entry.citation.title,entry.summary,*entry.keywords)).casefold()
            score=sum(term in set(re.findall(r'\w+',text)) for term in terms)
            if score:
                hits.append({'entry':entry.to_data(),'matched_terms':score})
        hits.sort(key=lambda h:(-h['matched_terms'],h['entry']['citation']['key']))
        payload={'query':query,'corpus_id':self.corpus_id,'corpus_provenance':self.provenance,
                 'entries_consulted':len(self.entries),'hits':hits[:limit],
                 'scope':'local supplied metadata snapshot; no global literature or priority claim',
                 'source_authentication_performed':False}
        return {**payload,'query_id':fingerprint(payload)}
