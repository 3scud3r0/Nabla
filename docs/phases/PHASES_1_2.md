# Fases 1 e 2 — calculadora científica e Forge

Esta implementação fornece todos os arquivos nomeados nas duas fases de
`vision.md`, usando as bibliotecas matemáticas existentes como núcleo. As APIs
abaixo executam cálculos e verificações; não são arquivos de placeholder. A
cobertura matemática é delimitada pelos contratos, não universal. A calibração e
a diversidade medidas são locais; validação externa continua sendo outro critério.

## Instalação e comandos

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest -q
.venv/bin/python tools/build_math_bundle.py --check

.venv/bin/nabla calc evaluate \
  --arguments '{"source":"(x+x)/x","values":{"x":3}}' \
  --notebook .nabla/calculo-novo.json
.venv/bin/nabla replay-notebook .nabla/calculo-novo.json

.venv/bin/nabla forge .nabla/forge-v2-novo --all-families \
  --count 24 --seed 42 --sizes 2 3 4 --calibrate \
  --license MIT --provenance 'Exemplos sinteticos locais produzidos por inverse-v2'
.venv/bin/nabla check-bundle .nabla/forge-v2-novo
```

Os destinos de notebook e factory devem ser novos para preservar arquivos
existentes. MIT é uma declaração para os exemplos sintéticos produzidos neste
comando, não uma licença atribuída a dados externos. Não há dependências novas
obrigatórias ou chamadas a serviços remotos.

Sem `--families`/`--all-families`, `nabla forge` mantém o ciclo v1 anterior, com
figuras/documentos/PDF opcional e suas duas famílias. `--families` seleciona um
subconjunto dos oito identificadores v2; `--sizes` alterna os tamanhos. O formato
v2 exporta dados/rastros/calibração; PDF permanece no fluxo v1. `check-bundle`
seleciona automaticamente o verificador pela versão do manifesto.

## Fase 1: arquivos e responsabilidades

Todos os caminhos de código abaixo são relativos a `src/nablamath/`.

| Arquivo/diretório solicitado | Implementação |
|---|---|
| `core/semantic_ir.py` | `SemanticExpression`: AST, tipos, domínio, unidade de resultado, obrigações e identidade independente da notação; contratos v1 anteriores preservados |
| `core/types.py` | `ScientificType`, domínios e formas escalares/vetoriais/matriciais |
| `core/units.py` | Sete dimensões SI, escalas racionais, inferência dimensional e `Quantity` |
| `core/precision.py` | Precisão decimal, erro absoluto exato, arredondamento externo e intervalos racionais |
| `core/obligations.py` | Obrigações não nulas/positivas/não negativas; estados satisfeita, violada ou não resolvida |
| `calc/session.py` | Sessões com bindings exatos, unidades, operações nas nove áreas, recibos versionados |
| `calc/notebook.py` | Células imutáveis encadeadas, persistência sem sobrescrita, hashes e reexecução independente dos resultados salvos |
| `math/linear_algebra/` | Matrizes existentes, resolução retangular com núcleo, LU pivotada, base ortogonal racional, condicionamento e polinômio característico |
| `math/calculus/` | API coesa para derivadas, primitivas polinomiais, integrais definidas, limites racionais, séries e integradores de EDO existentes |

Além dos caminhos obrigatórios, foram acrescentados fatoração racional em
`math/polynomials/factorization.py`, cônicas/construções em
`math/geometry/conics.py`, inferência estatística em
`math/statistics/inference.py` e otimização convexa com certificado KKT em
`math/optimization/quadratic.py`.

### Sessão com unidades e notebook

```python
from nablamath.calc import CalculationSession, Notebook
from nablamath.core.units import KILOMETER, HOUR

session = CalculationSession(precision=34)
session.bind('distance', 72, KILOMETER).bind('time', 1, HOUR)
calculation = session.evaluate('distance/time')
assert calculation.to_data()['result']['value'] == '20'  # m/s, canônico SI

