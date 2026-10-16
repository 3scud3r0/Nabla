# Ampliação integrada da matemática exata — contratos e reprodução

Esta expansão adiciona **cinco módulos algorítmicos**, uma camada de adaptação de 29 operações ao catálogo público e novos testes. Ela **não esgota toda a matemática**: a disciplina é aberta, e implementação computacional não equivale a prova formal universal, validação física ou descoberta científica.

## Organização

| Arquivo | Domínio e técnica | Garantia |
|---|---|---|
| [advanced_number_theory.py](../../src/nablamath/math/exact/advanced_number_theory.py) | MDC estendido, fatoração, funções aritméticas, primalidade, Tonelli–Shanks, BSGS, frações contínuas e Pell | Aritmética inteira exata, primalidade determinística **somente n<2⁶⁴** |
| [finite_fields.py](../../src/nablamath/math/exact/finite_fields.py) | Polinômios sobre Fₚ, Euclides, Rabin, Fₚ[x]/(f), inversa, traço e norma | Operações em corpo finito quando **f é irredutível** |
| [rigorous_analysis.py](../../src/nablamath/math/exact/rigorous_analysis.py) | Intervalos, Horner, Bernstein adaptativo, raízes por bisseção, integral de polinômios, Padé | Inclusões e identidades racionais exatas, com orçamento |
| [discrete_optimization.py](../../src/nablamath/math/exact/discrete_optimization.py) | Bellman–Ford, Floyd–Warshall, fluxo/corte, König, Kruskal, atribuição DP e Tarjan | Testemunhos exatos e invariantes combinatórios |
| [finite_probability.py](../../src/nablamath/math/exact/finite_probability.py) | Distribuições finitas, momentos, convolução, independência, inferência categórica e Markov | Normalização e identidades com frações exatas |
| [adapters.py](../../src/nablamath/math/exact/adapters.py) | Validação de operações, roteamento e resultados JSON | Integração única ao catálogo, sem segundo motor de CLI |

O [laboratório anterior](EXACT_LABORATORY.md) permanece intacto em \`laboratory.py\`, e todos os algoritmos podem ser importados pelo namespace \`nablamath.math.exact\`. O desktop local fornece descoberta e execução pelo mesmo motor de sessão em `GET /api/catalog` e `POST /api/calculate`; consulte [o guia do painel](../DESKTOP.md). O ponto de integração é \`src/nablamath/calc/catalog.py\`: operações declaradas entram automaticamente em \`AREAS\`, \`REQUIRED\`, \`OPTIONAL\`, \`CalculationSession.execute\` e \`nabla calc\`. Os recibos da versão 1 e o replay de notebooks permanecem na infraestrutura atual.

## 29 operações de cálculo

**Teoria dos números:** \`nt_primality\`, \`nt_factorization\`, \`nt_modular_roots\`, \`nt_discrete_log\`, \`nt_pell\`, \`nt_primitive_root\`.

**Álgebra finita:** \`ff_irreducible\`, \`ff_extension\`.

**Análise exata:** \`analysis_interval\`, \`analysis_extrema\`, \`analysis_root\`, \`analysis_pade\`, \`analysis_integral\`.

**Grafos e otimização:** \`graph_bellman_ford\`, \`graph_apsp\`, \`graph_max_flow\`, \`graph_matching\`, \`graph_mst\`, \`graph_assignment\`, \`graph_scc\`.

**Probabilidade:** \`prob_binomial\`, \`prob_poisson_binomial\`, \`prob_distribution\`, \`prob_convolution\`, \`prob_joint\`, \`prob_hypergeometric\`, \`prob_dirichlet\`, \`prob_stationary\`, \`prob_propagate\`.

### Exemplos pela CLI existente

\`\`\`sh
nabla calc nt_primality --arguments '{"n":2305843009213693951}'
nabla calc nt_modular_roots --arguments '{"a":2,"prime":7}'
nabla calc ff_extension --arguments '{"prime":2,"modulus":[1,1,1],"element":[0,1]}'
nabla calc analysis_root --arguments '{"coefficients":[-2,0,1],"lower":1,"upper":2,"steps":48}'
nabla calc graph_max_flow --arguments '{"vertices":["s","a","t"],"edges":[["s","a","3/2"],["a","t","1"]],"source":"s","sink":"t"}'
nabla calc prob_stationary --arguments '{"transition":[["1/2","1/2"],["1/4","3/4"]]}'
\`\`\`

Os dados são números inteiros ou frações representadas como strings, sem conversão de ponto flutuante para exatidão. A saída é JSON auditável, incluindo \`content_id\` de recibo quando chamada via \`CalculationSession\`. O modelo de notebook permite reexecutar os cálculos a partir dos argumentos declarados.

## Limites de escopo que precisam permanecer visíveis

- Primalidade usa o conjunto determinístico de testemunhos de Miller–Rabin válido para inteiros não negativos **menores que 2⁶⁴**. Não aplique a números maiores.
- Fatoração completa só até 10¹² com divisão por tentativa. Isso não é um fatorador geral de inteiros grandes.
- Logaritmo discreto BSGS e raiz primitiva só para módulo primo **até 10⁹**. Não são ferramentas criptográficas para curvas, chaves ou grupos grandes.
- Teste de irredutibilidade, corpos finitos e operações de traço/norma só em polinômios de grau até 12 sobre primos até 257, com cardinalidade até 10⁹.
- Intervalos racionais excluem \`float\`. A subdivisão de Bernstein pode falhar por limite de segmentos; seu sucesso fornece intervalos que incluem os mínimos e máximos, mas não os valores exatos dos extremos.
- Bisseção com sinais opostos certifica existência de alguma raiz real; não prova unicidade. Padé certifica correspondência da série de Taylor, não erro global de \`exp\`.
- Grafos têm limites finitos de vértices e arestas. Bellman–Ford rejeita ciclo negativo alcançável; Floyd–Warshall rejeita qualquer ciclo negativo; fluxo máximo devolve capacidade de corte igual ao fluxo computado.
- O matching calcula uma cobertura mínima de vértices bipartidos, não resolve grafos gerais. A atribuição usa programação dinâmica exponencial com n≤12.
- As distribuições probabilísticas usam suporte discreto finito e hipóteses explícitas de independência quando fazem convolução. A distribuição estacionária Markov só é reportada quando é **única**, sem alegar convergência.
- Funções não integradas diretamente ao catálogo ainda estão disponíveis via Python, mantendo a estrutura convencional de biblioteca e evitando 1 operação de CLI por método interno.

## Reproduzir e revisar

\`\`\`sh
python -m pip install -e ".[test]"
python -m pytest -q tests/math/test_exact_laboratory.py tests/math/test_advanced_exact_integration.py tests/integration/test_advanced_exact_notebook.py
python -m pytest -q tests/regression/test_public_api.py
python -m pytest -q
python tools/release_readiness.py
python tools/build_math_bundle.py
python tools/build_nabla_bundle.py
python tools/build_math_bundle.py --check
python tools/build_nabla_bundle.py --check
\`\`\`

A regeneração dos bundles de fontes versionados é **obrigatória** após qualquer alteração no código; seu não cumprimento impede afirmar que o PR passou nos gates de release. Mudanças neste perfil alpha foram registradas explicitamente em \`src/nablamath/public_api.json\` para que o inventário de operações instalado não diverja do catálogo.

A suíte de testes não substitui revisão matemática independente, nem implica que as 213 exigências científicas do roadmap estejam satisfeitas.
