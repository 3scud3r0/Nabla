"""Thirty authored V1 operations, fixed targets and closed JSON inputs."""
from importlib import import_module
from .advanced_math import obj,arr,mapping,N,I,B,T,Q,V,NV,NM,EX,EV,EM,FORM,S

ENTRIES={}


def add(name, module, function, fields, required, area, contract):
    ENTRIES[name]={'path':module+':'+function,'schema':obj(fields,required),
                   'area':area,'contract':contract}


MANIFOLD='ops.advanced_calculus_manifold'
ALGEBRA='ops.abstract_algebra_crypto'
STOCHASTIC='ops.stochastic_and_information'
GRAPHICS='graphics.spatial_engine_3d'
METRIC={'coordinates':S,'metric':EM}
add('manifold_christoffel',MANIFOLD,'manifold_christoffel',dict(METRIC,kind={'enum':['first','second']},point=NV),['coordinates','metric'],'geometry','Local Levi-Civita symbols, explicit chart domain and kind')
add('manifold_riemann',MANIFOLD,'manifold_riemann',dict(METRIC,covariant=B),['coordinates','metric'],'geometry','Exact local symbolic curvature; nonsingularity and smoothness hypotheses')
add('manifold_ricci',MANIFOLD,'manifold_ricci',dict(METRIC,cosmological_constant=EX),['coordinates','metric'],'geometry','Ricci, scalar and Einstein contractions; no automatic physical field validation')
add('geodesic_solve',MANIFOLD,'geodesic_solve',dict(METRIC,position=NV,velocity=NV,duration=N,samples=I,method=T,rtol=N,atol=N),['coordinates','metric','position','velocity'],'geometry','Adaptive local geodesic with observed tangent norm drift, not certified error')
add('euler_lagrange_solve',MANIFOLD,'euler_lagrange_solve',{'lagrangian':EX,'fields':S,'position':NV,'velocity':NV,'duration':N,'samples':I,'time':T,'method':T,'rtol':N,'atol':N},['lagrangian','fields','position','velocity'],'calculus','Regular first-order mechanical Lagrangian; derived dynamics and numerical energy diagnostics')
FIELD={'anyOf':[I,arr(I,64)]}
POINT={'anyOf':[{'type':'null'},arr(FIELD,2,2)]}
add('galois_field_op',ALGEBRA,'galois_field_op',{'p':I,'modulus':arr(I,17,2),'left':FIELD,'right':FIELD,'field_operation':T,'exponent':I},['p','modulus','left'],'algebra','Exact bounded GF(p^n); Python arithmetic is variable-time')
PRIME_COORDINATE={'anyOf':[I,{'type':'string','pattern':'^[0-9]+$','maxLength':160}]}
G1={'anyOf':[{'type':'null'},arr(PRIME_COORDINATE,3,2)]}
G2={'anyOf':[{'type':'null'},arr(arr(PRIME_COORDINATE,2,2),3,2)]}
add('elliptic_curve_pairing',ALGEBRA,'elliptic_curve_pairing',{'curve':{'enum':['BN254','BLS12-381']},'g1':G1,'g2':G2},[],'algebra','Subgroup-checked optimal Ate pairing via optional py_ecc backend; no SNARK protocol claim')
add('grobner_basis_solve',ALGEBRA,'grobner_basis_solve',{'generators':S,'variables':S,'order':T,'max_pairs':I},['generators','variables'],'algebra','Own bounded Buchberger over QQ with exact S-criterion verification')
add('lie_algebra_bch',ALGEBRA,'lie_algebra_bch',{'kind':{'enum':['so3','su2','su3']},'left':EV,'right':EV,'order':I},['kind','left','right'],'algebra','Exact matrix BCH through degree four; convergence beyond formal truncation not established')
SDE={'variables':S,'drift':EV,'diffusion':EM,'initial':NV,'duration':N,'steps':I,'seed':I,'paths':I,'convention':{'enum':['ito','stratonovich']}}
for name in ('sde_euler_maruyama','sde_milstein'):
    add(name,STOCHASTIC,name,SDE,['variables','drift','diffusion','initial'],'probability','Seeded SDE; Milstein requires commuting noise; convergence orders require regularity')
