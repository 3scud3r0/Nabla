"""Transactional scientific dataset revision/release failures are independently replayed."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from itertools import repeat
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from nablamath.core.semantic_contracts import canonical_payload
from nablamath.core.semantic_ir import fingerprint
from nablamath.datasets.schema import make_record, ScientificRecord
from nablamath.datasets.revision_store import DatasetLedger, DatasetRevision
from nablamath.datasets.revision_release import export_revision, verify_release
from nablamath.forge.reverse_builder import generate_task
from nablamath.forge.solvers import solve_task


def record(seed=1,split='train'):
    task=generate_task('linear_system',seed,2).task
    return make_record(task,solve_task(task),license_id='MIT',provenance='synthetic local seed '+str(seed),
                       scope='exact linear task',limitations='not empirical science',split=split)


def commit(ledger,head=None,add=(),remove=(),reason='revision test'):
    return ledger.commit(expected_head=head,actor='declared curator',reason=reason,add=add,remove=remove)


def test_revision_lifecycle_historical_snapshots_and_membership_diff(tmp_path):
    ledger=DatasetLedger(tmp_path/'data.sqlite3',dataset='curated-linear-v1')
    a,b,c=record(1),record(2),record(3)
    first=commit(ledger,add=[a,b])
    second=commit(ledger,first.content_id,add=[c],remove=[a.content_id])
    assert ledger.head==second.content_id
    selected,records=ledger.checkout(expected_head=second.content_id)
    assert selected==second and {r.content_id for r in records}=={b.content_id,c.content_id}
    old,records=ledger.snapshot(first.content_id,expected_head=second.content_id)
    assert old==first and {r.content_id for r in records}=={a.content_id,b.content_id}
    assert ledger.history(expected_head=second.content_id)==(first,second)
    diff=ledger.diff(first.content_id,second.content_id)
    assert diff['added']==[c.content_id] and diff['removed']==[a.content_id] and diff['unchanged']==1
    with pytest.raises(ValueError,match='pinned'):
        ledger.checkout(expected_head=first.content_id)


def test_reopen_database_preserves_dataset_binding_and_records(tmp_path):
    path=tmp_path/'ledger'
    ledger=DatasetLedger(path,dataset='one')
    revision=commit(ledger,add=[record()])
    restored=DatasetLedger(path,dataset='one')
    assert restored.checkout(expected_head=revision.content_id)==ledger.checkout(expected_head=revision.content_id)
    with pytest.raises(ValueError,match='another dataset'):
        DatasetLedger(path,dataset='two')


def test_cas_concurrent_admission_and_failure_atomicity(tmp_path):
    path=tmp_path/'concurrent'
    first=commit(DatasetLedger(path,dataset='study'),add=[record(1)])
    def attempt(seed):
        ledger=DatasetLedger(path,dataset='study')
        try:
            return commit(ledger,first.content_id,add=[record(seed)]).content_id
        except ValueError as error:
            assert 'Stale' in str(error)
            return None
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(attempt,range(10,14)))
    assert sum(value is not None for value in results)==1
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT count(*) FROM records').fetchone()[0]==2
        assert db.execute('SELECT count(*) FROM revisions').fetchone()[0]==2


@pytest.mark.parametrize('kind',['existing-add','unknown-remove','duplicate-add','duplicate-remove','empty','overlap'])
def test_invalid_transitions_never_leave_partial_records(tmp_path,kind):
    ledger=DatasetLedger(tmp_path/'data',dataset='strict')
    a,b=record(1),record(2)
    first=commit(ledger,add=[a])
    add,remove=([b],[])
    if kind=='existing-add':add=[a]
    elif kind=='unknown-remove':remove=['f'*64]
    elif kind=='duplicate-add':add=[b,b]
    elif kind=='duplicate-remove':remove=[a.content_id,a.content_id]
    elif kind=='empty':add=[]
    else:remove=[b.content_id]
    with pytest.raises(ValueError):
        commit(ledger,first.content_id,add=add,remove=remove)
    assert ledger.head==first.content_id
    assert len(ledger.checkout(expected_head=first.content_id)[1])==1
    with sqlite3.connect(ledger.path) as db:
        assert db.execute('SELECT count(*) FROM records').fetchone()[0]==1


def test_empty_dataset_revision_and_readd_archived_record(tmp_path):
    ledger=DatasetLedger(tmp_path/'data',dataset='empty-explicit')
    value=record()
    first=commit(ledger,add=[value])
    empty=commit(ledger,first.content_id,remove=[value.content_id])
    assert ledger.checkout(expected_head=empty.content_id)[1]==()
    restored=commit(ledger,empty.content_id,add=[value])
    assert ledger.checkout(expected_head=restored.content_id)[1]==(value,)


def test_bounded_generator_and_actor_validation(tmp_path):
    ledger=DatasetLedger(tmp_path/'data',dataset='bound')
    with pytest.raises(ValueError,match='budget'):
        commit(ledger,add=repeat(record()))
    for actor in ('',False,None,'x'*257):
        with pytest.raises(ValueError):
            ledger.commit(expected_head=None,actor=actor,reason='reason',add=[record()])
    assert ledger.head is None


def test_corrupted_record_or_missing_parent_fails_closed(tmp_path):
    ledger=DatasetLedger(tmp_path/'data',dataset='corruption')
    value=record()
    first=commit(ledger,add=[value])
    second=commit(ledger,first.content_id,add=[record(2)])
    with sqlite3.connect(ledger.path) as db:
        original=db.execute('SELECT payload FROM records WHERE id=?',(value.content_id,)).fetchone()[0]
        data=json.loads(original);data['license_id']='changed-license'
        db.execute('UPDATE records SET payload=? WHERE id=?',(canonical_payload(data),value.content_id))
    with pytest.raises(ValueError,match='commitment'):
        ledger.checkout(expected_head=second.content_id)
    with sqlite3.connect(ledger.path) as db:
        db.execute('UPDATE records SET payload=? WHERE id=?',(original,value.content_id))
        db.execute('UPDATE revisions SET parent=? WHERE id=?',('e'*64,second.content_id))
    with pytest.raises(ValueError,match='parent column'):
        ledger.history(expected_head=second.content_id)


def test_retained_record_corruption_blocks_commit_and_rolls_back(tmp_path):
    ledger=DatasetLedger(tmp_path/'data',dataset='admission')
    first_record=record(1)
    first=commit(ledger,add=[first_record])
    with sqlite3.connect(ledger.path) as db:
        db.execute('UPDATE records SET payload=? WHERE id=?',('{}',first_record.content_id))
    with pytest.raises(ValueError):
        commit(ledger,first.content_id,add=[record(2)])
    assert ledger.head==first.content_id
    with sqlite3.connect(ledger.path) as db:
        assert db.execute('SELECT count(*) FROM records').fetchone()[0]==1


def test_revision_refuses_rehashed_membership_changes_and_boolean_sequence():
    value=record()
    data={'schema_version':1,'dataset':'example','parent':None,'actor':'a','reason':'r',
          'added':[value.content_id],'removed':[],'members':[value.content_id],'sequence':1}
    revision=DatasetRevision(canonical_payload(data))
    assert revision.transition(None)
    for field,change in [('sequence',True),('schema_version',True),('members',[]),('added',[]),
                         ('parent','a'*64),('members',[value.content_id,value.content_id])]:
        invalid={**data,field:change}
        with pytest.raises(ValueError):
            DatasetRevision(canonical_payload(invalid))


def test_release_exact_replay_and_previous_snapshot_export(tmp_path):
    ledger=DatasetLedger(tmp_path/'data',dataset='release')
    a,b=record(1),record(2)
    first=commit(ledger,add=[a]);second=commit(ledger,first.content_id,add=[b])
    destination=tmp_path/'public'
    manifest=export_revision(ledger,destination,expected_head=second.content_id,revision_id=first.content_id)
    assert manifest['record_ids']==[a.content_id]
    assert verify_release(destination,expected_revision=first.content_id,
                          expected_release=manifest['release_id'])==manifest
    with pytest.raises(FileExistsError):
        export_revision(ledger,destination,expected_head=second.content_id)
    assert not list(tmp_path.glob('.nabla-release-*'))


def test_release_preserves_existing_empty_destination(tmp_path):
    ledger=DatasetLedger(tmp_path/'data',dataset='preserve')
    revision=commit(ledger,add=[record()])
    destination=tmp_path/'user-folder';destination.mkdir()
    with pytest.raises(FileExistsError):
        export_revision(ledger,destination,expected_head=revision.content_id)
    assert destination.is_dir() and list(destination.iterdir())==[]


@pytest.mark.parametrize('change',['bytes','extra','manifest-hash','record-id','scope','truncation'])
def test_release_corruption_rejected(tmp_path,change):
    ledger=DatasetLedger(tmp_path/'data',dataset='negative-release')
    revision=commit(ledger,add=[record()])
    destination=tmp_path/'out'
    export_revision(ledger,destination,expected_head=revision.content_id)
    content=destination/'content'
    if change=='bytes':
        with (content/'records.jsonl').open('ab') as stream:stream.write(b'bad')
    elif change=='extra':(content/'extra').write_text('unexpected')
    elif change=='truncation':(content/'records.jsonl').write_bytes(b'')
    else:
        path=content/'manifest.json';data=json.loads(path.read_text())
        if change=='manifest-hash':data['release_id']='0'*64
        elif change=='record-id':data['record_ids']=['0'*64]
        else:data['scope']='externally authenticated scientific corpus'
        path.write_text(canonical_payload(data))
    with pytest.raises(ValueError):
        verify_release(destination,expected_revision=revision.content_id)


def test_semantically_invalid_release_is_rejected_after_all_hashes_recomputed(tmp_path):
    ledger=DatasetLedger(tmp_path/'data',dataset='forged')
    revision=commit(ledger,add=[record()]);destination=tmp_path/'out'
    export_revision(ledger,destination,expected_head=revision.content_id)
    root=destination/'content';path=root/'records.jsonl'
    value=json.loads(path.read_text());value['trace']['verification']['valid']=False
    raw=(canonical_payload(value)+'\n').encode();path.write_bytes(raw)
    manifest=json.loads((root/'manifest.json').read_text())
    manifest['records_sha256']=hashlib.sha256(raw).hexdigest();manifest['records_bytes']=len(raw)
    manifest['release_id']=fingerprint({k:v for k,v in manifest.items() if k!='release_id'})
    (root/'manifest.json').write_text(canonical_payload(manifest))
    with pytest.raises(ValueError):
        verify_release(destination,expected_revision=revision.content_id)


def test_release_symlink_files_and_wrapper_refused(tmp_path):
    ledger=DatasetLedger(tmp_path/'data',dataset='symlink')
    revision=commit(ledger,add=[record()]);destination=tmp_path/'out'
    export_revision(ledger,destination,expected_head=revision.content_id)
    path=destination/'content/records.jsonl';copy=tmp_path/'copy'
    copy.write_bytes(path.read_bytes());path.unlink()
    try:path.symlink_to(copy)
    except OSError:pytest.skip('OS cannot create test symlink')
    with pytest.raises(ValueError,match='Regular'):
        verify_release(destination,expected_revision=revision.content_id)


def test_aggregate_snapshot_budget_checked_before_materializing_records(tmp_path,monkeypatch):
    import nablamath.datasets.revision_store as store
    ledger=DatasetLedger(tmp_path/'data',dataset='aggregate-budget')
    a,b=record(1),record(2)
    first=commit(ledger,add=[a])
    monkeypatch.setattr(store,'MAX_SNAPSHOT_BYTES',len(a.payload_json.encode())+len(b.payload_json.encode())-1)
    with pytest.raises(ValueError,match='aggregate'):
        commit(ledger,first.content_id,add=[b])
    assert ledger.head==first.content_id
    with sqlite3.connect(ledger.path) as db:
        assert db.execute('SELECT count(*) FROM records').fetchone()[0]==1
    monkeypatch.setattr(store,'MAX_SNAPSHOT_BYTES',1)
    monkeypatch.setattr(ledger,'_load_record',lambda *args:pytest.fail('Payload loaded before aggregate preflight'))
    with pytest.raises(ValueError,match='aggregate'):
        ledger.checkout(expected_head=first.content_id)


def test_incoming_byte_budget_leaves_no_partial_revision(tmp_path,monkeypatch):
    import nablamath.datasets.revision_store as store
    ledger=DatasetLedger(tmp_path/'data',dataset='incoming-budget')
    value=record()
    monkeypatch.setattr(store,'MAX_SNAPSHOT_BYTES',len(value.payload_json.encode())-1)
    with pytest.raises(ValueError,match='aggregate'):
        commit(ledger,add=[value])
    assert ledger.head is None
    with sqlite3.connect(ledger.path) as db:
        assert db.execute('SELECT count(*) FROM records').fetchone()[0]==0


def test_corrupt_record_wrong_nested_type_normalizes_validation_error(tmp_path):
    ledger=DatasetLedger(tmp_path/'data',dataset='wrong-type')
    value=record();revision=commit(ledger,add=[value])
    damaged=value.to_data();damaged['trace']=[]
    with sqlite3.connect(ledger.path) as db:
        db.execute('UPDATE records SET payload=? WHERE id=?',(canonical_payload(damaged),value.content_id))
    with pytest.raises(ValueError):
        ledger.checkout(expected_head=revision.content_id)


def test_read_only_open_never_repairs_or_mutates_database(tmp_path):
    ledger=DatasetLedger(tmp_path/'read only.sqlite3',dataset='readonly')
    revision=commit(ledger,add=[record()])
    before=ledger.path.read_bytes()
    readonly=DatasetLedger.open_read_only(ledger.path,dataset='readonly')
    assert readonly.checkout(expected_head=revision.content_id)==ledger.checkout(expected_head=revision.content_id)
    assert ledger.path.read_bytes()==before
    with pytest.raises(PermissionError):commit(readonly,revision.content_id,add=[record(2)])
    assert ledger.path.read_bytes()==before
    missing=tmp_path/'missing.sqlite3'
    with pytest.raises(ValueError):DatasetLedger.open_read_only(missing,dataset='readonly')
    assert not missing.exists()
