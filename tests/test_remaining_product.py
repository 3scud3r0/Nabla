"""Cross-product replay, consent, accessibility and publication failure tests."""
import copy
import importlib.util
import json
from pathlib import Path
import threading
from urllib.request import Request, urlopen
import re
import pytest
from nablamath.core.semantic_ir import fingerprint
from nablamath.desktop.workflows import ExperimentWorkflow
from nablamath.documents.document_model import Document, Section, Table
from nablamath.reports.canonical_bundle import report_bundle, verify_report_bundle
from nablamath.graphics.scientific_renderer import DataCurve, ScientificPlot
from nablamath.viz.accessible import accessible_plot, replay_accessible_plot


def test_local_workflow_consent_replay_idempotency(tmp_path):
    flow=ExperimentWorkflow(tmp_path)
    with pytest.raises(ValueError): flow.execute('x+1',{'x':'2'})
    receipt=flow.execute('x+1',{'x':'2'},consent=True,reviewer='operator')
    assert flow.replay(receipt)
    assert receipt==flow.execute('x+1',{'x':'2'},consent=True,reviewer='operator')
    assert len(list(tmp_path.glob('*.json')))==1
    changed=copy.deepcopy(receipt);changed['record']['source']='x+2'
    changed['workflow_id']=fingerprint({k:v for k,v in changed.items() if k!='workflow_id'})
    assert not flow.replay(changed)
    changed=copy.deepcopy(receipt);changed['formal_proof']=True
    assert not flow.replay(changed)


def test_bundle_integrity_and_numbering():
    evidence={'claim':'supplied exact instance'};identifier=fingerprint(evidence)
    document=Document('Report',(Section('Results','Bounded result',(identifier,),
        tables=(Table('Measurements',('Value',),(('1',),),(identifier,)),)),))
    bundle=report_bundle(document,{identifier:evidence})
    assert verify_report_bundle(bundle)
    assert bundle['manifest']['numbering']==[dict(kind='table',number=1,section=1,local_index=1)]
    changed=copy.deepcopy(bundle);changed['exports']['latex']+='tampered'
    assert not verify_report_bundle(changed)
    with pytest.raises(ValueError):report_bundle(document,{identifier:{'changed':True}})


def test_accessible_scientific_uncertainty():
    curve=DataCurve('Samples',((0,1),(1,2)),'local-source',lower=(0,1),upper=(2,3),uncertainty_kind='absolute_bound')
    plot=ScientificPlot('<script>',(curve,),'Time','Value','Local source','Sampled data only')
    result=accessible_plot(plot)
    assert replay_accessible_plot(result,plot)
    assert '<th scope="col">' in result['html']
    assert '<script>' not in result['html']
    assert 'absolute_bound' in result['accessibility']['alternative_text']
    changed=copy.deepcopy(result);changed['svg']+='modified'
    assert not replay_accessible_plot(changed,plot)


def test_publication_signed_exact_dry_run_revocation():
    pytest.importorskip('cryptography')
    from nablamath.knowledge.identity import generate_signing_key, public_key_hex, PeerKey, PeerTrust
    from nablamath.publisher.authorization import publication_plan, authorize_plan, PublicationReview
    private=generate_signing_key();trust=PeerTrust((PeerKey('operator',public_key_hex(private)),))
    artifacts={'data.json':b'{}'}
    plan=publication_plan(artifacts,destination='staging/local',reviewer='operator',license_id='CC0-1.0')
    with pytest.raises(ValueError):authorize_plan(plan,private,peer_id='operator',now_unix=10,expires_unix=50)
    envelope=authorize_plan(plan,private,peer_id='operator',now_unix=10,expires_unix=50,redistributable=True)
    review=PublicationReview(trust)
    kwargs=dict(destination='staging/local',reviewer='operator',license_id='CC0-1.0',now_unix=11)
    receipt=review.dry_run(artifacts,envelope,**kwargs)
    assert receipt['submitted'] is False
    assert review.dry_run(artifacts,envelope,**kwargs)==receipt
    with pytest.raises(ValueError):review.dry_run({'data.json':b'changed'},envelope,**kwargs)
    review.revoke(plan['plan_id'])
    with pytest.raises(ValueError):review.dry_run(artifacts,envelope,**kwargs)


