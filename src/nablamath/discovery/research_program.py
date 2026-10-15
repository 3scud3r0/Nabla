"""Reproducible bounded hypothesis programs with negative results and literature scope."""
from ..core.semantic_ir import canonical_json,fingerprint
from ..knowledge.literature import LiteratureCorpus
from .hypothesis import Hypothesis,Observation,ObservationSet
from .symbolic_regression import fit_and_evaluate,fit_models
from .experimental_design import propose_experiment
from .novelty_screen import screen_novelty
from ..falsifier.counterexample_miner import mine


def run_research(calibration,holdout,corpus,*,query,reference=None,max_degree=4):
    regression,selected=fit_and_evaluate(calibration,holdout,max_degree=max_degree)
    candidates=fit_models(calibration,max_degree=max_degree)
    hypotheses=[c['hypothesis'] for c in candidates[:3]]
    design=propose_experiment(hypotheses,range(-6,7),observed=[o.x for o in calibration.observations]) if len(hypotheses)>1 else None
    novelty=screen_novelty(selected,corpus,query=query)
    refutation=mine(((selected.expression,reference),),radius=4,budget=1000) if reference is not None else None
    payload={'schema_version':1,'regression':regression,'experimental_design':design,'novelty':novelty,
             'refutation':refutation,'corpus':corpus.to_data(),'query':query,'reference':reference,'max_degree':max_degree,
             'conclusion':'supported_on_holdout' if regression['holdout_result']['matches_all'] else 'not_supported_on_holdout',
             'global_novelty_established':False,'experimental_validation':False}
    return {**payload,'program_id':fingerprint(payload)}


def _observations(data):
    from ..core.units import Unit
    return ObservationSet(tuple(Observation(**row) for row in data['observations']),data['provenance'],data['role'],
                          Unit(tuple(data['input_unit']['dimensions']),data['input_unit']['scale']),
                          Unit(tuple(data['output_unit']['dimensions']),data['output_unit']['scale']),data['synthetic'])


def verify_research(report):
    try:
        if 'grammar' in report and 'selected' in report:
            from .basis_search import verify_basis_report
            return verify_basis_report(report)
        data=report['regression']
        actual=run_research(_observations(data['calibration']),_observations(data['holdout']),
                            LiteratureCorpus.from_data(report['corpus']),query=report['query'],
                            reference=report['reference'],max_degree=report['max_degree'])
        return canonical_json(actual)==canonical_json(report)
    except (ValueError,KeyError,TypeError,ArithmeticError):
        return False
