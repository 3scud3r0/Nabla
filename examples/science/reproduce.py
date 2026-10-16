"""Auditable finite experiments with installed Nabla; no optional dependencies.

Run: python examples/science/reproduce.py NEW_OUTPUT_DIRECTORY
Every operation has an explicit independent reference, not an output snapshot.
"""
from __future__ import annotations
import argparse
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler

from nablamath import __version__, calculate
from nablamath.calc import CalculationSession, Notebook
from nablamath.calc.catalog import catalog
from nablamath.core.units import Quantity, KILOMETER, HOUR, METER, SECOND
from nablamath.desktop.app import make_server
from nablamath.pipeline.scientific_cycle import build_scientific_artifact, replay_scientific_artifact
from nablamath.storage import save_result, load_result
from nablamath.store.backup import backup_database, restore_database

# Values below are derived from the displayed inputs by elementary arithmetic,
# closed formulas, enumerating tiny finite sets, or the analytic decay solution.
# They must never be regenerated from Nabla output.
REFERENCES = {
 'analysis_integral': ('integral', '1/3'),
 'analysis_pade': ('numerator', ['1','1/2']),
 'bayes': ('posterior.b', '3/4'), 'binomial': ('value', 15),
 'certified_integral': ('estimate','1/3'), 'condition': ('condition_inf','2'),
 'conic': ('classification','ellipse'), 'distribution': ('cdf',.5),
 'evaluate': ('value','4'), 'factor': ('roots',['-1','1']),
 'ff_extension': ('field_size',4), 'ff_irreducible': ('irreducible',True),
 'geometry': ('twice_signed_area','4'),
 'graph_apsp': ('distances.0.1','3/2'),
 'graph_assignment': ('minimum_cost','1'),
 'graph_bellman_ford': ('distances.t','3/2'),
 'graph_matching': ('cardinality',1), 'graph_max_flow': ('value','3/2'),
 'graph_mst': ('weight','3/2'), 'graph_scc': ('components',[['s'],['t']]),
 'least_squares': ('coefficients',['1','2']), 'limit': ('value','2'),
 'linear_regression': ('slope','2'),
 'markov': ('distribution',{'0':'3/8','1':'5/8'}),
 'markov_hitting': ('states.0.conditional_mean','2'),
 'markov_rewards': ('values',['4']),
 'markov_stationary': ('closed_classes.0.distribution',['1/2','1/2']),
 'matrix_inverse': ('inverse',[['-2','1'],['3/2','-1/2']]),
 'matrix_properties': ('determinant','-2'), 'maximum_flow': ('value','1'),
 'nt_discrete_log': ('exponent',3), 'nt_factorization': ('totient',4),
 'nt_modular_roots': ('roots',[3,4]), 'nt_pell': ('x','3'),
 'nt_primality': ('prime',True), 'nt_primitive_root': ('generator',3),
 'optimize': ('value','5'), 'polynomial_range': ('enclosure',{'lower':'0','upper':'1'}),
 'prob_binomial': ('mass',[[0,'1/4'],[1,'1/2'],[2,'1/4']]),
 'prob_convolution': ('mass',[[0,'1/4'],[1,'1/2'],[2,'1/4']]),
 'prob_dirichlet': ('predictive',['2/3','1/3']),
 'prob_distribution': ('variance','1/4'), 'prob_hypergeometric': ('probability','2/9'),
 'prob_joint': ('independent',True), 'prob_poisson_binomial': ('variance','1/2'),
 'prob_propagate': ('distribution',['1','0']), 'prob_stationary': ('stationary',['1/3','2/3']),
 'quadratic_optimize': ('value','-3'), 'rational_compare': ('equal_on_common_domain',True),
 'rational_limit': ('result.status','negative_infinity'), 'sat': ('assignment_verified',True),
 'series': ('coefficients',['1','1','1','1','1']),
 'shortest_paths': ('distances.c','5/2'), 'solve_linear': ('particular',['2','1']),
 'statistics': ('mean','2'), 'time_series': ('intercept_slope',[1.,1.]),
 'topological_sort': ('order',['a','b']),
}
SPECIAL = {'analysis_extrema','analysis_interval','analysis_root','approximate',
           'certified_function','differentiate','integrate','lu','orthogonal_basis',
           'simplify','ode','ode_adaptive'}


def require(condition, message):
    # Deliberately remains active under python -O.
    if not condition:
        raise AssertionError(message)


def lookup(data, path):
    for key in path.split('.'):
        data = data[int(key)] if isinstance(data,list) else data[key]
    return data


