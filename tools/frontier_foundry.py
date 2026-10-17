#!/usr/bin/env python3
"""Nabla Frontier Foundry v3: compositional inverse mathematical synthesis.

Ten construction grammars; exact solution certificates checked using independent
algorithms. No private model reasoning, universal formal proofs or training-data
provenance claims. Requires SymPy; native Nabla receipts are the default.
"""
from __future__ import annotations
import argparse
import copy
from fractions import Fraction
import hashlib
import itertools
import json
import math
import random
from pathlib import Path
import sys

import sympy as sp

VERSION = 3
MAX_COUNT = 100
NAMES = ('POLYNOMIAL_IDEAL_OBFUSCATION', 'POTENTIAL_RECONSTRUCTION',
         'LIE_REPRESENTATION_CONJUGACY', 'STOCHASTIC_INVARIANT_MEASURE',
         'CONFORMAL_CURVATURE', 'FINITE_FIELD_FIELD_INVARIANTS',
         'KIRCHHOFF_NETWORK', 'SYNDROME_DECODING',
         'DISCRETE_LYAPUNOV', 'RATIONAL_WALK_GENERATING_FUNCTION')


def canonical(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False)


def digest(v):
    return hashlib.sha256(canonical(v).encode('utf-8')).hexdigest()


def require(condition, explanation):
    """Fail closed also under `python -O` (unlike Python assert statements)."""
    if not condition:
        raise ArithmeticError(explanation)


def q(value):
    return str(sp.Rational(value))


def matrix_data(A):
    return [[q(e) for e in row] for row in A.tolist()]


def poly_terms(poly, variables, modulus=None):
    p = sp.Poly(poly, *variables, modulus=modulus) if modulus else sp.Poly(poly, *variables, domain=sp.QQ)
    return [[str(int(c) % modulus if modulus else sp.Rational(c)), list(exp)] for exp, c in p.terms()]


def portable_receipt(operation, inputs, result, *, metadata=None, parents=(), backend='python'):
    body = dict(schema_version=1, kind='execution_observation', operation=operation,
                inputs=inputs, result=result, backend=backend, metadata=metadata or {},
                parents=list(parents), formal_proof=False, replayable=False)
    return {**json.loads(canonical(body)), 'content_id': digest(body)}


def portable_verify(r):
    try:
        return r == portable_receipt(r['operation'], r['inputs'], r['result'],
                                     metadata=r['metadata'], parents=r['parents'], backend=r['backend'])
    except (ValueError, TypeError, KeyError):
        return False


def backend(native):
    if not native:
        return portable_receipt, portable_verify, 'portable_reference_contract'
    from nablamath.calc.receipt import receipt, verify_receipt, fingerprint, canonical as nabla_canonical
    if fingerprint({'test': [1, 'á']}) != digest({'test': [1, 'á']}) or nabla_canonical({'b': 2, 'a': 1}) != canonical({'b': 2, 'a': 1}):
        raise RuntimeError('Canonicalization mismatch with installed Nabla')
    from nablamath.calc.session import CalculationSession
    r = CalculationSession().execute('binomial', n=9, k=3).to_data()
    if not verify_receipt(r):
        raise RuntimeError('Nabla CalculationSession smoke receipt did not replay')
    return receipt, verify_receipt, 'native_nablamath'


def polynomial_ideal(j, rng):
    p = (101, 103, 107)[j % 3]
    degree = 3 + j % 4
    x, y, z = sp.symbols('x y z')
    a, b, c, d, e = [rng.randint(1, 9) for _ in range(5)]
    t = rng.randint(2, p-1)
    h2 = d*z**2 + e*z + 1
    h1 = a*z**(2+j%2) + b*z+c
    base = [x-h1, y-h2, z**degree-t]
    u, v, w = [rng.randint(1, 4) for _ in range(3)]
    mixed = [sp.expand(base[0]+u*z*base[1]+v*base[2]),
             sp.expand(base[1]+w*z**(1+j%2)*base[2]), base[2]]
    rng.shuffle(mixed)
    G = sp.groebner(mixed, x, y, z, modulus=p, order='lex')
    expected = sp.groebner(base, x, y, z, modulus=p, order='lex')
    # Two-sided ideal membership, plus independent Buchberger basis construction.
    for g in mixed:
        require(expected.reduce(g)[1] == 0, "Invariant verification failed at check 103")
    for g in base:
        require(G.reduce(g)[1] == 0, "Invariant verification failed at check 105")
    require({tuple(v.LM(order='lex').exponents) for v in G.polys} == {(1,0,0),(0,1,0),(0,0,degree)}, "Invariant verification failed at check 106")
    roots = [r for r in range(p) if pow(r, degree, p) == t]
    answer = {'reduced_basis': [poly_terms(g.as_expr(), (x,y,z), p) for g in G.polys],
              'quotient_dimension': degree, 'rational_point_count': len(roots), 'rational_z_roots': roots}
    problem = (f'Em F_{p}[x,y,z], ordem lex x>y>z, o ideal I é gerado por '
               f'F={list(map(str,mixed))}. Recupere a base reduzida de Gröbner, '
               'dim_Fp(R/I), e todos os valores de z de seus pontos Fp-racionais.')
    steps = ['Aplicar reduções de Buchberger aos três geradores mascarados (a mistura não altera o ideal).',
             'Normalizar o conjunto reduzido na ordem lex x>y>z e conferir os S-polinômios.',
             'A dimensão do quociente é o número de monômios padrão, não a contagem de pontos Fp.',
             'Enumerar as raízes do eliminante em Fp e recuperar x,y por substituição.']
    structure = ['finite_field', 'triangular_witness', 'polynomial_unimodular_mixing',
                 'buchberger_reduction', 'quotient_dimension', 'rational_locus']
    return {'p':p,'degree':degree,'generators':[str(t) for t in mixed]},problem,answer,steps,structure,{'buchberger_two_way': True, 'point_enumeration': True}


