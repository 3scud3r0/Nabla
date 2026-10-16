"""Public local CPU workflow, runnable against an installed wheel with python -I."""
import json
from pathlib import Path
import sys
from nablamath import __version__, calculate
from nablamath.calc import CalculationSession, Notebook
from nablamath.compatibility import runtime_report
from nablamath.pipeline.scientific_cycle import build_scientific_artifact, replay_scientific_artifact
from nablamath.stability import validate_public_api
from nablamath.storage import save_result, load_result, export_verified, import_snapshot
from nablamath.store.backup import backup_database, restore_database


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
    return {'version': __version__, 'notebook_cells': 1, 'stored_records': 1,
            'artifact_id': artifact.content_id, 'scope': 'local CPU workflow; no external acceptance'}


if __name__ == '__main__':
    print(json.dumps(run(sys.argv[1]), sort_keys=True))
