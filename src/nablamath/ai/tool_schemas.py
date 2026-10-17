"""Authored nested JSON types for every operation; no arbitrary JSON fallback."""
from copy import deepcopy

RATIONAL = {'anyOf':[{'type':'integer'}, {'type':'string','maxLength':128,
    'pattern':r'^[+-]?(?:[0-9]+(?:/[0-9]+|(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?)?|\.[0-9]+(?:[eE][+-]?[0-9]+)?)$'}]}
NUMBER = {'type':'number'}
INTEGER = {'type':'integer'}
TEXT = {'type':'string','minLength':1,'maxLength':4096}
BOOLEAN = {'type':'boolean'}
LARGE_INT = {'anyOf':[{'type':'integer'}, {'type':'string','pattern':'^[0-9]+$','maxLength':1235}]}


def array(items, *, minimum=1, maximum=10000):
    return {'type':'array','items':deepcopy(items),'minItems':minimum,'maxItems':maximum}


def record(properties, required=()):
    return {'type':'object','properties':deepcopy(properties),'required':list(required),'additionalProperties':False}


def mapping(values):
    return {'type':'object','maxProperties':128,'additionalProperties':deepcopy(values)}


def enum(*values):
    return {'type':'string','enum':list(values)}


VECTOR = array(RATIONAL)
MATRIX = array(VECTOR,maximum=1000)
PAIR = array(NUMBER,minimum=2,maximum=2)
COMPLEX = {'anyOf':[NUMBER,PAIR]}
SAMPLES = array(COMPLEX,maximum=65536)
TENSOR = {'anyOf':[NUMBER,array({'$ref':'#/$defs/tensor_value'})]}
GRAPH_NODES = array({'oneOf':[
    record({'op':{'const':'input'},'name':TEXT},('op','name')),
    record({'op':{'const':'constant'},'value':NUMBER},('op','value')),
    record({'op':enum('add','subtract','multiply','divide'),'args':array(INTEGER,minimum=2,maximum=2)},('op','args')),
    record({'op':enum('exp','log','sin','cos','tanh','negate'),'args':array(INTEGER,minimum=1,maximum=1)},('op','args')),
]},maximum=256)
GATES = array({'oneOf':[
    record({'gate':enum('X','Y','Z','H','S','T'),'target':INTEGER},('gate','target')),
    record({'gate':{'const':'CX'},'control':INTEGER,'target':INTEGER},('gate','control','target')),
    record({'gate':{'const':'RZ'},'target':INTEGER,'angle':NUMBER},('gate','target','angle')),
]},minimum=0,maximum=1000)

DEFAULTS = {}
for name in 'a base d k n prime target trials successes draws observed population steps window lag order max_attempts decision_limit max_pieces max_terms subdivisions numerator_degree denominator_degree max_segments samples burn_in thin seed output qubits shots rounds levels window_size hop max_evaluations exponent axis'.split():
    DEFAULTS[name] = INTEGER
for name in 'value lower upper center start end discount constant median population_variance success_probability alpha beta tolerance radius'.split():
    DEFAULTS[name] = RATIONAL
for name in 'atol rtol initial_step rate duration mean standard_deviation proposal_scale match mismatch gap sample_rate cutoff'.split():
    DEFAULTS[name] = NUMBER
for name in 'source numerator denominator variable left right first second method model kind direction field_operation'.split():
    DEFAULTS[name] = TEXT
for name in 'coefficients rhs linear x y response weights rewards probabilities initial distribution counts'.split():
    DEFAULTS[name] = VECTOR
for name in 'matrix predictors vectors hessian constraints costs points transition'.split():
    DEFAULTS[name] = MATRIX
for name in ('intercept','sample','closed','density_matrix'):
    DEFAULTS[name] = BOOLEAN
DEFAULTS.update({'likelihood':mapping(RATIONAL),'prior':mapping(RATIONAL),
    'inputs':mapping(NUMBER),'nodes':GRAPH_NODES,'gates':GATES,
    'vertices':array(TEXT,maximum=1000),'edges':array(array(TEXT,minimum=2,maximum=2),minimum=0),
    'x_bounds':array(RATIONAL,minimum=2,maximum=2),'y_bounds':array(RATIONAL,minimum=2,maximum=2),
    'nonzero':array(TEXT,minimum=0),'shape':array(INTEGER,maximum=16),'axes':array(INTEGER,minimum=0,maximum=16),
    'targets':array(INTEGER,maximum=16),'clauses':array(array(INTEGER,maximum=32),maximum=512),
    'values':VECTOR,'parameters':record({}),'point':RATIONAL,'modulus':LARGE_INT,
    'metric':MATRIX,'coordinates':array(TEXT,maximum=4),'polynomial':array(INTEGER,maximum=13),
    'other':TENSOR,'contour':array(COMPLEX,minimum=2,maximum=1024)})
DEFAULTS.update({'sink':TEXT,'objective':VECTOR,'element':array(INTEGER,maximum=13),'mass':MATRIX,
                 'certificate':{'$ref':'#/$defs/pocklington'}})


