"""Complete source selection, byte preservation and stale/tamper detection."""

import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('nabla_bundle', ROOT/'tools/build_nabla_bundle.py')
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)


def checkout(tmp_path):
    subprocess.run(['git','init','-q',str(tmp_path)],check=True)
    (tmp_path/'.gitignore').write_text('.venv/\n.nabla/\nsecret.py\n')
    return tmp_path


def put(root,name,data):
    path = root/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data)
    return path


def test_collects_all_source_components_and_excludes_local_data(tmp_path):
    root = checkout(tmp_path)
    wanted = ['src/nablamath/a.py','tests/test_a.py','services/a.py','sdk/a.rs',
              'legacy/a.py','website/app.js','tools/a.py','lean/A.lean',
              'packaging/windows/app.iss','configs/profile.yaml','protocol/schema/a.json',
              'templates/report/example.document.json','website/package.json','examples/plan.json']
    for name in wanted:
        put(root,name,b'content\n')
    for name in ['.venv/library.py','.nabla/run.py','secret.py','math.txt','NABLA.TXT',
                 'website/dist/app.js','sdk/rust/target/build.rs','benchmarks/results/run.json',
                 'docs/guide.md','image.png']:
        put(root,name,b'excluded\n')
    paths = {p.relative_to(root).as_posix() for p in bundle.source_paths(root)}
    assert paths == set(wanted)|{'.gitignore'}
    data = bundle.build_bundle(root)
    manifest = bundle.inspect_bundle(data)
    assert manifest['file_count'] == len(wanted)+1
    assert {row['path'] for row in manifest['files']} == paths


def test_preserves_crlf_missing_final_newline_and_marker_text(tmp_path):
    root = checkout(tmp_path)
    content = b'# accented: \xc3\xa7\r\nvalue = "@@NABLA_END_FILE"\r\nlast = 1'
    put(root,'a.py',content)
    data = bundle.build_bundle(root)
    manifest = bundle.inspect_bundle(data)
    entry = next(row for row in manifest['files'] if row['path']=='a.py')
    assert entry['bytes'] == len(content)
    assert entry['sha256'] == hashlib.sha256(content).hexdigest()
    assert entry['lines'] == 3
    assert content in data


def test_non_utf8_source_bytes_are_losslessly_encoded(tmp_path):
    root = checkout(tmp_path)
    put(root,'legacy.py',b'# coding: latin-1\nname = "\xe7"\n')
    manifest = bundle.inspect_bundle(bundle.build_bundle(root))
    entry = next(row for row in manifest['files'] if row['path']=='legacy.py')
    assert entry['encoding'] == 'base64'
    assert entry['bytes'] == len((root/'legacy.py').read_bytes())


def test_source_payload_corruption_is_rejected(tmp_path):
    root = checkout(tmp_path)
    put(root,'a.py',b'value = 12345\n')
    data = bundle.build_bundle(root)
    with pytest.raises(ValueError,match='hash'):
        bundle.inspect_bundle(data.replace(b'value = 12345',b'value = 12346'))
    with pytest.raises(ValueError):
        bundle.inspect_bundle(data+b'extra trailing payload')


def test_stable_order_and_source_updates_change_archive(tmp_path):
    root = checkout(tmp_path)
    put(root,'z.py',b'z=1\n')
    put(root,'a.py',b'a=1\n')
    before = bundle.build_bundle(root)
    assert before == bundle.build_bundle(root)
    names = [row['path'] for row in bundle.inspect_bundle(before)['files']]
    assert names == sorted(names)
    put(root,'a.py',b'a=2\n')
    assert bundle.build_bundle(root) != before


def test_atomic_writer_and_cli_staleness(tmp_path,monkeypatch,capsys):
    root = checkout(tmp_path)
    source = put(root,'a.py',b'a=1\n')
    output = root/'NABLA.TXT'
    original = bundle.build_bundle
    monkeypatch.setattr(bundle,'build_bundle',lambda:original(root))
    assert bundle.main(['--output',str(output)]) == 0
    assert bundle.main(['--output',str(output),'--check']) == 0
    source.write_bytes(b'a=2\n')
    assert bundle.main(['--output',str(output),'--check']) == 1
    assert bundle.main(['--output',str(output)]) == 0
    assert bundle.inspect_bundle(output.read_bytes())['file_count'] == 2
    assert not list(root.glob('.NABLA.TXT.*'))


def test_source_symlink_is_not_followed(tmp_path):
    root = checkout(tmp_path)
    target = put(root,'private.data',b'not a source\n')
    (root/'a.py').symlink_to(target)
    with pytest.raises(ValueError,match='symlink'):
        bundle.source_paths(root)


def test_deleted_tracked_source_is_not_archived_as_present(tmp_path):
    root = checkout(tmp_path)
    path = put(root,'a.py',b'a=1\n')
    subprocess.run(['git','-C',str(root),'add','a.py'],check=True)
    path.unlink()
    assert all(p.name!='a.py' for p in bundle.source_paths(root))


def test_root_must_be_checkout_root(tmp_path):
    root = checkout(tmp_path)
    directory = root/'subdirectory'
    directory.mkdir()
    with pytest.raises(ValueError,match='checkout root'):
        bundle.source_paths(directory)
