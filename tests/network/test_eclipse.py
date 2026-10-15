"""Deterministic anchor outage simulation, not an Internet eclipse experiment."""
import pytest
from nablamath.p2p.resilient_peers import Anchor,ResilientPeers


def test_group_loss_fails_closed_then_probes_recover():
    policy=ResilientPeers([Anchor('a'*64,'A','https://a.invalid'),
                           Anchor('b'*64,'B','https://b.invalid')],failure_limit=2,retry_seconds=10)
    assert policy.select(now=0)['ready']
    policy.observe('a'*64,success=False,now=1)
    policy.observe('a'*64,success=False,now=2)
    assert not policy.select(now=3)['ready']
    assert policy.select(now=12)['ready']
    policy.observe('a'*64,success=True,now=12)
    assert policy.select(now=13)['ready']
    with pytest.raises(ValueError,match='regressing'):
        policy.select(now=12)
