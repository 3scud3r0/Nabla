"""Scientific release admission binds exact policy, lineage, review and revision."""
from dataclasses import replace
from copy import deepcopy
from itertools import repeat

import pytest

from nablamath.core.semantic_ir import fingerprint
from nablamath.datasets.revision_store import DatasetLedger
from nablamath.datasets.revision_quality import (
    RevisionQualityPolicy,ReleaseReview,assess_revision,verify_assessment,
    release_reviewed_revision,compare_revision_cohorts,
)
from nablamath.datasets.revision_release import verify_release
from nablamath.datasets.schema import make_record
from nablamath.forge.reverse_builder import generate_task
from nablamath.forge.solvers import solve_task


def record(family,seed,split):
    task=generate_task(family,seed,2).task
    return make_record(task,solve_task(task),license_id='MIT',provenance='synthetic standalone fixture',
                       scope='bounded exact family',limitations='not empirical',split=split)


def fixture(tmp_path):
    records=[record(family,index+10,split) for index,(family,split) in enumerate([
        ('linear_system','train'),('polynomial_integral','validation'),('factored_polynomial','test')])]
    ledger=DatasetLedger(tmp_path/'ledger',dataset='family-heldout')
    revision=ledger.commit(expected_head=None,actor='curator',reason='frozen family partitions',add=records)
    policy=RevisionQualityPolicy(('MIT',))
    return ledger,revision,policy,records


def test_assessment_reuses_semantic_gate_and_local_release_review(tmp_path):
    ledger,revision,policy,records=fixture(tmp_path)
    report=assess_revision(ledger,expected_head=revision.content_id,policy=policy)
    assert report['eligible_for_local_release'] and report['leakage']['clean']
    assert report['external_training_utility_established'] is False
    assert report['license_grants_authenticated'] is False
    assert verify_assessment(report,ledger,expected_head=revision.content_id,policy=policy)
    review=ReleaseReview(revision.content_id,report['assessment_id'],'declared reviewer',True,'Metadata and exact replay checked')
    receipt=release_reviewed_revision(ledger,tmp_path/'release',expected_head=revision.content_id,
                                     assessment=report,review=review,policy=policy)
    assert receipt['review']['review_identity_authenticated'] is False
    assert verify_release(tmp_path/'release',expected_revision=revision.content_id)==receipt['manifest']


def test_declared_unknown_common_ancestor_crosses_partitions(tmp_path):
    ledger,revision,policy,records=fixture(tmp_path)
    ancestor=fingerprint({'unknown':'shared source'})
    lineage={records[0].content_id:[ancestor],records[2].content_id:[ancestor]}
    report=assess_revision(ledger,expected_head=revision.content_id,policy=policy,lineage=lineage)
    assert not report['eligible_for_local_release'] and not report['leakage']['clean']
    assert any(error['code']=='declared_lineage_or_semantic_leakage' for error in report['errors'])


def test_one_shot_lineage_generators_are_snapshotted_once(tmp_path):
    ledger,revision,policy,records=fixture(tmp_path)
    ancestor='b'*64
    lineage={records[0].content_id:(value for value in [ancestor])}
    report=assess_revision(ledger,expected_head=revision.content_id,policy=policy,lineage=lineage)
    assert report['lineage']=={records[0].content_id:[ancestor]}
    assert verify_assessment(report,ledger,expected_head=revision.content_id,policy=policy,
                             lineage={records[0].content_id:[ancestor]})


def test_policy_change_or_rehashed_success_does_not_release(tmp_path):
    ledger,revision,policy,records=fixture(tmp_path)
    report=assess_revision(ledger,expected_head=revision.content_id,policy=policy)
    review=ReleaseReview(revision.content_id,report['assessment_id'],'reviewer',True,'fixture review')
    for modified in (replace(policy,allowed_licenses=('CC0-1.0',)),replace(policy,allow_synthetic=False)):
        assert not verify_assessment(report,ledger,expected_head=revision.content_id,policy=modified)
        with pytest.raises(ValueError):
            release_reviewed_revision(ledger,tmp_path/'out',expected_head=revision.content_id,
                assessment=report,review=review,policy=modified)
    assert not (tmp_path/'out').exists()


def test_rejected_review_and_stale_revision_fail_without_output(tmp_path):
    ledger,revision,policy,records=fixture(tmp_path)
    report=assess_revision(ledger,expected_head=revision.content_id,policy=policy)
    review=ReleaseReview(revision.content_id,report['assessment_id'],'r',False,'rejected')
    with pytest.raises(PermissionError):
        release_reviewed_revision(ledger,tmp_path/'out',expected_head=revision.content_id,
                                  assessment=report,review=review,policy=policy)
    second=ledger.commit(expected_head=revision.content_id,actor='curator',reason='remove test',remove=[records[2].content_id])
    assert not verify_assessment(report,ledger,expected_head=revision.content_id,policy=policy)
    diff=compare_revision_cohorts(ledger,revision.content_id,second.content_id,expected_head=second.content_id)
    assert diff['exact_tasks_removed']==[records[2].task.content_id]
    assert len(diff['local_semantic_groups_removed'])==1 and not diff['global_novelty_established']


def test_missing_split_family_duplicates_and_license_failures_remain_negative(tmp_path):
    ledger,revision,policy,records=fixture(tmp_path)
    # Copying a task into another split changes record identity but does not
    # evade independently recomputed exact/semantic/family leakage detection.
    duplicate=records[0].with_split('test')
    second=ledger.commit(expected_head=revision.content_id,actor='curator',reason='bad split',add=[duplicate])
    report=assess_revision(ledger,expected_head=second.content_id,policy=policy)
    assert not report['eligible_for_local_release']
    forged=deepcopy(report);forged['eligible_for_local_release']=True;forged['errors']=[]
    forged['assessment_id']=fingerprint({key:value for key,value in forged.items() if key!='assessment_id'})
    assert not verify_assessment(forged,ledger,expected_head=second.content_id,policy=policy)


@pytest.mark.parametrize('kwargs',[{'allowed_licenses':()}, {'allowed_licenses':('MIT','MIT')},
 {'allowed_licenses':('MIT',),'minimum_records':True}, {'allowed_licenses':('MIT',),'minimum_families':9},
 {'allowed_licenses':('MIT',),'maximum_declared_defects':1}, {'allowed_licenses':('MIT',),'allow_synthetic':1},
 {'allowed_licenses':('MIT',),'required_splits':('unknown',)}])
def test_policy_refuses_ambiguous_or_ineffective_settings(kwargs):
    with pytest.raises(ValueError):RevisionQualityPolicy(**kwargs)


def test_lineage_unknown_self_duplicate_or_unbounded_parent_sets_refused(tmp_path):
    ledger,revision,policy,records=fixture(tmp_path)
    for lineage in ({'0'*64:[]},{records[0].content_id:[records[0].content_id]},
                    {records[0].content_id:['a'*64,'a'*64]}, {records[0].content_id:repeat('a'*64)}):
        with pytest.raises(ValueError):
            assess_revision(ledger,expected_head=revision.content_id,policy=policy,lineage=lineage)
