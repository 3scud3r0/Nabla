"""Exact interval propagation and lineage jackknife diagnostics for symbolic fits.

Intervals enclose predictions over declared input boxes by rational arithmetic.
They are not calibrated probability intervals, formal Lean certificates, or
claims about an unobserved scientific data distribution. Dependency between
repeated variables can widen an enclosure without making it unsound.
"""
from dataclasses import dataclass
from fractions import Fraction
from ..core.semantic_ir import fingerprint
from ._bounded import bounded_tuple
from .symbolic_beam import (Term,SymbolicModel,SearchBudget,search,validate_samples,
                           sample_digest,score_model,_number,load_model)
from .sparse_symbolic import SparseModel


@dataclass(frozen=True)
class Interval:
    lower: Fraction
    upper: Fraction

    def __post_init__(self):
        object.__setattr__(self,'lower',_number(self.lower));object.__setattr__(self,'upper',_number(self.upper))
        if self.lower>self.upper:raise ValueError('Interval endpoints out of order')

    def to_data(self):return [str(self.lower),str(self.upper)]

    def add(self,other):return Interval(_number(self.lower+other.lower),_number(self.upper+other.upper))

    def negate(self):return Interval(-self.upper,-self.lower)

    def multiply(self,other):
        products=[_number(a*b) for a in (self.lower,self.upper) for b in (other.lower,other.upper)]
        return Interval(min(products),max(products))

    def reciprocal(self):
        if self.lower<=0<=self.upper:raise ValueError('Input box crosses reciprocal singularity')
        values=(_number(1/self.lower),_number(1/self.upper))
        return Interval(min(values),max(values))

    def contains(self,value):return self.lower<=_number(value)<=self.upper


def term_interval(term,boxes):
    if not isinstance(term,Term):raise ValueError('Typed grammar term required')
    boxes=bounded_tuple(boxes,8,label='feature intervals')
    if not boxes or any(not isinstance(b,Interval) for b in boxes):raise ValueError('Typed nonempty feature box required')
    if term.operation=='one':return Interval(1,1)
    if term.operation=='variable':
        if term.variable>=len(boxes):raise ValueError('Feature box dimension mismatch')
        return boxes[term.variable]
    values=[term_interval(a,boxes) for a in term.arguments]
    if term.operation=='negate':return values[0].negate()
    if term.operation=='reciprocal':return values[0].reciprocal()
    if term.operation=='add':return values[0].add(values[1])
    return values[0].multiply(values[1])


def predict_interval(model,boxes):
    boxes=bounded_tuple(boxes,8,label='feature intervals')
    if isinstance(model,SymbolicModel):
        return term_interval(model.term,boxes).multiply(Interval(model.slope,model.slope)).add(Interval(model.intercept,model.intercept))
    if isinstance(model,SparseModel):
        result=Interval(model.intercept,model.intercept)
        for term,weight in zip(model.terms,model.weights):
            result=result.add(term_interval(term,boxes).multiply(Interval(weight,weight)))
        return result
    raise ValueError('Known declarative symbolic model required')


def sensitivity_report(model,points,*,radii):
    """Enclose predictions under declared absolute feature perturbations."""
    if not isinstance(model,(SymbolicModel,SparseModel)):raise ValueError('Known declarative symbolic model required')
    points=bounded_tuple(points,128,label='sensitivity points')
    radii=tuple(_number(r) for r in bounded_tuple(radii,8,label='feature radii'))
    if not radii or any(r<0 for r in radii) or not points:raise ValueError('Nonnegative radii and bounded points required')
    prepared=[]
    for point in points:
        values=tuple(_number(x) for x in bounded_tuple(point,8,label='point features'))
        if len(values)!=len(radii):raise ValueError('Sensitivity dimension mismatch')
        prepared.append(values)
    if len(set(prepared))!=len(prepared):raise ValueError('Duplicate sensitivity point')
    rows=[]
    for point in prepared:
        box=tuple(Interval(x-r,x+r) for x,r in zip(point,radii))
        try:
            nominal=model.predict(point); interval=predict_interval(model,box)
            row={'point':[str(x) for x in point],'nominal':str(nominal),'enclosure':interval.to_data(),
                 'max_absolute_deviation':str(max(abs(interval.lower-nominal),abs(interval.upper-nominal))),
                 'status':'enclosed'}
        except ValueError as exc:
            row={'point':[str(x) for x in point],'nominal':None,'enclosure':None,
                 'max_absolute_deviation':None,'status':'domain_or_arithmetic_failure','reason':str(exc)}
        rows.append(row)
    data={'version':'symbolic-box-sensitivity-v1','model_id':model.content_id,'radii':[str(r) for r in radii],
          'points':rows,'failures':sum(r['status']!='enclosed' for r in rows),
          'scope':'exact rational interval enclosure over declared boxes; not probabilistic coverage or formal kernel proof'}
    return {**data,'sensitivity_id':fingerprint(data)}


