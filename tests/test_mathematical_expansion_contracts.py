"""Catalog, closed tool schemas, replay and refusal cases. NOT RUN on delivery."""
import inspect
import importlib
import json
import hashlib
from pathlib import Path
import pytest


def test_all_advanced_targets_have_matching_closed_signatures():
    from nablamath.ops.advanced_math import ACTIONS
    for name,entry in ACTIONS.items():
        module,function=entry['path'].split(':');target=getattr(importlib.import_module('nablamath.'+module),function)
        parameters=inspect.signature(target).parameters
        fields=set(entry['schema']['properties'])
        assert fields<=parameters.keys(),name
        required={key for key,p in parameters.items() if p.default is inspect.Parameter.empty}
        assert required==set(entry['schema']['required']),name
        assert entry['schema']['additionalProperties'] is False


def test_frozen_catalog_and_packaged_implementation_status():
    from nablamath.stability import validate_public_api
    from nablamath.math.coverage import coverage,expansion
    from nablamath.ops.advanced_math import ACTIONS
    assert validate_public_api()['operations']==134
    inventory=expansion()
    assert {row['action'] for row in inventory['actions']}==set(ACTIONS)
    for row in inventory['actions']:
        encoded=json.dumps(ACTIONS[row['action']]['schema'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
        assert row['parameter_schema_sha256']==hashlib.sha256(encoded).hexdigest()
    assert inventory['test_execution']=='see_version_1_validation'
    assert not inventory['scientific_acceptance_established']
    assert all(not row['entire_subject_implemented'] for row in coverage()['classifications'])


def test_session_notebook_and_background_receipt_for_new_entry():
    from nablamath.calc import CalculationSession
    from nablamath.artifacts.notebook import Notebook
    from nablamath.calc.receipt import verify_receipt
    parameters={'reference':[1,2,0],'target':[3,4,0]}
    result=CalculationSession().mathematics('measure.radon_nikodym',**parameters)
    assert result.to_data()['result']['result']['density']==['3','2','0']
    assert verify_receipt(result.to_data())
    notebook=Notebook('Advanced exact measure');notebook.append(result)
    assert notebook.replay()==1
    with CalculationSession(background_receipts=True) as session:
        pending=session.mathematics('sets.operations',left=[[]],right=[[]])
        assert pending.to_data()['result']['result']['equal']


@pytest.mark.parametrize('payload',[
    {'action':'os.system','parameters':{'command':'anything'}},
    {'action':'sets.operations','parameters':{'left':[],'right':[],'code':'anything'}},
    {'action':'sets.operations','parameters':{'left':{'execute':'anything'},'right':[]}},
    {'action':'formal.translate','parameters':{'certificate':{'kind':'identity','left':'x','right':'x','lean':'by sorry'}}},
    {'action':'optimization.certificate','parameters':{'objective':[1],'matrix':[[{'source':'anything'}]],'lower':[1],'point':[1],'dual':[1]}},
])
def test_invalid_nested_input_cannot_start_math(payload,monkeypatch):
    jsonschema=pytest.importorskip('jsonschema')
    from nablamath.ai.agent_tools import AgentTools
    from nablamath.agents.permissions import Permissions
    tools=AgentTools(Permissions(frozenset({'advanced_math'})))
    def forbidden(*args,**kwargs):raise AssertionError('Invalid action reached execution')
    monkeypatch.setattr(tools.registry,'execute',forbidden)
    with pytest.raises(jsonschema.ValidationError):tools.call('advanced_math',payload)
    assert tools.calls==0


def test_advanced_schema_validates_all_foundation_structures():
    jsonschema=pytest.importorskip('jsonschema')
    from nablamath.ops.advanced_math import schema
    contract=schema();jsonschema.Draft202012Validator.check_schema(contract);validator=jsonschema.Draft202012Validator(contract)
    examples=[
        {'action':'proofs.check','parameters':{'proof':{'rule':'imp_intro','assumption':'P','premises':[{'rule':'assumption','formula':'P'}]}}},
        {'action':'constructive.type_check','parameters':{'term':{'op':'lambda','name':'x','type':'P','body':{'op':'var','name':'x'}}}},
        {'action':'models.satisfaction','parameters':{'domain':[0,1],'relations':{},'sentence':{'op':'forall','variable':'x','body':{'op':'equal','left':{'var':'x'},'right':{'var':'x'}}}}},
        {'action':'forms.derivative','parameters':{'coordinates':['x','y'],'components':{'0':'x*y'}}},
        {'action':'stochastic.system','parameters':{'drift':['0'],'diffusion':[['1']],'variables':['x'],'initial':[0]}},
    ]
    for example in examples:validator.validate(example)


@pytest.mark.parametrize('source',[
    '__import__("os")','x.__class__','[x for x in range(3)]','lambda: x','x[0]','open("file")','x**1000'
])
def test_symbolic_adapter_rejects_executable_syntax(source):
    pytest.importorskip('sympy')
    from nablamath.math._structured import expression
    with pytest.raises(ValueError):expression(source,['x'])


def test_direct_dispatch_never_imports_request_paths(monkeypatch):
    import nablamath.ops.advanced_math as module
    def forbidden(*args,**kwargs):raise AssertionError('Unexpected dynamic import')
    monkeypatch.setattr(module,'import_module',forbidden)
    with pytest.raises(ValueError):module.advanced_math('subprocess:run',{})


def test_cli_cases_cover_added_catalog_without_optional_dependencies():
    from nablamath.calc.catalog import catalog
    cases=json.loads((Path(__file__).resolve().parents[1]/'examples/science/catalog_cases.json').read_text())
    from nablamath.ops.v1_catalog import ENTRIES
    assert set(cases)=={entry['name'] for entry in catalog()['operations']}-set(ENTRIES)
    v1=json.loads((Path(__file__).resolve().parents[1]/'examples/v1/catalog_cases.json').read_text())
    assert set(v1)==set(ENTRIES)
    assert cases['advanced_math']['action']=='sets.operations'
