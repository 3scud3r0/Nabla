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
