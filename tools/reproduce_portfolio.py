"""Exploratory exact-solver portfolio comparisons, preserving accepted/rejected runs."""
import argparse
import json
from pathlib import Path
from nablamath.core.semantic_ir import canonical_json
from nablamath.forge.reverse_builder import generate_task
from nablamath.forge.deduplicate import semantic_fingerprint
from nablamath.evolution.portfolio import PortfolioPolicy,PortfolioCampaign,select_portfolio


def reproduce(destination):
    root=Path(destination);root.mkdir(parents=True,exist_ok=False)
    families=('linear_system','convex_quadratic','stationary_markov','polynomial_integral')
    protocol={'schema_version':1,'families':families,'baseline_strategies':['exact','alternate'],
              'calibration_count':8,'holdout_count':24,'calibration_seeds':[18100,28100],'holdout_seeds':[36200,46200],
              'alpha':.05,'max_generations':8,'minimum_effect':.05,'size':3,
              'scope':'exploratory finite solver-work comparisons, not preregistered external discovery',
              'selection':'calibration only; all reserved outcomes retained; uniform alternate is a weaker explicit baseline'}
    (root/'protocol.json').write_text(canonical_json(protocol)+'\n',encoding='utf-8')
    seen=set();runs=[]
    def tasks(seed,count):
        result=[]
        for i in range(count*100):
            task=generate_task(families[i%len(families)],seed+i,3).task;key=semantic_fingerprint(task)
            if key in seen:continue
            seen.add(key);result.append(task)
            if len(result)==count:return result
        raise ValueError('Orçamento de tarefas únicas esgotado')
    for index,strategy in enumerate(protocol['baseline_strategies']):
        calibration=tasks(protocol['calibration_seeds'][index],8);holdout=tasks(protocol['holdout_seeds'][index],24)
        candidate,selection=select_portfolio(calibration)
        baseline=PortfolioPolicy(tuple((family,strategy) for family in families))
        campaign=PortfolioCampaign(root/f'campaign-{strategy}.sqlite3',baseline)
        receipt=campaign.evaluate(candidate,calibration,holdout)
        rollback=None
        if receipt['accepted']:
            campaign.promote(receipt)
            rollback=campaign.rollback(baseline.policy_id,reason='Demonstrate operator rollback after accepted exploratory comparison')
        run={'baseline_strategy':strategy,'selection_measurements':selection,'receipt':receipt,'rollback':rollback}
        (root/f'run-{strategy}.json').write_text(canonical_json(run)+'\n',encoding='utf-8');runs.append(run)
    summary={'runs':[{'baseline':r['baseline_strategy'],'accepted':r['receipt']['accepted'],
                     'statistics':r['receipt']['statistics'],'effect':r['receipt']['effect']} for r in runs],
             'general_recursive_self_improvement_established':False}
    (root/'summary.json').write_text(canonical_json(summary)+'\n',encoding='utf-8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    print(json.dumps(reproduce(parser.parse_args().destination),sort_keys=True))
