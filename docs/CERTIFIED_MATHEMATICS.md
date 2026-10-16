# Análise certificada e cadeias finitas

Este perfil acrescenta seis operações públicas à `CalculationSession`, todas
reexecutáveis por notebooks e acessíveis por `nabla calc`. Os cálculos usam
racionais exatos. As alegações analíticas dos certificados Python não são
identificadas como provas Lean.

| Operação | Contrato | Limite principal |
|---|---|---|
| `polynomial_range` | enclosure por coeficientes de Bernstein e subdivisão | grau até 32; 256 subdivisões |
| `certified_integral` | quadratura com resto por derivadas limitado exatamente | polinômios; até 1.024 partes |
| `certified_function` | enclosure de exp, log, sin e cos por séries e restos explícitos | argumento limitado; 512 termos |
| `markov_hitting` | probabilidade de primeira entrada e momentos condicionais | 24 estados |
| `markov_stationary` | distribuições extremas nas classes fechadas e períodos | 24 estados |
| `markov_rewards` | recompensas descontadas por sistema linear exato | desconto em [0,1) |

```sh
.venv/bin/nabla calc polynomial_range --arguments '{"coefficients":[0,0,1],"lower":-1,"upper":1,"subdivisions":2}'
.venv/bin/nabla calc certified_integral --arguments '{"coefficients":[0,0,0,0,1],"lower":0,"upper":1}'
.venv/bin/nabla calc certified_function --arguments '{"kind":"exp","value":1,"tolerance":"1/100000000"}'
.venv/bin/nabla calc markov_hitting --arguments '{"transition":[["1/2","1/2"],[0,1]],"targets":[1]}'
```

## Intervalos e análise

`RationalInterval` oferece soma, subtração, produto, divisão, potências inteiras,
valor absoluto, bisseção, hull, interseção e raiz quadrada com extremos racionais.
Não há erro de arredondamento de ponto flutuante, mas dependências repetidas
podem alargar os intervalos. Divisões por intervalos contendo zero são recusadas.
Potências não positivas preservam a exigência conservadora de domínio não nulo.
Floats, booleans e racionais acima do orçamento não entram silenciosamente.

O enclosure de polinômios converte `p(a+(b-a)t)` à base de Bernstein em [0,1].
O mínimo e máximo dos coeficientes encerram o alcance porque as funções de base
são não negativas e somam um. A união dos enclosures de uma partição continua
cobrindo o intervalo inteiro. Os extremos retornados não são necessariamente
os extremos exatos da função.

A quadratura suporta ponto médio, trapézio e Simpson. Cada parte registra a
estimativa, os coeficientes de Bernstein da derivada necessária e o resto:

- Ponto médio: `M₂ h³/24`.
- Trapézio: `M₂ h³/12`.
- Simpson em um painel: `M₄ h⁵/2880`.

O refinamento divide a parte com maior erro certificado. Se o orçamento acabar,
a função falha, sem publicar uma aproximação como certificada. Extremos invertidos
preservam o sinal; polinômios até grau três têm erro Simpson nulo.

Para exp, o argumento é reduzido por potências de dois até módulo 1/2. A série
usa um majorante geométrico para a cauda, e os enclosures são elevados ao quadrado
para retornar ao argumento original. Log usa a série de atanh com resto limitado
por uma série geométrica. Sin e cos usam o teorema do resto de Taylor e o fato
de que suas derivadas têm módulo no máximo um. Esses fatos analíticos são parte
do contrato matemático; sua formalização Lean não foi implementada.

O perfil aceita exp/sin/cos em [-8,8], log em [1/8,8], e pede uma largura máxima
positiva. O limite de 4.096 bits para racionais intermediários pode encerrar
pedidos de precisão excessiva antes do número máximo de termos.

## Cadeias de Markov

As transições são racionais não negativas com soma exatamente um por linha.
Estados-alvo são parados na primeira entrada, mesmo quando não são absorventes
na matriz original. Estados que não alcançam o alvo têm probabilidade zero.

Para os estados que alcançam os alvos, o sistema restrito calcula
`h = Qh+r`. Depois calcula `g = h+Qg` e `s = h+2Qg+Qs`.
Aqui `g=E[T·1_hit]` e `s=E[T²·1_hit]`. Quando `h>0`, os momentos condicionais
são `g/h` e `s/h`. Quando `h<1`, a média incondicional é infinita, mesmo que a
média condicionada ao sucesso seja finita. Eventos de probabilidade zero não
recebem momentos condicionais inventados.

Classes comunicantes fechadas fornecem as distribuições estacionárias extremas;
toda distribuição estacionária é mistura convexa delas. O período é informado:
uma distribuição estacionária única não garante convergência de uma cadeia
periódica. Tempos médios de retorno na classe são `1/πᵢ`.

Recompensas com `0≤γ<1` resolvem `(I-γP)v=r`. O recibo reconfere resíduos exatos
e informa o majorante `||r||∞/(1-γ)`. Não há suporte implícito ao caso γ=1.

## Provas executáveis e reprodução

O corpus `lean/Conformance/` contém 30.000 instâncias geradas de dez famílias:
diferença de quadrados, quadrado afim, distributividade, inverso com hipótese,
monotonicidade afim, não negatividade de quadrados, aritmética racional fechada,
quadrado em intervalo simétrico, mínimo quadrático e soma de frações.
Cada família usa 3.000 pares de coeficientes racionais, em seis unidades de
compilação com até 500 teoremas cada. Não são 30.000 algoritmos,
resultados de pesquisa novos ou um holdout privado.

As fontes são emitidas a partir de `FormalStatement`, com hipóteses de domínio,
e registradas em um manifesto tipado por hash. O runner compila todas as famílias
com o Lean fixado, exige a auditoria de axiomas de cada nome esperado e só aceita
uma unidade inteira quando seu compilador termina com sucesso. Falhas e timeouts
continuam separados. Fontes anteriores intactas são arquivadas antes de refresh.

```sh
bash scripts/setup_lean_std.sh
.venv/bin/python tools/rational_proof_corpus.py --check
.venv/bin/python tools/rational_proof_corpus.py --verify .nabla/corpus-novo --workers 3
OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/math/test_certified_analysis.py tests/math/test_markov_analysis.py tests/test_lean_std.py
```

O workflow `rational-conformance.yml` reproduz esses passos em Linux. Sua execução
local não comprova que a versão modificada já passou no GitHub Actions.

Os testes usam antiderivadas exatas, extremos simbólicos e nullspaces do SymPy,
referências transcendentes de alta precisão, leis geométricas de primeira entrada,
ruína do jogador, resíduos e adulterações com hashes recalculados. Referências de
alta precisão são oráculos de comparação; não substituem os restos analíticos.

## O que permanece em aberto

Não estão implementados neste perfil: integração racional geral com quadráticas
irredutíveis, interval Newton multivariado, cálculo intervalar transcendente para
intervalos de entrada, derivadas arbitrárias de funções recebidas e provas Lean
dos teoremas analíticos usados pelos certificados Python. O laboratório Mathlib
original continua sendo uma validação separada.

Para um próximo lote finito de seis operações com profundidade semelhante,
estimo **1.000–3.000 linhas manuais adicionais**, incluindo testes e integração,
excluindo fontes geradas. É uma estimativa de planejamento baseada no tamanho
deste perfil, não uma medição da visão inteira. O roteiro amplo ainda tem 213
requisitos parciais e dependências de revisão, medições e experimentos externos;
não há uma quantidade finita ou defensável de linhas que garanta sua conclusão.
