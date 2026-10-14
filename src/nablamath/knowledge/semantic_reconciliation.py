"""Conservative semantic keys; equivalence proposals do not merge histories."""
import unicodedata
from ..core.semantic_ir import fingerprint
from ..expression import parse_expr,render
from ..math.algebra.groebner import polynomial_from_expr


def semantic_key(revision,metadata=None):
    if metadata is None:
        return fingerprint({'kind':'exact_text','statement':unicodedata.normalize('NFC',revision.statement)})
    if set(metadata)!={'kind','expression','domain','input_unit','output_unit','assumptions'} or metadata['kind']!='polynomial':
        raise ValueError('Metadados semânticos desconhecidos')
    if render(parse_expr(metadata['expression']))!=render(parse_expr(revision.statement)):
        raise ValueError('Expressão não corresponde ao enunciado da revisão')
    polynomial=polynomial_from_expr(parse_expr(metadata['expression']),('x',))
    from ..core.semantic_ir import rational
    if len(metadata['domain'])!=2 or rational(metadata['domain'][0])>=rational(metadata['domain'][1]):
        raise ValueError('Domínio semântico inválido')
    from ..core.obligations import domain_obligations
    data={**metadata,'domain_obligations':[o.to_data() for o in domain_obligations(parse_expr(metadata['expression']))],'expression':[[list(m),str(c)] for m,c in polynomial.terms],
          'domain':[str(rational(v)) for v in metadata['domain']]}
    return fingerprint(data)


def reconcile(ledgers,*,metadata=None):
    metadata=metadata or {};groups={};heads={}
    for ledger in ledgers:
        for claim in sorted({r.claim for r in ledger.revisions}):
            revision=ledger.latest(claim)
            key=semantic_key(revision,metadata.get(revision.revision_id))
            groups.setdefault(key,set()).add(revision.revision_id)
            heads.setdefault(claim,set()).add(revision.revision_id)
    revisions={r.revision_id:r for ledger in ledgers for r in ledger.revisions}
    for claim,values in heads.items():
        ancestors=set()
        for identifier in values:
            current=revisions[identifier].previous
            while current is not None:
                ancestors.add(current);current=revisions[current].previous
        heads[claim]=values-ancestors
    return {'equivalence_proposals':[{'semantic_id':key,'revisions':sorted(values)} for key,values in sorted(groups.items()) if len(values)>1],
            'concurrent_heads':{key:sorted(values) for key,values in heads.items() if len(values)>1},
            'automatic_merge_performed':False,'scope':'exact text or declared polynomial domains/units/assumptions only'}
