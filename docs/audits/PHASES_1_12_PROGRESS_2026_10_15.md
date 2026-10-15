# Progresso das fases F1–F12 — 15/10/2026

> Avaliação posterior: [progresso consolidado e CI nativo](PHASES_1_12_PROGRESS_70.md).
> Este arquivo preserva a avaliação intermediária de 48,21%.

**Estimativa ponderada: 48.21%**, ante 43.95% na avaliação anterior.
Média simples: 47.50%. Mesma rubrica C/30 + I/20 + V/20 + E/20 + O/10 e mesmos
pesos normalizados por 95 do [backlog anterior](PHASES_1_12_COMPLETION_BACKLOG.md).
F0 e F13 não entram no denominador. São estimativas de maturidade por julgamento
técnico, com margem aproximada de ±10 pontos no agregado; não são uma medição
objetiva de quanto falta para toda a visão científica de décadas.

Esta atualização avalia o código modificado sobre `f704f01ee69dbcc66805c480cb25c935919e5d2b`, antes de commit.
Os SHA-256 dos fontes, testes e ferramentas identificam o snapshot no
[registro de evidências](../../benchmarks/results/completion-hardening-2026-10-15.json).
O resultado Windows de 14/10 pertence à versão anterior; estas alterações ainda
não foram executadas no Windows nativo.

## Porcentagens atualizadas

| Fase | Antes | Agora | C | I | V | E | O |
|---|---:|---:|---:|---:|---:|---:|---:|
| F1 — Calculadora científica | 50% | **50%** | 15 | 10 | 15 | 5 | 5 |
| F2 — Forge e geração inversa | 45% | **50%** | 15 | 10 | 15 | 5 | 5 |
| F3 — Prove e Falsifier | 50% | **55%** | 15 | 15 | 15 | 5 | 5 |
| F4 — Geometria e imagens científicas | 55% | **60%** | 25 | 10 | 15 | 5 | 5 |
| F5 — Studio e publicação | 65% | **65%** | 25 | 15 | 15 | 5 | 5 |
| F6 — Datasets científicos | 55% | **55%** | 20 | 10 | 15 | 5 | 5 |
| F7 — Worlds e simulações | 40% | **50%** | 20 | 10 | 15 | 0 | 5 |
| F8 — Multimodalidade e agentes | 30% | **35%** | 15 | 10 | 5 | 0 | 5 |
| F9 — Discovery | 30% | **35%** | 15 | 10 | 5 | 0 | 5 |
| F10 — RSI controlado | 35% | **40%** | 10 | 10 | 10 | 5 | 5 |
| F11 — Outras disciplinas | 25% | **30%** | 15 | 5 | 5 | 0 | 5 |
| F12 — Conhecimento científico vivo | 35% | **45%** | 15 | 15 | 10 | 0 | 5 |

## Implementações e motivo das notas

- **F1:** Nova operação ode_adaptive com replay; a cobertura ampla das nove áreas ainda não justifica outro degrau de cinco pontos.
- **F2:** Análise estratificada de solvers com reconferência de respostas, denominadores suportados e intervalos de Wilson; sem nova demonstração de dificuldade avançada.
- **F3:** Vinculação verificável entre pergunta, tarefa, formalização, domínio e revisão declarada; identidade e equivalência linguística não são autenticadas.
- **F4:** Curvas racionais adaptativas com limite exato de erro vertical por segunda derivada e replay do bundle; orçamento insuficiente e possível polo falham explicitamente.
- **F5:** Tabelas canônicas com evidências e exportação HTML/LaTeX/Typst, incluindo PDFs compilados nos dois backends; falta revisão editorial externa e perfis completos.
- **F6:** Leitura binária limitada por linha/volume e exportação em fluxo com validação, fsync e publicação atômica sem sobrescrita; sem novo estudo externo de utilidade.
- **F7:** Dormand–Prince 5(4), tolerâncias locais, passos aceitos/rejeitados, orçamento, integração pública e erros comparados com soluções analíticas.
- **F8:** Referências estruturadas ligam resultados de dependências entre ferramentas; argumentos resolvidos entram no recibo e são reconferidos. Treinamento multimodal profundo permanece pendente.
- **F9:** Desenho experimental finito com custos, orçamento e exclusões explícitas; propostas continuam sem execução física ou demonstração de novidade.
- **F10:** Contrato congela efeito prático mínimo; gate rejeita ganho estatisticamente significativo mas inferior ao limiar, mantendo replay, regressões e rollback.
- **F11:** Resposta transitória RC com unidades, solver adaptativo, oráculo analítico e replay como evidência disciplinar; ainda sem medições reais.
- **F12:** Snapshots Ed25519, pinagem por par, revogação irreversível na trust store, rotação explícita e reconferência das assinaturas na reconciliação; federação ainda offline.

As fases 1, 5 e 6 receberam código, mas suas notas permanecem no mesmo degrau da
rubrica. Uma funcionalidade nova não fecha automaticamente uma lacuna ampla de
cobertura ou revisão externa. Nenhum ponto foi acrescentado por ganho de
aprendizado, descoberta inédita, revisão científica independente ou dados reais.

## Evidência executada

