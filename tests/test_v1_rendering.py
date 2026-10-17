"""Actual offline Chromium rendering and native Manim video smoke checks."""
import io
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

from nablamath.calc import CalculationSession
from nablamath.spatial_engine_3d import SpatialEngine3D
from nablamath.living_papers_compiler import LivingPapersCompiler
from nablamath.artifacts.bundle import create_bundle


def test_offline_webgl_and_html_audit_in_real_browser(tmp_path):
    sync=pytest.importorskip('playwright.sync_api')
    pytest.importorskip('qrcode')
    pytest.importorskip('PIL')
    record=CalculationSession().execute('beta_binomial',successes=2,trials=3).to_data()
    engine=SpatialEngine3D();mesh=engine.scalar_field([[0,1],[2,3]])
    scene=engine.standalone(mesh['vertices'],mesh['triangles'],tmp_path/'scene.html',audit_receipt=record,colors=mesh['colors'])
    with sync.sync_playwright() as playwright:
        chromium=shutil.which('chromium') or shutil.which('chromium-browser')
        if chromium is None and Path(playwright.chromium.executable_path).is_file():
            chromium=playwright.chromium.executable_path
        if not chromium:pytest.skip('Chromium executable unavailable')
        browser=playwright.chromium.launch(executable_path=chromium,headless=True,
            args=['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader'])
        page=browser.new_page(viewport={'width':960,'height':800})
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        # Managed Chromium forbids file:// navigation. Serve the exact bytes
        # through an intercepted HTTPS origin: no network or external assets.
        page.route('https://github.com/nabla-offline/scene', lambda route: route.fulfill(body=scene.read_text(),content_type='text/html'))
        page.goto('https://github.com/nabla-offline/scene')
        page.wait_for_function('document.querySelector("canvas").width > 0')
        from PIL import Image,ImageStat
        screenshot=page.locator('canvas').screenshot()
        image=Image.open(io.BytesIO(screenshot)).convert('RGB')
        assert max(ImageStat.Stat(image).stddev)>10, 'Mesh is blank'
        page.locator('canvas').hover();page.mouse.wheel(0,-100)
        assert not errors
        paper=LivingPapersCompiler().build(create_bundle([record]),tmp_path/'paper',{'title':'Audit','blocks':[]},pdf=False)
        page.route('https://github.com/nabla-offline/paper', lambda route: route.fulfill(body=paper.html.read_text(),content_type='text/html'))
        page.goto('https://github.com/nabla-offline/paper')
        page.wait_for_function('document.querySelector("#status").textContent.includes("integrity verified")')
        assert not errors
        browser.close()


def test_real_orbital_manim_video(tmp_path):
    pytest.importorskip('manim')
    record=CalculationSession().execute('beta_binomial',successes=2,trials=3).to_data()
    source=SpatialEngine3D.trajectory_animation([[0,0,0],[1,2,1],[2,1,2]],record,errors=[.1,.2,.1],duration=.2)
    path=tmp_path/'orbit.py';path.write_text(source)
    result=subprocess.run([sys.executable,'-m','manim','-ql','--disable_caching','--media_dir',str(tmp_path/'media'),str(path),'NablaSpatialAnimation'],capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stderr[-4000:]
    videos=list((tmp_path/'media').rglob('NablaSpatialAnimation.mp4'))
    assert len(videos)==1 and videos[0].stat().st_size>1000


def test_fundamental_group_generator_indices_are_contiguous():
    from nablamath.math.topology.homotopy import fundamental_group
    result=fundamental_group([[0,1,2],[0,2,3],[0,3,1]])
    assert result['generators']
    assert all(0<abs(g)<=len(result['generators']) for word in result['relators'] for g in word)


def test_bundled_three_orbit_colormap_and_time_in_browser(tmp_path):
    sync=pytest.importorskip('playwright.sync_api')
    np=pytest.importorskip('numpy')
    from nablamath.graphics.spatial_engine_3d import MeshData,Standalone3DViewer
    from PIL import Image,ImageStat
    mesh=MeshData(((0.,0.,0.),(1.,0.,0.),(0.,1.,0.)),((0,1,2),),(0.,1.,2.))
    record=CalculationSession().execute('beta_binomial',successes=2,trials=3).to_data()
    frames=[mesh.vertices,(np.asarray(mesh.vertices)+[0,0,.5]).tolist()]
    source=Standalone3DViewer().source(mesh,record,frames=frames,times=[0,2])
    with sync.sync_playwright() as playwright:
        executable=shutil.which('chromium') or shutil.which('chromium-browser')
        if not executable and Path(playwright.chromium.executable_path).is_file():executable=playwright.chromium.executable_path
        if not executable:pytest.skip('Chromium executable unavailable')
        browser=playwright.chromium.launch(executable_path=executable,headless=True,
            args=['--no-sandbox','--enable-unsafe-swiftshader','--use-angle=swiftshader'])
        page=browser.new_page(viewport={'width':960,'height':800})
        errors=[];requests=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda request:requests.append(request.url))
        page.route('https://github.com/nabla-offline/three',lambda route:route.fulfill(body=source,content_type='text/html'))
        page.goto('https://github.com/nabla-offline/three')
        page.wait_for_function('typeof THREE !== "undefined" && document.querySelector("canvas").width>0')
        assert page.evaluate('THREE.REVISION')=='180'
        page.locator('#colormap').select_option('plasma')
        page.locator('#time').fill('1');page.locator('#time').dispatch_event('input')
        assert '2' in page.locator('#clock').inner_text()
        page.locator('#wireframe').check();page.locator('#wireframe').uncheck()
        image=Image.open(io.BytesIO(page.locator('canvas').screenshot())).convert('RGB')
        assert max(ImageStat.Stat(image).stddev)>5
        assert not errors
        assert all(url.startswith(('https://github.com/nabla-offline/three','data:')) for url in requests)
        browser.close()


@pytest.mark.parametrize('equations', [[], ['x*x']])
def test_new_manim_mesh_and_equation_really_render(tmp_path, equations):
    pytest.importorskip('manim');pytest.importorskip('sympy')
    if equations and not shutil.which('dvisvgm'):
        pytest.skip('MathTex rendering requires dvisvgm; installation unavailable in this environment')
    from nablamath.graphics.spatial_engine_3d import MeshData,ManimSceneSynthesizer
    mesh=MeshData(((0.,0.,0.),(1.,0.,0.),(0.,1.,0.)),((0,1,2),))
    record=CalculationSession().execute('beta_binomial',successes=2,trials=3).to_data()
    animator=ManimSceneSynthesizer(duration=.2)
    source=animator.mesh_scene(mesh,record,equations=equations,variables=['x'])
    output=tmp_path/'proof.mp4'
    result=animator.render(source,output,timeout=120)
    assert output.is_file() and output.stat().st_size>1000
    assert b'ftyp' in output.read_bytes()[:32]
