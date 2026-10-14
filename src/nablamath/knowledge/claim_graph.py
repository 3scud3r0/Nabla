"""Version-addressed claims, explicit contradictions and dependency traversal."""
from dataclasses import dataclass,asdict
from ..core.semantic_ir import fingerprint


@dataclass(frozen=True)
class ClaimRelation:
    source: str
    target: str
    relation: str
    rationale: str

    def __post_init__(self):
        if self.source==self.target or self.relation not in {'supports','contradicts','uses'} or not self.rationale.strip():
            raise ValueError('Relação científica explícita inválida')


class ClaimGraph:
    def __init__(self,ledger,relations=()):
        self.ledger=ledger;self.relations=tuple(relations)
        known={r.revision_id for r in ledger.revisions}
        for relation in self.relations:
            if relation.source not in known or relation.target not in known:
                raise ValueError('Relação refere revisão ausente')
        edges={r.revision_id:set(r.dependencies) for r in ledger.revisions}
        for relation in self.relations:
            if relation.relation=='uses':edges[relation.source].add(relation.target)
        # Topological elimination bounds recursion and rejects cycles in dependencies.
        remaining={k:set(v) for k,v in edges.items()}
        while remaining:
            roots={k for k,v in remaining.items() if not v}
            if not roots:raise ValueError('Ciclo entre dependências de afirmações')
            remaining={k:v-roots for k,v in remaining.items() if k not in roots}
        self.dependencies=edges

    def affected_by(self,revision_id):
        if revision_id not in self.dependencies:raise KeyError(revision_id)
        affected={revision_id}
        while True:
            more={key for key,deps in self.dependencies.items() if deps&affected}
            more.update(r.revision_id for r in self.ledger.revisions if r.previous in affected)
            if more<=affected:break
            affected.update(more)
        return tuple(sorted(affected-{revision_id}))

    def to_data(self):
        return {'ledger':self.ledger.to_data(),'relations':[asdict(r) for r in self.relations],
                'semantics':'relations are explicit assertions, not automatically established entailments'}
