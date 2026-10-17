# Cobertura por grandes ramos da MSC 2020

Este inventário usa os 63 códigos principais da [MSC 2020](https://msc2020.org/) como referência de organização. Os nomes descritivos abaixo e o mapeamento são próprios do Nabla; a classificação completa não é redistribuída.

Foram acrescentados **22 módulos matemáticos executáveis**, integrados ao catálogo de **103 operações**, à CLI, ao HTTP, ao MCP, aos notebooks e aos recibos. Os perfis anteriores são reutilizados quando já existem. Cada linha descreve um perfil computacional delimitado, sem afirmar que todo o ramo, seus problemas abertos ou todas as suas subclasses foram implementados.

A área 01 é documental: metadados bibliográficos fornecidos pelo usuário. Não representa pesquisa historiográfica automática. A área 97 tem geração de exercícios verificáveis, sem alegação de eficácia pedagógica geral.

| Código | Área descritiva | Implementação | Perfil |
|---|---|---|---|
| 00 | Infraestrutura matemática | [catalog.py](../src/nablamath/calc/catalog.py) | Biblioteca existente — Catálogo e contratos de operações computacionais |
| 01 | Fontes históricas e bibliográficas | [citations.py](../src/nablamath/documents/citations.py) | Documental — Metadados bibliográficos fornecidos; não pesquisa historiográfica automática |
| 03 | Fundamentos e lógica | [smt_linear.py](../src/nablamath/math/logic/smt_linear.py) | Biblioteca existente — Proposições e aritmética linear em fragmentos controlados |
| 05 | Combinatória | [enumerative.py](../src/nablamath/math/combinatorics/enumerative.py) | Biblioteca existente — Contagem finita e identidades combinatórias |
| 06 | Ordens e reticulados | [order_theory.py](../src/nablamath/ops/order_theory.py) | Novo: `order_theory` — finite partial orders, Hasse covers and lattice joins/meets; 64 elements |
| 08 | Álgebras universais | [universal_algebra.py](../src/nablamath/ops/universal_algebra.py) | Novo: `universal_algebra` — finite binary algebras, generated subalgebras and congruence quotients |
| 11 | Teoria dos números | [advanced_number_theory.py](../src/nablamath/math/exact/advanced_number_theory.py) | Biblioteca existente — Problemas inteiros e modulares com orçamentos explícitos |
| 12 | Corpos e polinômios | [finite_fields.py](../src/nablamath/math/exact/finite_fields.py) | Biblioteca existente — Corpos finitos e extensões polinomiais |
| 13 | Álgebra comutativa | [groebner.py](../src/nablamath/math/algebra/groebner.py) | Biblioteca existente — Bases de Gröbner polinomiais em problemas finitos |
| 14 | Geometria algébrica | [algebraic_geometry.py](../src/nablamath/ops/algebraic_geometry.py) | Novo: `algebraic_geometry` — rational points and Zariski tangent spaces of explicitly generated affine schemes |
| 15 | Álgebra linear | [solvers.py](../src/nablamath/math/linear_algebra/solvers.py) | Biblioteca existente — Sistemas e decomposições racionais exatas |
| 16 | Anéis associativos | [rings.py](../src/nablamath/math/algebra/rings.py) | Biblioteca existente — Estruturas e verificações algébricas finitas |
| 17 | Álgebras de Lie | [lie_algebra.py](../src/nablamath/ops/lie_algebra.py) | Novo: `lie_algebra` — rational Lie brackets, Jacobi verification, center and Killing form; dimension at most six |
| 18 | Categorias e estruturas homológicas | [functors.py](../src/nablamath/math/category_theory/functors.py) | Biblioteca existente — Categorias finitas, funtores e transformações naturais |
| 19 | Invariantes K | [k_theory.py](../src/nablamath/ops/k_theory.py) | Novo: `k_theory` — exact K0 presentation of finite graph Leavitt path algebras, not general higher K-theory |
| 20 | Grupos | [groups.py](../src/nablamath/math/algebra/groups.py) | Biblioteca existente — Grupos finitos e operações estruturais |
| 22 | Grupos de Lie | [lie_groups.py](../src/nablamath/ops/lie_groups.py) | Novo: `lie_groups` — numerical SO(3) exponential, quaternion and left Jacobian in radians |
| 26 | Análise real | [certified_functions.py](../src/nablamath/math/analysis/certified_functions.py) | Biblioteca existente — Envoltórias racionais de funções em domínios delimitados |
| 28 | Medida e integração | [measure_theory.py](../src/nablamath/ops/measure_theory.py) | Novo: `measure_theory` — finite atomic measure integrals and exact conditional expectation |
| 30 | Análise complexa univariada | [complex_analysis.py](../src/nablamath/ops/complex_analysis.py) | Biblioteca existente — Contornos numéricos e mapas de Möbius |
| 31 | Potencial discreto | [potential_theory.py](../src/nablamath/ops/potential_theory.py) | Novo: `potential_theory` — exact finite weighted-graph Dirichlet solution, residuals and energy |
| 32 | Várias variáveis complexas | [several_complex_variables.py](../src/nablamath/ops/several_complex_variables.py) | Novo: `several_complex_variables` — exact Gaussian-rational holomorphic polynomial Jacobians and local inverse criterion |
| 33 | Funções especiais | [special_functions.py](../src/nablamath/ops/special_functions.py) | Novo: `special_functions` — real Gamma/Beta/error functions and optional SciPy Bessel/Legendre/Airy evaluation |
| 34 | Equações diferenciais ordinárias | [ode.py](../src/nablamath/numeric/ode.py) | Biblioteca existente — Integração numérica com modelos e tolerâncias declarados |
| 35 | Equações diferenciais parciais | [pde_general.py](../src/nablamath/numeric/pde_general.py) | Biblioteca existente — Perfis de Poisson e domínios de fronteira específicos |
| 37 | Dinâmica | [discrete.py](../src/nablamath/math/dynamical_systems/discrete.py) | Biblioteca existente — Iteração finita e sistemas discretos |
| 39 | Equações de diferenças | [difference_equations.py](../src/nablamath/ops/difference_equations.py) | Novo: `difference_equations` — exact affine constant-coefficient recurrence with explicit index and bit budgets |
| 40 | Sequências e séries | [sequences.py](../src/nablamath/math/analysis/sequences.py) | Biblioteca existente — Sequências e séries sob condições declaradas |
| 41 | Aproximação e interpolação | [approximation_theory.py](../src/nablamath/ops/approximation_theory.py) | Novo: `approximation_theory` — exact rational barycentric interpolation and query Lebesgue amplification |
| 42 | Análise harmônica euclidiana | [spectral.py](../src/nablamath/ops/spectral.py) | Biblioteca existente — FFT, Haar e sinais amostrados finitos |
| 43 | Harmônica em grupos | [abstract_harmonic_analysis.py](../src/nablamath/ops/abstract_harmonic_analysis.py) | Novo: `abstract_harmonic_analysis` — numerical Fourier characters on finite products of cyclic groups |
| 44 | Transformadas integrais | [integral_transforms.py](../src/nablamath/ops/integral_transforms.py) | Novo: `integral_transforms` — exact polynomial Laplace/unit-Mellin and finite real rational Z transforms |
| 45 | Equações integrais | [integral_equations.py](../src/nablamath/ops/integral_equations.py) | Novo: `integral_equations` — exact nonsingular second-kind Fredholm equation with polynomial finite-rank kernel |
| 46 | Espaços funcionais | [functional_analysis.py](../src/nablamath/ops/functional_analysis.py) | Novo: `functional_analysis` — exact finite weighted-Hilbert projection, orthogonality and Pythagoras identity |
| 47 | Operadores | [operator_theory.py](../src/nablamath/ops/operator_theory.py) | Novo: `operator_theory` — finite rational operators, adjoints, induced norms, positivity and resolvents |
| 49 | Cálculo variacional | [variational_calculus.py](../src/nablamath/ops/variational_calculus.py) | Novo: `variational_calculus` — exact scalar polynomial first-order Euler-Lagrange equation, momentum and energy |
| 51 | Geometria | [euclidean.py](../src/nablamath/math/geometry/euclidean.py) | Biblioteca existente — Geometria euclidiana e coordenadas exatas |
| 52 | Convexidade | [convex.py](../src/nablamath/math/geometry/convex.py) | Biblioteca existente — Objetos convexos finitos e algoritmos geométricos |
| 53 | Geometria diferencial | [differential_geometry.py](../src/nablamath/ops/differential_geometry.py) | Biblioteca existente — Métricas locais e curvatura em dimensão limitada |
| 54 | Topologia geral | [general.py](../src/nablamath/math/topology/general.py) | Biblioteca existente — Espaços topológicos finitos |
| 55 | Topologia algébrica | [homology.py](../src/nablamath/math/topology/homology.py) | Biblioteca existente — Complexos finitos e homologia racional |
| 57 | Superfícies e variedades trianguladas | [manifold_topology.py](../src/nablamath/ops/manifold_topology.py) | Novo: `manifold_topology` — finite triangulated surface links, boundaries, orientability and closed orientable genus |
| 58 | Análise global discreta | [global_analysis.py](../src/nablamath/ops/global_analysis.py) | Novo: `global_analysis` — finite simplicial Hodge Laplacian and exact harmonic projection |
| 60 | Probabilidade e processos estocásticos | [stochastic.py](../src/nablamath/math/probability/stochastic.py) | Biblioteca existente — Processos e caminhos amostrados em modelos declarados |
| 62 | Estatística | [multivariate.py](../src/nablamath/math/statistics/multivariate.py) | Biblioteca existente — Ajustes e inferência em modelos delimitados |
| 65 | Análise numérica | [linear.py](../src/nablamath/numeric/linear.py) | Biblioteca existente — Álgebra e aproximação numérica com contratos específicos |
| 68 | Computação matemática | [automata.py](../src/nablamath/math/formal_languages/automata.py) | Biblioteca existente — Autômatos e linguagens finitas |
| 70 | Mecânica de sistemas | [dynamics.py](../src/nablamath/physics/orbital/dynamics.py) | Biblioteca existente — Dinâmica de partículas e gravitação em modelos finitos |
| 74 | Mecânica de sólidos | [truss2d.py](../src/nablamath/physics/fea/truss2d.py) | Biblioteca existente — Elementos finitos de treliças e materiais declarados |
| 76 | Mecânica de fluidos | [navier_stokes.py](../src/nablamath/physics/fluids/navier_stokes.py) | Biblioteca existente — Perfis numéricos com malha e condições de contorno |
| 78 | Eletromagnetismo aplicado | [resistive.py](../src/nablamath/domains/circuits/resistive.py) | Biblioteca existente — Circuitos resistivos e modelos elétricos delimitados |
| 80 | Transferência térmica | [diffusion.py](../src/nablamath/worlds/pde/diffusion.py) | Biblioteca existente — Difusão térmica discreta em modelos de fronteira específicos |
| 81 | Matemática quântica | [quantum.py](../src/nablamath/domain/quantum.py) | Biblioteca existente — Circuitos unitários ideais em espaço de estados limitado |
| 82 | Mecânica estatística | [statistical_mechanics.py](../src/nablamath/ops/statistical_mechanics.py) | Novo: `statistical_mechanics` — stable finite canonical ensemble in caller-consistent units; no thermodynamic limit |
| 83 | Relatividade | [general.py](../src/nablamath/physics/relativity/general.py) | Biblioteca existente — Modelos relativísticos específicos e suas hipóteses |
| 85 | Modelos astronômicos | [dynamics.py](../src/nablamath/physics/orbital/dynamics.py) | Biblioteca existente — Órbitas e gravitação em perfis locais |
| 86 | Modelos geofísicos | [geophysics.py](../src/nablamath/ops/geophysics.py) | Novo: `geophysics` — vertical layered acoustic times/reflections or infinite Bouguer slab in SI units |
| 90 | Pesquisa operacional | [discrete_optimization.py](../src/nablamath/math/exact/discrete_optimization.py) | Biblioteca existente — Otimização e grafos finitos |
| 91 | Jogos e decisões | [normal_form.py](../src/nablamath/math/game_theory/normal_form.py) | Biblioteca existente — Jogos finitos em forma normal |
| 92 | Matemática biológica | [bioinformatics.py](../src/nablamath/domain/bioinformatics.py) | Biblioteca existente — Alinhamento de sequências; interpretação biológica externa |
| 93 | Controle | [linear.py](../src/nablamath/math/control/linear.py) | Biblioteca existente — Sistemas lineares e verificações estruturais |
| 94 | Informação e códigos | [coding.py](../src/nablamath/math/information/coding.py) | Biblioteca existente — Códigos e entropia de distribuições finitas |
| 97 | Ensino de matemática | [reverse_builder.py](../src/nablamath/forge/reverse_builder.py) | Biblioteca existente — Geração de exercícios com respostas verificáveis; sem avaliação pedagógica geral |

## Uso e verificação

```python
from nablamath.math.coverage import coverage, classification
from nablamath.calc import CalculationSession

print(classification("28"))
record = CalculationSession().execute("measure_theory", weights=[1, 3], values=[2, 4], partition=[0, 0])
print(record.to_data())
```

```bash
python -m pytest -q tests/test_msc_mathematics.py
nabla calc integral_equations --arguments '{"kernel":[[0,0],[0,1]],"rhs":[1]}'
python examples/science/reproduce.py .nabla/experimento-103-operacoes
```

Os testes incluem referências de grupos finitos, sl(2), forma normal de Smith independente, medidas e condicionamento, resíduos de Fredholm, transformadas diretas, projeção de Hilbert, teorema de Hodge discreto, esfera/torus/plano projetivo, mecânica estatística e modelos geofísicos. Há replay de recibos e notebook para cada módulo novo.

## Limites que permanecem explícitos

Os resultados exatos se restringem aos domínios finitos e polinomiais declarados. SO(3), funções especiais, Fourier e modelos físicos numéricos têm arredondamento. Funções especiais adicionais requerem SciPy. K₀ refere-se às álgebras de caminhos de Leavitt de grafos finitos; a análise funcional é finita; a topologia de variedades é de superfícies trianguladas; o Hodge é combinatório e não resolve problemas elípticos gerais em variedades suaves.

O inventário é distribuído no wheel como `nablamath/msc_coverage.json`. `entire_subject_implemented` permanece falso em todas as linhas. A aceitação científica dos 213 requisitos continua separada deste mapa e não foi promovida.
