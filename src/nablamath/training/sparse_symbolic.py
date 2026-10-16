"""Exact sparse combinations of train-generated nonlinear grammar features.

All coefficients and residuals are rational. Greedy forward selection is bounded
and deterministic, not globally optimal. Rank-deficient feature combinations
are reported rather than silently regularized or fitted to reserved labels.
"""
from dataclasses import dataclass,asdict
from fractions import Fraction
from ..core.semantic_ir import fingerprint
from ..math.linear_algebra import Matrix
from ._bounded import bounded_tuple
from .symbolic_beam import (Term,SearchBudget,search,validate_samples,sample_digest,
                            score_model,_number)

VERSION='exact-sparse-symbolic-v1'


@dataclass(frozen=True)
class SparseBudget:
    max_terms: int=4
    max_dictionary: int=32
    max_fits: int=128
    complexity_penalty: str='1/1000000'

    def __post_init__(self):
        for name,upper in (('max_terms',6),('max_dictionary',64),('max_fits',512)):
            value=getattr(self,name)
            if type(value) is not int or not 1<=value<=upper:
                raise ValueError('Sparse search resource budget exceeded')
        penalty=_number(self.complexity_penalty)
        if penalty<0:raise ValueError('Nonnegative sparse complexity penalty required')
        object.__setattr__(self,'complexity_penalty',str(penalty))

    def to_data(self):return asdict(self)


@dataclass(frozen=True)
class SparseModel:
    terms: tuple
    weights: tuple
    intercept: Fraction
    training_ids: tuple
    training_content_id: str

    def __post_init__(self):
        terms=bounded_tuple(self.terms,6,label='sparse terms')
        weights=tuple(_number(w) for w in bounded_tuple(self.weights,6,label='sparse weights'))
        if len(terms)!=len(weights) or any(not isinstance(t,Term) for t in terms):
            raise ValueError('Matching bounded terms and weights required')
        ids=[t.term_id for t in terms]
        if ids!=sorted(set(ids)) or any(t.operation=='one' for t in terms):
            raise ValueError('Canonical independent feature identifiers required')
        training_ids=bounded_tuple(self.training_ids,512,label='training IDs')
        if not training_ids or any(type(x) is not str or not x or len(x)>128 for x in training_ids) or list(training_ids)!=sorted(set(training_ids)):
            raise ValueError('Canonical training manifest required')
        digest=self.training_content_id
        if type(digest) is not str or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Content-addressed training manifest required')
        object.__setattr__(self,'terms',terms);object.__setattr__(self,'weights',weights)
        object.__setattr__(self,'training_ids',training_ids)
        object.__setattr__(self,'intercept',_number(self.intercept))

    @property
    def complexity(self):return 1+sum(t.size for t in self.terms)

    def predict(self,features):
        features=tuple(_number(x) for x in bounded_tuple(features,8,label='prediction features'))
        if not features:raise ValueError('Nonempty prediction features required')
        return _number(self.intercept+sum(w*t.evaluate(features) for t,w in zip(self.terms,self.weights)))

    def to_data(self):
        return {'version':VERSION,'terms':[t.to_data() for t in self.terms],'weights':[str(w) for w in self.weights],
                'intercept':str(self.intercept),'training_ids':list(self.training_ids),'training_content_id':self.training_content_id}

    @property
    def content_id(self):return fingerprint(self.to_data())

    @classmethod
    def from_data(cls,data):
        if type(data) is not dict or set(data)!={'version','terms','weights','intercept','training_ids','training_content_id'} or data['version']!=VERSION:
            raise ValueError('Invalid sparse model schema')
        terms=bounded_tuple(data['terms'],6,label='sparse terms')
        return cls(tuple(Term.from_data(t) for t in terms),data['weights'],data['intercept'],data['training_ids'],data['training_content_id'])


def fit_sparse(terms,training):
    training=validate_samples(training,split='train')
    terms=bounded_tuple(terms,6,label='sparse terms')
    if any(not isinstance(t,Term) for t in terms):raise ValueError('Typed grammar terms required')
    terms=tuple(sorted(terms,key=lambda t:t.term_id))
    if len({t.term_id for t in terms})!=len(terms):raise ValueError('Repeated dictionary term')
    if any(t.operation=='one' for t in terms):raise ValueError('Constant column already supplied by intercept')
    # The Gram matrix has at most seven rows/columns. Existing exact Matrix
    # operations supply the solve; no floating normal-equation conditioning claim.
    rows=tuple((Fraction(1),*(t.evaluate(s.features) for t in terms)) for s in training)
    design=Matrix(rows); target=Matrix(tuple((s.target,) for s in training))
    transpose=design.transpose(); gram=transpose@design
    if gram.determinant()==0:raise ValueError('Rank-deficient symbolic dictionary')
    coefficients=(gram.inverse()@(transpose@target)).rows
    intercept=_number(coefficients[0][0]); weights=tuple(_number(r[0]) for r in coefficients[1:])
    model=SparseModel(terms,weights,intercept,tuple(s.identifier for s in training),sample_digest(training))
    result=score_model(model,training)
    if result['mse'] is None:raise ValueError('Fitted model has invalid training domain')
    return model,_number(result['mse'])


