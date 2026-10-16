"""Proof checking never clones packages or accepts a mismatched compiler."""
from pathlib import Path
import subprocess
import pytest
from nablamath.formal import lean_checker as checker
from nablamath.formal.statement import FormalStatement
from nablamath.formal.lean_bridge import translate_statement


@pytest.fixture
def project(tmp_path,monkeypatch):
    (tmp_path/'lean-toolchain').write_text('leanprover/lean4:v4.34.0')
    (tmp_path/'lakefile.toml').write_text('name = "fixture"')
    monkeypatch.setattr(checker,'find_lake',lambda _:tmp_path/'bin/lake')
    return tmp_path


def test_missing_build_is_diagnosed_without_launching_any_process(project,monkeypatch):
    def unexpected(*a,**kw):
        pytest.fail('An absent Mathlib must not start Lake or Lean')
    monkeypatch.setattr(checker,'run_lean_process',unexpected)
    result=checker.check_lean(translate_statement(FormalStatement.equality('x+0','x')),project)
    assert result.status=='unavailable'
    assert 'setup_formal.sh' in result.diagnostics


def test_offline_checker_uses_only_built_paths_and_rejects_wrong_version(project,monkeypatch):
    artifact=project/'.lake/packages/mathlib/.lake/build/lib/lean/Mathlib/Tactic.olean'
    artifact.parent.mkdir(parents=True)
    artifact.touch()
    calls=[]
    monkeypatch.setenv('LEAN_PATH','/untrusted')
    monkeypatch.setenv('LEAN_SRC_PATH','/untrusted')
    def wrong_version(command,**kwargs):
        calls.append((command,kwargs))
        return subprocess.CompletedProcess(command,0,'Lean (version 4.33.0, fixture)','')
    monkeypatch.setattr(checker,'run_lean_process',wrong_version)
    result=checker.check_lean(translate_statement(FormalStatement.equality('x+0','x')),project)
    assert result.status=='unavailable'
    assert 'does not match' in result.diagnostics
    assert len(calls)==1
    assert calls[0][0]==[str(project/'bin/lean'),'--version']
    assert '/untrusted' not in calls[0][1]['env']['LEAN_PATH']
    assert 'LEAN_SRC_PATH' not in calls[0][1]['env']


def test_legacy_checker_also_refuses_resolution_when_build_is_missing(project,monkeypatch):
    from nablamath.formal.check import verify_with_lean
    from nablamath.research import calculate
    monkeypatch.setattr(checker,'run_lean_process',lambda *a,**kw:pytest.fail('Must not start a resolver'))
    result=verify_with_lean(calculate('1+1',{}),project)
    assert not result.verified
    assert 'Mathlib build missing' in result.detail


@pytest.mark.parametrize('audit,accepted',[
    ('does not depend on any axioms',True),
    ("depends on axioms: [propext, Classical.choice, Quot.sound]",True),
    ('depends on axioms: [sorryAx]',False),
    ('',False),
])
def test_legacy_checker_requires_successful_axiom_audit(project,monkeypatch,audit,accepted):
    from nablamath.formal.check import verify_with_lean
    from nablamath.research import calculate
    artifact=project/'.lake/packages/mathlib/.lake/build/lib/lean/Mathlib/Tactic.olean'
    artifact.parent.mkdir(parents=True)
    artifact.touch()
    calls=[]
    def compile(command,**kwargs):
        calls.append(command)
        assert 'env' not in command
        if command[-1]=='--version':
            return subprocess.CompletedProcess(command,0,'Lean (version 4.34.0, fixture)','')
        source=Path(command[-1]).read_text()
        assert '#print axioms nablamath_instance' in source
        return subprocess.CompletedProcess(command,0,audit,'')
    monkeypatch.setattr(checker,'run_lean_process',compile)
    result=verify_with_lean(calculate('1+1',{}),project)
    assert result.verified is accepted
    assert len(calls)==2
