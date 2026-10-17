"""Native equations, a reproducible figure, offline Three.js and animated GLB.

Run: python examples/v1/scientific_publication.py NEW_DIRECTORY
All display geometry is explicitly illustrative, not inferred from a receipt.
"""
from pathlib import Path
import json
import sys
import numpy as np
from PIL import Image, ImageDraw
from nablamath.calc import CalculationSession
from nablamath.artifacts.bundle import create_bundle
from nablamath.publishing.living_papers_compiler import (
    ScientificPaper, ScientificPaperProject, PDFQualityInspector,
    PublicationRecompiler, EditorialChecklist,
)
from nablamath.graphics.spatial_engine_3d import (
    SurfaceFactory, MeshData, SpatialExperiment, GLTFExporter, ColorMaps,
)


def reproduce(destination):
    root=Path(destination);root.mkdir(parents=True,exist_ok=False)
    session=CalculationSession()
    records=[session.execute('manifold_ricci',coordinates=['theta','phi'],
        metric=[[1,0],[0,'sin(theta)**2']]).to_data(),
        session.mathematics('stochastic_info.channel',channel=[[.9,.1],[.1,.9]]).to_data()]
    bundle=create_bundle(records)
    # Deterministic, high-resolution vector-like figure rendered to PNG.
    assets=root/'assets';assets.mkdir()
    image=Image.new('RGB',(1800,700),'white');draw=ImageDraw.Draw(image)
    for axis in ((160,590,1670,590),(160,100,160,590)):draw.line(axis,fill='#253f50',width=4)
    x=np.linspace(.001,.999,1000);y=1+(x*np.log2(x)+(1-x)*np.log2(1-x))
    line=[(float(160+1510*a),float(590-440*b)) for a,b in zip(x,y)]
    draw.line(line,fill='#167e85',width=7)
    draw.text((180,50),'Binary symmetric channel: capacity in bits per use',fill='#253f50',font_size=32)
    draw.text((1450,620),'Error probability',fill='#253f50',font_size=26)
    figure=assets/'channel.png';image.save(figure)
    paper=ScientificPaper('Geometry and information: a reproducible laboratory',
        authors=['Nabla Laboratory'],abstract='Exact local curvature and a finite-channel capacity calculation, with original data embedded in the publication.',
        bibliography=[{'id':'shannon','title':'A Mathematical Theory of Communication','authors':['Claude E. Shannon'],'year':1948,'type':'article','container':'Bell System Technical Journal'}])
    paper.section('Local geometry','sec:geometry')
    paper.paragraph('The unit sphere metric is evaluated in a regular coordinate chart. The scalar curvature is two; chart singularities remain excluded.')
    paper.equation('sin(theta)**2',['theta'],'eq:metric')
    paper.section('Information and uncertainty','sec:information')
    paper.equation('1+p*log(p)/log(2)+(1-p)*log(1-p)/log(2)',['p'],'eq:capacity')
    paper.paragraph('For crossover probability 0.1, the recorded capacity is {{capacity}} bits per use.')
    paper.table(['Quantity','Value'],[['Sphere scalar curvature','2'],['Channel capacity','{{capacity}}']],
        'Computed local and finite-channel references','tab:results')
    paper.figure('channel.png','Analytic capacity curve; illustrative samples evaluated with NumPy.','fig:capacity')
    paper.citation(['shannon']).reference('eq:capacity',prefix='Capacity formula: ')
    paper.section('Reproduction','sec:reproduction')
    paper.paragraph('Hashes identify the calculation record, not the truth of an arbitrary physical model. This PDF includes the experiment JSON and editable sources accompany the artifact.')
    project=ScientificPaperProject(paper,bundle,root/'publication',
        bindings={'capacity':'/receipts/1/result/result/capacity_bits'},asset_root=assets)
    built=project.build()
    quality=PDFQualityInspector.inspect(built.pdf,experiment_hash=bundle['content_id'])
    PDFQualityInspector.preview(built.pdf,root/'paper-preview.png')
    replay=PublicationRecompiler.typst(built.source,built.pdf)
    editorial=EditorialChecklist.inspect(paper,built.pdf,artifact=bundle)
    sphere=SurfaceFactory.icosphere(subdivisions=1)
    sphere=MeshData(sphere.vertices,sphere.triangles,tuple(p[2] for p in sphere.vertices),'Illustrative sphere')
    frames=[sphere.vertices,(np.asarray(sphere.vertices)*1.15).tolist()]
    spatial=SpatialExperiment(sphere,records,frames=frames,times=[0,1])
    spatial.build(root/'spatial',include_manim=True)
    # Textured animated reference for the independent Khronos validator.
    texture=Image.new('RGB',(2,2),'#167e85')
    import io
    stream=io.BytesIO();texture.save(stream,format='PNG')
    uv=[[(np.arctan2(p[2],p[0])+np.pi)/(2*np.pi),(p[1]+1)/2] for p in sphere.vertices]
    GLTFExporter().write(sphere,root/'textured-animated.glb',audit_receipt=records[0],
        colors=ColorMaps.map(sphere.scalars),uv=uv,texture_png=stream.getvalue(),frames=frames,times=[0,1])
    report={'pdf_layout':quality,'portable_source_replay':replay,'editorial':editorial,
            'spatial_verified':SpatialExperiment.verify(root/'spatial'),
            'scientific_acceptance_established':False}
    (root/'report.json').write_text(json.dumps(report,indent=2))
    assert quality['layout_checks_passed'] and replay['text_matches'] and editorial['automated_checks_passed']
    assert report['spatial_verified']
    return root


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: scientific_publication.py NEW_DIRECTORY')
    print(reproduce(sys.argv[1]))
