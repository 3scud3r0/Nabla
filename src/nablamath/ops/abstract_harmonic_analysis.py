"""Character Fourier transforms on finite products of cyclic groups (43)."""
import math
from itertools import product
from .spectral import fft,_complex
from ._area_utils import calculate as _calculate


def abstract_harmonic_analysis(group_orders, values, *, inverse=False):
    if not isinstance(group_orders,list) or not 1<=len(group_orders)<=8 or any(type(v) is not int or not 1<=v<=1024 for v in group_orders):
        raise ValueError('Require 1–8 finite cyclic factors')
    size = math.prod(group_orders)
    if size>4096 or not isinstance(values,list) or len(values)!=size or type(inverse) is not bool:
        raise ValueError('Finite group transform exceeds its 4096-element budget')
    result = [_complex(v) for v in values];original_energy = sum(abs(v)**2 for v in result)
    stride = size
    for width in group_orders:
        stride //= width
        for start in range(0,size,width*stride):
            for offset in range(stride):
                indices = [start+offset+j*stride for j in range(width)]
                transformed = fft([result[i] for i in indices],inverse=inverse)
                for i,value in zip(indices,transformed):result[i] = value
    energy = sum(abs(v)**2 for v in result)
    expected = original_energy/size if inverse else original_energy*size
    return {'values':[[v.real,v.imag] for v in result],
            'characters':[list(row) for row in product(*(range(n) for n in group_orders))],
            'parseval_residual':abs(energy-expected),'arithmetic':'floating_point',
            'convention':'Lexicographic cyclic coordinates; forward exp(-2*pi*i*sum(k_j*x_j/n_j)); inverse / group size',
            'scope':'Finite abelian groups; no arbitrary locally compact or noncommutative harmonic analysis.'}


def calculate(**arguments):return _calculate('abstract_harmonic_analysis',**arguments)


def group_fourier(table,values,representations):
    import numpy as np
    from ..math.algebra.representations import representation
    if not 1<=len(table)<=64 or len(values)!=len(table) or not representations or len(representations)>64:raise ValueError('Finite Fourier dimensions invalid')
    f=np.array([_complex(v) for v in values]);blocks=[];dimension_sum=0
    for matrices in representations:
        representation(table,matrices);rho=np.asarray(matrices,dtype=float)
        if any(np.linalg.norm(a.T@a-np.eye(len(a)))>1e-9 for a in rho):raise ValueError('Supplied rational representations must be orthogonal')
        block=sum((f[i]*rho[i].T for i in range(len(table))),np.zeros(rho[0].shape,dtype=complex))
        blocks.append([[[float(v.real),float(v.imag)] for v in row] for row in block]);dimension_sum+=rho.shape[1]**2
    return {'blocks':blocks,'sum_squared_dimensions':dimension_sum,
            'scope':'Fourier coefficients for supplied unitary representations; completeness/irreducibility are not inferred from dimension counts.'}


def group_convolution(table,left,right):
    from ..math.algebra.groups import FiniteGroup
    n=len(table)
    if not 1<=n<=64 or len(left)!=n or len(right)!=n or any(not isinstance(row,list) or len(row)!=n or any(type(v) is not int or not 0<=v<n for v in row) for row in table):raise ValueError('Finite convolution dimensions invalid')
    identity=next((e for e in range(n) if all(table[e][i]==i and table[i][e]==i for i in range(n))),None)
    if identity is None:raise ValueError('Group identity missing')
    group=FiniteGroup(tuple(range(n)),identity,{(i,j):table[i][j] for i in range(n) for j in range(n)})
    a,b=[_complex(v) for v in left],[_complex(v) for v in right]
    values=[sum(a[y]*b[table[group.inverse(y)][x]] for y in range(n)) for x in range(n)]
    return [[v.real,v.imag] for v in values]
