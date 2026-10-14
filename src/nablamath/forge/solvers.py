"""Two bounded strategies per family; neither receives constructor witnesses."""
from fractions import Fraction
from itertools import product
from ..core.semantic_ir import PolynomialSpec,rational
from ..expression import to_data,evaluate,render
from ..schema.expression import from_data
from ..math.linear_algebra import Matrix,solve_linear,characteristic_polynomial
from ..math.polynomials.univariate import Polynomial
from ..math.polynomials.factorization import factor_rational


def _linear(matrix,rhs,strategy):
    matrix=Matrix(tuple(tuple(rational(v) for v in row) for row in matrix))
    rhs=tuple(rational(v) for v in rhs)
    if strategy=='alternate':
        return tuple(row[0] for row in (matrix.inverse()@Matrix(tuple((v,) for v in rhs))).rows)
    result=solve_linear(matrix,rhs)
    if result.status!='unique':
        raise ValueError('Solver requer solucao unica')
    return result.particular


def _factor(coefficients,strategy):
    polynomial=Polynomial(tuple(rational(v) for v in coefficients))
    if strategy=='exact':
        result=factor_rational(polynomial)
        if not result.complete:
            raise ValueError('Fatores racionais incompletos')
        return result.roots
    roots=[]
    for root in range(-5,6):
        while polynomial.degree>0 and polynomial(root)==0:
            polynomial,remainder=polynomial.divmod(Polynomial((-root,1)))
            roots.append(Fraction(root))
    if polynomial.degree>0:
        raise ValueError('Estrategia de grade limitada a raizes inteiras -5..5')
    return tuple(roots)


def solve_task(task,strategy='exact'):
    if strategy not in {'exact','alternate'}:
        raise ValueError('Estrategia desconhecida')
    p=task.problem;n=task.size
    if task.family=='polynomial_integral':
        if strategy=='exact':
            from ..verify.certificate import solve
            coefficients=solve(task.legacy())
        else:
            coefficients=(Fraction(),)+tuple(rational(v)/(i+1) for i,v in enumerate(p['coefficients']))
        return {'coefficients':[str(v) for v in coefficients]}
    if task.family=='linear_system':
        return {'solution':[str(v) for v in _linear(p['matrix'],p['rhs'],strategy)]}
    if task.family=='factored_polynomial':
        return {'roots':[str(v) for v in _factor(p['coefficients'],strategy)]}
    if task.family=='convex_quadratic':
        return {'solution':[str(v) for v in _linear(p['matrix'],[-rational(v) for v in p['linear']],strategy)]}
    if task.family=='stationary_markov':
        rows=[[rational(p['transition'][j][i])-int(i==j) for j in range(n)] for i in range(n)]
        rows[-1]=[Fraction(1)]*n
        rhs=[Fraction()]*(n-1)+[Fraction(1)]
        return {'stationary':[str(v) for v in _linear(rows,rhs,strategy)]}
    if task.family=='prescribed_spectrum':
        a=Matrix(tuple(tuple(rational(v) for v in row) for row in p['matrix']))
        if strategy=='exact':
            coefficients=characteristic_polynomial(a)
        else:
            # Independent determinant interpolation, not the trace recurrence.
            samples=[]
            for x in range(n+1):
                shifted=Matrix(tuple(tuple(Fraction(x)*int(i==j)-a.rows[i][j] for j in range(n)) for i in range(n)))
                samples.append(shifted.determinant())
            vandermonde=[[Fraction(x)**j for j in range(n+1)] for x in range(n+1)]
            coefficients=_linear(vandermonde,samples,'alternate')
        eigenvalues=_factor(coefficients,strategy)
        columns=[];ordered=[]
        for eigenvalue in sorted(set(eigenvalues)):
            shifted=Matrix(tuple(tuple(a.rows[i][j]-eigenvalue*int(i==j) for j in range(n)) for i in range(n)))
            basis=solve_linear(shifted,[Fraction()]*n).nullspace
            for vector in basis:
                columns.append(vector);ordered.append(eigenvalue)
        if len(columns)!=n:
            raise ValueError('Matriz nao diagonalizavel sobre racionais')
        return {'eigenvalues':[str(v) for v in ordered],
                'eigenvectors':[[str(columns[j][i]) for j in range(n)] for i in range(n)]}
    if task.family=='polynomial_identity':
        left=from_data(p['left'])
        if strategy=='exact':
            from ..math.algebra.groebner import polynomial_from_expr
            expression=polynomial_from_expr(left,tuple(p['variables'])).to_expr()
        else:
            # Polynomial identity reconstruction from degree+1 exact samples.
            from ..math.algebra.groebner import polynomial_from_expr
            if p['variables']!=['x']:
                raise ValueError('Interpolacao alternativa univariada')
            polynomial=polynomial_from_expr(left,('x',))
            degree=max((m[0] for m,_ in polynomial.terms),default=0)
            vandermonde=[[Fraction(x)**j for j in range(degree+1)] for x in range(degree+1)]
            samples=[evaluate(left,{'x':Fraction(x)}) for x in range(degree+1)]
            coefficients=_linear(vandermonde,samples,'alternate')
            expression=PolynomialSpec(tuple(coefficients)).to_expr()
        return {'expression':to_data(expression)}
    if task.family=='counterexample':
        left,right=from_data(p['left']),from_data(p['right'])
        if strategy=='exact':
            from ..falsifier import search_equivalence
            result=search_equivalence(render(left),render(right),radius=p['radius'],budget=100000)
            if result.status!='counterexample':
                raise ValueError('Sem contraexemplo no orcamento')
            return {'assignment':{name:str(value) for name,value in result.witness}}
        for values in product(range(p['radius'],-p['radius']-1,-1),repeat=len(p['variables'])):
            mapping={name:Fraction(value) for name,value in zip(p['variables'],values)}
            if evaluate(left,mapping)!=evaluate(right,mapping):
                return {'assignment':{name:str(v) for name,v in mapping.items()}}
        raise ValueError('Sem contraexemplo no dominio')
    raise ValueError('Familia nao suportada')
