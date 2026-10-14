"""Prepare a Hub-compatible dataset locally; upload is a separate explicit API."""
import json
from pathlib import Path
from .bundle import verify_bundle


def prepare_hub(directory):
    root = Path(directory)
    if not verify_bundle(root):
        raise ValueError('Bundle inválido')
    card = json.loads((root/'card.json').read_text(encoding='utf-8'))
    content = ('---\npretty_name: Nabla scientific dataset\nconfigs:\n- config_name: default\n'
               '  data_files:\n  - split: train\n    path: train.jsonl\n'
               '  - split: validation\n    path: validation.jsonl\n'
               '  - split: test\n    path: test.jsonl\n---\n\n'
               '# Dataset científico rastreável\n\n'+json.dumps(card, indent=2, ensure_ascii=False)+'\n')
    # Write outside the verified bundle so its file manifest remains closed.
    return {'readme': content, 'directory': str(root), 'publication_performed': False}


def upload_bundle(directory, repo_id, *, private=True, token=None):
    prepared = prepare_hub(directory)
    from huggingface_hub import HfApi
    api = HfApi(token=token)
    api.create_repo(repo_id=repo_id, repo_type='dataset', private=private, exist_ok=True)
    result = api.upload_folder(repo_id=repo_id, repo_type='dataset', folder_path=prepared['directory'])
    api.upload_file(repo_id=repo_id, repo_type='dataset', path_or_fileobj=prepared['readme'].encode(), path_in_repo='README.md')
    return result
