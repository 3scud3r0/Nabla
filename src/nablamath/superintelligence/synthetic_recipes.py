"""Closed parameterized recipes over existing Nabla mathematical operations.

The finite scope of each operation is inherited from the calculation catalog.
These recipes are computational exercises, not complete theories of their areas.
"""
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Recipe:
    name: str
    title: str
    area: str
    make: Callable
    method: str


RECIPES = {}


def _add(name, title, area, make, method, *, advanced=False):
    def request(t, d):
        p = make(t, d)
        return {'operation':'advanced_math','arguments':{'action':name,'parameters':p}} if advanced else {'operation':name,'arguments':p}
    RECIPES[name] = Recipe(name, title, area, request, method)


def _advanced(name, title, area, make, method):
    _add(name, title, area, make, method, advanced=True)


# t changes mathematical inputs. A few canonical structures are intentionally
# fixed: their whole constructor family stays in a single dataset partition.
_add('matrix_properties','Determinante, posto e polinômio característico','linear_algebra',lambda t,d: {'matrix':[[t,1,0],[0,t+1,2],[0,0,t+2]]},'Triangularidade; produto diagonal e det(lambda I-A).')
_add('matrix_inverse','Inversão racional não diagonal','linear_algebra',lambda t,d: {'matrix':[[t,1],[1,t+1]]},'Eliminação racional e produtos com a inversa.')
_add('solve_linear','Sistema linear com unicidade','linear_algebra',lambda t,d: {'matrix':[[t,1],[1,t+1]],'rhs':[t*t+1,2*t+1]},'Eliminação exata e substituição na equação original.')
_add('least_squares','Mínimos quadrados multivariados ponderados','statistics',lambda t,d: {'predictors':[[0,0],[1,0],[0,1],[1,1],[2,1]],'response':[t,t+1,t+2,t+4,t+5],'weights':[1,2,1,3,2]},'Equações normais e ortogonalidade ponderada dos resíduos.')
_add('linear_regression','Regressão racional com resíduos','statistics',lambda t,d: {'x':[0,1,2,3,4],'y':[t,t+2,t+3,t+7,t+8]},'Covariância, variância e minimização da soma de quadrados.')
_add('quadratic_optimize','Otimização quadrática convexa','optimization',lambda t,d: {'hessian':[[2,1],[1,4]],'linear':[-t,-2*t]},'Gradiente nulo e Hessiana definida positiva.')
_add('rational_limit','Limite e singularidade removível','calculus',lambda t,d: {'source':f'(x**2-{t*t})/(x-{t})','point':t},'Fatoração no domínio perfurado; preservar o ponto excluído.')
_add('certified_integral','Quadratura com certificado de resto','calculus',lambda t,d: {'coefficients':[t,-2,0,1,3],'lower':'-1/2','upper':'3/2','tolerance':'1/1000','max_pieces':128},'Integração e cota racional do resto; inclusão não é valor pontual.')
_add('certified_function','Inclusão racional da exponencial','numerical',lambda t,d: {'kind':'exp','value':f'{t}/100','tolerance':'1/100000000','max_terms':128},'Taylor com cauda limitada; aproximação não é identidade.')
_add('polynomial_range','Envoltória de Bernstein','calculus',lambda t,d: {'coefficients':[t,-3,2,-1,1],'lower':-1,'upper':2,'subdivisions':4},'Inclusão exata da imagem; não presumir extremos atingidos.')
_add('markov_hitting','Absorção e momentos condicionais','probability',lambda t,d: {'transition':[['1/2','1/4','1/4'],[0,f'{t}/{t+1}',f'1/{t+1}'],[0,0,1]],'targets':[2]},'Sistemas de primeiro passo para probabilidade e tempo de chegada.')
_add('markov_stationary','Classes fechadas e medidas estacionárias','probability',lambda t,d: {'transition':[[f'{t}/{t+1}',f'1/{t+1}',0],['1/3','2/3',0],[0,0,1]]},'Classes recorrentes; pi P=pi e normalização racional.')
_add('markov_rewards','Equação de Bellman descontada','probability',lambda t,d: {'transition':[['1/2','1/2'],['1/3','2/3']],'rewards':[t,-1],'discount':'3/4'},'Resolver (I-gamma P)v=r; conferir resíduo zero.')
_add('bayes','Atualização bayesiana finita','probability',lambda t,d: {'prior':{'H0':'1/3','H1':'2/3'},'likelihood':{'H0':f'1/{t+1}','H1':'3/4'}},'Dividir pesos pela evidência positiva; posterior unitária.')
_add('nt_factorization','Fatoração e funções aritméticas','number_theory',lambda t,d: {'n':2**(d+2)*27*(t+1)},'Reconstrução por fatores primos, phi, mu e divisores.')
_add('nt_modular_roots','Raízes quadráticas em corpo primo','number_theory',lambda t,d: {'a':t*t%101,'prime':101},'Tonelli–Shanks e substituição modular.')
_add('nt_discrete_log','Logaritmo discreto BSGS','number_theory',lambda t,d: {'base':2,'target':pow(2,t,101),'prime':101},'Busca finita no subgrupo e potência modular de verificação.')
_add('nt_pell','Pell por frações contínuas','number_theory',lambda t,d: {'d':[2,3,5,6,7,10,11,13,17,19][t%10]},'Convergentes de sqrt(D); x²-Dy²=1.')
_add('ff_extension','Inverso, traço e norma em F9','algebra',lambda t,d: {'prime':3,'modulus':[1,0,1],'element':[t%3,1]},'Redução polinomial, Frobenius e grupo multiplicativo.')
_add('analysis_root','Bisseção racional certificada','calculus',lambda t,d: {'coefficients':[-t,0,1],'lower':0,'upper':t+1,'steps':16+d},'Mudança de sinal e intervalos encaixados; existência não prova unicidade.')
_add('analysis_pade','Aproximação de Padé','analysis',lambda t,d: {'numerator_degree':2+t%3,'denominator_degree':2+d%3},'Anular a diferença de séries até a ordem declarada.')
_add('graph_assignment','Atribuição ótima exata','optimization',lambda t,d: {'costs':[[t,2,7],[4,t+1,3],[5,1,t+2]]},'Programação dinâmica sobre subconjuntos e colunas distintas.')
_add('graph_max_flow','Fluxo máximo e corte mínimo','discrete',lambda t,d: {'vertices':['s','a','b','z'],'edges':[['s','a',t],['s','b',t+1],['a','b',2],['a','z',t+2],['b','z',t]],'source':'s','sink':'z'},'Capacidades, conservação e igualdade fluxo/corte.')
_add('graph_bellman_ford','Caminhos mínimos com pesos negativos','discrete',lambda t,d: {'vertices':['s','a','b'],'edges':[['s','a',t],['a','b',-2],['s','b',t+1]],'source':'s'},'Relaxamentos exatos e recusa de ciclos negativos alcançáveis.')
_add('graph_matching','Matching e cobertura mínima','discrete',lambda t,d: {'left':[f'a{t}','b','c'],'right':['x','y','z'],'edges':[[f'a{t}','x'],[f'a{t}','y'],['b','y'],['c','z']]},'Caminhos aumentantes e igualdade de König.')
_add('prob_poisson_binomial','Bernoulli não idênticas','probability',lambda t,d: {'probabilities':['1/2',f'1/{t+1}','2/3','3/4']},'Produto dos geradores; normalização e momentos.')
_add('prob_dirichlet','Posterior Dirichlet-categórica','probability',lambda t,d: {'alpha':[1,2,3],'counts':[t,t+1,2]},'Somar contagens e normalizar parâmetros preditivos.')
_add('prob_hypergeometric','Amostragem sem reposição','probability',lambda t,d: {'population':t+20,'successes':t+5,'draws':5,'observed':2},'Razão de coeficientes binomiais no suporte admissível.')
_add('beta_binomial','Posterior Beta-binomial','probability',lambda t,d: {'successes':t,'trials':t+7,'alpha':2,'beta':3},'Atualização conjugada e parametrização da probabilidade latente.')

