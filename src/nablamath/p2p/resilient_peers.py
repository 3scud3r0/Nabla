"""Explicitly pinned peer selection with diversity quotas and fail-closed recovery.

Diversity labels are operator declarations, not proof of independence. An eclipse
cannot be prevented when all configured trust anchors are unavailable.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Anchor:
    peer_id: str
    operator_group: str
    endpoint: str

    def __post_init__(self):
        from .peer import Peer
        Peer(self.peer_id,self.endpoint,frozenset({'objects'}))
        if type(self.operator_group) is not str or not self.operator_group.strip():
            raise ValueError('Explicit operator group required')


class ResilientPeers:
    def __init__(self,anchors,*,minimum_groups=2,failure_limit=3,retry_seconds=60):
        anchors=tuple(anchors)
        if not anchors or len(anchors)>1000 or any(not isinstance(a,Anchor) for a in anchors):
            raise ValueError('Bounded anchors required')
        if len({a.peer_id for a in anchors})!=len(anchors):
            raise ValueError('Duplicate anchor')
        for value in (minimum_groups,failure_limit,retry_seconds):
            if type(value) is not int or value<1:
                raise ValueError('Positive limits required')
        self.anchors={a.peer_id:a for a in anchors}
        self.minimum_groups=minimum_groups;self.failure_limit=failure_limit;self.retry_seconds=retry_seconds
        self.failures={};self.blocked_until={};self.last_time=-1

    def _clock(self,now):
        if type(now) is not int or now<0 or now<self.last_time:
            raise ValueError('Invalid or regressing clock')
        self.last_time=now

    def observe(self,peer_id,*,success,now):
        self._clock(now)
        if peer_id not in self.anchors or type(success) is not bool:
            raise ValueError('Unknown anchor or invalid outcome')
        self.failures[peer_id]=0 if success else self.failures.get(peer_id,0)+1
        if self.failures[peer_id]>=self.failure_limit:
            self.blocked_until[peer_id]=now+self.retry_seconds
        elif success:
            self.blocked_until.pop(peer_id,None)

    def select(self,*,now):
        self._clock(now)
        # One peer per explicitly configured group prevents quantity-based votes.
        groups={}
        for peer,anchor in sorted(self.anchors.items()):
            if self.blocked_until.get(peer,0)<=now:
                groups.setdefault(anchor.operator_group,anchor)
        if len(groups)<self.minimum_groups:
            return {'ready':False,'peers':[],'reason':'Insufficient configured diversity',
                    'sybil_resistance_established':False}
        return {'ready':True,'peers':[a.peer_id for _,a in sorted(groups.items())],
                'sybil_resistance_established':False}
