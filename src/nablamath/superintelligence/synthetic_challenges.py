"""Twenty composite expert profiles over the real Nabla calculation catalog.

Every profile has distinct mathematical data and an explicit acceptance scope.
The profiles are authored, bounded exercises, not calibrated research problems.
References use int/Fraction where stated; symbolic cross-checks share a CAS.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import combinations, permutations
import math


@dataclass(frozen=True)
class Challenge:
    title: str
    area: str
    build: object
    burden: str


CHALLENGES = {}


def challenge(name, title, area, burden):
    def register(function):
        CHALLENGES['challenge.' + name] = Challenge(title, area, function, burden)
        return function
    return register


def _advanced(b, action, description, **parameters):
    return b.calc('advanced_math', description, action=action, parameters=parameters)['result']


def _strings(matrix):
    return [[str(value) for value in row] for row in matrix]


def _eye(n):
    return [[Q(i == j) for j in range(n)] for i in range(n)]


def _transpose(a):
    return list(map(list, zip(*a, strict=True)))


def _product(a, b):
    columns = _transpose(b)
    return [[sum((x*y for x, y in zip(row, column, strict=True)), Q())
             for column in columns] for row in a]


def _matvec(a, x):
    return [sum((u*v for u, v in zip(row, x, strict=True)), Q()) for row in a]


def _sub(a, b):
    return [[x-y for x, y in zip(row, other, strict=True)]
            for row, other in zip(a, b, strict=True)]


def _add(a, b):
    return [[x+y for x,y in zip(row,other,strict=True)] for row,other in zip(a,b,strict=True)]


def _flat(a):
    return [value for row in a for value in row]


def _certify(b, residuals, claims, *, independent=True):
    residuals = [Q(value) for value in residuals]
    if not residuals or any(residuals):
        raise ArithmeticError('Referência do desafio rejeitou o resultado: ' + claims)
    b.steps[-1]['certificate'] = {
        'kind':'challenge_reference_check', 'independent_of_producing_solver':independent,
        'arithmetic':'python_int_fraction' if independent else 'shared_symbolic_backend',
        'claims':[claims], 'residuals':[str(value) for value in residuals],
        'scope':'Apenas os invariantes listados, sem prova formal nem calibração de dificuldade.'}


def _link(b, *indices):
    b.steps[-1]['depends_on'] = list(indices)


def _dense_unimodular(n, shift=1):
    """Product of integer unit triangular matrices; determinant is one."""
    lower = [[Q(1 if i == j else ((i+j+shift) % 3-1 if i > j else 0))
              for j in range(n)] for i in range(n)]
    upper = [[Q(1 if i == j else ((i+2*j+shift) % 3-1 if i < j else 0))
              for j in range(n)] for i in range(n)]
    return _product(lower, upper)


@challenge('lyapunov', 'Controle matricial: Lyapunov denso e positividade',
           'teoria de controle e equações matriciais',
           'Matriz 7×7; sistema racional simétrico de 28 incógnitas; 49 resíduos e 7 menores.')
def lyapunov(b):
    n = 7
    c = _dense_unimodular(n, b.rng.randrange(5))
    p = _product(_transpose(c), c)
    for i in range(n):
        p[i][i] += 1
    a = [[Q(i+1, 8*n) if i == j else Q(1, 4*n) if j == i+1 else Q()
          for j in range(n)] for i in range(n)]
    q = _sub(p, _product(_product(_transpose(a), p), a))
    pairs = [(i,j) for i in range(n) for j in range(i,n)]
    operator = [[Q(i == k and j == l)-a[k][i]*a[l][j]
                 + (Q(i == l and j == k)-a[l][i]*a[k][j] if k != l else 0)
                 for k,l in pairs] for i,j in pairs]
    r = b.calc('solve_linear', 'Vetorizar a equação sem trocar a ordem de A e P.',
               matrix=_strings(operator), rhs=[str(q[i][j]) for i,j in pairs])
    solved = [[Q() for j in range(n)] for i in range(n)]
    for (i,j),value in zip(pairs,r['particular'],strict=True):
        solved[i][j] = solved[j][i] = Q(value)
    residual = _sub(_sub(solved, _product(_product(_transpose(a), solved), a)), q)
    _certify(b, [v for row in residual for v in row], 'P−AᵀPA=Q entrada por entrada.')
    for size in range(1, n+1):
        props = b.calc('matrix_properties', f'Menor principal de ordem {size}: critério de Sylvester.',
                       matrix=_strings([row[:size] for row in solved[:size]]))
        _link(b, 1)
        if Q(props['determinant']) <= 0:
            raise ArithmeticError('Menor principal não positivo')
    return (f'Resolva P−AᵀPA=Q e certifique P definida positiva. A={_strings(a)}; Q={_strings(q)}.',
            {'P':_strings(solved), 'residuals_zero':True, 'positive_principal_minors':n},
            'Vetorização racional, substituição direta e Sylvester; estabilidade vem da diagonal triangular de A.')


@challenge('arithmetic', 'Equações de Pell com soluções de dezenas de dígitos',
           'teoria dos números diofantina', 'Pell em D=61,109,181,661 e verificações inteiras exatas.')
def arithmetic(b):
    answers = []
    for d in (61, 109, 181, 661):
        r = b.calc('nt_pell', f'Encontrar a solução fundamental positiva para D={d}.', d=d)
        x, y = int(r['x']), int(r['y'])
        _certify(b, [x*x-d*y*y-1], 'Identidade inteira de Pell; esta referência não prova minimalidade.')
        answers.append({'D':d, 'x':str(x), 'y':str(y)})
    return ('Resolva x²−Dy²=1 em inteiros positivos para D=61,109,181,661. '
            'Compare o crescimento das soluções fundamentais obtidas por frações contínuas.',
            answers, 'Períodos de frações contínuas de raízes quadráticas e reconstrução inteira exata.')


@challenge('modules', 'Módulo abeliano por apresentação densa e fatores invariantes',
           'álgebra comutativa e módulos', 'Smith de apresentação inteira densa 8×8 com torção não coprima.')
def modules(b):
    n = 8
    invariant = [2, 6, 12, 60, 420, 840, 2520, 27720]
    u, v = _dense_unimodular(n, 1), _dense_unimodular(n, 3)
    diagonal = [[Q(invariant[i] if i == j else 0) for j in range(n)] for i in range(n)]
    a = _product(_product(u, diagonal), v)
    r = _advanced(b, 'modules.presentation', 'Extrair os fatores invariantes por Smith.', relations=_strings(a))
    if list(map(int,r['smith_diagonal'])) != invariant:
        raise ArithmeticError('Fatores invariantes divergem da apresentação unimodular')
    props = b.calc('matrix_properties', 'Conferir a ordem pelo determinante da apresentação.', matrix=_strings(a))
    _certify(b, [abs(Q(props['determinant']))-math.prod(invariant)],
             'Índice da rede pela construção unimodular e determinante.')
    return (f'Decomponha Z^8/im(A) em fatores invariantes e calcule a ordem. A={_strings(a)}.',
            {'presentation':r, 'expected_invariant_factors':invariant, 'order':str(math.prod(invariant))},
            'Equivalências unimodulares inteiras e Smith; ordem finita não determina sozinha a decomposição.')


@challenge('homological', 'Complexo denso com homotopia contrátil explícita',
           'álgebra homológica', 'Complexo 6←12←6, mudanças de base densas e identidade dh+hd=I.')
def homological(b):
    import sympy as sp
    n = 6
    s0 = sp.Matrix(_dense_unimodular(n, 1))
    s1 = sp.Matrix(_dense_unimodular(2*n, 2))
    s2 = sp.Matrix(_dense_unimodular(n, 3))
    i = sp.eye(n); z = sp.zeros(n)
    d1 = s0*i.row_join(z)*s1.inv()
    d2 = s1*z.col_join(i)*s2.inv()
    h0 = s1*i.col_join(z)*s0.inv()
    h1 = s2*z.row_join(i)*s1.inv()
    encode = lambda m: [[str(v) for v in row] for row in m.tolist()]
    ds = [encode(d1), encode(d2)]; dims = [n, 2*n, n]
    complex_result = _advanced(b, 'homological.complex', 'Calcular os grupos de homologia sobre Q.',
                               dimensions=dims, differentials=ds)
    identity = [encode(sp.eye(k)) for k in dims]
    zeros = [encode(sp.zeros(k)) for k in dims]
    r = _advanced(b, 'homological.homotopy', 'Verificar contração da identidade para o mapa zero.',
                  dimensions=dims, differentials=ds, left=identity, right=zeros,
                  homotopies=[encode(h0), encode(h1)])
    _link(b, 1)
    if not r['chain_homotopic'] or complex_result['betti_numbers'] != [0, 0, 0]:
        raise ArithmeticError('Contração inconsistente')
    a1,a2,c0,c1 = ([[Q(v) for v in row] for row in matrix.tolist()] for matrix in (d1,d2,h0,h1))
    residuals = _flat(_product(a1,a2))
    residuals += _flat(_sub(_product(a1,c0),_eye(n)))
    residuals += _flat(_sub(_add(_product(c0,a1),_product(a2,c1)),_eye(2*n)))
    residuals += _flat(_sub(_product(c1,a2),_eye(n)))
    _certify(b,residuals,'Produtos racionais independentes verificam d²=0 e dh+hd=I nos três graus.')
    return (f'Demonstre a aciclicidade do complexo C0←C1←C2 de dimensões {dims}, '
            f'com d1={ds[0]}, d2={ds[1]}; use h0={encode(h0)}, h1={encode(h1)}.',
            {'homology':complex_result, 'homotopy':r},
            'Mudanças de base racionais; d²=0, cálculo de núcleos/imagens e verificação matricial de dh+hd=I.')


@challenge('representations', 'Representação regular de S3 e sua decomposição',
           'teoria de representações', 'Seis matrizes 6×6, comutante de 36 incógnitas e três irreducíveis.')
def representations(b):
    group = list(permutations(range(3)))
    compose = lambda p, q: tuple(p[q[i]] for i in range(3))
    table = [[group.index(compose(p, q)) for q in group] for p in group]
    regular = [[[int(i == table[g][j]) for j in range(6)] for i in range(6)] for g in range(6)]
    sign = [(-1)**sum(p[i] > p[j] for i in range(3) for j in range(i+1, 3)) for p in group]
    # Basis (e0-e2,e1-e2) of the standard invariant plane.
    standard = []
    for p in group:
        columns = []
        for j in range(2):
            vector = [int(k == p[j])-int(k == p[2]) for k in range(3)]
            columns.append(vector[:2])
        standard.append(_transpose(columns))
    irreducibles = [[[[1]] for _ in group], [[[s]] for s in sign], standard]
    r = _advanced(b, 'representations.decompose', 'Decompor pelo produto interno dos caracteres.',
                  table=table, matrices=regular, irreducibles=irreducibles)
    commutant = _advanced(b, 'representations.intertwiners', 'Resolver TA_g=A_gT para o comutante regular.',
                         left=regular, right=regular)
    residuals = [commutant['dimension']-6]
    for raw in commutant['basis']:
        x = [[Q(v) for v in row] for row in raw]
        for a in regular:
            residuals += _flat(_sub(_product(x,a),_product(a,x)))
    _certify(b,residuals,'Todos os geradores retornados comutam com a ação regular; dimensão relatada igual a |S3|.')
    if r['multiplicities'] != [1, 1, 2]:
        raise ArithmeticError('Multiplicidades da representação regular incorretas')
    return ('Construa a representação regular esquerda de S3, decomponha-a sobre C e determine '
            f'o comutante. Elementos como permutações de (0,1,2): {group}; tabela={table}.',
            {'decomposition':r, 'commutant_dimension':commutant['dimension']},
            'Leis do grupo, representação regular, caracteres ortogonais e sistema de intertwiners; não inferir irreducibilidade sobre outros corpos.')


@challenge('lie', 'Álgebra de Takiff de sl2: radical, Killing e PBW',
           'álgebras de Lie', 'Seis geradores de sl2[ε]/ε², radical abeliano e palavra PBW de comprimento dez.')
def lie(b):
    base = [[[0]*3 for _ in range(3)] for _ in range(3)]
    for i,j,k,value in ((0,1,2,1),(2,0,0,2),(2,1,1,-2)):
        base[i][j][k] = value; base[j][i][k] = -value
    structure = [[[0]*6 for _ in range(6)] for _ in range(6)]
    for i in range(6):
        for j in range(6):
            degree = i//3+j//3
            if degree < 2:
                for k in range(3):
                    structure[i][j][3*degree+k] = base[i%3][j%3][k]
    r = _advanced(b, 'lie.structure', 'Verificar Jacobi, centro, Killing e séries estruturais.', structure=structure)
    pbw = _advanced(b, 'lie.pbw', 'Reordenar a palavra preservando termos de comutador.',
                    structure=structure, word=[5,2,4,1,3,0,2,1,0,2])
    decomposition = _advanced(b, 'lie.decomposition', 'Identificar radical e quociente semissimples.', structure=structure)
    killing = [[Q(v) for v in row] for row in r['killing_form']]
    _certify(b, _flat([row[3:] for row in killing])+_flat(killing[3:])+
             [r['derived_dimension']-6,len(r['center_basis']),len(decomposition['nilpotent_radical_basis'])-3],
             'Takiff é perfeita, tem centro zero, radical nilpotente tridimensional e Killing nula nas direções εsl2.')
    _link(b,1)
    return ('Considere g=sl2(Q)[ε]/(ε²) na base (e,f,h,εe,εf,εh), com '
            '[e,f]=h, [h,e]=2e, [h,f]=−2f. Calcule Jacobi, centro, Killing, radical e a forma '
            'PBW da palavra εh h εf f εe e h f e h. Distingua perfeito de semissimples.',
            {'structure':r, 'pbw':pbw, 'decomposition':decomposition},
            'Extensão de Takiff, representação adjunta e redução PBW; radical εsl2 abeliano com quociente sl2.')


@challenge('schemes', 'Cúbica torcida: eliminação, saturação e dimensão',
           'geometria algébrica', 'Eliminação de dois parâmetros em seis variáveis e saturação de ideal.')
def schemes(b):
    equations = ['x-s**3', 'y-s**2*t', 'z-s*t**2', 'w-t**3']
    elimination = _advanced(b, 'schemes.eliminate', 'Eliminar os parâmetros da parametrização homogênea.',
                            equations=equations, variables=['s','t','x','y','z','w'], remove=['s','t'])
    generators = elimination['generators']
    affine = _advanced(b, 'schemes.affine', 'Calcular base de Gröbner e dimensão do cone afim.',
                       equations=generators, variables=['x','y','z','w'])
    _link(b, 1)
    saturated = _advanced(b, 'schemes.saturate', 'Saturar o ideal parcial pela coordenada x.',
                          equations=['x*z-y**2', 'x*w-y*z'], variables=['x','y','z','w'], denominator='x')
    import sympy as sp
    from ..math._structured import expression
    x,y,z,w,s,t = sp.symbols('x y z w s t')
    checks = [sp.expand(expression(g,['x','y','z','w'])[0].subs(
        {x:s**3,y:s**2*t,z:s*t**2,w:t**3},simultaneous=True)) for g in generators]
    _certify(b,checks,'Geradores eliminados anulam a parametrização; esta checagem compartilha o CAS.',independent=False)
    _link(b,1)
    if affine['dimension'] != 2:
        raise ArithmeticError('Dimensão do cone da cúbica torcida inesperada')
    return ('Parta de (s³,s²t,st²,t³), elimine s,t e recupere o ideal da cúbica torcida. '
            'Compare com (xz−y²,xw−yz):x^∞ e calcule a dimensão do cone afim.',
            {'elimination':elimination, 'affine_cone':affine, 'saturation':saturated},
            'Eliminação lexicográfica e saturação por variável auxiliar sobre Q; imagem construtível e fecho não são confundidos.')


@challenge('topology', 'Homologia integral de T²∨RP²∨S²',
           'topologia algébrica', 'Triangulação com torção Z/2 e duas classes livres em grau dois.')
def topology(b):
    facets = []
    vertex = lambda i,j: (i%3)*3+j%3
    for i in range(3):
        for j in range(3):
            a,c,d,e = vertex(i,j),vertex(i+1,j),vertex(i,j+1),vertex(i+1,j+1)
            facets.extend([[a,c,e], [a,d,e]])
    # Six-vertex minimal triangulation of the real projective plane.
    rp = [(0,1,2),(0,1,3),(0,2,4),(0,3,5),(0,4,5),
          (1,2,5),(1,3,4),(1,4,5),(2,3,4),(2,3,5)]
    label = {0:0, 1:9, 2:10, 3:11, 4:12, 5:13}
    facets += [[label[v] for v in face] for face in rp]
    facets += [list(face) for face in combinations([0,14,15,16], 3)]
    homology, cohomology = [], []
    for degree in range(3):
        h = _advanced(b, 'topology.integral_homology', f'Homologia integral em grau {degree}.',
                      facets=facets, degree=degree)
        homology.append(h)
        cohomology.append(_advanced(b, 'topology.integral_cohomology', f'Cohomologia integral em grau {degree}.',
                                    facets=facets, degree=degree))
    if [h['free_rank'] for h in homology] != [1,2,2] or list(map(int, homology[1]['torsion'])) != [2]:
        raise ArithmeticError('Homologia da soma em cunha não confere')
    if [h['free_rank'] for h in cohomology] != [1,2,2] or list(map(int,cohomology[2]['torsion'])) != [2]:
        raise ArithmeticError('Torção cohomológica não foi transportada ao grau correto')
    return (f'Calcule H_k e H^k com coeficientes em Z, k=0,1,2, para a triangulação {facets}. '
            'Distingua torção homológica, cohomológica e números de Betti.',
            {'homology':homology, 'cohomology':cohomology},
            'Bordos simpliciais orientados, Smith integral e coeficientes universais; Betti racionais não detectam a torção.')


@challenge('geometry', 'Conexão em carta polinomial não ortogonal',
           'geometria diferencial', 'Pullback métrico 3×3 e derivada covariante com dependência não linear.')
def geometry(b):
    import sympy as sp
    u,v,w = sp.symbols('u v w')
    mapping = sp.Matrix([u,u*v,u*v*w]); jacobian = mapping.jacobian([u,v,w])
    metric = jacobian.T*jacobian
    encoded = [[str(sp.expand(x)) for x in row] for row in metric.tolist()]
    r = _advanced(b, 'geometry.pullback', 'Transportar a métrica euclidiana pela carta não ortogonal.',
                  metric=[[1,0,0],[0,1,0],[0,0,1]], coordinates=['x','y','z'],
                  new_coordinates=['u','v','w'], mapping=list(map(str,mapping)))
    covariant = _advanced(b, 'geometry.covariant', 'Calcular a conexão e ∇V no domínio regular.',
                          metric=encoded, coordinates=['u','v','w'],
                          vector=['u**2*v+w','v**2*w+u','u*w**2+v'])
    _link(b, 1)
    from ..math._structured import expression
    residuals = [sp.expand(expression(raw,['u','v','w'])[0]-metric[i,j])
                 for i,row in enumerate(r['metric']) for j,raw in enumerate(row)]
    _certify(b,residuals,'Métrica retornada igual a JᵀJ, sob verificação com o mesmo CAS.',independent=False)
    return ('Na carta (x,y,z)=(u,uv,uvw), determine a métrica induzida e a derivada covariante '
            'de V=(u²v+w,v²w+u,uw²+v). Trabalhe em u≠0 e v≠0, onde det(J)=u²v.',
            {'metric':r, 'covariant_derivative':covariant},
            'JᵀJ, Levi-Civita e correção de conexão; o domínio regular é parte obrigatória da solução.')


@challenge('forms', 'Naturalidade da derivada exterior sob aplicação polinomial',
           'cálculo exterior e formas diferenciais', '2-forma em dimensão quatro, pullback e identidade dF*=F*d.')
def forms(b):
    coordinates = ['x','y','z','t']
    omega = {'0,1':'x*z**2+t**3', '0,2':'y*t+x**2', '1,3':'z**2*x-y', '2,3':'x*y*t'}
    mapping = ['u+v*w', 'v+u*w', 'w+u*v', 'u*v*w']
    d_omega = _advanced(b, 'forms.derivative', 'Calcular dω preservando orientação e sinais.',
                        coordinates=coordinates, components=omega)
    pull = _advanced(b, 'forms.pullback', 'Calcular F*ω pela matriz jacobiana da aplicação.',
                     source_coordinates=['u','v','w'], target_coordinates=coordinates,
                     mapping=mapping, components=omega)
    left = _advanced(b, 'forms.derivative', 'Diferenciar a forma transportada: d(F*ω).',
                     coordinates=['u','v','w'], components=pull)
    _link(b, 2)
    right = _advanced(b, 'forms.pullback', 'Transportar a derivada: F*(dω).',
                      source_coordinates=['u','v','w'], target_coordinates=coordinates,
                      mapping=mapping, components=d_omega)
    _link(b, 1)
    if left != right:
        raise ArithmeticError('Naturalidade da derivada exterior violada')
    integral = _advanced(b, 'forms.integrate', 'Integrar a 3-forma no cubo orientado.',
                         coordinates=['u','v','w'], components=left, bounds=[[0,1],[0,1],[0,1]])
    _link(b, 3)
    return (f'Para ω={omega} e F(u,v,w)={mapping}, calcule dω, F*ω e compare dF*ω com F*dω. '
            'Integre a forma resultante no cubo unitário com orientação du∧dv∧dw.',
            {'pullback':pull, 'commuting_derivative':left, 'integral':integral},
            'Álgebra exterior exata, menores orientados de Jacobiano e integração polinomial; comparação usa o mesmo CAS.')


@challenge('stochastic', 'Gerador de Itô tridimensional com ruído multiplicativo acoplado',
           'cálculo estocástico', 'Hessiana polinomial de grau seis e covariação não diagonal de três Brownianos.')
def stochastic(b):
    import sympy as sp
    from ..math._structured import expression
    variables = ['x','y','z']; x,y,z = sp.symbols('x y z')
    function = '(x**2+x*y+2*y**2+z**2)**3+x*y*z**2'
    drift = ['y-x**3', 'z-x*y', 'x-z**3']
    diffusion = [['x','y','1'], ['0','x+z','y'], ['z','1','x-y']]
    r = _advanced(b, 'stochastic.ito', 'Calcular gradiente, Hessiana, BBᵀ e deriva transformada.',
                  function=function, drift=drift, diffusion=diffusion, variables=variables)
    jets = _advanced(b, 'autograd.jet', 'Verificar derivadas mistas até ordem quatro no ponto (1,−1,2).',
                     source=function, variables=variables, point=[1,-1,2], order=4)
    _link(b, 1)
    # Evaluate the generator separately at a rational point, without assuming
    # independent noise components imply a diagonal state covariance BB^T.
    f,_ = expression(function, variables)
    mu = sp.Matrix([expression(v, variables)[0] for v in drift])
    sigma = sp.Matrix([[expression(v, variables)[0] for v in row] for row in diffusion])
    g = sum(mu[i]*sp.diff(f, s) for i,s in enumerate((x,y,z)))
    g += sum((sigma*sigma.T)[i,j]*sp.diff(f,s,t)/2
             for i,s in enumerate((x,y,z)) for j,t in enumerate((x,y,z)))
    expected = str(sp.expand(g))
    returned,_ = expression(r['dt'],variables)
    _certify(b,[sp.expand(returned-g)],'Deriva de Itô igual à contração completa BBᵀ:Hess/2 + μ·grad, no mesmo CAS.',independent=False)
    return (f'Para dX=μdt+B dW, com μ={drift}, B={diffusion}, calcule o gerador de Itô '
            f'de f={function} e o jet de ordem quatro em (1,−1,2). W tem três componentes independentes.',
            {'ito':r, 'jet_at_point':jets, 'symbolic_generator_reference':expected},
            'L f=μ·∇f+tr(BBᵀ Hess f)/2; coeficientes locais, sem alegar solução global ou não explosão.')


@challenge('variations', 'Campos acoplados com cinética não linear e potencial sêxtico',
           'cálculo das variações', 'Duas equações de campo em três coordenadas e Hessiana de Legendre 6×6.')
def variations(b):
    density = ('(1+u**2+v**2)*(u_d0**2+2*u_d1**2+3*u_d2**2+'
               '2*v_d0**2+3*v_d1**2+4*v_d2**2)/2+'
               'u_d0*v_d1-u_d1*v_d0+(u**2+v**2)**3/6+x*u+y*v')
    r = _advanced(b, 'variations.density', 'Extrair Euler–Lagrange, fluxos de borda e Hessiana de Legendre.',
                  lagrangian=density, coordinates=['x','y','z'], fields=['u','v'])
    hessian = r['legendre_hessian']
    if len(hessian) != 6 or any(hessian[i][j] != hessian[j][i] for i in range(6) for j in range(6)):
        raise ArithmeticError('Hessiana de Legendre não simétrica')
    return (f'Derive as equações de Euler–Lagrange dos campos u,v para a densidade L={density}. '
            'Determine os fluxos naturais de bordo e discuta o alcance local da condição de Legendre.',
            r, 'Derivadas totais dos jets e variações com termos de fronteira; Hessiana positiva não prova mínimo global.')


@challenge('residues', 'Polos múltiplos e teorema global dos resíduos',
           'análise complexa', 'Quatro polos de multiplicidades 4,3,2,2; expansão de Laurent e cancelamento global.')
def residues(b):
    source = '(z**7+3*z**5-2*z**2+7)/((z-1)**4*(z+2)**3*(z-3)**2*(z+4)**2)'
    answers = []
    for point in (1,-2,3,-4):
        r = _advanced(b, 'complex.meromorphic', f'Extrair parte principal e resíduo no polo {point}.',
                      source=source, variable='z', point=str(point), order=4)
        answers.append({'point':point, **r})
    total = sum(Q(r['residue']) for r in answers)
    _certify(b, [total], 'Soma dos resíduos finitos zero: decaimento O(z^−4) no infinito.')
    _link(b,1,2,3)
    inside = Q(answers[0]['residue'])+Q(answers[1]['residue'])
    return (f'Para f(z)={source}, determine os resíduos e as partes principais dos quatro polos; '
            'calcule ∮_|z|=5/2 f(z)dz e confira o resíduo no infinito.',
            {'local_expansions':answers, 'contour_integral':f'2*pi*i*({inside})', 'sum_of_residues':'0'},
            'Laurent local, ordem dos polos e teorema dos resíduos; a circunferência não atravessa polos.')


@challenge('hilbert', 'Projeção de Hilbert ponderada com base racional densa',
           'análise funcional', 'Projeção de dimensão cinco em Q^10; ortogonalidade ponderada e Pitágoras.')
def hilbert(b):
    rows = [[Q((j+1)**i, (i+1)*(j+2)) for j in range(10)] for i in range(5)]
    target = [Q((-1)**j*(j*j+3), j+1) for j in range(10)]
    weights = [Q(j+1, j+2) for j in range(10)]
    r = b.calc('functional_analysis', 'Resolver o sistema de Gram e verificar a projeção ortogonal.',
               basis=_strings(rows), target=list(map(str,target)), weights=list(map(str,weights)))
    coefficients = list(map(Q,r['coefficients'])); projection = list(map(Q,r['projection']))
    membership = [projection[j]-sum(coefficients[i]*rows[i][j] for i in range(5)) for j in range(10)]
    residual = [t-p for t,p in zip(target,projection,strict=True)]
    orthogonal = [sum(weights[j]*row[j]*residual[j] for j in range(10)) for row in rows]
    _certify(b,membership+orthogonal,'Projeção pertence ao subespaço declarado e seu resíduo é ortogonal a toda a base.')
    return (f'Em Q^10 com produto interno ⟨x,y⟩=Σw_j x_jy_j, projete t sobre o espaço gerado '
            f'pelas linhas B={_strings(rows)}. t={list(map(str,target))}; w={list(map(str,weights))}. '
            'Verifique ortogonalidade e Pitágoras sem arredondamento.', r,
            'Sistema de Gram racional definido positivo; modelo finito de Hilbert, sem extrapolar para dimensão infinita.')


@challenge('distributions', 'Distribuições singulares de alta ordem e dualidade da derivada',
           'teoria das distribuições', 'Doze derivadas de Dirac até ordem dez e função-teste polinomial de grau vinte.')
def distributions(b):
    terms = [{'weight':str(Q((-1)**i*(i+1), i+2)), 'point':str(Q(i-5, 3)), 'order':i%8}
             for i in range(12)]
    source = 'x**20-3*x**17+2*x**11-x**7+5*x**3-7'
    derivative = _advanced(b, 'distributions.derivative', 'Construir D³T como distribuição.', terms=terms, order=3)
    a = _advanced(b, 'distributions.pairing', 'Calcular ⟨D³T,φ⟩ pelos valores dos jets nos suportes.',
                  terms=derivative, test_function=source)
    _link(b, 1)
    # Direct rational polynomial derivative evaluation, separate from the CAS.
    coefficients = {20:1, 17:-3, 11:2, 7:-1, 3:5, 0:-7}
    def evaluate_derivative(order, point):
        return sum((Q(c*math.factorial(k), math.factorial(k-order))*point**(k-order)
                    for k,c in coefficients.items() if k >= order), Q())
    expected = sum((Q(t['weight'])*(-1)**(t['order']+3)*evaluate_derivative(t['order']+3, Q(t['point']))
                    for t in terms), Q())
    _certify(b, [Q(a['pairing'])-expected], 'Dualidade ⟨D³T,φ⟩=−⟨T,φ‴⟩ por fórmula polinomial racional.')
    fourier = _advanced(b, 'distributions.fourier', 'Transportar derivadas para potências de iω na transformada.', terms=terms)
    return (f'Considere T com termos (peso,ponto,ordem)={terms} e φ={source}. '
            'Calcule ⟨D³T,φ⟩, verifique a dualidade e determine F[T].',
            {'pairing_D3':a['pairing'], 'fourier':fourier},
            'Ação de distribuições pontuais no germe suave; sinais (−1)^k e convenção F[T](ω)=⟨T,e^(−iωx)⟩ explícitos.')


@challenge('markov', 'Absorção concorrente e recompensas de cadeia racional',
           'probabilidade e processos de Markov', 'Oito estados, dois absorventes, momentos condicionais e Bellman descontado.')
def markov(b):
    n = 8; transition = []
    for i in range(n-2):
        weights = [Q(((i+2)*(j+3)+j*j)%11+1) for j in range(n)]
        transition.append([w/sum(weights) for w in weights])
    transition += [[Q(i == j) for j in range(n)] for i in (6,7)]
    first = b.calc('markov_hitting', 'Probabilidade e dois momentos de atingir o absorvente 6.',
                   transition=_strings(transition), targets=[6])
    second = b.calc('markov_hitting', 'Probabilidade e dois momentos de atingir o absorvente 7.',
                    transition=_strings(transition), targets=[7])
    checks = [Q(x['probability'])+Q(y['probability'])-1
              for x,y in zip(first['states'],second['states'],strict=True)]
    for result,target in ((first,6),(second,7)):
        h = [Q(s['probability']) for s in result['states']]
        g = [Q(s['joint_first_moment']) for s in result['states']]
        m = [Q(s['joint_second_moment']) for s in result['states']]
        ph,pg,pm = (_matvec(transition,v) for v in (h,g,m))
        for i in range(n):
            if i != target:
                checks += [h[i]-ph[i],g[i]-h[i]-pg[i],m[i]-h[i]-2*pg[i]-pm[i]]
    _certify(b,checks,'Partição das absorções e recorrências de primeiro passo dos momentos conjuntos de ordens um e dois.')
    _link(b,1)
    reward = b.calc('markov_rewards', 'Resolver a equação de Bellman com desconto 17/19.',
                    transition=_strings(transition), rewards=[i*i-3*i+1 for i in range(n)], discount='17/19')
    return (f'Para P={_strings(transition)}, calcule as probabilidades de absorção e os dois primeiros '
            'momentos condicionais para os alvos 6 e 7. Resolva também v=r+(17/19)Pv, r_i=i²−3i+1.',
            {'target_6':first, 'target_7':second, 'discounted_rewards':reward},
            'Primeiro passo racional; distinguir esperança incondicional infinita de esperança condicional finita.')


@challenge('networks', 'Fluxo máximo racional com certificado por todos os cortes',
           'teoria dos grafos', 'Doze vértices, ciclos e capacidades racionais; enumeração independente de 1.024 cortes.')
def networks(b):
    vertices = ['s']+[f'v{i}' for i in range(10)]+['t']
    edges = []
    for i in range(10):
        edges += [['s',f'v{i}',str(Q(2*i+7, i+2))], [f'v{i}','t',str(Q(3*i+5, i+3))]]
        for j in range(10):
            if i != j and (i+j)%3 == 0:
                edges.append([f'v{i}',f'v{j}',str(Q(i+j+1, abs(i-j)+2))])
    r = b.calc('graph_max_flow', 'Calcular fluxo e corte mínimo, com referência por enumeração exaustiva.',
               vertices=vertices, edges=edges, source='s', sink='t')
    return (f'Determine fluxo máximo e corte mínimo no digrafo com vértices {vertices} e '
            f'arestas (origem,destino,capacidade)={edges}. Não presuma aciclicidade.', r,
            'Caminhos aumentantes com aritmética racional e comparação com os 2^10 cortes s–t possíveis.')


@challenge('duality', 'Dualidade linear em dimensão dez com complementaridade',
           'otimização convexa', 'Dez variáveis, dezoito restrições racionais e certificado primal-dual exato.')
def duality(b):
    n = 10
    active = _dense_unimodular(n, 4)
    extra = [[Q((2*i+j)%7-3, j+1) for j in range(n)] for i in range(8)]
    a = active+extra
    x = [Q(i+1, i+2) for i in range(n)]
    lower = _matvec(a,x)
    for i in range(n, len(a)):
        lower[i] -= Q(i+1, 7)
    y = [Q(i+2, i+3) for i in range(n)]+[Q()]*8
    objective = _matvec(_transpose(a),y)
    r = _advanced(b, 'optimization.certificate', 'Conferir viabilidade, folgas e lacuna primal-dual.',
                  objective=list(map(str,objective)), matrix=_strings(a), lower=list(map(str,lower)),
                  point=list(map(str,x)), dual=list(map(str,y)))
    value = sum(c*v for c,v in zip(objective,x,strict=True))
    dual_value = sum(c*v for c,v in zip(lower,y,strict=True))
    slack = [v-w for v,w in zip(_matvec(a,x),lower,strict=True)]
    if min(slack) < 0 or min(x+y) < 0:
        raise ArithmeticError('Referência primal-dual inviável')
    complementarity = [s*v for s,v in zip(slack,y,strict=True)]
    _certify(b, [value-dual_value, Q(r['duality_gap'])]+complementarity,
             'Viabilidade construída, complementaridade exata e igualdade dos objetivos primal e dual.')
    if not r['optimal']:
        raise ArithmeticError('Certificado ótimo recusado')
    return (f'Minimize cᵀx sujeito a Ax≥b e x≥0. A={_strings(a)}; b={list(map(str,lower))}; '
            f'c={list(map(str,objective))}. Certifique x*={list(map(str,x))} e y*={list(map(str,y))}.',
            {'certificate':r, 'optimal_value':str(value)},
            'Dual max bᵀy com Aᵀy≤c,y≥0; viabilidade e lacuna nula provam otimalidade do par fornecido.')


@challenge('pade', 'Padé [10/10] da exponencial com 21 coeficientes casados',
           'teoria da aproximação', 'Sistema racional de Padé e 21 identidades de convolução formal.')
def pade(b):
    r = b.calc('analysis_pade', 'Construir o aproximante racional [10/10] de exp(x).',
               numerator_degree=10, denominator_degree=10)
    p,q = list(map(Q,r['numerator'])),list(map(Q,r['denominator']))
    residuals = [sum(q[j]*Q(1,math.factorial(k-j)) for j in range(min(k,10)+1))
                 - (p[k] if k < len(p) else Q()) for k in range(21)]
    _certify(b,residuals,'Todos os 21 coeficientes de Q10 exp−P10 se anulam, por convolução racional direta.')
    return ('Construa P10/Q10 para exp(x), normalizado por Q10(0)=1, e confira '
            'Q10(x)exp(x)−P10(x)=O(x^21). Separe casamento formal de séries de uma cota global de erro.',
            r, 'Eliminação racional e convolução dos coeficientes de Taylor; aproximação formal não certifica erro global.')


@challenge('fredholm', 'Fredholm exato com núcleo polinomial denso de posto oito',
           'equações integrais', 'Núcleo 8×8, solução polinomial de grau onze e doze resíduos de coeficientes.')
def fredholm(b):
    n = 8
    kernel = [[Q((-1)**(i+j)*(i+1), 100*(i+j+2)*(j+1)) for j in range(n)] for i in range(n)]
    coefficients = [Q((-1)**k*(k+1), k+2) for k in range(12)]
    moment = [Q(1,k+1) for k in range(24)]
    image = [sum(kernel[i][j]*moment[j+k]*coefficients[k] for j in range(n) for k in range(12))
             if i < n else Q() for i in range(12)]
    rhs = [v-w for v,w in zip(coefficients,image,strict=True)]
    r = b.calc('integral_equations', 'Resolver a equação por momentos polinomiais exatos.',
               kernel=_strings(kernel), rhs=list(map(str,rhs)), lower=0, upper=1, coupling=1)
    solved = list(map(Q,r['coefficients']))
    residuals = [solved[i]-rhs[i]-(sum(kernel[i][j]*moment[j+k]*solved[k]
                                    for j in range(n) for k in range(12)) if i<n else Q())
                 for i in range(12)]
    _certify(b, residuals, 'Equação integral original por integração monomial e igualdade de todos os coeficientes.')
    contraction_bound = sum(abs(kernel[i][j])/Q(j+1) for i in range(n) for j in range(n))
    if contraction_bound >= 1:
        raise ArithmeticError('Não foi estabelecida a contração no espaço contínuo')
    r = {**r,'operator_norm_upper_bound_sup':str(contraction_bound),
         'uniqueness':'Em C[0,1] pela série de Neumann, pois a cota racional da norma do operador é menor que um.'}
    return (f'Resolva u(x)=f(x)+∫_0^1 K(x,t)u(t)dt, com K(x,t)=Σ K_ij x^i t^j, '
            f'K={_strings(kernel)}, e f com coeficientes crescentes {list(map(str,rhs))}. '
            'Prove a identidade no espaço polinomial e informe o alcance da unicidade.', r,
            'Redução de posto finito a sistema de momentos; resíduo polinomial exato em vez de teste em poucos pontos.')


ADVANCED_20 = tuple(CHALLENGES)