_advanced('representations.intertwiners','Comutante e intertwiners','algebra',lambda t,d: {'left':[[[1,0],[0,1]],[[0,1],[1,0]]],'right':[[[1,0],[0,1]],[[0,1],[1,0]]]},'Resolver TA_g=B_gT como sistema homogêneo.')
_advanced('modules.presentation','Smith e torção de módulo','algebra',lambda t,d: {'relations':[[t+1,0],[0,2*(t+1)]]},'Decompor o módulo abeliano finitamente apresentado sobre Z.')
_advanced('modules.homomorphism','Núcleo e imagem racional','algebra',lambda t,d: {'matrix':[[1,t,0],[2,2*t,0]]},'Posto-nulidade e bases por eliminação.')
_advanced('homological.complex','Homologia de complexo com d²=0','algebra',lambda t,d: {'dimensions':[1,2,1],'differentials':[[[t,0]],[[0],[t+1]]]},'Conferir composição nula e calcular ker(d)/im(d).')
_advanced('homological.ext_tor','Ext e Tor de grupos cíclicos','algebra',lambda t,d: {'m':6*t,'n':9*t},'Resolução livre cíclica e máximo divisor comum.')
_advanced('schemes.affine','Esquema afim de curva cúbica','geometry',lambda t,d: {'equations':[f'y**2-x**3-{t}'],'variables':['x','y']},'Gröbner e dimensão no perfil finito declarado.')
_advanced('schemes.eliminate','Eliminação em ideal afim','geometry',lambda t,d: {'equations':[f'x-y-{t}','y*y-1'],'variables':['x','y'],'remove':['x']},'Ordem de eliminação; ideal projetado não é a imagem real.')
_advanced('schemes.saturate','Saturação por denominador','geometry',lambda t,d: {'equations':[f'x*(y-{t})'],'variables':['x','y'],'denominator':'x'},'Remover componentes em x=0 por variável auxiliar.')
_advanced('schemes.primary','Decomposição primária univariada','geometry',lambda t,d: {'polynomial':f'(x-{t})**2*(x+1)**3'},'Fatores, multiplicidades e estrutura não reduzida.')
_advanced('forms.derivative','Derivada exterior polinomial','geometry',lambda t,d: {'coordinates':['x','y','z'],'components':{'0':f'{t}*y*z','1':'x*z','2':'x*y'}},'Antissimetria do produto exterior e identidade d²=0.')
_advanced('forms.pullback','Pullback por imersão polinomial','geometry',lambda t,d: {'source_coordinates':['u','v'],'target_coordinates':['x','y','z'],'mapping':['u','v',f'{t}*u*v'],'components':{'0,2':'y','1,2':'x'}},'Substituição simultânea e menores orientados do Jacobiano.')
_advanced('forms.integrate','Integral orientada de forma','geometry',lambda t,d: {'coordinates':['x','y'],'components':{'0,1':f'{t}*x*y+x**2'},'bounds':[[0,1],[0,2]]},'Integral iterada exata com orientação declarada.')
_advanced('bundles.connection','Transformação de calibre de conexão','geometry',lambda t,d: {'coordinates':['x'],'connection':[[['0']]],'gauge':[[f'exp({t}*x)']]},'g^-1 A g+g^-1 dg no domínio inversível.')
_advanced('distributions.pairing','Derivadas da distribuição de Dirac','analysis',lambda t,d: {'terms':[{'weight':t,'point':1,'order':2},{'weight':2,'point':0,'order':1}],'test_function':'x**4+x'},'delta^(k)(phi)=(-1)^k phi^(k)(a).')
_advanced('distributions.fourier','Fourier de distribuições pontuais','analysis',lambda t,d: {'terms':[{'weight':t,'point':1,'order':2}]},'Convenção de frequência e sinal na transformação de derivadas.')
_advanced('sobolev.norm','Norma de Sobolev com traço nulo','analysis',lambda t,d: {'source':f'{t}*x*(1-x)','order':2,'lower':0,'upper':1},'Somar normas L² das derivadas fracas polinomiais.')
_advanced('homotopy.fundamental_group','Grupo fundamental de grafo','topology',lambda t,d: {'facets':[[t,t+1],[t+1,t+2],[t,t+2]]},'Árvore maximal, geradores livres e relações presentes.')
_advanced('topology.integral_homology','Homologia integral e torção','topology',lambda t,d: {'facets':[[t,t+1],[t+1,t+2],[t,t+2]],'degree':1},'Bordos sobre Z e Smith; Betti racional não detecta torção.')
_advanced('topology.cup','Produto cup de cocadeias','topology',lambda t,d: {'facets':[[0,1,2]],'left_degree':1,'left':[t,2,3],'right_degree':1,'right':[4,5,6]},'Convenção de Alexander–Whitney e orientação de vértices.')
_advanced('order.boolean','Álgebra booleana finita','order_theory',lambda t,d: {'universe_size':8,'left':t%256,'right':85},'Reticulado e complemento relativo ao universo finito.')
_advanced('lie.roots','Sistema de raízes A2','algebra',lambda t,d: {'cartan':[[2,-1],[-1,2]]},'Reflexões simples e fechamento finito das raízes.')
_advanced('lie.pbw','Redução de Poincaré–Birkhoff–Witt','algebra',lambda t,d: {'structure':[[[0,0],[0,t]],[[0,-t],[0,0]]],'word':[1,0,1,0]},'Reordenar palavras com correções pelo colchete.')
_advanced('k.higher_finite_field','K-teoria superior de corpo finito','algebra',lambda t,d: {'prime':3,'degree':2*(t%4)+1},'Perfil de Quillen para corpos finitos, não K-teoria geral.')
_advanced('measure.radon_nikodym','Radon–Nikodym em espaço atômico','analysis',lambda t,d: {'reference':[1,2,0],'target':[t,2*t,0]},'Continuidade absoluta e densidade nos átomos positivos.')
_advanced('measure.continuous','Expectativa sob densidade contínua','analysis',lambda t,d: {'density':'2*x','integrand':f'x**{2+t%4}','lower':0,'upper':1},'Normalização e integral ponderada no intervalo indicado.')
_advanced('transforms.symbolic','Laplace simbólica e convergência','analysis',lambda t,d: {'kind':'laplace','source':f'x**{t%4+2}*exp(-x)','variable':'x','parameter':'s'},'Integral imprópria e região de convergência.')
_advanced('complex.holomorphic_jet','Jet holomorfo multivariado','complex_analysis',lambda t,d: {'sources':[f'z**2+{t}*w','z*w+w**2'],'variables':['z','w'],'point':[1,2],'order':2},'Jacobiano e critério de inversão local, não global.')
_advanced('complex.meromorphic','Parte principal e resíduo','complex_analysis',lambda t,d: {'source':f'exp(x)/(x-{t})**2','variable':'x','point':t,'order':3},'Laurent no ponto isolado e coeficiente de ordem -1.')
_advanced('functional.series','Norma e resto de série ortogonal','analysis',lambda t,d: {'coefficients':[1,f'1/{t+1}','1/3'],'weights':[1,2,3],'tail_bound':'1/100'},'Pitágoras ponderado e cauda como hipótese fornecida.')
_advanced('variations.fields','Equações de Euler–Lagrange','calculus',lambda t,d: {'lagrangian':f'(q_1**2-{t}*q_0**2)/2','coordinates':['t'],'fields':['q']},'Derivada variacional e convenção de índices dos jets.')
_advanced('variations.density','Equação variacional de campo','calculus',lambda t,d: {'lagrangian':f'(u_d0**2+u_d1**2+{t}*u**2)/2','coordinates':['x','y'],'fields':['u']},'Divergência do momento variacional e termo potencial.')
_advanced('geometry.pullback','Métrica induzida em nova carta','geometry',lambda t,d: {'metric':[[1,0],[0,1]],'coordinates':['x','y'],'new_coordinates':['u','v'],'mapping':['u',f'{t}*v']},'J^T g J e assinatura em cartas regulares.')
_advanced('geometry.covariant','Derivada covariante curvilínea','geometry',lambda t,d: {'metric':[[1,0],[0,'r**2']],'coordinates':['r','theta'],'vector':[f'{t}*r','r*theta']},'Levi-Civita e não degenerescência r != 0.')
_advanced('galois.polynomial','Grupo de Galois de cúbica','algebra',lambda t,d: {'coefficients':[-(2+t%4),0,0,1]},'Fatoração, discriminante e perfil de grau suportado.')
_advanced('fields.primitive','Elemento primitivo de extensão','algebra',lambda t,d: {'radicals':['sqrt(2)','sqrt(3)']},'Polinômio mínimo e grau da extensão composta.')
_advanced('linear.algebraic_spectral','Espectro sobre fecho algébrico','linear_algebra',lambda t,d: {'matrix':[[0,t+1],[1,0]]},'Multiplicidades algébricas e dimensões dos autoespaços.')
_advanced('elliptic.rational_points','Pontos racionais em curva elíptica','number_theory',lambda t,d: {'a':-t,'b':1,'height':3+d},'Substituição na equação; busca limitada não é enumeração completa.')
_advanced('stochastic.ito','Itô multivariado com covariação','probability',lambda t,d: {'function':f'x**2+{t}*x*y+y**2','drift':['x','-y'],'diffusion':[['x','1'],['0','y']],'variables':['x','y']},'f_t+a·grad(f)+tr(BB^T Hess(f))/2; Brownianos independentes.')
_advanced('autograd.jet','Gradiente, Hessiana e jets','calculus',lambda t,d: {'source':f'(x*x+{t}*y)**3+x*y','variables':['x','y'],'point':[1,2],'order':3},'Diferenciação multivariada e simetria das derivadas mistas.')
_advanced('autograd.implicit','Diferenciação implícita não linear','calculus',lambda t,d: {'equations':['y*y-x'],'parameters':['x'],'unknowns':['y'],'point':[(t+1)**2,t+1]},'Jacobiano nas incógnitas inversível no ponto regular.')
_advanced('optimization.certificate','Certificado de dualidade linear','optimization',lambda t,d: {'objective':[1],'matrix':[[1]],'lower':[t],'point':[t],'dual':[1]},'Viabilidade primal/dual e lacuna exatamente zero.')
_advanced('bayesian.conjugate','Inferência Gamma–Poisson','probability',lambda t,d: {'kind':'gamma_poisson','data':[t,2,3],'prior':{'shape':2,'rate':3}},'Atualização exata de forma e taxa, com parametrização explícita.')