notebook = Notebook('Velocidade')
notebook.append(calculation)
assert notebook.replay() == 1
# notebook.save('arquivo-novo.json')
```

A sintaxe é a AST racional já existente: inteiros, símbolos, operações aritméticas
racionais e potências inteiras limitadas. `x^2` e `x**2` possuem a mesma identidade.
Isso não promete identificar todas as expressões matematicamente equivalentes.
Condições de denominador ou de potência não positiva permanecem no objeto, mesmo
quando uma forma derivada é constante. Entradas são inteiros/frações, sem coerção
silenciosa de floats no núcleo exato. Grandezas são avaliadas em SI, convertendo
os valores antes da aritmética. Somar dimensões incompatíveis é um erro.

Unidades são multiplicativas: não há conversões afins Celsius/Fahrenheit. A
inferência requer escalares racionais; matrizes e vetores são tratados pela API
de álgebra linear, não pelo parser escalar. Aproximações decimais registram o
valor racional original, política e erro absoluto; não se apresentam como exatas.
Intervalos que atravessam zero não podem ser usados como divisores.

### Operações disponíveis em `CalculationSession.execute`

| Área | Operações da sessão e limites principais |
|---|---|
| Álgebra | `evaluate`, `simplify` com hipóteses, `factor` racional com multiplicidades e residual não resolvido |
| Álgebra linear | `solve_linear` (única/indeterminada/inconsistente), `lu`, `orthogonal_basis`; matrizes até 32×32 nas novas APIs |
| Cálculo | `differentiate`, `integrate`, `limit`, `series`, `ode`; primitivas/integrais exatas polinomiais; séries até ordem 8 |
| Discreta | `binomial`, `topological_sort`; bibliotecas de grafos/lógica/recorrências existentes continuam acessíveis diretamente |
| Probabilidade | `markov`, transições racionais finitas, até 16 estados e 1000 passos na sessão |
| Estatística | `statistics`: média/variância, teste de sinais (`median`), média móvel (`window`) e intervalo de Chebyshev (`population_variance`, `radius`) |
| Numérica | `approximate`, `condition`; precisão de 8–1000 dígitos e condicionamento exato na norma infinito |
| Otimização | `optimize` linear 2D em caixa, `quadratic_optimize` estritamente convexo com até 8 variáveis e 8 desigualdades |
| Geometria | `geometry` para triângulos, `conic`; APIs diretas para transformações afins e circuncentro racional |

Exemplos de argumentos JSON:

```bash
.venv/bin/nabla calc differentiate --arguments '{"source":"1/x"}'
.venv/bin/nabla calc integrate --arguments '{"source":"3*x*x","start":0,"end":2}'
.venv/bin/nabla calc solve_linear --arguments '{"matrix":[[1,1],[1,-1]],"rhs":[3,1]}'
.venv/bin/nabla calc statistics --arguments '{"values":[1,2,3,4],"median":0,"window":2,"population_variance":1,"radius":2}'
.venv/bin/nabla calc quadratic_optimize --arguments '{"hessian":[[2]],"linear":[-4],"constraints":[[1]],"upper":[1]}'
```

O intervalo de Chebyshev exige observações iid e a variância populacional
conhecida **declarada pelo chamador**; não usa variância amostral como se fosse
conhecida. O teste de sinais exige sinais independentes equiprováveis sob a
hipótese nula; empates são excluídos. Esses pressupostos não são inferidos dos dados.

A fatoração informa `complete=false` para um residual sem fatores racionais
identificados; não chama um polinômio como `x²+1` de resolvido sobre os racionais.
Um orçamento explícito limita enumeração de divisores. A base ortogonal não é
normalizada: evita introduzir raízes irracionais em uma API racional.
A otimização quadrática verifica Hessiana definida positiva, viabilidade, sinal
dos multiplicadores, estacionariedade e complementaridade. Outros problemas não
convexos são rejeitados, não classificados como globalmente resolvidos.

## Fase 2: arquivos e responsabilidades

| Arquivo solicitado | Implementação |
|---|---|
| `forge/task_spec.py` | Problemas imutáveis para oito famílias, esquema versionado e testemunhos separados |
| `forge/reverse_builder.py` | Despacho de construtores v2, preservação exata de `generate()` v1 |
| `forge/sampling.py` | Sementes independentes de 63 bits e planos balanceados por família/tamanho |
| `forge/difficulty.py` | Execução de duas estratégias, orçamento medido, respostas verificadas, falhas e calibração reproduzível em escopo declarado |
| `forge/deduplicate.py` | Identidade semântica, normalização polinomial, equivalência por operações de linha e relatório de diversidade local |
| `forge/constructors/integration.py` | Primitiva escolhida antes do integrando |
| `forge/constructors/polynomial.py` | Fatores/raízes escolhidos antes da multiplicação |
| `forge/constructors/linear_systems.py` | Solução escolhida antes do vetor independente |
| `verify/trace.py` | Verificador por família e recibos que são conferidos por reexecução |
| `datasets/splits.py` | Splits determinísticos por família inteira e auditoria de contaminação semântica |

Os outros cinco exemplos da fase também estão implementados como construtores:
`spectrum.py`, `optimization.py`, `markov.py`, `identities.py` e
`counterexamples.py`. `forge/solvers.py` recebe apenas o problema, nunca o
respectivo testemunho. `forge/factory.py` integra geração, solução, verificação,
deduplicação, partição, direitos declarados e exportação atômica.

### Construção, solução e verificação independentes

| Identificador | Construção inversa | Solução e conferência |
|---|---|---|
| `polynomial_integral` | Escolher primitiva e derivar coeficientes | Integrador simbólico vs divisão direta; verificador deriva a resposta e compara todos os coeficientes |
| `factored_polynomial` | Escolher raízes inteiras e multiplicar fatores | Teorema das raízes racionais vs grade de raízes; n+1 avaliações exatas certificam a identidade de grau n, incluindo multiplicidades |
| `linear_system` | Escolher solução e matriz diagonalmente dominante | Eliminação vs inversão; resíduos e determinante exatos |
| `prescribed_spectrum` | Base de Householder racional e autovalores escolhidos | Polinômio característico por recorrência vs interpolação de determinantes; resíduos de todos os autovetores e base invertível |
| `convex_quadratic` | Escolher ótimo e reconstruir Hessiana positiva/termo linear | Eliminação vs inversão; critério de Sylvester e estacionariedade |
| `stationary_markov` | Escolher distribuição e reconstruir transição estritamente positiva | Sistemas estacionários por duas estratégias; simplex, resíduos e positividade que garante unicidade |
| `polynomial_identity` | Reescrita distributiva válida no domínio polinomial | Expansão simbólica vs interpolação; grade exata de tamanho suficiente para os graus certificados |
| `counterexample` | Construir uma igualdade deliberadamente falsa e uma violação conhecida | Busca por norma L1 vs ordem reversa; desigualdade racional exata e pertencimento ao domínio inteiro declarado |

```python
from nablamath.forge import generate_task
from nablamath.forge.solvers import solve_task
from nablamath.verify.trace import build_trace

