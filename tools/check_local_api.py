"""Compare the local v1 candidate API against an explicit normative fixture.

The fixture is an engineering regression contract, not approval of a 1.0 release.
Updating it requires a reviewed compatibility decision and migration notes.
"""
import argparse
import importlib
import inspect
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'configs/release/local-v1-api.json'
MODULES = ('nablamath', 'nablamath.calc', 'nablamath.schema.expression',
           'nablamath.schema.units', 'nablamath.compatibility')


def current_contract():
    from nablamath.calc.session import AREAS, REQUIRED, OPTIONAL, Calculation, CalculationSession
    from nablamath.calc.notebook import Notebook
    exports = {}
    for name in MODULES:
        module = importlib.import_module(name)
        names = sorted(module.__all__ if name != 'nablamath.schema.units' else
                       ['Unit', 'Quantity', 'ONE', 'METER', 'SECOND', 'KILOGRAM', 'KILOMETER', 'HOUR'])
        if any(not hasattr(module, symbol) for symbol in names):
            raise ValueError('Missing public export: ' + name)
        exports[name] = names
    methods = {}
    for cls, names in [(Calculation, ('to_data',)),
                       (CalculationSession, ('bind', 'evaluate', 'execute', 'replay_request')),
                       (Notebook, ('append', 'load', 'replay', 'save', 'to_data'))]:
        for name in names:
            methods[cls.__name__ + '.' + name] = str(inspect.signature(getattr(cls, name)))
    return {'schema_version': 1, 'profile': 'local-v1-candidate',
            'exports': exports, 'methods': methods,
            'operations': {name: {'area': AREAS[name], 'required': sorted(REQUIRED[name]),
                                  'optional': sorted(OPTIONAL.get(name, set()))}
                           for name in sorted(AREAS)},
            'notebook_schema_version': 1, 'calculation_schema_version': 1}


def validate(fixture=FIXTURE):
    from nablamath.core.semantic_contracts import load_json
    expected = load_json(Path(fixture).read_text(encoding='utf-8'))
    if not isinstance(expected, dict):
        raise ValueError('API fixture must be an object')
    actual = current_contract()
    if expected != actual:
        sections = sorted(key for key in actual.keys() | expected.keys() if actual.get(key) != expected.get(key))
        raise ValueError('Public API changed; review compatibility and migration: ' + ', '.join(sections))
    return {'profile': actual['profile'], 'operations': len(actual['operations']),
            'modules': len(actual['exports']), 'contract_matches': True,
            'release_accepted': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=FIXTURE)
    args = parser.parse_args(argv)
    print(json.dumps(validate(args.fixture), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
