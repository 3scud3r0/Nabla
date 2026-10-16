"""Cross-module artifacts are regenerated, not accepted on rehashed flags alone."""
import hashlib
import json
from pathlib import Path

import pytest

from nablamath.core.semantic_contracts import canonical_payload
from nablamath.core.semantic_ir import fingerprint
from nablamath.pipeline.delivery_cycle import run_delivery_cycle,verify_delivery_cycle


@pytest.fixture
def cycle(tmp_path):
    root=tmp_path/'cycle'
    summary=run_delivery_cycle(root,seed=987012,train_count=4,validation_count=2,test_count=3)
    return root,summary


def rehash(root):
    path=root/'manifest.json';data=json.loads(path.read_text())
    for name in data['files']:
        data['files'][name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
    data['run_id']=fingerprint({key:value for key,value in data.items() if key!='run_id'})
    path.write_text(canonical_payload(data)+'\n')
    return data['run_id']


def test_end_to_end_exact_training_revision_release_model_algebra_and_conservation(cycle):
    root,result=cycle
    before={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
    for _ in range(3):
        assert verify_delivery_cycle(root,expected_run_id=result['run_id'])
        assert {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}==before
    assert result['primary_correct']==3 and result['test_tasks']==3
    assert result['ablation_correct']<result['primary_correct']
    assert result['root_certificate_verified']
    assert result['water_max_conservation_residual']<1e-12
    assert result['original_reserved48_used'] is False
    assert result['fully_calibrated_and_ready'] is False
    assert (root/'training-release/content/records.jsonl').is_file()
    with pytest.raises(FileExistsError):run_delivery_cycle(root)


@pytest.mark.parametrize('artifact,field,value',[
 ('summary.json','fully_calibrated_and_ready',True),
 ('summary.json','primary_correct',999),
 ('learning.json','scope','general intelligence established'),
 ('selection.json','test_observed',True),
 ('water.json','experimental_validation',True),
 ('assessment.json','license_grants_authenticated',True),
 ('release-receipt.json','scope','externally approved release'),
])
def test_rehashed_false_assurance_claims_fail_semantic_replay(cycle,artifact,field,value):
    root,original=cycle
    path=root/artifact;data=json.loads(path.read_text());data[field]=value
    path.write_text(canonical_payload(data))
    new_id=rehash(root)
    assert not verify_delivery_cycle(root,expected_run_id=original['run_id'])
    assert not verify_delivery_cycle(root,expected_run_id=new_id)


def test_extra_nested_manifest_cannot_hide_from_inventory(cycle):
    root,result=cycle
    extra=root/'unexpected/manifest.json';extra.parent.mkdir();extra.write_text('{}')
    assert not verify_delivery_cycle(root,expected_run_id=result['run_id'])


def test_protocol_cannot_be_edited_after_selection_without_regeneration(cycle):
    root,_=cycle
    path=root/'protocol.json';data=json.loads(path.read_text());data['seed']+=1
    path.write_text(canonical_payload(data))
    assert not verify_delivery_cycle(root,expected_run_id=rehash(root))


def test_missing_database_fails_without_creating_fake_evidence(cycle):
    root,result=cycle
    db=root/'datasets.sqlite3';db.unlink()
    assert not verify_delivery_cycle(root,expected_run_id=result['run_id'])
    assert not db.exists()


def test_corrupted_sqlite_is_false_even_after_file_digest_recomputed(cycle):
    root,_=cycle
    (root/'datasets.sqlite3').write_bytes(b'not a SQLite database')
    assert not verify_delivery_cycle(root,expected_run_id=rehash(root))


@pytest.mark.parametrize('kwargs',[{'seed':True},{'seed':-1},{'train_count':1},
 {'validation_count':9},{'test_count':25},{'test_count':False}])
def test_budget_refusals_precede_output_creation(tmp_path,kwargs):
    root=tmp_path/'invalid'
    with pytest.raises(ValueError):run_delivery_cycle(root,**kwargs)
    assert not root.exists()
