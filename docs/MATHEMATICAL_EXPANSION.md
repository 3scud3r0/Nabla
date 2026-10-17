# Expansão matemática e consolidação da versão 1

Esta entrega amplia os módulos identificados no roteiro anterior e cria os 14
módulos especializados propostos. As funções ficam acessíveis pela API Python e
pela operação auditável `advanced_math`, que reúne ações nomeadas, assinaturas
fechadas e esquemas MCP próprios. O catálogo principal tem 103 operações.

**Atualização da versão 1:** os testes antes mantidos sem execução foram
incluídos na campanha atual, agora autorizada pelo usuário. Consulte os
[resultados e falhas preservadas](releases/V1_VALIDATION.md). As 139 ações
originais receberam 17 ações novas, totalizando 156, sem alterar as 103
operações do catálogo principal. A aceitação científica dos 213 critérios
permanece separada da execução de testes.

## Novos módulos

Todos os caminhos abaixo são relativos a `src/nablamath/`.

| Arquivo novo | Algoritmos e contratos implementados |
|---|---|
| `math/algebra/representations.py` | Representações racionais de grupos finitos por tabelas, caracteres, intertwiners, ortogonalidade e decomposição por uma família de irredutíveis validada. |
| `math/algebra/modules.py` | Apresentações de grupos abelianos por Smith sobre Z, núcleos/imagens/conúcleos racionais e resolução livre racional de comprimento um. |
| `math/algebra/homological.py` | Complexos de cadeias racionais, exatidão, mapas e homotopias de cadeias; Ext/Tor de grupos cíclicos sobre Z. |
| `math/geometry/schemes.py` | Bases de Gröbner e dimensão afim, eliminação, saturação, cartas projetivas; radicalização e decomposição primária exatas de ideais zero-dimensionais sobre Q. |
| `math/geometry/sheaves.py` | Diagramas finitos de espaços vetoriais, compatibilidade de restrições, seções globais e complexo/cohomologia de Čech da cobertura fornecida. |
| `math/geometry/fiber_bundles.py` | Cociclos constantes de fibrados sobre um nervo fornecido, seções, transformação de gauge de conexões locais e transporte paralelo numérico. |
| `math/geometry/differential_forms.py` | Formas coordenadas, produto exterior, derivada exterior, pullback e integração de formas de grau máximo em caixas. |
| `math/analysis/distributions.py` | Somas de derivadas de Dirac, pareamento, derivação, Fourier e distribuições regulares de densidade polinomial em intervalos. |
| `math/analysis/sobolev.py` | Normas Hᵏ de polinômios em intervalos, traços, constante de Poincaré sob traço zero e contratos explícitos de erro de truncamento. |
| `math/topology/homotopy.py` | Apresentações do grupo fundamental de complexos conexos pelo 2-esqueleto e verificação de aplicações simpliciais. |
| `math/set_theory/axiomatic.py` | Conjuntos hereditariamente finitos, instâncias finitas de axiomas e derivações com axiomas declarados como hipóteses. |
| `math/logic/model_theory.py` | Satisfação de sentenças de primeira ordem em estruturas relacionais finitas; decisão SMT no fragmento linear sem quantificadores sobre inteiros, com timeout nativo e hipóteses explícitas. |
| `math/logic/proof_theory.py` | Verificador de dedução natural intuicionista com descarga de hipóteses e árvores limitadas. |
| `math/logic/constructive.py` | Verificador Curry–Howard de termos simplesmente tipados com funções, produtos, somas e eliminação do vazio. |

`math/_structured.py` fornece parsing AST fechado, números racionais limitados,
serialização e validação dos arrays. Não chama `eval`, `sympify`, `parse_expr`
ou `lambdify` com texto recebido.

## Ampliações dos módulos existentes

