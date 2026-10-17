"""Build a V1 experiment, offline scene, GLB and attached-data paper in a fresh root."""
from pathlib import Path
import sys
from nablamath.calc import CalculationSession
from nablamath.artifacts.bundle import create_bundle, save_bundle
from nablamath.living_papers_compiler import LivingPapersCompiler
from nablamath.spatial_engine_3d import SpatialEngine3D


def reproduce(destination):
    root=Path(destination)
    root.mkdir(parents=True,exist_ok=False)
    session=CalculationSession()
    records=[session.mathematics('manifold.stokes',coordinates=['x','y'],
                components={'1':'x'},bounds=[[0,2],[0,3]]).to_data(),
             session.mathematics('algebra_crypto.field',p=2,
                modulus=[1,1,0,1,1,0,0,0,1],left=[1,1,1,0,1,0,1,0],
                right=[1,1,0,0,0,0,0,1],operation='multiply').to_data(),
             session.mathematics('stochastic_info.channel',channel=[[.9,.1],[.1,.9]]).to_data()]
    bundle=create_bundle(records)
    save_bundle(bundle,root/'experiment.json')
    engine=SpatialEngine3D()
    mesh=engine.scalar_field([[0,.2,.4],[.2,1,.2],[.4,.2,0]])
    engine.standalone(mesh['vertices'],mesh['triangles'],root/'scene.html',audit_receipt=records[-1],colors=mesh['colors'])
    engine.export_glb(mesh['vertices'],mesh['triangles'],root/'scene.glb',audit_receipt=records[-1],colors=mesh['colors'])
    paper=LivingPapersCompiler().build(bundle,root/'paper',
        {'title':'Nabla 1.0 — laboratório reprodutível','authors':['Laboratório Nabla'],
         'abstract':'Três referências computacionais com recibos auditáveis: Stokes em um retângulo, multiplicação em GF(256) e capacidade de um canal binário simétrico.',
         'blocks':[{'kind':'heading','text':'Cálculo em variedades'},
                   {'kind':'paragraph','text':'A integral de fronteira é {{stokes}}, igual à integral da derivada exterior.'},
                   {'kind':'equation','text':'Integral na fronteira de ω = integral de dω no domínio'},
                   {'kind':'heading','text':'Álgebra exata e informação'},
                   {'kind':'table','headers':['Referência','Resultado'],
                    'rows':[['GF(256), 0x57 × 0x83','{{field}}'],['Canal binário, erro 0,1','{{capacity}} bits/uso']]},
                   {'kind':'heading','text':'Reprodutibilidade'},
                   {'kind':'paragraph','text':'O JSON anexado contém os recibos. O QR identifica o experimento e o HTML permite conferir os bytes sem um serviço externo. A superfície 3D associada é ilustrativa, não uma solução derivada desses cálculos.'}]},
        bindings={'stokes':'/receipts/0/result/result/boundary',
                  'field':'/receipts/1/result/result/coefficients',
                  'capacity':'/receipts/2/result/result/capacity_bits'})
    assert LivingPapersCompiler.verify(paper.directory)
    return root


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python examples/v1/reproduce.py NEW_DIRECTORY')
    print(reproduce(sys.argv[1]))
