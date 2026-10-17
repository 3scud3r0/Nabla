"""Offline 3-D scenes, glTF/GLB export and native Manim source generation.

The default standalone viewer contains a small native WebGL renderer, so it
needs neither a CDN nor Node. A trusted, locally supplied Three.js UMD build
can instead be embedded as a base64 script. A frame rate is hardware-dependent.
"""
import base64
import hashlib
import html
import json
import math
import re
from pathlib import Path

from ..calc.receipt import verify_receipt
from ..core.semantic_ir import canonical_json
from ..graphics.webgl_exporter import WebGLExporter, _publish_bytes
from ..graphics.manim_animator import ManimAnimator


_VIEWER = r'''
const data=JSON.parse(document.getElementById('scene').textContent);
const canvas=document.querySelector('canvas');
let yaw=.6,pitch=.4,zoom=1,drag=null;
const points=data.positions,indices=data.indices;
const bounds=[[Infinity,-Infinity],[Infinity,-Infinity],[Infinity,-Infinity]];for(const p of points)for(let k=0;k<3;k++){bounds[k][0]=Math.min(bounds[k][0],p[k]);bounds[k][1]=Math.max(bounds[k][1],p[k]);}
const center=bounds.map(b=>(b[0]+b[1])/2),scale=Math.max(...bounds.map(b=>b[1]-b[0]))||1;
const positions=points.flatMap(p=>p.map((v,k)=>2*(v-center[k])/scale));
const colors=data.colors.flat(),normals=data.normals.flat();
function resize(){const d=Math.min(devicePixelRatio||1,2);canvas.width=Math.round(canvas.clientWidth*d);canvas.height=Math.round(canvas.clientHeight*d);}
const vertex=`attribute vec3 position; attribute vec3 color; attribute vec3 normal;
uniform mat4 transform; uniform mat4 rotation; varying vec3 tint;
void main(){gl_Position=transform*vec4(position,1.); vec3 n=normalize((rotation*vec4(normal,0.)).xyz);
tint=color*(.35+.65*abs(dot(n,normalize(vec3(.4,.7,1.)))));}`;
const fragment=`precision mediump float; varying vec3 tint; void main(){gl_FragColor=vec4(tint,1.);}`;
function matrix(){const c=Math.cos(yaw),s=Math.sin(yaw),a=Math.cos(pitch),b=Math.sin(pitch);
const rotation=[c,s*b,-s*a,0,0,a,b,0,s,-c*b,c*a,0,0,0,0,1];
const ratio=canvas.width/canvas.height;let transform=rotation.slice();
for(let col=0;col<4;col++){transform[col*4]*=zoom/Math.max(1,ratio);transform[col*4+1]*=zoom/Math.max(1,1/ratio);transform[col*4+2]*=.25;}
return {rotation,transform};}
let draw;
if(data.renderer==='three'){
 const renderer=new THREE.WebGLRenderer({canvas,antialias:true});renderer.setClearColor(0x101e2c);
 const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(45,1,.01,100);
 const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.Float32BufferAttribute(positions,3));
 geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors,3));geometry.setIndex(indices);geometry.computeVertexNormals();
 const mesh=new THREE.Mesh(geometry,new THREE.MeshBasicMaterial({vertexColors:true,side:THREE.DoubleSide}));scene.add(mesh);
 draw=()=>{resize();renderer.setSize(canvas.width,canvas.height,false);camera.aspect=canvas.width/canvas.height;camera.updateProjectionMatrix();camera.position.set(0,0,4/zoom);mesh.rotation.set(pitch,yaw,0);renderer.render(scene,camera);};
}else{
 const gl=canvas.getContext('webgl',{antialias:true});if(!gl)throw Error('WebGL unavailable in this browser');
 const program=gl.createProgram();
 for(const [kind,source] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]){
  const shader=gl.createShader(kind);gl.shaderSource(shader,source);gl.compileShader(shader);
  if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(shader));gl.attachShader(program,shader);
 }
 gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw Error('Shader linking failed');gl.useProgram(program);
 // Expand triangle corners, avoiding the WebGL1 uint32-index extension.
 for(const [name,values] of [['position',positions],['color',colors],['normal',normals]]){
  const buffer=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,buffer);
  gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(indices.flatMap(i=>values.slice(i*3,i*3+3))),gl.STATIC_DRAW);
  const location=gl.getAttribLocation(program,name);gl.enableVertexAttribArray(location);gl.vertexAttribPointer(location,3,gl.FLOAT,false,0,0);
 }
 gl.enable(gl.DEPTH_TEST);
 draw=()=>{resize();gl.viewport(0,0,canvas.width,canvas.height);gl.clearColor(.06,.12,.17,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
 const m=matrix();for(const key of ['rotation','transform'])gl.uniformMatrix4fv(gl.getUniformLocation(program,key),false,m[key]);
 gl.drawArrays(gl.TRIANGLES,0,indices.length);};
}
canvas.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY];canvas.setPointerCapture(e.pointerId);});
canvas.addEventListener('pointerup',()=>drag=null);canvas.addEventListener('pointercancel',()=>drag=null);
canvas.addEventListener('pointermove',e=>{if(drag){yaw+=(e.clientX-drag[0])*.01;pitch+=(e.clientY-drag[1])*.01;drag=[e.clientX,e.clientY];draw();}});
canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=Math.max(.15,Math.min(8,zoom*Math.exp(-e.deltaY*.001)));draw();},{passive:false});
window.addEventListener('resize',draw);draw();
document.getElementById('download').onclick=()=>{const blob=new Blob([JSON.stringify(data.receipt,null,2)],{type:'application/json'});
const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='receipt.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};
'''


class SpatialEngine3D:
    def __init__(self, *, max_vertices=100000, max_triangles=200000):
        self.exporter = WebGLExporter(max_vertices=max_vertices,max_triangles=max_triangles)

    @staticmethod
    def scalar_field(values, *, spacing=(1.,1.), height_scale=1.):
        """Map a 2-D scalar grid to a colored heightfield, Y up."""
        vertices, triangles = WebGLExporter.heightfield(values,spacing=spacing,height_scale=height_scale)
        flattened = [float(v) for row in values for v in row]
        if not all(math.isfinite(v) for v in flattened):
            raise ValueError('Finite scalar field required')
        lo,hi = min(flattened),max(flattened)
        fractions = [(v-lo)/(hi-lo) if hi>lo else .5 for v in flattened]
        colors = [[t,.3+.4*(1-abs(2*t-1)),1-t] for t in fractions]
        return {'vertices':vertices,'triangles':triangles,'colors':colors,
                'range':[lo,hi],'representation':'colored heightfield, not a volume isosurface'}

    @staticmethod
    def vector_field(origins, vectors, *, scale=1., width=.03):
        """Represent finite vector samples by triangular arrow glyphs."""
        import numpy as np
        x,v = np.asarray(origins,dtype=float),np.asarray(vectors,dtype=float)
        if x.ndim != 2 or x.shape[1:] != (3,) or x.shape != v.shape or not 1<=len(x)<=10000:
            raise ValueError('Matching bounded XYZ samples required')
        if not np.isfinite(x).all() or not np.isfinite(v).all() or not math.isfinite(scale) or scale<=0 or not math.isfinite(width) or width<=0:
            raise ValueError('Finite vectors and positive glyph scales required')
        vertices,triangles = [],[]
        for origin,direction in zip(x,v):
            norm = np.linalg.norm(direction)
            if norm == 0:
                continue
            tangent = direction/norm
            axis = np.eye(3)[int(np.argmin(abs(tangent)))]
            side = np.cross(tangent,axis);side *= width/np.linalg.norm(side)
            tip = origin+scale*direction
            base = len(vertices)
            vertices.extend([origin.tolist(),(tip-.25*scale*direction+side).tolist(),tip.tolist(),
                             (tip-.25*scale*direction-side).tolist()])
            triangles.extend([[base,base+1,base+2],[base,base+2,base+3]])
        if not triangles:
            raise ValueError('At least one nonzero vector required')
        return {'vertices':vertices,'triangles':triangles,'representation':'sampled vector arrow glyphs'}

    def standalone(self, vertices, triangles, destination, *, audit_receipt, colors=None,
                   title='Nabla · spatial experiment', three_js=None):
        """Write an offline viewer. Optional Three.js must be a trusted UMD build.

No network fetch is performed. Mathematical data are inert escaped JSON.
The supplied engine is executable application code, not an untrusted asset.
"""
        if not isinstance(title,str) or not 1<=len(title)<=4096:
            raise ValueError('Bounded scene title required')
        document, binary = self.exporter._mesh(vertices,triangles,audit_receipt,colors)
        # Reuse the exporter validation, float32 rounding and generated normals.
        import struct
        def accessor(index):
            spec = document['accessors'][index]
            view = document['bufferViews'][spec['bufferView']]
            size = {'VEC3':3,'VEC4':4,'SCALAR':1}[spec['type']]
            code = 'f' if spec['componentType']==5126 else 'I'
            offset = view.get('byteOffset',0)+spec.get('byteOffset',0)
            values = struct.unpack_from('<'+code*(spec['count']*size),binary,offset)
            return [list(values[i:i+size]) for i in range(0,len(values),size)]
        primitive = document['meshes'][0]['primitives'][0]
        attributes = primitive['attributes']
        positions = accessor(attributes['POSITION'])
        rgb = accessor(attributes['COLOR_0']) if 'COLOR_0' in attributes else [[.2,.65,.9] for _ in positions]
        scene = {'positions':positions,'normals':accessor(attributes['NORMAL']),
                 'colors':[c[:3] for c in rgb], 'indices':[v[0] for v in accessor(primitive['indices'])],
                 'receipt':audit_receipt,'renderer':'three' if three_js else 'native'}
        engine = ''
        if three_js is not None:
            with Path(three_js).open('rb') as stream:
                raw = stream.read(4*1024*1024+1)
            if len(raw)>4*1024*1024 or b'THREE' not in raw:
                raise ValueError('Bounded trusted Three.js UMD script required')
            engine = '<script src="data:text/javascript;base64,'+base64.b64encode(raw).decode()+'"></script>'
        encoded = canonical_json(scene).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
        page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        page += '<title>'+html.escape(title)+'</title><style>body{margin:0;background:#101e2c;color:#e3edf5;font:15px system-ui}header,footer{padding:16px}canvas{display:block;width:100%;height:75vh;touch-action:none}button{padding:8px;border:0;border-radius:5px}small{overflow-wrap:anywhere}</style>'
        page += '<header><h1>'+html.escape(title)+'</h1>Drag to orbit · Scroll to zoom</header><canvas aria-label="Interactive 3D mesh"></canvas>'
        page += '<footer><button id="download">Download audit receipt</button><p><small>Receipt SHA-256: '+html.escape(audit_receipt['content_id'])+'</small></p></footer>'
        page += '<script id="scene" type="application/json">'+encoded+'</script>'+engine+'<script>'+_VIEWER+'</script></html>'
        return _publish_bytes(destination,page.encode())

    def export_gltf(self, vertices, triangles, destination, *, audit_receipt, colors=None):
        return self.exporter.export_gltf(vertices,triangles,destination,audit_receipt=audit_receipt,colors=colors)

    def export_glb(self, vertices, triangles, destination, *, audit_receipt, colors=None):
        return self.exporter.export_glb(vertices,triangles,destination,audit_receipt=audit_receipt,colors=colors)

    @staticmethod
    def manim(audit_receipt, destination, *, duration=3):
        return ManimAnimator(duration=duration).export_script(audit_receipt,destination)

    @staticmethod
    def trajectory_animation(points, audit_receipt, *, errors=None, duration=5):
        """Native Manim ThreeDScene source with orbit and explicit error bars.

This depicts supplied samples associated with a receipt. It does not assert
that samples were computed by that receipt or invent analytic solution steps.
"""
        if not verify_receipt(audit_receipt):
            raise ValueError('Valid receipt required')
        if not isinstance(points,(list,tuple)) or not 2<=len(points)<=10000 or any(len(p)!=3 for p in points):
            raise ValueError('2–10000 XYZ samples required')
        if any(type(v) not in (int,float) or not math.isfinite(v) for p in points for v in p):
            raise ValueError('Finite XYZ samples required')
        if errors is None:
            errors = [0.]*len(points)
        if len(errors)!=len(points) or any(type(e) not in (int,float) or not math.isfinite(e) or e<0 for e in errors):
            raise ValueError('One nonnegative error radius per point required')
        if type(duration) not in (int,float) or not math.isfinite(duration) or not .2<=duration<=60:
            raise ValueError('Duration must be .2–60 seconds')
        data = {'points':points,'errors':errors,'duration':duration,'hash':audit_receipt['content_id']}
        return '''import json
from manim import ThreeDScene, ThreeDAxes, VMobject, Text, Line, Create, BLUE, DOWN, RIGHT, DEGREES
DATA=json.loads('''+repr(canonical_json(data))+''')
class NablaSpatialAnimation(ThreeDScene):
    def construct(self):
        audit=Text('SHA-256: '+DATA['hash'],font_size=10).to_corner(DOWN+RIGHT)
        self.add_fixed_in_frame_mobjects(audit)
        points=DATA['points']
        ranges=[]
        for k in range(3):
            low=min(p[k]-e for p,e in zip(points,DATA['errors']))
            high=max(p[k]+e for p,e in zip(points,DATA['errors']))
            pad=max((high-low)*.1,.1)
            ranges.append([low-pad,high+pad,(high-low+2*pad)/4])
        axes=ThreeDAxes(x_range=ranges[0],y_range=ranges[1],z_range=ranges[2])
        curve=VMobject(color=BLUE).set_points_as_corners([axes.c2p(*p) for p in points])
        self.set_camera_orientation(phi=65*DEGREES,theta=-45*DEGREES)
        self.add(axes)
        for p,e in zip(points,DATA['errors']):
            if e: self.add(Line(axes.c2p(p[0],p[1],p[2]-e),axes.c2p(p[0],p[1],p[2]+e)))
        self.begin_ambient_camera_rotation(rate=.12)
        self.play(Create(curve),run_time=DATA['duration'])
        self.stop_ambient_camera_rotation()
'''

# New mesh construction, scalar/vector field sampling and surface diagnostics.
from dataclasses import dataclass
from importlib import resources
from ..math._structured import expression, names, sympy


def _finite_points(values, minimum=1, maximum=1000000):
    import numpy as np
    points=np.asarray(values,dtype=float)
    if points.ndim!=2 or points.shape[1]!=3 or not minimum<=len(points)<=maximum or not np.isfinite(points).all():
        raise ValueError('Bounded finite XYZ point array required')
    return points


