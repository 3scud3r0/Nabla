"""Finite capability queries and generated bidirectional evidence remain honest."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import pytest

from nablamath.cli import main
from nablamath.core.capabilities import ScientificCapabilities
from nablamath.core.semantic_contracts import canonical_payload
from nablamath.compatibility import support_contract

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'docs/acceptance/scientific_capabilities.yaml'


def load_tool(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_capability_manifest_paths_and_refusals():
    registry=ScientificCapabilities.load(MANIFEST)
    assert registry.validate_evidence(ROOT)
    profile=registry.query('rational-integration','integrate_rational')
    assert profile['absolute_tolerance']=='0'
    assert 'general_risch' in profile['refused']
    with pytest.raises(NotImplementedError):
        registry.query('rational-integration','general_risch')
    with pytest.raises(NotImplementedError):
        registry.query('unknown','integrate_rational')
    profile['operations'].append('general_risch')
    with pytest.raises(NotImplementedError):
        registry.query('rational-integration','general_risch')


def test_cli_contract_query_does_not_execute_a_scientific_claim(capsys):
    assert main(['capabilities',str(MANIFEST),'--profile','rational-integration',
                 '--operation','integrate_rational'])==0
    result=json.loads(capsys.readouterr().out)
    assert result['scientific_completion_established'] is False
    assert result['contract']['domain']
    assert main(['capabilities',str(MANIFEST),'--profile','rational-integration',
                 '--operation','general_risch'])==1
    assert 'outside' in capsys.readouterr().err


@pytest.mark.parametrize('field,value', [
    ('absolute_tolerance',0.01),('relative_tolerance','-1/3'),
    ('requirements',[True]),('requirements',[1,1]),('implementation',['../outside.py']),
    ('tests',['/tmp/fake.py']),('operations',[]),('id',''),('domain',''),
])
def test_malformed_capabilities_refused(field,value):
    data=json.loads(MANIFEST.read_text())
    data['profiles'][0][field]=value
    with pytest.raises(ValueError):
        ScientificCapabilities(canonical_payload(data))


def test_conflicting_operations_and_duplicate_profiles_are_rejected():
    data=json.loads(MANIFEST.read_text())
    data['profiles'][0]['refused'].append(data['profiles'][0]['operations'][0])
    with pytest.raises(ValueError):
        ScientificCapabilities(canonical_payload(data))
    data=json.loads(MANIFEST.read_text())
    data['profiles'].append(deepcopy(data['profiles'][0]))
    with pytest.raises(ValueError):
        ScientificCapabilities(canonical_payload(data))


def test_generated_contracts_are_current_and_preserve_original_ids(tmp_path):
    update=load_tool('update_public_contracts')
    (tmp_path/'docs/acceptance').mkdir(parents=True)
    matrix=(ROOT/'docs/acceptance/evidence_matrix.json').read_bytes()
    (tmp_path/'docs/acceptance/evidence_matrix.json').write_bytes(matrix)
    update.write_contracts(tmp_path)
    for name in ('scientific_capabilities.yaml','vision_traceability.json'):
        assert (tmp_path/'docs/acceptance'/name).read_bytes()==(ROOT/'docs/acceptance'/name).read_bytes()
    report=load_tool('check_public_contracts').validate(ROOT)
    assert report['requirements']==213 and report['local_links']>30


def test_public_link_checker_rejects_missing_and_repository_escape(tmp_path):
    check=load_tool('check_public_contracts')
    document=tmp_path/'README.md'
    document.write_text('[Missing](no-such-file.md)')
    with pytest.raises(ValueError):
        check.local_links(document,tmp_path)
    document.write_text('[Escape](../outside.md)')
    with pytest.raises(ValueError):
        check.local_links(document,tmp_path)


def test_contract_evidence_rejects_missing_paths(tmp_path):
    registry=ScientificCapabilities.load(MANIFEST)
    with pytest.raises(ValueError,match='Missing'):
        registry.validate_evidence(tmp_path)


def test_shipped_lean_pin_matches_formal_project():
    assert (ROOT/'lean/lean-toolchain').read_text().strip().endswith(support_contract()['lean']['toolchain'])


@pytest.mark.parametrize('name', ['.', 'a//b.py', 'a/./b.py', 'C:/module.py', 'module.py/'])
def test_evidence_paths_use_canonical_cross_platform_relative_names(name):
    data=json.loads(MANIFEST.read_text())
    data['profiles'][0]['implementation']=[name]
    with pytest.raises(ValueError,match='Repository-relative'):
        ScientificCapabilities(canonical_payload(data))


@pytest.mark.parametrize('corruption', ['truncate','duplicate','boolean-id','trace-boolean-id','phase-duplicate'])
def test_traceability_checker_refuses_structural_corruption(tmp_path,monkeypatch,corruption):
    from types import SimpleNamespace
    check=load_tool('check_public_contracts')
    folder=tmp_path/'docs/acceptance'
    folder.mkdir(parents=True)
    original=[{'id':i,'target':f'path-{i}','status':'partial','implementation':['x.py'],
               'tests':['test_x.py']} for i in range(1,214)]
    mapped=[{**row,'phases':['F0']} for row in original]
    if corruption=='truncate':
        original.pop()
    elif corruption=='duplicate':
        original[-1]['id']=212
    elif corruption=='boolean-id':
        original[0]['id']=True
    elif corruption=='trace-boolean-id':
        mapped[0]['id']=True
    else:
        mapped[0]['phases']=['F0','F0']
    (folder/'evidence_matrix.json').write_text(json.dumps({'requirements':original}))
    (folder/'vision_traceability.json').write_text(json.dumps({'requirements':mapped}))
    monkeypatch.setattr(check.ScientificCapabilities,'load',lambda _:SimpleNamespace(
        validate_evidence=lambda _:True,content_id='declared-test-only'))
    monkeypatch.setattr(check,'local_links',lambda *args:0)
    with pytest.raises(ValueError):
        check.validate(tmp_path)


def test_checker_json_reader_bounds_bytes_and_rejects_duplicate_keys(tmp_path):
    check=load_tool('check_public_contracts')
    path=tmp_path/'contract.json'
    path.write_text(' '*1_000_001)
    with pytest.raises(ValueError,match='byte budget'):
        check._bounded_json(path)
    path.write_text('{"requirements":[],"requirements":[]}')
    with pytest.raises(ValueError,match='Duplicate'):
        check._bounded_json(path)


def test_all85_dispositions_and104_backlog_entries_remain_explicit():
    data=json.loads((ROOT/'docs/acceptance/remaining_85_implementation.json').read_text())
    assert len(data['requirements'])==data['original_planned_count']==85
    assert [row['id'] for row in data['requirements']]==data['baseline_planned_ids']
    assert {row['status'] for row in data['requirements']}=={'partial'}
    assert sum(row['change_kind']=='existing_tested_profile_recognized' for row in data['requirements'])==13
    matrix=json.loads((ROOT/'docs/acceptance/evidence_matrix.json').read_text())['requirements']
    for row in data['requirements']:
        for field in ('implementation','tests','remaining'):
            assert row[field]==matrix[row['id']-1][field]
    backlog=json.loads((ROOT/'docs/acceptance/backlog_traceability.json').read_text())
    assert len({row['id'] for row in backlog['items']})==backlog['count']==104
    assert {row['acceptance_status'] for row in backlog['items']}=={'pending_completion'}
    assert backlog['all_backlog_acceptance_established'] is False
