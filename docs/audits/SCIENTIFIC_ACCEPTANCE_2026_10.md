# Atendimento à auditoria de 14/10/2026

A estimativa de 31,04% fornecida pelo usuário é uma avaliação técnica do escopo,
não uma métrica automatizada. Não foi substituída por 100% com base em nomes de
arquivos, títulos de PR ou quantidade de testes. Há avanços mensuráveis e critérios
científicos ainda não demonstrados.

## Correção Windows

As anotações públicas do [instalador](https://github.com/3scud3r0/Nabla/actions/runs/38620098364)
identificaram `documents/publication.py:65`, “Publicação não reproduzível”. A falha
foi reproduzida com o locale C e UTF-8 desativado: o exportador gravava UTF-8 e o
verificador relia com a codificação padrão do sistema. A correção explicita UTF-8
nos caminhos afetados, sem reduzir asserts nem depender apenas de variável do CI.

`tests/regression/test_portable_io.py` executa publicação com caracteres portugueses
e gregos em um subprocesso sem UTF-8 padrão, verifica codificação explícita e
backup SQLite com espaços/`#`. Conexões do catálogo de projetos e registro de
modelos agora fecham explicitamente. URIs SQLite usam `Path.as_uri()`.
`.gitattributes` fixa finais de linha para fontes atuais e preserva o histórico.

O instalador agora roda pytest, exporta JUnit e é construído também em branches
`feat/**`/`fix/**`, sem publicar release nessas branches. O tag alpha do release
no main usa o número da execução para não colidir com o release anterior. Links
de download foram corrigidos para o repositório Nabla. A validação nativa do
Windows deve ser conferida na execução da branch; passar em Linux não a substitui.

## Benchmark independente

```sh
nabla independent-benchmark .nabla/independent-solvers.json --count 24 --seed 103 --timeout 15
```

O [relatório completo](../../benchmarks/results/independent-solvers-2026-10.json)
registra problemas/IDs/sementes, versão dos backends, candidatos, verificação exata,
tempo do solver e tempo de parede sob subprocesso encerrável. São oito famílias e
três tamanhos (2, 4 e 8). Tempo de importação não é confundido com tempo do solver.

| Backend | Resolvidos | Incorretos | Timeout | Fora do perfil |
| --- | ---: | ---: | ---: | ---: |
| Nabla | 24 | 0 | 0 | 0 |
| SymPy | 24 | 0 | 0 | 0 |
| Z3 | 18 | 0 | 0 | 6 |

Os seis casos não suportados por Z3 são fatoração/espectros, não falhas de correção.
O benchmark não demonstrou dificuldade avançada dos problemas testados. “Todos os
solvers resolveram” é evidência de correção nesse recorte, sem provar utilidade para
raciocínio especializado. A ferramenta conserva esse resultado e não atribui
rótulo “expert” sem dificuldade observada.

## Experimento controlado com dados externos e pesos abertos

Foi obtido o GSM8K do repositório oficial OpenAI `grade-school-math`, licença MIT,
commit `3101c7d5072418e28b9008a6636bde82a006892c`. Fontes e SHA-256 estão no
[manifesto](../../benchmarks/results/controlled-learning-2026-10/source-manifest.json),
com a licença preservada. Não houve upload a serviços externos.

```sh
python tools/fetch_learning_benchmark.py .nabla/external/gsm8k
OPENBLAS_NUM_THREADS=1 nabla learning-experiment .nabla/external/gsm8k .nabla/controlled-study --train-count 256 --test-count 128 --steps 1000
```

Modelo: regressor neural aberto 128→32→1, tanh, Adam e atributos de texto por hash;
alvo numérico transformado por log com sinal. Não é um LLM pré-treinado, modelo de
fronteira ou experimento de treinamento multimodal profundo. Foram usados 256
exemplos externos de treino, 128 de teste e 256 problemas Nabla verificados.
Controle e tratamento têm o mesmo número de linhas, inicialização e passos: onde
o tratamento recebe dados Nabla, o controle recebe repetição dos dados externos.
Racionais e respostas finais externas são comparados exatamente no perfil de
saídas inteiras do regressor. Racionais não inteiros continuam registrados como
erro quando não podem ser representados pela saída inteira.

O protocolo é escrito antes do treino daquela execução. O estudo foi reproduzido
para conferir os artefatos, mantendo configuração e holdout; não foi declarado
como pré-registro externo nem ajustado para produzir um resultado positivo.
Auditoria de sobreposição por pergunta exata não garante ausência de todo template
ou contaminação de corpora externos.

| Semente | Sem Nabla | Com Nabla | Teste | p pareado |
| --- | ---: | ---: | ---: | ---: |
| 11 | 1 | 0 | 128 | 1,0 |
| 23 | 0 | 0 | 128 | 1,0 |
| 37 | 0 | 1 | 128 | 1,0 |

**Ganho médio de acurácia: 0.** Não há ganho externo demonstrado. A acurácia muito
baixa também mostra a limitação da arquitetura. Resultados negativos são
preservados: [relatório](../../benchmarks/results/controlled-learning-2026-10/report.json),
[protocolo](../../benchmarks/results/controlled-learning-2026-10/protocol.json), pesos
NPZ sem pickle e versões do ambiente. `verify_experiment_artifacts` carrega os
pesos com `allow_pickle=False`, reexecuta previsões e reconfere os agregados.
Essa verificação de artefatos não autentica uma execução independente do treinamento.

## Critérios explícitos em vez de percentual artificial

```sh
python tools/assess_vision.py --research .nabla/research-912 --benchmark .nabla/independent-solvers.json --learning .nabla/controlled-study/report.json --junit .nabla/python-tests.xml --output .nabla/vision-acceptance.json
```

`--require-all` retorna erro enquanto houver critérios não demonstrados. A
[ficha de aceitação](../../benchmarks/results/vision-acceptance-2026-10.json) distingue
cobertura de caminhos (diagnóstico), testes, CI nativo, dificuldade, ganho externo,
novidade, RSI geral, validação física e revisão científica independente.
`vision_completion_percent` permanece `null`: não existe uma correspondência
validada entre esses checks e toda a visão. F13 continua sendo horizonte aberto.

As fases 9–12 agora possuem implementações delimitadas e um laboratório integrado:
duas gerações de políticas aceitas, rejeição, rollback, dez modelos disciplinares,
16 revisões de claims e uma divergência federada conservada. Isso fecha lacunas de
engenharia, mas não comprova descoberta autônoma geral, autoaperfeiçoamento amplo,
melhoria de modelos de fronteira ou ciência experimental validada. Esses critérios
continuam visíveis e não podem ser transformados em 100% apenas alterando um número.
