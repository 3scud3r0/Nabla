"""Frozen-protocol supervised linear reasoning baseline, not LLM fine tuning."""
from dataclasses import dataclass, asdict
import math
import random
from ._bounded import bounded_tuple
from ..core.semantic_ir import fingerprint


def _vector(values):
    values = bounded_tuple(values,256,label='features')
    if not values or len(values)>256 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>100 for x in values):
        raise ValueError('Bounded finite features required')
    return values


@dataclass(frozen=True)
class ReasoningProtocol:
    owner: str
    training_ids: tuple[str, ...]
    training_content_id: str
    seed: int = 0
    epochs: int = 100
    learning_rate: float = .01
    l2: float = .001

    def __post_init__(self):
        object.__setattr__(self,'training_ids',bounded_tuple(self.training_ids,10000,label='training IDs'))
        if not isinstance(self.owner,str) or not self.owner.strip() or not self.training_ids or len(set(self.training_ids))!=len(self.training_ids):
            raise ValueError('Owner and unique frozen training IDs required')
        if not isinstance(self.training_content_id,str) or len(self.training_content_id)!=64 or any(c not in '0123456789abcdef' for c in self.training_content_id):
            raise ValueError('Frozen training content digest required')
        if type(self.seed) is not int or type(self.epochs) is not int or not 1<=self.epochs<=1000:
            raise ValueError('Invalid training budget')
        if any(type(x) not in (int,float) or not math.isfinite(x) for x in (self.learning_rate,self.l2)) or not 0<self.learning_rate<=.1 or not 0<=self.l2<=1:
            raise ValueError('Invalid optimizer')

    @property
    def protocol_id(self):
        return fingerprint(asdict(self))


def freeze_protocol(rows, *, owner, **kwargs):
    rows=bounded_tuple(rows,10000,label='training rows')
    return ReasoningProtocol(owner,tuple(sorted(r['id'] for r in rows)),
                             fingerprint(sorted(rows,key=lambda row:row['id'])),**kwargs)


@dataclass(frozen=True)
class ReasoningModel:
    weights: tuple[float,...]
    bias: float
    protocol_id: str
    training_ids: tuple[str,...]
    losses: tuple[float,...]

    def predict(self, features):
        features = _vector(features)
        if len(features)!=len(self.weights):
            raise ValueError('Feature dimension mismatch')
        return self.bias + sum(a*b for a,b in zip(features,self.weights))

    @property
    def content_id(self):
        return fingerprint(asdict(self))


def fit_reasoning(rows, protocol):
    rows = bounded_tuple(rows,10000,label='training rows')
    if not isinstance(protocol,ReasoningProtocol) or not 1<=len(rows)<=10000:
        raise ValueError('Frozen bounded protocol required')
    if tuple(sorted(r['id'] for r in rows))!=tuple(sorted(protocol.training_ids)):
        raise ValueError('Training manifest mismatch')
    if fingerprint(sorted(rows,key=lambda row:row['id']))!=protocol.training_content_id:
        raise ValueError('Training content differs from preregistered snapshot')
    prepared=[]
    for row in rows:
        x=_vector(row['features']); y=row['target']
        if row['split']!='train' or type(y) not in (int,float) or not math.isfinite(y) or abs(y)>10000:
            raise ValueError('Only finite labeled training records allowed')
        prepared.append((x,y))
    dimension=len(prepared[0][0])
    if any(len(x)!=dimension for x,y in prepared):
        raise ValueError('Inconsistent dimensions')
    weights=[0.]*dimension; bias=0.; losses=[]; rng=random.Random(protocol.seed)
    for _ in range(protocol.epochs):
        rng.shuffle(prepared)
        # Batch gradient with scale normalization keeps bounded inputs stable.
        gradient=[0.]*dimension; gb=0.; loss=0.
        scale=max(1.,max(sum(v*v for v in x) for x,y in prepared))
        for x,y in prepared:
            error=bias+sum(a*b for a,b in zip(x,weights))-y
            loss+=error*error; gb+=error
            for j,value in enumerate(x): gradient[j]+=error*value
        rate=protocol.learning_rate/scale
        for j in range(dimension): weights[j]-=rate*(gradient[j]/len(rows)+protocol.l2*weights[j])
        bias-=rate*gb/len(rows)
        losses.append(loss/len(rows))
    return ReasoningModel(tuple(weights),bias,protocol.protocol_id,tuple(sorted(protocol.training_ids)),tuple(losses))