- **422 testes e 296 subtestes aprovados**, sem falhas, erros ou skips. O JUnit tem 718 entradas; isso não significa 718 funções de teste.
- Novo conjunto `tests/test_completion_hardening.py`: 16 testes de erro numérico, orçamento, roundtrip, adulteração, unidades, vínculos de resultados, referências formais, tabelas, desenho experimental, chaves/assinaturas e efeito prático de políticas.
- `tools/reproduce_completion.py` executado com **Typst e LaTeX**, produzindo dois PDFs reais e bundles verificados com tabelas e evidências.
- Dataset escrito em fluxo e reimportado com verificação; falha intermediária não publica destino incompleto e destino existente não é sobrescrito.
- Curva racional `x³` em [-1, 2], tolerância vertical 1/1000: limites racionais por segmento, replay, SVG e PNG verificados. O limite se refere à interpolação vertical do modelo, não aos pixels.
- Oscilador harmônico: 510 passos adaptativos aceitos; erro máximo ao longo da trajetória contra solução analítica **8,06411826204112 × 10⁻¹⁰**. Estimativa de erro local não é um limite rigoroso de erro global.
- Agente executa `solve → verify`, vinculando o candidato da primeira ação à segunda; replay reconfere argumentos resolvidos e resultado.
- Ledger com evidência exata exportado, assinado com Ed25519, importado com chave pública fixada e reconciliado. Chave privada demonstrativa fica apenas em memória. A assinatura autentica a chave configurada, não uma identidade científica real.
- Laboratório F9–F12 reexecutado: duas gerações aceitas, rejeição e rollback, dez modelos disciplinares, 16 revisões de claims, conflito preservado e proveniência válida.
- `math.txt` regenerado dos fontes e verificado com `tools/build_math_bundle.py --check`.

O workflow científico foi estendido para instalar o extra `federation`, executar
os novos testes e reproduzir o bundle integrado. A configuração está pronta;
**não foi apresentada como uma nova execução de CI aprovada**.

## Relação com o backlog

Os 104 itens do backlog anterior continuam sendo o plano completo do perfil
proposto. A tabela abaixo registra avanço parcial, sem marcar tarefas extensas
como concluídas por terem recebido apenas um subconjunto da implementação.

| Itens | Avanço implementado | O que ainda falta nesses itens |
|---|---|---|
| F01-02, F01-08 | Operação adaptativa pública e replay/teste da sessão | Catálogo e corpus independente de todas as nove áreas |
| F02-04, F02-06 | Análise por família/tamanho/backend, intervalo de sucesso, respostas rechecadas | Corpus novo, estratégias adicionais, protocolo e dificuldade avançada observada |
| F03-01, F03-07 | Vinculação por hashes da pergunta/tarefa/formalização e revisão declarada | Integrar todos os fluxos de prova, autenticar revisores e revisar equivalência linguística |
| F04-03, F04-06 | Refinamento com limite exato por segmento e reconstrução do modelo | Curvas/objetos mais gerais, tratamentos geométricos adicionais e corpus visual revisado |
| F05-01, F05-03, F05-04 | Tabelas rastreáveis no modelo e nos três exportadores | Provas/referências cruzadas completas, vínculo semântico de claims e revisão visual/editorial |
| F06-04 | JSONL em fluxo, limites por linha/volume, validação e publicação atômica | Retomada transacional, perfil de escala medido e integração streaming de Parquet/bundles |
| F07-02, F07-04 | DOPRI54 com tolerâncias, diagnósticos e comparação analítica | Eventos, rigidez, estudos gerais de estabilidade, EDPs e solver externo |
| F08-06 | Referências de resultados tipadas por caminho JSON e dependências explícitas | Planejamento adaptativo delimitado, estado persistente e retomada |
| F09-05 | Discriminação por custo, orçamento e exclusões | Modelos de ruído/custo mais amplos, viabilidade avaliada e experiências realizadas |
| F10-05 | Limiar de efeito prático no contrato e no gate | Inferência sequencial, poder estatístico e validação de independência/múltiplas campanhas |
| F11-02 | Transiente RC com unidades, oráculo e replay disciplinar | Topologias dinâmicas mais amplas, simulador externo e dados observados |
| F12-02 | Assinaturas, pinagem, revogação e rotação explícita | Persistência operacional segura de identidade, distribuição de confiança e identidade real |
| T-03, T-05 | Novos testes no workflow e bundle integrado reexecutável | Execução nativa do novo CI e cobertura de todos os tipos do artefato científico completo |

Todos os itens não mencionados continuam pendentes conforme o backlog original.
A nova implementação não resolve automaticamente descoberta geral, ganho de
modelos ou validação experimental.

## Reprodução

```sh
python -m pip install -e '.[test,formal,graphics,documents,data,research,federation]'
python -m pytest -q --junitxml=.nabla/completion-hardening-tests.xml
python tools/reproduce_completion.py .nabla/completion-new-typst --pdf-backend typst
python tools/reproduce_completion.py .nabla/completion-new-latex --pdf-backend latex
nabla research-laboratory .nabla/completion-new-research
python tools/build_math_bundle.py --check
```

Os destinos dos laboratórios devem ser novos: as ferramentas recusam sobrescrever
artefatos existentes. LaTeX requer o compilador do sistema e suas dependências;
Typst usa o backend opcional documentado. As assinaturas usam chaves efêmeras,
portanto os bytes dos envelopes mudam entre execuções; a verificação permanece
reproduzível com a chave pública exportada em cada bundle.

## Pendências que impedem 100%

O benchmark anterior continua sem dificuldade avançada demonstrada e o experimento
GSM8K continua com ganho médio zero. Não houve novo treinamento de modelo aberto,
coleta de observações reais, verificação bibliográfica abrangente ou revisão por
cientistas independentes nesta entrega. Além dessas evidências, ainda falta a
ampliação de escopo e integração detalhada no backlog por fase. Atingir 100% exige
concluir e validar esse perfil; elevar os números sem essas entregas não seria
uma avaliação honesta.
