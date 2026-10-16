"""Frozen dependency installation must reuse pins and preserve local work."""
import importlib.util
import json
from pathlib import Path
import subprocess
import pytest

_spec = importlib.util.spec_from_file_location('setup_formal_dependencies', Path(__file__).resolve().parents[1] / 'tools/setup_formal_dependencies.py')
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)


@pytest.fixture
def dependency(tmp_path):
    origin = tmp_path / 'origin'
    origin.mkdir()
    module.run(['git','init','--quiet'],cwd=origin)
    (origin/'source.lean').write_text('theorem sample : True := True.intro\n')
    module.run(['git','add','.'],cwd=origin)
    module.run(['git','-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','--quiet','-m','fixture'],cwd=origin)
    revision = module.run(['git','rev-parse','HEAD'],cwd=origin)
    project = tmp_path/'project'
    project.mkdir()
    data={'packagesDir':'.lake/packages','packages':[{'name':'example','rev':revision,'url':'https://github.com/example/example','type':'git','subDir':None}]}
    (project/'lake-manifest.json').write_text(json.dumps(data))
    return origin,project,data


def test_install_exact_commit_reuse_and_refuse_dirty_checkout(dependency, monkeypatch):
    origin,project,data=dependency
    original=(project/'lake-manifest.json').read_bytes()
    real_run=module.run
    def local_transport(command,**kwargs):
        if command[:4]==['git','remote','add','origin']:
            command=[*command[:4],str(origin)]
        return real_run(command,**kwargs)
    monkeypatch.setattr(module,'run',local_transport)
    assert module.install(project)[0]['status']=='installed'
    assert module.install(project)[0]['status']=='reused'
    assert (project/'lake-manifest.json').read_bytes()==original
    target=project/'.lake/packages/example'
    assert real_run(['git','rev-parse','HEAD'],cwd=target)==data['packages'][0]['rev']
    (target/'source.lean').write_text('local work')
    with pytest.raises(ValueError,match='local changes'):
        module.install(project)
    assert (target/'source.lean').read_text()=='local work'


@pytest.mark.parametrize('field,value',[('name','../escape'),('rev','main'),('url','https://elsewhere.invalid/repo'),('type','path'),('subDir','../../')])
def test_reject_unpinned_or_unsafe_manifest(dependency,field,value):
    _,project,data=dependency
    data['packages'][0][field]=value
    (project/'lake-manifest.json').write_text(json.dumps(data))
    with pytest.raises(ValueError):
        module.packages(project)
    assert not (project/'.lake').exists()