| Área / arquivos | Ampliação |
|---|---|
| `ops/order_theory.py`, `ops/universal_algebra.py` | Heyting/Boole, subconjuntos por bitsets, ordens por predicados em domínios finitos; aridades 0–4, identidades por termos, congruências e álgebras livres de funções-termo em variedades geradas por uma álgebra finita. |
| `ops/algebraic_geometry.py`, `ops/lie_algebra.py`, `ops/k_theory.py` | Ideais; representações de Lie, radical solúvel, radical nilpotente, testemunha de Levi, PBW e raízes; K₀/K₁ de corpos primos, K superior de corpos finitos e K complexo de esferas. |
| `ops/measure_theory.py`, `ops/potential_theory.py`, `ops/lie_groups.py` | Radon–Nikodym atômico, produtos e densidades polinomiais contínuas; Green e collocation por painéis; exponencial/logaritmo SO/SL/SU/SE(3), Fréchet, adjunto e integração por exponenciais. |
| `ops/special_functions.py`, `ops/approximation_theory.py` | Avaliação complexa multiprecisão, hipergeométricas/elípticas; splines, Chebyshev, minimax discreto, Remez contínuo polinomial, Padé e certificado de erro Bernstein do polinômio retornado. |
| `ops/integral_transforms.py`, `ops/integral_equations.py`, `ops/difference_equations.py` | Transformadas/inversões simbólicas e quadratura oscilatória; Nyström Fredholm/Volterra e regularização; recorrências lineares de coeficientes polinomiais e sistemas discretos não lineares. |
| `ops/several_complex_variables.py`, `ops/abstract_harmonic_analysis.py` | Jets holomorfos locais; Fourier em representações fornecidas de grupos finitos e convolução não comutativa. |
| `ops/functional_analysis.py`, `ops/operator_theory.py` | Séries ortogonais com hipótese explícita de cauda, ponto fixo por contração e espectro de operadores esparsos simétricos com resíduos. |
| `ops/variational_calculus.py`, `ops/manifold_topology.py`, `ops/global_analysis.py` | Euler–Lagrange de várias coordenadas/campos e ordens, momentos de fronteira e Hessianas; invariantes integrais de complexos; de Rham coordenado e Hodge ponderado discreto. |
| `ops/statistical_mechanics.py`, `ops/geophysics.py` | Ensembles micro/grande-canônico, Ising finito; gravidade de massas pontuais, inversão Gaussiana regularizada e onda acústica 2D com CFL explícito. |
| `ops/spectral.py`, `ops/complex_analysis.py`, `ops/differential_geometry.py` | FFT multidimensional, wavelets, DFT não uniforme e diagnóstico de amostragem; resíduos/Laurent/polos racionais; pullbacks, derivadas covariantes e geodésicas. |
| `ops/abstract_algebra.py`, `math/algebra/galois.py`, `math/algebra/extensions.py`, `math/algebra/groups.py` | Fatoração limitada, geração de certificados Pocklington uint64; Galois de grau até seis, extensões até grau 16, elementos primitivos/fatoração em corpos de números; grupos por permutações/Schreier–Sims e quocientes limitados. |
| `math/category_theory/categories.py`, `math/category_theory/functors.py` | Categorias por caminhos e relações redutoras; composição de funtores, adjunções e equivalências finitas por unidades/conidades e identidades triangulares. |
| `math/topology/homology.py`, `math/topology/general.py`, `math/set_theory/finite.py` | Homologia/cohomologia integral com torção, bases de cohomologia racional e produto cup em classes, continuidade/Lipschitz polinomial em intervalo compacto e progressões inteiras infinitas decidíveis. |
| `math/calculus/risch.py`, `math/linear_algebra/exact_spectral.py`, `math/number_theory/elliptic_curves.py` | Integração racional/Risch do backend com guardas do domínio original, raízes/espaços próprios algébricos, curvas sobre Q, busca limitada de pontos e isogenia explícita de grau dois. |
| `math/probability/ito.py`, `math/probability/stochastic.py`, `numeric/stiff_ode.py`, `numeric/pde_general.py` | Itô multivariado, Euler/Milstein vetorial, saltos, refinamento Browniano aninhado; BDF/Radau vetorial com Jacobiano e eventos; Poisson cartesiano 1D–3D, FEM 1D com fronteiras mistas e refinamento adaptativo. |
| `ops/autograd.py`, `ops/bayesian_inference.py`, `ops/convex_optimization.py` | Jets simbólicos que especificam regras de AD, derivação implícita/VJP de solução linear; novas conjugadas, hierarquia Gaussiana, Metropolis, R-hat/ESS/MCSE; programação cônica/SDP e verificação racional independente de certificados LP. |

## Recibos, ferramentas e prova formal

`CalculationSession.mathematics(action, **parameters)` utiliza o mesmo fluxo de
recibos imutáveis, opção de buffer, catálogo, CLI/HTTP e replay de notebook.
`ops/advanced_math.py` contém somente uma lista autorizada de módulos/funções.
O cliente não escolhe caminhos Python nem envia callbacks executáveis.