@dataclass(frozen=True)
class MeshData:
    """Validated triangular surface with immutable position/topology arrays."""
    vertices: tuple
    triangles: tuple
    scalars: tuple | None = None
    label: str = 'Nabla mesh'

    def __post_init__(self):
        import numpy as np
        points=_finite_points(self.vertices,3,1000000)
        faces=np.asarray(self.triangles)
        if faces.ndim!=2 or faces.shape[1]!=3 or not 1<=len(faces)<=2000000 or faces.dtype.kind not in 'iu':
            raise ValueError('Integer triangle index array required')
        if faces.min()<0 or faces.max()>=len(points) or np.any(np.diff(np.sort(faces,axis=1),axis=1)==0):
            raise ValueError('Triangles contain repeated or out-of-bounds vertices')
        areas=np.linalg.norm(np.cross(points[faces[:,1]]-points[faces[:,0]],points[faces[:,2]]-points[faces[:,0]]),axis=1)/2
        if np.any(areas<=1e-15):raise ValueError('Zero-area or sub-resolution triangles are not accepted')
        if not isinstance(self.label,str) or not 1<=len(self.label)<=4096:raise ValueError('Bounded mesh label required')
        if self.scalars is not None:
            values=np.asarray(self.scalars,dtype=float)
            if values.shape!=(len(points),) or not np.isfinite(values).all():raise ValueError('One finite scalar per vertex required')
            object.__setattr__(self,'scalars',tuple(float(v) for v in values))
        object.__setattr__(self,'vertices',tuple(tuple(float(v) for v in p) for p in points))
        object.__setattr__(self,'triangles',tuple(tuple(int(v) for v in face) for face in faces))

    def normals(self):
        """Area-weighted vertex normals, with zero for cancelling incident faces."""
        import numpy as np
        points=np.asarray(self.vertices);faces=np.asarray(self.triangles)
        vectors=np.cross(points[faces[:,1]]-points[faces[:,0]],points[faces[:,2]]-points[faces[:,0]])
        normals=np.zeros_like(points)
        for slot in range(3):np.add.at(normals,faces[:,slot],vectors)
        lengths=np.linalg.norm(normals,axis=1);nonzero=lengths>0
        normals[nonzero]/=lengths[nonzero,None]
        return normals.tolist()

    def bounds(self):
        import numpy as np
        points=np.asarray(self.vertices)
        return {'minimum':points.min(axis=0).tolist(),'maximum':points.max(axis=0).tolist()}

    def surface_area(self):
        import numpy as np
        points=np.asarray(self.vertices);faces=np.asarray(self.triangles)
        return float(np.linalg.norm(np.cross(points[faces[:,1]]-points[faces[:,0]],points[faces[:,2]]-points[faces[:,0]]),axis=1).sum()/2)

    def topology(self):
        """Edge incidence, Euler characteristic and orientation diagnostics."""
        counts={};directions={};used=set()
        for face in self.triangles:
            used.update(face)
            for a,b in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])):
                edge=tuple(sorted((a,b)))
                counts[edge]=counts.get(edge,0)+1
                directions[edge]=directions.get(edge,0)+(1 if a<b else -1)
        boundary=[edge for edge,count in counts.items() if count==1]
        nonmanifold=[edge for edge,count in counts.items() if count>2]
        inconsistent=[edge for edge,count in counts.items() if count==2 and directions[edge]!=0]
        return {'vertices_used':len(used),'unused_vertices':len(self.vertices)-len(used),
                'edges':len(counts),'faces':len(self.triangles),
                'euler_characteristic':len(used)-len(counts)+len(self.triangles),
                'boundary_edges':[list(e) for e in boundary],
                'nonmanifold_edges':[list(e) for e in nonmanifold],
                'inconsistent_orientation':[list(e) for e in inconsistent],
                'closed_oriented_surface':not boundary and not nonmanifold and not inconsistent}

    def signed_volume(self):
        import numpy as np
        if not self.topology()['closed_oriented_surface']:
            raise ValueError('Volume requires a closed consistently oriented triangular surface')
        points=np.asarray(self.vertices);faces=np.asarray(self.triangles)
        # Shift the origin near the mesh to reduce cancellation for distant geometry.
        shifted=points-points.mean(axis=0)
        return float(np.einsum('ij,ij->i',shifted[faces[:,0]],np.cross(shifted[faces[:,1]],shifted[faces[:,2]])).sum()/6)

    def transform(self, matrix):
        """Apply a nonsingular affine 4x4 transform, reversing winding on reflection."""
        import numpy as np
        value=np.asarray(matrix,dtype=float)
        if value.shape!=(4,4) or not np.isfinite(value).all() or not np.allclose(value[3],[0,0,0,1],atol=1e-12,rtol=0):
            raise ValueError('Finite affine homogeneous 4x4 matrix required')
        determinant=float(np.linalg.det(value[:3,:3]))
        if abs(determinant)<1e-14:raise ValueError('Singular mesh transform')
        points=np.asarray(self.vertices)@value[:3,:3].T+value[:3,3]
        faces=self.triangles if determinant>0 else tuple((a,c,b) for a,b,c in self.triangles)
        return MeshData(tuple(map(tuple,points)),faces,self.scalars,self.label)

    def to_data(self):
        return {'vertices':[list(p) for p in self.vertices],'triangles':[list(p) for p in self.triangles],
                'scalars':None if self.scalars is None else list(self.scalars),'label':self.label}


class ColorMaps:
    """Piecewise-linear perceptual map samples, not full 256-entry LUT replicas."""
    ANCHORS={
        'viridis':((.267,.005,.329),(.230,.322,.546),(.128,.567,.551),(.369,.789,.383),(.993,.906,.144)),
        'plasma':((.050,.030,.528),(.495,.012,.658),(.798,.280,.470),(.973,.586,.252),(.940,.975,.131)),
        'magma':((.001,.000,.014),(.316,.072,.485),(.716,.215,.475),(.987,.536,.382),(.987,.991,.750)),
    }

    @classmethod
    def map(cls, values, kind='viridis', lower=None, upper=None):
        import numpy as np
        if kind not in cls.ANCHORS:raise ValueError('Colormap is viridis, plasma or magma')
        scalar=np.asarray(values,dtype=float)
        if scalar.ndim!=1 or not 1<=len(scalar)<=1000000 or not np.isfinite(scalar).all():
            raise ValueError('Finite scalar color samples required')
        lower=float(scalar.min()) if lower is None else float(lower)
        upper=float(scalar.max()) if upper is None else float(upper)
        if not math.isfinite(lower) or not math.isfinite(upper) or lower>upper:raise ValueError('Invalid color range')
        fraction=np.full_like(scalar,.5) if lower==upper else np.clip((scalar-lower)/(upper-lower),0,1)
        anchors=np.asarray(cls.ANCHORS[kind]);nodes=np.linspace(0,1,len(anchors))
        return np.column_stack([np.interp(fraction,nodes,anchors[:,i]) for i in range(3)]).tolist()


class SurfaceFactory:
    """New parametric/implicit/ellipsoidal surface construction algorithms."""
    @staticmethod
    def parametric(components, parameters, bounds, shape=(51,51), *, periodic=(False,False)):
        import numpy as np
        parameters=names(parameters,2)
        if len(parameters)!=2 or len(components)!=3 or len(bounds)!=2 or len(shape)!=2 or len(periodic)!=2:
            raise ValueError('A surface needs two parameters and three XYZ components')
        if any(type(v) is not int or not 2<=v<=512 for v in shape) or shape[0]*shape[1]>100000:
            raise ValueError('Parametric surface grid budget exceeded')
        if any(type(v) is not bool for v in periodic):raise ValueError('Periodicity flags must be boolean')
        intervals=np.asarray(bounds,dtype=float)
        if intervals.shape!=(2,2) or not np.isfinite(intervals).all() or np.any(intervals[:,1]<=intervals[:,0]):
            raise ValueError('Two finite increasing parameter intervals required')
        grids=np.meshgrid(*(np.linspace(a,b,count,endpoint=not wrap) for (a,b),count,wrap in zip(intervals,shape,periodic)),indexing='ij')
        values=[]
        for source in components:
            value,symbols=expression(source,parameters)
            function=sympy().lambdify(symbols,value,modules='numpy',cse=True)
            array=np.broadcast_to(np.asarray(function(*grids),dtype=float),tuple(shape))
            if not np.isfinite(array).all():raise ValueError('Surface expression is singular on the sample grid')
            values.append(array)
        points=np.stack(values,axis=-1).reshape(-1,3)
        faces=[];rows,columns=shape
        for i in range(rows if periodic[0] else rows-1):
            for j in range(columns if periodic[1] else columns-1):
                a=i*columns+j;b=((i+1)%rows)*columns+j
                c=i*columns+(j+1)%columns;d=((i+1)%rows)*columns+(j+1)%columns
                faces.extend(((a,b,c),(b,d,c)))
        return MeshData(tuple(map(tuple,points)),tuple(faces),label='Parametric surface')

    @staticmethod
    def icosphere(radius=1., subdivisions=2, center=(0.,0.,0.)):
        import numpy as np
        if type(subdivisions) is not int or not 0<=subdivisions<=6 or type(radius) not in (int,float) or not math.isfinite(radius) or radius<=0:
            raise ValueError('Positive radius and 0–6 icosphere subdivisions required')
        center=np.asarray(center,dtype=float)
        if center.shape!=(3,) or not np.isfinite(center).all():raise ValueError('Finite sphere center required')
        phi=(1+math.sqrt(5))/2
        vertices=[(-1,phi,0),(1,phi,0),(-1,-phi,0),(1,-phi,0),(0,-1,phi),(0,1,phi),(0,-1,-phi),(0,1,-phi),(phi,0,-1),(phi,0,1),(-phi,0,-1),(-phi,0,1)]
        points=[np.asarray(v,dtype=float)/np.linalg.norm(v) for v in vertices]
        faces=[(0,11,5),(0,5,1),(0,1,7),(0,7,10),(0,10,11),(1,5,9),(5,11,4),(11,10,2),(10,7,6),(7,1,8),(3,9,4),(3,4,2),(3,2,6),(3,6,8),(3,8,9),(4,9,5),(2,4,11),(6,2,10),(8,6,7),(9,8,1)]
        for _ in range(subdivisions):
            cache={};next_faces=[]
            def midpoint(a,b):
                key=tuple(sorted((a,b)))
                if key not in cache:
                    value=points[a]+points[b];value=value/np.linalg.norm(value)
                    cache[key]=len(points);points.append(value)
                return cache[key]
            for a,b,c in faces:
                ab,bc,ca=midpoint(a,b),midpoint(b,c),midpoint(c,a)
                next_faces.extend(((a,ab,ca),(b,bc,ab),(c,ca,bc),(ab,bc,ca)))
            faces=next_faces
        return MeshData(tuple(tuple(center+radius*v) for v in points),tuple(faces),label='Icosphere')

    @staticmethod
    def ellipsoid(tensor, *, center=(0.,0.,0.), scale=1., subdivisions=2):
        """Unit quadratic-form ellipsoid xᵀ G x=scale², requiring G positive definite."""
        import numpy as np
        matrix=np.asarray(tensor,dtype=float)
        if matrix.shape!=(3,3) or not np.isfinite(matrix).all() or not np.allclose(matrix,matrix.T,atol=1e-12,rtol=1e-12):
            raise ValueError('Symmetric finite 3x3 tensor required')
        eigenvalues,vectors=np.linalg.eigh(matrix)
        if eigenvalues.min()<=0:raise ValueError('A Euclidean ellipsoid requires a positive-definite tensor')
        if not math.isfinite(scale) or scale<=0:raise ValueError('Positive ellipsoid scale required')
        transform=np.eye(4);transform[:3,:3]=vectors@np.diag(scale/np.sqrt(eigenvalues));transform[:3,3]=center
        mesh=SurfaceFactory.icosphere(subdivisions=subdivisions).transform(transform)
        return MeshData(mesh.vertices,mesh.triangles,label='Positive-definite tensor ellipsoid')

    @staticmethod
    def implicit(field, level=0., *, origin=(0.,0.,0.), spacing=(1.,1.,1.)):
        """Marching tetrahedra on a finite scalar grid, with shared edge vertices.

        Every cube uses the same six-tetrahedra decomposition around its body
        diagonal. Face orientation follows increasing scalar value. The result
        is a piecewise-linear isosurface; sampling error and unresolved small
        features remain distinct from mesh validity.
        """
        import numpy as np
        values=np.asarray(field,dtype=float);origin=np.asarray(origin,dtype=float);spacing=np.asarray(spacing,dtype=float)
        if values.ndim!=3 or any(not 2<=v<=64 for v in values.shape) or values.size>131072 or not np.isfinite(values).all():
            raise ValueError('Finite 3D scalar grid with axes 2–64 and <=131072 samples required')
        if origin.shape!=(3,) or spacing.shape!=(3,) or not np.isfinite(origin).all() or not np.isfinite(spacing).all() or (spacing<=0).any() or not math.isfinite(level):
            raise ValueError('Finite origin, positive spacing and finite isovalue required')
        offsets=np.asarray([(0,0,0),(1,0,0),(1,1,0),(0,1,0),(0,0,1),(1,0,1),(1,1,1),(0,1,1)])
        tetrahedra=((0,1,2,6),(0,2,3,6),(0,3,7,6),(0,7,4,6),(0,4,5,6),(0,5,1,6))
        edges=((0,1),(0,2),(0,3),(1,2),(1,3),(2,3))
        points=[];faces=[];cache={}
        for index in np.ndindex(tuple(v-1 for v in values.shape)):
            nodes=offsets+np.asarray(index)
            samples=np.asarray([values[tuple(v)]-level for v in nodes])
            if (samples>=0).all() or (samples<0).all():continue
            xyz=origin+nodes*spacing
            for tet in tetrahedra:
                selected=np.asarray(tet);v=samples[selected];p=xyz[selected];crossings=[]
                if (v>=0).all() or (v<0).all():continue
                gradient=np.linalg.solve(p[1:]-p[0],v[1:]-v[0])
                for first,second in edges:
                    if (v[first]>=0)==(v[second]>=0):continue
                    first_node=tuple(nodes[tet[first]]);second_node=tuple(nodes[tet[second]])
                    fraction=v[first]/(v[first]-v[second])
                    if fraction==0:key=('node',first_node)
                    elif fraction==1:key=('node',second_node)
                    else:key=('edge',*sorted((first_node,second_node)))
                    if key not in cache:
                        cache[key]=len(points);points.append(p[first]+fraction*(p[second]-p[first]))
                    if cache[key] not in crossings:crossings.append(cache[key])
                if len(crossings)<3:continue
                polygon=np.asarray([points[i] for i in crossings]);center=polygon.mean(axis=0)
                normal=gradient/np.linalg.norm(gradient)
                u=polygon[0]-center
                if np.linalg.norm(u)<1e-14:continue
                u/=np.linalg.norm(u);w=np.cross(normal,u)
                angles=np.arctan2((polygon-center)@w,(polygon-center)@u)
                ring=[crossings[i] for i in np.argsort(angles)]
                for j in range(1,len(ring)-1):
                    face=(ring[0],ring[j],ring[j+1])
                    area=np.cross(points[face[1]]-points[face[0]],points[face[2]]-points[face[0]])
                    if np.linalg.norm(area)>1e-14:faces.append(face)
        if not faces:raise ValueError('No nondegenerate isosurface crosses the supplied grid')
        unique=list(dict.fromkeys(faces));used=sorted({i for face in unique for i in face});remap={old:new for new,old in enumerate(used)}
        return MeshData(tuple(tuple(points[i]) for i in used),tuple(tuple(remap[i] for i in face) for face in unique),label='Marching-tetrahedra isosurface')


