"""Append-only local review declarations, conflict checks and nonbinding decisions."""
from dataclasses import dataclass,asdict
from ..core.semantic_ir import fingerprint


@dataclass(frozen=True)
class Reviewer:
    reviewer_id: str
    domains: tuple[str,...]
    conflicts_with: tuple[str,...] = ()

    def __post_init__(self):
        object.__setattr__(self,'domains',tuple(self.domains));object.__setattr__(self,'conflicts_with',tuple(self.conflicts_with))
        if not self.reviewer_id.strip() or not self.domains or any(not d.strip() for d in self.domains):
            raise ValueError('Identidade e especialidades declaradas obrigatórias')


@dataclass(frozen=True)
class Review:
    revision_id: str
    reviewer_id: str
    domain: str
    decision: str
    rationale: str
    evidence: tuple[str,...]
    previous: str | None = None

    def __post_init__(self):
        object.__setattr__(self,'evidence',tuple(self.evidence))
        if self.decision not in {'accept','reject','revise'} or not self.rationale.strip() or not self.evidence:
            raise ValueError('Revisão requer decisão, justificativa e evidências')

    @property
    def review_id(self):
        return fingerprint(asdict(self))

    def to_data(self):return {**asdict(self),'review_id':self.review_id}


class ReviewBoard:
    def __init__(self,reviewers,*,authors):
        reviewers=tuple(reviewers);self.reviewers={r.reviewer_id:r for r in reviewers}
        if len(self.reviewers)!=len(reviewers):raise ValueError('Revisor duplicado')
        self.authors={key:tuple(value) for key,value in authors.items()};self._reviews=[];self._latest={}

    def submit(self,review,ledger):
        ledger.get(review.revision_id)
        known={key for revision in ledger.revisions for key in revision.evidence}
        if not set(review.evidence)<=known:raise ValueError('Evidência de revisão ausente do histórico')
        reviewer=self.reviewers[review.reviewer_id];authors=self.authors.get(review.revision_id)
        if not authors or reviewer.reviewer_id in authors or set(authors)&set(reviewer.conflicts_with):
            raise ValueError('Autoria não declarada, autorrevisão ou conflito conhecido')
        if review.domain not in reviewer.domains:
            raise ValueError('Especialidade não declarada')
        key=(review.revision_id,review.reviewer_id)
        if review.previous!=self._latest.get(key):raise ValueError('Histórico de revisão divergente')
        self._reviews.append(review);self._latest[key]=review.review_id
        return review.review_id

    def decision(self,revision_id,*,minimum=2):
        if type(minimum) is not int or not 2<=minimum<=100:raise ValueError('Pelo menos dois revisores requeridos')
        current=[r for r in self._reviews if r.revision_id==revision_id and self._latest[(r.revision_id,r.reviewer_id)]==r.review_id]
        accepted=sum(r.decision=='accept' for r in current)
        return {'revision_id':revision_id,'accepts':accepted,'reviewers':len(current),
                'recommended':accepted>=minimum and all(r.decision=='accept' for r in current),
                'reviews':[r.to_data() for r in current],'claim_status_changed':False,
                'identity_and_expertise_independently_authenticated':False}
