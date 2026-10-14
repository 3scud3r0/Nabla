"""Rational Householder eigenbasis, prescribed real eigenvalues and symmetric reconstruction."""
from fractions import Fraction
from ..sampling import rng_for
from ..task_spec import TaskSpec


def construct(seed,size=3):
    rng=rng_for(seed,size)
    vector=[Fraction(rng.choice((-3,-2,-1,1,2,3))) for _ in range(size)]
    norm=sum(v*v for v in vector)
    q=[[Fraction(i==j)-2*vector[i]*vector[j]/norm for j in range(size)] for i in range(size)]
    eigenvalues=sorted(rng.randint(-5,5) for _ in range(size))
    matrix=[[sum(q[i][k]*eigenvalues[k]*q[j][k] for k in range(size)) for j in range(size)] for i in range(size)]
    return TaskSpec('prescribed_spectrum',{'matrix':[[str(v) for v in row] for row in matrix]},size),{
        'eigenvalues':[str(v) for v in eigenvalues],'eigenvectors':[[str(v) for v in row] for row in q]}