class VectorFieldVisualizer:
    """Adaptive streamlines, parallel-transport tubes and physical field glyphs."""
    @staticmethod
    def streamline(components, initial, *, duration=1., samples=201,
                   bounds=None, coordinates=('x','y','z'), direction=1):
        import numpy as np
        from scipy.integrate import solve_ivp
        coordinates=names(coordinates,3)
        if len(coordinates)!=3 or len(components)!=3:raise ValueError('Three-dimensional vector field required')
        point=np.asarray(initial,dtype=float)
        if point.shape!=(3,) or not np.isfinite(point).all() or type(samples) is not int or not 2<=samples<=10001 or not 0<duration<=10000:
            raise ValueError('Invalid streamline initial data or sample budget')
        if type(direction) is not int or direction not in (-1,1):raise ValueError('Streamline direction is +/-1')
        symbols=tuple(map(sympy().Symbol,coordinates))
        expressions=[expression(v,coordinates)[0] for v in components]
        kernel=sympy().lambdify(symbols,expressions,modules='numpy',cse=True)
        def rhs(time,state):
            value=np.asarray(kernel(*state),dtype=float)
            if value.shape!=(3,) or not np.isfinite(value).all():raise ArithmeticError('Nonfinite streamline field')
            return direction*value
        events=[]
        if bounds is not None:
            box=np.asarray(bounds,dtype=float)
            if box.shape!=(3,2) or not np.isfinite(box).all() or np.any(box[:,1]<=box[:,0]) or np.any(point<box[:,0]) or np.any(point>box[:,1]):
                raise ValueError('Initial streamline point must be inside a finite box')
            def exit_box(time,state):return float(np.min(np.minimum(state-box[:,0],box[:,1]-state)))
            exit_box.terminal=True;exit_box.direction=-1;events=[exit_box]
        solution=solve_ivp(rhs,(0,duration),point,dense_output=True,events=events,rtol=1e-8,atol=1e-10)
        if not solution.success:raise ArithmeticError('Streamline integration failed: '+solution.message)
        end=float(solution.t[-1]);times=np.linspace(0,end,samples);points=solution.sol(times).T
        speed=np.linalg.norm(np.asarray([rhs(t,p) for t,p in zip(times,points)]),axis=1)
        return {'times':times.tolist(),'points':points.tolist(),'speed':speed.tolist(),
                'stopped_at_boundary':bool(events and any(len(v) for v in solution.t_events)),
                'scope':'Numerical integral curve; no topology/completeness guarantee'}

    @staticmethod
    def tube(points, radius=.02, sides=8):
        """Build an open-ended tube using minimally rotating discrete frames."""
        import numpy as np
        curve=_finite_points(points,2,10000)
        if type(sides) is not int or not 3<=sides<=64 or not math.isfinite(radius) or radius<=0:
            raise ValueError('Positive tube radius and 3–64 polygon sides required')
        differences=np.diff(curve,axis=0)
        if np.any(np.linalg.norm(differences,axis=1)<1e-14):raise ValueError('Tube needs distinct consecutive samples')
        tangents=np.empty_like(curve);tangents[0]=differences[0];tangents[-1]=differences[-1]
        if len(curve)>2:tangents[1:-1]=differences[:-1]+differences[1:]
        lengths=np.linalg.norm(tangents,axis=1)
        if np.any(lengths<1e-14):raise ValueError('Tube has an unresolved 180-degree cusp')
        tangents/=lengths[:,None]
        axis=np.eye(3)[np.argmin(abs(tangents[0]))]
        normal=np.cross(tangents[0],axis);normal/=np.linalg.norm(normal)
        vertices=[];faces=[]
        for i,(point,tangent) in enumerate(zip(curve,tangents)):
            projected=normal-tangent*np.dot(normal,tangent)
            if np.linalg.norm(projected)<1e-10:
                axis=np.eye(3)[np.argmin(abs(tangent))];projected=np.cross(tangent,axis)
            normal=projected/np.linalg.norm(projected);binormal=np.cross(tangent,normal)
            for j in range(sides):
                angle=2*math.pi*j/sides
                vertices.append(tuple(point+radius*(math.cos(angle)*normal+math.sin(angle)*binormal)))
            if i:
                for j in range(sides):
                    a=(i-1)*sides+j;b=(i-1)*sides+(j+1)%sides;c=i*sides+j;d=i*sides+(j+1)%sides
                    faces.extend(((a,b,c),(b,d,c)))
        return MeshData(tuple(vertices),tuple(faces),label='Streamline tube')

    @staticmethod
    def wavefunction_density(source, axes, *, coordinates=('x','y','z')):
        """Sample complex ψ, returning |ψ|² and an explicit finite-box norm."""
        import numpy as np
        coordinates=names(coordinates,3)
        if len(coordinates)!=3 or len(axes)!=3:raise ValueError('Three spatial axes required')
        arrays=[np.asarray(axis,dtype=float) for axis in axes]
        if any(a.ndim!=1 or not 2<=len(a)<=128 or not np.isfinite(a).all() or np.any(np.diff(a)<=0) for a in arrays) or math.prod(map(len,arrays))>1000000:
            raise ValueError('Wavefunction sampling grid budget exceeded')
        value,symbols=expression(source,coordinates)
        kernel=sympy().lambdify(symbols,value,modules='numpy',cse=True)
        grids=np.meshgrid(*arrays,indexing='ij');psi=np.broadcast_to(np.asarray(kernel(*grids),dtype=complex),tuple(map(len,arrays)))
        if not np.isfinite(psi).all():raise ValueError('Wavefunction is singular on the sample grid')
        density=abs(psi)**2
        integral=density
        integrate=(np.trapezoid if hasattr(np, 'trapezoid') else np.trapz)
        for axis in reversed(range(3)):integral=integrate(integral,arrays[axis],axis=axis)
        return {'density':density.tolist(),'phase':np.angle(psi).tolist(),
                'finite_box_norm_estimate':float(integral),
                'scope':'Trapezoidal finite-box estimate; tails and normalization not certified'}


