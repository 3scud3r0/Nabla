"""Explicit data references to prior declared dependencies; no expression evaluation."""
from ..core.semantic_ir import canonical_json


def references(value, *, depth=0):
    if depth > 16:
        raise ValueError('Referência excede profundidade')
    found = []
    if isinstance(value, dict):
        if '$result' in value:
            ref = value['$result']
            if (set(value) != {'$result'} or not isinstance(ref, dict) or set(ref) != {'action', 'path'}
                    or not isinstance(ref['action'], str) or not isinstance(ref['path'], list)
                    or len(ref['path']) > 16
                    or any(not isinstance(p, str) and type(p) is not int for p in ref['path'])
                    or any(type(p) is int and p < 0 for p in ref['path'])):
                raise ValueError('Contrato de referência inválido')
            found.append(ref)
        else:
            for child in value.values():
                found.extend(references(child, depth=depth+1))
    elif isinstance(value, list):
        for child in value:
            found.extend(references(child, depth=depth+1))
    return found


def resolve(value, results):
    """Resolve only JSON object keys/list indices. No attributes or arbitrary code."""
    references(value)
    def visit(node):
        if isinstance(node, dict):
            if '$result' in node:
                ref = node['$result']
                if ref['action'] not in results:
                    raise ValueError('Resultado de dependência indisponível')
                selected = results[ref['action']]
                for part in ref['path']:
                    if isinstance(selected, dict) and isinstance(part, str) and part in selected:
                        selected = selected[part]
                    elif isinstance(selected, list) and type(part) is int and part < len(selected):
                        selected = selected[part]
                    else:
                        raise ValueError('Caminho de resultado incompatível')
                return selected
            return {key: visit(child) for key, child in node.items()}
        if isinstance(node, list):
            return [visit(child) for child in node]
        return node
    import json
    return json.loads(canonical_json(visit(value)))