item = generate_task('prescribed_spectrum', seed=42, size=3)
answer = solve_task(item.task)  # não recebe item.witness
trace = build_trace(item.task, answer)
assert trace.to_data()['verification']['valid']
assert trace.replay()
```

A geração usa tamanhos de 1 a 8. A estratégia alternativa de fatoração/espectro
busca raízes inteiras em -5..5, que é o domínio dos respectivos construtores.
Problemas arbitrários fora desse domínio podem falhar nessa estratégia sem
invalidar a resposta de outra. Não há promessa de resolver espectros irracionais,
integrais gerais ou otimização não convexa. Os contraexemplos tratam conjecturas
polinomiais deliberadamente construídas, não hipóteses científicas novas.

### Dificuldade, diversidade e partições

`--calibrate` executa as duas estratégias com verificadores separados. O orçamento
conta linhas Python realmente executadas no pacote e em `fractions.py`, incluindo
aritmética racional; tempo de parede é registrado apenas como informação adicional.
As observações distinguem `completed`, `budget_exhausted`,
`unsupported_or_failed` e `wrong_answer`. Os rótulos `low_budget`, `medium_budget`,
`high_budget`, `strategy_sensitive` e `unresolved_within_budget` dependem de
sucesso, estratégia e trabalho medido — não apenas do tamanho da expressão.

A calibração fica limitada a 128 problemas e 2 milhões de eventos por solução.
Seu recibo inclui versão do Python, plataforma, IDs dos problemas, respostas,
verificações e resultados negativos. As contagens dependem do interpretador e da
versão do código. Tempos e IDs de calibração que os incluem não são determinísticos
em bytes; sem calibração, os bundles v2 são determinísticos para as mesmas opções.

Os perfis são **benchmarks locais relativos aos solvers incluídos**, não calibração
externa contra SymPy/Maple/solvers comerciais ou dificuldade humana. Reexecução
confere as respostas e coerência dos rótulos; não autentica quem mediu o tempo.
Ganhos de aprendizado, novidade e qualidade externa de datasets não foram medidos.

A deduplicação remove variantes sintáticas de identidades e sistemas equivalentes
por operações de linha, além de repetições exatas. O card mede tentativas,
duplicatas, tarefas únicas e cobertura por família/tamanho. Essas métricas locais
não demonstram diversidade científica externa. Famílias inteiras ficam reservadas
a uma partição, incluindo todos os tamanhos/sementes. Os percentuais são aplicados
à lista fixa de oito famílias em ordem determinística com salt; com oito grupos,
80/10/10 corresponde a seis famílias de treino, uma de validação e uma de teste.
Um subconjunto escolhido pelo usuário pode conter somente uma partição.

## Compatibilidade e validação

Os contratos `ScientificTask`, `GeneratedTask` e `generate()` v1 permanecem
compatíveis, incluindo as sementes e testemunhos usados antes desta rodada.
`nablamath.dataset` v1 continua existente; `nablamath.datasets` é a API de
partições v2 solicitada por `vision.md`. Não há renomeação destrutiva.

Os testes dedicados são `tests/test_phase1_calculator.py` e
`tests/test_phase2_forge.py`. Eles exercitam todos os comandos de sessão,
reexecução de notebooks, todos os construtores em tamanhos 1/3/8 e três sementes,
duas estratégias de solução, singularidades, multiplicidades, KKT, pressupostos
estatísticos, limites, contaminação, adulteração mesmo com hashes recalculados,
reprodutibilidade e preservação de arquivos. A instalação dos módulos também
foi verificada separadamente a partir de uma wheel, fora do checkout.

A documentação não marca as fases como cientificamente encerradas: os critérios
externos de `vision.md` continuam aplicáveis. Todos os arquivos solicitados e os
fluxos delimitados descritos aqui estão implementados e testados.

### Evidência da rodada

- Suíte completa: **327 testes e 247 subtestes aprovados**, sem falhas ou skips.
- Instalação em diretório separado a partir da wheel: imports, calculadora e
  geração/solução/verificação das oito famílias aprovados.
- Exemplo retido em `.nabla/phases12-final/`: 24 problemas sem duplicatas
  semânticas, 18 de treino, 3 de validação e 3 de teste; 48 execuções de solver
  concluídas e verificadas na calibração local.
- `nabla check-bundle .nabla/phases12-final` e a reexecução do notebook de exemplo
  retornaram válidos; `math.txt` foi regenerado e conferido; diff sem erros de whitespace.

Os artefatos `.nabla/` são saídas locais ignoradas pelo Git. Nenhum commit,
publicação remota ou declaração de validação científica externa foi realizado.
