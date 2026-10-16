"""Bounded exact symbolic feature search, with train-only affine parameter fitting.

The grammar is intentionally small: constants, named variables, sums, products,
negation and guarded reciprocals. Expressions are data, never Python source.
Beam ranking consumes training data only. A separate module selects candidates
on validation observations and owns the durable final-test boundary.
"""
from dataclasses import dataclass, asdict
from fractions import Fraction
from ..core.semantic_ir import rational, fingerprint
from ._bounded import bounded_tuple

VERSION='exact-symbolic-beam-v1'


def _number(value):
    result=rational(value)
    if result.numerator.bit_length()>512 or result.denominator.bit_length()>512:
        raise ValueError('Exact arithmetic bit budget exceeded')
    return result


@dataclass(frozen=True)
class Sample:
    identifier: str
    group: str
    features: tuple
    target: Fraction
    split: str

    def __post_init__(self):
        for value in (self.identifier,self.group):
            if type(value) is not str or not value.strip() or len(value)>128:
                raise ValueError('Bounded sample and lineage group labels required')
        features=tuple(_number(x) for x in bounded_tuple(self.features,8,label='symbolic features'))
        if not features or type(self.split) is not str or self.split not in {'train','validation','test'}:
            raise ValueError('Features and declared partition required')
        object.__setattr__(self,'features',features)
        object.__setattr__(self,'target',_number(self.target))

    def to_data(self):
        return {'identifier':self.identifier,'group':self.group,'features':[str(x) for x in self.features],
                'target':str(self.target),'split':self.split}

    @classmethod
    def from_data(cls,data):
        if type(data) is not dict or set(data)!={'identifier','group','features','target','split'}:
            raise ValueError('Invalid sample fields')
        return cls(**data)

    @property
    def content_id(self):
        return fingerprint(self.to_data())


@dataclass(frozen=True)
class Term:
    operation: str
    arguments: tuple=()
    variable: int=0

    def __post_init__(self):
        args=bounded_tuple(self.arguments,2,label='term children')
        object.__setattr__(self,'arguments',args)
        arity={'one':0,'variable':0,'add':2,'multiply':2,'negate':1,'reciprocal':1}
        if type(self.operation) is not str or self.operation not in arity or len(args)!=arity[self.operation] or any(not isinstance(a,Term) for a in args):
            raise ValueError('Unknown symbolic operation or arity')
        if type(self.variable) is not int or not 0<=self.variable<8:
            raise ValueError('Invalid variable index')
        if self.operation!='variable' and self.variable!=0:
            raise ValueError('Only variable terms carry an index')
        if self.depth>6 or self.size>31:
            raise ValueError('Expression grammar budget exceeded')
        if self.operation in {'add','multiply'} and args[0].term_id>args[1].term_id:
            raise ValueError('Commutative children must be canonical')

    @property
    def depth(self):
        return 1+max((a.depth for a in self.arguments),default=0)

    @property
    def size(self):
        return 1+sum(a.size for a in self.arguments)

    def to_data(self):
        return {'operation':self.operation,'variable':self.variable,'arguments':[a.to_data() for a in self.arguments]}

    @property
    def term_id(self):
        return fingerprint(self.to_data())

    @classmethod
    def from_data(cls,data,_depth=0):
        if _depth>6 or type(data) is not dict or set(data)!={'operation','variable','arguments'}:
            raise ValueError('Invalid expression data')
        args=bounded_tuple(data['arguments'],2,label='term children')
        return cls(data['operation'],tuple(cls.from_data(a,_depth+1) for a in args),data['variable'])

    def evaluate(self,features):
        if self.operation=='one':return Fraction(1)
        if self.operation=='variable':
            if self.variable>=len(features):raise ValueError('Variable outside feature schema')
            return _number(features[self.variable])
        values=[a.evaluate(features) for a in self.arguments]
        if self.operation=='negate':return _number(-values[0])
        if self.operation=='reciprocal':
            if not values[0]:raise ValueError('Reciprocal domain excludes zero')
            return _number(1/values[0])
        if self.operation=='add':return _number(values[0]+values[1])
        return _number(values[0]*values[1])


