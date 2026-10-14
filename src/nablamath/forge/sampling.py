"""Deterministic independent streams and bounded balanced sampling plans."""
import random
from ..core.semantic_ir import fingerprint


def rng_for(seed,size=3):
    if type(seed) is not int or not 0<=seed<2**63 or type(size) is not int or not 1<=size<=8:
        raise ValueError('Semente de 63 bits e tamanho de 1 a 8 requeridos')
    return random.Random(seed)


def sampling_plan(count,seed,families,sizes=(2,3,4)):
    from .task_spec import FAMILIES
    rng_for(seed)
    if type(count) is not int or not 1<=count<=1000 or not families or len(set(families))!=len(families) or any(f not in FAMILIES for f in families):
        raise ValueError('Plano de familias ou quantidade invalido')
    if not sizes or len(set(sizes))!=len(sizes) or any(type(s) is not int or not 1<=s<=8 for s in sizes):
        raise ValueError('Tamanhos invalidos')
    for index in range(count):
        family=families[index%len(families)]
        size=sizes[(index//len(families))%len(sizes)]
        derived=int(fingerprint({'seed':seed,'index':index,'family':family,'size':size})[:15],16)
        yield family,derived,size
