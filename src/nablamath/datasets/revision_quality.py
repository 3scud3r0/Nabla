"""Replay-bound dataset release eligibility with declared lineage and license gates.

A policy describes local release admission. It does not authenticate provenance,
license grants, publishers, independent reviewers or real-world training utility.
Scientific record verification and the existing asset quality gate are reused.
"""
from dataclasses import dataclass, asdict
from pathlib import Path

from ..core.semantic_contracts import canonical_payload, require_digest, require_text
from ..core.semantic_ir import fingerprint
from ..forge.deduplicate import semantic_fingerprint
from .quality_gate import quality_gate
from .revision_store import DatasetLedger, MAX_MEMBERS, bounded
from .revision_release import export_revision
from .semantic_leakage import LeakageAuditor, LeakageRecord


@dataclass(frozen=True)
class RevisionQualityPolicy:
    allowed_licenses: tuple[str,...]
    required_splits: tuple[str,...] = ('train','validation','test')
    minimum_records: int = 3
    minimum_families: int = 2
    maximum_declared_defects: int = 0
    allow_synthetic: bool = True

    def __post_init__(self):
        licenses=bounded(self.allowed_licenses,32,'license allowlist')
        if not licenses or len(set(licenses))!=len(licenses):
            raise ValueError('Unique nonempty license declarations required')
        for value in licenses:
            require_text(value,'declared license',limit=128)
        splits=bounded(self.required_splits,3,'required splits')
        if not splits or any(value not in ('train','validation','test') for value in splits) or len(set(splits))!=len(splits):
            raise ValueError('Unique declared train/validation/test partitions required')
        for name,maximum in [('minimum_records',MAX_MEMBERS),('minimum_families',8),
                             ('maximum_declared_defects',0)]:
            value=getattr(self,name)
            minimum=0 if name=='maximum_declared_defects' else 1
            if type(value) is not int or not minimum<=value<=maximum:
                raise ValueError('Invalid quality policy bound: '+name)
        if type(self.allow_synthetic) is not bool:
            raise ValueError('Explicit synthetic-data decision required')
        object.__setattr__(self,'allowed_licenses',tuple(sorted(licenses)))
        object.__setattr__(self,'required_splits',tuple(sorted(splits)))

    def to_data(self):
        data=asdict(self)
        data['allowed_licenses']=list(data['allowed_licenses'])
        data['required_splits']=list(data['required_splits'])
        return data

    @property
    def content_id(self):
        return fingerprint(self.to_data())


def assess_revision(ledger,*,expected_head,policy,lineage=None,asset_root=None):
    if not isinstance(ledger,DatasetLedger) or not isinstance(policy,RevisionQualityPolicy):
        raise ValueError('Typed ledger and quality policy required')
    revision,records=ledger.checkout(expected_head=expected_head)
    lineage={} if lineage is None else lineage
    if not isinstance(lineage,dict) or len(lineage)>MAX_MEMBERS:
        raise ValueError('Bounded declared lineage mapping required')
    members={record.content_id for record in records}
    if not set(lineage)<=members:
        raise ValueError('Lineage contains unknown dataset member')
    detached_lineage={}
    for key,values in lineage.items():
        parents=bounded(values,128,'declared parents')
        for parent in parents:
            require_digest(parent)
        if len(set(parents))!=len(parents) or key in parents:
            raise ValueError('Duplicate or self-referential declared lineage')
        detached_lineage[key]=tuple(sorted(parents))
    lineage=detached_lineage
    errors=[]
    families={}
    splits={name:0 for name in ('train','validation','test','unassigned')}
    licenses={}
    auditor=LeakageAuditor(max_records=MAX_MEMBERS,max_nodes=MAX_MEMBERS*8)
    for record in records:
        data=record.to_data()
        families[record.task.family]=families.get(record.task.family,0)+1
        split=data['split'];splits[split]+=1
        license_id=data['license_id'];licenses[license_id]=licenses.get(license_id,0)+1
        if license_id not in policy.allowed_licenses:
            errors.append({'code':'license_not_allowlisted','record_id':record.content_id})
        if data['synthetic'] and not policy.allow_synthetic:
            errors.append({'code':'synthetic_not_allowed','record_id':record.content_id})
        if len(data['defects'])>policy.maximum_declared_defects:
            errors.append({'code':'declared_defects_exceed_policy','record_id':record.content_id})
        if split=='unassigned':
            errors.append({'code':'unassigned_partition','record_id':record.content_id})
            continue
        parents=bounded(lineage.get(record.content_id,()),128,'declared parents')
        auditor.add(LeakageRecord(record.content_id,split,semantic_fingerprint(record.task),parents))
    if len(records)<policy.minimum_records:
        errors.append({'code':'insufficient_records'})
    if len(families)<policy.minimum_families:
        errors.append({'code':'insufficient_families'})
    for split in policy.required_splits:
        if not splits[split]:
            errors.append({'code':'missing_required_split','split':split})
    leakage=auditor.report()
    if not leakage['clean']:
        errors.append({'code':'declared_lineage_or_semantic_leakage'})
    quality=quality_gate(records,asset_root=asset_root,require_partitions=True)
    if not quality['accepted']:
        errors.append({'code':'scientific_record_or_asset_quality_gate'})
    declarations={key:sorted(bounded(value,128,'declared parents')) for key,value in sorted(lineage.items())}
    result={'schema_version':1,'revision_id':revision.content_id,'policy':policy.to_data(),
            'policy_id':policy.content_id,'lineage':declarations,'record_count':len(records),
            'families':families,'splits':splits,'licenses':licenses,'errors':errors,
            'leakage':leakage,'quality_gate':quality,'eligible_for_local_release':not errors,
            'external_training_utility_established':False,'license_grants_authenticated':False,
            'scope':'local exact replay and declared metadata policy; not scientific or legal certification'}
    canonical_payload(result)
    return {**result,'assessment_id':fingerprint(result)}