def operation_properties(name, fields):
    missing = set(fields)-DEFAULTS.keys()
    if missing:
        raise ValueError('Operation schema fields require authored types: '+repr(sorted(missing)))
    props = {field:deepcopy(DEFAULTS[field]) for field in fields}
    def set_fields(**overrides):
        for field,schema in overrides.items():
            if field in props:
                props[field] = deepcopy(schema)
    weighted_edge = {'type':'array','prefixItems':[TEXT,TEXT,RATIONAL],'items':False,'minItems':3,'maxItems':3}
    if name in {'shortest_paths','maximum_flow','graph_bellman_ford','graph_apsp','graph_max_flow','graph_mst'}:
        set_fields(edges=array(weighted_edge,minimum=0))
    if name == 'graph_matching':
        set_fields(left=array(TEXT),right=array(TEXT))
    if name in {'rational_limit','limit'}:
        set_fields(point={'anyOf':[RATIONAL,enum('infinity','+infinity','-infinity')]})
    if name == 'evaluate':
        set_fields(values=mapping(RATIONAL))
    if name in {'ode','ode_adaptive'}:
        set_fields(initial=array(NUMBER,maximum=2),model=enum('exponential_decay','harmonic_oscillator'),method=enum('euler','rk4'))
    if name == 'distribution':
        set_fields(kind=enum('normal','exponential','poisson'),value=NUMBER,
                   parameters=record({'mean':NUMBER,'standard_deviation':NUMBER,'rate':NUMBER}))
    if name == 'time_series':
        set_fields(values=array(NUMBER),alpha=NUMBER)
    if name == 'quadratic_optimize':
        set_fields(upper=VECTOR)
    if name == 'ff_extension':
        set_fields(modulus=array(INTEGER,maximum=13),element=array(INTEGER,maximum=13))
    if name == 'prob_dirichlet':
        set_fields(alpha=VECTOR,counts=array(INTEGER))
    if name in {'prob_distribution','prob_convolution','prob_joint'}:
        width = 3 if name == 'prob_joint' else 2
        law = array(array(RATIONAL,minimum=width,maximum=width))
        set_fields(mass=law,left=law,right=law)
    if name == 'sequence_align':
        set_fields(first={'type':'string','pattern':'^[A-Za-z]+$','minLength':1,'maxLength':10000},second={'type':'string','pattern':'^[A-Za-z]+$','minLength':1,'maxLength':10000})
    if name == 'geo_distance':
        set_fields(first=PAIR,second=PAIR,radius=NUMBER)
    if name == 'tensor':
        set_fields(kind=enum('add','multiply','matmul','sum','mean','reshape','transpose'),values=TENSOR)
    if name == 'spectral':
        set_fields(kind=enum('fft','ifft','haar','inverse_haar','convolve','spectrum','lowpass','stft'),values=SAMPLES,other=SAMPLES)
    if name == 'complex_analysis':
        set_fields(kind=enum('contour','mobius'),points=array(COMPLEX),coefficients=array(COMPLEX,minimum=4,maximum=4),tolerance=NUMBER)
    if name == 'differential_geometry':
        component = {'anyOf':[RATIONAL,TEXT]}
        set_fields(metric=array(array(component,maximum=4),maximum=4),first=array(array(array(RATIONAL,maximum=4),maximum=4),maximum=4),
                   second=array(array(array(array(RATIONAL,maximum=4),maximum=4),maximum=4),maximum=4),point=mapping(component))
    if name == 'abstract_algebra':
        set_fields(kind=enum('primality','certificate','modular_power','modular_inverse','galois'),n=LARGE_INT,value=LARGE_INT,
                   modulus=LARGE_INT,exponent=LARGE_INT,left=array(INTEGER,maximum=12),right=array(INTEGER,maximum=12))
    return props


def schema_for(operation):
    from ..ops.v1_catalog import ENTRIES as V1_ENTRIES, schema as v1_schema
    if operation["name"] in V1_ENTRIES:
        return v1_schema(operation["name"])
    if operation['name']=='advanced_math':
        from ..ops.advanced_math import schema
        return schema()
    if operation['name']=='omni_superintelligence':
        from ..superintelligence.omni_engine import OmniEngine
        return OmniEngine.catalog_schema()
    from .area_tool_schemas import FIELDS,schema
    name = operation['name']
    if name in FIELDS:
        return schema(operation)
    fields = operation['required']+operation['optional']
    schema = record(operation_properties(name,fields),operation['required'])
    if name == 'tensor':
        schema['$defs'] = {'tensor_value':TENSOR}
    if name == 'abstract_algebra':
        schema['$defs'] = {'pocklington':record({'n':LARGE_INT,'factors':array(record({
            'prime':LARGE_INT,'exponent':INTEGER,'witness':LARGE_INT,'certificate':{'$ref':'#/$defs/pocklington'}},
            ('prime','exponent','witness')),maximum=32)},('n','factors'))}
        schema['properties']['certificate'] = {'$ref':'#/$defs/pocklington'}
    requirements = {
        'tensor': {'add':['other'],'multiply':['other'],'matmul':['other'],'reshape':['shape']},
        'complex_analysis': {'contour':['source','contour'],'mobius':['points','coefficients']},
        'spectral': {'convolve':['other'],'lowpass':['cutoff']},
        'abstract_algebra': {'primality':['n'],'certificate':['certificate'],
            'modular_power':['value','exponent','modulus'],'modular_inverse':['value','modulus'],
            'galois':['prime','polynomial','left']},
    }
    if name in requirements:
        schema['allOf'] = [{'if':{'properties':{'kind':{'const':kind}},'required':['kind']},
                            'then':{'required':required}} for kind,required in requirements[name].items()]
    return schema
