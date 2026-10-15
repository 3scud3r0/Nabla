"""Bounded CSL-JSON metadata import with immutable source snapshot receipts.

No networking, invented citations or global novelty claims. The caller supplies
an HTTPS source identifier, retrieval date and license; declarations are recorded,
not independently authenticated.
"""
import hashlib
import json
import re
from datetime import date
from ..documents.citations import Citation
from ..core.semantic_ir import fingerprint
from .literature import LiteratureEntry,LiteratureCorpus


def import_csl(raw,*,source_url,retrieved_at,license_id):
    if not isinstance(raw,bytes) or not 1<=len(raw)<=16*1024*1024:
        raise ValueError('Snapshot bibliográfico binário limitado obrigatório')
    if not isinstance(source_url,str) or not source_url.startswith('https://') or not license_id.strip():
        raise ValueError('Fonte HTTPS e licença obrigatórias')
    date.fromisoformat(retrieved_at)
    data=json.loads(raw.decode('utf-8'))
    if not isinstance(data,list) or not 1<=len(data)<=10000:raise ValueError('CSL-JSON deve ser lista limitada')
    entries=[]
    for row in data:
        title=row.get('title','');doi=row.get('DOI','');url=row.get('URL','')
        authors=tuple(a.get('literal') or ' '.join(filter(None,(a.get('given'),a.get('family')))) for a in row.get('author',()))
        try:year=row['issued']['date-parts'][0][0]
        except (KeyError,IndexError,TypeError) as exc:raise ValueError('Ano bibliográfico ausente') from exc
        if any(not isinstance(v,str) or len(v)>16384 for v in (title,doi,url,*authors)):
            raise ValueError('Metadado bibliográfico inválido')
        key='ref_'+fingerprint({'doi':doi,'title':title,'authors':authors,'year':year})[:24]
        abstract=row.get('abstract','')
        if not isinstance(abstract,str) or len(abstract)>100000:raise ValueError('Resumo fora do limite')
        summary=re.sub('<[^>]*>',' ',abstract).strip() or 'Bibliographic metadata only; abstract not supplied.'
        keyword=row.get('keyword','')
        if not isinstance(keyword,str):raise ValueError('Palavras-chave devem ser texto CSL')
        entries.append(LiteratureEntry(Citation(key,title,authors,year,url,doi),summary,
                       tuple(k.strip() for k in keyword.split(',') if k.strip()),source_url,license_id))
    digest=hashlib.sha256(raw).hexdigest()
    corpus=LiteratureCorpus(entries,provenance=f'{source_url} retrieved {retrieved_at} sha256:{digest}')
    receipt={'schema_version':1,'format':'CSL-JSON','source_url':source_url,'retrieved_at':retrieved_at,
             'license_id':license_id,'source_sha256':digest,'source_bytes':len(raw),'corpus_id':corpus.corpus_id,
             'entries':len(entries),'source_authentication_performed':False,'global_novelty_established':False}
    return corpus,{**receipt,'import_id':fingerprint(receipt)}
