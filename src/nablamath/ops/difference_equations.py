"""Exact affine constant-coefficient recurrences, with bounded growth (39)."""
from collections import deque
from ._area_utils import vector,scalar,calculate as _calculate


def difference_equations(coefficients, initial, index, *, forcing=0):
    coefficients,initial = vector(coefficients,maximum=32),vector(initial,maximum=32)
    if len(coefficients)!=len(initial) or type(index) is not int or not 0<=index<=10000:
        raise ValueError('Recurrence order/initial values differ or index exceeds 10000')
    forcing = scalar(forcing);state = deque(initial,maxlen=len(initial))
    for _ in range(len(initial),index+1):
        value = sum(a*b for a,b in zip(coefficients,reversed(state)))+forcing
        if max(value.numerator.bit_length(),value.denominator.bit_length())>16384:
            raise ValueError('Recurrence exceeds its 16384-bit arithmetic budget')
        state.append(value)
    return {'index':index,'value':initial[index] if index<len(initial) else state[-1],
            'last_state':list(state) if index>=len(initial) else initial[:index+1],
            'order':len(initial),'arithmetic':'exact_rational',
            'convention':'a[n] = sum(c[j]*a[n-1-j]) + forcing'}


def calculate(**arguments):return _calculate('difference_equations',**arguments)
