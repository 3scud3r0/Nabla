# Ciclo científico local e avanços de vision.md

Esta entrega estabiliza a base e implementa recortes executáveis das fases 1–12.
Não encerra essas fases: os critérios científicos em `vision.md` continuam em
vigor. A fase 13 é um horizonte aberto; contratos versionados ajudam a evolução,
mas não implementam teorias, tecnologias ou hardware ainda inexistentes.

As fases 1 e 2 foram ampliadas posteriormente com todos os arquivos solicitados,
oito famílias Forge v2 e calculadora científica: [implementação atual](PHASES_1_2.md).
As fases 3 e 4 também foram ampliadas: [provas e cenas científicas](PHASES_3_4.md).
O fluxo v1 descrito abaixo continua compatível.

## Executar

Na raiz do checkout, com Python 3.10–3.14:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/nabla doctor
.venv/bin/python -m pytest -q
.venv/bin/python tools/build_math_bundle.py --check

.venv/bin/nabla forge .nabla/meu-ciclo --count 20 --seed 42 --size 3 \
  --license MIT --provenance 'Exemplos sinteticos gerados localmente por inverse-v1' \
  --pdf-backend latex
.venv/bin/nabla check-bundle .nabla/meu-ciclo
```

O destino deve ser novo. O exemplo declara MIT somente para os exemplos
sintéticos locais produzidos pelo gerador; não licencia dados externos.
PDF é opcional: omita `--pdf-backend latex` quando `pdflatex` não estiver instalado.
`--pdf-backend typst` requer o executável `typst`; o exportador de fontes Typst
está implementado, mas a compilação Typst não foi exercitada neste ambiente.

O ciclo alterna integrais polinomiais e sistemas lineares. A primitiva ou solução
é escolhida primeiro; um solver que recebe apenas o problema recupera a resposta.
O verificador usa outro caminho: derivação simbólica e igualdade de todos os
coeficientes para integrais; resíduos e determinante exatos para sistemas.
A constante da primitiva não é única: o gerador e solver escolhem zero.

São produzidos `records.jsonl`, `train.jsonl`, `validation.jsonl`, `test.jsonl`,
`card.json`, `manifest.json`, `figures/*.{json,svg,png}` e `report.{html,tex,typ}`.
Quando solicitado e compilado com sucesso, há também `report.pdf`.
Textos, equações e figuras compartilham o modelo do problema. Dados exatos das
cenas ficam nos metadados; as curvas são amostras, com escalas independentes,
e não uma construção geométrica contínua certificada.

Sem PDF, os artefatos são determinísticos para a mesma versão, semente e opções.
O compilador PDF pode inserir datas/identificadores: não há garantia de identidade
binária do PDF. SHA-256 detecta alterações, mas não autentica o autor. A validação
também reexecuta a matemática e reconstrói as modalidades gráficas, rejeitando
certificados ou figuras adulterados mesmo se seu hash for recalculado.

## Cobertura por fase

| Fase | Capacidade entregue nesta rodada | O que continua aberto |
|---|---|---|
| 0 | Recuperação de módulos/teste corrompidos, API pública, preservação de domínio, auditoria e bundle atualizado | Auditoria histórica completa e execução de toda matriz de plataformas |
| 1 | Contratos racionais canônicos e integração com AST, matrizes e cálculo existentes | Cobertura geral das áreas matemáticas previstas |
| 2 | Construção inversa reproduzível de integrais e sistemas, deduplicação semântica | Outras famílias, dificuldade calibrada e diversidade externa |
| 3 | Certificados exatos independentes e busca de contraexemplos com domínio explícito | Novas provas Lean/SMT e revisão formal independente |
| 4 | Cenas matemáticas editáveis em JSON, SVG e PNG determinísticos | Geometria de restrições geral e testes visuais amplos |
| 5 | Modelo de documento, equações/figuras, HTML/LaTeX/Typst e PDF por compilador opcional | Compilação Typst exercitada, bibliografia e templates editoriais amplos |
| 6 | JSONL, direitos declarados, manifesto, reexecução, deduplicação e splits por template | Parquet, perfis completos e avaliações externas de qualidade/utilidade |
| 7 | Decaimento e oscilador com Euler/RK4, unidades, erros, energia e convergência | PDEs/malhas e validação com medições |
| 8 | Conferência de alinhamento problema/solução/figuras e contaminação de partições locais | Treino multimodal, agentes novos e demonstração de melhoria em modelos |
| 9 | Contraexemplos exatos em grade finita, incluindo divergência de domínios | Regressão simbólica, experimentos e novidade bibliográfica |
| 10 | Seleção entre políticas fixas, holdout separado, teste de sinais, orçamento e política de reversão no recibo | Autoedição isolada, holdouts inéditos externos e ganhos gerais |
| 11 | Circuitos CC resistivos exatos com referência aterrada e fontes de corrente | AC, dispositivos não lineares, instrumentos e outras disciplinas |
| 12 | Histórico versionado de afirmações, evidências referenciadas, dependências e impacto | Revisão por pares real, federação e reconciliação semântica |
| 13 | Contratos rejeitam versões desconhecidas e mantêm proveniência | Horizonte aberto; sem alegação de implementação completa |

## Partições, evidência e limites

Todas as variantes de uma família/tamanho ficam na mesma partição determinística.
Um ciclo pequeno pode conter somente treino, como o exemplo de tamanho 3. Não são
inventados conjuntos de avaliação para preencher arquivos. Varie os tamanhos e
reserve famílias inéditas antes de avaliar generalização. A auditoria detecta
sobreposição de tarefas/templates e registros na partição errada, somente entre
os dados locais fornecidos; não compara com corpora externos ou históricos de LLMs.

A dificuldade permanece `uncalibrated`; `formal_proof` é falso. A licença e origem
são declarações do curador, não validação jurídica. O gerador limita tamanho a 8,
quantidade a 1000 e semente a inteiros não negativos de 63 bits. O pipeline evita
sobrescrever o destino e limpa a saída temporária se uma etapa falhar.

## Refutação e simulação

```bash
.venv/bin/nabla falsify 'x/x' '1' --radius 3 --budget 1000
.venv/bin/nabla falsify 'x*x' 'x' --radius 4
.venv/bin/nabla simulate harmonic_oscillator --initial 1 0 --steps 20 --method rk4
.venv/bin/nabla simulate exponential_decay --initial 1 --rate 1 --duration 1
```

A busca retorna contraexemplo, divergência de domínio, orçamento esgotado ou
nenhum contraexemplo **no domínio inteiro finito declarado**. Este último nunca
significa prova universal. O primeiro testemunho é mínimo em norma L1 dentro da
grade, não entre todos os racionais. Máximo: quatro variáveis, raio 32 e 100 mil
avaliações, com limites adicionais de tamanho e custo aritmético.

A simulação compara dois refinamentos com solução analítica independente. A CLI
retorna 1 se o erro refinado exceder a tolerância. Energia do oscilador é por
unidade de massa. Não há dados observados nem validação experimental. Componentes
com unidades distintas são conferidos individualmente; a tolerância escalar
aplica-se ao valor numérico de cada componente nas unidades SI declaradas.

## Circuitos, seleção controlada e conhecimento versionado

```python
from nablamath.domains.circuits import Resistor, solve_dc
circuit = solve_dc((Resistor('a', 'b', 10), Resistor('b', '0', 10)), {'a': 1})
assert dict(circuit.voltages)['a'] == 20
assert circuit.verified  # KCL em todos os nós e potência fornecida=dissipada

from nablamath.worlds import ModelSpec
from nablamath.evolution import SolverPolicy, select_on_calibration, evaluate_proposal
calibration = (ModelSpec('exponential_decay', (1,), .75),)
holdout = tuple(ModelSpec('exponential_decay', (1,), rate) for rate in (.5,.6,.7,.8,.9,1.))
baseline = SolverPolicy('euler', 80)
candidate = select_on_calibration((baseline, SolverPolicy('rk4', 20)), calibration)
receipt = evaluate_proposal(candidate, baseline, calibration, holdout, max_derivative_calls=80)
# Comparação com 80 chamadas de derivada em cada política. O recibo guarda
# perdas, IDs, regressões, p-valor e baseline para reversão; não modifica código.

from nablamath.knowledge.versioned_claims import ClaimRevision, ClaimLedger
ledger = ClaimLedger()
a = ledger.append(ClaimRevision('model-a', 'Modelo sob investigação', 'proposed'))
b = ledger.append(ClaimRevision('claim-b', 'Resultado dependente', 'supported',
                               evidence=('experiment:receipt-01',), dependencies=(a,)))
ledger.append(ClaimRevision('model-a', 'Modelo sob investigação', 'refuted',
                           evidence=('counterexample:receipt-02',), previous=a))
assert b in ledger.affected_by(a)
```

Circuitos: resistências positivas em ohms, correntes em ampères e terra com
potencial zero; componentes flutuantes são rejeitados. Potência é em watts.

O avaliador aceita somente Euler/RK4, não funções executáveis arbitrárias.
Calibração e holdout não podem compartilhar casos idênticos, e cada caso só pode
aparecer uma vez em cada conjunto. Um p-valor baixo depende de hipóteses de
independência: taxas sintéticas parecidas não as garantem. `accepted` significa
apenas aprovação do gate numérico declarado, não autorização de release ou
comprovação de RSI científico. O chamador ainda deve reservar holdouts novos e
impedir seleção repetida sobre eles; não existe cofre de holdout externo.

No histórico, dependências apontam para revisões imutáveis existentes. Revisões
posteriores preservam as antigas; novas versões exigem o `previous` atual.
`save` cria um arquivo novo e `load` confere hashes/linhagem. Evidências são
referências declaradas: o estado `supported` não executa provas automaticamente,
e impacto não altera silenciosamente o estado das afirmações dependentes.