def sparse_search(training,*,grammar_budget=None,sparse_budget=None):
    training=validate_samples(training,split='train')
    grammar_budget=grammar_budget or SearchBudget(); sparse_budget=sparse_budget or SparseBudget()
    if not isinstance(grammar_budget,SearchBudget) or not isinstance(sparse_budget,SparseBudget):
        raise ValueError('Typed sparse and grammar budgets required')
    grammar=search(training,budget=grammar_budget)
    dictionary={}
    for row in grammar['candidates']:
        term=Term.from_data(row['model']['term'])
        if term.operation!='one':dictionary.setdefault(term.term_id,term)
        if len(dictionary)>=sparse_budget.max_dictionary:break
    model,mse=fit_sparse((),training); penalty=_number(sparse_budget.complexity_penalty)
    def candidate(model,mse,step):
        return {'model':model.to_data(),'model_id':model.content_id,'training_mse':str(mse),
                'rank_score':str(_number(mse+penalty*model.complexity)),'step':step}
    current=candidate(model,mse,0); path=[current]; considered=[current]; failures=[]; fit_count=1
    for step in range(1,sparse_budget.max_terms+1):
        accepted=[]; selected={t.term_id for t in model.terms}
        for term_id,term in sorted(dictionary.items()):
            if term_id in selected:continue
            if fit_count>=sparse_budget.max_fits:break
            fit_count+=1
            try:
                proposal,error=fit_sparse((*model.terms,term),training)
                row=candidate(proposal,error,step);accepted.append(row);considered.append(row)
            except ValueError as exc:
                failures.append({'step':step,'term_id':term_id,'reason':str(exc)})
        if not accepted:break
        best=min(accepted,key=lambda r:(_number(r['rank_score']),r['model_id']))
        if _number(best['rank_score'])>=_number(current['rank_score']):break
        current=best;path.append(current);model=SparseModel.from_data(current['model'])
        if fit_count>=sparse_budget.max_fits:break
    data={'version':VERSION,'grammar_search':grammar,'sparse_budget':sparse_budget.to_data(),
          'training_content_id':sample_digest(training),'candidates':path,'considered':considered,
          'dictionary_ids':sorted(dictionary),'failures':failures,'fits':fit_count,
          'budget_exhausted':fit_count>=sparse_budget.max_fits,
          'scope':'greedy exact feature combinations; training rank and bounded dictionary may miss laws'}
    return {**data,'search_id':fingerprint(data)}


def replay_sparse_search(report,training):
    try:return sparse_search(training,grammar_budget=SearchBudget(**report['grammar_search']['budget']),sparse_budget=SparseBudget(**report['sparse_budget']))==report
    except (ValueError,TypeError,KeyError):return False


def freeze_sparse_experiment(samples,*,owner,grammar_budget,sparse_budget,ablation_budgets=()):
    from .symbolic_protocol import freeze_experiment
    if not isinstance(sparse_budget,SparseBudget):raise ValueError('SparseBudget required')
    experiment=freeze_experiment(samples,owner=owner,budget=grammar_budget,ablation_budgets=ablation_budgets)
    experiment.pop('experiment_id')
    experiment['version']='sparse-symbolic-experiment-v1';experiment['sparse_budget']=sparse_budget.to_data()
    experiment['selection_rule']='validation_mse_then_sparse_complexity_then_model_id; primary grammar only'
    return {**experiment,'experiment_id':fingerprint(experiment)}


def train_sparse_and_select(experiment,training,validation):
    from .symbolic_protocol import _partition,_validate_learning_partitions
    if experiment.get('version')!='sparse-symbolic-experiment-v1' or fingerprint({k:v for k,v in experiment.items() if k!='experiment_id'})!=experiment['experiment_id']:
        raise ValueError('Invalid sparse experiment')
    training=_partition(experiment,training,'train');validation=_partition(experiment,validation,'validation')
    _validate_learning_partitions(training,validation)
    budget=SparseBudget(**experiment['sparse_budget'])
    def run(grammar):
        report=sparse_search(training,grammar_budget=SearchBudget(**grammar),sparse_budget=budget)
        scores=[]
        for candidate in report['candidates']:
            model=SparseModel.from_data(candidate['model']); result=score_model(model,validation)
            scores.append({'model_id':model.content_id,'model':model.to_data(),'validation':result,'complexity':model.complexity})
        valid=[r for r in scores if r['validation']['mse'] is not None]
        selected=min(valid,key=lambda r:(_number(r['validation']['mse']),r['complexity'],r['model_id'])) if valid else None
        return report,scores,selected
    primary,scores,winner=run(experiment['budget'])
    if winner is None:raise ValueError('No sparse validation candidate')
    ablations=[]
    for grammar in experiment['ablation_budgets']:
        report,_,selected=run(grammar)
        ablations.append({'search':report,'selected_model_id':selected['model_id'] if selected else None,
                          'validation':selected['validation'] if selected else None})
    data={'version':'sparse-selection-v1','experiment_id':experiment['experiment_id'],'search':primary,
          'validation_content_id':sample_digest(validation),'candidate_scores':scores,
          'selected_model':winner['model'],'selected_model_id':winner['model_id'],
          'ablations':ablations,'test_observed':False,
          'scope':'sparse training path selected using validation only; no external generalization claim'}
    return {**data,'selection_id':fingerprint(data)}
