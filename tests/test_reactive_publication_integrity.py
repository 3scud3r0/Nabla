"""Regression coverage for the stable audit link and immutable paper revision."""
import json
import pytest

pytest.importorskip('typst')
pytest.importorskip('pypdf')
pytest.importorskip('qrcode')

from nablamath.artifacts.bundle import create_bundle
from nablamath.calc import CalculationSession
from nablamath.publishing.living_papers_compiler import LivingPaperCompiler


def compiler_fixture(tmp_path):
    template = tmp_path/'paper.typ'
    template.write_text('= Reproducible paper\n\nBounded synthetic result.\n', encoding='utf-8')
    bundle = create_bundle([CalculationSession().execute(
        'beta_binomial', successes=2, trials=3).to_data()])
    return LivingPaperCompiler(template, bundle, tmp_path/'paper.pdf')


@pytest.mark.parametrize('damage', ['missing_audit', 'modified_audit', 'modified_pdf'])
def test_cached_publication_repairs_both_stable_outputs(tmp_path, damage):
    compiler = compiler_fixture(tmp_path)
    first = compiler.build()
    assert first.changed
    expected_audit = (first.manifest.parent/'audit.html').read_bytes()
    expected_pdf = (first.manifest.parent/'paper.pdf').read_bytes()
    assert not compiler.build().changed
    if damage == 'missing_audit':
        (tmp_path/'audit.html').unlink()
    elif damage == 'modified_audit':
        (tmp_path/'audit.html').write_text('broken audit link')
    else:
        (tmp_path/'paper.pdf').write_bytes(b'not a PDF')
    recovered = compiler.build()
    assert recovered.changed
    assert recovered.revision == first.revision
    assert (tmp_path/'audit.html').read_bytes() == expected_audit
    assert (tmp_path/'paper.pdf').read_bytes() == expected_pdf
    assert not compiler.build().changed


@pytest.mark.parametrize('target', ['audit.html', 'artifact.json', 'compiled.source', 'paper.pdf'])
def test_corrupted_immutable_revision_fails_closed(tmp_path, target):
    compiler = compiler_fixture(tmp_path)
    first = compiler.build()
    (first.manifest.parent/target).write_bytes(b'corrupted immutable revision')
    with pytest.raises((ValueError, OSError), match='altered|invalid|Invalid|decode|PDF'):
        compiler.build()
