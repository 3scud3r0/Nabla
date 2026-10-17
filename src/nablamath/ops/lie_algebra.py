"""Finite-dimensional rational Lie algebras, Jacobi, center and Killing form (17)."""
from fractions import Fraction
from ._area_utils import vector,nullspace,rref,calculate as _calculate
from ..math.linear_algebra.matrices import Matrix


def lie_algebra(structure, *, left=None, right=None):
    if not isinstance(structure,list) or not 1<=len(structure)<=6:
        raise ValueError('Lie dimension must be 1–6')
    n = len(structure)
    if any(not isinstance(layer,list) or len(layer)!=n for layer in structure):raise ValueError('Invalid structure constants')
    c = [[vector(row,maximum=n) for row in layer] for layer in structure]
    if any(len(row)!=n for layer in c for row in layer):raise ValueError('Invalid structure constants')
    if any(c[i][j][k]!=-c[j][i][k] for i in range(n) for j in range(n) for k in range(n)):
        raise ValueError('Bracket must be antisymmetric')
    for i in range(n):
        for j in range(n):
            for k in range(n):
                for out in range(n):
                    value = sum(c[j][k][m]*c[i][m][out]+c[k][i][m]*c[j][m][out]+c[i][j][m]*c[k][m][out] for m in range(n))
                    if value:raise ValueError('Structure constants violate Jacobi')
    killing = [[sum(c[i][b][a]*c[j][a][b] for a in range(n) for b in range(n)) for j in range(n)] for i in range(n)]
    central_constraints = [[c[i][j][k] for i in range(n)] for j in range(n) for k in range(n)]
    derived_columns = [[c[i][j][k] for i in range(n) for j in range(n)] for k in range(n)]
    result = {'dimension':n,'jacobi_verified':True,'killing_form':killing,
              'center_basis':nullspace(central_constraints,n),'derived_dimension':len(rref(derived_columns)[1]),
              'semisimple_over_characteristic_zero':bool(Matrix(tuple(tuple(row) for row in killing)).determinant())}
    if (left is None)!=(right is None):raise ValueError('Bracket requires both vectors')
    if left is not None:
        a,b = vector(left,maximum=n),vector(right,maximum=n)
        if len(a)!=n or len(b)!=n:raise ValueError('Bracket vector dimensions differ')
        result['bracket'] = [sum((a[i]*b[j]*c[i][j][k] for i in range(n) for j in range(n)),Fraction(0)) for k in range(n)]
    return result


def calculate(**arguments):return _calculate('lie_algebra',**arguments)


def lie_structure(structure,representation=None):
    from ..math._structured import sympy,rational_matrix,data
    sp=sympy();base=lie_algebra(structure);n=len(structure)
    c=[[[sp.Rational(str(v)) for v in row] for row in layer] for layer in structure]
    unit=[sp.eye(n)[:,i] for i in range(n)]
    def bracket(a,b):return sp.Matrix([sum(a[i]*b[j]*c[i][j][k] for i in range(n) for j in range(n)) for k in range(n)])
    def span(vectors):return sp.Matrix.hstack(*vectors).columnspace() if vectors else []
    def series(lower):
        values=unit;dimensions=[n]
        for _ in range(n+1):
            new=span([bracket(a,b) for a in (unit if lower else values) for b in values])
            dimensions.append(len(new))
            if not new or len(new)==len(values):break
            values=new
        return dimensions
    derived=span([bracket(a,b) for a in unit for b in unit]);killing=sp.Matrix(base['killing_form'])
    radical=sp.Matrix.vstack(*(v.T*killing for v in derived)).nullspace() if derived else unit
    result={**base,'derived_series_dimensions':series(False),'lower_central_dimensions':series(True),
            'solvable_radical_basis':data(radical),'solvable':series(False)[-1]==0,'nilpotent':series(True)[-1]==0,
            'adjoint_representation':data([sp.Matrix([[c[i][j][k] for j in range(n)] for k in range(n)]) for i in range(n)])}
    if representation is not None:
        blocks=[rational_matrix(m,maximum=16) for m in representation]
        if len(blocks)!=n or any(m.shape!=blocks[0].shape or m.rows!=m.cols for m in blocks):raise ValueError('One square representation matrix per Lie basis vector required')
        valid=all(blocks[i]*blocks[j]-blocks[j]*blocks[i]==sum((c[i][j][k]*blocks[k] for k in range(n)),sp.zeros(blocks[0].rows)) for i in range(n) for j in range(n))
        result['representation_valid']=valid
    return result


