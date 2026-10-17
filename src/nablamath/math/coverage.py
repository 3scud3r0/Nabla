"""Inspectable MSC implementation map, separate from scientific acceptance."""
from importlib.resources import files
from ..core.semantic_contracts import load_json


def coverage():
    data=load_json(files('nablamath').joinpath('msc_coverage.json').read_text(encoding='utf-8'))
    if data['schema_version']!=1 or len(data['classifications'])!=63 or len({row['code'] for row in data['classifications']})!=63:
        raise ValueError('Invalid MSC coverage inventory')
    return data


def classification(code):
    if not isinstance(code,str) or len(code)!=2 or not code.isdecimal():
        raise ValueError('A two-digit MSC major code is required')
    for row in coverage()['classifications']:
        if row['code']==code:return row
    raise KeyError('MSC major code is not in this inventory: '+code)


def expansion():
    """Return authored implementation inventory with explicit validation-report reference."""
    return load_json(files('nablamath').joinpath('mathematical_expansion.json').read_text(encoding='utf-8'))


__all__=['coverage','classification','expansion']
