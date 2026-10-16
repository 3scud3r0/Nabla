"""Frozen local-CPU v1 API signatures; mathematical acceptance is a separate gate."""
from importlib.resources import files
from .core.semantic_contracts import load_json


def public_contract():
    """Return a detached copy of the public contract shipped in the wheel."""
    data = load_json(files('nablamath').joinpath('public_api.json').read_text(encoding='utf-8'))
    if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise ValueError('Unsupported public API contract version')
    return data


def validate_public_api():
    from . import __all__
    from .calc.catalog import catalog
    contract = public_contract()
    if sorted(__all__) != contract['package_exports']:
        raise ValueError('Public package exports differ from frozen v1 contract')
    if catalog() != contract['catalog']:
        raise ValueError('Calculation catalog differs from frozen v1 contract')
    return {'profile': contract['profile'], 'operations': len(contract['catalog']['operations']),
            'scope': 'public signatures and descriptions; not universal mathematical acceptance'}


__all__ = ['public_contract', 'validate_public_api']
