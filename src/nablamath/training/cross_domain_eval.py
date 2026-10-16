"""Preregistered domain transfer with explicit overlap rejection and uncertainty."""
from dataclasses import dataclass
import math
from ._bounded import bounded_tuple
from .reasoning_finetune import _vector
from ..core.semantic_ir import fingerprint


@dataclass(frozen=True)
class TransferCase:
    task_id: str
    family: str
    domain: str
    features: tuple
    expected: float
    semantic_id: str

    def __post_init__(self):
        object.__setattr__(self,'features',_vector(self.features))
        if any(not isinstance(v,str) or not v.strip() for v in (self.task_id,self.family,self.domain,self.semantic_id)):
            raise ValueError('Task provenance required')
        if type(self.expected) not in (int,float) or not math.isfinite(self.expected):
            raise ValueError('Finite reference required')


def evaluate_transfer(model, cases, *, training_cases, benchmark, tolerance=1e-6, required_domains=()):
    cases,train=bounded_tuple(cases,10000,label='evaluation cases'),bounded_tuple(training_cases,10000,label='training cases')
    if any(not isinstance(c,TransferCase) for c in (*cases,*train)):
        raise ValueError('Typed transfer cases required')
    required_domains=bounded_tuple(required_domains,100,label='required domains')
    if not isinstance(benchmark,str) or not benchmark.strip() or not 1<=len(cases)<=10000 or not train:
        raise ValueError('Frozen named evaluation and training manifest required')
    if type(tolerance) not in (int,float) or not math.isfinite(tolerance) or not 0<=tolerance<=1:
        raise ValueError('Invalid tolerance')
    if len({c.task_id for c in (*cases,*train)})!=len(cases)+len(train):
        raise ValueError('Repeated task identity')
    if {c.semantic_id for c in cases}&{c.semantic_id for c in train}:
        raise ValueError('Semantic leakage')
    if {c.family for c in cases}&{c.family for c in train}:
        raise ValueError('Family leakage')
    if not set(required_domains)<={c.domain for c in cases}:
        raise ValueError('Missing preregistered domain')
    if set(getattr(model,'training_ids',()))!={c.task_id for c in train}:
        raise ValueError('Model training manifest mismatch')
    rows=[]
    for case in cases:
        try:
            value=model.predict(case.features)
            valid=type(value) in (int,float) and math.isfinite(value)
            error=abs(value-case.expected) if valid else None
            prediction=value if valid else None
        except Exception:
            prediction,error=None,None
        rows.append({'task_id':case.task_id,'semantic_id':case.semantic_id,'domain':case.domain,
                     'prediction':prediction,'expected':case.expected,'absolute_error':error,
                     'passed':error is not None and error<=tolerance})
    domains={}
    for domain in sorted({c.domain for c in cases}):
        group=[r for r in rows if r['domain']==domain]; n=len(group); k=sum(r['passed'] for r in group)
        z=1.959963984540054; center=(k/n+z*z/(2*n))/(1+z*z/n)
        half=z*math.sqrt((k/n)*(1-k/n)/n+z*z/(4*n*n))/(1+z*z/n)
        domains[domain]={'passed':k,'total':n,'accuracy':k/n,'wilson_95':[max(0,center-half),min(1,center+half)]}
    data={'benchmark':benchmark,'model_id':model.content_id,'training_ids':sorted(c.task_id for c in train),
          'tolerance':tolerance,'results':rows,'domains':domains,'passed':sum(r['passed'] for r in rows),
          'total':len(rows),'scope':'supplied frozen domain cases only; no AGI or external independence claim'}
    return {**data,'evaluation_id':fingerprint(data)}