add('fokker_planck_solve',STOCHASTIC,'fokker_planck_solve',{'centers':NV,'drift':NV,'diffusion':NV,'density':NV,'duration':N,'steps':I,'method':T},['centers','drift','diffusion','density'],'probability','Conservative variable-coefficient 1D finite volumes with reflecting boundary')
add('information_divergence_kl',STOCHASTIC,'information_divergence_kl',{'probabilities':NV,'reference':NV,'base':N},['probabilities','reference'],'probability','Discrete KL with explicit infinite-divergence support mismatch')
JSON_VALUE={'$ref':'#/$defs/v1_json_value'}
AUDIT={'type':'object','maxProperties':32,'additionalProperties':JSON_VALUE}
GEOMETRY={'vertices':NM,'triangles':arr(arr(I,3,3),200000,1),'audit_receipt':AUDIT}
add('graphics_export_gltf',GRAPHICS,'graphics_export_gltf',dict(GEOMETRY,colors=NM,binary=B),list(GEOMETRY),'geometry','In-memory glTF/GLB serialization; supplied geometry remains distinct from receipt replay')
add('graphics_export_html3d',GRAPHICS,'graphics_export_html3d',dict(GEOMETRY,scalars=NV,frames=arr(NM,128,1),times=NV,title=T),list(GEOMETRY),'geometry','Offline embedded Three.js/OrbitControls viewer; device-dependent performance')
add('graphics_compile_manim',GRAPHICS,'graphics_compile_manim',dict(GEOMETRY,frames=arr(NM,64,1),equations=S,variables=S,duration=N),list(GEOMETRY),'geometry','Generated native Manim script; renderer and optional TeX required for MP4')
add('manifold_tensor',MANIFOLD,'manifold_tensor',dict(METRIC,variance=arr({'enum':[-1,1]},5),components=JSON_VALUE,kind=T,slots=arr(I,5),scalar=EX,other=JSON_VALUE,other_variance=arr({'enum':[-1,1]},5)),['coordinates','variance','components','kind'],'geometry','Rank <=5 mixed tensor operations on one chart')
add('manifold_surface_fem',MANIFOLD,'manifold_surface_fem',{'vertices':NM,'triangles':arr(arr(I,3,3),200000,1),'kind':T,'values':NV,'duration':N,'steps':I,'source':I,'count':I,'dirichlet':mapping(N),'zero_mean':B},['vertices','triangles','kind'],'geometry','Sparse triangular-surface FEM; numerical continuum error remains uncertified')
add('manifold_stress_scalar',MANIFOLD,'scalar_field_stress',dict(METRIC,field=EX,potential=EX,field_symbol=T),['coordinates','metric','field'],'geometry','Local minimally coupled scalar stress and field residual, c=1')
add('manifold_stress_maxwell',MANIFOLD,'maxwell_field_stress',dict(METRIC,potential=EV),['coordinates','metric','potential'],'geometry','Four-dimensional Maxwell stress and source-free residual under explicit conventions')
add('manifold_adm',MANIFOLD,'adm_decomposition',METRIC,['coordinates','metric'],'geometry','3+1 split; positive lapse squared and spatial positive definiteness are hypotheses')
add('algebra_field_factorization',ALGEBRA,'algebra_field_factorization',{'p':I,'modulus':arr(I,17,2),'coefficients':arr(FIELD,129,1),'seed':I},['p','modulus','coefficients'],'algebra','Square-free, distinct/equal-degree finite-field factorization with exact reconstruction')
add('algebra_reed_solomon',ALGEBRA,'algebra_reed_solomon',{'p':I,'modulus':arr(I,17,2),'nodes':arr(FIELD,256,1),'message_length':I,'values':arr(FIELD,256,1),'kind':T,'errors':I},['p','modulus','nodes','message_length','values'],'algebra','Exact evaluation coding and verified Berlekamp-Welch unique error correction')
add('algebra_ntt',ALGEBRA,'number_theoretic_transform',{'values':arr(I,65536,1),'prime':I,'inverse':B,'root':I},['values','prime'],'algebra','Exact radix-two modular NTT, prime below 2^31; no constant-time claim')
add('information_channel_capacity',STOCHASTIC,'gaussian_channel_capacity',{'noise_variances':NV,'power':N,'gains':NV,'tolerance':N},['noise_variances','power'],'probability','Water-filling capacity of independent real Gaussian subchannels, bits/use')
add('information_gaussian_process',STOCHASTIC,'gaussian_process',{'train_x':NM,'train_y':NV,'query_x':NM,'length_scale':N,'variance':N,'noise':N},['train_x','train_y','query_x'],'probability','Finite RBF Gaussian-process posterior; supplied hyperparameters and noise variance')
add('information_mutual',STOCHASTIC,'mutual_information',{'joint':NM,'base':N},['joint'],'probability','Discrete-law mutual information; no causal inference or estimator calibration')
add('stochastic_linear_transition',STOCHASTIC,'linear_sde_transition',{'drift_matrix':NM,'diffusion_matrix':NM,'duration':N,'offset':NV},['drift_matrix','diffusion_matrix','duration'],'probability','Van Loan transition and process covariance for affine constant-coefficient SDE')
add('graphics_surface_parametric',GRAPHICS,'parametric_surface',{'components':S,'parameters':S,'bounds':NM,'shape':arr(I,2,2),'periodic':arr(B,2,2)},['components','parameters','bounds'],'geometry','Sampled parametric triangular surface; topology and sampling error remain explicit')
add('publishing_badge_svg','publishing.living_papers_compiler','provenance_badge',{'experiment_hash':T,'timestamp':T,'verification_link':T},['experiment_hash','timestamp'],'geometry','Escaped local-link SVG provenance badge; hash integrity is not scientific certification')

OPERATIONS={name:(entry['area'],set(entry['schema']['required']),set(entry['schema']['properties'])-set(entry['schema']['required']),entry['contract']) for name,entry in ENTRIES.items()}


def schema(name):
    from copy import deepcopy
    result=deepcopy(ENTRIES[name]['schema'])
    result['$defs']={'v1_json_value':{'anyOf':[N,B,T,{'type':'null'},arr(JSON_VALUE,100000),mapping(JSON_VALUE)]}}
    return result


def execute(name, arguments):
    if name not in ENTRIES or not isinstance(arguments,dict):raise ValueError('Unknown V1 operation')
    entry=ENTRIES[name];fields=entry['schema'];required=set(fields['required']);allowed=set(fields['properties'])
    if not required<=arguments.keys() or arguments.keys()-allowed:raise ValueError('Arguments differ from the closed V1 signature')
    module,function=entry['path'].split(':')
    result=getattr(import_module('nablamath.'+module),function)(**arguments)
    from ..math._structured import data
    return data(result)
