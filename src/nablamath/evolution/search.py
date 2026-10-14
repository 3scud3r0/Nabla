"""Select bounded descendants on calibration only; reserved data stays outside search."""
from .policy_genome import PolicyGenome
from .proposal_validator import validate_proposal
from .evaluator import _loss


def search_policies(parent,calibration,contract,*,step_counts=(10,20,40,80)):
    calibration=tuple(calibration); step_counts=tuple(step_counts)
    if not 1<=len(calibration)<=64 or not step_counts or len(step_counts)*2>contract.max_candidates:
        raise ValueError('Orçamento de busca/calibração excedido')
    candidates=[]; rejected=[]
    for method in ('euler','rk4'):
        for steps in step_counts:
            try:
                genome=PolicyGenome(method,steps,parent.genome_id,parent.generation+1)
                validate_proposal(genome,parent,contract)
                errors=tuple(_loss(genome.as_policy(),m) for m in calibration)
                if any(not __import__('math').isfinite(e) for e in errors):
                    raise ValueError('Candidato não finito')
                candidates.append((max(errors),genome.as_policy().derivative_calls,genome))
            except ValueError as exc:
                rejected.append({'method':method,'steps':steps,'reason':str(exc)})
    if not candidates:
        raise ValueError('Nenhum candidato válido')
    candidates.sort(key=lambda row:(row[0],row[1],row[2].genome_id))
    winner=candidates[0][2]
    return winner,{'selected':winner.to_data(),'calibration_only':True,
                   'candidates':[{'genome':g.to_data(),'max_error':e,'derivative_calls':cost} for e,cost,g in candidates],
                   'rejected':rejected,'contract_id':contract.contract_id}