_add('potential_theory','Dirichlet em rede condutiva','analysis',lambda t,d: {'conductance':[[0,1,0],[1,0,t],[0,t,0]],'boundary':{'0':0,'2':1}},'Equações harmônicas, energia e condições de contorno.')
_add('functional_analysis','Projeção de Hilbert ponderada','analysis',lambda t,d: {'basis':[[1,0,1],[0,1,1]],'target':[t,2,3],'weights':[1,2,3]},'Resíduo ortogonal e identidade de Pitágoras.')
_add('operator_theory','Adjunto, norma e resolvente','analysis',lambda t,d: {'matrix':[[t,1],[1,t+1]],'parameter':-1},'Operadores racionais finitos; positividade e resolvente.')
_add('integral_equations','Fredholm com núcleo separável','analysis',lambda t,d: {'kernel':[[f'1/{t+2}']],'rhs':[1,1],'lower':0,'upper':1,'coupling':1},'Sistema finito por momentos polinomiais; equação integral original.')
_add('difference_equations','Recorrência afim de ordem dois','analysis',lambda t,d: {'coefficients':[1,1],'initial':[0,1],'index':t+10,'forcing':1},'Propagação exata com estado aumentado e termo não homogêneo.')
_add('approximation_theory','Interpolação baricêntrica','analysis',lambda t,d: {'nodes':[0,1,2,3],'values':[t,t+1,t+8,t+27],'points':['1/2','3/2','5/2']},'Pesos racionais e amplificação de Lebesgue nas consultas.')
_add('integral_transforms','Transformada polinomial exata','analysis',lambda t,d: {'kind':'laplace_polynomial','values':[t,1,2,3],'parameter':2},'Momentos fatoriais do núcleo exponencial com parâmetro positivo.')
_add('measure_theory','Esperança condicional finita','analysis',lambda t,d: {'weights':[1,2,3,4],'values':[t,2,3,5],'partition':[0,0,1,1]},'Médias ponderadas por bloco da partição.')
_add('manifold_topology','Invariantes de superfície triangulada','topology',lambda t,d: {'facets':[[t,t+1,t+2],[t,t+1,t+3],[t,t+2,t+3],[t+1,t+2,t+3]]},'Links, Euler, orientabilidade e gênero sob hipóteses verificadas.')
_add('global_analysis','Laplaciano de Hodge simplicial','topology',lambda t,d: {'facets':[[t,t+1],[t+1,t+2],[t,t+2]],'degree':1,'form':[1,2,3]},'Bordos, cobordos e projeção harmônica em complexo finito.')
_add('algebraic_geometry','Tangente de variedade afim singular','geometry',lambda t,d: {'equations':['y**2-x**3'],'variables':['x','y'],'point':[0,0]},'Jacobiano no ponto; dimensão tangente não é dimensão global.')
_add('lie_algebra','Colchete, centro e Killing','algebra',lambda t,d: {'structure':[[[0,0],[0,t]],[[0,-t],[0,0]]]},'Antissimetria, Jacobi e representação adjunta racional.')
_add('k_theory','K0 de álgebra de grafo','algebra',lambda t,d: {'adjacency':[[t+1,1],[1,2]]},'Cokernel de I-A^T no perfil de Leavitt suportado.')
_advanced('proofs.check','Dedução natural com descarga','logic',lambda t,d: {'proof':{'rule':'imp_intro','assumption':f'P{t}','premises':[{'rule':'assumption','formula':f'P{t}'}]},'expected':['imp',f'P{t}',f'P{t}']},'Checagem recursiva das regras e hipóteses não descarregadas.')
_advanced('constructive.type_check','Curry–Howard e termo identidade','logic',lambda t,d: {'term':{'op':'lambda','name':'x','type':f'P{t}','body':{'op':'var','name':'x'}},'expected':['imp',f'P{t}',f'P{t}']},'Regras do cálculo lambda simplesmente tipado.')
_advanced('models.satisfaction','Ordem dos quantificadores','logic',lambda t,d: {'domain':[t,t+1,t+2],'relations':{},'sentence':{'op':'forall','variable':'x','body':{'op':'exists','variable':'y','body':{'op':'equal','left':{'var':'x'},'right':{'var':'y'}}}}},'Enumerar o domínio finito sem generalizar a modelos infinitos.')