def replay_sensitivity(report,model):
    try:
        return sensitivity_report(model,[r['point'] for r in report['points']],radii=report['radii'])==report
    except (ValueError,TypeError,KeyError):return False


def jackknife_lineage(training,validation,*,budget,probe_points):
    """Leave one train lineage group out, refit and reselect on validation only.

    This is a training-sensitivity diagnostic. Repeated validation use is explicit
    and does not authorize reusing final test cases or claim statistical coverage.
    """
    training=validate_samples(training,split='train');validation=validate_samples(validation,split='validation')
    if not isinstance(budget,SearchBudget) or budget.max_evaluations>128 or budget.beam_width>16:
        raise ValueError('Jackknife requires a small explicit search budget')
    if len(training)>128:raise ValueError('Jackknife training sample cap exceeded')
    groups=sorted({s.group for s in training})
    if not 2<=len(groups)<=16:raise ValueError('Jackknife requires two to sixteen train lineage groups')
    if {s.group for s in training}&{s.group for s in validation}:raise ValueError('Validation lineage leakage')
    if {s.features for s in training}&{s.features for s in validation}:raise ValueError('Validation input leakage')
    probes=tuple(tuple(_number(x) for x in bounded_tuple(p,8,label='probe features')) for p in bounded_tuple(probe_points,32,label='probe points'))
    if not probes or any(len(p)!=len(training[0].features) for p in probes):raise ValueError('Probe schema mismatch')
    rows=[]
    for group in groups:
        retained=[s for s in training if s.group!=group]
        report=search(retained,budget=budget); candidates=[]
        for candidate in report['candidates']:
            model=SymbolicModel.from_data(candidate['model']); metric=score_model(model,validation)
            if metric['mse'] is not None:candidates.append((model,metric))
        if not candidates:
            rows.append({'omitted_group':group,'status':'no_validation_model','search_id':report['search_id']})
            continue
        model,metric=min(candidates,key=lambda pair:(_number(pair[1]['mse']),pair[0].term.size,pair[0].content_id))
        predictions=[]
        for point in probes:
            try:predictions.append(str(model.predict(point)))
            except ValueError:predictions.append(None)
        rows.append({'omitted_group':group,'status':'fitted','retained_training_id':sample_digest(retained),
                     'search_id':report['search_id'],'model':model.to_data(),'model_id':model.content_id,
                     'validation':metric,'predictions':predictions})
    ranges=[]
    for index,point in enumerate(probes):
        values=[_number(row['predictions'][index]) for row in rows if row['status']=='fitted' and row['predictions'][index] is not None]
        ranges.append({'point':[str(x) for x in point],'minimum':str(min(values)) if values else None,
                       'maximum':str(max(values)) if values else None,'observed_predictions':len(values),
                       'missing_predictions':len(groups)-len(values)})
    data={'version':'symbolic-lineage-jackknife-v1','training_content_id':sample_digest(training),
          'validation_content_id':sample_digest(validation),'budget':budget.to_data(),
          'probe_points':[[str(x) for x in p] for p in probes],'fits':rows,'prediction_ranges':ranges,
          'scope':'leave-one-train-group-out sensitivity; validation reused explicitly; final test never consumed'}
    return {**data,'diagnostic_id':fingerprint(data)}


def replay_jackknife(report,training,validation):
    try:return jackknife_lineage(training,validation,budget=SearchBudget(**report['budget']),probe_points=report['probe_points'])==report
    except (ValueError,TypeError,KeyError):return False
