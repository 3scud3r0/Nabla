"""Actual print output: mathematical typography, multipage tables and provenance."""
import importlib.util
import json
from pathlib import Path
import shutil
import pytest


def test_typed_living_paper_fraction_vector_matrix_and_literal_metadata(tmp_path):
    pytest.importorskip('typst');pypdf=pytest.importorskip('pypdf')
    from nablamath.artifacts.bundle import create_bundle
    from nablamath.calc.receipt import receipt
    from nablamath.publishing import TypstCompiler,verify_publication
    bundle=create_bundle([receipt('layout.fixture',{}, {'ratio':'1/3','vector':[1.,2.],
        'matrix':[[1,2],[3,4]],'raw_text':'#panic("data is literal")','large':list(range(500))})])
    paper=TypstCompiler().compile(bundle,tmp_path/'paper.pdf',title='TITLE IDENTIFIER · resultados',
        authors=['Demonstração sintética'],abstract='Frações exatas, matrizes e dados literais.',language='pt')
    assert verify_publication(paper.pdf)
    text='\n'.join(page.extract_text() for page in pypdf.PdfReader(paper.pdf).pages)
    assert 'IDENTIFIER' in text and 'data is literal' in text and '500 entries' in text
    manifest=json.loads(paper.manifest.read_text());root=tmp_path/'paper.pdf.history'/manifest['snapshot']
    data=json.loads((root/'experiment.json').read_text())
    values={entry['name']:entry['value'] for entry in data['results']}
    assert values['ratio']=={'kind':'exact','numerator':'1','denominator':'3'}
    assert values['matrix']['kind']=='matrix' and values['vector']['kind']=='vector'
    assert json.loads((root/'bundle.json').read_text())==bundle


@pytest.mark.parametrize('backend',['typst','latex'])
def test_real_multipage_table_repeats_headers_and_preserves_all_rows(tmp_path,backend):
    pypdf=pytest.importorskip('pypdf')
    if backend=='typst' and not shutil.which('typst') and importlib.util.find_spec('typst') is None:
        pytest.skip('Typst renderer is optional')
    if backend=='latex' and not shutil.which('pdflatex'):
        pytest.skip('LaTeX renderer is optional')
    from examples.science.editorial_showcase import demonstration_document
    from nablamath.documents.pdf_builder import build_pdf
    document,_=demonstration_document()
    pdf=build_pdf(document,tmp_path/(backend+'.pdf'),backend)
    reader=pypdf.PdfReader(pdf);texts=[page.extract_text() for page in reader.pages]
    assert 2<=len(texts)<=8
    assert all(document.content_id in ''.join(text.split()) for text in texts)
    assert '0.00091188' in '\n'.join(texts)
    table_pages=[text for text in texts if any(value in text for value in ['0.904837','0.367879','0.049787','0.006737','0.000911'])]
    assert len(table_pages)>=2 and all('Tempo' in ''.join(text.split()) and 'RK4' in text for text in table_pages)


def test_older_published_artifacts_verify_with_their_original_print_profile(tmp_path):
    import hashlib
    from nablamath.documents.document_model import Document,Section
    from nablamath.documents.publication import publish,verify_publication
    from nablamath.documents.legacy_exporters import to_html,to_latex,to_typst
    document=Document('Legacy paper',(Section('Result','A preserved historical result'),))
    root=tmp_path/'legacy';publish(document,root)
    manifest=json.loads((root/'manifest.json').read_text());manifest.pop('render_profile')
    for suffix,exporter in [('html',to_html),('tex',to_latex),('typ',to_typst)]:
        path=root/('document.'+suffix);path.write_text(exporter(document),encoding='utf-8')
        manifest['files'][path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    (root/'manifest.json').write_text(json.dumps(manifest))
    assert verify_publication(root)
    manifest['render_profile']='unknown';(root/'manifest.json').write_text(json.dumps(manifest))
    assert not verify_publication(root)


def test_signed_living_paper_has_readable_audit_footer_on_every_page(tmp_path):
    pytest.importorskip('typst');pypdf=pytest.importorskip('pypdf');pytest.importorskip('cryptography')
    from nablamath.artifacts.bundle import create_bundle
    from nablamath.calc import CalculationSession
    from nablamath.federation.crypto_registry import CryptoRegistry,generate_key,public_key_hex,sign
    from nablamath.publishing import TypstCompiler,verify_publication
    bundle=create_bundle([CalculationSession().execute('binomial',n=5,k=2).to_data()])
    key=generate_key();trust=CryptoRegistry();trust.pin('layout-test',public_key_hex(key));signature=sign(bundle,key,signer='layout-test')
    template=tmp_path/'pages.typ';template.write_text('#for i in range(3) [\n= Audited page #i\nResult: {{value}}\n#if i < 2 { pagebreak() }\n]')
    paper=TypstCompiler(trust=trust,require_signature=True).compile(bundle,tmp_path/'signed.pdf',template=template,signature=signature)
    pages=pypdf.PdfReader(paper.pdf).pages
    assert len(pages)==3 and verify_publication(paper.pdf,trust=trust,require_signature=True)
    for page in pages:
        text=''.join(page.extract_text().split())
        assert bundle['content_id'] in text and signature['signature'] in text
