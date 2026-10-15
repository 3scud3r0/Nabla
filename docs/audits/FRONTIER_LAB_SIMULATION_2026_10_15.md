# Simulação de uso por um laboratório — 15 de outubro de 2026

**A campanha passou nos cenários selecionados das 12 fases; a estimativa da visão
permanece 70,32%, e a meta de 95% não foi demonstrada.** A utilização é simulada,
com execução real dos componentes do Nabla. Nenhum laboratório externo participou.
Não se atribuiu evidência externa por representar papéis locais de curadoria,
avaliação, computação científica e revisão de release.

Os [artefatos completos da campanha](../../benchmarks/results/frontier-lab-951017/summary.json)
estão versionados: protocolo, fontes identificadas por SHA-256, versões, datasets,
modelos, avaliações, provas, cenas, PDFs, logs e manifestos. O protocolo fixa a seed
951017, o corpus e os procedimentos; os conjuntos reservados são comprometidos
antes do ajuste dos modelos. O operador local tem acesso aos dados, portanto isso
não constitui avaliação secreta administrada por entidade independente.

## Resultados observados

| Experimento | Resultado |
|---|---|
| Corpus sintético | 192 tarefas únicas, oito famílias, tamanhos 2/3/4 |
| Partições separadas por família/template | 96 treino, 48 validação, 48 teste |
| Vizinho mais próximo, todas as entradas | 0/48 validação; 0/48 teste |
| Vizinho mais próximo, somente texto | 0/48 validação; 0/48 teste |
| Solver exato de referência, sem treinamento | 48/48 validação; 48/48 teste |
| Corpus independente de 32 tarefas, tamanhos 2/4/8 | Nabla 32/32, SymPy 32/32; Z3 24/24 suportadas e oito não suportadas |
| Dificuldade avançada contra os backends | Nenhum desafio observado neste corpus |
| Controles adversariais do dataset/avaliação | Quatro passaram |
| Modelos idealizados por disciplina | 16 casos com referências analíticas e replay passaram |
| Publicação científica | Três PDFs Typst compilados, evidências e integridade reconferidas |
| Formalização | Certificado Lean reexecutado; revisão humana da tradução continua pendente |
| Federação | Assinatura válida aceita; assinatura falsa em quarentena; chave revogada recusada inclusive na exportação |
| Portfólio contra baseline `exact` | Rejeitado: seis melhorias, 18 empates, efeito mediano zero |
| Portfólio contra baseline `alternate` mais fraco | Aceito: 18 melhorias, seis empates, efeito mediano 36,2454%; promoção e rollback exercitados |

O corpus de aprendizado exige generalização para famílias ausentes do treino.
As famílias não têm necessariamente a mesma estrutura de resposta; o fracasso do
baseline nesse teste não mede aprendizado dentro de distribuição. O solver exato
é uma referência de funcionamento das ferramentas, não um modelo que aprendeu
com os dados. O replay dos nove checkpoints neurais da campanha anterior também
passou, preservando seus resultados anteriores, sem novo treinamento externo.

## Cobertura do roteiro por fase

| Fase | Cenário efetivamente executado | Nota da visão mantida |
|---|---|---:|
| F1 | Catálogo de 33 operações, replay e referência numérica NIST | 80% |
| F2 | Oito famílias e 32 problemas conferidos contra solvers independentes | 70% |
| F3 | Bundle formal e certificado Lean reexecutados | 70% |
| F4 | Seis cenas com modelos, SVG e PNG | 75% |
| F5 | Artigo, relatório de engenharia e material didático compilados | 75% |
| F6 | Release JSONL/Parquet, partições e quatro controles adversariais | 75% |
| F7 | EDO/EDP, referência analítica e rejeição de FTCS instável | 70% |
| F8 | Dois baselines treinados, seis avaliações, checkpoint neural e agente retomado | 60% |
| F9 | Recuperação de lei racional sintética em pontos reservados e replay | 65% |
| F10 | Dois portfólios, gates, promoção e rollback | 70% |
| F11 | Elasticidade, RLC, cinética e hidrostática; quatro escalas por modelo | 60% |
| F12 | Troca assinada, quarentena, revogação e artefatos duráveis | 70% |

Os perfis selecionados são testes de aceitação delimitados. A aprovação de um
perfil não encerra a fase inteira, e o programa registra explicitamente essa
distinção em `whole_phase_completion_established: false` para cada fase.