def binary(operation,left,right):
    return Term(operation,tuple(sorted((left,right),key=lambda t:t.term_id)))


@dataclass(frozen=True)
class SearchBudget:
    depth: int=3
    beam_width: int=12
    max_evaluations: int=1000
    complexity_penalty: str='1/1000000'
    operations: tuple=('add','multiply','reciprocal')

    def __post_init__(self):
        if type(self.depth) is not int or not 1<=self.depth<=5 or type(self.beam_width) is not int or not 1<=self.beam_width<=64:
            raise ValueError('Bounded grammar depth and beam width required')
        if type(self.max_evaluations) is not int or not 1<=self.max_evaluations<=10000:
            raise ValueError('Bounded candidate evaluation count required')
        operations=bounded_tuple(self.operations,4,label='grammar operations')
        if not operations or any(type(op) is not str for op in operations) or len(set(operations))!=len(operations) or not set(operations)<={'add','multiply','negate','reciprocal'}:
            raise ValueError('Explicit unique grammar operations required')
        object.__setattr__(self,'operations',operations)
        penalty=_number(self.complexity_penalty)
        if penalty<0:raise ValueError('Nonnegative complexity penalty required')
        object.__setattr__(self,'complexity_penalty',str(penalty))

    def to_data(self):
        return {**asdict(self),'operations':list(self.operations)}


@dataclass(frozen=True)
class SymbolicModel:
    term: Term
    slope: Fraction
    intercept: Fraction
    training_ids: tuple
    training_content_id: str

    def __post_init__(self):
        if not isinstance(self.term,Term):raise ValueError('Declarative symbolic term required')
        object.__setattr__(self,'slope',_number(self.slope))
        object.__setattr__(self,'intercept',_number(self.intercept))
        ids=bounded_tuple(self.training_ids,512,label='training IDs')
        if not ids or any(type(x) is not str or not x or len(x)>128 for x in ids) or tuple(sorted(set(ids)))!=ids:
            raise ValueError('Canonical training identity manifest required')
        object.__setattr__(self,'training_ids',ids)
        if type(self.training_content_id) is not str or len(self.training_content_id)!=64 or any(c not in '0123456789abcdef' for c in self.training_content_id):
            raise ValueError('Training content digest required')

    def predict(self,features):
        features=tuple(_number(x) for x in bounded_tuple(features,8,label='prediction features'))
        if not features:raise ValueError('Nonempty prediction features required')
        return _number(self.slope*self.term.evaluate(features)+self.intercept)

    def to_data(self):
        return {'version':VERSION,'term':self.term.to_data(),'slope':str(self.slope),'intercept':str(self.intercept),
                'training_ids':list(self.training_ids),'training_content_id':self.training_content_id}

    @property
    def content_id(self):
        return fingerprint(self.to_data())

    @classmethod
    def from_data(cls,data):
        if type(data) is not dict or set(data)!={'version','term','slope','intercept','training_ids','training_content_id'} or data['version']!=VERSION:
            raise ValueError('Unsupported model data')
        return cls(Term.from_data(data['term']),data['slope'],data['intercept'],data['training_ids'],data['training_content_id'])


def validate_samples(samples,*,split=None):
    samples=bounded_tuple(samples,512,label='symbolic samples')
    if not samples or any(not isinstance(s,Sample) for s in samples):
        raise ValueError('Typed nonempty bounded samples required')
    if len({s.identifier for s in samples})!=len(samples):raise ValueError('Duplicate sample identity')
    if len({len(s.features) for s in samples})!=1:raise ValueError('Inconsistent feature schema')
    if split and any(s.split!=split for s in samples):raise ValueError('Wrong dataset partition')
    return tuple(sorted(samples,key=lambda s:s.identifier))


def sample_digest(samples):
    return fingerprint([s.to_data() for s in validate_samples(samples)])


