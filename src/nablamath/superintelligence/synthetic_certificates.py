"""Small reference checks independent of the producing solver's algorithm.

Checks use Python integer/Fraction arithmetic, never the solver under test.
Their stated claims are narrower than complete validation of a result object.
"""
from fractions import Fraction as F
from itertools import permutations, combinations
import math


def _matrix(a):
    return [[F(v) for v in row] for row in a]


def _dot(a,b):
    return sum((x*y for x,y in zip(a,b,strict=True)),F())


def _det(a):
    n = len(a)
    return sum(((-1)**sum(p[i]>p[j] for i in range(n) for j in range(i+1,n))
                *math.prod(a[i][p[i]] for i in range(n)) for p in permutations(range(n))),F())


def reference_certificate(operation,a,r):
    """Return None where no independent reference is authored; fail on disagreement."""
    residuals,claims = [],[]
    if operation == 'solve_linear' and r['status'] == 'unique':
        x = list(map(F,r['particular']))
        residuals = [_dot(row,x)-F(v) for row,v in zip(_matrix(a['matrix']),a['rhs'],strict=True)]
        claims = ['Ax=b por substituição; a unicidade não é certificada por este teste.']
    elif operation == 'matrix_inverse':
        x,y = _matrix(a['matrix']),_matrix(r['inverse']);n=len(x)
        for left,right in ((x,y),(y,x)):
            residuals += [sum(left[i][k]*right[k][j] for k in range(n))-int(i==j) for i in range(n) for j in range(n)]
        claims = ['AX=XA=I por produto direto racional.']
    elif operation == 'matrix_properties' and len(a['matrix']) <= 5:
        residuals = [_det(_matrix(a['matrix']))-F(r['determinant'])]
        claims = ['Determinante por fórmula de Leibniz; posto e polinômio característico não checados aqui.']
    elif operation == 'least_squares':
        x = [[F(1)]+list(map(F,row)) if a.get('intercept',True) else list(map(F,row)) for row in a['predictors']]
        c = list(map(F,r['coefficients']));y=list(map(F,a['response']))
        e = [v-_dot(row,c) for row,v in zip(x,y,strict=True)]
        w = list(map(F,a.get('weights',[1]*len(x))))
        residuals = [sum(w[i]*x[i][j]*e[i] for i in range(len(x))) for j in range(len(c))]
        residuals += [F(r['residual_sum_squares'])-sum(v*z*z for v,z in zip(w,e,strict=True))]
        claims = ['Equações normais ponderadas e soma de quadrados por produto direto.']
    elif operation == 'linear_regression':
        x,y = list(map(F,a['x'])),list(map(F,a['y']))
        e = [v-F(r['intercept'])-F(r['slope'])*u for u,v in zip(x,y,strict=True)]
        residuals = [sum(e),_dot(x,e),sum(v*v for v in e)-F(r['residual_sum_squares'])]
        claims = ['Resíduos ortogonais a 1 e x; soma de quadrados.']
    elif operation == 'nt_factorization':
        factors = r['factors'];n=a['n'];value=math.prod(p**k for p,k in factors)
        if any(p<2 or k<1 or any(p%d==0 for d in range(2,math.isqrt(p)+1)) for p,k in factors):
            raise ArithmeticError('Fator não primo no certificado')
        phi = n
        for p,k in factors:phi=phi//p*(p-1)
        residuals = [F(value-n),F(phi-r['totient'])]
        claims = ['Reconstrução, primalidade dos fatores por divisão e fórmula de Euler.']
    elif operation == 'nt_modular_roots':
        expected = [x for x in range(a['prime']) if x*x%a['prime']==a['a']%a['prime']]
        if r['roots'] != expected:raise ArithmeticError('Raízes modulares divergentes')
        residuals = [F(0)];claims=['Conjunto completo de raízes por enumeração independente do corpo pequeno.']
    elif operation == 'nt_discrete_log':
        expected = next((k for k in range(a['prime']) if pow(a['base'],k,a['prime'])==a['target']%a['prime']),None)
        if r['exponent'] != expected:raise ArithmeticError('Logaritmo discreto divergente')
        residuals=[F(0)];claims=['Expoente mínimo por enumeração independente no corpo pequeno.']
    elif operation == 'nt_pell':
        residuals=[F(int(r['x'])**2-a['d']*int(r['y'])**2-1)]
        claims=['Identidade de Pell; minimalidade não checada por este certificado.']
    elif operation == 'graph_assignment':
        cost = _matrix(a['costs']);n=len(cost)
        assignment=r['assignment']
        if sorted(assignment)!=list(range(n)):raise ArithmeticError('Atribuição inviável')
        minimum=min(sum(cost[i][p[i]] for i in range(n)) for p in permutations(range(n)))
        residuals=[minimum-F(r['minimum_cost']),sum(cost[i][assignment[i]] for i in range(n))-minimum]
        claims=['Ótimo por enumeração de permutações, independente do DP.']
    elif operation == 'graph_max_flow':
        interior=[v for v in a['vertices'] if v not in (a['source'],a['sink'])]
        cuts=[]
        for mask in range(2**len(interior)):
            side={a['source']}|{v for i,v in enumerate(interior) if mask>>i&1}
            cuts.append(sum((F(w) for u,v,w in a['edges'] if u in side and v not in side),F()))
        residuals=[min(cuts)-F(r['value']),F(r['cut_capacity'])-F(r['value'])]
        claims=['Valor ótimo por enumeração de todos os cortes; não valida fluxo ausente do resultado.']
    elif operation == 'graph_matching':
        pairs=r['pairs'];edges={tuple(e) for e in a['edges']}
        cover=set(r['minimum_vertex_cover']['left'])|set(r['minimum_vertex_cover']['right'])
        if (any(tuple(p) not in edges for p in pairs) or len({p[0] for p in pairs})!=len(pairs)
            or len({p[1] for p in pairs})!=len(pairs) or any(u not in cover and v not in cover for u,v in edges)):
            raise ArithmeticError('Matching ou cobertura inviável')
        residuals=[F(len(pairs)-len(cover)),F(len(pairs)-r['cardinality'])]
        claims=['Matching e cobertura viáveis com cardinalidades iguais: certificado primal-dual.']
    elif operation == 'prob_dirichlet':
        posterior=[F(x)+F(y) for x,y in zip(a['alpha'],a['counts'],strict=True)]
        expected=[x/sum(posterior) for x in posterior]
        residuals=[F(v)-e for v,e in zip(r['predictive'],expected,strict=True)]
        claims=['Preditiva conjugada por normalização independente.']
    elif operation == 'bayes':
        weights={k:F(v)*F(a['likelihood'][k]) for k,v in a['prior'].items()}
        z=sum(weights.values())
        residuals=[F(r['evidence'])-z]+[F(r['posterior'][k])-v/z for k,v in weights.items()]
        claims=['Evidência e posterior calculadas diretamente.']
    elif operation == 'markov_rewards':
        transition=_matrix(a['transition']);x=list(map(F,r['values']));discount=F(a['discount'])
        residuals=[x[i]-discount*_dot(row,x)-F(a['rewards'][i]) for i,row in enumerate(transition)]
        claims=['Resíduo de Bellman exato por substituição.']
    elif operation == 'markov_stationary':
        transition=_matrix(a['transition']);n=len(transition)
        for item in r['closed_classes']:
            pi=list(map(F,item['distribution']))
            if any(x<0 for x in pi):raise ArithmeticError('Probabilidade negativa')
            residuals += [sum(pi)-1]+[sum(pi[i]*transition[i][j] for i in range(n))-pi[j] for j in range(n)]
        claims=['Cada distribuição listada é não negativa, normalizada e estacionária; exaustividade não checada aqui.']
    elif operation == 'potential_theory':
        x=list(map(F,r['values']));g=_matrix(a['conductance'])
        boundary={int(k):F(v) for k,v in a['boundary'].items()}
        residuals=[x[i]-v for i,v in boundary.items()]
        residuals += [sum(g[i][j]*(x[i]-x[j]) for j in range(len(x))) for i in range(len(x)) if i not in boundary]
        claims=['Valores de contorno e lei de Kirchhoff por substituição.']
    elif operation == 'functional_analysis':
        basis=_matrix(a['basis']);target=list(map(F,a['target']));x=list(map(F,r['projection']))
        e=[v-w for v,w in zip(target,x,strict=True)];weights=list(map(F,a.get('weights',[1]*len(x))))
        residuals=[sum(w*v*z for w,v,z in zip(weights,row,e,strict=True)) for row in basis]
        residuals += [sum(w*(u*u-v*v-z*z) for w,u,v,z in zip(weights,target,x,e,strict=True))]
        claims=['Ortogonalidade ponderada e Pitágoras, não completude em espaço infinito.']
    elif operation == 'measure_theory':
        w,v=list(map(F,a['weights'])),list(map(F,a['values']));labels=a['partition']
        expected=[]
        for label in labels:
            denominator=sum(weight for weight,k in zip(w,labels,strict=True) if k==label)
            expected.append(sum(weight*x for weight,x,k in zip(w,v,labels,strict=True) if k==label)/denominator if denominator else F())
        residuals=[F(x)-y for x,y in zip(r['conditional_expectation'],expected,strict=True)]
        residuals += [F(r['integral'])-_dot(w,v),_dot(w,expected)-_dot(w,v)]
        claims=['Esperanças condicionais por bloco e igualdade das integrais.']
    elif operation == 'integral_transforms' and a['kind']=='laplace_polynomial':
        s=F(a['parameter'])
        expected=sum(F(v)*math.factorial(k)/s**(k+1) for k,v in enumerate(a['values']))
        residuals=[F(r['value'])-expected];claims=['Identidade de momentos fatoriais em Re(s)>0.']
    else:
        return None
    if not claims or not residuals or any(x != 0 for x in residuals):
        raise ArithmeticError('Certificado de referência recusado: '+operation)
    return {'kind':'reference_check','independent_of_producing_solver':True,
            'arithmetic':'python_int_fraction','claims':claims,'residuals':[str(x) for x in residuals],
            'scope':'Apenas as afirmações listadas; não revisão independente nem prova formal de toda a trajetória.'}