def verify_assessment(assessment,ledger,*,expected_head,policy,lineage=None,asset_root=None):
    try:
        expected=assess_revision(ledger,expected_head=expected_head,policy=policy,
                                 lineage=lineage,asset_root=asset_root)
        return canonical_payload(expected)==canonical_payload(assessment)
    except (ValueError,TypeError,KeyError,ArithmeticError,OSError):
        return False


@dataclass(frozen=True)
class ReleaseReview:
    revision_id: str
    assessment_id: str
    reviewer: str
    accepted: bool
    notes: str

    def __post_init__(self):
        require_digest(self.revision_id)
        require_digest(self.assessment_id)
        require_text(self.reviewer,'reviewer',limit=256)
        require_text(self.notes,'review correspondence')
        if type(self.accepted) is not bool:
            raise ValueError('Explicit review decision required')

    def to_data(self):
        data=asdict(self)
        data['review_identity_authenticated']=False
        return {**data,'review_id':fingerprint(data)}


def release_reviewed_revision(ledger,destination,*,expected_head,assessment,review,
                              policy,lineage=None,asset_root=None):
    if not isinstance(review,ReleaseReview):
        raise ValueError('Typed review declaration required')
    if not verify_assessment(assessment,ledger,expected_head=expected_head,policy=policy,
                             lineage=lineage,asset_root=asset_root):
        raise ValueError('Assessment failed full independent regeneration')
    if (not assessment['eligible_for_local_release'] or not review.accepted
        or review.revision_id!=expected_head or review.assessment_id!=assessment['assessment_id']):
        raise PermissionError('Affirmative exact-revision assessment review required')
    manifest=export_revision(ledger,destination,expected_head=expected_head)
    result={'manifest':manifest,'assessment':assessment,'review':review.to_data(),
            'scope':'local reviewed data-only release; no remote publication or authenticated human review'}
    return {**result,'receipt_id':fingerprint(result)}


def compare_revision_cohorts(ledger,older,newer,*,expected_head):
    old_revision,old_records=ledger.snapshot(older,expected_head=expected_head)
    new_revision,new_records=ledger.snapshot(newer,expected_head=expected_head)
    old_semantics={semantic_fingerprint(record.task) for record in old_records}
    new_semantics={semantic_fingerprint(record.task) for record in new_records}
    old_tasks={record.task.content_id for record in old_records}
    new_tasks={record.task.content_id for record in new_records}
    result={'older':old_revision.content_id,'newer':new_revision.content_id,
            'membership_diff':ledger.diff(older,newer),
            'exact_tasks_added':sorted(new_tasks-old_tasks),'exact_tasks_removed':sorted(old_tasks-new_tasks),
            'local_semantic_groups_added':sorted(new_semantics-old_semantics),
            'local_semantic_groups_removed':sorted(old_semantics-new_semantics),
            'global_novelty_established':False,'scope':'local Forge semantic quotient only'}
    return {**result,'comparison_id':fingerprint(result)}
