"""Finite exact sign tests and distribution-free bounds with explicit assumptions."""
from fractions import Fraction
from math import comb
from .descriptive import mean


def sign_test(values,median=0):
    values=tuple(Fraction(v) for v in values)
    if not 1<=len(values)<=4096:
        raise ValueError('Teste limitado a 4096 observacoes')
    median=Fraction(median)
    positive=sum(v>median for v in values);negative=sum(v<median for v in values)
    n=positive+negative
    tail=sum(comb(n,k) for k in range(min(positive,negative)+1))
    return {'positive':positive,'negative':negative,'ties':len(values)-n,
            'p_value':min(Fraction(1),Fraction(2*tail,2**n)) if n else Fraction(1),
            'null':'independent equiprobable nonzero signs; ties omitted'}


def mean_confidence_bound(values,population_variance,radius):
    values=tuple(Fraction(v) for v in values)
    variance=Fraction(population_variance);radius=Fraction(radius)
    if not 1<=len(values)<=10000 or variance<0 or radius<=0:
        raise ValueError('Amostra, variancia ou raio invalido')
    center=mean(values)
    confidence=max(Fraction(),1-variance/(len(values)*radius**2))
    return {'interval':(center-radius,center+radius),'confidence_at_least':confidence,
            'method':'Chebyshev for sample mean','assumptions':'independent identically distributed observations; supplied population variance is known'}


def exact_moving_average(values,window):
    values=tuple(Fraction(v) for v in values)
    if len(values)>10000 or type(window) is not int or not 1<=window<=len(values):
        raise ValueError('Janela fora do limite')
    return tuple(sum(values[i:i+window],Fraction())/window for i in range(len(values)-window+1))
