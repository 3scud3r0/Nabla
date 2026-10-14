"""Exact least-squares search over a bounded polynomial expression grammar."""
from fractions import Fraction
from ..core.semantic_ir import PolynomialSpec, rational, fingerprint
from ..core.units import ONE
from ..expression import render
from ..math.linear_algebra import Matrix
from .hypothesis import Hypothesis, assess


def fit_models(calibration, *, max_degree=4, complexity_penalty='1/1000000'):
    if calibration.role!='calibration' or type(max_degree) is not int or not 0<=max_degree<=6:
        raise ValueError('Busca requer calibração e grau entre 0 e 6')
    if calibration.input_unit!=ONE or calibration.output_unit!=ONE:
        raise ValueError('Esta gramática ajusta variáveis adimensionais')
    penalty=rational(complexity_penalty)
    if penalty<0:
        raise ValueError('Penalidade não negativa obrigatória')
    observations=calibration.observations
    candidates=[]
    for degree in range(min(max_degree,len(observations)-1)+1):
        design=Matrix(tuple(tuple(o.x**k for k in range(degree+1)) for o in observations))
        response=Matrix(tuple((o.y,) for o in observations))
        transpose=design.transpose()
        weights=(transpose@design).inverse()@(transpose@response)
        coefficients=tuple(row[0] for row in weights.rows)
        polynomial=PolynomialSpec(coefficients)
        hypothesis=Hypothesis(render(polynomial.to_expr()),'Polynomial grammar, calibrated observations only',lower=-1000000,upper=1000000)
        squared=sum((polynomial.evaluate(o.x)-o.y)**2 for o in observations)/len(observations)
        complexity=len(polynomial.coefficients)
        candidates.append({'hypothesis':hypothesis,'degree':degree,'mse':squared,
                           'score':squared+penalty*complexity,'coefficients':polynomial.to_data()})
    unique={}
    for candidate in candidates:
        unique.setdefault(candidate['hypothesis'].hypothesis_id,candidate)
    candidates=list(unique.values())
    return tuple(sorted(candidates,key=lambda r:(r['score'],len(r['coefficients']),r['hypothesis'].hypothesis_id)))


def fit_and_evaluate(calibration, holdout, **options):
    if holdout.role!='holdout' or {o.x for o in calibration.observations}&{o.x for o in holdout.observations}:
        raise ValueError('Holdout ausente ou contaminado por entradas de calibração')
    candidates=fit_models(calibration,**options)
    selected=candidates[0]['hypothesis']
    payload={'schema_version':1,'grammar':'univariate_polynomials_degree_0_to_6',
             'calibration':calibration.to_data(),'holdout':holdout.to_data(),
             'selected':selected.to_data(),'selection_dataset_id':calibration.dataset_id,
             'candidates':[{'hypothesis':c['hypothesis'].to_data(),'degree':c['degree'],
                            'mse':str(c['mse']),'score':str(c['score']),'coefficients':c['coefficients']} for c in candidates],
             'calibration_result':assess(selected,calibration),'holdout_result':assess(selected,holdout),
             'formal_proof':False,'limitations':'Finite data and bounded grammar do not establish a novel law.'}
    return {**payload,'report_id':fingerprint(payload)},selected