```python
from nablamath.calc import CalculationSession

record = CalculationSession().mathematics(
    'measure.radon_nikodym', reference=[1, 2, 0], target=[3, 4, 0])
print(record.to_data())
```

O exemplo acima documenta a API. A campanha da versão 1 verifica sessão e recibos.

`formal/translate.py` transforma identidades e testemunhas matriciais em
obrigações escalares independentes. `formal/lean_checker.py` pode verificar todas
as obrigações sob um orçamento compartilhado, quando o usuário executar a API e
dispuser de Lean/Mathlib compilados. `formal/translation_review.py` vincula revisão,
certificado e recibo aos seus hashes. Não se considera a geração de Lean como
prova, nem um nome de revisor como identidade autenticada.

## Dependências e limites

O núcleo continua sem dependências obrigatórias. `advanced` reúne SymPy >=1.14,
NumPy, SciPy, mpmath, PyWavelets e CVXPY. Imports são locais às funções. As
operações finitas de conjuntos/lógica não exigem estes extras. CVXPY depende de
um solver cônico instalado e suportado. A precisão mpmath não é um intervalo
certificado; resultados SciPy possuem resíduos/estimativas explícitos.
O fragmento inteiro SMT exige o extra `formal`. Seu timeout nativo é distinto do
prazo total de processo aplicado por `AgentTools`; chamadas diretas ao Python não
herdam o supervisor de processos do MCP.

Não há decisão geral de igualdade em categorias apresentadas, reconhecimento de
variedades em toda dimensão, Risch de todas as torres, decomposição primária de
todo ideal, convergência de qualquer MCMC ou solução de qualquer EDP. As APIs
implementam classes computáveis e recusam entradas fora delas. Isso preserva os
limites matemáticos reais do roteiro.

## Testes da expansão original

- `tests/test_mathematical_expansion_exact.py`: referências algébricas,
  topológicas, lógicas, diferenciais e certificados exatos.
- `tests/test_mathematical_expansion_numerical.py`: referências analíticas,
  soluções manufaturadas, algoritmos numéricos e condições de estabilidade.
- `tests/test_mathematical_expansion_contracts.py`: assinaturas, schemas,
  permissões, recibos, replay e rejeição de sintaxe executável.
- `tests/test_mathematical_expansion_formal.py`: obrigações, corrupção de
  tradução, vinculação de revisão e preservação do estado Lean indisponível.

## Inventário das ações

O arquivo `src/nablamath/mathematical_expansion.json` distribui os nomes, módulos,
funções, arquivos e a referência de validação no wheel. A tabela
abaixo é gerada estaticamente a partir da lista autorizada, sem executar as ações.

Total atual: **156 ações avançadas**; 139 da expansão original e 17 da versão 1. Os hashes dos schemas de parâmetros também ficam no inventário.

