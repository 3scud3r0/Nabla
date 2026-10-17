"""Hereditarily finite sets and explicit axiom-instance records.

This module does not decide consistency of ZFC or identify finite checks with
the infinite axioms. Separation is a finite executable construction only.
"""
from ..logic.proof_theory import check_proof


def decode(value,depth=0):
    if depth>16 or not isinstance(value,list) or len(value)>256:raise ValueError('Hereditary finite set budget exceeded')
    result=frozenset(decode(v,depth+1) for v in value)
    return result


def encode(value):
    return sorted((encode(v) for v in value),key=repr)


def finite_set_operations(left,right):
    a,b=decode(left),decode(right)
    return {'equal':a==b,'member':a in b,'subset':a<=b,'union':encode(a|b),'intersection':encode(a&b),
            'pair':encode(frozenset((a,b))),'union_of_left':encode(frozenset().union(*a)),
            'extensionality_verified':(a==b)==all((v in a)==(v in b) for v in a|b)}


def axiom_instance(name,parameters):
    if name not in {'extensionality','empty','pairing','union','foundation'}:raise ValueError('Unsupported finite axiom instance')
    if not isinstance(parameters,list) or not parameters or len(parameters)>2:raise ValueError('One or two finite sets required')
    sets=[decode(v) for v in parameters];a=sets[0]
    if name=='empty':witness=frozenset()
    elif name=='pairing':
        if len(sets)!=2:raise ValueError('Pairing needs two sets')
        witness=frozenset(sets)
    elif name=='union':witness=frozenset().union(*a)
    elif name=='foundation':witness=next((v for v in a if not(v&a)),None)
    else:
        if len(sets)!=2:raise ValueError('Extensionality needs two sets')
        return {'instance_holds':(a==sets[1])==all((v in a)==(v in sets[1]) for v in a|sets[1]),'scope':'Hereditary finite sets only'}
    return {'witness':encode(witness) if witness is not None else None,'instance_holds':True,
            'scope':'Hereditary finite sets; infinity, replacement and ZFC consistency are not established.'}


def verify_derivation(proof,axioms,conclusion):
    result=check_proof(proof,assumptions=axioms,expected=conclusion)
    return {**result,'axioms_are_assumptions':True,'set_theoretic_axioms_authenticated':False}
