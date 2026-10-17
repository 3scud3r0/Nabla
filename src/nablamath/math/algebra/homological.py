"""Finite rational chain complexes; exactness, chain maps, Ext/Tor over Z."""
from .._structured import rational_matrix, sympy, data
from math import gcd


def chain_complex(dimensions, differentials):
    sp=sympy()
    if not isinstance(dimensions,list) or not 1<=len(dimensions)<=16 or any(type(v) is not int or not 0<=v<=64 for v in dimensions) or len(differentials)!=len(dimensions)-1:
        raise ValueError('Invalid chain dimensions')
    ds=[]
    for i,raw in enumerate(differentials,1):
        a=rational_matrix(raw) if dimensions[i-1] and dimensions[i] else sp.zeros(dimensions[i-1],dimensions[i])
        if a.shape!=(dimensions[i-1],dimensions[i]):raise ValueError('Differential dimensions differ')
        ds.append(a)
    if any(ds[i]*ds[i+1] != sp.zeros(ds[i].rows,ds[i+1].cols) for i in range(len(ds)-1)):
        raise ValueError('Boundary squared is nonzero')
    ranks=[0]+[a.rank() for a in ds]+[0]
    betti=[n-ranks[i]-ranks[i+1] for i,n in enumerate(dimensions)]
    return {'betti_numbers':betti,'exact':all(v==0 for v in betti),'boundary_squared_zero':True}


def chain_map(source_dimensions, source_differentials, target_dimensions, target_differentials, maps):
    sp=sympy();chain_complex(source_dimensions,source_differentials);chain_complex(target_dimensions,target_differentials)
    if len(source_dimensions)!=len(target_dimensions) or len(maps)!=len(source_dimensions):raise ValueError('Chain lengths differ')
    fs=[rational_matrix(x) for x in maps]
    if any(f.shape!=(b,a) for f,a,b in zip(fs,source_dimensions,target_dimensions)):raise ValueError('Chain-map shape mismatch')
    for i in range(1,len(fs)):
        if rational_matrix(target_differentials[i-1])*fs[i]!=fs[i-1]*rational_matrix(source_differentials[i-1]):
            return {'is_chain_map':False,'failed_degree':i}
    return {'is_chain_map':True}


def cyclic_ext_tor(m,n):
    if any(type(v) is not int or not 1<=v<=10**12 for v in (m,n)):raise ValueError('Positive cyclic orders required')
    d=gcd(m,n)
    return {'tensor_order':d,'tor1_order':d,'ext1_order':d,'higher_ext_vanish':True,
            'convention':'Z/1 is the zero group; Ext^1_Z(Z/m,Z/n), Tor_1^Z(Z/m,Z/n)'}


def chain_homotopy(dimensions,differentials,left,right,homotopies):
    sp=sympy();chain_complex(dimensions,differentials);n=len(dimensions)
    if len(left)!=n or len(right)!=n or len(homotopies)!=n-1:raise ValueError('Homotopy degrees differ')
    for maps in (left,right):
        if not chain_map(dimensions,differentials,dimensions,differentials,maps)['is_chain_map']:raise ValueError('Homotopy endpoints must be chain maps')
    fs=[rational_matrix(v) for v in left];gs=[rational_matrix(v) for v in right];hs=[rational_matrix(v) for v in homotopies];ds=[rational_matrix(v) for v in differentials]
    for i,size in enumerate(dimensions):
        if fs[i].shape!=(size,size) or gs[i].shape!=(size,size):raise ValueError('Endomorphism shape mismatch')
        residual=sp.zeros(size)
        if i<n-1:
            if hs[i].shape!=(dimensions[i+1],size):raise ValueError('Homotopy raises degree by one')
            residual+=ds[i]*hs[i]
        if i>0:residual+=hs[i-1]*ds[i-1]
        if fs[i]-gs[i]!=residual:return {'chain_homotopic':False,'failed_degree':i}
    return {'chain_homotopic':True,'identity':'f-g = d*h+h*d'}
