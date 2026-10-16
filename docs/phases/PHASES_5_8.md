# Fases 5–8: fluxos executáveis e limites verificáveis

Todos os caminhos prioritários das fases 5–8 de `vision.md` têm implementações.
As capacidades são delimitadas abaixo. Existência de módulos, compilação e volume
de dados não demonstram qualidade de treinamento geral, validação experimental
ou conclusão de todo o horizonte científico proposto na visão.

## Instalação e ciclo integrado

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test,formal,graphics,documents,data]'
.venv/bin/nabla laboratory .nabla/laboratory-58 --count 32 --seed 42 --parquet
```

O comando cria um diretório novo, sem sobrescrever o anterior: dataset v3,
partições, card, Parquet opcional, modelos e avaliações, ablações, simulação térmica,
convergência, balanço de fluxo, animação SVG, recibo de agente, figura PNG quando
Pillow está instalado e artigo em JSON/HTML/LaTeX/Typst/PDF. Tudo recebe manifesto
SHA-256. O PDF usa Typst (CLI ou binding Python); LaTeX pode usar `pdflatex`.
Não há publicação remota automática. A execução requer o extra `documents`.

## Fase 5: Studio

- `documents/document_model.py`: documento, seções, equações AST e figuras, origem
  sintética explícita, limitações obrigatórias, bibliografia e citações declaradas.
- `equation_blocks.py`: serialização reversível de expressões; não aceita LaTeX
  executável como fonte matemática.
- `citations.py`: referências fornecidas pelo autor, com chaves únicas e ano;
  títulos/DOIs não são inventados ou autenticados automaticamente.
- `figures.py`: ingestão de PNG, caminhos relativos, SHA-256 e validação do conteúdo.
- `latex_exporter.py`, `typst_exporter.py`, `html_exporter.py`: o mesmo AST em três
  formatos, com escape de texto, equações, referências, figuras e limitações.
- `pdf_builder.py`: compilação real em temporário, timeout, raiz controlada no
  Typst e shell escape desativado no LaTeX. Tipos de letra e compilador podem
  alterar os bytes de um PDF; o manifesto identifica o artefato efetivamente gerado.
- `publication.py`: diretório publicado atomicamente e rechecagem do documento,
  fontes renderizadas, figuras e hashes. Fontes citadas podem ser anexadas pelo seu
  SHA-256; `require_evidence=True` rejeita citações sem artefato. Referências não
  resolvidas permanecem listadas explicitamente no manifesto. Hashes atestam
  integridade, sem provar automaticamente afirmações da prosa. A rechecagem de PDF confere integridade e
  formato, sem alegar que extrai/reprova a matemática a partir dos pixels.
- `templates/research_paper/`: exemplo completo e receita com hipótese, método,
  resultados, discussão, limitações e referências; sem conteúdo artificial para
  atingir contagem de páginas.

```sh
nabla studio templates/research_paper/example.document.json .nabla/article --pdf-backend typst --evidence templates/research_paper/evidence-map.json --require-evidence
```

A revisão visual local conferiu hierarquia de títulos, margens, figura e
legibilidade. Símbolos Unicode arbitrários podem exigir Typst ou configuração
adicional do LaTeX; uma falha de compilação é reportada, sem substituir conteúdo.

## Fase 6: Dataset

O schema v3 em `datasets/schema.py` é aditivo: contratos anteriores em `dataset/`,
Forge v1/v2 e a política `datasets/splits.py` continuam disponíveis. Cada registro
inclui problema, solução com rastro reexecutável, tentativas inclusive falhas,
certificados associados, artefatos, licença declarada, procedência, escopo,
limitações, dificuldade (inclusive `uncalibrated`), defeitos e versão do verificador.
Não se confia em um campo armazenado `valid=true`.

`serializer.py` limita JSONL e refaz as verificações. `semantic_fingerprint.py`
reutiliza a normalização exata do Forge, inclusive sistemas lineares equivalentes.
`split_policy.py` mantém famílias de construtores inteiras em treino, validação ou
teste. `curation.py` retém motivos de rejeição. `quality_gate.py` rejeita duplicatas,
contaminação, defeitos declarados, falta de metadados, hashes divergentes e
modalidades que não correspondam ao modelo canônico. `model_card.py` resume
licenças, fontes, famílias, partições e limitações; avaliações anexadas são
reconferidas contra os registros do dataset.

Os artefatos admitidos neste perfil são representações canônicas reexecutáveis
(texto, equação, diagrama SVG, simulação da integral polinomial, rastro e
certificados associados). Um anexo arbitrário não passa a ser semanticamente
validado só porque seu hash coincide. Novos perfis exigem verificadores próprios.
Certificados associados provam seus enunciados declarados; não são automaticamente
provas de equivalência com qualquer tarefa do registro.

`export/jsonl.py`, `parquet.py` e `bundle.py` fazem exportação e leitura reversível,
com conferência de metadados e partições. Arrow é opcional e tem limites de alocação.
`export/huggingface.py` prepara README e partições compatíveis; `upload_bundle` é
uma operação explícita separada que usa a autenticação normal do Hub. O laboratório
e os testes não publicam nada em serviços externos.

```sh
nabla dataset-build .nabla/data58 --count 32 --seed 42 --license CC0-1.0 --provenance 'Experimento sintético local' --parquet
nabla dataset-check .nabla/data58
```

A licença é uma declaração do curador, não uma auditoria jurídica. O gate mede
qualidade matemática e integridade local; utilidade externa de treinamento exige
avaliação própria e não é inferida do tamanho do dataset.

## Fase 7: Worlds

`worlds/model_spec.py` define contratos SI imutáveis para decaimento exponencial,
oscilador harmônico e calor 1D. A API anterior `worlds.ModelSpec` permanece válida.
`ode/` reutiliza Euler/RK4; `integrators/` compartilha os kernels e verifica a
estabilidade explícita da difusão. `mesh/` define malha uniforme limitada.

`pde/` implementa a equação linear do calor com condição inicial senoidal e
fronteiras Dirichlet nulas. O FTCS exige `diffusivity*dt/dx² <= 0.5`. O orçamento
limita células, passos e snapshots. Os resultados incluem unidades, parâmetros,
malha, estados, solução analítica independente e erro máximo.

`conservation.py` mede energia do oscilador e balanço térmico com fluxo pela
fronteira; não afirma que a massa térmica seja constante sob Dirichlet.
`convergence.py` refina dx por 2 e dt por 4 e mede ordem/erro contra solução fechada.
`sensitivity.py` usa diferenças centrais com dois passos para sensibilidade de
parâmetros. `validation.py` compara referências e observações fornecidas com
unidades, incertezas, procedência e resíduos. Interpolação entre snapshots é linear;
a procedência de um instrumento não é autenticada pelo software.
`animation.py` gera SVG autocontido a partir dos estados efetivamente calculados.

```sh
nabla world-heat .nabla/heat58.json --cells 20 --steps 200 --diffusivity .1 --duration .1
```

Não há solver geral de todas as EDPs, malha tridimensional, multifísica ou validação
experimental automática. Esses domínios exigem novos modelos e evidências.

## Fase 8: modalidades, agentes e aprendizado

`datasets/multimodal.py` liga texto, equações, diagramas, rastros, certificados e
uma simulação opcional ao mesmo problema. `datasets/alignments.py` recalcula os
conteúdos; trocar só `task_id` ou recalcular um hash não legitima uma imagem de
outro problema. Diagramas mostram o polinômio ou matriz do problema. Rastros,
soluções, provas associadas e trajetórias alvo não entram na API de inferência.

`agents/tool_registry.py` oferece ferramentas `solve` e `simulate`, com contratos
JSON fechados. Código das ferramentas é confiável e cadastrado pela aplicação;
não há ferramenta de shell ou de rede padrão. `permissions.py` limita capacidades,
chamadas, bytes e tempo. Cada chamada ocorre em subprocesso encerrável.
`proposals.py` define planos ordenados sem ciclos; `planner.py` faz preflight de
todas as ações, encerra após falhas e gera recibos encadeados. `verify_run` reexecuta
as ferramentas científicas conhecidas por padrão. Subprocesso não é um sandbox
para executar código hostil. A API anterior `agents.Proposal` é preservada; a nova
proposta é `agents.ScientificProposal` ou `agents.proposals.Proposal`.

`training/curriculum.py` só aceita treino. `baselines.py` realmente ajusta um
baseline pequeno de vizinho mais próximo sobre características de texto/equações/
SVG; seus parâmetros e identidade são exportados. É uma referência limitada,
não um modelo multimodal de grande porte. `contamination.py` mede sobreposição
semântica e de famílias locais. `evaluation.py` recebe apenas entradas, confere as
respostas pelo verificador exato, publica acurácia, intervalo de Wilson, resultados
por tarefa e comparação pareada exata, incluindo regressões e ausência de ganho.
Modelos externos podem implementar `predict(inputs)` e fornecer identificador de
versão explícito. Registros externos são importados via schema v3 com origem,
licença e procedência declaradas. Essa declaração não autentica a fonte externa.

`training/ablation.py` retreina cada variante sobre o mesmo treino e avalia no mesmo
holdout; preserva todos os resultados sem selecionar automaticamente um vencedor.
O relatório de ablações não deve ser usado para ajustar o modelo sobre o teste.

```sh
nabla evaluate-dataset .nabla/data58 .nabla/evaluation58.json --benchmark generated-family-holdout
nabla agent examples/scientific_plan.json .nabla/agent58.json --allow solve --max-calls 2 --timeout 10
```

No laboratório local de seed 42, foram curados 32 registros e o baseline acertou
0 de 4 exemplos de famílias reservadas. A ordem observada do FTCS foi aproximadamente
1,9977. Esses são resultados sintéticos delimitados. Não foi executado treinamento
de um modelo amplo nem demonstrada melhora em um corpus externo independente.

## Validação

```sh
python tools/build_math_bundle.py
python -m pytest -q
python tools/build_math_bundle.py --check
```

Os testes das fases 5–8 exercitam compiladores PDF reais quando instalados, leitura
Parquet, manipulação de hashes, rechecagem de modalidades, isolamento de holdouts,
referência analítica de EDP/EDO, instabilidade, conservação, observações incorretas,
capacidades e timeouts de agentes, treino real e resultados negativos. Dependências
opcionais ausentes são reportadas como skips nos testes específicos. O upload ao
Hub é testado com cliente simulado, sem envio externo. O ciclo completo também foi
executado pela CLI e seu PDF revisado visualmente.

Resultado da suíte completa neste ambiente: **378 testes e 287 subtestes aprovados**.
Os cinco testes do site e seu build também passaram. Os dois backends PDF, Typst e
LaTeX, foram executados; nenhum teste foi omitido por falta dessas dependências.
