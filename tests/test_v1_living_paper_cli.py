"""Real CLI construction, extraction and portable native-equation replay."""
import json
import subprocess
import sys
import pytest
pytest.importorskip('typst');pytest.importorskip('pypdf');pytest.importorskip('qrcode')
from nablamath.calc import CalculationSession
from nablamath.artifacts.bundle import create_bundle


def test_living_paper_build_inspect_extract(tmp_path):
    bundle=create_bundle([CalculationSession().execute('beta_binomial',successes=2,trials=3).to_data()])
    artifact=tmp_path/'run.json';artifact.write_text(json.dumps(bundle))
    template=tmp_path/'paper.typ';template.write_text('= CLI paper\n#nabla-val("mean")\n')
    bindings=tmp_path/'bindings.json';bindings.write_text(json.dumps({'mean':'/receipts/0/result/mean'}))
    output=tmp_path/'paper.pdf'
    result=subprocess.run([sys.executable,'-m','nablamath.cli.main','living-paper','build',str(template),'--artifact',str(artifact),'--output',str(output),'--bindings',bindings.read_text()],capture_output=True,text=True,timeout=60)
    assert result.returncode==0,result.stderr
    assert output.read_bytes().startswith(b'%PDF')
    extracted=tmp_path/'extracted.json'
    inspected=subprocess.run([sys.executable,'-m','nablamath.cli.main','living-paper','inspect',str(output),'--extract',str(extracted)],capture_output=True,text=True,timeout=60)
    assert inspected.returncode==0,inspected.stderr
    assert json.loads(extracted.read_text())==bundle


def test_portable_source_replay_and_editorial_checklist(tmp_path):
    pytest.importorskip('sympy');pytest.importorskip('pymupdf')
    from nablamath.publishing.living_papers_compiler import ScientificPaper,ScientificPaperProject,PublicationRecompiler,EditorialChecklist
    paper=ScientificPaper('Portable mathematics',authors=['Nabla'],abstract='Closed-expression equations and reproducible data.',bibliography=[{'id':'ref','title':'Reference','authors':['Author'],'year':2026,'type':'article'}])
    paper.section('Result','sec:result').equation('x*x+1',['x'],'eq:result').citation(['ref'])
    bundle=create_bundle([CalculationSession().execute('beta_binomial',successes=2,trials=3).to_data()])
    built=ScientificPaperProject(paper,bundle,tmp_path/'project').build()
    replay=PublicationRecompiler.typst(built.source,built.pdf)
    assert replay['text_matches'] and replay['page_count_matches']
    checked=EditorialChecklist.inspect(paper,built.pdf,artifact=bundle)
    assert checked['automated_checks_passed'],checked['findings']
    assert not checked['pdfa_compliance_established']
