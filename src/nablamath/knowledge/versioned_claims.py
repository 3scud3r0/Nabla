"""Append-only local claims. Evidence references are declarations, not automatic proofs."""
from dataclasses import dataclass, asdict
import json
from pathlib import Path

from ..core.semantic_ir import canonical_json, fingerprint


@dataclass(frozen=True)
class ClaimRevision:
    claim: str
    statement: str
    status: str
    evidence: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    previous: str | None = None
    schema_version: int = 1

    def __post_init__(self):
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        if not self.claim.strip() or not self.statement.strip() or self.schema_version != 1:
            raise ValueError('Afirmacao requer identificador, enunciado e versao valida')
        if self.status not in {'proposed', 'supported', 'refuted', 'withdrawn'}:
            raise ValueError('Estado de afirmacao invalido')
        if self.status in {'supported', 'refuted'} and not self.evidence:
            raise ValueError('Suporte/refutacao requer referencias de evidencia')
        if any(not isinstance(v, str) or not v.strip() for v in self.evidence + self.dependencies):
            raise ValueError('Referencias vazias nao permitidas')
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError('Dependencias repetidas')

    @property
    def revision_id(self):
        return fingerprint(asdict(self))

    def to_data(self):
        return {**asdict(self), 'revision_id': self.revision_id}


class ClaimLedger:
    def __init__(self, revisions=()):
        self._revisions = {}
        self._latest = {}
        for revision in revisions:
            self.append(revision)

    def get(self, revision_id):
        return self._revisions[revision_id]

    def to_data(self):
        return {'schema_version':1,'revisions':[r.to_data() for r in self.revisions]}

    @classmethod
    def from_data(cls,data):
        if set(data)!={'schema_version','revisions'} or data['schema_version']!=1 or len(data['revisions'])>10000:
            raise ValueError('Contrato de histórico inválido')
        ledger=cls()
        for item in data['revisions']:
            row=dict(item);identifier=row.pop('revision_id')
            revision=ClaimRevision(**row)
            if revision.revision_id!=identifier:
                raise ValueError('Hash de revisão divergente')
            ledger.append(revision)
        return ledger

    @property
    def revisions(self):
        return tuple(self._revisions.values())

    def latest(self, claim: str) -> ClaimRevision:
        return self._revisions[self._latest[claim]]

    def append(self, revision: ClaimRevision) -> str:
        if revision.revision_id in self._revisions:
            raise ValueError('Revisao duplicada')
        if revision.previous != self._latest.get(revision.claim):
            raise ValueError('Revisao anterior ausente ou desatualizada')
        for dependency in revision.dependencies:
            if dependency not in self._revisions:
                raise ValueError('Dependencia ausente')
        self._revisions[revision.revision_id] = revision
        self._latest[revision.claim] = revision.revision_id
        return revision.revision_id

    def affected_by(self, revision_id: str) -> tuple[str, ...]:
        if revision_id not in self._revisions:
            raise KeyError(revision_id)
        affected = {revision_id}
        # Append order is already topological; dependencies are immutable IDs.
        for identifier, revision in self._revisions.items():
            if revision.previous in affected or any(d in affected for d in revision.dependencies):
                affected.add(identifier)
        return tuple(sorted(affected - {revision_id}))

    def save(self, path: Path) -> None:
        """Exclusive creation preserves any existing user ledger."""
        with Path(path).open('x', encoding='utf-8') as stream:
            for revision in self.revisions:
                stream.write(canonical_json(revision.to_data()) + '\n')

    @classmethod
    def load(cls, path: Path):
        if Path(path).stat().st_size > 16*1024*1024:
            raise ValueError('Historico excede o limite')
        ledger = cls()
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            identifier = row.pop('revision_id')
            row['evidence'] = tuple(row['evidence'])
            row['dependencies'] = tuple(row['dependencies'])
            revision = ClaimRevision(**row)
            if revision.revision_id != identifier:
                raise ValueError('Hash de revisao divergente')
            ledger.append(revision)
        return ledger