class GLTFExporter:
    """New glTF 2.0 builder with textures and animated morph targets.

    Buffers are little-endian, four-byte aligned and embedded in GLB or in the
    JSON data URI. POSITION bounds refer to rounded float32 storage. Animation
    interpolation is LINEAR between sampled morph targets; it does not solve
    additional physics between simulation snapshots.
    """
    def __init__(self, *, max_vertices=1000000, max_binary_bytes=128*1024*1024):
        if type(max_vertices) is not int or not 3<=max_vertices<=1000000 or type(max_binary_bytes) is not int or not 1024<=max_binary_bytes<=256*1024*1024:
            raise ValueError('Invalid glTF resource budget')
        self.max_vertices=max_vertices;self.max_binary_bytes=max_binary_bytes

    def document(self, mesh, audit_receipt, *, colors=None, uv=None, texture_png=None,
                 frames=None, times=None, metallic=0., roughness=.65):
        import struct
        import numpy as np
        if not isinstance(mesh,MeshData) or len(mesh.vertices)>self.max_vertices:
            raise ValueError('Validated MeshData within exporter budget required')
        if not verify_receipt(audit_receipt):raise ValueError('Valid receipt required for glTF provenance')
        if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in (metallic,roughness)):
            raise ValueError('PBR metallic/roughness must be in [0,1]')
        chunks=[];views=[];accessors=[];length=0
        def append(raw,target=None):
            nonlocal length
            padding=(-length)%4
            if padding:chunks.append(b'\x00'*padding);length+=padding
            if length+len(raw)>self.max_binary_bytes:raise ValueError('glTF binary budget exceeded')
            index=len(views);view={'buffer':0,'byteOffset':length,'byteLength':len(raw)}
            if target is not None:view['target']=target
            views.append(view);chunks.append(raw);length+=len(raw)
            return index
        def accessor(values, kind, *, integer=False, target=None, bounds=False):
            array=np.asarray(values,dtype='<u4' if integer else '<f4')
            size={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[kind]
            if array.size==0 or array.size%size or (not integer and not np.isfinite(array).all()):
                raise ValueError('Invalid glTF accessor shape/finiteness')
            reshaped=array.reshape(-1,size)
            spec={'bufferView':append(array.tobytes(order='C'),target),'componentType':5125 if integer else 5126,
                  'count':len(reshaped),'type':kind}
            if bounds:
                spec['min']=reshaped.min(axis=0).tolist();spec['max']=reshaped.max(axis=0).tolist()
            index=len(accessors);accessors.append(spec);return index
        rounded=np.asarray(mesh.vertices,dtype=np.float32).astype(float)
        mesh=MeshData(tuple(map(tuple,rounded)),mesh.triangles,mesh.scalars,mesh.label)
        normals=np.asarray(mesh.normals())
        if np.any(np.linalg.norm(normals,axis=1)<.99):raise ValueError('Mesh has undefined vertex normals from cancelling faces')
        positions=accessor(mesh.vertices,'VEC3',target=34962,bounds=True)
        attributes={'POSITION':positions,'NORMAL':accessor(normals,'VEC3',target=34962)}
        if colors is not None:
            values=np.asarray(colors,dtype=float)
            if values.shape not in ((len(mesh.vertices),3),(len(mesh.vertices),4)) or not np.isfinite(values).all() or (values<0).any() or (values>1).any():
                raise ValueError('Finite RGB/RGBA values in [0,1] required per vertex')
            attributes['COLOR_0']=accessor(values,'VEC'+str(values.shape[1]),target=34962)
        if uv is not None:
            values=np.asarray(uv,dtype=float)
            if values.shape!=(len(mesh.vertices),2) or not np.isfinite(values).all():raise ValueError('One finite UV pair per vertex required')
            attributes['TEXCOORD_0']=accessor(values,'VEC2',target=34962)
        if texture_png is not None and uv is None:raise ValueError('Textures require UV coordinates')
        primitive={'attributes':attributes,'indices':accessor(mesh.triangles,'SCALAR',integer=True,target=34963),
                   'mode':4,'material':0}
        material={'name':'Nabla scientific material','doubleSided':True,
                  'pbrMetallicRoughness':{'metallicFactor':metallic,'roughnessFactor':roughness}}
        data={'asset':{'version':'2.0','generator':'Nabla GLTFExporter'},
              'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0,'name':mesh.label}],
              'meshes':[{'name':mesh.label,'primitives':[primitive]}],
              'materials':[material],'buffers':[{}],'bufferViews':views,'accessors':accessors}
        if texture_png is not None:
            if not isinstance(texture_png,bytes) or not texture_png.startswith(b'\x89PNG\r\n\x1a\n') or len(texture_png)>16*1024*1024:
                raise ValueError('Bounded PNG texture bytes required')
            import io
            from PIL import Image
            with Image.open(io.BytesIO(texture_png)) as image:
                if image.width*image.height>16000000:raise ValueError('Texture pixel budget exceeded')
                image.verify()
            image_view=append(texture_png)
            data['images']=[{'bufferView':image_view,'mimeType':'image/png'}]
            data['samplers']=[{'magFilter':9729,'minFilter':9729,'wrapS':33071,'wrapT':33071}]
            data['textures']=[{'source':0,'sampler':0}]
            material['pbrMetallicRoughness']['baseColorTexture']={'index':0,'texCoord':0}
        if frames is not None:
            snapshots=np.asarray(frames,dtype=float)
            clock=np.asarray(times,dtype=float) if times is not None else np.arange(len(snapshots),dtype=float)
            if snapshots.ndim!=3 or snapshots.shape[1:]!=(len(mesh.vertices),3) or not 2<=len(snapshots)<=32 or snapshots.size>6000000 or not np.isfinite(snapshots).all():
                raise ValueError('Animation supports 2–32 matching finite mesh frames')
            if clock.shape!=(len(snapshots),) or not np.isfinite(clock).all() or clock[0]<0 or np.any(np.diff(clock)<=0):
                raise ValueError('Animation needs increasing nonnegative timestamps')
            targets=[]
            base=np.asarray(mesh.vertices)
            for frame in snapshots:
                frame_mesh=MeshData(tuple(map(tuple,frame)),mesh.triangles)
                frame_normals=np.asarray(frame_mesh.normals())
                targets.append({'POSITION':accessor(frame-base,'VEC3',target=34962,bounds=True),
                                'NORMAL':accessor(frame_normals-normals,'VEC3',target=34962)})
            primitive['targets']=targets
            data['meshes'][0]['weights']=[1.]+[0.]*(len(targets)-1)
            clock_accessor=accessor(clock,'SCALAR',bounds=True)
            weights=accessor(np.eye(len(targets)),'SCALAR')
            data['animations']=[{'name':'Recorded simulation','samplers':[{'input':clock_accessor,'output':weights,'interpolation':'LINEAR'}],
                                 'channels':[{'sampler':0,'target':{'node':0,'path':'weights'}}]}]
        binary=b''.join(chunks)
        data['buffers'][0]['byteLength']=len(binary)
        data['asset']['extras']={'nabla':{'receipt':audit_receipt,'receipt_id':audit_receipt['content_id'],
                                         'buffer_sha256':hashlib.sha256(binary).hexdigest(),
                                         'coordinate_system':'right-handed Y-up; units supplied by experiment',
                                         'mesh_samples_verified_against_receipt':False}}
        return data,binary

    def glb_bytes(self, mesh, audit_receipt, **options):
        import struct
        data,binary=self.document(mesh,audit_receipt,**options)
        encoded=canonical_json(data).encode();encoded+=b' '*((-len(encoded))%4)
        padded=binary+b'\x00'*((-len(binary))%4)
        size=12+8+len(encoded)+8+len(padded)
        return (struct.pack('<4sII',b'glTF',2,size)+struct.pack('<I4s',len(encoded),b'JSON')+encoded
                +struct.pack('<I4s',len(padded),b'BIN\x00')+padded)

    def gltf_json(self, mesh, audit_receipt, **options):
        data,binary=self.document(mesh,audit_receipt,**options)
        data['buffers'][0]['uri']='data:application/octet-stream;base64,'+base64.b64encode(binary).decode()
        return canonical_json(data)

    def write(self, mesh, destination, *, audit_receipt, **options):
        path=Path(destination)
        if path.suffix.lower()=='.glb':raw=self.glb_bytes(mesh,audit_receipt,**options)
        elif path.suffix.lower()=='.gltf':raw=self.gltf_json(mesh,audit_receipt,**options).encode()
        else:raise ValueError('glTF destination suffix is .glb or .gltf')
        return _publish_bytes(path,raw)


_STANDALONE_VIEWER = r'''
const input=JSON.parse(document.getElementById('nabla-data').textContent);
const canvas=document.getElementById('scene'),renderer=new THREE.WebGLRenderer({canvas,antialias:true});
renderer.setClearColor(0x101e2c);renderer.setPixelRatio(Math.min(devicePixelRatio||1,2));
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(45,1,.001,10000);
const geometry=new THREE.BufferGeometry();let frame=0,playing=false,last=0;
const maps=input.maps;
const bounds=new THREE.Box3();for(const points of input.frames)for(const p of points)bounds.expandByPoint(new THREE.Vector3(...p));
const center=bounds.getCenter(new THREE.Vector3()),extent=bounds.getSize(new THREE.Vector3()).length()||1;
function positions(points){return new Float32Array(points.flatMap(p=>[(p[0]-center.x)/extent,(p[1]-center.y)/extent,(p[2]-center.z)/extent]));}
geometry.setAttribute('position',new THREE.BufferAttribute(positions(input.frames[0]),3));
geometry.setIndex(input.triangles.flat());geometry.computeVertexNormals();
function recolor(){const name=document.getElementById('colormap').value;const colors=input.colors[name][frame];
geometry.setAttribute('color',new THREE.Float32BufferAttribute(colors.flat(),3));}
const material=new THREE.MeshStandardMaterial({vertexColors:true,roughness:.65,metalness:0,side:THREE.DoubleSide});
const mesh=new THREE.Mesh(geometry,material);scene.add(mesh);recolor();
scene.add(new THREE.HemisphereLight(0xcce5ff,0x27352a,2));const light=new THREE.DirectionalLight(0xffffff,2.5);light.position.set(2,3,4);scene.add(light);
camera.position.set(1.3,1,1.7);const controls=new THREE.OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.08;
const slider=document.getElementById('time'),clock=document.getElementById('clock');slider.max=input.frames.length-1;
function select(index){frame=Math.max(0,Math.min(input.frames.length-1,index));slider.value=frame;clock.textContent='t = '+input.times[frame];
geometry.setAttribute('position',new THREE.BufferAttribute(positions(input.frames[frame]),3));geometry.computeVertexNormals();geometry.computeBoundingSphere();recolor();}
slider.oninput=()=>select(Number(slider.value));document.getElementById('colormap').onchange=recolor;
document.getElementById('wireframe').onchange=e=>material.wireframe=e.target.checked;
document.getElementById('play').onclick=()=>{playing=!playing;document.getElementById('play').textContent=playing?'Pause':'Play';};
document.getElementById('reset').onclick=()=>{camera.position.set(1.3,1,1.7);controls.target.set(0,0,0);controls.update();};
function download(name,bytes,type){const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([bytes],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
document.getElementById('audit').onclick=()=>download('nabla-receipt.json',JSON.stringify(input.receipt,null,2),'application/json');
document.getElementById('image').onclick=()=>{renderer.render(scene,camera);canvas.toBlob(blob=>{if(blob)download('nabla-scene.png',blob,'image/png');});};
function loop(now){requestAnimationFrame(loop);const width=canvas.clientWidth,height=canvas.clientHeight;
if(canvas.width!==Math.round(width*renderer.getPixelRatio())||canvas.height!==Math.round(height*renderer.getPixelRatio())){renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();}
if(playing&&now-last>250){select((frame+1)%input.frames.length);last=now;}controls.update();renderer.render(scene,camera);}
select(0);requestAnimationFrame(loop);
'''


class Standalone3DViewer:
    """Single-file Three.js + OrbitControls viewer with time and colormap controls."""
    @staticmethod
    def _engine():
        directory=resources.files('nablamath.graphics').joinpath('vendor')
        raw=directory.joinpath('three-orbit-0.180.0.min.js').read_bytes()
        manifest=json.loads(directory.joinpath('provenance.json').read_text(encoding='utf-8'))
        import hashlib
        if hashlib.sha256(raw).hexdigest()!=manifest['sha256']:
            raise ValueError('Bundled Three.js/OrbitControls integrity check failed')
        return raw,manifest

    def source(self, mesh, audit_receipt, *, frames=None, times=None, scalars=None,
               title='Nabla scientific visualization'):
        import numpy as np
        if not isinstance(mesh,MeshData) or not verify_receipt(audit_receipt):raise ValueError('Validated mesh and receipt required')
        if not isinstance(title,str) or not 1<=len(title)<=4096:raise ValueError('Bounded visualization title required')
        if frames is None:frames=[mesh.vertices]
        snapshots=np.asarray(frames,dtype=float)
        if snapshots.ndim!=3 or snapshots.shape[1:]!=(len(mesh.vertices),3) or not 1<=len(snapshots)<=128 or snapshots.size>6000000 or not np.isfinite(snapshots).all():
            raise ValueError('Viewer supports 1–128 matching finite frames within the vertex budget')
        # Validate each snapshot's triangles instead of validating only frame zero.
        for frame in snapshots:MeshData(tuple(map(tuple,frame)),mesh.triangles)
        clock=np.arange(len(snapshots),dtype=float) if times is None else np.asarray(times,dtype=float)
        if clock.shape!=(len(snapshots),) or not np.isfinite(clock).all() or np.any(np.diff(clock)<=0):raise ValueError('Increasing finite frame times required')
        if scalars is None:
            base=np.asarray(mesh.scalars if mesh.scalars is not None else np.asarray(mesh.vertices)[:,1],dtype=float)
            values=np.broadcast_to(base,(len(snapshots),len(mesh.vertices)))
        else:
            values=np.asarray(scalars,dtype=float)
            if values.shape==(len(mesh.vertices),):values=np.broadcast_to(values,(len(snapshots),len(mesh.vertices)))
        if values.shape!=(len(snapshots),len(mesh.vertices)) or not np.isfinite(values).all():raise ValueError('Finite scalar per frame/vertex required')
        low,high=float(values.min()),float(values.max())
        colors={kind:[ColorMaps.map(row,kind,low,high) for row in values] for kind in ColorMaps.ANCHORS}
        engine,provenance=self._engine()
        data={'frames':snapshots.tolist(),'times':clock.tolist(),'triangles':[list(v) for v in mesh.triangles],
              'colors':colors,'maps':list(ColorMaps.ANCHORS),'receipt':audit_receipt,
              'representation':'Recorded mesh samples; interpolation/display does not certify the simulation'}
        encoded=canonical_json(data).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
        page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+html.escape(title)+'</title>'
        page+='<style>body{margin:0;background:#101e2c;color:#e6f0f5;font:14px system-ui}header,footer{padding:14px 20px}h1{font-size:20px}canvas{display:block;width:100%;height:72vh;touch-action:none}nav{display:flex;gap:12px;align-items:center;flex-wrap:wrap}button,select{padding:7px;border:0;border-radius:5px}input[type=range]{flex:1;min-width:150px}small{overflow-wrap:anywhere}</style>'
        page+='<header><h1>'+html.escape(title)+'</h1><nav><button id="play">Play</button><button id="reset">Reset camera</button><label>Colormap <select id="colormap"><option>viridis</option><option>plasma</option><option>magma</option></select></label><label><input id="wireframe" type="checkbox">Wireframe</label></nav></header>'
        page+='<canvas id="scene" aria-label="Interactive three-dimensional scientific mesh"></canvas><footer><nav><input id="time" type="range" min="0" value="0" step="1"><span id="clock"></span><button id="audit">Audit receipt</button><button id="image">Save PNG</button></nav>'
        page+='<p><small>Receipt SHA-256: '+audit_receipt['content_id']+'</small></p><small>Three.js '+provenance['version']+' / MIT · Frame rate depends on device and scene.</small></footer>'
        page+='<script id="nabla-data" type="application/json">'+encoded+'</script><script src="data:text/javascript;base64,'+base64.b64encode(engine).decode()+'"></script><script>'+_STANDALONE_VIEWER+'</script></html>'
        if len(page.encode())>128*1024*1024:raise ValueError('Standalone viewer byte budget exceeded')
        return page

    def write(self, mesh, destination, *, audit_receipt, **options):
        return _publish_bytes(destination,self.source(mesh,audit_receipt,**options).encode())


class ManimSceneSynthesizer:
    """Generate literal-data Manim scenes for mesh histories and autograd DAGs.

    MathTex receives only LaTeX emitted from Nabla's closed mathematical AST.
    Raw caller LaTeX is not executed. Rendering still needs Manim, FFmpeg and,
    for MathTex, a working local TeX installation. Scene transitions explain
    supplied data; they do not manufacture proof steps absent from the receipt.
    """
    def __init__(self, *, duration=5., max_faces=2000):
        if type(duration) not in (int,float) or not math.isfinite(duration) or not .2<=duration<=120:
            raise ValueError('Manim duration must be .2–120 seconds')
        if type(max_faces) is not int or not 1<=max_faces<=10000:raise ValueError('Invalid Manim polygon budget')
        self.duration=duration;self.max_faces=max_faces

    @staticmethod
    def _equations(sources, variables):
        variables=names(variables,16)
        if not isinstance(sources,(list,tuple)) or len(sources)>32:raise ValueError('At most 32 equation expressions required')
        result=[]
        for source in sources:
            value,_=expression(source,variables)
            result.append(sympy().latex(value))
        return result

    def mesh_scene(self, mesh, audit_receipt, *, frames=None, equations=(), variables=('x',),
                   errors=None):
        import numpy as np
        if not isinstance(mesh,MeshData) or not verify_receipt(audit_receipt):raise ValueError('Validated mesh/receipt required')
        if len(mesh.triangles)>self.max_faces:raise ValueError('Manim mesh exceeds polygon budget; use WebGL for large meshes')
        snapshots=np.asarray([mesh.vertices] if frames is None else frames,dtype=float)
        if snapshots.ndim!=3 or snapshots.shape[1:]!=(len(mesh.vertices),3) or not 1<=len(snapshots)<=64 or not np.isfinite(snapshots).all():
            raise ValueError('Matching finite mesh animation frames required')
        for frame in snapshots:MeshData(tuple(map(tuple,frame)),mesh.triangles)
        uncertainty=None
        if errors is not None:
            uncertainty=np.asarray(errors,dtype=float)
            if uncertainty.shape!=(len(snapshots),len(mesh.vertices)) or not np.isfinite(uncertainty).all() or (uncertainty<0).any():
                raise ValueError('One nonnegative vertical error per frame/vertex required')
        payload={'frames':snapshots.tolist(),'triangles':[list(v) for v in mesh.triangles],
                 'equations':self._equations(equations,variables),'hash':audit_receipt['content_id'],
                 'duration':self.duration,'errors':None if uncertainty is None else uncertainty.tolist()}
        literal=repr(canonical_json(payload))
        return '''# Generated mesh presentation, not a proof of the associated experiment.
import json
import numpy as np
from manim import ThreeDScene, ThreeDAxes, Polygon, VGroup, Text, MathTex, Line, Transform, FadeIn, DEGREES, DOWN, RIGHT, UP, BLUE
DATA=json.loads('''+literal+''')
class ScientificProof(ThreeDScene):
    def construct(self):
        all_points=np.asarray(DATA['frames'])
        low=all_points.min(axis=(0,1));high=all_points.max(axis=(0,1))
        span=np.maximum(high-low,.2);padding=.12*span
        axes=ThreeDAxes(x_range=[low[0]-padding[0],high[0]+padding[0],span[0]/4],
                          y_range=[low[1]-padding[1],high[1]+padding[1],span[1]/4],
                          z_range=[low[2]-padding[2],high[2]+padding[2],span[2]/4],
                          x_length=6,y_length=5,z_length=4)
        self.set_camera_orientation(phi=65*DEGREES,theta=-45*DEGREES)
        audit=Text('SHA-256: '+DATA['hash'],font_size=9).to_corner(DOWN+RIGHT)
        self.add_fixed_in_frame_mobjects(audit)
        self.add(axes)
        def surface(frame):
            return VGroup(*[Polygon(*[axes.c2p(*frame[index]) for index in face],
                          color=BLUE,fill_opacity=.65,stroke_width=.3) for face in DATA['triangles']])
        def bars(index):
            if DATA['errors'] is None:return VGroup()
            return VGroup(*[Line(axes.c2p(p[0],p[1],p[2]-e),axes.c2p(p[0],p[1],p[2]+e),stroke_width=1)
                         for p,e in zip(DATA['frames'][index],DATA['errors'][index]) if e>0])
        current=surface(DATA['frames'][0]);uncertainty=bars(0)
        self.add(current,uncertainty)
        self.begin_ambient_camera_rotation(rate=.12)
        frame_duration=DATA['duration']/max(1,len(DATA['frames'])-1)
        for index,frame in enumerate(DATA['frames'][1:],1):
            self.play(Transform(current,surface(frame)),Transform(uncertainty,bars(index)),run_time=frame_duration)
        if len(DATA['frames'])==1:self.wait(DATA['duration'])
        self.stop_ambient_camera_rotation()
        previous=None
        for source in DATA['equations']:
            formula=MathTex(source,font_size=28).to_edge(UP)
            if formula.width>12:formula.scale_to_fit_width(12)
            self.add_fixed_in_frame_mobjects(formula)
            if previous is None:self.play(FadeIn(formula),run_time=.2)
            else:self.play(Transform(previous,formula),run_time=.4)
            previous=formula if previous is None else previous
            self.wait(.2)
'''

    def autograd_scene(self, audit_receipt):
        if not verify_receipt(audit_receipt):raise ValueError('Valid calculation receipt required')
        if audit_receipt.get('request',{}).get('operation')!='autograd':
            raise ValueError('Autograd scene requires an autograd catalog receipt')
        arguments=audit_receipt['request']['arguments'];nodes=arguments['nodes']
        if len(nodes)>64:raise ValueError('Manim graph layout supports at most 64 nodes')
        # Replay the closed DAG to reject a hash-consistent but mathematically
        # fabricated calculation before presenting its derivative labels.
        from ..ops.autograd import differentiate_graph
        replay=differentiate_graph(**arguments)
        if replay!=audit_receipt['result']:raise ValueError('Autograd receipt result differs from independent replay')
        levels=[]
        for index,node in enumerate(nodes):
            parents=node.get('args',[])
            if any(type(p) is not int or not 0<=p<index for p in parents):raise ValueError('DAG references must precede the node')
            levels.append(0 if not parents else 1+max(levels[p] for p in parents))
        layers={level:[i for i,v in enumerate(levels) if v==level] for level in sorted(set(levels))}
        positions={}
        for level,indices in layers.items():
            for row,index in enumerate(indices):
                positions[str(index)]=[-5+10*level/max(1,max(levels)),2-4*row/max(1,len(indices)-1),0]
        payload={'nodes':nodes,'positions':positions,'result':replay,'output':arguments['output'],
                 'hash':audit_receipt['content_id'],'duration':self.duration}
        return '''import json
from manim import Scene, Dot, Text, Arrow, VGroup, FadeIn, Create, BLUE, ORANGE, DOWN, RIGHT, UP
DATA=json.loads('''+repr(canonical_json(payload))+''')
class ScientificAutograd(Scene):
    def construct(self):
        audit=Text('SHA-256: '+DATA['hash'],font_size=9).to_corner(DOWN+RIGHT)
        self.add(audit)
        dots={}
        for index,node in enumerate(DATA['nodes']):
            point=DATA['positions'][str(index)]
            label=str(index)+': '+str(node.get('name',node.get('value',node['op'])))
            dot=Dot(point,color=ORANGE if index==DATA['output'] else BLUE)
            text=Text(label,font_size=14).next_to(dot,UP,buff=.08)
            for parent in node.get('args',[]):
                self.play(Create(Arrow(DATA['positions'][str(parent)],point,buff=.13,stroke_width=1)),run_time=.05)
            self.play(FadeIn(VGroup(dot,text)),run_time=DATA['duration']/len(DATA['nodes']))
            dots[index]=dot
        summary=Text('output = '+str(DATA['result']['value'])+'; gradient = '+str(DATA['result']['gradient']),font_size=18).to_edge(DOWN)
        if summary.width>12:summary.scale_to_fit_width(12)
        self.play(FadeIn(summary),run_time=.2)
        self.wait(.3)
'''

    def write(self, source, destination):
        import ast
        if not isinstance(source,str) or len(source)>8*1024*1024:raise ValueError('Bounded generated Manim source required')
        ast.parse(source)
        return _publish_bytes(destination,source.encode())

    def render(self, source, destination, *, scene='ScientificProof', timeout=120,
               quality='low'):
        import sys
        import shutil
        import tempfile
        if scene not in ('ScientificProof','ScientificAutograd'):raise ValueError('Unknown generated scene class')
        if quality not in ('low','medium','high'):raise ValueError('Video quality is low, medium or high')
        if type(timeout) not in (int,float) or not 1<=timeout<=600:raise ValueError('Render timeout must be 1–600 seconds')
        from ..artifacts.process import run_renderer
        quality_flag={'low':'-ql','medium':'-qm','high':'-qh'}[quality]
        with tempfile.TemporaryDirectory(prefix='nabla-scene-') as directory:
            stage=Path(directory);script=self.write(source,stage/'scene.py')
            run_renderer([sys.executable,'-m','manim',quality_flag,'--disable_caching','--media_dir',str(stage/'media'),str(script),scene],cwd=stage,timeout=timeout)
            outputs=list((stage/'media').rglob(scene+'.mp4'))
            if len(outputs)!=1 or outputs[0].stat().st_size<32:raise RuntimeError('Manim did not produce exactly one complete MP4')
            raw=outputs[0].read_bytes()
            if raw[4:8]!=b'ftyp':raise ValueError('Manim output is not an ISO media file')
            return _publish_bytes(destination,raw)


def graphics_export_gltf(vertices, triangles, audit_receipt, colors=None, binary=True):
    """Catalog-safe in-memory export; callers choose the destination separately."""
    mesh=MeshData(tuple(map(tuple,vertices)),tuple(map(tuple,triangles)))
    exporter=GLTFExporter()
    if type(binary) is not bool:raise ValueError('binary must be boolean')
    if binary:
        raw=exporter.glb_bytes(mesh,audit_receipt,colors=colors)
        return {'format':'glb','base64':base64.b64encode(raw).decode(),'bytes':len(raw)}
    source=exporter.gltf_json(mesh,audit_receipt,colors=colors)
    return {'format':'gltf','json':json.loads(source)}


def graphics_export_html3d(vertices, triangles, audit_receipt, scalars=None,
                           frames=None, times=None, title='Nabla scientific visualization'):
    mesh=MeshData(tuple(map(tuple,vertices)),tuple(map(tuple,triangles)),
                  None if scalars is None else tuple(scalars))
    source=Standalone3DViewer().source(mesh,audit_receipt,frames=frames,times=times,title=title)
    return {'format':'html','source':source,'offline':True,
            'scope':'Data and renderer embedded; browser/hardware determine rendering performance'}


def graphics_compile_manim(vertices, triangles, audit_receipt, frames=None,
                            equations=(), variables=('x',), duration=5.):
    mesh=MeshData(tuple(map(tuple,vertices)),tuple(map(tuple,triangles)))
    source=ManimSceneSynthesizer(duration=duration).mesh_scene(mesh,audit_receipt,frames=frames,equations=equations,variables=variables)
    return {'format':'python','scene':'ScientificProof','source':source,
            'rendering_required':'Manim and optional TeX dependencies are external'}


__all__=['SpatialEngine3D','MeshData','ColorMaps','SurfaceFactory','VectorFieldVisualizer',
         'GLTFExporter','Standalone3DViewer','ManimSceneSynthesizer',
         'graphics_export_gltf','graphics_export_html3d','graphics_compile_manim']


def parametric_surface(components, parameters, bounds, shape=(51,51), periodic=(False,False)):
    return SurfaceFactory.parametric(components,parameters,bounds,shape,periodic=periodic).to_data()


__all__ += ['parametric_surface']


@dataclass(frozen=True)
class RaycastHit:
    triangle: int
    point: tuple
    barycentric: tuple
    distance: float
    normal: tuple

    def to_data(self):
        return {'triangle':self.triangle,'point':list(self.point),'barycentric':list(self.barycentric),
                'distance':self.distance,'normal':list(self.normal)}


class MeshBVH:
    """Axis-aligned bounding hierarchy with vectorized triangle ray intersection.

    Intersection is geometric floating-point picking, not an exact predicate
    suitable for proving incidence theorems. Shared-edge hits are resolved by
    nearest distance then triangle index for reproducible visualization.
    """
    def __init__(self, mesh, *, leaf_size=16):
        import numpy as np
        if not isinstance(mesh,MeshData) or len(mesh.triangles)>200000:raise ValueError('Validated mesh within BVH budget required')
        if type(leaf_size) is not int or not 2<=leaf_size<=128:raise ValueError('BVH leaf size must be 2–128')
        self.mesh=mesh;self.points=np.asarray(mesh.vertices);self.faces=np.asarray(mesh.triangles)
        self.corners=self.points[self.faces];self.centroids=self.corners.mean(axis=1);self.nodes=[]
        def build(indices):
            node_index=len(self.nodes);corners=self.corners[indices]
            lower=corners.min(axis=(0,1));upper=corners.max(axis=(0,1))
            node={'minimum':lower,'maximum':upper,'triangles':None,'children':None}
            self.nodes.append(node)
            if len(indices)<=leaf_size:node['triangles']=indices;return node_index
            spread=np.ptp(self.centroids[indices],axis=0);axis=int(np.argmax(spread))
            order=np.argsort(self.centroids[indices,axis],kind='stable');middle=len(indices)//2
            node['children']=(build(indices[order[:middle]]),build(indices[order[middle:]]))
            return node_index
        build(np.arange(len(self.faces)))

    @staticmethod
    def _box(origin, direction, lower, upper, maximum):
        near=0.;far=maximum
        for axis in range(3):
            if abs(direction[axis])<1e-15:
                if origin[axis]<lower[axis] or origin[axis]>upper[axis]:return None
                continue
            first=(lower[axis]-origin[axis])/direction[axis];second=(upper[axis]-origin[axis])/direction[axis]
            near=max(near,min(first,second));far=min(far,max(first,second))
            if near>far:return None
        return near

    def intersect(self, origin, direction, *, maximum_distance=1e30,
                  cull_backfaces=False, tolerance=1e-10):
        import heapq
        import numpy as np
        start=np.asarray(origin,dtype=float);vector=np.asarray(direction,dtype=float)
        if start.shape!=(3,) or vector.shape!=(3,) or not np.isfinite(start).all() or not np.isfinite(vector).all():
            raise ValueError('Finite ray origin/direction triples required')
        norm=float(np.linalg.norm(vector))
        if norm==0 or not math.isfinite(maximum_distance) or maximum_distance<=0 or not 0<tolerance<.01 or type(cull_backfaces) is not bool:
            raise ValueError('Invalid ray length, tolerance or culling policy')
        vector=vector/norm;best=maximum_distance;hit=None
        first=self._box(start,vector,self.nodes[0]['minimum'],self.nodes[0]['maximum'],best)
        if first is None:return None
        pending=[(first,0)]
        while pending:
            distance,node_index=heapq.heappop(pending)
            if distance>best:continue
            node=self.nodes[node_index]
            if node['children'] is not None:
                for child in node['children']:
                    item=self.nodes[child];entry=self._box(start,vector,item['minimum'],item['maximum'],best)
                    if entry is not None:heapq.heappush(pending,(entry,child))
                continue
            indices=node['triangles'];corners=self.corners[indices]
            edge1=corners[:,1]-corners[:,0];edge2=corners[:,2]-corners[:,0]
            p=np.cross(np.broadcast_to(vector,edge2.shape),edge2);det=np.einsum('ij,ij->i',edge1,p)
            mask=det>tolerance if cull_backfaces else abs(det)>tolerance
            inverse=np.zeros_like(det);inverse[mask]=1/det[mask]
            offset=start-corners[:,0];u=np.einsum('ij,ij->i',offset,p)*inverse
            q=np.cross(offset,edge1);v=(q@vector)*inverse;t=np.einsum('ij,ij->i',edge2,q)*inverse
            valid=np.flatnonzero(mask&(u>=-tolerance)&(v>=-tolerance)&(u+v<=1+tolerance)&(t>=0)&(t<=best))
            for local in valid:
                triangle=int(indices[local]);current=float(t[local])
                if hit is not None and current==best and triangle>=hit.triangle:continue
                normal=np.cross(edge1[local],edge2[local]);normal/=np.linalg.norm(normal)
                best=current;hit=RaycastHit(triangle,tuple(start+current*vector),
                    (float(1-u[local]-v[local]),float(u[local]),float(v[local])),current,tuple(normal))
        return hit

    def interpolate_scalar(self, hit, values=None):
        if not isinstance(hit,RaycastHit) or not 0<=hit.triangle<len(self.faces):raise ValueError('RaycastHit on this mesh required')
        scalar=self.mesh.scalars if values is None else values
        if scalar is None or len(scalar)!=len(self.points):raise ValueError('Per-vertex scalar values required')
        if any(not math.isfinite(float(v)) for v in scalar):raise ValueError('Finite interpolation scalars required')
        return sum(float(scalar[index])*weight for index,weight in zip(self.faces[hit.triangle],hit.barycentric))


class MeshProcessor:
    """Subdivision, smoothing and mesh quality operations with explicit diagnostics."""
    @staticmethod
    def boundary_loops(mesh):
        if not isinstance(mesh,MeshData):raise ValueError('Validated mesh required')
        topology=mesh.topology()
        if topology['nonmanifold_edges']:raise ValueError('Boundary loops require edge-manifold topology')
        adjacency={}
        for a,b in topology['boundary_edges']:
            adjacency.setdefault(a,[]).append(b);adjacency.setdefault(b,[]).append(a)
        if any(len(neighbors)!=2 for neighbors in adjacency.values()):raise ValueError('Boundary branches or pinched vertices prevent a loop decomposition')
        unused={tuple(sorted(edge)) for edge in topology['boundary_edges']};loops=[]
        while unused:
            first=min(unused);start,following=first;loop=[start];previous=start;current=following
            unused.remove(first)
            while current!=start:
                loop.append(current);candidates=[v for v in adjacency[current] if v!=previous]
                if len(candidates)!=1:raise ArithmeticError('Boundary traversal became ambiguous')
                following=candidates[0];edge=tuple(sorted((current,following)))
                if edge not in unused:raise ArithmeticError('Boundary traversal reused an edge before closing')
                unused.remove(edge);previous,current=current,following
            loops.append(loop)
        return {'loops':loops,'boundary_vertices':len(adjacency)}

    @staticmethod
    def quality(mesh):
        import numpy as np
        if not isinstance(mesh,MeshData):raise ValueError('Validated mesh required')
        points=np.asarray(mesh.vertices);faces=np.asarray(mesh.triangles);corners=points[faces]
        lengths=np.stack([np.linalg.norm(corners[:,i]-corners[:,j],axis=1) for i,j in ((0,1),(1,2),(2,0))],axis=1)
        double_area=np.linalg.norm(np.cross(corners[:,1]-corners[:,0],corners[:,2]-corners[:,0]),axis=1)
        perimeter=lengths.sum(axis=1);inradius=double_area/perimeter
        circumradius=np.prod(lengths,axis=1)/(2*double_area)
        aspect=circumradius/(2*inradius)
        cosines=[]
        for i in range(3):
            a=lengths[:,i];b=lengths[:,(i+1)%3];opposite=lengths[:,(i+2)%3]
            cosines.append(np.clip((a*a+b*b-opposite*opposite)/(2*a*b),-1,1))
        angles=np.arccos(np.stack(cosines,axis=1))*180/math.pi
        return {'minimum_angle_degrees':float(angles.min()),'maximum_angle_degrees':float(angles.max()),
                'maximum_radius_ratio':float(aspect.max()),'mean_radius_ratio':float(aspect.mean()),
                'equilateral_radius_ratio':1.,'surface_area':mesh.surface_area(),
                'topology':mesh.topology(),'scope':'Geometric shape diagnostics; no mesh-convergence certificate'}

    @staticmethod
    def loop_subdivide(mesh, iterations=1):
        import numpy as np
        if not isinstance(mesh,MeshData) or type(iterations) is not int or not 0<=iterations<=5:
            raise ValueError('Validated mesh and 0–5 subdivision steps required')
        if len(mesh.triangles)*4**iterations>200000:raise ValueError('Loop subdivision face budget exceeded')
        current=mesh
        for _ in range(iterations):
            points=np.asarray(current.vertices);neighbors=[set() for _ in points];opposites={};boundary_neighbors=[set() for _ in points]
            for face in current.triangles:
                for a,b,c in ((face[0],face[1],face[2]),(face[1],face[2],face[0]),(face[2],face[0],face[1])):
                    neighbors[a].add(b);neighbors[b].add(a);opposites.setdefault(tuple(sorted((a,b))),[]).append(c)
            if any(len(v)>2 for v in opposites.values()):raise ValueError('Loop subdivision needs an edge-manifold surface')
            for (a,b),opposite in opposites.items():
                if len(opposite)==1:boundary_neighbors[a].add(b);boundary_neighbors[b].add(a)
            if any(boundary and len(boundary)!=2 for boundary in boundary_neighbors):raise ValueError('Loop subdivision refuses pinched or branching boundaries')
            weights=[]
            for index,adjacent in enumerate(neighbors):
                boundary=boundary_neighbors[index]
                if boundary:row={index:.75,**{j:.125 for j in boundary}}
                else:
                    count=len(adjacent)
                    if count<3:raise ValueError('Interior Loop vertex needs at least three neighbors')
                    beta=(5/8-(3/8+math.cos(2*math.pi/count)/4)**2)/count
                    row={index:1-count*beta,**{j:beta for j in adjacent}}
                weights.append(row)
            edge_positions={}
            for edge,opposite in sorted(opposites.items()):
                a,b=edge;edge_positions[edge]=len(weights)
                if len(opposite)==1:weights.append({a:.5,b:.5})
                else:
                    row={a:3/8,b:3/8}
                    for index in opposite:row[index]=row.get(index,0)+1/8
                    weights.append(row)
            vertices=[tuple(sum(weight*points[index] for index,weight in row.items())) for row in weights]
            faces=[]
            for a,b,c in current.triangles:
                ab=edge_positions[tuple(sorted((a,b)))];bc=edge_positions[tuple(sorted((b,c)))];ca=edge_positions[tuple(sorted((c,a)))]
                faces.extend(((a,ab,ca),(b,bc,ab),(c,ca,bc),(ab,bc,ca)))
            scalars=None if current.scalars is None else tuple(sum(weight*current.scalars[index] for index,weight in row.items()) for row in weights)
            current=MeshData(tuple(vertices),tuple(faces),scalars,label=current.label+' / Loop')
        return current

    @staticmethod
    def taubin_smooth(mesh, iterations=10, *, forward=.5, reverse=-.53, fixed_boundary=True):
        import numpy as np
        from scipy.sparse import coo_matrix,diags
        if not isinstance(mesh,MeshData) or type(iterations) is not int or not 0<=iterations<=1000:
            raise ValueError('Validated mesh and bounded smoothing iterations required')
        if not 0<forward<1 or not -1<reverse<0 or type(fixed_boundary) is not bool:
            raise ValueError('Taubin smoothing requires forward in (0,1), reverse in (-1,0)')
        adjacency=[set() for _ in mesh.vertices]
        for a,b,c in mesh.triangles:
            adjacency[a].update((b,c));adjacency[b].update((a,c));adjacency[c].update((a,b))
        if any(not row for row in adjacency):raise ValueError('Smoothing refuses isolated vertices')
        rows=[];columns=[];values=[]
        for i,row in enumerate(adjacency):
            for j in row:rows.append(i);columns.append(j);values.append(1/len(row))
        operator=coo_matrix((values,(rows,columns)),shape=(len(adjacency),)*2).tocsr()-diags(np.ones(len(adjacency)))
        fixed={v for edge in mesh.topology()['boundary_edges'] for v in edge} if fixed_boundary else set()
        points=np.asarray(mesh.vertices)
        for _ in range(iterations):
            for rate in (forward,reverse):
                displacement=rate*(operator@points)
                if fixed:displacement[list(fixed)]=0
                points=points+displacement
                if not np.isfinite(points).all():raise ArithmeticError('Smoothing became nonfinite')
        result=MeshData(tuple(map(tuple,points)),mesh.triangles,mesh.scalars,mesh.label+' / Taubin')
        return {'mesh':result,'initial_area':mesh.surface_area(),'final_area':result.surface_area(),
                'scope':'Geometric smoothing; volume, field equations and topology embeddings are not certified'}

    @staticmethod
    def connected_components(mesh):
        if not isinstance(mesh,MeshData):raise ValueError('Validated mesh required')
        parent=list(range(len(mesh.vertices)))
        def find(index):
            while parent[index]!=index:
                parent[index]=parent[parent[index]];index=parent[index]
            return index
        for a,b,c in mesh.triangles:
            for left,right in ((a,b),(b,c)):
                first,second=find(left),find(right)
                if first!=second:parent[max(first,second)]=min(first,second)
        groups={}
        for index in range(len(parent)):groups.setdefault(find(index),[]).append(index)
        return {'components':list(groups.values()),'count':len(groups)}


class ScalarContours:
    """Piecewise-linear level sets on triangular meshes with degeneracies explicit."""
    @staticmethod
    def extract(mesh, levels, *, scalars=None):
        import numpy as np
        if not isinstance(mesh,MeshData):raise ValueError('Validated mesh required')
        values=mesh.scalars if scalars is None else scalars
        if values is None or len(values)!=len(mesh.vertices) or any(not math.isfinite(float(v)) for v in values):
            raise ValueError('A finite scalar per mesh vertex required')
        if not isinstance(levels,(list,tuple)) or not 1<=len(levels)<=64 or any(not math.isfinite(float(v)) for v in levels):
            raise ValueError('1–64 finite contour levels required')
        points=np.asarray(mesh.vertices);values=np.asarray(values,dtype=float);result=[]
        for level in levels:
            vertices=[];segments=set();cache={};coincident=[]
            def vertex(key,point):
                if key not in cache:cache[key]=len(vertices);vertices.append(point.tolist())
                return cache[key]
            for index,face in enumerate(mesh.triangles):
                residual=values[list(face)]-level
                if np.all(residual==0):coincident.append(index);continue
                intersections=[]
                for slot,next_slot in ((0,1),(1,2),(2,0)):
                    a,b=face[slot],face[next_slot];u,v=residual[slot],residual[next_slot]
                    if u==0:intersections.append(vertex(('vertex',a),points[a]))
                    if v==0:intersections.append(vertex(('vertex',b),points[b]))
                    if u*v<0:
                        fraction=u/(u-v);key=('edge',*sorted((a,b)))
                        intersections.append(vertex(key,points[a]+fraction*(points[b]-points[a])))
                intersections=list(dict.fromkeys(intersections))
                if len(intersections)==2:segments.add(tuple(sorted(intersections)))
                elif len(intersections)>2:raise ArithmeticError('Non-coincident linear triangle produced more than one contour segment')
            adjacency={}
            for a,b in segments:adjacency.setdefault(a,[]).append(b);adjacency.setdefault(b,[]).append(a)
            branches=[i for i,neighbors in adjacency.items() if len(neighbors)>2]
            result.append({'level':float(level),'vertices':vertices,'segments':[list(v) for v in sorted(segments)],
                           'branch_vertices':branches,'coincident_faces':coincident,
                           'scope':'Piecewise-linear level set; coincident faces are regions, not arbitrary selected curves'})
        return result


class VolumeField:
    """Structured scalar volume with bounded trilinear sampling and image slices."""
    def __init__(self, values, *, origin=(0.,0.,0.), spacing=(1.,1.,1.)):
        import numpy as np
        self.values=np.asarray(values,dtype=float);self.origin=np.asarray(origin,dtype=float);self.spacing=np.asarray(spacing,dtype=float)
        if self.values.ndim!=3 or any(not 2<=n<=256 for n in self.values.shape) or self.values.size>4000000 or not np.isfinite(self.values).all():
            raise ValueError('Finite bounded 3D volume required')
        if self.origin.shape!=(3,) or self.spacing.shape!=(3,) or not np.isfinite(self.origin).all() or not np.isfinite(self.spacing).all() or np.any(self.spacing<=0):
            raise ValueError('Finite origin and positive volume spacing required')

    def sample(self, points, *, outside='reject'):
        import numpy as np
        locations=_finite_points(points,1,100000)
        if outside not in ('reject','clamp'):raise ValueError('Outside policy is reject or clamp')
        coordinate=(locations-self.origin)/self.spacing;maximum=np.asarray(self.values.shape)-1
        if outside=='reject' and (np.any(coordinate<0) or np.any(coordinate>maximum)):
            raise ValueError('Volume sample is outside the declared grid')
        coordinate=np.clip(coordinate,0,maximum);lower=np.floor(coordinate).astype(int);lower=np.minimum(lower,maximum-1)
        fraction=coordinate-lower;result=np.zeros(len(locations))
        for i in (0,1):
            for j in (0,1):
                for k in (0,1):
                    weight=np.prod(np.where(np.asarray((i,j,k)),fraction,1-fraction),axis=1)
                    result+=weight*self.values[lower[:,0]+i,lower[:,1]+j,lower[:,2]+k]
        return result.tolist()

    def slice_png(self, axis, index, *, colormap='viridis', lower=None, upper=None):
        import numpy as np
        import io
        from PIL import Image
        if type(axis) is not int or not 0<=axis<3 or type(index) is not int or not 0<=index<self.values.shape[axis]:
            raise ValueError('Volume slice axis/index outside grid')
        plane=np.take(self.values,index,axis=axis)
        colors=ColorMaps.map(plane.ravel(),colormap,lower,upper)
        image=np.rint(np.asarray(colors).reshape(*plane.shape,3)*255).astype('uint8')
        stream=io.BytesIO();Image.fromarray(image).save(stream,format='PNG')
        return stream.getvalue()

    def isosurface(self, level):
        return SurfaceFactory.implicit(self.values,level,origin=self.origin,spacing=self.spacing)

    def integral(self):
        import numpy as np
        integrate=(np.trapezoid if hasattr(np, 'trapezoid') else np.trapz);value=self.values
        for axis in reversed(range(3)):value=integrate(value,dx=self.spacing[axis],axis=axis)
        return {'integral':float(value),'quadrature':'Tensor-product trapezoidal rule',
                'scope':'Finite-grid integral estimate; no tail or discretization-error certificate'}

    def gradient(self):
        import numpy as np
        derivatives=np.gradient(self.values,*self.spacing,edge_order=1)
        return {'components':[value.tolist() for value in derivatives],
                'scope':'Centered finite differences in the interior, first-order at the grid boundary'}


class QuantumFieldVisualizer:
    """Hydrogenic orbitals and finite-grid probability diagnostics for 3D scenes."""
    @staticmethod
    def hydrogen_orbital(points, principal, angular, magnetic, *, bohr_radius=1.):
        import numpy as np
        from scipy.special import eval_genlaguerre,gammaln
        from scipy import special
        xyz=_finite_points(points,1,1000000)
        if any(type(v) is not int for v in (principal,angular,magnetic)) or not 1<=principal<=20 or not 0<=angular<principal or abs(magnetic)>angular:
            raise ValueError('Hydrogen quantum numbers require n>=1, 0<=l<n, |m|<=l, n<=20')
        if type(bohr_radius) not in (int,float) or not math.isfinite(bohr_radius) or bohr_radius<=0:
            raise ValueError('Positive Bohr radius required')
        radius=np.linalg.norm(xyz,axis=1);rho=2*radius/(principal*bohr_radius)
        cosine=np.divide(xyz[:,2],radius,out=np.ones_like(radius),where=radius>0)
        polar=np.arccos(np.clip(cosine,-1,1));azimuth=np.arctan2(xyz[:,1],xyz[:,0])
        log_normal=.5*(3*math.log(2/(principal*bohr_radius))+gammaln(principal-angular)-math.log(2*principal)-gammaln(principal+angular+1))
        radial=math.exp(log_normal)*np.exp(-rho/2)*rho**angular*eval_genlaguerre(principal-angular-1,2*angular+1,rho)
        if hasattr(special,'sph_harm_y'):harmonic=special.sph_harm_y(angular,magnetic,polar,azimuth)
        else:harmonic=special.sph_harm(magnetic,angular,azimuth,polar)
        wave=radial*harmonic
        if not np.isfinite(wave).all():raise ArithmeticError('Hydrogen orbital evaluation became nonfinite')
        return {'real':wave.real.tolist(),'imaginary':wave.imag.tolist(),'density':(abs(wave)**2).tolist(),
                'phase':np.angle(wave).tolist(),'quantum_numbers':[principal,angular,magnetic],
                'scope':'Nonrelativistic one-electron Coulomb model; supplied Bohr length scale'}

    @staticmethod
    def probability_current(real, imaginary, gradient_real, gradient_imaginary, *, hbar=1., mass=1.):
        import numpy as np
        re=np.asarray(real,dtype=float);im=np.asarray(imaginary,dtype=float)
        gre=np.asarray(gradient_real,dtype=float);gim=np.asarray(gradient_imaginary,dtype=float)
        if re.ndim!=1 or im.shape!=re.shape or gre.shape!=(len(re),3) or gim.shape!=gre.shape or len(re)>1000000:
            raise ValueError('Matching wavefunction and XYZ gradient samples required')
        if not all(np.isfinite(v).all() for v in (re,im,gre,gim)) or not math.isfinite(hbar) or not math.isfinite(mass) or hbar<=0 or mass<=0:
            raise ValueError('Finite wave data and positive hbar/mass required')
        current=(hbar/mass)*(re[:,None]*gim-im[:,None]*gre)
        return {'vectors':current.tolist(),'density':(re*re+im*im).tolist(),
                'convention':'j=(hbar/m) Im(conjugate(psi) grad psi); no electromagnetic vector potential'}


__all__ += ['RaycastHit','MeshBVH','MeshProcessor','ScalarContours','VolumeField',
            'QuantumFieldVisualizer']


class SceneTimeline:
    """Mesh snapshots with per-frame receipt lineage and deterministic interpolation."""
    def __init__(self, mesh, frames, times, receipts):
        import numpy as np
        if not isinstance(mesh,MeshData):raise ValueError('Validated base mesh required')
        self.mesh=mesh;self.frames=np.asarray(frames,dtype=float);self.times=np.asarray(times,dtype=float)
        if self.frames.ndim!=3 or self.frames.shape[1:]!=(len(mesh.vertices),3) or not 2<=len(self.frames)<=128 or self.frames.size>6000000 or not np.isfinite(self.frames).all():
            raise ValueError('2–128 finite matching mesh frames within the memory budget required')
        if self.times.shape!=(len(self.frames),) or not np.isfinite(self.times).all() or np.any(np.diff(self.times)<=0):
            raise ValueError('One strictly increasing timestamp per frame required')
        if not isinstance(receipts,(list,tuple)) or len(receipts)!=len(self.frames) or not all(verify_receipt(r) for r in receipts):
            raise ValueError('One verified receipt per frame required')
        self.receipts=tuple(json.loads(canonical_json(r)) for r in receipts)
        for frame in self.frames:MeshData(tuple(map(tuple,frame)),mesh.triangles)

    def sample(self, time, *, clamp=False):
        import numpy as np
        if type(time) not in (int,float) or not math.isfinite(time) or type(clamp) is not bool:raise ValueError('Finite sample time and boolean clamp policy required')
        if not clamp and not self.times[0]<=time<=self.times[-1]:raise ValueError('Timeline time is outside the recorded interval')
        time=float(np.clip(time,self.times[0],self.times[-1]));right=int(np.searchsorted(self.times,time,side='right'))
        right=max(1,min(right,len(self.times)-1));left=right-1
        weight=(time-self.times[left])/(self.times[right]-self.times[left])
        points=(1-weight)*self.frames[left]+weight*self.frames[right]
        mesh=MeshData(tuple(map(tuple,points)),self.mesh.triangles,self.mesh.scalars,self.mesh.label)
        return {'mesh':mesh,'time':time,'left_frame':left,'right_frame':right,'weight':float(weight),
                'source_receipts':[self.receipts[left]['content_id'],self.receipts[right]['content_id']],
                'scope':'Linear geometry interpolation; not an additional simulated or proved state'}

    def velocity(self, time):
        result=self.sample(time)
        left,right=result['left_frame'],result['right_frame']
        value=(self.frames[right]-self.frames[left])/(self.times[right]-self.times[left])
        return {'vectors':value.tolist(),'left_frame':left,'right_frame':right,
                'scope':'Piecewise-constant velocity of the displayed linear interpolation'}

    def observation_receipt(self):
        from ..calc.receipt import receipt
        from ..core.semantic_ir import fingerprint
        return receipt('graphics.recorded_mesh_sequence',
            {'times':self.times.tolist(),'parent_receipts':[r['content_id'] for r in self.receipts]},
            {'mesh_sha256':fingerprint(self.mesh.to_data()),'frames_sha256':fingerprint(self.frames.tolist())},
            backend='nabla.scene_timeline',parents=[r['content_id'] for r in self.receipts],
            metadata={'coupling_to_parent_math_verified':False,'interpolation':'linear'})

    def viewer(self, destination, **options):
        return Standalone3DViewer().write(self.mesh,destination,audit_receipt=self.observation_receipt(),
            frames=self.frames.tolist(),times=self.times.tolist(),**options)

    def export(self, destination, **options):
        return GLTFExporter().write(self.mesh,destination,audit_receipt=self.observation_receipt(),
            frames=self.frames.tolist(),times=self.times.tolist(),**options)

    def interpolation_quality(self, *, area_tolerance=1e-12):
        """Find quartic-area minima along every linear triangle motion segment."""
        import numpy as np
        if type(area_tolerance) not in (int,float) or not 0<area_tolerance<1:raise ValueError('Positive interpolation area tolerance required')
        if len(self.mesh.triangles)*(len(self.frames)-1)>20000:raise ValueError('Continuous interpolation diagnostic budget exceeded')
        faces=np.asarray(self.mesh.triangles);minimum=math.inf;where=None;warnings=[]
        for interval in range(len(self.frames)-1):
            start=self.frames[interval][faces];delta=self.frames[interval+1][faces]-start
            u=start[:,1]-start[:,0];v=start[:,2]-start[:,0]
            du=delta[:,1]-delta[:,0];dv=delta[:,2]-delta[:,0]
            first=np.cross(u,v);second=np.cross(du,v)+np.cross(u,dv);third=np.cross(du,dv)
            for index,(a,b,c) in enumerate(zip(first,second,third)):
                coefficients=np.asarray([a@a,2*a@b,b@b+2*a@c,2*b@c,c@c])
                derivative=coefficients[1:]*np.arange(1,5)
                roots=np.polynomial.polynomial.polyroots(derivative) if np.any(derivative) else []
                candidates=[0.,1.]+[float(r.real) for r in roots if abs(r.imag)<1e-9 and 0<r.real<1]
                for parameter in candidates:
                    cross=a+parameter*b+parameter**2*c;area=float(np.linalg.norm(cross)/2)
                    if area<minimum:minimum=area;where={'interval':interval,'triangle':index,'fraction':parameter}
                    if area<area_tolerance:warnings.append({'interval':interval,'triangle':index,'fraction':parameter,'area':area})
        return {'minimum_area_estimate':minimum,'at':where,'near_degenerate_candidates':warnings,
                'scope':'Floating-point polynomial stationary-point diagnostic, not exact real-root isolation'}


class CameraPath:
    """Smooth camera positions and quaternion-SLERP orientations at keyframes."""
    def __init__(self, times, positions, targets, *, up=(0.,1.,0.)):
        import numpy as np
        from scipy.spatial.transform import Rotation,Slerp
        from scipy.interpolate import PchipInterpolator
        self.times=np.asarray(times,dtype=float);self.positions=_finite_points(positions,2,10000);target=_finite_points(targets,2,10000)
        if self.times.shape!=(len(self.positions),) or target.shape!=self.positions.shape or not np.isfinite(self.times).all() or np.any(np.diff(self.times)<=0):
            raise ValueError('Matching camera keyframes and increasing times required')
        vertical=np.asarray(up,dtype=float)
        if vertical.shape!=(3,) or not np.isfinite(vertical).all() or np.linalg.norm(vertical)==0:raise ValueError('Finite nonzero camera up vector required')
        vertical/=np.linalg.norm(vertical);matrices=[]
        for point,look in zip(self.positions,target):
            forward=look-point;length=np.linalg.norm(forward)
            if length<1e-12:raise ValueError('Camera position and target coincide')
            forward/=length;right=np.cross(forward,vertical)
            if np.linalg.norm(right)<1e-10:raise ValueError('Camera forward is parallel to its up direction')
            right/=np.linalg.norm(right);corrected=np.cross(right,forward)
            matrices.append(np.column_stack((right,corrected,-forward)))
        self._rotation=Slerp(self.times,Rotation.from_matrix(np.asarray(matrices)))
        self._position=PchipInterpolator(self.times,self.positions,axis=0)

    def sample(self, times):
        import numpy as np
        clock=np.asarray(times,dtype=float)
        if clock.ndim!=1 or not 1<=len(clock)<=100000 or not np.isfinite(clock).all() or np.any(clock<self.times[0]) or np.any(clock>self.times[-1]):
            raise ValueError('Camera sample times outside keyframe range')
        positions=self._position(clock);rotations=self._rotation(clock)
        forward=rotations.apply(np.tile([0.,0.,-1.],(len(clock),1)))
        return {'times':clock.tolist(),'positions':positions.tolist(),'quaternions_xyzw':rotations.as_quat().tolist(),
                'forward':forward.tolist(),'scope':'PCHIP position and shortest-arc orientation interpolation; no obstacle avoidance'}

    @classmethod
    def orbit(cls, center=(0.,0.,0.), radius=3., elevation=.5, *, duration=5.,
              turns=1., samples=33):
        import numpy as np
        center=np.asarray(center,dtype=float)
        if center.shape!=(3,) or not np.isfinite(center).all() or not math.isfinite(radius) or radius<=0 or not -1.55<elevation<1.55:
            raise ValueError('Finite orbit center, positive radius and non-polar elevation required')
        if type(samples) is not int or not 2<=samples<=10000 or not 0<duration<=10000 or not math.isfinite(turns):raise ValueError('Invalid camera orbit duration/samples')
        angles=np.linspace(0,turns*2*math.pi,samples)
        positions=center+radius*np.column_stack((math.cos(elevation)*np.sin(angles),np.full(samples,math.sin(elevation)),math.cos(elevation)*np.cos(angles)))
        return cls(np.linspace(0,duration,samples),positions,np.broadcast_to(center,positions.shape))


class GLTFInspector:
    """Structural and provenance checks for Nabla's GLB/glTF export profile.

    This inspector checks bounds, index ranges, unit normals, morph cardinality
    and receipt/buffer binding. It does not replace the complete Khronos glTF
    Validator or certify arbitrary third-party extension semantics.
    """
    @staticmethod
    def load(path):
        import struct
        root=Path(path)
        with root.open('rb') as stream:raw=stream.read(256*1024*1024+1)
        if len(raw)>256*1024*1024:raise ValueError('glTF inspection byte budget exceeded')
        if raw.startswith(b'glTF'):
            if len(raw)<28 or struct.unpack_from('<4sII',raw)!=(b'glTF',2,len(raw)):raise ValueError('Invalid GLB file header')
            json_length,kind=struct.unpack_from('<I4s',raw,12)
            if kind!=b'JSON' or json_length%4 or 20+json_length+8>len(raw):raise ValueError('Invalid GLB JSON chunk')
            document=json.loads(raw[20:20+json_length]);binary_length,kind=struct.unpack_from('<I4s',raw,20+json_length)
            if kind!=b'BIN\x00' or binary_length%4 or 28+json_length+binary_length!=len(raw):raise ValueError('Invalid GLB binary chunk')
            binary=raw[28+json_length:]
        else:
            document=json.loads(raw)
            buffers=document.get('buffers',[])
            if len(buffers)!=1:raise ValueError('Inspector supports one-buffer glTF profile')
            uri=buffers[0].get('uri')
            if not isinstance(uri,str):raise ValueError('glTF buffer URI missing')
            if uri.startswith('data:application/octet-stream;base64,'):
                binary=base64.b64decode(uri.split(',',1)[1],validate=True)
            else:
                target=Path(uri)
                if target.is_absolute() or '..' in target.parts or ':' in uri or '\\' in uri:raise ValueError('External buffer path escapes local glTF directory')
                target=root.parent/target
                if target.is_symlink() or not target.resolve().is_relative_to(root.parent.resolve()):raise ValueError('glTF buffer cannot follow an external symlink')
                with target.open('rb') as stream:binary=stream.read(256*1024*1024+1)
                if len(binary)>256*1024*1024:raise ValueError('External buffer exceeds byte budget')
        if document.get('asset',{}).get('version')!='2.0' or len(document.get('buffers',[]))!=1:
            raise ValueError('Only glTF 2.0 single-buffer profile supported')
        declared=document['buffers'][0]['byteLength']
        if type(declared) is not int or declared<0 or not 0<=len(binary)-declared<=3:raise ValueError('Declared glTF buffer length differs from actual bytes')
        return document,binary[:declared]

    @classmethod
    def inspect(cls, path):
        import numpy as np
        import hashlib
        document,binary=cls.load(path);views=document.get('bufferViews',[]);accessors=document.get('accessors',[])
        if len(views)>10000 or len(accessors)>10000:raise ValueError('glTF structural object budget exceeded')
        arrays=[];components={5125:('<u4',4),5126:('<f4',4)};widths={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}
        for view in views:
            if view.get('buffer')!=0 or type(view.get('byteOffset',0)) is not int or type(view.get('byteLength')) is not int or view.get('byteOffset',0)%4 or view.get('byteOffset',0)<0 or view['byteLength']<0 or view.get('byteOffset',0)+view['byteLength']>len(binary):
                raise ValueError('glTF bufferView exceeds aligned binary bounds')
        for accessor in accessors:
            if accessor.get('componentType') not in components or accessor.get('type') not in widths or 'sparse' in accessor:
                raise ValueError('Accessor is outside the supported dense float32/uint32 profile')
            view_index=accessor.get('bufferView');count=accessor.get('count');width=widths[accessor['type']]
            if type(view_index) is not int or not 0<=view_index<len(views) or type(count) is not int or not 1<=count<=10000000:
                raise ValueError('Accessor view/count invalid')
            view=views[view_index];dtype,size=components[accessor['componentType']];offset=accessor.get('byteOffset',0)
            if type(offset) is not int or offset<0 or offset%size or 'byteStride' in view or offset+count*width*size>view['byteLength']:
                raise ValueError('Accessor exceeds tightly packed buffer view')
            array=np.frombuffer(binary,dtype=dtype,count=count*width,offset=view.get('byteOffset',0)+offset).reshape(count,width)
            if not np.isfinite(array).all():raise ValueError('Nonfinite glTF accessor')
            for key,actual in [('min',array.min(axis=0)),('max',array.max(axis=0))]:
                if key in accessor and (len(accessor[key])!=width or not np.allclose(accessor[key],actual,rtol=1e-6,atol=1e-8)):
                    raise ValueError('Accessor bounds do not describe the actual stored float32 values')
            arrays.append(array)
        triangles=vertices=0
        for mesh in document.get('meshes',[]):
            for primitive in mesh.get('primitives',[]):
                attributes=primitive.get('attributes',{})
                if primitive.get('mode',4)!=4 or 'POSITION' not in attributes or 'indices' not in primitive:
                    raise ValueError('Only indexed triangle primitives supported by this profile')
                def value(index):
                    if type(index) is not int or not 0<=index<len(arrays):raise ValueError('Primitive accessor index invalid')
                    return arrays[index]
                positions=value(attributes['POSITION']);indices=value(primitive['indices'])
                if positions.shape[1]!=3 or indices.shape[1]!=1 or len(indices)%3 or indices.dtype.kind!='u' or indices.max()>=len(positions):
                    raise ValueError('Triangle primitive position/index dimensions or ranges invalid')
                triangles+=len(indices)//3;vertices+=len(positions)
                if 'NORMAL' in attributes:
                    normal=value(attributes['NORMAL'])
                    if normal.shape!=positions.shape or not np.allclose(np.linalg.norm(normal,axis=1),1,atol=1e-3,rtol=0):raise ValueError('glTF NORMAL is not a unit per-vertex vector')
                for target in primitive.get('targets',[]):
                    if 'POSITION' not in target or value(target['POSITION']).shape!=positions.shape:raise ValueError('Morph target position cardinality mismatch')
                if 'weights' in mesh and len(mesh['weights'])!=len(primitive.get('targets',[])):
                    raise ValueError('Morph target and default weight counts differ')
        evidence=document.get('asset',{}).get('extras',{}).get('nabla')
        if not evidence or not verify_receipt(evidence.get('receipt')) or evidence.get('receipt_id')!=evidence['receipt']['content_id'] or hashlib.sha256(binary).hexdigest()!=evidence.get('buffer_sha256'):
            raise ValueError('glTF receipt/buffer provenance failed')
        return {'version':'2.0','vertices':vertices,'triangles':triangles,'accessors':len(accessors),
                'binary_bytes':len(binary),'receipt_id':evidence['receipt_id'],'profile_checks_passed':True,
                'scope':'Nabla dense triangular export profile, not full Khronos extension validation'}


__all__ += ['SceneTimeline','CameraPath','GLTFInspector']


class GlyphFactory:
    """Closed 3-D arrow and tensor glyphs, suitable for universal triangle export."""
    @staticmethod
    def arrows(origins, vectors, *, radius=.02, scale=1., sides=8):
        import numpy as np
        points=_finite_points(origins,1,10000);directions=_finite_points(vectors,1,10000)
        if points.shape!=directions.shape or type(sides) is not int or not 3<=sides<=32 or not math.isfinite(radius) or radius<=0 or not math.isfinite(scale) or scale<=0:
            raise ValueError('Matching vector samples, positive scales and 3–32 arrow sides required')
        if len(points)*sides*6>200000:raise ValueError('Arrow glyph face budget exceeded')
        vertices=[];faces=[];scalars=[];skipped=[]
        for sample,(origin,vector) in enumerate(zip(points,directions)):
            norm=float(np.linalg.norm(vector))
            if norm==0:skipped.append(sample);continue
            w=vector/norm;axis=np.eye(3)[np.argmin(abs(w))];u=np.cross(axis,w);u/=np.linalg.norm(u);v=np.cross(w,u)
            length=norm*scale;base=len(vertices);vertices.append(tuple(origin));scalars.append(norm)
            for z,r in ((0.,radius),(.75*length,radius),(.75*length,2*radius)):
                for j in range(sides):
                    angle=2*math.pi*j/sides
                    vertices.append(tuple(origin+z*w+r*(math.cos(angle)*u+math.sin(angle)*v)));scalars.append(norm)
            tip=len(vertices);vertices.append(tuple(origin+length*w));scalars.append(norm)
            for j in range(sides):
                next_index=(j+1)%sides
                a,b=base+1+j,base+1+next_index;c,d=a+sides,b+sides;e,f=c+sides,d+sides
                faces.extend(((base,b,a),(a,b,c),(b,d,c),(c,f,e),(c,d,f),(e,f,tip)))
        if not faces:raise ValueError('Arrow glyph set has no nonzero vectors')
        return {'mesh':MeshData(tuple(vertices),tuple(faces),tuple(scalars),'Vector arrows'),
                'skipped_zero_vectors':skipped,'scalar_meaning':'Unscaled vector magnitude'}

    @staticmethod
    def tensor_ellipsoids(centers, tensors, *, kind='metric', scale=1., subdivisions=1,
                          minimum_axis_ratio=.02):
        import numpy as np
        points=_finite_points(centers,1,256);matrices=np.asarray(tensors,dtype=float)
        if matrices.shape!=(len(points),3,3) or not np.isfinite(matrices).all() or kind not in ('metric','stress'):
            raise ValueError('One finite symmetric 3x3 tensor per glyph center required')
        if not math.isfinite(scale) or scale<=0 or not 0<minimum_axis_ratio<=1:
            raise ValueError('Positive tensor display scale and explicit axis floor required')
        base=SurfaceFactory.icosphere(subdivisions=subdivisions)
        if len(base.triangles)*len(points)>200000:raise ValueError('Tensor glyph face budget exceeded')
        vertices=[];faces=[];values=[];diagnostics=[]
        for center,matrix in zip(points,matrices):
            if not np.allclose(matrix,matrix.T,atol=1e-12,rtol=1e-12):raise ValueError('Tensor glyph requires symmetric tensors')
            eigenvalues,vectors=np.linalg.eigh(matrix)
            if kind=='metric':
                if eigenvalues.min()<=0:raise ValueError('Metric ellipsoid requires positive definiteness; Lorentzian metrics are not Euclidean ellipsoids')
                axes=scale/np.sqrt(eigenvalues);floor_applied=False
            else:
                magnitudes=abs(eigenvalues);maximum=float(magnitudes.max())
                if maximum==0:raise ValueError('Zero stress tensor has no oriented ellipsoid')
                axes=scale*np.maximum(magnitudes/maximum,minimum_axis_ratio)
                floor_applied=bool(np.any(magnitudes/maximum<minimum_axis_ratio))
            transform=np.eye(4);transform[:3,:3]=vectors@np.diag(axes);transform[:3,3]=center
            glyph=base.transform(transform);offset=len(vertices)
            vertices.extend(glyph.vertices);faces.extend(tuple(offset+i for i in face) for face in glyph.triangles)
            values.extend([float(np.trace(matrix))]*len(glyph.vertices))
            diagnostics.append({'eigenvalues':eigenvalues.tolist(),'display_axes':axes.tolist(),'axis_floor_applied':floor_applied})
        return {'mesh':MeshData(tuple(vertices),tuple(faces),tuple(values),'Tensor ellipsoids'),
                'glyphs':diagnostics,'kind':kind,'scalar_meaning':'Tensor trace',
                'scope':'Metric unit quadrics, or stress magnitudes normalized for display; displayed stress axes are not physical metric lengths'}

    @staticmethod
    def merge(meshes, *, label='Merged scientific glyphs'):
        if not isinstance(meshes,(list,tuple)) or not meshes or len(meshes)>10000 or not all(isinstance(mesh,MeshData) for mesh in meshes):
            raise ValueError('Nonempty bounded list of validated meshes required')
        if sum(len(mesh.vertices) for mesh in meshes)>1000000 or sum(len(mesh.triangles) for mesh in meshes)>2000000:
            raise ValueError('Merged mesh budget exceeded')
        vertices=[];faces=[];scalars=[];with_scalars=all(mesh.scalars is not None for mesh in meshes)
        for mesh in meshes:
            offset=len(vertices);vertices.extend(mesh.vertices);faces.extend(tuple(offset+i for i in face) for face in mesh.triangles)
            if with_scalars:scalars.extend(mesh.scalars)
        return MeshData(tuple(vertices),tuple(faces),tuple(scalars) if with_scalars else None,label)


class MeshClipper:
    """Geometric half-space clipping with an optional simple-polygon end cap."""
    @staticmethod
    def _triangulate_polygon(points, indices, normal, tolerance):
        import numpy as np
        if not 3<=len(indices)<=2048:raise ValueError('Cap polygon supports 3–2048 vertices')
        n=np.asarray(normal,dtype=float);n/=np.linalg.norm(n)
        axis=np.eye(3)[np.argmin(abs(n))];u=np.cross(axis,n);u/=np.linalg.norm(u);v=np.cross(n,u)
        polygon=np.asarray([points[i] for i in indices]);flat=np.column_stack((polygon@u,polygon@v))
        signed=.5*sum(flat[i,0]*flat[(i+1)%len(flat),1]-flat[(i+1)%len(flat),0]*flat[i,1] for i in range(len(flat)))
        if abs(signed)<=tolerance:raise ValueError('Cap polygon is degenerate')
        order=list(range(len(indices)))
        if signed<0:order.reverse()
        def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
        faces=[];work=0
        while len(order)>3:
            ear=None
            for position,current in enumerate(order):
                work+=1
                if work>1000000:raise ArithmeticError('Cap triangulation work budget exhausted')
                previous=order[position-1];following=order[(position+1)%len(order)]
                a,b,c=flat[previous],flat[current],flat[following]
                if cross(a,b,c)<=tolerance:continue
                contains=False
                for other in order:
                    if other in (previous,current,following):continue
                    point=flat[other]
                    if min(cross(a,b,point),cross(b,c,point),cross(c,a,point))>=-tolerance:
                        contains=True;break
                if not contains:ear=position;faces.append((indices[previous],indices[current],indices[following]));break
            if ear is None:raise ValueError('Cap polygon is non-simple or numerically unresolved')
            order.pop(ear)
        faces.append(tuple(indices[i] for i in order))
        return faces

    @staticmethod
    def clip(mesh, normal, offset, *, keep_positive=True, cap=False, tolerance=1e-10):
        import numpy as np
        if not isinstance(mesh,MeshData):raise ValueError('Validated triangular mesh required')
        n=np.asarray(normal,dtype=float)
        if n.shape!=(3,) or not np.isfinite(n).all() or np.linalg.norm(n)==0 or not math.isfinite(offset) or type(keep_positive) is not bool or type(cap) is not bool or not 0<tolerance<.01:
            raise ValueError('Finite plane, boolean clipping policies and positive tolerance required')
        length=float(np.linalg.norm(n));n/=length;d=offset/length
        if not keep_positive:n=-n;d=-d
        points=np.asarray(mesh.vertices);distance=points@n-d;vertices=[];faces=[];cache={};scalars=[]
        def original(index):
            key=('vertex',index)
            if key not in cache:
                cache[key]=len(vertices);vertices.append(points[index])
                if mesh.scalars is not None:scalars.append(mesh.scalars[index])
            return cache[key]
        def crossing(a,b):
            if abs(distance[a])<=tolerance:return original(a)
            if abs(distance[b])<=tolerance:return original(b)
            key=('edge',*sorted((a,b)))
            if key not in cache:
                fraction=distance[a]/(distance[a]-distance[b]);cache[key]=len(vertices)
                vertices.append(points[a]+fraction*(points[b]-points[a]))
                if mesh.scalars is not None:scalars.append((1-fraction)*mesh.scalars[a]+fraction*mesh.scalars[b])
            return cache[key]
        for face in mesh.triangles:
            polygon=[]
            for a,b in ((face[0],face[1]),(face[1],face[2]),(face[2],face[0])):
                inside_a=distance[a]>=-tolerance;inside_b=distance[b]>=-tolerance
                if inside_a:polygon.append(original(a))
                if inside_a!=inside_b:polygon.append(crossing(a,b))
            polygon=list(dict.fromkeys(polygon))
            for i in range(1,len(polygon)-1):
                triangle=(polygon[0],polygon[i],polygon[i+1]);a,b,c=(vertices[v] for v in triangle)
                if np.linalg.norm(np.cross(b-a,c-a))>tolerance:faces.append(triangle)
        if not faces:raise ValueError('Clipping removed every nondegenerate triangle')
        used=sorted({v for face in faces for v in face});remap={old:new for new,old in enumerate(used)}
        vertices=[vertices[i] for i in used];faces=[tuple(remap[v] for v in face) for face in faces]
        values=tuple(scalars[i] for i in used) if mesh.scalars is not None else None
        clipped=MeshData(tuple(map(tuple,vertices)),tuple(faces),values,mesh.label+' / clipped')
        if cap:
            if not mesh.topology()['closed_oriented_surface']:raise ValueError('Automatic cap requires the original mesh to be a closed oriented surface')
            loops=MeshProcessor.boundary_loops(clipped)['loops']
            if len(loops)!=1:raise ValueError('Automatic cap currently supports one simple boundary loop without holes')
            outward=-n;cap_faces=MeshClipper._triangulate_polygon(vertices,loops[0],outward,tolerance)
            clipped=MeshData(clipped.vertices,clipped.triangles+tuple(cap_faces),clipped.scalars,clipped.label+' / capped')
            if not clipped.topology()['closed_oriented_surface']:raise ArithmeticError('Clipped cap did not close the oriented surface')
        return clipped


__all__ += ['GlyphFactory','MeshClipper']


class SpatialExperiment:
    """Publish a complete offline spatial artifact with immutable data hashes.

    The artifact binds mesh samples to supplied parent receipts. Optional JSON
    pointers verify that the actual XYZ arrays occur in those receipts; this is
    a data-binding check, not a proof of a physical model or interpolation law.
    """
    def __init__(self, mesh, receipts, *, frames=None, times=None, geometry_bindings=None):
        import numpy as np
        if not isinstance(mesh,MeshData) or not isinstance(receipts,(list,tuple)) or not 1<=len(receipts)<=128 or not all(verify_receipt(r) for r in receipts):
            raise ValueError('Validated mesh and 1–128 verified receipts required')
        self.mesh=mesh;self.receipts=tuple(json.loads(canonical_json(r)) for r in receipts)
        self.frames=np.asarray([mesh.vertices] if frames is None else frames,dtype=float)
        self.times=np.arange(len(self.frames),dtype=float) if times is None else np.asarray(times,dtype=float)
        if self.frames.ndim!=3 or self.frames.shape[1:]!=(len(mesh.vertices),3) or not 1<=len(self.frames)<=128 or self.frames.size>6000000 or not np.isfinite(self.frames).all():
            raise ValueError('Spatial experiment frame dimensions/budget invalid')
        if self.times.shape!=(len(self.frames),) or not np.isfinite(self.times).all() or np.any(np.diff(self.times)<=0):raise ValueError('Increasing spatial frame times required')
        for frame in self.frames:MeshData(tuple(map(tuple,frame)),mesh.triangles)
        self.geometry_bindings=geometry_bindings
        self.geometry_values_verified=False
        if geometry_bindings is not None:self._verify_bindings(geometry_bindings)

    @staticmethod
    def _pointer(value, pointer):
        if not isinstance(pointer,str) or not pointer.startswith('/') or len(pointer)>4096:raise ValueError('Geometry binding requires a bounded JSON Pointer')
        for token in pointer.split('/')[1:]:
            if re.search(r'~(?![01])',token):raise ValueError('Invalid JSON Pointer escape')
            token=token.replace('~1','/').replace('~0','~')
            if isinstance(value,list):
                if not re.fullmatch(r'0|[1-9][0-9]*',token):raise ValueError('Canonical nonnegative JSON Pointer array index required')
                index=int(token)
                if index>=len(value):raise ValueError('Geometry pointer index out of bounds')
                value=value[index]
            elif isinstance(value,dict):value=value[token]
            else:raise ValueError('Geometry pointer traverses a scalar')
        return value

    def _verify_bindings(self, bindings):
        import numpy as np
        from fractions import Fraction
        if not isinstance(bindings,(list,tuple)) or len(bindings)!=len(self.frames):raise ValueError('One geometry binding per frame required')
        for frame,binding in zip(self.frames,bindings):
            if not isinstance(binding,dict) or set(binding)!={'receipt_index','pointer'}:raise ValueError('Geometry binding needs receipt_index and pointer')
            index=binding['receipt_index']
            if type(index) is not int or not 0<=index<len(self.receipts):raise ValueError('Geometry binding receipt index invalid')
            values=self._pointer(self.receipts[index],binding['pointer'])
            if not isinstance(values,list) or len(values)!=len(frame) or any(not isinstance(row,list) or len(row)!=3 for row in values):
                raise ValueError('Bound geometry is not an XYZ array matching the mesh')
            numeric=[]
            for row in values:
                converted=[]
                for value in row:
                    if type(value) in (int,float):number=float(value)
                    elif isinstance(value,str) and len(value)<=128:
                        try:number=float(Fraction(value))
                        except (ValueError,ZeroDivisionError) as error:raise ValueError('Bound geometry contains a nonnumeric rational') from error
                    else:raise ValueError('Bound geometry contains an unsupported coordinate value')
                    if not math.isfinite(number):raise ValueError('Bound geometry is nonfinite')
                    converted.append(number)
                numeric.append(converted)
            if not np.array_equal(np.asarray(numeric),frame):raise ValueError('Displayed frame differs from the referenced receipt values')
        self.geometry_values_verified=True

    def observation_receipt(self):
        from ..calc.receipt import receipt
        from ..core.semantic_ir import fingerprint
        return receipt('graphics.spatial_experiment',
            {'parent_receipts':[r['content_id'] for r in self.receipts],'times':self.times.tolist(),
             'geometry_bindings':self.geometry_bindings},
            {'mesh_sha256':fingerprint(self.mesh.to_data()),'frames_sha256':fingerprint(self.frames.tolist())},
            backend='nabla.spatial_experiment',parents=[r['content_id'] for r in self.receipts],
            metadata={'geometry_values_verified':self.geometry_values_verified,
                      'scientific_model_verified':False,'samples':'Recorded or externally supplied, as indicated by geometry_bindings'})

    def build(self, destination, *, title='Nabla spatial experiment', colormap='viridis',
              include_manim=False):
        import tempfile
        from ..artifacts.bundle import create_bundle
        target=Path(destination)
        if target.exists() or target.is_symlink():raise FileExistsError('Spatial artifact requires a fresh destination')
        if colormap not in ColorMaps.ANCHORS or type(include_manim) is not bool:raise ValueError('Invalid colormap or animation policy')
        target.parent.mkdir(parents=True,exist_ok=True)
        observation=self.observation_receipt();bundle=create_bundle(list(self.receipts)+[observation])
        with tempfile.TemporaryDirectory(prefix='.nabla-spatial-',dir=target.parent) as directory:
            stage=Path(directory)/'artifact';stage.mkdir()
            colors=ColorMaps.map(self.mesh.scalars,colormap) if self.mesh.scalars is not None else None
            export_options={'colors':colors}
            if len(self.frames)>1:export_options.update(frames=self.frames.tolist(),times=self.times.tolist())
            GLTFExporter().write(self.mesh,stage/'scene.glb',audit_receipt=observation,**export_options)
            structural=GLTFInspector.inspect(stage/'scene.glb')
            page=Standalone3DViewer().source(self.mesh,observation,frames=self.frames.tolist(),times=self.times.tolist(),title=title)
            encoded=base64.b64encode(canonical_json(bundle).encode()).decode()
            download='<button id="experiment-download">Download complete experiment</button><script>document.getElementById("experiment-download").onclick=()=>{const bytes=Uint8Array.from(atob('+json.dumps(encoded)+'),c=>c.charCodeAt(0));const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([bytes],{type:"application/json"}));a.download="experiment.json";a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);};</script>'
            page=page.replace('</html>',download+'</html>')
            (stage/'scene.html').write_text(page,encoding='utf-8')
            (stage/'experiment.json').write_text(canonical_json(bundle),encoding='utf-8')
            (stage/'mesh.json').write_text(canonical_json(self.mesh.to_data()),encoding='utf-8')
            (stage/'frames.json').write_text(canonical_json({'times':self.times.tolist(),'frames':self.frames.tolist()}),encoding='utf-8')
            if include_manim:
                source=ManimSceneSynthesizer().mesh_scene(self.mesh,observation,frames=self.frames.tolist())
                (stage/'scene.py').write_text(source,encoding='utf-8')
            manifest={'schema':'nabla.spatial-artifact.v1','experiment_hash':bundle['content_id'],
                      'observation_receipt':observation['content_id'],'geometry_values_verified':self.geometry_values_verified,
                      'structural_profile':structural,
                      'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.iterdir()) if p.is_file()},
                      'scientific_acceptance_established':False}
            (stage/'manifest.json').write_text(canonical_json(manifest),encoding='utf-8')
            stage.rename(target)
        return {'directory':str(target),'experiment_hash':bundle['content_id'],'observation_receipt':observation['content_id'],
                'geometry_values_verified':self.geometry_values_verified,'files':len(manifest['files'])}

    @staticmethod
    def verify(directory):
        from ..artifacts.bundle import load_bundle
        from ..core.semantic_ir import fingerprint
        root=Path(directory)
        try:
            if root.is_symlink():return False
            manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
            if manifest['schema']!='nabla.spatial-artifact.v1':return False
            actual={p.name for p in root.iterdir() if p.is_file() and p.name!='manifest.json'}
            if actual!=set(manifest['files']):return False
            for name,digest in manifest['files'].items():
                path=root/name
                if Path(name).name!=name or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:return False
            bundle=load_bundle(root/'experiment.json')
            if bundle['content_id']!=manifest['experiment_hash']:return False
            GLTFInspector.inspect(root/'scene.glb')
            records=[r for r in bundle['receipts'] if r['content_id']==manifest['observation_receipt']]
            if len(records)!=1:return False
            mesh=json.loads((root/'mesh.json').read_text(encoding='utf-8'));frames=json.loads((root/'frames.json').read_text(encoding='utf-8'))
            return records[0]['result']=={'mesh_sha256':fingerprint(mesh),'frames_sha256':fingerprint(frames['frames'])}
        except (OSError,ValueError,TypeError,KeyError,ArithmeticError):return False


__all__ += ['SpatialExperiment']


class MeshSampling:
    """Area-weighted reproducible sampling and geometric distance diagnostics."""

    @staticmethod
    def surface(mesh, count=1000, *, seed=0):
        import numpy as np
        if not isinstance(mesh, MeshData):
            raise ValueError('Validated triangle mesh required')
        if type(count) is not int or not 1 <= count <= 1000000:
            raise ValueError('Surface sample count outside budget')
        if type(seed) is not int or not 0 <= seed < 2**64:
            raise ValueError('Unsigned 64-bit sampling seed required')
        vertices = np.asarray(mesh.vertices)
        triangles = vertices[np.asarray(mesh.triangles)]
        areas = np.linalg.norm(np.cross(triangles[:, 1]-triangles[:, 0],
                                        triangles[:, 2]-triangles[:, 0]), axis=1)/2
        total = float(areas.sum())
        if not math.isfinite(total) or total <= 0:
            raise ValueError('Mesh has no finite positive area')
        rng = np.random.Generator(np.random.PCG64(seed))
        indices = rng.choice(len(triangles), count, p=areas/total)
        uniform = rng.random((count, 2))
        root = np.sqrt(uniform[:, 0])
        barycentric = np.column_stack((1-root, root*(1-uniform[:, 1]), root*uniform[:, 1]))
        points = np.einsum('ni,nij->nj', barycentric, triangles[indices])
        result = {'points': points.tolist(), 'triangle_indices': indices.tolist(),
                  'barycentric': barycentric.tolist(), 'area': total, 'seed': seed,
                  'distribution': 'Uniform with respect to triangle surface area'}
        if mesh.scalars is not None:
            values = np.asarray(mesh.scalars)[np.asarray(mesh.triangles)[indices]]
            result['scalars'] = np.einsum('ni,ni->n', barycentric, values).tolist()
        return result

    @staticmethod
    def closest_points(mesh, points):
        """Closest points using a bounded vectorized face-interior/edge search.

        Every triangle contributes its three clamped edge projections and its
        planar projection when that projection lies inside the triangle.
        This is an exact geometric search up to floating-point rounding, unlike
        a nearest-vertex approximation. Work is bounded by points times faces.
        """
        import numpy as np
        if not isinstance(mesh, MeshData):
            raise ValueError('Validated triangle mesh required')
        query = _finite_points(points, 1, 100000)
        if len(query)*len(mesh.triangles) > 2000000:
            raise ValueError('Closest-point work budget exceeded')
        triangles = np.asarray(mesh.vertices)[np.asarray(mesh.triangles)]
        a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
        u, v = b-a, c-a
        uu = np.einsum('ij,ij->i', u, u)
        uv = np.einsum('ij,ij->i', u, v)
        vv = np.einsum('ij,ij->i', v, v)
        denominator = uu*vv-uv*uv
        if np.any(denominator <= 0):
            raise ArithmeticError('Triangle Gram determinant lost positive precision')
        answers = []
        for point in query:
            displacement = point-a
            du = np.einsum('ij,ij->i', displacement, u)
            dv = np.einsum('ij,ij->i', displacement, v)
            beta = (vv*du-uv*dv)/denominator
            gamma = (uu*dv-uv*du)/denominator
            interior = (beta >= 0) & (gamma >= 0) & (beta+gamma <= 1)
            projected = a+beta[:, None]*u+gamma[:, None]*v
            candidates = [projected]
            valid = [interior]
            for start, end in ((a, b), (b, c), (c, a)):
                direction = end-start
                parameter = np.einsum('ij,ij->i', point-start, direction)
                parameter /= np.einsum('ij,ij->i', direction, direction)
                parameter = np.clip(parameter, 0, 1)
                candidates.append(start+parameter[:, None]*direction)
                valid.append(np.ones(len(triangles), dtype=bool))
            candidates = np.stack(candidates, axis=1)
            distances = np.sum((candidates-point)**2, axis=2)
            distances[~np.stack(valid, axis=1)] = np.inf
            flat = int(np.argmin(distances))
            face, kind = np.unravel_index(flat, distances.shape)
            closest = candidates[face, kind]
            offset = closest-a[face]
            bu, bv = float(offset@u[face]), float(offset@v[face])
            beta_hit = (vv[face]*bu-uv[face]*bv)/denominator[face]
            gamma_hit = (uu[face]*bv-uv[face]*bu)/denominator[face]
            barycentric = [float(1-beta_hit-gamma_hit), float(beta_hit), float(gamma_hit)]
            answer = {'point': closest.tolist(), 'distance': float(np.sqrt(distances[face, kind])),
                      'triangle_index': int(face), 'barycentric': barycentric}
            if mesh.scalars is not None:
                answer['scalar'] = float(np.asarray(mesh.scalars)[np.asarray(mesh.triangles)[face]]@barycentric)
            answers.append(answer)
        return answers

    @staticmethod
    def sampled_distance(left, right, count=1000, *, seed=0):
        """Sampled symmetric distances, explicitly a lower estimate of Hausdorff."""
        import numpy as np
        first = MeshSampling.surface(left, count, seed=seed)
        second = MeshSampling.surface(right, count, seed=seed)
        forward = np.asarray([r['distance'] for r in MeshSampling.closest_points(right, first['points'])])
        backward = np.asarray([r['distance'] for r in MeshSampling.closest_points(left, second['points'])])
        return {'sampled_hausdorff_lower_estimate': float(max(forward.max(), backward.max())),
                'symmetric_mean_distance': float((forward.mean()+backward.mean())/2),
                'symmetric_rms_distance': float(np.sqrt((np.mean(forward**2)+np.mean(backward**2))/2)),
                'samples_per_surface': count, 'seed': seed,
                'scope': 'Random surface samples; not a certified global Hausdorff upper bound'}


__all__ += ['MeshSampling']


def integrate_vertex_field(mesh, values):
    """Exact integral of a continuous piecewise-linear scalar/vector field.

    Values are specified at vertices; the triangle integral is its area times
    the arithmetic mean of its three vertex values. This integrates the mesh
    interpolant, rather than an unspecified continuum field.
    """
    import numpy as np
    if not isinstance(mesh, MeshData):
        raise ValueError('Validated mesh required')
    data = np.asarray(values, dtype=float)
    if data.ndim not in (1, 2) or data.shape[0] != len(mesh.vertices):
        raise ValueError('One scalar or vector per mesh vertex required')
    if data.ndim == 2 and not 1 <= data.shape[1] <= 16:
        raise ValueError('Vector field component budget exceeded')
    if not np.isfinite(data).all():
        raise ValueError('Finite field values required')
    indices = np.asarray(mesh.triangles)
    triangles = np.asarray(mesh.vertices)[indices]
    areas = np.linalg.norm(np.cross(triangles[:, 1]-triangles[:, 0],
                                    triangles[:, 2]-triangles[:, 0]), axis=1)/2
    averages = data[indices].mean(axis=1)
    result = np.tensordot(areas, averages, axes=(0, 0))
    if not np.isfinite(result).all():
        raise ArithmeticError('Surface field integral overflow')
    return {'integral': result.tolist(), 'area': float(areas.sum()),
            'field_representation': 'Continuous piecewise-linear on the supplied triangle mesh',
            'quadrature': 'Exact barycentric first-degree rule up to floating-point rounding'}


__all__ += ['integrate_vertex_field']