| Ação | Arquivo | Função |
|---|---|---|
| `representations.validate` | [src/nablamath/math/algebra/representations.py](../src/nablamath/math/algebra/representations.py) | `representation` |
| `representations.intertwiners` | [src/nablamath/math/algebra/representations.py](../src/nablamath/math/algebra/representations.py) | `intertwiners` |
| `representations.characters` | [src/nablamath/math/algebra/representations.py](../src/nablamath/math/algebra/representations.py) | `character_inner_product` |
| `modules.presentation` | [src/nablamath/math/algebra/modules.py](../src/nablamath/math/algebra/modules.py) | `presentation` |
| `modules.homomorphism` | [src/nablamath/math/algebra/modules.py](../src/nablamath/math/algebra/modules.py) | `rational_homomorphism` |
| `modules.resolution` | [src/nablamath/math/algebra/modules.py](../src/nablamath/math/algebra/modules.py) | `finite_free_resolution` |
| `homological.complex` | [src/nablamath/math/algebra/homological.py](../src/nablamath/math/algebra/homological.py) | `chain_complex` |
| `homological.chain_map` | [src/nablamath/math/algebra/homological.py](../src/nablamath/math/algebra/homological.py) | `chain_map` |
| `homological.ext_tor` | [src/nablamath/math/algebra/homological.py](../src/nablamath/math/algebra/homological.py) | `cyclic_ext_tor` |
| `schemes.affine` | [src/nablamath/math/geometry/schemes.py](../src/nablamath/math/geometry/schemes.py) | `affine_scheme` |
| `schemes.eliminate` | [src/nablamath/math/geometry/schemes.py](../src/nablamath/math/geometry/schemes.py) | `eliminate` |
| `schemes.saturate` | [src/nablamath/math/geometry/schemes.py](../src/nablamath/math/geometry/schemes.py) | `saturate` |
| `schemes.primary` | [src/nablamath/math/geometry/schemes.py](../src/nablamath/math/geometry/schemes.py) | `univariate_primary` |
| `schemes.projective_chart` | [src/nablamath/math/geometry/schemes.py](../src/nablamath/math/geometry/schemes.py) | `projective_chart` |
| `sheaves.sections` | [src/nablamath/math/geometry/sheaves.py](../src/nablamath/math/geometry/sheaves.py) | `global_sections` |
| `sheaves.cech` | [src/nablamath/math/geometry/sheaves.py](../src/nablamath/math/geometry/sheaves.py) | `cech_cohomology` |
| `forms.derivative` | [src/nablamath/math/geometry/differential_forms.py](../src/nablamath/math/geometry/differential_forms.py) | `exterior_derivative` |
| `forms.wedge` | [src/nablamath/math/geometry/differential_forms.py](../src/nablamath/math/geometry/differential_forms.py) | `wedge` |
| `forms.pullback` | [src/nablamath/math/geometry/differential_forms.py](../src/nablamath/math/geometry/differential_forms.py) | `pullback` |
| `forms.integrate` | [src/nablamath/math/geometry/differential_forms.py](../src/nablamath/math/geometry/differential_forms.py) | `integrate_box` |
| `bundles.verify` | [src/nablamath/math/geometry/fiber_bundles.py](../src/nablamath/math/geometry/fiber_bundles.py) | `verify_bundle` |
| `bundles.sections` | [src/nablamath/math/geometry/fiber_bundles.py](../src/nablamath/math/geometry/fiber_bundles.py) | `compatible_sections` |
| `bundles.connection` | [src/nablamath/math/geometry/fiber_bundles.py](../src/nablamath/math/geometry/fiber_bundles.py) | `gauge_connection` |
| `distributions.pairing` | [src/nablamath/math/analysis/distributions.py](../src/nablamath/math/analysis/distributions.py) | `dirac_pairing` |
| `distributions.derivative` | [src/nablamath/math/analysis/distributions.py](../src/nablamath/math/analysis/distributions.py) | `derivative` |
| `distributions.fourier` | [src/nablamath/math/analysis/distributions.py](../src/nablamath/math/analysis/distributions.py) | `fourier` |
| `distributions.regular` | [src/nablamath/math/analysis/distributions.py](../src/nablamath/math/analysis/distributions.py) | `regular_pairing` |
| `sobolev.norm` | [src/nablamath/math/analysis/sobolev.py](../src/nablamath/math/analysis/sobolev.py) | `polynomial_norm` |
| `sobolev.tail` | [src/nablamath/math/analysis/sobolev.py](../src/nablamath/math/analysis/sobolev.py) | `truncation_bound` |
| `homotopy.fundamental_group` | [src/nablamath/math/topology/homotopy.py](../src/nablamath/math/topology/homotopy.py) | `fundamental_group` |
| `homotopy.simplicial_map` | [src/nablamath/math/topology/homotopy.py](../src/nablamath/math/topology/homotopy.py) | `simplicial_map` |
| `proofs.check` | [src/nablamath/math/logic/proof_theory.py](../src/nablamath/math/logic/proof_theory.py) | `check_proof` |
| `constructive.type_check` | [src/nablamath/math/logic/constructive.py](../src/nablamath/math/logic/constructive.py) | `type_check` |
| `models.satisfaction` | [src/nablamath/math/logic/model_theory.py](../src/nablamath/math/logic/model_theory.py) | `satisfies` |
| `sets.operations` | [src/nablamath/math/set_theory/axiomatic.py](../src/nablamath/math/set_theory/axiomatic.py) | `finite_set_operations` |
| `sets.axiom` | [src/nablamath/math/set_theory/axiomatic.py](../src/nablamath/math/set_theory/axiomatic.py) | `axiom_instance` |
| `sets.derivation` | [src/nablamath/math/set_theory/axiomatic.py](../src/nablamath/math/set_theory/axiomatic.py) | `verify_derivation` |
| `order.heyting` | [src/nablamath/ops/order_theory.py](../src/nablamath/ops/order_theory.py) | `heyting_algebra` |
| `order.boolean` | [src/nablamath/ops/order_theory.py](../src/nablamath/ops/order_theory.py) | `boolean_bitset` |
| `order.symbolic` | [src/nablamath/ops/order_theory.py](../src/nablamath/ops/order_theory.py) | `symbolic_order` |
| `universal.signature` | [src/nablamath/ops/universal_algebra.py](../src/nablamath/ops/universal_algebra.py) | `finite_signature` |
| `universal.congruences` | [src/nablamath/ops/universal_algebra.py](../src/nablamath/ops/universal_algebra.py) | `congruences` |
| `universal.free` | [src/nablamath/ops/universal_algebra.py](../src/nablamath/ops/universal_algebra.py) | `free_term_algebra` |
| `algebraic.ideals` | [src/nablamath/ops/algebraic_geometry.py](../src/nablamath/ops/algebraic_geometry.py) | `ideal_analysis` |
| `lie.structure` | [src/nablamath/ops/lie_algebra.py](../src/nablamath/ops/lie_algebra.py) | `lie_structure` |
| `k.groups` | [src/nablamath/ops/k_theory.py](../src/nablamath/ops/k_theory.py) | `k_groups` |
| `measure.radon_nikodym` | [src/nablamath/ops/measure_theory.py](../src/nablamath/ops/measure_theory.py) | `radon_nikodym` |
| `measure.product` | [src/nablamath/ops/measure_theory.py](../src/nablamath/ops/measure_theory.py) | `product_measure` |
| `measure.continuous` | [src/nablamath/ops/measure_theory.py](../src/nablamath/ops/measure_theory.py) | `continuous_integral` |
| `lie.matrix_group` | [src/nablamath/ops/lie_groups.py](../src/nablamath/ops/lie_groups.py) | `matrix_group` |
| `lie.se3_adjoint` | [src/nablamath/ops/lie_groups.py](../src/nablamath/ops/lie_groups.py) | `se3_adjoint` |
| `lie.integrate` | [src/nablamath/ops/lie_groups.py](../src/nablamath/ops/lie_groups.py) | `integrate_group` |
| `potential.green` | [src/nablamath/ops/potential_theory.py](../src/nablamath/ops/potential_theory.py) | `green_function` |
| `potential.boundary` | [src/nablamath/ops/potential_theory.py](../src/nablamath/ops/potential_theory.py) | `boundary_single_layer` |
| `special.precision` | [src/nablamath/ops/special_functions.py](../src/nablamath/ops/special_functions.py) | `high_precision` |
| `approximation.spline` | [src/nablamath/ops/approximation_theory.py](../src/nablamath/ops/approximation_theory.py) | `spline` |
| `approximation.chebyshev` | [src/nablamath/ops/approximation_theory.py](../src/nablamath/ops/approximation_theory.py) | `chebyshev_fit` |
| `approximation.minimax` | [src/nablamath/ops/approximation_theory.py](../src/nablamath/ops/approximation_theory.py) | `remez_grid` |
| `approximation.pade` | [src/nablamath/ops/approximation_theory.py](../src/nablamath/ops/approximation_theory.py) | `pade` |
| `transforms.symbolic` | [src/nablamath/ops/integral_transforms.py](../src/nablamath/ops/integral_transforms.py) | `symbolic_transform` |
| `transforms.oscillatory` | [src/nablamath/ops/integral_transforms.py](../src/nablamath/ops/integral_transforms.py) | `oscillatory_integral` |
| `recurrence.symbolic` | [src/nablamath/ops/difference_equations.py](../src/nablamath/ops/difference_equations.py) | `variable_recurrence` |
| `recurrence.system` | [src/nablamath/ops/difference_equations.py](../src/nablamath/ops/difference_equations.py) | `discrete_system` |
| `integral_equations.nystrom` | [src/nablamath/ops/integral_equations.py](../src/nablamath/ops/integral_equations.py) | `numerical_integral_equation` |
| `complex.holomorphic_jet` | [src/nablamath/ops/several_complex_variables.py](../src/nablamath/ops/several_complex_variables.py) | `holomorphic_jet` |
| `harmonic.group_fourier` | [src/nablamath/ops/abstract_harmonic_analysis.py](../src/nablamath/ops/abstract_harmonic_analysis.py) | `group_fourier` |
| `harmonic.convolution` | [src/nablamath/ops/abstract_harmonic_analysis.py](../src/nablamath/ops/abstract_harmonic_analysis.py) | `group_convolution` |
| `functional.series` | [src/nablamath/ops/functional_analysis.py](../src/nablamath/ops/functional_analysis.py) | `orthogonal_series` |
| `functional.fixed_point` | [src/nablamath/ops/functional_analysis.py](../src/nablamath/ops/functional_analysis.py) | `contraction_fixed_point` |
| `operators.sparse_spectrum` | [src/nablamath/ops/operator_theory.py](../src/nablamath/ops/operator_theory.py) | `sparse_spectrum` |
| `variations.fields` | [src/nablamath/ops/variational_calculus.py](../src/nablamath/ops/variational_calculus.py) | `euler_lagrange_fields` |
| `manifolds.invariants` | [src/nablamath/ops/manifold_topology.py](../src/nablamath/ops/manifold_topology.py) | `complex_invariants` |
| `global.de_rham` | [src/nablamath/ops/global_analysis.py](../src/nablamath/ops/global_analysis.py) | `de_rham_derivative` |
| `global.weighted_hodge` | [src/nablamath/ops/global_analysis.py](../src/nablamath/ops/global_analysis.py) | `weighted_hodge` |
| `ensembles.microcanonical` | [src/nablamath/ops/statistical_mechanics.py](../src/nablamath/ops/statistical_mechanics.py) | `microcanonical` |
| `ensembles.grand` | [src/nablamath/ops/statistical_mechanics.py](../src/nablamath/ops/statistical_mechanics.py) | `grand_canonical` |
| `ensembles.ising` | [src/nablamath/ops/statistical_mechanics.py](../src/nablamath/ops/statistical_mechanics.py) | `ising_chain` |
| `geophysics.gravity` | [src/nablamath/ops/geophysics.py](../src/nablamath/ops/geophysics.py) | `gravity_point_masses` |
| `geophysics.inverse` | [src/nablamath/ops/geophysics.py](../src/nablamath/ops/geophysics.py) | `tikhonov_inversion` |
| `spectral.multidimensional` | [src/nablamath/ops/spectral.py](../src/nablamath/ops/spectral.py) | `multidimensional_fft` |
| `spectral.wavelet` | [src/nablamath/ops/spectral.py](../src/nablamath/ops/spectral.py) | `wavelet_transform` |
| `spectral.nonuniform` | [src/nablamath/ops/spectral.py](../src/nablamath/ops/spectral.py) | `nonuniform_dft` |
| `spectral.diagnostics` | [src/nablamath/ops/spectral.py](../src/nablamath/ops/spectral.py) | `sampling_diagnostics` |
| `complex.meromorphic` | [src/nablamath/ops/complex_analysis.py](../src/nablamath/ops/complex_analysis.py) | `meromorphic_analysis` |
| `complex.clearance` | [src/nablamath/ops/complex_analysis.py](../src/nablamath/ops/complex_analysis.py) | `contour_clearance` |
| `geometry.pullback` | [src/nablamath/ops/differential_geometry.py](../src/nablamath/ops/differential_geometry.py) | `coordinate_pullback` |
| `geometry.geodesic` | [src/nablamath/ops/differential_geometry.py](../src/nablamath/ops/differential_geometry.py) | `geodesic` |
| `geometry.covariant` | [src/nablamath/ops/differential_geometry.py](../src/nablamath/ops/differential_geometry.py) | `covariant_derivative` |
| `integers.factor` | [src/nablamath/ops/abstract_algebra.py](../src/nablamath/ops/abstract_algebra.py) | `factor_integer` |
| `integers.certificate` | [src/nablamath/ops/abstract_algebra.py](../src/nablamath/ops/abstract_algebra.py) | `pocklington_certificate` |
| `galois.polynomial` | [src/nablamath/math/algebra/galois.py](../src/nablamath/math/algebra/galois.py) | `polynomial_galois` |
| `fields.primitive` | [src/nablamath/math/algebra/extensions.py](../src/nablamath/math/algebra/extensions.py) | `number_field` |
| `groups.permutation` | [src/nablamath/math/algebra/groups.py](../src/nablamath/math/algebra/groups.py) | `permutation_group` |
| `topology.integral_homology` | [src/nablamath/math/topology/homology.py](../src/nablamath/math/topology/homology.py) | `integral_homology` |
| `topology.cup` | [src/nablamath/math/topology/homology.py](../src/nablamath/math/topology/homology.py) | `cup_product` |
| `topology.continuity` | [src/nablamath/math/topology/general.py](../src/nablamath/math/topology/general.py) | `polynomial_continuity` |
| `calculus.elementary` | [src/nablamath/math/calculus/risch.py](../src/nablamath/math/calculus/risch.py) | `integrate_elementary` |
| `linear.algebraic_spectral` | [src/nablamath/math/linear_algebra/exact_spectral.py](../src/nablamath/math/linear_algebra/exact_spectral.py) | `algebraic_spectral` |
| `elliptic.rational_points` | [src/nablamath/math/number_theory/elliptic_curves.py](../src/nablamath/math/number_theory/elliptic_curves.py) | `rational_points` |
| `elliptic.isogeny` | [src/nablamath/math/number_theory/elliptic_curves.py](../src/nablamath/math/number_theory/elliptic_curves.py) | `two_isogeny` |
| `stochastic.ito` | [src/nablamath/math/probability/ito.py](../src/nablamath/math/probability/ito.py) | `multivariate_ito` |
| `stochastic.system` | [src/nablamath/math/probability/stochastic.py](../src/nablamath/math/probability/stochastic.py) | `sde_system` |
| `stochastic.refinement` | [src/nablamath/math/probability/stochastic.py](../src/nablamath/math/probability/stochastic.py) | `sde_refinement` |
| `ode.stiff` | [src/nablamath/numeric/stiff_ode.py](../src/nablamath/numeric/stiff_ode.py) | `solve_stiff_system` |
| `pde.poisson` | [src/nablamath/numeric/pde_general.py](../src/nablamath/numeric/pde_general.py) | `poisson_cartesian` |
| `pde.fem` | [src/nablamath/numeric/pde_general.py](../src/nablamath/numeric/pde_general.py) | `poisson_fem_1d` |
| `autograd.jet` | [src/nablamath/ops/autograd.py](../src/nablamath/ops/autograd.py) | `expression_derivatives` |
| `autograd.implicit` | [src/nablamath/ops/autograd.py](../src/nablamath/ops/autograd.py) | `implicit_derivative` |
| `autograd.solve_vjp` | [src/nablamath/ops/autograd.py](../src/nablamath/ops/autograd.py) | `linear_solve_vjp` |
| `bayesian.conjugate` | [src/nablamath/ops/bayesian_inference.py](../src/nablamath/ops/bayesian_inference.py) | `conjugate_update` |
| `bayesian.hierarchy` | [src/nablamath/ops/bayesian_inference.py](../src/nablamath/ops/bayesian_inference.py) | `gaussian_hierarchy` |
| `bayesian.sample` | [src/nablamath/ops/bayesian_inference.py](../src/nablamath/ops/bayesian_inference.py) | `sample_posterior` |
| `optimization.conic` | [src/nablamath/ops/convex_optimization.py](../src/nablamath/ops/convex_optimization.py) | `conic_program` |
| `optimization.certificate` | [src/nablamath/ops/convex_optimization.py](../src/nablamath/ops/convex_optimization.py) | `verify_linear_certificate` |
| `formal.translate` | [src/nablamath/formal/translate.py](../src/nablamath/formal/translate.py) | `translate_certificate` |
| `representations.decompose` | [src/nablamath/math/algebra/representations.py](../src/nablamath/math/algebra/representations.py) | `decompose_character` |
| `homological.homotopy` | [src/nablamath/math/algebra/homological.py](../src/nablamath/math/algebra/homological.py) | `chain_homotopy` |
| `bundles.transport` | [src/nablamath/math/geometry/fiber_bundles.py](../src/nablamath/math/geometry/fiber_bundles.py) | `parallel_transport` |
| `lie.decomposition` | [src/nablamath/ops/lie_algebra.py](../src/nablamath/ops/lie_algebra.py) | `lie_decomposition` |
| `lie.pbw` | [src/nablamath/ops/lie_algebra.py](../src/nablamath/ops/lie_algebra.py) | `pbw_reduce` |
| `lie.roots` | [src/nablamath/ops/lie_algebra.py](../src/nablamath/ops/lie_algebra.py) | `root_system` |
| `k.higher_finite_field` | [src/nablamath/ops/k_theory.py](../src/nablamath/ops/k_theory.py) | `finite_field_higher_k` |
| `variations.density` | [src/nablamath/ops/variational_calculus.py](../src/nablamath/ops/variational_calculus.py) | `euler_lagrange_density` |
| `pde.adaptive` | [src/nablamath/numeric/pde_general.py](../src/nablamath/numeric/pde_general.py) | `adaptive_poisson_1d` |
| `geophysics.wave` | [src/nablamath/ops/geophysics.py](../src/nablamath/ops/geophysics.py) | `acoustic_wave_2d` |
| `approximation.remez` | [src/nablamath/ops/approximation_theory.py](../src/nablamath/ops/approximation_theory.py) | `remez_polynomial` |
| `bayesian.diagnostics` | [src/nablamath/ops/bayesian_inference.py](../src/nablamath/ops/bayesian_inference.py) | `posterior_diagnostics` |
| `stochastic.adaptive` | [src/nablamath/math/probability/stochastic.py](../src/nablamath/math/probability/stochastic.py) | `adaptive_sde` |
| `schemes.radical` | [src/nablamath/math/geometry/schemes.py](../src/nablamath/math/geometry/schemes.py) | `zero_dimensional_radical` |
| `schemes.primary_zero_dimensional` | [src/nablamath/math/geometry/schemes.py](../src/nablamath/math/geometry/schemes.py) | `zero_dimensional_primary` |
| `topology.cohomology` | [src/nablamath/math/topology/homology.py](../src/nablamath/math/topology/homology.py) | `cohomology_basis` |
| `topology.integral_cohomology` | [src/nablamath/math/topology/homology.py](../src/nablamath/math/topology/homology.py) | `integral_cohomology` |
| `topology.cup_class` | [src/nablamath/math/topology/homology.py](../src/nablamath/math/topology/homology.py) | `cup_class` |
| `models.linear_integers` | [src/nablamath/math/logic/model_theory.py](../src/nablamath/math/logic/model_theory.py) | `decide_linear_integers` |
| `categories.paths` | [src/nablamath/math/category_theory/categories.py](../src/nablamath/math/category_theory/categories.py) | `presented_equality` |
| `categories.adjunction` | [src/nablamath/math/category_theory/functors.py](../src/nablamath/math/category_theory/functors.py) | `finite_adjunction` |
| `fields.arithmetic` | [src/nablamath/math/algebra/extensions.py](../src/nablamath/math/algebra/extensions.py) | `field_arithmetic` |
| `sets.progression` | [src/nablamath/math/set_theory/finite.py](../src/nablamath/math/set_theory/finite.py) | `progression` |
| `elliptic.add` | [src/nablamath/math/number_theory/elliptic_curves.py](../src/nablamath/math/number_theory/elliptic_curves.py) | `rational_add` |

