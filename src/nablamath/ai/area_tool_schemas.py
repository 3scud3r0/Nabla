"""Closed nested argument schemas for the added MSC computational profiles."""
from .tool_schemas import RATIONAL,NUMBER,INTEGER,BOOLEAN,TEXT,VECTOR,MATRIX,PAIR,COMPLEX,array,record,mapping,enum

NAMES = array({'type':'string','pattern':'^[A-Za-z][A-Za-z0-9_]*$','maxLength':64},maximum=4)
COMPLEX_EXACT = {'anyOf':[RATIONAL,array(RATIONAL,minimum=2,maximum=2)]}
FIELDS = {
 'order_theory':{'relation':array(array(BOOLEAN,maximum=64),maximum=64)},
 'universal_algebra':{'tables':array(array(array(INTEGER,maximum=16),maximum=16),maximum=4),'generators':array(INTEGER,maximum=16),'partition':array(INTEGER,maximum=16)},
 'algebraic_geometry':{'equations':array(TEXT,maximum=32),'variables':NAMES,'point':array(RATIONAL,maximum=4)},
 'lie_algebra':{'structure':array(array(array(RATIONAL,maximum=6),maximum=6),maximum=6),'left':array(RATIONAL,maximum=6),'right':array(RATIONAL,maximum=6)},
 'k_theory':{'adjacency':array(array(INTEGER,maximum=6),maximum=6)},
 'measure_theory':{'weights':VECTOR,'values':VECTOR,'partition':array(INTEGER)},
 'lie_groups':{'rotation_vector':array(NUMBER,minimum=3,maximum=3)},
 'potential_theory':{'conductance':MATRIX,'boundary':mapping(RATIONAL)},
 'special_functions':{'kind':enum('gamma','logabs_gamma','erf','erfc','beta','bessel_j','legendre','airy_ai'),'x':NUMBER,'y':NUMBER,'order':INTEGER},
 'difference_equations':{'coefficients':array(RATIONAL,maximum=32),'initial':array(RATIONAL,maximum=32),'index':INTEGER,'forcing':RATIONAL},
 'approximation_theory':{'nodes':array(RATIONAL,maximum=64),'values':array(RATIONAL,maximum=64),'points':array(RATIONAL,maximum=512)},
 'integral_transforms':{'kind':enum('laplace_polynomial','mellin_unit_polynomial','z_finite'),'values':array(RATIONAL,maximum=64),'parameter':RATIONAL},
 'integral_equations':{'kernel':array(array(RATIONAL,maximum=12),maximum=12),'rhs':array(RATIONAL,maximum=12),'lower':RATIONAL,'upper':RATIONAL,'coupling':RATIONAL},
 'several_complex_variables':{'sources':array(TEXT,maximum=4),'variables':NAMES,'point':array(COMPLEX_EXACT,maximum=4)},
 'abstract_harmonic_analysis':{'group_orders':array(INTEGER,maximum=8),'values':array(COMPLEX,maximum=4096),'inverse':BOOLEAN},
 'functional_analysis':{'basis':MATRIX,'target':VECTOR,'weights':VECTOR},
 'operator_theory':{'matrix':MATRIX,'parameter':RATIONAL},
 'variational_calculus':{'lagrangian':TEXT},
 'manifold_topology':{'facets':array(array(INTEGER,minimum=3,maximum=3),maximum=128)},
 'global_analysis':{'facets':array(array(INTEGER,maximum=4),maximum=64),'degree':INTEGER,'form':array(RATIONAL,minimum=0,maximum=32)},
 'statistical_mechanics':{'energies':array(NUMBER,maximum=4096),'temperature':NUMBER,'boltzmann':NUMBER,'degeneracies':array(INTEGER,maximum=4096)},
 'geophysics':{'kind':enum('vertical_seismic','bouguer_slab'),'thicknesses':array(NUMBER,maximum=1024),'velocities':array(NUMBER,maximum=1024),'densities':array(NUMBER,maximum=1024),'density':NUMBER,'height':NUMBER},
}


def schema(operation):
    name = operation['name']
    result = record(FIELDS[name],operation['required'])
    if set(FIELDS[name])!=set(operation['required']+operation['optional']):
        raise ValueError('MSC tool schema differs from the public operation contract')
    if name=='geophysics':
        result['allOf'] = [{'if':{'properties':{'kind':{'const':kind}},'required':['kind']},'then':{'required':fields}}
                           for kind,fields in [('vertical_seismic',['thicknesses','velocities']),('bouguer_slab',['density','height'])]]
    if name=='special_functions':
        result['allOf'] = [{'if':{'properties':{'kind':{'const':'beta'}},'required':['kind']},'then':{'required':['y']}}]
    return result