def test_http_experiment_equivalence_and_origin(tmp_path):
    from nablamath.desktop.app import make_server
    server,_=make_server(tmp_path)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        html=urlopen(base).read().decode()
        token=re.search(r"X-Nabla-Token':'([^']+)'",html).group(1)
        payload=dict(expression='x*x+1',values={'x':'2'},reviewer='operator',consent=True)
        request=Request(base+'/api/experiment',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-Nabla-Token':token,'Origin':base})
        receipt=json.load(urlopen(request))
        assert ExperimentWorkflow.replay(receipt)
        direct=ExperimentWorkflow(tmp_path/'direct').execute('x*x+1',{'x':'2'},consent=True,reviewer='operator')
        assert receipt==direct
    finally:
        server.shutdown();server.server_close();thread.join()


@pytest.mark.parametrize('name',['research_paper','engineering_report','teaching'])
def test_templates_export_and_optional_real_compilation(name,tmp_path):
    from nablamath.documents.pdf_builder import build_pdf
    root=Path(__file__).resolve().parents[1]
    document=Document.from_data(json.loads((root/'templates'/name/'example.document.json').read_text()))
    evidence=json.loads((root/'templates/research_paper/evidence.json').read_text())
    # Legacy template evidence is checked by its existing map; source exports are canonical.
    assert document.sections and evidence
    from nablamath.documents.exporters import to_html,to_latex,to_typst
    assert document.title in to_html(document)
    assert '\\end{document}' in to_latex(document)
    assert '#set page' in to_typst(document)
    if importlib.util.find_spec('typst'):
        assert build_pdf(document,tmp_path/(name+'.pdf')).read_bytes().startswith(b'%PDF-')
    import shutil
    if shutil.which('pdflatex'):
        assert build_pdf(document,tmp_path/(name+'-latex.pdf'),backend='latex').read_bytes().startswith(b'%PDF-')


def test_published_audited_example(tmp_path):
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('audited_example',root/'examples/audited_local_experiment.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert ExperimentWorkflow.replay(module.run(tmp_path))


def test_multimodal_plot_and_animation_integrity():
    from nablamath.graphics.scientific_export import export_scientific_plot,replay_scientific_export,export_animation
    curve=DataCurve('Samples',((0,1),(1,2)),'local-source')
    plot=ScientificPlot('Samples',(curve,),'Time','Value','Local source','Samples only')
    exported=export_scientific_plot(plot)
    assert replay_scientific_export(exported,plot)
    assert 'Samples,0,1' in exported['outputs']['csv']
    changed=copy.deepcopy(exported);changed['outputs']['csv']='tampered'
    assert not replay_scientific_export(changed,plot)
    animation=export_animation((plot,plot),(0,'1/2'))
    assert animation['times']==['0','1/2']
    with pytest.raises(ValueError):export_animation((plot,plot),(0,0))
    from itertools import repeat
    with pytest.raises(ValueError):export_animation(repeat(plot),repeat(0))


def test_website_status_is_matrix_derived():
    import subprocess
    root=Path(__file__).resolve().parents[1]
    script="""import fs from 'node:fs';
import assert from 'node:assert/strict';
import {deriveEvidenceStatus} from './website/src/evidence.js';
const m=JSON.parse(fs.readFileSync('docs/acceptance/evidence_matrix.json'));
const status=deriveEvidenceStatus(m);
assert.equal(status.planned+status.partial+status.validated,213);
assert.equal(status.validated,m.requirements.filter(r=>r.status==='validated').length);
m.requirements[1].id=m.requirements[0].id;
assert.throws(()=>deriveEvidenceStatus(m));
"""
    import shutil
    if shutil.which('node') is None:
        pytest.skip('Website evidence test requires optional Node runtime')
    subprocess.run(['node','--input-type=module','-e',script],cwd=root,check=True,capture_output=True,timeout=20)


@pytest.mark.parametrize('name',['first_problem.py','orbit_report.py','scientific_phases_5_8.py','frozen_evaluation.py','audited_local_experiment.py'])
def test_each_published_python_example_runs(name,tmp_path):
    import subprocess,sys
    root=Path(__file__).resolve().parents[1]
    import shutil
    if (name == 'scientific_phases_5_8.py' and shutil.which('typst') is None
            and importlib.util.find_spec('typst') is None):
        pytest.skip('Integrated PDF example requires optional documents extra or Typst executable')
    arguments=[] if name in {'first_problem.py','orbit_report.py'} else [str(tmp_path/'output')]
    subprocess.run([sys.executable,str(root/'examples'/name),*arguments],cwd=tmp_path,
                   capture_output=True,check=True,timeout=60)


def test_workflow_replay_rejects_rehashed_unrelated_report(tmp_path):
    receipt=ExperimentWorkflow(tmp_path).execute('x+1',{'x':'2'},consent=True,reviewer='operator')
    evidence_id=fingerprint(receipt['record'])
    altered=Document('Unrelated report',(Section('Results','This prose was not generated by the experiment.',(evidence_id,),
        tables=(Table('False assignments',('Variable','Value'),(('x','99'),),(evidence_id,)),)),))
    receipt['report']=report_bundle(altered,{evidence_id:receipt['record']})
    receipt['workflow_id']=fingerprint({k:v for k,v in receipt.items() if k!='workflow_id'})
    assert verify_report_bundle(receipt['report'])
    assert not ExperimentWorkflow.replay(receipt)


def test_workflow_normalizes_equivalent_rational_assignments(tmp_path):
    flow=ExperimentWorkflow(tmp_path)
    a=flow.execute('x+1',{'x':'4/2'},consent=True,reviewer='operator')
    b=flow.execute('x+1',{'x':'2'},consent=True,reviewer='operator')
    assert a==b
    assert flow.replay(a)


def test_workflow_rejects_power_amplification_before_calculation(tmp_path):
    flow=ExperimentWorkflow(tmp_path)
    with pytest.raises(ValueError,match='budget'):
        flow.execute('((x**32)**32)**32',{'x':'2'},consent=True,reviewer='operator')
    with pytest.raises(ValueError,match='budget'):
        flow.execute('x+1',{'x':2**4097},consent=True,reviewer='operator')
    assert not flow.replay({'record': {'source':'x+1','values':{'x':'2'}}})


def test_publication_rejects_unbounded_or_control_character_names():
    from nablamath.publisher.authorization import publication_plan
    kwargs=dict(destination='local',reviewer='operator',license_id='CC0-1.0')
    for name in ['x'*257,'data\x00json','data\njson',1]:
        with pytest.raises(ValueError):
            publication_plan({name:b'{}'},**kwargs)