def expression_value(node, x):
    """Tiny independent AST interpreter for these polynomial reference checks."""
    if node['kind']=='number': return F(node['numerator'],node['denominator'])
    if node['kind']=='symbol':
        require(node['name']=='x','Unexpected polynomial variable')
        return F(x)
    a,b=expression_value(node['left'],x),expression_value(node['right'],x)
    op=node['op']
    if op=='+': return a+b
    if op=='-': return a-b
    if op=='*': return a*b
    if op=='/': return a/b
    if op=='**': return a**b.numerator
    raise ValueError('Unknown AST operation')


def reference_check(name, result):
    if name in REFERENCES:
        path, expected=REFERENCES[name]
        require(lookup(result,path)==expected, f'{name}: reference mismatch at {path}')
        return {'kind':'closed-form/finite-reference','path':path,'expected':expected}
    require(name in SPECIAL, 'Operation lacks an independent reference: '+name)
    if name=='analysis_extrema':
        require(F(result['minimum']['lower'])<=0<=F(result['minimum']['upper']), 'Minimum enclosure')
        require(F(result['maximum']['lower'])<=1<=F(result['maximum']['upper']), 'Maximum enclosure')
    elif name=='analysis_interval':
        require(F(result['enclosure']['lower'])<=-1 and F(result['enclosure']['upper'])>=2,'Range of x²−2 on [1,2]')
    elif name=='analysis_root':
        lo,hi=map(F,(result['interval']['lower'],result['interval']['upper']))
        require(lo*lo<=2<=hi*hi and hi-lo<=F(1,4),'Bisection bracket for sqrt(2)')
    elif name=='approximate':
        require(abs(F(result['decimal'])-F(1,3))==F(result['absolute_error']),'Decimal rounding error')
    elif name=='certified_function':
        lo,hi=map(F,(result['enclosure']['lower'],result['enclosure']['upper']))
        # Independent positive-term series and geometric upper bound for exp(1).
        lower=sum((F(1,math.factorial(k)) for k in range(21)),F(0))
        upper=lower+F(1,math.factorial(21))*F(22,21)
        require(lo<=lower<=upper<=hi,'Certified exp(1) enclosure')
    elif name in {'differentiate','integrate','simplify'}:
        field={'differentiate':'expression','integrate':'antiderivative','simplify':'expression'}[name]
        for x in (-2,0,2,3):
            expected={'differentiate':2*F(x),'integrate':F(x)**3/3,'simplify':F(x)}[name]
            require(expression_value(result[field],x)==expected, name+' polynomial reference')
    elif name=='lu':
        L,U,P=(result[k]['rows'] for k in ('lower','upper','permutation'))
        A=[[0,1],[1,2]]
        product=lambda a,b:[[sum(F(a[i][k])*F(b[k][j]) for k in range(2)) for j in range(2)] for i in range(2)]
        require(product(L,U)==product(P,A),'PA=LU exact residual')
    elif name=='orthogonal_basis':
        require(len(result)==2 and sum(F(a)*F(b) for a,b in zip(*result))==0,'Orthogonality')
        require(all(any(F(x)!=0 for x in row) for row in result),'Nonzero basis vectors')
    elif name in {'ode','ode_adaptive'}:
        tolerance=2e-5 if name=='ode' else 2e-8
        error=abs(result['final'][0]-math.exp(-1))
        require(error<tolerance,'Analytic exponential-decay error')
        return {'kind':'analytic-reference','expected':math.exp(-1),'absolute_tolerance':tolerance,'observed_error':error}
    return {'kind':'independent-identity-or-enclosure','passed':True}


def hypothesis_experiment(root, session):
    # Known synthetic law, fixed train/holdout split; no novelty is claimed.
    training=[(x,1+2*x) for x in range(8)]
    holdout=[(x,1+2*x) for x in range(20,28)]
    fitted=session.execute('least_squares',predictors=[[x] for x,y in training],response=[y for x,y in training]).to_data()['result']
    a,b=map(F,fitted['coefficients'])
    errors=[a+b*x-y for x,y in holdout]
    wrong_errors=[a+(b+1)*x-y for x,y in holdout]
    require(all(e==0 for e in errors) and any(e!=0 for e in wrong_errors),'Reserved-point positive/negative controls')
    data={'source':'synthetic known law y=1+2x','train':training,'holdout':holdout,'fit':fitted,
          'holdout_residuals':[str(e) for e in errors],'wrong_law_residuals':[str(e) for e in wrong_errors],
          'empirical_validation':False,'novel_discovery':False}
    (root/'hypothesis.json').write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    return {'training_points':8,'reserved_points':8,'exact_recovery':True,'wrong_law_rejected':True}