def potential_recovery(j, rng):
    x,y,z,t=sp.symbols('x y z t')
    variables=(x,y,z)
    degree=2+j%3
    monomials=[x*x,y*y,z*z,x*y,y*z,x*z,x*y*z,x**degree,y**degree,z**degree]
    P=sum(rng.randint(-4,4)*term for term in monomials)+rng.randint(-6,6)
    P=sp.expand(P.subs({x:x+(1+j%3)*y,y:y+(1+j%2)*z}, simultaneous=True))
    gradients=[sp.diff(P,v) for v in variables]
    require(all(sp.expand(sp.diff(gradients[i],variables[k])-sp.diff(gradients[k],variables[i]))==0 for i in range(3) for k in range(3)), "Invariant verification failed at check 130")
    c=P.subs({x:0,y:0,z:0})
    # Reconstruction from the path integral, not from the planted coefficients.
    radial=sum(v*g.subs({x:t*x,y:t*y,z:t*z}, simultaneous=True) for v,g in zip(variables,gradients))
    restored=sp.expand(c+sp.integrate(radial,(t,0,1)))
    require(sp.expand(P-restored)==0, "Invariant verification failed at check 135")
    hessian=sp.hessian(P,variables)
    answer={'potential_terms': poly_terms(restored,variables),
            'gradient_at_origin':[q(g.subs({x:0,y:0,z:0})) for g in gradients],
            'hessian_trace_at_origin':q(sp.trace(hessian.subs({x:0,y:0,z:0})))}
    problem=(f'Um potencial polinomial desconhecido V(x,y,z) de grau ≤{sp.Poly(P,x,y,z).total_degree()} '
             f'tem gradiente G={[str(g) for g in gradients]} e V(0,0,0)={c}. '
             'Reconstrua V de modo exato, calcule G(0) e tr Hess(V)(0). Verifique compatibilidade ∂iGj=∂jGi.')
    steps=['Verificar a condição de integrabilidade ∂iGj=∂jGi para todas as seis comparações.',
           'Integrar a 1-forma ao longo da curva radial t↦t(x,y,z), entre 0 e 1.',
           'Adicionar o valor V(0) e conferir as três derivadas parciais independentemente.']
    structure=['exact_forms','mixed_coordinate_shear','cross_derivative_integrability','radial_path_integral','hessian']
    return {'degree':sp.Poly(P,x,y,z).total_degree(),'gradient':[str(g) for g in gradients], 'origin_value':q(c)},problem,answer,steps,structure,{'curl_zero':True,'independent_path_integral':True}


