# Auditoria de conclusão matemática

**Conclusão: não foi atingido 100%.** “Toda a matemática” não é um requisito finito,
e vários itens específicos solicitados continuam ausentes ou possuem apenas um
subconjunto declarado. Este documento impede que volume de código seja confundido
com completude científica.

| Pedido | Implementado neste recorte | Ainda necessário para 100% do pedido |
|---|---|---|
| F4/F5 de Faugère | F4 racional de referência com lotes por grau, matrizes Macaulay e eliminação esparsa exata; F5 de referência com signatures, reduções signature-safe, critérios e conclusão auditada por Buchberger | estruturas compactas/fora da memória industriais, critérios F5 completos certificados, backend CUDA/Triton real e benchmarks em hardware |
| Extensões algébricas | `Q(α)` exato para polinômios irredutíveis de grau 2/3 | fatoração/irreducibilidade geral, embeddings, corpos de decomposição, grupos de Galois |
| Álgebra linear geral | matrizes racionais básicas já existentes | autovalores algébricos gerais, Jordan certificada e SVD exata/algebraica |
| Diferenciação simbólica | toda a AST racional atual, com produto, quociente, potências e domínio | ampliar a AST com funções elementares/especiais e provar regras em Lean |
| Integração simbólica | polinômios racionais univariados certificados | algoritmo de Risch completo e extensões transcendentes |
| Limites/séries | jets de Taylor exatos, limites e Laurent racional em pontos racionais | Laurent transcendente, limites transcendentes e L'Hôpital geral com hipóteses |
| Análise complexa | resíduos e polos exatos de funções racionais em pontos racionais | funções transcendentes, ramos e contornos gerais certificados |
| SAT/SMT | DPLL, CDCL de referência, resolução proposicional, LRA racional, lógica diferencial inteira e semântica exata de bit-vectors/arrays persistentes | bit-blasting, congruence closure, teoria completa de arrays, aritmética inteira geral, Nelson–Oppen e desempenho industrial |
| ATP de primeira ordem | modelos finitos, unificação com occurs-check e saturação limitada por resolução/superposição com igualdade sobre cláusulas já normalizadas | clausificação/skolemização, ordenação de redução industrial, subsunção/indexação, busca justa completa e certificados Lean |
| Topologia algébrica | complexos simpliciais, homologia racional e π1 de grafos | homologia sobre PID com torsão, π1 geral, cohomologia e sequências espectrais |
| Geometria diferencial | formas polinomiais, wedge, derivada exterior e tensores exatos de métrica/Christoffel/Riemann/Ricci a partir do 2-jet | atlas, mudanças de carta, pullback, integração e teoremas globais |
| Curvas elípticas | lei de grupo sobre `Fp` e multiplicação escalar | protocolos, curvas padronizadas, side-channel hardening, emparelhamentos e provas |
| Primalidade | Miller–Rabin determinístico 64-bit e AKS educacional limitado | grandes inteiros certificados, ECPP/APR-CL e benchmarks industriais |
| Fatoração | tentativa elementar preexistente | Quadratic Sieve e GNFS completos |
| Probabilidade contínua | Normal, Exponencial e Poisson; momentos/CDFs | medidas gerais, transformadas, inferência e integração simbólica abrangente |
| Processos/Itô | Browniano, Euler–Maruyama e fórmula de Itô simbólica polinomial | funções gerais, ordens fortes/fracas, Milstein e verificação de convergência |
| E-graph | núcleo limitado e auditável | linguagem geral de padrões, análises de e-class, regras transcendentes e provas Lean |
| Ponte Lean/dados | instâncias racionais, identidades gerais das regras algébricas/e-graph e pipeline local | teoremas gerais para cálculo/novos domínios, autoformalização revisada e dataset público aprovado |

## Regra de publicação

Uma linha só pode migrar para “completa” após API, casos negativos, propriedades,
referência independente, benchmark, documentação de domínio e — quando a alegação
for formal — prova aceita pelo kernel. O `math.txt` é regenerado a partir das fontes
atuais e substitui integralmente a versão anterior, mas não altera esta auditoria.

<!-- nabla:contracts:start -->
## Contratos executáveis e pendências atuais

A matriz registra 213 requisitos com perfis parciais, 0 planejados e 0 integralmente validados. Uma referência de implementação não equivale à aceitação integral.

- [Matriz original dos 213 requisitos](acceptance/evidence_matrix.json).
- [Rastreabilidade de fases, requisitos, testes e evidências](acceptance/vision_traceability.json).
- [Domínios, operações, recusas e tolerâncias](acceptance/scientific_capabilities.yaml).

F0 explicita contratos e infraestrutura; F13 continua horizonte aberto. Os perfis de software não demonstram autonomia científica geral. Provas formais exigem kernel e auditoria de hipóteses; GPU exige execução identificada; observações e revisão externa não são substituídas por fixtures ou identidade declarada.

Verificar: `python tools/check_roadmap.py` e `python tools/check_public_contracts.py`, na raiz do repositório.
<!-- nabla:contracts:end -->