def finite_campaign(session):
    count=0
    for n in range(128):
        prime=n>=2 and all(n%d for d in range(2,math.isqrt(n)+1))
        require(session.execute('nt_primality',n=n).to_data()['result']['prime']==prime,'Trial-division reference')
        count+=1
    for p in (3,5,7,11,13):
        for a in range(p):
            expected=[x for x in range(p) if x*x%p==a]
            require(session.execute('nt_modular_roots',a=a,prime=p).to_data()['result']['roots']==expected,'Enumerated modular roots')
            count+=1
    for n in range(9):
        masses=session.execute('prob_binomial',trials=n,success_probability='1/2').to_data()['result']['mass']
        require(masses==[[k,str(F(math.comb(n,k),2**n))] for k in range(n+1)],'Independent binomial formula')
        count+=1
    return {'independently_checked_cases':count}


def forge_experiment(root):
    from nablamath.forge import FAMILIES, generate_task
    from nablamath.forge.solvers import solve_task
    from nablamath.verify.trace import verify_candidate
    rows=[]
    for family in FAMILIES:
        generated=generate_task(family,seed=42,size=3)
        answers={strategy:solve_task(generated.task,strategy) for strategy in ('exact','alternate')}
        verified={strategy:verify_candidate(generated.task,answer).valid for strategy,answer in answers.items()}
        require(all(verified.values()),'Forge verification failed: '+family)
        rows.append({'family':family,'problem':generated.task.to_data(),'answers':answers,'verified':verified})
    (root/'forge.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    return {'families':len(rows),'solver_verifier_runs':2*len(rows),'seed':42,'size':3}


def negative_controls(session, root):
    invalid=[('evaluate',{'source':'1/x','values':{'x':0}}),
             ('matrix_inverse',{'matrix':[[1,1],[1,1]]}),
             ('nt_primality',{'n':2**64}),
             ('ff_extension',{'prime':2,'modulus':[0,0,1],'element':[0,1]}),
             ('prob_distribution',{'mass':[[0,'1/3']]}),
             ('graph_assignment',{'costs':[[0]*13 for _ in range(13)]}),
             ('nt_primality',{'n':97,'unrecognized':1})]
    rejected=[]
    for name,arguments in invalid:
        try: session.execute(name,**arguments)
        except (ValueError,ZeroDivisionError): rejected.append(name)
        else: raise AssertionError('Invalid request accepted: '+name)
    require((Quantity(72,KILOMETER)/Quantity(1,HOUR)).to(METER/SECOND).value==20,'SI speed conversion')
    try: Quantity(1,METER).to(SECOND)
    except ValueError: rejected.append('incompatible_SI_dimensions')
    else: raise AssertionError('Incompatible SI dimensions accepted')
    data=json.loads((root/'catalog.notebook.json').read_text(encoding='utf-8'))
    data['cells'][0]['calculation']['result']={'forged':True}
    tampered=root/'tampered.notebook.json'
    tampered.write_text(json.dumps(data),encoding='utf-8')
    try: Notebook.load(tampered).replay()
    except (ValueError,KeyError): rejected.append('tampered_notebook')
    else: raise AssertionError('Tampered notebook accepted')
    return {'rejected':rejected,'count':len(rejected),'speed_m_per_s':'20'}


def interfaces(root, cases):
    client=build_opener(ProxyHandler({}))
    server,_=make_server(root/'desktop')
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with client.open(base+'/',timeout=5) as r:page=r.read().decode('utf-8')
        token=page.split("const auth='",1)[1].split("'",1)[0]
        payload={'operation':'analysis_integral','arguments':cases['analysis_integral']}
        request=Request(base+'/api/calculate',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-Nabla-Token':token,'Origin':base})
        with client.open(request,timeout=5) as r: desktop=json.load(r)
        require(desktop['result']['integral']=='1/3','Desktop independent integral reference')
        saved_request=Request(base+'/api/save-calculation',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-Nabla-Token':token,'Origin':base})
        with client.open(saved_request,timeout=5) as r:saved=json.load(r)
        require(Notebook.load(saved['path']).replay()==1,'Desktop persistent notebook replay')
        try:client.open(Request(base+'/api/catalog',headers={'X-Nabla-Token':'wrong'}),timeout=5)
        except HTTPError as error:require(error.code==403,'Invalid token response')
        else:raise AssertionError('Invalid token accepted')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=5)
    args=[sys.executable,'-I','-m','nablamath.cli','calc','analysis_integral','--arguments',json.dumps(cases['analysis_integral'])]
    completed=subprocess.run(args,capture_output=True,text=True,check=True,timeout=20)
    cli=json.loads(completed.stdout)
    require(cli==desktop,'Installed CLI and HTTP receipts differ')
    result=calculate('(x+x)/x',{'x':3})
    database=root/'results.sqlite3'
    save_result(database,result)
    backup_database(database,root/'backup.sqlite3')
    restore_database(root/'backup.sqlite3',root/'restored.sqlite3')
    require(load_result(root/'restored.sqlite3',result.content_id)==result.to_data(),'SQLite restore identity')
    return {'http_calculation':True,'cli_identical_receipt':True,'desktop_saved_notebook':True,
            'invalid_token_rejected':True,'sqlite_backup_restore':True}


def run(destination, *, cases_path=None):
    cases_path=Path(cases_path) if cases_path else Path(__file__).with_name('catalog_cases.json')
    cases=json.loads(cases_path.read_text(encoding='utf-8'))
    names={row['name'] for row in catalog()['operations']}
    require(set(cases)==names==set(REFERENCES)|SPECIAL,'Catalog/inputs/references coverage mismatch')
    root=Path(destination);root.mkdir(parents=True,exist_ok=False)
    session=CalculationSession();notebook=Notebook('69 bounded operations with independent references')
    rows=[]
    for name,arguments in cases.items():
        receipt=session.execute(name,**arguments);data=receipt.to_data()
        reference=reference_check(name,data['result'])
        require(data['formal_proof'] is False,'Computation mislabelled as formal proof')
        notebook.append(receipt)
        rows.append({'operation':name,'reference':reference,'receipt_id':data['content_id'],'passed':True})
    notebook.save(root/'catalog.notebook.json')
    require(Notebook.load(root/'catalog.notebook.json').replay()==len(cases),'Complete notebook replay')
    forge=forge_experiment(root)
    study=hypothesis_experiment(root,session)
    campaign=finite_campaign(session)
    controls=negative_controls(session,root)
    interface=interfaces(root,cases)
    artifacts=[]
    for family in ('linear_system','polynomial_integral'):
        artifact=build_scientific_artifact(family=family,seed=21,size=2,license_id='MIT',provenance='known synthetic scientist demonstration')
        replay=replay_scientific_artifact(artifact)
        (root/(family+'.artifact.json')).write_text(json.dumps(artifact.to_data(),indent=2)+'\n',encoding='utf-8')
        for node in artifact.nodes:
            if node.kind=='figure':(root/(family+'.svg')).write_text(node.payload['svg'],encoding='utf-8')
            if node.kind=='document':(root/(family+'.html')).write_text(node.payload['html'],encoding='utf-8')
        artifacts.append(replay)
    report={'schema_version':1,'version':__version__,'passed':True,'catalog_operations':len(rows),
            'operations':rows,'notebook_replayed_cells':len(rows),'forge':forge,'hypothesis':study,'finite_campaign':campaign,
            'negative_controls':controls,'interfaces':interface,'artifacts':artifacts,
            'limitations':['Finite examples do not prove correctness for all possible inputs.',
                           'Synthetic data; no empirical physical validation or novel discovery.',
                           'Floating ODE references have explicit tolerances; they are not exact proofs.',
                           'Formal compilation and kernel axiom audit are separate evidence.',
                           'No GPU, external services, public federation or Windows execution in this experiment.']}
    files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file()}
    report['artifact_sha256']=files
    (root/'report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    lines=['# Nabla — demonstração científica reproduzível','',f'Versão: {__version__}. {len(rows)} operações executadas com referências independentes e notebook reexecutado.',
           '',f"Campanha finita: {campaign['independently_checked_cases']} casos. Controles negativos rejeitados: {controls['count']}.",
           '', 'Lei sintética y=1+2x recuperada em 8 pontos de treino e verificada em 8 pontos reservados; uma lei errada foi rejeitada.',
           '', '| Operação | Referência | Resultado |','|---|---|---|']
    lines += [f"| `{r['operation']}` | {r['reference']['kind']} | passou |" for r in rows]
    lines += ['', '## Limites', '']+[f'- {v}' for v in report['limitations']]
    (root/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    report=run(args.destination)
    print(json.dumps({'passed':report['passed'],'version':report['version'],'operations':report['catalog_operations'],
                      'reference_cases':report['finite_campaign']['independently_checked_cases']}))
