"""Regression tests for fail-closed reactive publication recovery.

The renderer/PDF transport is stubbed; these tests exercise the real revision
hashes, stable publication files, cache decision and recovery logic.
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from nablamath.artifacts.bundle import create_bundle
from nablamath.calc.receipt import receipt
from nablamath.publishing.living_papers_compiler import LivingPaperCompiler, VerifiablePDFWriter


@pytest.fixture
def paper(tmp_path, monkeypatch):
    bundle = create_bundle([receipt('publication-regression', {}, {'value': 7})])
    template = tmp_path / 'paper.typ'
    template.write_text('= Auditable paper\n', encoding='utf-8')
    output = tmp_path / 'paper.pdf'
    compiler = LivingPaperCompiler(template, bundle, output)

    def render(_bundle, destination, **kwargs):
        destination = Path(destination)
        destination.write_bytes(b'%PDF-1.7\nfixture-rendered\n')
        return SimpleNamespace(pdf=destination)

    def write(source, destination, _bundle, **kwargs):
        Path(destination).write_bytes(Path(source).read_bytes() + b'%verified-bundle\n')
        return {}

    def inspect(path, **kwargs):
        if not Path(path).read_bytes().startswith(b'%PDF-1.7'):
            raise ValueError('Damaged PDF')
        return {'bundle': bundle}

    monkeypatch.setattr(compiler.renderer, 'compile', render)
    monkeypatch.setattr(VerifiablePDFWriter, 'write', write)
    monkeypatch.setattr(VerifiablePDFWriter, 'inspect', inspect)
    return compiler, output


def test_cache_hit_requires_intact_pdf_and_audit(paper):
    compiler, output = paper
    initial = compiler.build()
    assert initial.changed
    assert not compiler.build().changed
    manifest = json.loads(initial.manifest.read_text(encoding='utf-8'))
    audit = output.parent / 'audit.html'
    assert manifest['audit_sha256'] == hashlib.sha256(audit.read_bytes()).hexdigest()
    assert manifest['artifact_sha256'] == hashlib.sha256(initial.artifact.read_bytes()).hexdigest()
    assert manifest['source_sha256'] == hashlib.sha256(initial.source.read_bytes()).hexdigest()


@pytest.mark.parametrize('damage', ['delete_audit', 'modify_audit', 'modify_pdf', 'delete_pdf'])
def test_stable_publication_is_recovered_from_verified_revision(paper, damage):
    compiler, output = paper
    initial = compiler.build()
    original_pdf = output.read_bytes()
    audit = output.parent / 'audit.html'
    original_audit = audit.read_bytes()

    if damage == 'delete_audit':
        audit.unlink()
    elif damage == 'modify_audit':
        audit.write_bytes(b'forged HTML')
    elif damage == 'modify_pdf':
        output.write_bytes(b'%PDF-1.7\nforged PDF')
    else:
        output.unlink()

    recovered = compiler.build()
    assert recovered.changed
    assert recovered.revision == initial.revision
    assert output.read_bytes() == original_pdf
    assert audit.read_bytes() == original_audit
    assert not compiler.build().changed


@pytest.mark.parametrize('name', ['paper.pdf', 'audit.html', 'artifact.json', 'compiled.source'])
def test_tampered_immutable_revision_fails_closed(paper, name):
    compiler, output = paper
    initial = compiler.build()
    original_pdf = output.read_bytes()
    immutable_file = initial.manifest.parent / name
    immutable_file.write_bytes(immutable_file.read_bytes() + b'ATTACK')
    (output.parent / 'audit.html').unlink()

    with pytest.raises(ValueError, match='altered'):
        compiler.build()
    assert output.read_bytes() == original_pdf


def test_missing_immutable_companion_fails_closed(paper):
    compiler, output = paper
    initial = compiler.build()
    (initial.manifest.parent / 'audit.html').unlink()
    (output.parent / 'audit.html').unlink()

    with pytest.raises(ValueError, match='incomplete'):
        compiler.build()


def test_rebuild_of_same_experiment_does_not_change_revision(paper):
    compiler, output = paper
    initial = compiler.build()
    (output.parent / 'audit.html').unlink()
    recovered = compiler.build()
    assert recovered.experiment_hash == initial.experiment_hash
    assert recovered.revision == initial.revision
    assert len(list((output.parent / 'paper.pdf.revisions').iterdir())) == 1


def test_watcher_repairs_deleted_audit_without_new_receipt(paper):
    compiler, output = paper
    with compiler.watch(delay=.05) as watcher:
        original = watcher.wait_for_build(count=1, timeout=10)
        audit = output.parent / 'audit.html'
        original_bytes = audit.read_bytes()
        audit.unlink()
        rebuilt = watcher.wait_for_build(count=2, timeout=10)
        assert rebuilt.revision == original.revision
        assert audit.read_bytes() == original_bytes
        assert watcher.status()['error'] is None
