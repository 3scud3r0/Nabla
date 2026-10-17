"""glTF 2.0 / GLB mesh export with embedded Nabla receipt provenance.

Coordinates follow glTF: metres, right-handed, Y up. Rendering speed is the
consumer engine's responsibility; exporting glTF does not certify a frame rate.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import tempfile

from ..calc.receipt import verify_receipt
from ..core.semantic_ir import canonical_json


def _publish_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    descriptor,temporary = tempfile.mkstemp(prefix='.nabla-',dir=path.parent)
    try:
        with os.fdopen(descriptor,'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.link(temporary,path)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return path


class WebGLExporter:
    def __init__(self, *, max_vertices=1000000, max_triangles=2000000):
        if any(type(v) is not int or not 1 <= v <= 2000000 for v in (max_vertices,max_triangles)):
            raise ValueError('Invalid mesh budget')
        self.max_vertices,self.max_triangles = max_vertices,max_triangles

    @staticmethod
    def heightfield(values, *, spacing=(1.,1.), height_scale=1.):
        if not isinstance(values,(list,tuple)) or not 2 <= len(values) <= 1000:
            raise ValueError('Heightfield requires 2–1000 rows')
        width = len(values[0])
        if not 2 <= width <= 1000 or any(len(row) != width for row in values):
            raise ValueError('Heightfield must be rectangular with 2–1000 columns')
        if len(spacing) != 2 or any(type(x) not in (int,float) or not math.isfinite(x) or x <= 0 for x in spacing) or not math.isfinite(height_scale):
            raise ValueError('Invalid heightfield scales')
        vertices = [[col*spacing[0],float(value)*height_scale,-row*spacing[1]]
                    for row,values_row in enumerate(values) for col,value in enumerate(values_row)]
        triangles = []
        for row in range(len(values)-1):
            for col in range(width-1):
                a = row*width+col; b = a+1; c = a+width; d = c+1
                triangles.extend(((a,b,c),(b,d,c)))
        return vertices,triangles

    def _mesh(self, vertices, triangles, audit_receipt, colors=None):
        if not verify_receipt(audit_receipt):
            raise ValueError('A valid Nabla receipt is required')
        if not isinstance(vertices,(list,tuple)) or not 3 <= len(vertices) <= self.max_vertices:
            raise ValueError('Mesh vertex budget exceeded')
        points = []
        for point in vertices:
            if len(point) != 3 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v) > 1e30 for v in point):
                raise ValueError('Vertices require finite float32-compatible XYZ triples')
            # Geometry and normals must describe the positions actually stored.
            points.append(struct.unpack('<3f',struct.pack('<3f',*point)))
        if not isinstance(triangles,(list,tuple)) or not 1 <= len(triangles) <= self.max_triangles:
            raise ValueError('Mesh triangle budget exceeded')
        indices = []
        normals = [[0.,0.,0.] for _ in points]
        for face in triangles:
            if len(face) != 3 or any(type(i) is not int or not 0 <= i < len(points) for i in face) or len(set(face)) != 3:
                raise ValueError('Triangle indices must be distinct and inside the mesh')
            a,b,c = (points[i] for i in face)
            u = [b[k]-a[k] for k in range(3)]; v = [c[k]-a[k] for k in range(3)]
            normal = [u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
            if sum(x*x for x in normal) == 0:
                raise ValueError('Degenerate triangles cannot define surface normals')
            for index in face:
                normals[index] = [normals[index][k]+normal[k] for k in range(3)]
            indices.extend(face)
        for i,normal in enumerate(normals):
            norm = math.sqrt(sum(x*x for x in normal))
            normals[i] = [v/norm for v in normal] if norm else [0.,1.,0.]
        chunks,views,accessors = [],[],[]
        def buffer(values, components, component_type, kind, target):
            offset = sum(len(chunk) for chunk in chunks)
            padding = (-offset) % 4
            if padding:
                chunks.append(b'\0'*padding); offset += padding
            code = 'f' if component_type == 5126 else 'I'
            raw = struct.pack('<'+code*len(values),*values)
            view = len(views); views.append({'buffer':0,'byteOffset':offset,'byteLength':len(raw),'target':target})
            accessor = {'bufferView':view,'componentType':component_type,'count':len(values)//components,'type':kind}
            accessors.append(accessor); chunks.append(raw)
            return len(accessors)-1
        position = buffer([v for p in points for v in p],3,5126,'VEC3',34962)
        # Bounds describe the stored float32 positions, including rounding.
        stored = struct.unpack('<'+'f'*(3*len(points)),chunks[0])
        accessors[position]['min'] = [min(stored[k::3]) for k in range(3)]
        accessors[position]['max'] = [max(stored[k::3]) for k in range(3)]
        normal = buffer([v for row in normals for v in row],3,5126,'VEC3',34962)
        element = buffer(indices,1,5125,'SCALAR',34963)
        attributes = {'POSITION':position,'NORMAL':normal}
        if colors is not None:
            if len(colors) != len(points) or any(len(row) != 3 or any(type(v) not in (int,float) or not math.isfinite(v) or not 0 <= v <= 1 for v in row) for row in colors):
                raise ValueError('Colors must provide RGB in [0,1] per vertex')
            attributes['COLOR_0'] = buffer([v for row in colors for v in row],3,5126,'VEC3',34962)
        binary = b''.join(chunks)
        data = {'asset':{'version':'2.0','generator':'Nabla WebGLExporter',
                        'extras':{'nabla':{'receipt':audit_receipt,'receipt_id':audit_receipt['content_id'],
                                          'buffer_sha256':hashlib.sha256(binary).hexdigest(),
                                          'coordinate_system':'right-handed Y-up metres'}}},
                'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0}],
                'meshes':[{'primitives':[{'attributes':attributes,'indices':element,'mode':4}]}],
                'buffers':[{'byteLength':len(binary)}],'bufferViews':views,'accessors':accessors}
        return data,binary

    def export_glb(self, vertices, triangles, destination, *, audit_receipt, colors=None):
        data,binary = self._mesh(vertices,triangles,audit_receipt,colors)
        encoded = canonical_json(data).encode()
        encoded += b' '*((-len(encoded)) % 4)
        padded = binary+b'\0'*((-len(binary)) % 4)
        length = 12+8+len(encoded)+8+len(padded)
        glb = struct.pack('<4sII',b'glTF',2,length)+struct.pack('<I4s',len(encoded),b'JSON')+encoded
        glb += struct.pack('<I4s',len(padded),b'BIN\0')+padded
        return _publish_bytes(destination,glb)

    def export_gltf(self, vertices, triangles, destination, *, audit_receipt, colors=None):
        data,binary = self._mesh(vertices,triangles,audit_receipt,colors)
        root = Path(destination)
        root.mkdir(parents=True,exist_ok=False)
        data['buffers'][0]['uri'] = 'mesh.bin'
        try:
            _publish_bytes(root/'mesh.bin',binary)
            _publish_bytes(root/'scene.gltf',canonical_json(data).encode())
        except BaseException:
            for path in (root/'mesh.bin',root/'scene.gltf'):
                path.unlink(missing_ok=True)
            root.rmdir()
            raise
        return root/'scene.gltf'

    @staticmethod
    def inspect_glb(path):
        path = Path(path)
        if path.stat().st_size > 256*1024*1024:
            raise ValueError('GLB exceeds inspection budget')
        raw = path.read_bytes()
        if len(raw) < 28 or struct.unpack('<4sII',raw[:12]) != (b'glTF',2,len(raw)):
            raise ValueError('Invalid GLB header')
        size,kind = struct.unpack('<I4s',raw[12:20])
        if kind != b'JSON' or size % 4 or 20+size+8 > len(raw):
            raise ValueError('Invalid GLB JSON chunk')
        data = json.loads(raw[20:20+size])
        length,kind = struct.unpack('<I4s',raw[20+size:28+size])
        binary = raw[28+size:]
        if kind != b'BIN\0' or length != len(binary) or length % 4:
            raise ValueError('Invalid GLB binary chunk')
        declared = data['buffers'][0]['byteLength']
        evidence = data['asset']['extras']['nabla']
        if not 0 <= len(binary)-declared <= 3 or hashlib.sha256(binary[:declared]).hexdigest() != evidence['buffer_sha256'] or not verify_receipt(evidence['receipt']) or evidence['receipt']['content_id'] != evidence['receipt_id']:
            raise ValueError('GLB provenance or buffer integrity failed')
        for view in data['bufferViews']:
            if view['buffer'] != 0 or view['byteOffset'] % 4 or view['byteOffset'] < 0 or view['byteLength'] < 0 or view['byteOffset']+view['byteLength'] > declared:
                raise ValueError('GLB buffer view exceeds its buffer')
        return data
