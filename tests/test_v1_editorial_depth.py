"""Native equations, reference semantics, archives and measured PDF layouts."""
import json
from pathlib import Path
import pytest
pytest.importorskip('sympy');pytest.importorskip('typst');pytest.importorskip('pypdf')
from nablamath.calc import CalculationSession
from nablamath.artifacts.bundle import create_bundle
from nablamath.publishing.living_papers_compiler import (
    ScientificNumberFormatter,ScientificEquation,LabelRegistry,Bibliography,
    ScientificPaper,ScientificPaperProject,PaperArchive,PDFQualityInspector,
    PaperRevisionLedger,PublicationDataInspector,VerifiablePDFWriter,
)


def test_decimal_significance_and_uncertainty_carry():
    assert ScientificNumberFormatter.significant('1/3',4)=='0.3333'
    assert ScientificNumberFormatter.significant('12345',3)=='1.23e4'
    result=ScientificNumberFormatter.uncertainty('12.3456','.0789',unit='m')
    assert result['text']=='12.346 ± 0.079 m'
    assert ScientificNumberFormatter.uncertainty('1.234','.0999')['uncertainty']=='0.10'
    with pytest.raises(ValueError):ScientificNumberFormatter.significant(float('nan'))


def test_equation_syntax_escape_and_cross_references():
    equation=ScientificEquation('exp(-x*x/2)/sqrt(2*pi)',['x'])
    assert '\\frac' in equation.latex() and '#math.equation' in equation.typst()
    with pytest.raises(ValueError):ScientificEquation('__import__("os")',['x'])
    assert '$ sin(theta) $' in ScientificEquation('sin(theta)',['theta']).typst()
    labels=LabelRegistry();labels.reference('eq:future')
    with pytest.raises(ValueError):labels.validate_all()
    labels.define('eq:future','equation');assert labels.validate_all()['labels']['eq:future']['number']==1
    with pytest.raises(ValueError):labels.define('eq:future','equation')


def test_native_paper_pdf_attachments_archives_and_revision_chain(tmp_path):
    pytest.importorskip('pymupdf')
    bibliography=[{'id':'gauss','title':'A reference & a title','authors':['A. Author'],'year':2020,
                   'type':'article','doi':'10.1000/example','container':'Journal'}]
    paper=ScientificPaper('Nabla — artigo com equações',authors=['Laboratório Nabla'],
        abstract='Uma referência matemática independente e dados auditáveis.',bibliography=bibliography,language='pt')
    paper.section('Resultados','sec:results').paragraph('A média do experimento é {{mean}}.')
    paper.equation('exp(-x*x/2)/sqrt(2*pi)',['x'],'eq:normal')
    paper.table(['Grandeza','Valor'],[['Média','{{mean}}']],'Resultado auditável','tab:mean')
    paper.citation(['gauss']).reference('eq:normal',prefix='Equação: ').footnote('Nota editorial segura.')
    ast=paper.to_data();assert ScientificPaper.from_data(ast).to_data()==ast
    bundle=create_bundle([CalculationSession().execute('beta_binomial',successes=2,trials=3).to_data()])
    project=ScientificPaperProject(paper,bundle,tmp_path/'project',bindings={'mean':'/receipts/0/result/mean'})
    built=project.build();assert not project.build().changed
    assert VerifiablePDFWriter.inspect(built.pdf)['bundle']==bundle
    quality=PDFQualityInspector.inspect(built.pdf,experiment_hash=bundle['content_id'])
    assert quality['layout_checks_passed'],quality['issues']
    preview=PDFQualityInspector.preview(built.pdf,tmp_path/'preview.png')
    assert preview.read_bytes().startswith(b'\x89PNG')
    extracted=PublicationDataInspector.extract(built.pdf,tmp_path/'extracted.json')
    assert extracted['experiment_hash']==bundle['content_id']
    assert PublicationDataInspector.compare(built.pdf,built.pdf)['identical_experiment']
    assert len(PublicationDataInspector.receipt_index(built.pdf)['receipts'])==1
    ledger=PaperRevisionLedger(tmp_path/'revisions.jsonl')
    first=ledger.append(built.pdf,built.source,timestamp='2026-10-17T00:00:00Z')
    second=ledger.append(built.pdf,built.source,expected_tip=first['content_id'],timestamp='2026-10-17T00:00:01Z')
    assert len(ledger.records(expected_tip=second['content_id']))==2
    assert not ledger.changes(0,1)['pdf_changed']
    archive=PaperArchive.create(built.pdf.parent,tmp_path/'paper.zip')
    restored=PaperArchive.extract(tmp_path/'paper.zip',tmp_path/'restored')
    assert restored['files']>5 and (tmp_path/'restored/paper.pdf').read_bytes()==built.pdf.read_bytes()
    same=PaperArchive.create(built.pdf.parent,tmp_path/'paper2.zip')
    assert same['sha256']==archive['sha256']
