"""Append-only hash-linked policy events, including rejected evaluations and rollback."""
from ..core.semantic_ir import fingerprint


class Lineage:
    def __init__(self,events=()):
        self._events=[]
        for event in events:
            payload={k:v for k,v in event.items() if k!='event_id'}
            if event['event_id']!=fingerprint(payload) or payload['previous']!=self.head:
                raise ValueError('Cadeia de linhagem inválida')
            self._events.append(dict(event))

    @property
    def head(self):
        return self._events[-1]['event_id'] if self._events else None

    @property
    def events(self):
        import copy
        return tuple(copy.deepcopy(self._events))

    def append(self,*,action,genome_id,receipt_id=None):
        if action not in {'baseline','accepted','rejected','rollback'}:
            raise ValueError('Ação de linhagem inválida')
        payload={'action':action,'genome_id':genome_id,'receipt_id':receipt_id,'previous':self.head}
        event={**payload,'event_id':fingerprint(payload)}
        self._events.append(event)
        return event['event_id']