# Numerical exercises state their finite precision and do not claim exact proof.
_add('spectral','DFT complexa, frequências e convenções','spectral',lambda t,d: {'kind':'fft','values':[t,1,0,-1,2,0,1,-2]},'DFT numérica não normalizada; arredondamento não é incluído em intervalo certificado.')
_add('statistical_mechanics','Ensemble canônico e capacidade térmica','statistical_mechanics',lambda t,d: {'energies':[0,1,t/10,3],'degeneracies':[1,2,1,3],'temperature':2,'boltzmann':1},'Log-sum-exp, probabilidades e flutuações energéticas em ensemble finito.')
_advanced('lie.matrix_group','Exponencial no grupo de Lie SO(2)','geometry',lambda t,d: {'kind':'SO','matrix':[[0,-t/100],[t/100,0]]},'Exponencial matricial de gerador antissimétrico; erros de ponto flutuante.')
_advanced('functional.fixed_point','Ponto fixo por contração','analysis',lambda t,d: {'matrix':[[.2,.1],[0,.25]],'offset':[t,1],'tolerance':1e-10},'Fator de contração e cota a posteriori; arredondamento não incluído.')
_advanced('pde.fem','Poisson por elementos finitos','numerical',lambda t,d: {'nodes':[0,.25,.5,.75,1],'forcing':str(t),'left':{'kind':'dirichlet','value':0},'right':{'kind':'dirichlet','value':0}},'Galerkin linear, contornos e resíduo discreto; sem cota automática do erro contínuo.')
_advanced('special.precision','Função zeta em precisão arbitrária','analysis',lambda t,d: {'kind':'zeta','x':2+t/100,'digits':60},'Avaliação mpmath a 60 dígitos; representação decimal não é inclusão certificada.')
_advanced('ensembles.ising','Enumeração do modelo de Ising finito','statistical_mechanics',lambda t,d: {'size':4,'coupling':t/20,'field':.2,'temperature':2},'Enumeração das configurações; observáveis finitos não estabelecem limite termodinâmico.')

NUMERICAL_FAMILIES = frozenset({'spectral','statistical_mechanics','lie.matrix_group',
    'functional.fixed_point','pde.fem','special.precision','ensembles.ising'})
