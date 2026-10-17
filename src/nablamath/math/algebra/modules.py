"""Finitely presented abelian groups, viewed as modules over Z."""
from .._structured import rational_matrix, sympy, data


def presentation(relations, generators=None):
    sp=sympy()
    from sympy.matrices.normalforms import smith_normal_form
    if not relations:
        if type(generators) is not int or not 0<=generators<=64: raise ValueError('Free generator count required')
        return {'free_rank':generators,'torsion':[],'smith_diagonal':[]}
    a=rational_matrix(relations)
    if any(v.q!=1 for v in a): raise ValueError('Integer relation columns required')
    if generators is not None and generators!=a.rows: raise ValueError('Relation row count must equal generator count')
    normal=smith_normal_form(a,domain=sp.ZZ)
    diagonal=[abs(int(normal[i,i])) for i in range(min(a.shape)) if normal[i,i]]
    return {'free_rank':a.rows-len(diagonal),'torsion':[v for v in diagonal if v>1],
            'smith_diagonal':diagonal,'convention':'coker(relations: Z^columns -> Z^rows)'}


def rational_homomorphism(matrix):
    a=rational_matrix(matrix)
    return {'rank':a.rank(),'kernel_basis':data(a.nullspace()),'image_basis':data(a.columnspace()),
            'cokernel_dimension':a.rows-a.rank(),'coefficient_field':'Q'}


def finite_free_resolution(relations):
    """Injective presentation over Q after replacing relations by an image basis."""
    sp=sympy();a=rational_matrix(relations);basis=a.columnspace()
    differential=sp.Matrix.hstack(*basis) if basis else sp.zeros(a.rows,0)
    return {'differential':data(differential),'degrees':[len(basis),a.rows],
            'quotient_dimension':a.rows-len(basis),'field':'Q','length':1}
