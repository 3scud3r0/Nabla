"""Untrusted notebook envelopes must remain strict even after rehashing."""
import json
import pytest
from nablamath.calc.notebook import Notebook
from nablamath.calc.session import CalculationSession
from nablamath.core.semantic_ir import fingerprint


def snapshot():
    book = Notebook('regression')
    book.append(CalculationSession().evaluate('2+3'))
    return book.to_data()


def rehash(data):
    for cell in data['cells']:
        calc = cell['calculation']
        calc['content_id'] = fingerprint({k: v for k, v in calc.items() if k != 'content_id'})
        cell['cell_id'] = fingerprint({k: v for k, v in cell.items() if k != 'cell_id'})
    data['content_id'] = fingerprint({k: v for k, v in data.items() if k != 'content_id'})
    return data


def test_roundtrip_retains_portable_v1(tmp_path):
    path = tmp_path / 'notebook.json'
    path.write_text(json.dumps(snapshot()))
    assert Notebook.load(path).replay() == 1


@pytest.mark.parametrize('mutation', ['version', 'calculation_version', 'formal', 'cell_extra', 'result_type', 'not_object', 'cell_not_object'])
def test_rehash_cannot_authorize_contract_changes(tmp_path, mutation):
    data = snapshot()
    if mutation == 'version':
        data['schema_version'] = True
    elif mutation == 'calculation_version':
        data['cells'][0]['calculation']['schema_version'] = True
    elif mutation == 'formal':
        data['cells'][0]['calculation']['formal_proof'] = 0
    elif mutation == 'cell_extra':
        data['cells'][0]['extra'] = 'ignored?'
    elif mutation == 'result_type':
        data['cells'][0]['calculation']['result']['approximation']['digits'] = True
    data = rehash(data)
    if mutation == 'not_object':
        data = []
    if mutation == 'cell_not_object':
        data['cells'] = [None]
        data['content_id'] = fingerprint({k: v for k, v in data.items() if k != 'content_id'})
    path = tmp_path / 'bad.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        Notebook.load(path)


def test_duplicate_top_level_key_is_rejected(tmp_path):
    data = json.dumps(snapshot())
    path = tmp_path / 'duplicate.json'
    path.write_text('{"schema_version": 99,' + data[1:])
    with pytest.raises(ValueError, match='Duplicate'):
        Notebook.load(path)