def lie_decomposition(structure):
    """Solvable/nilpotent radicals and a checked Levi complement, n<=6."""
    from ..math._structured import sympy,data
    sp=sympy();base=lie_structure(structure);n=len(structure);unit=[sp.eye(n)[:,i] for i in range(n)]
    c=[[[sp.Rational(str(v)) for v in row] for row in layer] for layer in structure]
    def bracket(a,b):return sp.Matrix([sum(a[i]*b[j]*c[i][j][k] for i in range(n) for j in range(n)) for k in range(n)])
    derived=sp.Matrix.hstack(*(bracket(a,b) for a in unit for b in unit)).columnspace()
    killing=sp.Matrix(base['killing_form']);radical=sp.Matrix.vstack(*(v.T*killing for v in derived)).nullspace() if derived else unit
    r=len(radical);parameters=sp.symbols('u:'+str(r));ad=[sp.Matrix.hstack(*(bracket(v,e) for e in unit)) for v in radical]
    generic=sum((u*a for u,a in zip(parameters,ad)),sp.zeros(n));weights=[]
    if parameters:
        for eigenvalue in generic.eigenvals():
            polynomial=sp.Poly(sp.expand(eigenvalue),*parameters,extension=True)
            if polynomial.total_degree()>1 or polynomial.TC()!=0:raise ArithmeticError('Backend did not resolve linear radical weights')
            weights.append([sp.diff(eigenvalue,u) for u in parameters])
    kernel=sp.Matrix(weights).nullspace() if weights else [sp.eye(r)[:,i] for i in range(r)]
    nilradical=[sp.Matrix.hstack(*radical)*v for v in kernel] if radical else []
    full=list(radical);complement=[]
    for e in unit:
        if not full or sp.Matrix.hstack(*(full+[e])).rank()>len(full):full.append(e);complement.append(e)
    levi=[]
    if complement:
        basis=sp.Matrix.hstack(*(radical+complement));inverse=basis.inv();q=len(complement)
        if not radical:levi=complement
        else:
            unknown=sp.symbols('a:'+str(r*q));candidate=[complement[i]+sum((unknown[i*r+j]*radical[j] for j in range(r)),sp.zeros(n,1)) for i in range(q)]
            equations=[]
            for i in range(q):
                for j in range(i):
                    quotient=(inverse*bracket(complement[i],complement[j]))[r:,:]
                    residual=bracket(candidate[i],candidate[j])-sum((quotient[k]*candidate[k] for k in range(q)),sp.zeros(n,1));equations.extend(residual)
            solutions=sp.solve(equations,unknown,dict=True)
            if not solutions:raise ArithmeticError('Levi complement solver did not produce a witness')
            solution=solutions[0];free=set(unknown)-set(solution);solution={k:sp.simplify(v.subs({u:0 for u in free})) for k,v in solution.items()};solution.update({u:0 for u in free})
            levi=[v.subs(solution) for v in candidate]
            if any(e.subs(solution)!=0 for e in equations):raise ArithmeticError('Levi witness failed exact bracket verification')
    return {**base,'nilpotent_radical_basis':data(nilradical),'levi_basis':data(levi),
            'scope':'Finite rational Lie algebra; symbolic weight/complement algorithms must produce exact witnesses or raise explicitly.'}


def pbw_reduce(structure,word):
    from fractions import Fraction
    lie_algebra(structure);n=len(structure)
    if not isinstance(word,list) or len(word)>10 or any(type(i) is not int or not 0<=i<n for i in word):raise ValueError('PBW word budget exceeded')
    pending={tuple(word):Fraction(1)};ordered={};iterations=0
    while pending:
        term,coefficient=pending.popitem();iterations+=1
        if iterations>100000 or len(pending)+len(ordered)>4096:raise ValueError('PBW expansion budget exceeded')
        i=next((k for k in range(len(term)-1) if term[k]>term[k+1]),None)
        if i is None:ordered[term]=ordered.get(term,0)+coefficient;continue
        a,b=term[i:i+2];swapped=term[:i]+(b,a)+term[i+2:];pending[swapped]=pending.get(swapped,0)+coefficient
        for k in range(n):
            key=term[:i]+(k,)+term[i+2:];pending[key]=pending.get(key,0)+coefficient*Fraction(structure[a][b][k])
        pending={k:v for k,v in pending.items() if v}
    return {'terms':[{'word':list(word),'coefficient':str(value)} for word,value in sorted(ordered.items()) if value],
            'scope':'PBW normal form in the universal enveloping algebra of the supplied verified Lie algebra.'}


def root_system(cartan):
    from ..math._structured import rational_matrix,sympy
    sp=sympy();a=rational_matrix(cartan,maximum=4);n=a.rows
    if a.cols!=n or any(a[i,i]!=2 for i in range(n)) or any(v.q!=1 or abs(v)>4 for v in a) or any(a[i,j]>0 or (a[i,j]==0)!=(a[j,i]==0) for i in range(n) for j in range(n) if i!=j):raise ValueError('Crystallographic Cartan matrix required')
    roots={tuple(int(i==j) for i in range(n)) for j in range(n)};pending=list(roots)
    while pending:
        root=pending.pop()
        for i in range(n):
            reflected=list(root);reflected[i]-=sum(int(a[i,j])*root[j] for j in range(n));v=tuple(reflected)
            if v not in roots:
                roots.add(v);pending.append(v)
                if len(roots)>4096:raise ValueError('Root closure is not finite within the declared budget')
    return {'roots':[list(v) for v in sorted(roots)],'positive_roots':[list(v) for v in sorted(roots) if all(x>=0 for x in v)],'rank':n}
