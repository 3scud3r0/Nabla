"""External-review conformance, without fabricating independent replication."""
import pytest
from nablamath.discovery.literature_search import record_literature_review
from nablamath.core.semantic_ir import fingerprint
from nablamath.discovery.independent_replication import record_replication
from nablamath.knowledge.replication_protocol import ReplicationProtocol


def test_external_review_cannot_be_inferred_from_empty_search():
    payload={'query':'unknown','sources':[],'live_network_used':False,'global_novelty_established':False,'external_source_authentication':False}
    search={**payload,'search_id':fingerprint(payload)}
    with pytest.raises(ValueError):record_literature_review(search,reviewer='reviewer',author='author',consulted_citation_keys=[],false_positive_keys=[],conclusion='antecedent_found')
    result=record_literature_review(search,reviewer='reviewer',author='author',consulted_citation_keys=[],false_positive_keys=[],conclusion='no_match_in_supplied_sources')
    assert not result['identity_authenticated']
    assert not result['global_novelty_established']


def test_missing_external_replication_protocol_fails_closed():
    with pytest.raises(ValueError):record_replication(None,replicator='r',affiliations=['lab'],conflicts=[],measured=1,evidence={},source_evidence={})


def test_replication_preserves_negative_result_and_declared_identity_limits():
    artifact={'experiment':'bounded reference fixture','measurement':2.0}
    key=fingerprint(artifact)
    protocol=ReplicationProtocol('claim-v1','owner',('original-author',),'error',0.,.1,(key,),'Replay fixture, compare declared error')
    result=record_replication(protocol,replicator='declared-external-reviewer',affiliations=['declared independent lab'],
          conflicts=[],measured=2.,evidence={key:artifact},source_evidence={key:artifact})
    assert result['outcome']=='negative_result'
    assert not result['external_identity_verified']
    assert not result['claim_status_changed']
    with pytest.raises(ValueError):
        record_replication(protocol,replicator='original-author',affiliations=['lab'],conflicts=[],
                           measured=0.,evidence={key:artifact},source_evidence={key:artifact})
