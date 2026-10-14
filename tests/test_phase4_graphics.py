from dataclasses import replace
from fractions import Fraction as F
import hashlib
import importlib.util
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from nablamath.core.semantic_ir import canonical_json
from nablamath.graphics.scene_graph import GeometryScene,Point,Segment,Circle,Polyline
from nablamath.graphics.coordinate_system import CoordinateSystem
from nablamath.graphics.geometry_constraints import GeometryConstraint as C
from nablamath.graphics.layout import clip_line,place_labels,build_primitives
from nablamath.graphics.svg_renderer import render_svg
from nablamath.graphics.raster_renderer import render_png
from nablamath.graphics.sampling import function_scene,vector_field_scene,phase_portrait_scene
from nablamath.graphics.artifacts import export_scene,verify_scene_bundle,replay_model
from nablamath.verify.geometry import verify_geometry,verify_geometry_certificate
from nablamath.forge.constructors.geometry import construct
from nablamath.cli import main

PIL_AVAILABLE=importlib.util.find_spec('PIL') is not None


class ExactGeometryTests(unittest.TestCase):
    def test_every_inverse_construction_seeds_and_sizes(self):
        for kind in ('right_triangle','parallelogram','circumcircle'):
            for size in (1,3,8):
                for seed in (0,17,42):
                    with self.subTest(kind=kind,size=size,seed=seed):
                        scene=construct(seed,size,kind)
                        self.assertTrue(verify_geometry(scene).valid)
                        self.assertTrue(replay_model(scene)['valid'])
                        self.assertEqual(scene,GeometryScene.from_data(scene.to_data()))
                        self.assertTrue(verify_geometry_certificate(scene,verify_geometry(scene).to_data()))
                        self.assertEqual(scene.content_id,construct(seed,size,kind).content_id)

    def test_all_constraint_kinds_and_degenerate_rejection(self):
        points=(Point('A',0,0),Point('B',2,0),Point('C',0,2),Point('M',1,0),Point('D',0,0))
        constraints=(C('coincident',('A','D')),C('distinct',('A','B')),C('collinear',('A','M','B')),
            C('noncollinear',('A','B','C')),C('parallel',('A','B','M','B')),C('perpendicular',('A','B','A','C')),
            C('equal_distance',('A','B','A','C')),C('distance_squared',('A','B'),4),C('on_circle',('B','A'),4),
            C('midpoint',('M','A','B')),C('orientation',('A','B','C'),1))
        scene=GeometryScene('constraints',CoordinateSystem(-1,3,-1,3),points,constraints=constraints)
        self.assertTrue(verify_geometry(scene).valid)
        wrong=replace(scene,constraints=(C('distance_squared',('A','B'),5),))
        self.assertFalse(verify_geometry(wrong).valid)
        degenerate=replace(scene,segments=(Segment('zero','A','D'),))
        self.assertFalse(verify_geometry(degenerate).valid)
        with self.assertRaises(ValueError):replace(scene,segments=(Segment('bad','A','missing'),))
        with self.assertRaises(ValueError):C('perpendicular',('A','B'))
        with self.assertRaises(ValueError):Circle('bad','A',-1)

    def test_coordinate_roundtrip_uniform_scale_and_clipping(self):
        transform=CoordinateSystem(-2,8,-1,3).transform(800,600)
        self.assertEqual(transform.sx,transform.sy)
        point=(F(5,3),F(7,4));pixel=transform.pixel(*point);roundtrip=transform.world(*pixel)
        self.assertLessEqual(abs(roundtrip[0]-point[0]),F(1,2)/transform.sx)
        self.assertLessEqual(abs(roundtrip[1]-point[1]),F(1,2)/transform.sy)
        self.assertEqual(clip_line((-100,50),(200,50),(0,0,100,100)),((0,50),(100,50)))
        self.assertIsNone(clip_line((-100,-100),(-1,-1),(0,0,100,100)))
        with self.assertRaises(ValueError):CoordinateSystem(0,0,0,1)
        with self.assertRaises(ValueError):transform.system.transform(32,32)

    def test_layout_is_deterministic_and_reports_crowding(self):
        points=[(f'P{i}',80,80) for i in range(20)]
        a=place_labels(points,200,150)
        self.assertEqual(a,place_labels(points,200,150))
        self.assertTrue(a[1])
        scene=construct();primitives,layout=build_primitives(scene)
        self.assertTrue(primitives)
        self.assertTrue(layout['aspect_preserved'])


