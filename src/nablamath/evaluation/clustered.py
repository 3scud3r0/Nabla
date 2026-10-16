"""Paired cluster-aware descriptive evaluation with explicit inferential assumptions.

Within-group dependence is preserved by cluster bootstrap and sign flips. Neither
an exact p-value nor a narrow interval establishes exchangeability, external
novelty, causal effects or authentic observations. All numerical inputs are exact
rationals; caller identities, model provenance and group definitions are supplied.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import islice, product
import math
import random

from ..core.semantic_contracts import canonical_payload, require_digest, require_text
from ..core.semantic_ir import fingerprint, rational

MAX_OBSERVATIONS=512
MAX_GROUPS=64
MAX_BOOTSTRAPS=4096
MAX_ENUMERATIONS=65536


def _number(value,label,*,positive=False):
    result=rational(value)
    if max(abs(result.numerator).bit_length(),result.denominator.bit_length())>32:
        raise ValueError(label+' rational precision budget exceeded')
    if positive and result<=0:
        raise ValueError(label+' must be positive')
    if abs(result)>1_000_000:
        raise ValueError(label+' magnitude budget exceeded')
    return result


def _integer(value,label,minimum,maximum):
    if type(value) is not int or not minimum<=value<=maximum:
        raise ValueError(label+' outside explicit bounds')
    return value


@dataclass(frozen=True)
class PairedMeasurement:
    task_id: str
    group: str
    domain: str
    candidate_loss: Fraction
    baseline_loss: Fraction
    weight: Fraction = Fraction(1)

    def __post_init__(self):
        require_digest(self.task_id)
        require_text(self.group,'group',limit=128)
        require_text(self.domain,'domain',limit=128)
        for name in ('candidate_loss','baseline_loss'):
            value=_number(getattr(self,name),name)
            if value<0:
                raise ValueError('Losses must be nonnegative')
            object.__setattr__(self,name,value)
        object.__setattr__(self,'weight',_number(self.weight,'weight',positive=True))

    @property
    def improvement(self):
        return self.baseline_loss-self.candidate_loss

    def to_data(self):
        return {'task_id':self.task_id,'group':self.group,'domain':self.domain,
                'candidate_loss':str(self.candidate_loss),'baseline_loss':str(self.baseline_loss),
                'weight':str(self.weight)}


def measurements(rows):
    try:
        values=tuple(islice(iter(rows),MAX_OBSERVATIONS+1))
    except TypeError as exc:
        raise ValueError("Finite iterable of paired measurements required") from exc
    if not values or len(values)>MAX_OBSERVATIONS or any(not isinstance(r,PairedMeasurement) for r in values):
        raise ValueError('One to512 typed paired measurements required')
    identifiers=[row.task_id for row in values]
    if len(set(identifiers))!=len(identifiers):
        raise ValueError('Duplicate paired task identity')
    groups={row.group for row in values}
    if len(groups)>MAX_GROUPS:
        raise ValueError('Cluster count budget exceeded')
    # A declared dependence group cannot be split across domain reports, which
    # would falsely imply that the same cluster supplies independent domain units.
    group_domains={}
    for row in values:
        if row.group in group_domains and group_domains[row.group]!=row.domain:
            raise ValueError('A dependence cluster must belong to one declared domain')
        group_domains[row.group]=row.domain
    return tuple(sorted(values,key=lambda row:row.task_id))


def _aggregate(rows):
    by_group={}
    for row in rows:
        numerator,denominator=by_group.get(row.group,(Fraction(0),Fraction(0)))
        by_group[row.group]=(numerator+row.weight*row.improvement,denominator+row.weight)
    return {name:by_group[name] for name in sorted(by_group)}


def _quantile(values,probability):
    ordered=sorted(values)
    position=Fraction(len(ordered)-1)*probability
    low=position.numerator//position.denominator
    high=min(low+1,len(ordered)-1)
    fraction=position-low
    return ordered[low]*(1-fraction)+ordered[high]*fraction


def cluster_bootstrap(rows,*,repetitions=1024,seed=951017,coverage='19/20'):
    rows=measurements(rows)
    _integer(repetitions,'bootstrap repetitions',32,MAX_BOOTSTRAPS)
    _integer(seed,'seed',0,2**32-1)
    coverage=_number(coverage,'coverage')
    if not 0<coverage<1:
        raise ValueError('Coverage must be strictly between zero and one')
    clusters=tuple(_aggregate(rows).values())
    if len(clusters)<2:
        raise ValueError('Cluster bootstrap requires at least two declared clusters')
    rng=random.Random(seed)
    estimates=[]
    for _ in range(repetitions):
        sample=[clusters[rng.randrange(len(clusters))] for _ in clusters]
        estimates.append(sum((pair[0] for pair in sample),Fraction(0))/sum((pair[1] for pair in sample),Fraction(0)))
    tail=(1-coverage)/2
    lower,upper=_quantile(estimates,tail),_quantile(estimates,1-tail)
    numerator=sum((r.weight*r.improvement for r in rows),Fraction(0))
    total=sum((r.weight for r in rows),Fraction(0))
    result={'schema_version':1,'method':'whole-cluster-percentile-bootstrap-v1',
            'observation_count':len(rows),'cluster_count':len(clusters),'repetitions':repetitions,
            'seed':seed,'coverage':str(coverage),'weighted_improvement':str(numerator/total),
            'interval':[str(lower),str(upper)],'cohort_id':fingerprint([r.to_data() for r in rows]),
            'assumptions':['Declared clusters are exchangeable sampling units',
                           'Percentile intervals are approximate, not finite-sample guaranteed'],
            'assumptions_externally_validated':False,'scientific_gain_established':False}
    return {**result,'report_id':fingerprint(result)}


def paired_randomization(rows,*,mode='exact',repetitions=4096,seed=951017):
    """Two-sided cluster sign flips; retain ties, use a Monte Carlo plus-one p."""
    rows=measurements(rows)
    clusters=tuple(_aggregate(rows).values())
    contributions=tuple(pair[0] for pair in clusters)
    observed=abs(sum(contributions,Fraction(0)))
    if mode not in ('exact','monte_carlo'):
        raise ValueError('Explicit exact or monte_carlo randomization mode required')
    _integer(seed,'seed',0,2**32-1)
    if mode=='exact':
        count=2**len(clusters)
        if count>MAX_ENUMERATIONS:
            raise ValueError('Exact randomization exceeds enumeration budget')
        signs=product((-1,1),repeat=len(clusters))
        extreme=sum(abs(sum((sign*value for sign,value in zip(bits,contributions)),Fraction(0)))>=observed
                    for bits in signs)
        probability=Fraction(extreme,count)
    else:
        count=_integer(repetitions,'randomizations',32,MAX_BOOTSTRAPS)
        rng=random.Random(seed)
        extreme=0
        for _ in range(count):
            statistic=abs(sum((rng.choice((-1,1))*value for value in contributions),Fraction(0)))
            extreme+=statistic>=observed
        probability=Fraction(extreme+1,count+1)
    result={'schema_version':1,'method':'paired-cluster-sign-flip-v1','mode':mode,
        'cluster_count':len(clusters),'observation_count':len(rows),'randomizations':count,
        'extreme':extreme,'two_sided_p':str(probability),'seed':seed,
        'observed_weighted_sum':str(observed),'cohort_id':fingerprint([r.to_data() for r in rows]),
        'null':'Candidate/baseline labels exchangeable jointly within each declared cluster',
        'null_assumption_externally_validated':False,'causal_or_external_gain_established':False}
    return {**result,'report_id':fingerprint(result)}


def domain_summary(rows):
    rows=measurements(rows)
    domains={}
    for row in rows:
        domains.setdefault(row.domain,[]).append(row)
    summaries={}
    for name,values in sorted(domains.items()):
        total=sum((r.weight for r in values),Fraction(0))
        candidate=sum((r.weight*r.candidate_loss for r in values),Fraction(0))/total
        baseline=sum((r.weight*r.baseline_loss for r in values),Fraction(0))/total
        summaries[name]={'count':len(values),'clusters':len({r.group for r in values}),
                         'weight':str(total),'candidate_loss':str(candidate),
                         'baseline_loss':str(baseline),'improvement':str(baseline-candidate)}
    total=sum((r.weight for r in rows),Fraction(0))
    micro=sum((r.weight*r.improvement for r in rows),Fraction(0))/total
    macro=sum((Fraction(r['improvement']) for r in summaries.values()),Fraction(0))/len(summaries)
    result={'schema_version':1,'domains':summaries,'micro_improvement':str(micro),
            'macro_domain_improvement':str(macro),'cohort_id':fingerprint([r.to_data() for r in rows]),
            'domain_comparability_established':False,
            'scope':'Shared loss scales/weights supplied by caller; do not infer cross-discipline equivalence'}
    return {**result,'report_id':fingerprint(result)}


def verify_cluster_report(report,rows,*,kind,**kwargs):
    methods={'bootstrap':cluster_bootstrap,'randomization':paired_randomization,'domains':domain_summary}
    try:
        if kind not in methods:
            return False
        return canonical_payload(methods[kind](rows,**kwargs))==canonical_payload(report)
    except (ValueError,TypeError,KeyError,ArithmeticError):
        return False


def zero_failure_sample_size(*,maximum_failure_rate,alpha='1/20',maximum=10_000):
    """Binomial zero-failure planning bound; independent trials are an assumption."""
    rate=_number(maximum_failure_rate,'failure rate')
    alpha=_number(alpha,'alpha')
    _integer(maximum,'maximum sample',1,10_000)
    if not 0<rate<1 or not 0<alpha<1:
        raise ValueError('Failure rate and alpha must be strictly between zero and one')
    approximate=math.ceil(math.log(float(alpha))/math.log1p(-float(rate)))
    if approximate>maximum:
        raise ValueError('Required sample exceeds predeclared budget')
    # Exact rational inequalities fix any floating rounding at an integer bound.
    sample=max(1,approximate)
    while (1-rate)**sample>alpha:
        sample+=1
        if sample>maximum:
            raise ValueError('Required sample exceeds predeclared budget')
    while sample>1 and (1-rate)**(sample-1)<=alpha:
        sample-=1
    return {'sample_size':sample,'maximum_failure_rate':str(rate),'alpha':str(alpha),
            'assumption':'Independent identically distributed Bernoulli failure trials',
            'actual_independence_established':False,'actual_trials_executed':0}