## Ações da consolidação 1.0

| Ação | Implementação |
|---|---|
| `manifold.metric` | `ops.advanced_calculus_manifold:symbolic_metric` |
| `manifold.interior` | `ops.advanced_calculus_manifold:interior_product` |
| `manifold.bracket` | `ops.advanced_calculus_manifold:lie_bracket` |
| `manifold.lie_derivative` | `ops.advanced_calculus_manifold:lie_derivative` |
| `manifold.hodge` | `ops.advanced_calculus_manifold:hodge_star` |
| `manifold.stokes` | `ops.advanced_calculus_manifold:stokes_box` |
| `algebra_crypto.field` | `ops.abstract_algebra_crypto:finite_field` |
| `algebra_crypto.elliptic` | `ops.abstract_algebra_crypto:elliptic` |
| `algebra_crypto.groebner` | `ops.abstract_algebra_crypto:groebner_basis` |
| `stochastic_info.generator` | `ops.stochastic_and_information:stochastic_generator` |
| `stochastic_info.fokker_planck` | `ops.stochastic_and_information:fokker_planck_1d` |
| `stochastic_info.gaussian` | `ops.stochastic_and_information:gaussian_information` |
| `stochastic_info.discrete` | `ops.stochastic_and_information:discrete_information` |
| `stochastic_info.channel` | `ops.stochastic_and_information:channel_capacity` |
| `stochastic_info.gp` | `ops.stochastic_and_information:gaussian_process` |
| `stochastic_info.gaussian_copula` | `ops.stochastic_and_information:gaussian_copula` |
| `stochastic_info.clayton_copula` | `ops.stochastic_and_information:clayton_copula` |

## Catálogo da entrega 1.0

A expansão v1 acrescenta 30 operações canônicas (133 no total), além das
156 ações especializadas já inventariadas. Seus contratos vivem em
`src/nablamath/ops/v1_catalog.py`; os 30 casos reproduzíveis estão em
`examples/v1/catalog_cases.json`. Os cinco módulos canônicos têm mais de
10 mil linhas de implementações próprias e integração, não uma concatenação
dos motores anteriores. Consulte [o contrato](releases/V1.md) e os
[resultados executados](releases/V1_VALIDATION.md) para limites e evidências.
