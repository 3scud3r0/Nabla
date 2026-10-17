"""Signed claim events with exact counterexample replay and author-only withdrawal."""
import json
from ..core.semantic_ir import canonical_json, rational
from ..formal.statement import FormalStatement
from .crypto_registry import sign


def claim_event(statement, private_key, *, signer):
    if not isinstance(statement,FormalStatement):
        raise TypeError('Structured FormalStatement required')
    return sign({'kind':'claim','statement':statement.to_data()},private_key,signer=signer)


def refutation_event(claim_id, witness, private_key, *, signer):
    return sign({'kind':'refutation','claim_id':claim_id,'witness':witness},private_key,signer=signer)


def withdrawal_event(claim_id, reason, private_key, *, signer):
    return sign({'kind':'withdrawal','claim_id':claim_id,'reason':reason},private_key,signer=signer)


class ClaimRegistry:
    def __init__(self, trust):
        self.trust, self._events, self._claims = trust, {}, {}

    def append(self, envelope):
        if not self.trust.verify(envelope):
            raise ValueError('Untrusted or invalid claim signature')
        event = json.loads(canonical_json(envelope))
        identifier, payload = event['content_id'],event['payload']
        if identifier in self._events or len(self._events) >= 10000:
            raise ValueError('Duplicate event or registry budget exhausted')
        kind = payload.get('kind')
        if kind == 'claim' and set(payload) == {'kind','statement'}:
            statement = FormalStatement.from_data(payload['statement'])
            self._claims[identifier] = {'statement':statement,'author':event['signer'],
                                         'refutations':[],'withdrawals':[]}
        elif kind in {'refutation','withdrawal'}:
            expected = {'kind','claim_id','witness' if kind == 'refutation' else 'reason'}
            if set(payload) != expected or payload['claim_id'] not in self._claims:
                raise ValueError('Unknown claim or invalid event fields')
            claim = self._claims[payload['claim_id']]
            if kind == 'withdrawal':
                if event['signer'] != claim['author'] or not isinstance(payload['reason'],str) or not payload['reason'].strip():
                    raise ValueError('Only the claim author can withdraw with a reason')
                claim['withdrawals'].append(identifier)
            else:
                statement = claim['statement']
                witness = payload['witness']
                if not isinstance(witness,dict) or set(witness) != set(statement.variables):
                    raise ValueError('Counterexample must assign every declared variable')
                values = {k:rational(v) for k,v in witness.items()}
                if not all(p.evaluate(values) for p in statement.hypotheses) or statement.goal.evaluate(values):
                    raise ValueError('Witness does not refute the exact statement under its hypotheses')
                claim['refutations'].append(identifier)
        else:
            raise ValueError('Unknown claim event')
        self._events[identifier] = event
        return identifier

    def status(self, claim_id):
        claim = self._claims[claim_id]
        dependencies = [claim_id,*claim['refutations'],*claim['withdrawals']]
        trusted = all(self.trust.verify(self._events[i]) for i in dependencies)
        return {'claim_id':claim_id,'status':('withdrawn' if claim['withdrawals'] else
                'refuted' if claim['refutations'] else 'proposed'),
                'refutations':list(claim['refutations']),'withdrawals':list(claim['withdrawals']),
                'signatures_currently_trusted':trusted,'formal_proof':False}

    def to_data(self):
        return {'schema_version':1,'events':json.loads(canonical_json(list(self._events.values())))}

    @classmethod
    def from_data(cls, data, trust):
        if not isinstance(data,dict) or set(data) != {'schema_version','events'} or data['schema_version'] != 1 or not isinstance(data['events'],list):
            raise ValueError('Invalid claims registry')
        registry = cls(trust)
        for event in data['events']:
            registry.append(event)
        return registry
