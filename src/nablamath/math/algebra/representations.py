"""Finite-dimensional rational representations and exact intertwiners."""
from .._structured import rational_matrix, sympy, data


def representation(table, matrices):
    sp = sympy(); n = len(table)
    if not 1 <= n <= 64 or len(matrices) != n or any(len(row) != n or any(type(i) is not int or not 0 <= i < n for i in row) for row in table):
        raise ValueError('Invalid finite multiplication table')
    from .groups import FiniteGroup
    # Validate group laws independently of the proposed representation.
    identities=[e for e in range(n) if all(table[e][i]==i and table[i][e]==i for i in range(n))]
    if len(identities)!=1:raise ValueError('Unique group identity required')
    FiniteGroup(tuple(range(n)),identities[0],{(i,j):table[i][j] for i in range(n) for j in range(n)})
    blocks = [rational_matrix(m,maximum=16) for m in matrices]; d = blocks[0].rows
    if any(m.shape != (d,d) for m in blocks): raise ValueError('Representation dimensions differ')
    if any(blocks[table[i][j]] != blocks[i]*blocks[j] for i in range(n) for j in range(n)):
        raise ValueError('Matrices do not preserve multiplication')
    if any(m.det() == 0 for m in blocks): raise ValueError('Group matrices must be invertible')
    characters = [sp.trace(m) for m in blocks]
    return {'dimension': d, 'character': data(characters), 'faithful': len({tuple(m) for m in blocks}) == n,
            'validated': True, 'scope': 'Explicit finite group representation over Q; no complex irreducibility assertion.'}


def intertwiners(left, right):
    sp = sympy()
    if not left or len(left) != len(right) or len(left)>64: raise ValueError('Paired generator matrices required')
    a=[rational_matrix(m,maximum=16) for m in left]; b=[rational_matrix(m,maximum=16) for m in right]
    n,m=a[0].rows,b[0].rows
    if any(x.shape!=(n,n) for x in a) or any(x.shape!=(m,m) for x in b): raise ValueError('Square generator matrices required')
    # Row-major vectorization of X A - B X.
    unknown=sp.Matrix(m,n,sp.symbols('u:'+str(m*n)))
    equations=[v for x,y in zip(a,b) for v in unknown*x-y*unknown]
    system,_=sp.linear_eq_to_matrix(equations,list(unknown))
    basis=[sp.Matrix(m,n,v) for v in system.nullspace()]
    return {'dimension':len(basis),'basis':data(basis)}


def character_inner_product(left, right):
    sp=sympy()
    if not left or len(left)!=len(right) or len(left)>4096: raise ValueError('Paired finite characters required')
    from ...ops._area_utils import scalar
    return sum((sp.Rational(str(scalar(a)))*sp.Rational(str(scalar(b))) for a,b in zip(left,right)),sp.Integer(0))/len(left)


def decompose_character(table,matrices,irreducibles):
    sp=sympy();target=representation(table,matrices);characters=[];dimensions=[]
    if not irreducibles or len(irreducibles)>64:raise ValueError('Explicit irreducible representations required')
    for blocks in irreducibles:
        result=representation(table,blocks);characters.append(result['character']);dimensions.append(result['dimension'])
    for i,left in enumerate(characters):
        for j,right in enumerate(characters):
            if character_inner_product(left,right)!=int(i==j):raise ValueError('Proposed characters are not an orthonormal irreducible family')
    complete=sum(d*d for d in dimensions)==len(table)
    multiplicities=[character_inner_product(target['character'],character) for character in characters]
    if any(v.is_integer is not True or v<0 for v in multiplicities):raise ValueError('Character multiplicity is not a nonnegative integer')
    return {'multiplicities':list(map(int,multiplicities)),'complete_irreducible_family':complete,
            'unresolved_dimension':target['dimension']-sum(int(m)*d for m,d in zip(multiplicities,dimensions)),
            'scope':'Exact character decomposition of validated rational matrices, regarded over C.'}
