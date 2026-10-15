"""Exact finite rational basis discovery with disjoint selection and holdout data."""
from itertools import combinations
from ..core.semantic_ir import SemanticExpression, rational, fingerprint
from ..core.units import ONE
from ..expression import evaluate,parse_expr,render
from ..math.linear_algebra import Matrix
from .hypothesis import Hypothesis, assess


def discover_basis(calibration, holdout, *, basis=('1','x','x*x','1/x'), max_terms=3,
                   penalty='1/1000000', max_candidates=128):
    if calibration.role!='calibration' or holdout.role!='holdout' or calibration.input_unit!=ONE or calibration.output_unit!=ONE:
        raise ValueError('Busca exige calibração/holdout adimensionais')
    if {o.x for o in calibration.observations}&{o.x for o in holdout.observations}:
        raise ValueError('Sobreposição calibração/holdout')
    basis=tuple(basis); penalty=rational(penalty)
    if (not 1<=len(basis)<=12 or len(set(basis))!=len(basis) or type(max_terms) is not int
            or not 1<=max_terms<=min(5,len(basis)) or type(max_candidates) is not int or not 1<=max_candidates<=512 or penalty<0):
        raise ValueError('Gramática ou orçamento inválido')
    expressions=[SemanticExpression.parse(source) for source in basis]
    if any(set(n for n,_ in e.variable_types)-{'x'} for e in expressions):
        raise ValueError('Gramática aceita apenas x')
    candidates=[];rejected=[];attempts=0
    for size in range(1,max_terms+1):
        for indices in combinations(range(len(basis)),size):
            if attempts>=max_candidates:break
            attempts+=1
            try:
                design=Matrix(tuple(tuple(evaluate(expressions[i].expression,{'x':o.x}) for i in indices) for o in calibration.observations))
                response=Matrix(tuple((o.y,) for o in calibration.observations))
                t=design.transpose();coeff=(t@design).inverse()@(t@response)
                weights=tuple(row[0] for row in coeff.rows)
                source=' + '.join(f'({w})*({basis[i]})' for i,w in zip(indices,weights))
                hypothesis=Hypothesis(source,'Finite rational basis search; calibration only',lower=-1000000,upper=1000000)
                mse=sum((hypothesis.predict(o.x)-o.y)**2 for o in calibration.observations)/len(calibration.observations)
                complexity=sum(w!=0 for w in weights)
                candidates.append({'hypothesis':hypothesis.to_data(),'hypothesis_id':hypothesis.hypothesis_id,
                                   'indices':indices,'weights':[str(w) for w in weights],'mse':str(mse),
                                   'score':str(mse+penalty*complexity),'complexity':complexity})
            except (ValueError,ArithmeticError) as exc:
                rejected.append({'indices':indices,'reason':str(exc)})
        if attempts>=max_candidates:break
    if not candidates:raise ValueError('Nenhum modelo identificável na gramática')
    candidates.sort(key=lambda c:(rational(c['score']),c['complexity'],c['hypothesis_id']))
    selected=candidates[0]
    h=selected['hypothesis'];hypothesis=Hypothesis(h['expression'],h['scope'],lower=h['lower'],upper=h['upper'])
    payload={'schema_version':1,'grammar':list(basis),'penalty':str(penalty),'max_terms':max_terms,
             'max_candidates':max_candidates,'attempted':attempts,'budget_reached':attempts>=max_candidates,
             'calibration':calibration.to_data(),'holdout':holdout.to_data(),'selected':selected,
             'candidates':candidates,'rejected':rejected,'calibration_result':assess(hypothesis,calibration),
             'holdout_result':assess(hypothesis,holdout),'global_novelty_established':False,
             'limitations':'Finite rational grammar; singular designs rejected; no global novelty or observed-data authentication.'}
    return {**payload,'report_id':fingerprint(payload)}


def verify_basis_report(report):
    """Replay selection and holdout assessment without trusting stored success flags."""
    from .research_program import _observations
    from ..core.semantic_ir import canonical_json
    try:
        actual=discover_basis(_observations(report['calibration']),_observations(report['holdout']),
                basis=report['grammar'],max_terms=report['max_terms'],penalty=report['penalty'],max_candidates=report['max_candidates'])
        return canonical_json(actual)==canonical_json(report)
    except (ValueError,KeyError,TypeError,ArithmeticError):return False