Mesmos pesos normalizados pela soma 95 e eixos C/30, I/20, V/20, E/20, O/10 da
[avaliação anterior](PHASES_1_12_PROGRESS_70.md). A estimativa é julgamento técnico,
com incerteza aproximada de ±10 pontos; sua casa decimal decorre da ponderação.
Esta rodada amplia reprodução/aceitação, mas não cobre integralmente critérios
pendentes para conceder cinco pontos adicionais a uma fase inteira.

## Código e verificações novos

- `benchmarks/laboratory.py` gera corpus, registra compromissos, treina os dois
  baselines, publica release, executa controles e reconstitui todos os resultados.
  O verificador reconstrói o corpus a partir do protocolo e refaz treinamento e
  inferência; não aceita apenas os hashes ou as métricas fornecidas.
- `tools/simulate_frontier_lab.py` coordena cinco subprocessos com timeout,
  preservação de falhas, journal e relatórios por fase. Não executa comandos
  arbitrários fornecidos por usuários nem simula identidade de pesquisadores reais.
- 15 testes novos verificam execução, falsificações com hashes recalculados,
  limites, modelos malformados, arquivos extras e preservação de falhas/timeouts.
- **468 testes e 312 subtestes passaram em 43,86 segundos**, incluindo os 15 testes
  novos, após a correção do controle descrito abaixo. Contagens e duração constam
  em `local-validation.json` e `tests.xml` nos artefatos. `math.txt` foi regenerado
  e conferido.
- Wheel construído e o novo workload executado/reproduzido por importação isolada,
  sem recorrer ao pacote editável nem às dependências opcionais.
- CI atualizado para testes e replay dos artefatos publicados em Linux/Windows;
  **essa configuração não equivale a CI remoto já executado neste commit**.
- `.gitattributes` preserva os bytes dos artefatos identificados por hashes,
  inclusive JSON, para evitar conversão de fim de linha no checkout Windows.
  Um checkout com `core.autocrlf=true` e `core.eol=crlf` preservou os hashes dos
  141 arquivos de artefatos. Isso simula a configuração de Git, sem alegar execução
  nativa Windows. PDFs são marcados como binários; whitespace de arquivos gerados
  é preservado, sem alterar bytes ou hashes para satisfazer verificação editorial.

Houve um ensaio inicial de desenvolvimento, antes de completar o congelamento de
metadados e os relatórios por fase. Seus cinco blocos passaram e seu
[resultado foi preservado](../../benchmarks/results/frontier-lab-development-951017.json).
A campanha com congelamento foi repetida após a correção abaixo, sempre com a
mesma seed e protocolo de dados. Não houve busca por uma seed com resultado melhor
nem remoção das avaliações com zero acertos. Durante o empacotamento, a tentativa pelo pip da
venv sem isolamento falhou porque ali faltava setuptools; o backend setuptools
84.0.0 já instalado no Python do ambiente construiu o wheel, sem baixar pacotes.

O primeiro smoke do wheel, com a seed adicional 23117, detectou uma falha no
**controle de injeção de vazamento**: ele usava o primeiro registro ordenado como
se fosse de treino. Nessa seed, o registro era de teste e ambos os extremos do
ancestral compartilhado podiam ficar no teste. O controle, corretamente, retornou
falso e o smoke falhou. A seleção agora exige explicitamente uma amostra de treino.
Uma regressão fixa essa seed; o smoke isolado e a campanha foram repetidos após a
correção. O [resultado que falhou](../../benchmarks/results/frontier-lab-control-failure-23117.json)
e o [ensaio anterior à correção](../../benchmarks/results/frontier-lab-pre-control-fix-951017.json)
foram preservados, sem reclassificá-los como validação do código corrigido.

## O que ainda impede os 95%

Com os valores atuais de evidência externa, mesmo todos os outros eixos no máximo
resultariam em 83,68%, não 95%. A simulação não substitui ganho reproduzível em
benchmark externo, uso real por pesquisadores, descoberta nova reproduzida,
validação física observacional ou revisão independente. O
[backlog completo](PHASES_1_12_COMPLETION_BACKLOG.md) continua válido.

O campo automático `vision_completion_percent` permanece `null` e
`vision_target_demonstrated` permanece `false`. Os resultados desta execução
sustentam o funcionamento dos recortes acima e tornam as lacunas auditáveis.

## Reprodução

Consulte o [guia da campanha](../FRONTIER_LAB_SIMULATION.md). Destino novo:

```sh
OPENBLAS_NUM_THREADS=1 python tools/simulate_frontier_lab.py .nabla/frontier-lab-reproduction --per-family 24 --seed 951017
```

Os manifestos registram integridade de bytes; SQLite, assinaturas efêmeras,
tempos e compiladores podem gerar bytes diferentes em nova execução. O replay
semântico dos datasets e resultados é o critério de comparação apropriado.
