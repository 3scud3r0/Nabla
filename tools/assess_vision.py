"""Report measured acceptance evidence; never infer scientific completion from paths."""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]


def assess(research,benchmark,learning,*,junit=None,windows=None):
    def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
    root=Path(research);summary=read(root/'summary.json');discovery=read(root/'discovery.json');reviews=read(root/'peer-review.json')
    bench,experiment=read(benchmark),read(learning)
    phases={}
    for number in range(13):
        section=(ROOT/'vision.md').read_text(encoding='utf-8').split(f'### Fase {number} —',1)[1].split('### Fase ',1)[0].split('\n---',1)[0]
        paths=[]
        for line in section.splitlines():
            if line.startswith(('**Arquivos','**Pastas','| `')):paths.extend(re.findall(r'`([^`]+)`',line))
        missing=[p for p in paths if not (ROOT/p).exists() and not (ROOT/'src/nablamath'/p).exists()]
        phases[str(number)]={'paths':len(paths),'missing':missing,'coverage_fraction':(len(paths)-len(missing))/len(paths) if paths else None}
    criteria=[]
    def item(name,value,evidence):criteria.append({'criterion':name,'status':'supported' if value is True else 'not_demonstrated' if value is False else 'unverified','evidence':evidence})
    item('priority_paths_present',all(not r['missing'] for r in phases.values()),'Path diagnostic only; does not establish scientific completeness')
    if junit:
        tree=ET.parse(junit).getroot();suites=list(tree.iter('testsuite'))
        failures=sum(int(s.get('failures','0'))+int(s.get('errors','0')) for s in suites)
        executed=sum(int(s.get('tests','0')) for s in suites)
        item('local_tests_pass',executed>0 and failures==0,{'tests':executed,'failures':failures,'source':str(junit)})
    else:item('local_tests_pass',None,'No test report supplied')
    ci=read(windows) if windows else {}
    item('windows_python_matrix',ci.get('python_matrix_passed'),ci or 'Awaiting native CI result')
    item('windows_installer',ci.get('installer_passed'),ci or 'Awaiting native packaged-executable and Inno Setup checks')
    item('independent_solver_measurements',bench['summary']['sympy']['solved']>0 and bench['summary']['z3']['solved']>0,bench['summary'])
    item('advanced_problem_difficulty',bench['advanced_tasks_observed']>0,{'backend_challenges_observed':bench['advanced_tasks_observed'],'scope':bench['scope']})
    gain=experiment['positive_gain_observed'] and experiment['gain_demonstrated_in_every_seed'] and all(r['paired_exact_p_value']<=.05/len(experiment['runs']) for r in experiment['runs'])
    item('external_learning_gain',gain,{'mean_accuracy_gain':experiment['mean_accuracy_gain'],'experiment_id':experiment['experiment_id']})
    item('frontier_model_gain',False,'Experiment uses an open small numeric regressor, not a frontier language model')
    item('global_scientific_novelty',discovery['global_novelty_established'],'Local supplied literature snapshot only')
    item('general_recursive_self_improvement',False,'Two bounded numerical-policy generations are not arbitrary general self-improvement')
    item('experimental_physical_validation',summary['experimental_validation'],'Disciplinary examples and instrument fixture are synthetic')
    item('independent_scientific_peer_review',reviews['identity_and_expertise_independently_authenticated'],'Review declarations are local synthetic demonstrations')
    item('versioned_knowledge_replay',summary['provenance_valid'] and summary['concurrent_claims_preserved']>0,summary)
    return {'priority_path_diagnostics':phases,'criteria':criteria,
            'all_research_criteria_demonstrated':all(c['status']=='supported' for c in criteria),
            'vision_completion_percent':None,'reason':'No validated mapping from these measurements to the full 2026–2056 scientific vision. F13 remains open-ended.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--research',type=Path,required=True);parser.add_argument('--benchmark',type=Path,required=True)
    parser.add_argument('--learning',type=Path,required=True);parser.add_argument('--junit',type=Path)
    parser.add_argument('--windows',type=Path);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--require-all',action='store_true')
    args=parser.parse_args();report=assess(args.research,args.benchmark,args.learning,junit=args.junit,windows=args.windows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'all_research_criteria_demonstrated':report['all_research_criteria_demonstrated'],
                      'unmet':[c['criterion'] for c in report['criteria'] if c['status']!='supported']}))
    raise SystemExit(1 if args.require_all and not report['all_research_criteria_demonstrated'] else 0)