def fit_affine(term,training):
    """Exact least squares for y=a*term(x)+b; constant terms use a=0."""
    training=validate_samples(training,split='train')
    if not isinstance(term,Term):raise ValueError('Typed grammar term required')
    points=[term.evaluate(s.features) for s in training]
    n=len(points); sx=sum(points); sy=sum(s.target for s in training)
    denominator=n*sum(x*x for x in points)-sx*sx
    slope=Fraction(0) if not denominator else _number((n*sum(x*s.target for x,s in zip(points,training))-sx*sy)/denominator)
    intercept=_number((sy-slope*sx)/n)
    model=SymbolicModel(term,slope,intercept,tuple(s.identifier for s in training),sample_digest(training))
    mse=_number(sum((model.predict(s.features)-s.target)**2 for s in training)/n)
    return model,mse


def score_model(model,samples):
    samples=validate_samples(samples)
    errors=[]; excluded=[]
    for sample in samples:
        try:errors.append(_number((model.predict(sample.features)-sample.target)**2))
        except ValueError:excluded.append(sample.identifier)
    # Domain failures are not silently dropped from averages or ranking.
    return {'mse':str(_number(sum(errors)/len(errors))) if not excluded else None,
            'total':len(samples),'domain_failures':excluded,'exact_matches':sum(error==0 for error in errors)}


def search(training,*,budget=None):
    training=validate_samples(training,split='train'); budget=budget or SearchBudget()
    if not isinstance(budget,SearchBudget):raise ValueError('SearchBudget required')
    atoms=[Term('one')]+[Term('variable',variable=i) for i in range(len(training[0].features))]
    pending=atoms; seen=set(); candidates=[]; failures=[]; generations=[]
    penalty=_number(budget.complexity_penalty)
    for generation in range(budget.depth):
        ranked=[]
        for term in sorted(pending,key=lambda t:t.term_id):
            if term.term_id in seen:continue
            if len(seen)>=budget.max_evaluations:break
            seen.add(term.term_id)
            try:
                model,mse=fit_affine(term,training)
                row={'model':model.to_data(),'model_id':model.content_id,'training_mse':str(mse),
                     'rank_score':str(_number(mse+penalty*term.size)),'generation':generation}
                ranked.append(row); candidates.append(row)
            except ValueError as exc:
                failures.append({'term_id':term.term_id,'reason':str(exc)})
        generations.append({'generation':generation,'evaluated':len(ranked),'failed':len(failures)})
        if len(seen)>=budget.max_evaluations or generation==budget.depth-1:break
        leaders=sorted(candidates,key=lambda r:(_number(r['rank_score']),r['model_id']))[:budget.beam_width]
        terms=[Term.from_data(r['model']['term']) for r in leaders]
        proposals={}
        for left in terms:
            for op in budget.operations:
                if op in {'negate','reciprocal'}:
                    children=[(left,)]
                else:
                    children=[tuple(sorted((left,right),key=lambda t:t.term_id)) for right in (*atoms,*terms)]
                for args in children:
                    try:term=Term(op,args)
                    except ValueError:continue
                    if term.depth<=budget.depth and term.term_id not in seen:proposals[term.term_id]=term
        pending=list(proposals.values())
        if not pending:break
    candidates.sort(key=lambda r:(_number(r['rank_score']),r['model_id']))
    data={'version':VERSION,'budget':budget.to_data(),'training_content_id':sample_digest(training),
          'training_ids':[s.identifier for s in training],'candidates':candidates,'failures':failures,
          'generations':generations,'attempted':len(seen),'budget_exhausted':len(seen)>=budget.max_evaluations,
          'scope':'finite exact symbolic grammar; no novelty or scientific generalization established'}
    return {**data,'search_id':fingerprint(data)}


def replay_search(report,training):
    try:
        return search(training,budget=SearchBudget(**report['budget']))==report
    except (ValueError,TypeError,KeyError):return False


def load_model(data):
    """Closed schema dispatch; artifacts cannot nominate executable classes."""
    if type(data) is not dict:raise ValueError('Model object required')
    if data.get('version')=='exact-sparse-symbolic-v1':
        from .sparse_symbolic import SparseModel
        return SparseModel.from_data(data)
    return SymbolicModel.from_data(data)
