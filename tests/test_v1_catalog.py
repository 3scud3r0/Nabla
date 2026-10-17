"""All thirty V1 operations: schemas, references, receipts and replay."""
import importlib
import inspect
import json
from pathlib import Path
import pytest
from nablamath.ops.v1_catalog import ENTRIES

CASES=json.loads((Path(__file__).resolve().parents[1]/'examples/v1/catalog_cases.json').read_text())


def test_every_v1_target_has_a_closed_exact_signature_and_example():
    assert len(ENTRIES)==30 and set(ENTRIES)==set(CASES)
    for name,entry in ENTRIES.items():
        module,function=entry['path'].split(':')
        target=getattr(importlib.import_module('nablamath.'+module),function)
        parameters=inspect.signature(target).parameters
        assert set(entry['schema']['properties'])==set(parameters),name
        assert set(entry['schema']['required'])=={k for k,p in parameters.items() if p.default is inspect.Parameter.empty},name
        assert entry['schema']['additionalProperties'] is False


@pytest.mark.parametrize('operation',sorted(ENTRIES))
def test_v1_operation_receipt_schema_and_replay(operation):
    for dependency in ('numpy','sympy','scipy'):pytest.importorskip(dependency)
    if operation=='elliptic_curve_pairing':pytest.importorskip('py_ecc')
    from nablamath.calc import CalculationSession,Notebook
    from nablamath.calc.receipt import verify_receipt
    from nablamath.ops.v1_catalog import schema
    arguments=CASES[operation]
    jsonschema=pytest.importorskip('jsonschema')
    contract=schema(operation);jsonschema.Draft202012Validator.check_schema(contract)
    jsonschema.Draft202012Validator(contract).validate(arguments)
    record=CalculationSession().execute(operation,**arguments)
    encoded=record.to_data();assert verify_receipt(encoded)
    assert CalculationSession.replay_request(encoded['request']).to_data()==encoded
    notebook=Notebook(operation);notebook.append(record);assert notebook.replay()==1
    value=encoded['result']
    if operation=='manifold_ricci':assert value['scalar']=='0'
    elif operation=='manifold_tensor':assert value['components']=='2'
    elif operation=='galois_field_op':assert value['coefficients']==[2]
    elif operation=='information_mutual':assert value['mutual_information']==pytest.approx(1)
    elif operation=='information_channel_capacity':assert value['capacity_bits']==pytest.approx(1)
    elif operation=='information_divergence_kl':assert value['divergence']==pytest.approx(0)
    elif operation=='manifold_stress_maxwell':assert value['stress_tensor'][0][0]=='2'
    elif operation=='manifold_surface_fem':assert value['integral']==pytest.approx(.5)
    elif operation=='graphics_export_gltf':assert value['format']=='glb'
    elif operation=='algebra_reed_solomon':assert value['codeword']==[[1],[6],[3],[6],[1],[2],[2]]