def lie_conjugation(j,rng):
    m=2+j%4; n=m+1
    E,F,H=sp.zeros(n),sp.zeros(n),sp.diag(*[m-2*i for i in range(n)])
    for i in range(1,n): E[i-1,i]=i*(m-i+1)
    for i in range(n-1): F[i+1,i]=1
    U=sp.eye(n)
    shear_count=2+j%3
    for t in range(shear_count):
        a=(t+j)%n; b=(a+1+t//n)%n
        if a==b:b=(b+1)%n
        B=sp.eye(n); B[a,b]=rng.choice([-2,-1,1,2]);U=B*U
    Ui=U.inv()
    E,F,H=(U*M*Ui for M in (E,F,H))
    C=sp.Rational(1,2)*H*H+E*F+F*E
    eigen=sp.Rational(m*(m+2),2)
    require(C==eigen*sp.eye(n) and H*E-E*H==2*E and H*F-F*H==-2*F and E*F-F*E==H, "Invariant verification failed at check 165")
    answer={'casimir_eigenvalue':q(eigen),'irrep_dimension':n,
            'trace_h_square':q(sp.trace(H*H)), 'raising_nilpotency_order':m+1}
    problem=(f'Considere E,F,H ∈ Mat_{n}(Q), numa base desconhecida, dados por '
             f'E={matrix_data(E)}, F={matrix_data(F)}, H={matrix_data(H)}. '
             'Verifique [H,E]=2E, [H,F]=-2F, [E,F]=H e determine o autovalor de '
             'Ω=H²/2+EF+FE, sua dimensão, tr(H²) e o índice de nilpotência de E.')
    steps=['Comutar as matrizes fornecidas usando multiplicação exata, não a apresentação padrão.',
           'Calcular Ω=H²/2+EF+FE, verificar que é escalar central nesta representação.',
           'Computar E^k sucessivamente para determinar o primeiro expoente com E^k=0.']
    structure=['sl2_lie_brackets','unimodular_conjugations','casimir_centrality','nilpotency','trace']
    return {'E':matrix_data(E),'F':matrix_data(F),'H':matrix_data(H),'shear_count':shear_count},problem,answer,steps,structure,{'lie_commutators':True,'matrix_casimir':True}


def stochastic_invariant(j,rng):
    x=sp.symbols('x',positive=True)
    sigma=1+j%3; s=2+j%6; lam=sp.Rational(1+j%5,1+(j//2)%3)
    alpha=sp.Rational(sigma*sigma*(s+1),2); beta=sigma*sigma*lam
    mu=alpha*x-beta*x**3; volatility=sigma*x
    exponent=s-1
    shape=sp.Rational(s,2)
    normalized=2*lam**shape / sp.gamma(shape)*x**exponent*sp.exp(-lam*x*x)
    current=sp.simplify(mu*normalized-sp.Rational(1,2)*sp.diff(volatility**2*normalized,x))
    require(current==0, "Invariant verification failed at check 188")
    Z=sp.gamma(shape)/(2*lam**shape)
    require(sp.simplify(sp.integrate(x**exponent*sp.exp(-lam*x*x),(x,0,sp.oo))-Z)==0, "Invariant verification failed at check 190")
    mean2=shape/lam;mean4=shape*(shape+1)/lam**2
    generator_check=sp.simplify((2*alpha+sigma*sigma)*mean2-2*beta*mean4)
    require(generator_check==0, "Invariant verification failed at check 193")
    answer={'stratonovich_linear':q(alpha-sp.Rational(sigma*sigma,2)),
            'stratonovich_cubic':q(-beta), 'stationary_power':exponent,
            'stationary_rate':q(lam), 'normalization_Z':str(sp.simplify(Z)),
            'moment_x2':q(mean2), 'moment_x4':q(mean4)}
    problem=(f'Para X0>0: dX=(({alpha})X-({beta})X³)dt+{sigma}X dW (Itô). '
             'Encontre a deriva de Stratonovich, a densidade estacionária p=C x^a exp(-λ x²), '
             'Z=1/C e os momentos E[X²], E[X⁴], com condição de fluxo nulo no semieixo positivo.')
    steps=['Converter Itô em Stratonovich subtraindo b(x)b\'(x)/2.',
           'Impor J=μp-(b²p)\'/2=0 e comparar as potências de x.',
           'Integrar o perfil via Γ((a+1)/2) e verificar o momento gerador E[L x²]=0.',
           'O estado absorvente 0 não foi identificado com o estado estacionário em x>0.']
    structure=['ito_stratonovich','multiplicative_noise','zero_flux','gamma_integral','stationary_generator_moment']
    return {'alpha':q(alpha),'beta':q(beta),'sigma':sigma,'shape':s},problem,answer,steps,structure,{'probability_normalized':True,'zero_flux':True,'generator_moment':True}


def conformal_geometry(j,rng):
    x,y=sp.symbols('x y');v=(x,y)
    h=1+j%3; A=sp.Matrix([[1,h],[0,1]]) if j%2 else sp.Matrix([[1,0],[h,1]])
    Q=A.T*A;Qi=Q.inv()
    a,b,c,d,e=[rng.randint(-3,3) for _ in range(5)]
    if not a and not c:a=1
    u=a*x*x+b*x*y+c*y*y+d*x+e*y
    grad=[sp.diff(u,k) for k in v]
    Gamma=[[[sp.expand((int(k==i)*grad[jj]+int(k==jj)*grad[i])-Q[i,jj]*sum(Qi[k,l]*grad[l] for l in range(2))) for jj in range(2)] for i in range(2)] for k in range(2)]
    Ric=sp.Matrix(2,2,lambda i,jj:sp.expand(sum(sp.diff(Gamma[k][i][jj],v[k])-sp.diff(Gamma[k][i][k],v[jj]) for k in range(2)) + sum(Gamma[k][k][l]*Gamma[l][i][jj]-Gamma[k][jj][l]*Gamma[l][i][k] for k in range(2) for l in range(2))))
    lap=sp.expand(sum(Qi[i,jj]*sp.diff(u,v[i],v[jj]) for i in range(2) for jj in range(2)))
    require(Ric==(-lap)*Q, "Invariant verification failed at check 220")
    scalar_factor=sp.expand(-2*lap)
    answer={'scalar_curvature_prefactor':poly_terms(scalar_factor,v),
            'scalar_curvature_at_origin':q(scalar_factor.subs({x:0,y:0})),
            'determinant_metric_prefactor':q(Q.det()),
            'gaussian_curvature_at_origin':q(scalar_factor.subs({x:0,y:0})/2)}
    problem=(f'Seja a métrica riemanniana g=e^(2u(x,y)) Q numa carta, com '
             f'Q={matrix_data(Q)}, u(x,y)={u}. '
             'Deduzir R(x,y) na forma e^(-2u) P(x,y), K(0,0), R(0,0) e det(g)/e^(4u).')
    steps=['A métrica base Q é constante, positiva definida e tem determinante não nulo.',
           'Calcular a conexão Γ^k_ij=δki u_j+δkj u_i−Qij Q^{kl}u_l.',
           'Contrair R_ij obtido de Γ e verificar R=e^(-2u)[-2 Q^{ij}∂i∂j u].',
           'Usar K=R/2 em dimensão 2; separar singularidades de coordenadas e curvatura.']
    structure=['metric_affine_pullback','conformal_change','christoffel_symbols','ricci_contraction','scalar_curvature']
    return {'Q':matrix_data(Q),'u':str(u),'shear':h},problem,answer,steps,structure,{'full_ricci_tensor_checked':True,'positive_definite_base':True}


def finite_field_invariants(j,rng):
    p=(7,11,13)[j%3]; degree=3+j%3
    x,t=sp.symbols('x t')
    f=None
    for trial in range(500):
        coeffs=[rng.randrange(p) for _ in range(degree)]
        if coeffs[0]==0:continue
        candidate=sp.Poly(x**degree+sum(coeffs[i]*x**i for i in range(degree)),x,modulus=p)
        if candidate.is_irreducible:
            f=candidate;break
    if f is None:raise ArithmeticError('Could not find irreducible polynomial')
    a=rng.randrange(1,p); b=rng.randrange(p)
    new=sp.Poly(sum(int(c)*a**(degree-i)*(t-b)**i for i,c in enumerate(reversed(f.all_coeffs()))),t,modulus=p)
    require(new.degree()==degree and new.LC()%p==1, "Invariant verification failed at check 250")
    M=sp.zeros(degree)
    for col in range(degree):
        rem=sp.Poly((a*x+b)*x**col,x,modulus=p).rem(f)
        for row in range(degree): M[row,col]=int(rem.nth(row))%p
    trace=int(sp.trace(M))%p;norm=int(M.det())%p
    require(trace==(-new.nth(degree-1))%p, "Invariant verification failed at check 256")
    require(norm==((-1)**degree*new.nth(0))%p, "Invariant verification failed at check 257")
    answer={'minimal_polynomial_coefficients_ascending':[int(new.nth(i))%p for i in range(degree+1)],
            'field_trace':trace,'field_norm':norm,'extension_degree':degree}
    problem=(f'Em F_{p^degree}=F_{p}[x]/(f), f(x)={f.as_expr()} irredutível, '
             f'defina α={a}x+{b}. Determine o polinômio mínimo m_α(t) mônico, '
             'Tr_{Fq/Fp}(α), Norm_{Fq/Fp}(α) e o grau da extensão gerada por α.')
    steps=['Testar a irredutibilidade de f em Fp com aritmética polinomial exata.',
           'Aplicar a transformação m(t)=a^d f((t-b)/a) e reduzir os coeficientes módulo p.',
           'Calcular independentemente traço e determinante da matriz de multiplicação por α.',
           'Conferir a igualdade dos dois métodos e que o grau mínimo permanece d.']
    structure=['irreducible_field_extension','affine_primitive_transform','minimal_polynomial','multiplication_matrix','trace_norm']
    return {'p':p,'f_ascending':[int(f.nth(i))%p for i in range(degree+1)],'alpha_a':a,'alpha_b':b},problem,answer,steps,structure,{'irreducibility':True,'matrix_trace_norm':True}


def kirchhoff_graph(j,rng):
    n=4+j%3
    edges=[(i,i+1,rng.randint(1,6)) for i in range(n-1)]
    all_pairs=[(a,b) for a in range(n) for b in range(a+1,n) if (a,b) not in {(x,y) for x,y,w in edges}]
    rng.shuffle(all_pairs)
    edges.extend((a,b,rng.randint(1,5)) for a,b in all_pairs[:1+j%3])
    L=sp.zeros(n)
    for a,b,w in edges:
        L[a,a]+=w;L[b,b]+=w;L[a,b]-=w;L[b,a]-=w
    tau=L[:n-1,:n-1].det()
    def count_tree_weight():
        total=0
        for subset in itertools.combinations(edges,n-1):
            parent=list(range(n))
            def find(v):
                while v!=parent[v]:v=parent[v]
                return v
            acyclic=True
            for u,v,_w in subset:
                a,b=find(u),find(v)
                if a==b:acyclic=False;break
                parent[a]=b
            if acyclic and len({find(v) for v in range(n)})==1:
                total+=math.prod(w for _,_,w in subset)
        return total
    require(tau==count_tree_weight(), "Invariant verification failed at check 296")
    u=0;v=n-1
    Lg=L[:n-1,:n-1]
    bvec=sp.Matrix([1 if i==u else (-1 if i==v else 0) for i in range(n-1)])
    potentials=Lg.inv()*bvec
    resist=(bvec.T*potentials)[0]
    require(resist>0, "Invariant verification failed at check 302")
    energy=sum(w*((potentials[a] if a<n-1 else 0)-(potentials[b] if b<n-1 else 0))**2 for a,b,w in edges)
    require(sp.simplify(energy-resist)==0, "Invariant verification failed at check 304")
    answer={'weighted_spanning_tree_count':int(tau),'effective_resistance':q(resist),
            'effective_conductance':q(1/resist)}
    problem=(f'Rede resistiva com {n} vértices e condutâncias nas arestas (u,v,c): {edges}. '
             f'Determine τ(G)=Σ_árvores ∏c, R_efetiva({u},{v}) e sua condutância inversa. '
             'Apresente método de Laplaciano e um segundo cheque combinatório.')
    steps=['Montar L=D−W e remover uma linha e uma coluna para τ pela fórmula matriz-árvore.',
           'Recontar independentemente árvores geradoras, rejeitando ciclos por união de componentes.',
           'Injetar uma unidade de corrente entre os terminais, resolver potencial e calcular dissipação.',
           'A energia Σc(ΔV)² deve coincidir com R_efetiva para corrente unitária.']
    structure=['weighted_graph','matrix_tree_theorem','union_find_enumeration','grounded_laplacian','effective_resistance']
    return {'vertices':n,'edges':[list(e) for e in edges], 'terminals':[u,v]},problem,answer,steps,structure,{'combinatorial_tree_count':True,'thomson_energy_identity':True}


def syndrome_code(j,rng):
    p=2 if j%2==0 else 3;k=3+j%2;r=3;n=k+r
    def wt(v):return sum(int(x)%p!=0 for x in v)
    P=None; dmin=0
    for attempt in range(4000):
        cand=sp.Matrix([[rng.randrange(p) for _ in range(k)] for _ in range(r)])
        G=sp.Matrix.hstack(sp.eye(k),-cand.T)
        cw=[G.T*sp.Matrix(ms) for ms in itertools.product(range(p),repeat=k) if any(ms)]
        dmin=min(wt(c) for c in cw)
        if dmin>=3:P=cand;break
    if P is None:raise ArithmeticError('Could not construct 1-error-correcting code')
    H=sp.Matrix.hstack(P,sp.eye(r));G=sp.Matrix.hstack(sp.eye(k),-P.T)
    require(all(int(v)%p==0 for v in H*G.T), "Invariant verification failed at check 330")
    msg=[rng.randrange(p) for _ in range(k)]
    encoded=[int(v)%p for v in (G.T*sp.Matrix(msg))]
    pos=rng.randrange(n);delta=rng.randrange(1,p)
    received=encoded.copy();received[pos]=(received[pos]+delta)%p
    syndrome=[int(v)%p for v in H*sp.Matrix(received)]
    candidates=[]
    for i in range(n):
        for e in range(1,p):
            if [int(v*e)%p for v in H[:,i]]==syndrome:candidates.append((i,e))
    require(candidates==[(pos,delta)], "Invariant verification failed at check 340")
    answer={'message':msg,'codeword':encoded,'error_position':pos,'error_symbol':delta,
            'minimum_distance':dmin,'syndrome':syndrome}
    problem=(f'Código linear C⊂F_{p}^{n} com matriz de paridade H={matrix_data(H)} '
             f'e palavra recebida r={received}. A distância mínima é pelo menos 3. '
             'Determine a síndrome, localize/corrija um único erro, recupere mensagem sistemática e calcule d_min.')
    steps=['Verificar a paridade Hc=0 e construir um gerador sistemático G=[I|-Pᵀ].',
           'Enumerar mensagens não nulas (espaço pequeno) para certificar a distância mínima.',
           'Comparar a síndrome de r com cada coluna H multiplicada por erro não nulo.',
           'Corrigir um símbolo e conferir Hc=0, garantindo unicidade para uma única alteração.']
    structure=['finite_field_linear_code','parity_check','syndrome','exhaustive_distance_certificate','unique_nearest_decoder']
    return {'p':p,'H':matrix_data(H),'received':received},problem,answer,steps,structure,{'all_codewords_enumerated':True,'unique_error_decoder':True}


def discrete_lyapunov(j,rng):
    n=2+j%2
    eigen=[sp.Rational(1+(i+j)%3,4+(i+j)%3) for i in range(n)]
    S=sp.eye(n)
    for it in range(1+j%3):
        a=it%n;b=(a+1)%n;B=sp.eye(n);B[a,b]=rng.choice([-2,-1,1,2]);S=B*S
    D=sp.diag(*eigen);A=S*D*S.inv()
    Q=sp.diag(*[1+(i+j)%3 for i in range(n)])
    C=S.T*Q*S
    C=sp.Matrix(n,n,lambda i,k:sp.simplify(C[i,k]/(1-eigen[i]*eigen[k])))
    P=S.inv().T*C*S.inv()
    require(P==P.T and sp.simplify(P-A.T*P*A-Q)==sp.zeros(n), "Invariant verification failed at check 365")
    principals=[sp.factor(P[:i,:i].det()) for i in range(1,n+1)]
    require(all(a>0 for a in principals), "Invariant verification failed at check 367")
    # Uniqueness follows |lambda_i lambda_j|<1 for all pairs.
    require(all(abs(a*b)<1 for a in eigen for b in eigen), "Invariant verification failed at check 369")
    answer={'lyapunov_solution':matrix_data(P),'leading_principal_minors':list(map(q,principals)),
            'spectral_radius':q(max(abs(t) for t in eigen))}
    problem=(f'Para dinâmica x_(t+1)=A x_t e Q>0, A={matrix_data(A)}, Q={matrix_data(Q)}, '
             'determine a solução simétrica exata P da equação de Lyapunov '
             'P−Aᵀ P A=Q; prove P>0 por menores principais e calcule ρ(A).')
    steps=['Exibir estabilidade via autovalores racionais de A e ρ(A)<1.',
           'Transformar a equação por uma base de autovetores e resolver cada entrada C_ij/(1−λ_i λ_j).',
           'Retornar à base original e conferir exatamente P−AᵀPA=Q.',
           'Usar menores principais positivos como certificado de positividade definida.']
    structure=['rational_linear_dynamics','similarity_obfuscation','discrete_lyapunov','spectral_stability','sylvester_positive_definite']
    return {'A':matrix_data(A),'Q':matrix_data(Q)},problem,answer,steps,structure,{'matrix_residual_zero':True,'sylvester_criterion':True}


def rational_walks(j,rng):
    n=3+j%2;z=sp.symbols('z')
    A=sp.Matrix([[rng.randint(0,2) for _ in range(n)] for _ in range(n)])
    for i in range(n):A[i,(i+1)%n]+=1
    origin=j%n;target=(origin+1+j//2)%n
    M=sp.eye(n)-z*A
    func=sp.cancel(M.adjugate()[origin,target]/M.det())
    num,den=sp.fraction(func)
    dc=sp.Poly(den,z,domain=sp.QQ)
    factor=dc.nth(0)
    require(factor!=0, "Invariant verification failed at check 393")
    numerator=sp.Poly(sp.cancel(num/factor),z,domain=sp.QQ)
    denominator=sp.Poly(sp.cancel(den/factor),z,domain=sp.QQ)
    coeff=[q((A**k)[origin,target]) for k in range(9)]
    # Independent coefficient extraction from generating-function power series.
    expanded=sp.series(func,z,0,9).removeO()
    require(all(sp.Rational(coeff[k])==expanded.coeff(z,k) for k in range(9)), "Invariant verification failed at check 399")
    require(sp.cancel(func-numerator.as_expr()/denominator.as_expr())==0, "Invariant verification failed at check 400")
    answer={'numerator_ascending':[q(numerator.nth(i)) for i in range(numerator.degree()+1)],
            'denominator_ascending':[q(denominator.nth(i)) for i in range(denominator.degree()+1)],
            'walk_counts_length_0_through_8':coeff}
    problem=(f'Um multigrafo direcionado tem matriz de adjacência A={matrix_data(A)}. '
             f'Encontre G(z)=[(I−zA)^(-1)]_{{{origin},{target}}} como função racional P(z)/Q(z) '
             '(Q(0)=1, fração reduzida), e calcule a contagem de passeios de comprimento 0..8 entre os vértices.')
    steps=['Usar adj(I−zA)/det(I−zA) e cancelar fatores comuns exatamente.',
           'Escolher denominador normalizado Q(0)=1 e expressar coeficientes ascendentes.',
           'Conferir a série como Σ(A^k)_{origem,destino} z^k por multiplicações matriciais independentes.']
    structure=['directed_multigraph','resolvent','adjugate_determinant','rational_function','walk_count_recurrence']
    return {'adjacency':matrix_data(A),'source':origin,'target':target},problem,answer,steps,structure,{'matrix_powers_against_series':True,'rational_resolvent_identity':True}


# Ten genuinely different optional verification obligations in each base grammar:
# all six pairs and all four triples of the four domain-specific operators.
OPERATOR_SETS = list(itertools.combinations(range(4), 2)) + list(itertools.combinations(range(4), 3))
require(len(OPERATOR_SETS) == 10, "Invariant verification failed at check 417")


def _from_mat(rows):
    return sp.Matrix([[sp.Rational(item) for item in row] for row in rows])


def enrichment(family, variant, parameters, answer):
    """Attach actual, computed domain-specific tasks (not decorative labels).

    A signature denotes *which mathematical operations* are requested; the
    selected tasks alter the answer schema and verification obligations.
    """
    chosen = OPERATOR_SETS[variant]
    descriptions = []
    results = {}
    if family == 0:
        p = parameters['p'];x,y,z = sp.symbols('x y z')
        G=sp.groebner([sp.sympify(e, locals={'x':x,'y':y,'z':z}) for e in parameters['generators']],x,y,z,modulus=p,order='lex')
        elimination = G.polys[-1].as_expr()
        d=parameters['degree']
        # Construct alternate independent reductions from the generated ideal.
        rem_xz=G.reduce(x*z)[1]
        rem_yy=G.reduce(y*y)[1]
        values={'eliminant_z_coefficients': [int(sp.Poly(elimination,z,modulus=p).nth(i))%p for i in range(d+1)],
                'normal_form_xz':poly_terms(rem_xz,(x,y,z),p),
                'normal_form_y_squared':poly_terms(rem_yy,(x,y,z),p),
                'geometric_point_count_with_multiplicity':d}
        descriptions=['coeficientes do eliminante em z','forma normal de xz','forma normal de y²',
                      'número de pontos sobre o fecho algébrico com multiplicidades']
        require(G.reduce(rem_xz-x*z)[1]==0 and G.reduce(rem_yy-y*y)[1]==0, "Invariant verification failed at check 447")
    elif family == 1:
        x,y,z=sp.symbols('x y z');v=(x,y,z)
        G=[sp.sympify(s,locals={'x':x,'y':y,'z':z}) for s in parameters['gradient']]
        H=sp.Matrix([[sp.diff(G[i],v[j]) for j in range(3)] for i in range(3)])
        values={'gradient_at_point_100':[q(g.subs({x:1,y:0,z:0})) for g in G],
                'hessian_determinant_at_origin':q(H.subs({x:0,y:0,z:0}).det()),
                'divergence_terms':poly_terms(sum(sp.diff(G[i],v[i]) for i in range(3)),v),
                'directional_derivative_111':q(sum(g.subs({x:1,y:1,z:1}) for g in G))}
        descriptions=['gradiente em (1,0,0)','det Hess(V) na origem',
                      'polinômio div G','derivada direcional na direção (1,1,1) no ponto (1,1,1)']
        require(H==H.T, "Invariant verification failed at check 458")
    elif family == 2:
        E,F,H=[_from_mat(parameters[k]) for k in ('E','F','H')]
        t=sp.symbols('t')
        char=H.charpoly(t).as_expr()
        values={'raising_rank':int(E.rank()),'trace_EF':q(sp.trace(E*F)),
                'determinant_H':q(H.det()),
                'characteristic_H_ascending':[q(sp.Poly(char,t).nth(i)) for i in range(H.rows+1)]}
        descriptions=['posto do operador E','traço(EF)','determinante de H','polinômio característico de H']
        require(int(E.rank())==E.rows-1, "Invariant verification failed at check 467")
    elif family == 3:
        s=parameters['shape'];lam=sp.Rational(answer['stationary_rate'])
        moments=lambda k:sp.prod(sp.Rational(s,2)+i for i in range(k))/lam**k
        beta=sp.Rational(parameters['beta']);alpha=sp.Rational(parameters['alpha']);sigma=parameters['sigma']
        values={'stationary_moment_x6':q(moments(3)),
                'stationary_moment_x8':q(moments(4)),
                'mode_squared':q(sp.Rational(s-1,2)/lam),
                'generator_x4_residual':q((4*alpha+6*sigma**2)*moments(2)-4*beta*moments(3))}
        descriptions=['momento estacionário E[X⁶]','momento estacionário E[X⁸]',
                      'quadrado da moda da densidade','resíduo de E[L X⁴]']
        require(sp.Rational(values['generator_x4_residual'])==0, "Invariant verification failed at check 478")
    elif family == 4:
        x,y=sp.symbols('x y');Q=_from_mat(parameters['Q']);Qi=Q.inv()
        u=sp.sympify(parameters['u'],locals={'x':x,'y':y})
        lap=sum(Qi[i,k]*sp.diff(u,(x,y)[i],(x,y)[k]) for i in range(2) for k in range(2))
        Ric=-lap*Q
        values={'gaussian_prefactor':poly_terms(-lap,(x,y)),
                'inverse_base_metric':matrix_data(Qi),
                'ricci_tensor_at_origin':matrix_data(Ric.subs({x:0,y:0})),
                'scalar_curvature_prefactor_at_1_1':q((-2*lap).subs({x:1,y:1}))}
        descriptions=['fator de K(x,y) multiplicando e^(-2u)','inversa de Q',
                      'tensor de Ricci na origem','fator de R em (1,1)']
        require(Ric==Ric.T, "Invariant verification failed at check 490")
    elif family == 5:
        p=parameters['p']; degree=len(parameters['f_ascending'])-1
        x=sp.symbols('x'); f=sp.Poly(sum(c*x**i for i,c in enumerate(parameters['f_ascending'])),x,modulus=p)
        a=parameters['alpha_a'];b=parameters['alpha_b']
        M=sp.zeros(degree)
        for col in range(degree):
            rem=sp.Poly((a*x+b)*x**col,x,modulus=p).rem(f)
            for row in range(degree):M[row,col]=int(rem.nth(row))%p
        # Coefficients are represented mod p; multiplication matrices supply
        # an unrelated route to the field invariants.
        min_poly=sp.Poly(sum(coef*x**i for i,coef in enumerate(answer['minimal_polynomial_coefficients_ascending'])),x,modulus=p)
        values={'trace_alpha_squared':int(sp.trace(M*M))%p,
                'norm_alpha_plus_one':int((M+sp.eye(degree)).det())%p,
                'minimal_polynomial_squarefree':sp.gcd(min_poly,min_poly.diff()).degree()==0,
                'trace_alpha_cubed':int(sp.trace(M*M*M))%p}
        descriptions=['traço de α²','norma de α+1','separabilidade do polinômio mínimo','traço de α³']
        require(values['minimal_polynomial_squarefree'], "Invariant verification failed at check 507")
    elif family == 6:
        n=parameters['vertices'];edges=parameters['edges']
        def lapl(weighted):
            L=sp.zeros(n)
            for a,b,w in edges:
                if not weighted:w=1
                L[a,a]+=w;L[b,b]+=w;L[a,b]-=w;L[b,a]-=w
            return L
        L=lapl(True);binary=lapl(False)
        def resistance(a,b):
            rhs=sp.Matrix([(1 if i==a else 0)-(1 if i==b else 0) for i in range(n-1)])
            return (rhs.T*L[:n-1,:n-1].inv()*rhs)[0]
        values={'unweighted_spanning_trees':int(binary[:n-1,:n-1].det()),
                'secondary_effective_resistance':q(resistance(1,n-1)),
                'degree_weighted_origin':int(L[0,0]),
                'effective_resistance_0_1':q(resistance(0,1))}
        descriptions=['árvores geradoras desconsiderando pesos','resistência efetiva (1,n−1)',
                      'grau ponderado do vértice 0','resistência efetiva (0,1)']
        require(values['unweighted_spanning_trees']>0, "Invariant verification failed at check 526")
    elif family == 7:
        p=parameters['p'];H=_from_mat(parameters['H']);r,k=H.rows,H.cols-H.rows
        P=H[:,:k];G=sp.Matrix.hstack(sp.eye(k),-P.T)
        weights={}
        for m in itertools.product(range(p),repeat=k):
            cw=G.T*sp.Matrix(m)
            w=sum(int(v)%p!=0 for v in cw)
            weights[str(w)]=weights.get(str(w),0)+1
        values={'code_cardinality':p**k,
                'weight_enumerator':{key:weights[key] for key in sorted(weights,key=int)},
                'parity_check_rank':int(H.rank()),
                'minimum_nonzero_weight_count':weights[str(answer['minimum_distance'])]}
        descriptions=['cardinalidade do código','enumerador de pesos completo',
                      'posto da matriz de paridade','número de palavras de peso mínimo']
        require(sum(weights.values())==p**k, "Invariant verification failed at check 541")
    elif family == 8:
        P=_from_mat(answer['lyapunov_solution']);A=_from_mat(parameters['A']);Q=_from_mat(parameters['Q'])
        resid=P-A.T*P*A-Q
        values={'lyapunov_trace':q(sp.trace(P)), 'lyapunov_determinant':q(P.det()),
                'residual_frobenius_squared':q(sp.trace(resid.T*resid)),
                'energy_for_all_ones':q((sp.ones(P.rows,1).T*P*sp.ones(P.rows,1))[0])}
        descriptions=['tr P','det P','norma de Frobenius ao quadrado do resíduo',
                      'energia V(1,…,1)']
        require(resid==sp.zeros(P.rows), "Invariant verification failed at check 550")
    else:
        A=_from_mat(parameters['adjacency']);src=parameters['source'];dst=parameters['target']
        z=sp.symbols('z');n=A.rows
        char=sp.Poly(A.charpoly(z).as_expr(),z)
        values={'length_9_walk_count':int((A**9)[src,dst]),
                'length_10_walk_count':int((A**10)[src,dst]),
                'adjacency_characteristic_ascending':[q(char.nth(i)) for i in range(n+1)],
                'closed_walks_length_6':int(sp.trace(A**6))}
        descriptions=['passeios de comprimento 9','passeios de comprimento 10',
                      'polinômio característico de A','número de passeios fechados de comprimento 6']
        require(values['closed_walks_length_6']>=0, "Invariant verification failed at check 561")
    names=list(values)
    picked={names[k]:values[names[k]] for k in chosen}
    requested=[descriptions[k] for k in chosen]
    operators=['optional:'+names[k] for k in chosen]
    require(len(picked)==len(chosen), "Invariant verification failed at check 566")
    return picked, requested, operators


GENERATORS=(polynomial_ideal,potential_recovery,lie_conjugation,stochastic_invariant,
            conformal_geometry,finite_field_invariants,kirchhoff_graph,syndrome_code,
            discrete_lyapunov,rational_walks)


def create_record(index,make_receipt,verify_receipt,backend_name):
    if type(index) is not int or not 1<=index<=MAX_COUNT:raise ValueError('Index out of range')
    family=(index-1)%len(GENERATORS)
    variant=(index-1)//len(GENERATORS)
    seed=202610170000+index*104729
    rng=random.Random(seed)
    parameters,problem,answer,derivation,operations,checks=GENERATORS[family](variant,rng)
    require(all(value is True for value in checks.values()), "Invariant verification failed at check 582")
    extensions, additional_tasks, optional_ops=enrichment(family,variant,parameters,answer)
    answer={**answer, **extensions}
    operations=[*operations,*optional_ops]
    problem+='\nObrigações composicionais adicionais: '+ '; '.join(additional_tasks)+'.'
    derivation=[*derivation, 'Resolver também as obrigações adicionais com aritmética exata e conferir os invariantes.']
    checks={**checks,'optional_operators_independently_recomputed':True}
    signature=canonical({'family':NAMES[family],'tasks':optional_ops})
    split='test_unseen_family' if family>=8 else 'train'
    complexity={'operator_count':len(operations),'answer_size_bytes':len(canonical(answer)),
                'symbolic_size_bytes':len(problem),'difficulty_label':'structural_proxy_not_model_calibrated'}
    record={'schema_version':VERSION,'problem_id':f'FOUNDRY-{index:04d}',
            'domain':NAMES[family],'split':split,'seed':seed,
            'grammar_signature':signature,
            'parameters':parameters,'problem':problem,'answer':answer,
            'derivation':derivation,'operations':operations,
            'validation_checks':checks,'complexity':complexity,
            'proof_status':'INDEPENDENT_EXACT_CHECKS_NOT_FORMAL_PROOF',
            'source':'inverse_constructed_synthetic_no_scraping'}
    rec=make_receipt('frontier_foundry_v3',
                     {'problem_id':record['problem_id'],'domain':record['domain'],
                      'seed':seed,'parameters_digest':digest(parameters)},
                     {'answer_digest':digest(answer),'checks':checks},
                     metadata={'schema_version':VERSION,'backend':backend_name,
                               'proof_status':record['proof_status']})
    if not verify_receipt(rec):raise ArithmeticError('Invalid Nabla/portable receipt')
    return {**record,'receipt':rec,'record_sha256':digest(record)}


def normalize_numeric(value):
    if type(value) is bool:return value
    if type(value) is int:return str(value)
    if isinstance(value,str):
        if len(value)>128: return value
        try:
            # Rational leaf normalization; exact symbolic text remains canonical.
            return str(Fraction(value))
        except (ValueError,ZeroDivisionError):return value
    if isinstance(value,list):return [normalize_numeric(x) for x in value]
    if isinstance(value,dict):return {k:normalize_numeric(v) for k,v in value.items()}
    return value


def grade_answer(expected,candidate):
    """Executable reward: strict keys/shapes, rational equivalence, no eval/sympify."""
    if not isinstance(candidate,dict) or set(candidate)!=set(expected):return False
    try:return canonical(normalize_numeric(candidate))==canonical(normalize_numeric(expected))
    except (TypeError,ValueError,RecursionError):return False


def mutate(answer):
    value=copy.deepcopy(answer)
    for key,v in value.items():
        if type(v) is int:
            value[key]=v+1;return value
        if type(v) is str:
            value[key]=v+'__tampered';return value
        if isinstance(v,list):
            value[key]=v+['__tampered'];return value
    raise ValueError('No mutable observable solution field')


def render_txt(record):
    return ('='*84+'\n'+record['problem_id']+' | '+record['domain']+' | '+record['split']+'\n'
            +'CONTENT_SHA256: '+record['record_sha256']+'\n'
            +'RECEIPT_SHA256: '+record['receipt']['content_id']+'\n'+'='*84+'\n'
            +'[PROBLEM]\n'+record['problem']+'\n\n'
            +'<derivation>\n'+'\n'.join(f'{j}. {line}' for j,line in enumerate(record['derivation'],1))+'\n</derivation>\n\n'
            +'<solution>\n'+json.dumps(record['answer'],ensure_ascii=False,indent=2,sort_keys=True)+'\n</solution>\n'
            +'[AUDIT]\n'+canonical({'operations':record['operations'],'checks':record['validation_checks'],
                                     'proof_status':record['proof_status'],'backend':record['receipt']['metadata']['backend']})+'\n\n')


def build(count,out,portable):
    if type(count) is not int or not 1<=count<=MAX_COUNT:raise ValueError('count must be 1..100')
    make,verify,back=backend(not portable)
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    records=[create_record(i,make,verify,back) for i in range(1,count+1)]
    if len({r['grammar_signature'] for r in records})!=len(records):
        raise ArithmeticError('Duplicate composition grammar signature')
    txt=('# NABLA FRONTIER FOUNDRY v3 | 100 synthetically inverse-constructed problems\n'
         '# 10 mathematical families; 80 training vs. 20 unseen-family evaluation records for count=100.\n'
         '# Proof status: independent exact checks, NOT Lean/SMT formal certificates.\n'
         '# SHA-256: content integrity, NOT authorship or mathematical correctness.\n'
         '# derivation: public checkable explanation, NOT a private model thought trace.\n'
         f'# Backend: {back}; generated: {count}\n\n') + ''.join(render_txt(r) for r in records)
    encoded=txt.encode('utf-8')
    out.write_bytes(encoded)
    base=out.with_suffix('')
    (base.parent/(base.name+'.jsonl')).write_text(''.join(canonical(r)+'\n' for r in records),encoding='utf-8')
    (base.parent/(base.name+'.eval_prompts.jsonl')).write_text(''.join(canonical({k:r[k] for k in ('problem_id','domain','split','problem','operations')})+'\n' for r in records if r['split']!='train'),encoding='utf-8')
    (base.parent/(base.name+'.eval_answer_key.jsonl')).write_text(''.join(canonical({'problem_id':r['problem_id'],'answer':r['answer'],'sha256':r['record_sha256']})+'\n' for r in records if r['split']!='train'),encoding='utf-8')
    manifest={'schema_version':VERSION,'count':count,'sha256':hashlib.sha256(encoded).hexdigest(),
              'record_digest':digest([r['record_sha256'] for r in records]),
              'backend':back,'family_count':len({r['domain'] for r in records}),
              'domain_counts':{name:sum(r['domain']==name for r in records) for name in NAMES},
              'distinct_operator_grammars':len({r['grammar_signature'] for r in records}),
              'train_count':sum(r['split']=='train' for r in records),
              'test_unseen_family_count':sum(r['split']!='train' for r in records),
              'formal_proof_count':0,'native_laboratory_executed':not portable,
              'limitations':['Offline exact CAS checks are not universal Lean/Z3 proofs.',
                             'Structural complexity is not difficulty calibrated on reasoning models.',
                             'Public TXT contains all answers; sealed evaluation requires separate handling.',
                             '100 distinct operator-task compositions over 10 base mathematical families, not 100 new theories.']}
    Path(str(out)+'.manifest.json').write_text(canonical(manifest)+'\n',encoding='utf-8')
    return manifest


def verify_dataset(out,portable):
    out=Path(out)
    if not out.exists() or not Path(str(out)+'.manifest.json').exists():return False
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        expected=Path(temp)/out.name
        generated=build(json.loads(Path(str(out)+'.manifest.json').read_text())['count'],expected,portable)
        original=json.loads(Path(str(out)+'.manifest.json').read_text())
        if generated!=original or out.read_bytes()!=expected.read_bytes():return False
        for suffix in ('.jsonl','.eval_prompts.jsonl','.eval_answer_key.jsonl'):
            a=out.with_suffix('').parent/(out.stem+suffix)
            b=expected.with_suffix('').parent/(expected.stem+suffix)
            if not a.exists() or a.read_bytes()!=b.read_bytes():return False
    return True


def score_predictions(dataset,predictions):
    ground={r['problem_id']:r for r in map(json.loads,Path(dataset).read_text(encoding='utf-8').splitlines()) if r}
    seen=set();rows=[]
    for line in Path(predictions).read_text(encoding='utf-8').splitlines():
        if not line.strip():continue
        response=json.loads(line)
        ident=response['problem_id']
        if ident in seen or ident not in ground:raise ValueError('Duplicate or unknown problem ID')
        seen.add(ident)
        ref=ground[ident]
        rows.append({'problem_id':ident,'domain':ref['domain'],'split':ref['split'],
                     'passed':grade_answer(ref['answer'],response.get('answer'))})
    if not rows:raise ValueError('No predictions to grade')
    stats={name:{'attempted':sum(r['domain']==name for r in rows),
                 'passed':sum(r['domain']==name and r['passed'] for r in rows)} for name in NAMES if any(r['domain']==name for r in rows)}
    # Curriculum weights target verified failure patterns; do not invent model performance.
    priorities=sorted([{'domain':k,'failed':v['attempted']-v['passed'],
                        'error_rate':(v['attempted']-v['passed'])/v['attempted']} for k,v in stats.items()],
                      key=lambda r:(-r['error_rate'],-r['failed'],r['domain']))
    return {'attempted':len(rows),'passed':sum(r['passed'] for r in rows),'by_domain':stats,
            'curriculum_failure_priorities':priorities,
            'note':'Difficulty measured only on submitted model predictions; no internal OpenAI model benchmark.'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--count',type=int,default=100)
    p.add_argument('--output',type=Path,default=Path('dataset_frontier_foundry_100.txt'))
    p.add_argument('--portable',action='store_true',help='Explicitly use reference receipt contract when Nabla is unavailable')
    p.add_argument('--verify',action='store_true',help='Rebuild and byte-compare TXT, JSONL, splits and manifest')
    p.add_argument('--score',type=Path,help='Model predictions JSONL (problem_id, answer); exact RLVR reward and curriculum')
    args=p.parse_args(argv)
    if args.score:
        data=score_predictions(args.output.with_suffix('').with_suffix('.jsonl'),args.score)
    elif args.verify:
        if not verify_dataset(args.output,args.portable):raise SystemExit('FAIL: dataset replay or integrity mismatch')
        data={'result':'full_byte_replay_passed','file':str(args.output)}
    else:data=build(args.count,args.output,args.portable)
    print(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=True))


if __name__=='__main__':main()