class ScientificSamplingTests(unittest.TestCase):
    def test_polynomial_samples_and_poles_between_grid_points(self):
        scene=function_scene('x*x',xmin=-1,xmax=1,samples=9)
        for curve in scene.curves:
            for x,y in curve.coordinates:self.assertEqual(y,x*x)
        scene=function_scene('1/(x-1/3)',samples=32)
        self.assertGreaterEqual(len(scene.curves),2)
        for curve in scene.curves:
            self.assertFalse(min(x for x,_ in curve.coordinates)<F(1,3)<max(x for x,_ in curve.coordinates))
        self.assertGreater(json.loads(scene.model_json)['guarded_intervals'],0)
        self.assertTrue(replay_model(scene)['valid'])

    def test_vector_field_retains_direction_and_raw_magnitude(self):
        scene=vector_field_scene('-y','x',grid=5)
        self.assertEqual(len(scene.arrows),24)
        for arrow in scene.arrows:
            x,y=arrow.start;u,v=arrow.vector
            self.assertEqual((u,v),(-y,x))
            self.assertEqual((arrow.end[0]-x)*v-(arrow.end[1]-y)*u,0)
        self.assertTrue(replay_model(scene)['valid'])
        with self.assertRaises(ValueError):vector_field_scene(grid=17)
        with self.assertRaises(ValueError):vector_field_scene('z','x')

    def test_phase_portrait_initials_energy_and_numerical_label(self):
        scene=phase_portrait_scene(initials=((1,0),),duration=1,steps=100,grid=5)
        curve=scene.curves[0]
        self.assertEqual(curve.coordinates[0],(1,0))
        self.assertEqual(curve.role,'numerical_trajectory')
        self.assertLess(max(abs(float(x*x+y*y)-1) for x,y in curve.coordinates),1e-8)
        self.assertTrue(replay_model(scene)['valid'])
        self.assertEqual(json.loads(scene.model_json)['method'],'rk4_float')


@unittest.skipUnless(PIL_AVAILABLE,'optional graphics extra (Pillow) absent')
class GeometryRenderingTests(unittest.TestCase):
    def test_svg_png_metadata_and_deterministic_nonblank_images(self):
        from PIL import Image
        scene=construct()
        svg=render_svg(scene,800,600);png=render_png(scene,800,600)
        self.assertEqual(svg,render_svg(scene,800,600));self.assertEqual(png,render_png(scene,800,600))
        root=ET.fromstring(svg)
        metadata=json.loads(root.find('{http://www.w3.org/2000/svg}metadata').text)
        self.assertEqual(metadata['scene'],scene.to_data())
        image=Image.open(BytesIO(png));self.assertEqual(image.size,(800,600))
        self.assertEqual(json.loads(image.info['NablaScene']),scene.to_data())
        self.assertEqual(json.loads(image.info['NablaLayout']),metadata['layout'])
        pixels=list(image.get_flattened_data()) if hasattr(image,'get_flattened_data') else list(image.getdata());self.assertGreater(sum(p!=(255,255,255) for p in pixels),1000)
        self.assertLess(sum(p!=(255,255,255) for p in pixels),len(pixels)//2)
        pixel=scene.coordinates.transform(800,600).pixel(scene.points[0].x,scene.points[0].y)
        self.assertEqual(image.getpixel(pixel),(23,54,95))

    def test_svg_escapes_titles_and_invalid_constraints_stop_export(self):
        scene=replace(construct(),title='<script>alert("x")</script>')
        svg=render_svg(scene)
        self.assertNotIn('<script>',svg)
        self.assertIn('&lt;script&gt;',svg)
        bad=replace(construct(),constraints=(C('coincident',('A','B')),))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):export_scene(bad,Path(directory)/'bad')
            self.assertEqual(list(Path(directory).iterdir()),[])

    def test_roundtrip_and_rehashed_geometric_or_visual_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'figure';export_scene(construct(),root)
            self.assertTrue(verify_scene_bundle(root))
            with self.assertRaises(FileExistsError):export_scene(construct(),root)
            row=json.loads((root/'scene.json').read_text());row['points'][0]['x']='999'
            (root/'scene.json').write_text(canonical_json(row))
            manifest=json.loads((root/'manifest.json').read_text())
            manifest['files']['scene.json']=hashlib.sha256((root/'scene.json').read_bytes()).hexdigest()
            (root/'manifest.json').write_text(canonical_json(manifest))
            self.assertFalse(verify_scene_bundle(root))

    def test_cli_all_scientific_scene_types(self):
        with tempfile.TemporaryDirectory() as directory:
            for kind in ('right_triangle','parallelogram','circumcircle','function','vector_field','phase_portrait'):
                root=Path(directory)/kind
                self.assertEqual(main(['diagram',str(root),'--kind',kind,'--steps','20']),0)
                self.assertEqual(main(['check-diagram',str(root)]),0)
