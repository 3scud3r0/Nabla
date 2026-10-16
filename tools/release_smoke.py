"""Public local CPU workflow, runnable against an installed wheel with python -I."""
import json
from pathlib import Path
import sys
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler
from nablamath import __version__, calculate
from nablamath.calc import CalculationSession, Notebook
from nablamath.compatibility import runtime_report
from nablamath.pipeline.scientific_cycle import build_scientific_artifact, replay_scientific_artifact
from nablamath.stability import validate_public_api
from nablamath.storage import save_result, load_result, export_verified, import_snapshot
from nablamath.store.backup import backup_database, restore_database


def desktop_smoke(directory):
    """Exercise packaged HTML, authenticated HTTP and advanced notebook replay."""
    from nablamath.calc.catalog import catalog
    from nablamath.desktop.app import make_server
    server, _ = make_server(directory)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    # Loopback traffic must stay local even on hosts configured with a proxy.
    client = build_opener(ProxyHandler({}))
    try:
        with client.open(base+'/', timeout=5) as response:
            page = response.read().decode('utf-8')
        assert 'id="scientific-calculate"' in page
        token = page.split("const auth='", 1)[1].split("'", 1)[0]

        def request(path, payload=None, auth=token):
            body = None if payload is None else json.dumps(payload).encode('utf-8')
            headers = {'X-Nabla-Token': auth, 'Origin': base,
                       'Content-Type': 'application/json'}
            with client.open(Request(base+path, data=body, headers=headers), timeout=5) as response:
                return json.load(response)

        assert request('/api/catalog') == catalog()
        payload = {'operation': 'analysis_integral',
                   'arguments': {'coefficients': [0, 0, 1], 'lower': 0, 'upper': 1}}
        receipt = request('/api/calculate', payload)
        assert receipt == CalculationSession().execute(
            payload['operation'], **payload['arguments']).to_data()
        assert receipt['result']['integral'] == '1/3'
        saved = request('/api/save-calculation', payload)
        assert saved['replayed'] and Notebook.load(saved['path']).replay() == 1
        try:
            request('/api/catalog', auth='invalid')
        except HTTPError as error:
            assert error.code == 403
        else:
            raise AssertionError('Desktop accepted an invalid session token')
        return {'http': True, 'catalog_operations': len(catalog()['operations']),
                'advanced_receipt': True, 'saved_notebook_replayed': True,
                'invalid_token_rejected': True}
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def run(directory):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    validate_public_api()
    calculation = CalculationSession().execute('certified_integral', coefficients=[0, 0, 1],
                                               lower=0, upper=1, tolerance='1/100')
    notebook = Notebook('Installed wheel acceptance')
    notebook.append(calculation)
    notebook.save(root/'notebook.json')
    assert Notebook.load(root/'notebook.json').replay() == 1
    result = calculate('(x+x)/x', {'x': 3})
    assert save_result(root/'results.db', result)
    assert export_verified(root/'results.db', root/'records.jsonl')[0] == 1
    assert import_snapshot(root/'import.db', root/'records.jsonl') == (1, 0)
    backup_database(root/'results.db', root/'backup.db')
    restore_database(root/'backup.db', root/'restored.db')
    assert load_result(root/'restored.db', result.content_id) == result.to_data()
    artifact = build_scientific_artifact(family='linear_system', seed=21, size=2,
                                         license_id='MIT', provenance='release smoke synthetic fixture')
    replay_scientific_artifact(artifact)
    assert runtime_report().compatible
    desktop = desktop_smoke(root/'desktop')
    return {'version': __version__, 'notebook_cells': 1, 'stored_records': 1,
            'desktop': desktop,
            'artifact_id': artifact.content_id, 'scope': 'local CPU workflow; no external acceptance'}


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[1]), sort_keys=True))
