# Auditoria das fases 1–12 e backlog para conclusão

> Atualização posterior: [progresso de 15/10/2026](PHASES_1_12_PROGRESS_2026_10_15.md).
> As notas abaixo preservam a avaliação anterior; consulte a atualização para o estado atual.

Data do registro: 15/10/2026 (UTC). Evidências do snapshot de 14/10/2026. Repositório: `3scud3r0/Nabla`.
Snapshot auditado: `f704f01ee69dbcc66805c480cb25c935919e5d2b`, branch
`feat/scientific-phases-9-12`. Esta avaliação é do checkout local; não afirma que
esse commit já foi integrado à `main`. Documento criado após esse snapshot.

## Resultado e significado dos percentuais

Considero as **12 fases F1–F12**. F0 é fundação; F13 é horizonte aberto e fica fora
do denominador. Os percentuais abaixo são **estimativas técnicas de maturidade**,
com julgamento explícito, não cobertura automática de testes, probabilidade de
sucesso, fração do tempo restante ou uma certificação de conclusão científica.

O `vision.md` não define catálogo fechado de todas as operações, disciplinas ou
experimentos. Portanto, não é possível enumerar “exatamente todo código” para
100% de uma visão aberta. Este arquivo faz o trabalho executável: identifica as
lacunas observadas e define um **perfil de aceitação delimitado proposto**, com
backlog, caminhos e critérios. Completar esse perfil não significa resolver toda
a matemática, pesquisa autônoma geral ou todas as ciências.

Pontuação por fase, soma de cinco eixos:

| Eixo | Máximo | O que avalia |
|---|---:|---|
| C: cobertura funcional | 30 | Abrangência dos objetivos da fase, além de um exemplo |
| I: integração | 20 | Uso pelos fluxos públicos e interoperabilidade dos artefatos |
| V: verificação | 20 | Contratos, referências independentes, casos-limite e falhas |
| E: evidência externa | 20 | Benchmarks inéditos, reprodução, medições e revisão aplicáveis |
| O: operação | 10 | Reprodutibilidade, portabilidade, versionamento e limites |

Os valores são atribuídos em passos de cinco pontos. Zero em E significa ausência
de validação externa adequada à amplitude da fase, não ausência de testes locais.
O máximo de um eixo exige cobertura do perfil inteiro, não só um exemplo que
passou. Esta rubrica organiza a estimativa; não transforma julgamento em medição.
Margem prudente do agregado: aproximadamente **±10 pontos percentuais**.

Para continuidade com a auditoria anterior, uso seus pesos de F1–F12, que somam
95, e os normalizo: `P = soma(peso × percentual_da_fase) / 95`.
A F0 de peso 5 foi excluída; assim, o novo agregado não é diretamente comparável
aos 31,04% da avaliação anterior. A rubrica também é nova: a diferença não mede
isoladamente quanto foi implementado desde aquela avaliação.

**Estimativa ponderada atual: 43,9%, Média simples das 12 fases: 42,9%,**

| Fase | Peso original | C/30 | I/20 | V/20 | E/20 | O/10 | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| F1 — Calculadora científica | 8 | 15 | 10 | 15 | 5 | 5 | **50%** |
| F2 — Forge e geração inversa | 12 | 15 | 10 | 10 | 5 | 5 | **45%** |
| F3 — Prove e Falsifier | 10 | 15 | 10 | 15 | 5 | 5 | **50%** |
| F4 — Geometria e imagens científicas | 7 | 20 | 10 | 15 | 5 | 5 | **55%** |
| F5 — Studio e publicação | 7 | 25 | 15 | 15 | 5 | 5 | **65%** |
| F6 — Datasets científicos | 10 | 20 | 10 | 15 | 5 | 5 | **55%** |
| F7 — Worlds e simulações | 8 | 15 | 10 | 10 | 0 | 5 | **40%** |
| F8 — Multimodalidade e agentes | 8 | 10 | 10 | 5 | 0 | 5 | **30%** |
| F9 — Discovery | 10 | 10 | 10 | 5 | 0 | 5 | **30%** |
| F10 — RSI controlado | 8 | 10 | 10 | 5 | 5 | 5 | **35%** |
| F11 — Outras disciplinas | 4 | 10 | 5 | 5 | 0 | 5 | **25%** |
| F12 — Conhecimento científico vivo | 3 | 15 | 10 | 5 | 0 | 5 | **35%** |

## Evidências usadas e limites da verificação

- [Visão](../../vision.md), especialmente as saídas de F1–F12, e o código canônico em `src/nablamath/`.
- [Fases 1–2](../PHASES_1_2.md), [3–4](../PHASES_3_4.md), [5–8](../PHASES_5_8.md) e [9–12](../PHASES_9_12.md), confrontadas com módulos e contratos.
- [Aceitação científica](SCIENTIFIC_ACCEPTANCE_2026_10.md) e [relatório estruturado](../../benchmarks/results/vision-acceptance-2026-10.json).
- [CI registrado](../../benchmarks/results/ci-evidence-2026-10.json): dez workflows aprovados no commit de código `22bdf6c23e7a2e5f823a2992e78ad9b3402d0db5`, inclusive matriz Windows/Linux e instalador Windows. É evidência histórica desse commit, não execução nova desta auditoria documental.
- Execução local anteriormente registrada: **406 testes e 295 subtestes** aprovados; o JUnit soma 701 entradas. Não são 701 funções de teste distintas. A suíte não foi reexecutada para esta alteração somente documental.
- [Benchmark independente](../../benchmarks/results/independent-solvers-2026-10.json): Nabla 24/24, SymPy 24/24, Z3 18/24 e seis não suportados. Zero desafios avançados observados nesse recorte.
- [Experimento externo](../../benchmarks/results/controlled-learning-2026-10/report.json): GSM8K, três sementes, ganho médio de acurácia **zero**. O modelo é MLP numérico pequeno, não LLM ou treinamento multimodal profundo.
- Laboratório F9–F12: regressão polinomial, duas gerações de políticas numéricas, dez modelos disciplinares, ledger e federação offline demonstrativos. Não comprovam novidade global, RSI geral, validação física ou revisão independente.

A cobertura de todos os caminhos prioritários é real, mas presença de arquivo não
mede profundidade da implementação. O campo automático `vision_completion_percent`
continua `null` no relatório anterior: não foi alterado para fabricar uma métrica.
A estimativa humana deste documento tem escopo e metodologia diferentes.

## Como executar o backlog

Todos os itens abaixo estão **pendentes de conclusão**; alguns estendem código já
existente. Caminhos sem prefixo são relativos a `src/nablamath/`, exceto `tests/`,
`benchmarks/`, `templates/`, `lean/` e `docs/`, relativos à raiz. `[novo]` significa
arquivo/pasta proposto, ainda não implementado. Diretórios designam extensão dos
módulos atuais, não instrução para criar arquivos vazios. Preservar API pública e
histórico; não duplicar módulos só para satisfazer uma árvore de pastas.

Cada item tem implementação e critério de aceitação. O código inclui testes,
ferramentas e exportação de evidências. Quando o critério exige pessoas, medições,
compute ou descoberta, isso é explicitado: escrever software para registrar um
resultado não equivale a obter o resultado.


## F1 — Calculadora científica: 50%

**Implementado:** IR escalar tipada, unidades SI, obrigações, intervalos, 21 operações e notebook reproduzível.

**Justificativa da nota:** A sessão expõe um subconjunto das bibliotecas; cálculo é predominantemente polinomial e os contratos não são uniformes nas nove áreas.

**Fontes principais:** `tests/test_phase1_calculator.py` e os módulos abaixo.

### F01-01

**Arquivos:** `core/semantic_ir.py; core/types.py; core/obligations.py`.

**Codificar:** Unificar contratos de escalares, vetores, matrizes e funções; transportar domínio e obrigações entre operações sem converter significado em texto.

**Aceite:** Serialização/replay preservam tipos e hipóteses; dimensões incompatíveis e obrigações não satisfeitas são recusadas.

### F01-02

**Arquivos:** `calc/session.py; calc/notebook.py`.

**Codificar:** Registrar operações das nove áreas com schemas, domínio, limites, unidades, precisão, versões e erros estruturados; conectar bibliotecas existentes antes de escrever algoritmos duplicados.

**Aceite:** Uma matriz publicada de operações cobre cada área do vision.md e cada operação tem replay, exemplo válido e caso fora do domínio.

### F01-03

**Arquivos:** `math/calculus/; symbolic/`.

**Codificar:** Completar o perfil declarado de limites laterais, singularidades, integração racional e séries com resto/intervalo de validade; reaproveitar diferenciação simbólica existente.

**Aceite:** Casos regulares e singulares conferidos por oráculo independente; integrais impróprias divergentes e resultados condicionais não são aceitos como valores exatos incondicionais.

### F01-04

**Arquivos:** `math/linear_algebra/; core/precision.py`.

**Codificar:** Integrar decomposições e sistemas retangulares com condicionamento e estimativa de erro; declarar perfil exato versus aproximado.

**Aceite:** Reconstrução/resíduo e limites de erro verificados em sistemas bem condicionados, singulares e quase singulares.

### F01-05

**Arquivos:** `math/probability/; math/statistics/; calc/session.py`.

**Codificar:** Expor distribuições, estimação, testes, intervalos e séries temporais com hipóteses estatísticas, alternativas e validade de amostra.

**Aceite:** Casos de referência reproduzidos; amostras inválidas e aplicação fora das hipóteses geram diagnóstico explícito.

### F01-06

**Arquivos:** `math/optimization/; math/geometry/; math/graph_theory/; calc/session.py`.

**Codificar:** Completar integração de restrições/KKT, transformações/construções, grafos, recorrências e lógica no perfil público, conservando certificados e limitações.

**Aceite:** Viabilidade e otimalidade não são confundidas; transformações preservam relações; operações discretas têm testemunho verificável.

### F01-07

**Arquivos:** `core/units.py; core/precision.py; calc/session.py`.

**Codificar:** Propagar unidades e erro em operações compostas; distinguir valores exatos, aproximações e intervalos; rejeitar conversões não suportadas.

**Aceite:** Análise dimensional atravessa a sessão e o notebook; precisão solicitada é cumprida ou a impossibilidade é declarada.

### F01-08

**Arquivos:** `tests/test_phase1_calculator.py; benchmarks/calculator/ [novo]`.

**Codificar:** Criar corpus independente estratificado por área, casos-limite e invariantes; publicar matriz de conformidade por operação e plataforma.

**Aceite:** Todas as operações do perfil possuem evidência externa ou referência analítica, testes de falha e resultados auditáveis; revisão matemática dos contratos registrada.


## F2 — Forge e geração inversa: 45%

**Implementado:** Oito famílias construtivas, testemunhos, verificadores, sementes, deduplicação e benchmark Nabla/SymPy/Z3.

**Justificativa da nota:** Os 24 casos medidos não demonstraram dificuldade avançada; diversidade e generalização estão pouco caracterizadas.

**Fontes principais:** `tests/test_phase2_forge.py` e os módulos abaixo.

### F02-01

**Arquivos:** `forge/task_spec.py; forge/reverse_builder.py`.

**Codificar:** Versionar contratos de testemunho, hipóteses, solução e verificadores por família; suportar composição de tarefas sem revelar o testemunho na entrada.

**Aceite:** Regeração por semente é idêntica e adulterações de solução, hipótese ou testemunho são detectadas.

### F02-02

**Arquivos:** `forge/constructors/; verify/trace.py`.

**Codificar:** Ampliar templates das oito famílias com estruturas não equivalentes triviais, preservando construção inversa e correção independente.

**Aceite:** Cada família possui variantes estruturalmente distintas; dificuldade não é atribuída pelo tamanho ou pela escolha de coeficientes.

### F02-03

**Arquivos:** `forge/sampling.py; forge/deduplicate.py; datasets/semantic_fingerprint.py`.

**Codificar:** Medir cobertura de estruturas, equivalência por renomeação/reescala e distribuição de parâmetros; controlar redundância por orçamento.

**Aceite:** Duplicatas semânticas conhecidas são agrupadas e relatório de diversidade separa famílias, templates e instâncias.

### F02-04

**Arquivos:** `forge/difficulty.py; benchmarks/independent.py`.

**Codificar:** Calibrar dificuldade por solver, estratégia, memória/tempo, taxa de sucesso e intervalo de incerteza; distinguir unsupported, erro e timeout.

**Aceite:** Rótulos possuem evidência versionada e não promovem caso sem suporte a difícil; resultados podem ser reproduzidos fora do gerador.

### F02-05

**Arquivos:** `datasets/splits.py; datasets/split_policy.py`.

**Codificar:** Separar templates, composições e classes semânticas entre treino e holdout, além da separação atual por família.

**Aceite:** Auditoria acusa colisões por testemunho, template e equivalência; nenhuma decisão de geração usa o holdout final.

### F02-06

**Arquivos:** `benchmarks/independent.py; benchmarks/forge_challenge/ [novo]`.

**Codificar:** Criar suíte reservada com baselines simbólicos, numéricos e, quando aplicável, modelos de raciocínio; fixar protocolo antes da avaliação.

**Aceite:** Instâncias, versões, limites e respostas verificadas constam do relatório; parcela de desafios permanece inédita para seleção.

### F02-07

**Arquivos:** `forge/reverse_builder.py; datasets/quality_gate.py`.

**Codificar:** Integrar geração guiada pelas lacunas de cobertura/dificuldade com limites, parada e preservação de falhas.

**Aceite:** Execução encerrável produz apenas tarefas verificadas; falhas e rejeições permanecem no relatório sem seleção retrospectiva dos sucessos.

### F02-08

**Arquivos:** `tests/test_phase2_forge.py; benchmarks/results/`.

**Codificar:** Publicar avaliação de correção, diversidade e dificuldade em amostra dimensionada por protocolo e revisão de problemas por avaliador independente.

**Aceite:** Saída da F2 demonstrada nas oito famílias; a exigência de dificuldade avançada continua aberta se os baselines resolverem tudo.


## F3 — Prove e Falsifier: 50%

**Implementado:** Tradução Lean delimitada, compilação e auditoria de axiomas; Z3 QF_LRA; busca e redução finitas de contraexemplos.

**Justificativa da nota:** Revisão estrutural não certifica correspondência humana entre pergunta e teorema; cobertura e minimização são limitadas.

**Fontes principais:** `tests/test_phase3_formal.py` e os módulos abaixo.

### F03-01

**Arquivos:** `formal/translation_review.py; forge/task_spec.py`.

**Codificar:** Ligar a pergunta original, a IR, as hipóteses e a proposição formal por identificadores e revisão explícita de tradução.

**Aceite:** Troca de pergunta, quantificador, domínio ou hipótese invalida a vinculação; aprovação humana não é simulada por flag automática.

### F03-02

**Arquivos:** `formal/lean_bridge.py; lean/Nabla/`.

**Codificar:** Publicar e completar os fragmentos suportados de álgebra, desigualdades e problemas selecionados, com rejeição de traduções fora do perfil.

**Aceite:** Corpus de traduções positivas/negativas e exemplos equivalentes conferidos; nenhum sorry ou axioma não autorizado.

### F03-03

**Arquivos:** `formal/smt_bridge.py; verify/certificate.py`.

**Codificar:** Documentar contrato por lógica SMT, testemunhos e distinção entre sat/unsat/unknown; ampliar apenas fragmentos com replay seguro.

**Aceite:** Modelos são reconferidos; unknown/timeouts não viram prova; SMT não é apresentado como certificado Lean.

### F03-04

**Arquivos:** `formal/lean_checker.py; verify/certificate.py`.

**Codificar:** Empacotar fontes, toolchain, dependências, versões e política de axiomas para reconferência em ambiente limpo.

**Aceite:** Terceiro reconstrói o certificado sem cache do autor; alteração de fonte ou dependência é detectada.

### F03-05

**Arquivos:** `falsifier/search.py; falsifier/counterexample_miner.py`.

**Codificar:** Adicionar estratégias específicas ao domínio: racionais, fronteiras, singularidades e orientação por restrições, com cobertura e orçamento declarados.

**Aceite:** Contraexemplo é reavaliado no enunciado original; busca inconclusiva nunca é prova de validade.

### F03-06

**Arquivos:** `falsifier/shrink.py`.

**Codificar:** Definir ordem de minimalidade por domínio e produzir certificado do escopo explorado durante redução.

**Aceite:** Resultado diz mínimo no escopo ou apenas reduzido; exemplos impossíveis de minimizar conservam o testemunho válido.

### F03-07

**Arquivos:** `formal/translation_review.py; knowledge/provenance_audit.py`.

**Codificar:** Persistir falhas de tradução, revisão, axiomas, timeout e refutação como evidências tipadas vinculadas à tarefa.

**Aceite:** Pipeline e documento preservam distinção entre igualdade exata, prova formal e teste finito.

### F03-08

**Arquivos:** `tests/test_phase3_formal.py; benchmarks/formal/ [novo]`.

**Codificar:** Construir corpus independente com proposições válidas, falsas e ambiguidades de tradução; obter revisão dos mapeamentos.

**Aceite:** Todos os fragmentos declarados têm taxa de cobertura e erros publicada; correspondência pergunta-teorema é auditada externamente.


## F4 — Geometria e imagens científicas: 55%

**Implementado:** Cenas editáveis, 11 relações exatas, construções delimitadas, SVG/PNG, campos e retratos de fase.

**Justificativa da nota:** Amostragem de curvas, legibilidade e regressão visual precisam de cobertura mais abrangente.

**Fontes principais:** `tests/test_phase4_graphics.py` e os módulos abaixo.

### F04-01

**Arquivos:** `graphics/scene_graph.py; graphics/geometry_constraints.py`.

**Codificar:** Completar contratos de curvas, equações, relações e origem das construções; preservar dependências e obrigações geométricas.

**Aceite:** Cena serializada reconstrói o modelo sem inferir matemática de pixels; objetos inválidos são recusados.

### F04-02

**Arquivos:** `forge/constructors/geometry.py; verify/geometry.py`.

**Codificar:** Ampliar construções coordenadas com degenerações, interseções e testemunhos; conferir relações por método independente.

**Aceite:** Casos colineares, tangentes, paralelos e sem interseção têm resultados explícitos e verificáveis.

### F04-03

**Arquivos:** `graphics/sampling.py`.

**Codificar:** Implementar refinamento por tolerância e detecção de descontinuidades no perfil de curvas; quantificar erro de aproximação de círculos e trajetórias.

**Aceite:** Curvas não atravessam polos; metadados indicam tolerância, limite de amostras e erro conhecido ou não certificado.

### F04-04

**Arquivos:** `graphics/coordinate_system.py; graphics/layout.py`.

**Codificar:** Tratar escalas, clipping, legendas, unidades, rótulos e margens em cenas densas; registrar limitações de layout.

**Aceite:** Transformações reversíveis preservam coordenadas; nenhum objeto requerido desaparece sem diagnóstico.

### F04-05

**Arquivos:** `graphics/svg_renderer.py; graphics/raster_renderer.py; graphics/rendering.py`.

**Codificar:** Manter semântica comum nos formatos, metadados e identificadores; estabilizar fontes e rendering no ambiente suportado.

**Aceite:** SVG/PNG correspondem à mesma cena; testes conferem orientação, escala e dados embutidos.

### F04-06

**Arquivos:** `graphics/artifacts.py; datasets/alignments.py`.

**Codificar:** Ligar figura, modelo, tarefa e verificações por hashes e versões; preservar edição sem invalidar silenciosamente a proveniência.

**Aceite:** Editar modelo exige nova verificação; imagem alterada ou metadado inconsistente é detectado.

### F04-07

**Arquivos:** `tests/test_phase4_graphics.py; tests/visual/ [novo]`.

**Codificar:** Adicionar corpus visual de referência com comparação tolerante, casos de clipping e fontes em Linux/Windows.

**Aceite:** Diferenças relevantes falham no CI; alterações de referência exigem inspeção registrada.

### F04-08

**Arquivos:** `benchmarks/results/graphics-review/ [novo]`.

**Codificar:** Executar revisão humana de legibilidade, fidelidade e editabilidade do corpus e corrigir os defeitos encontrados.

**Aceite:** Relatório identifica cenas/revisores/defeitos e correções; não é necessário competir com AlphaGeometry para cumprir a saída delimitada de F4.


## F5 — Studio e publicação: 65%

**Implementado:** Modelo comum, exportação LaTeX/Typst/HTML, PDFs reais, referências e bundles de evidências.

**Justificativa da nota:** Compilação e hashes não asseguram qualidade visual nem que o texto seja sustentado pelas evidências.

**Fontes principais:** `tests/test_phase5_studio.py` e os módulos abaixo.

### F05-01

**Arquivos:** `documents/document_model.py; documents/equation_blocks.py`.

**Codificar:** Completar blocos estruturados para tabelas, provas, hipóteses, resultados, limitações e referências cruzadas necessários aos perfis editorialmente declarados.

**Aceite:** Artigo, relatório e apostila são expressos pelo modelo comum sem inserir fontes específicas de um compilador no conteúdo canônico.

### F05-02

**Arquivos:** `documents/citations.py`.

**Codificar:** Resolver referências importadas, campos obrigatórios, identificadores e citações cruzadas, mantendo origem e revisão.

**Aceite:** Referência ausente, duplicada ou sem origem é sinalizada; bibliografia não é inventada pelo exportador.

### F05-03

**Arquivos:** `documents/figures.py; documents/publication.py`.

**Codificar:** Vincular tabelas, equações, claims e figuras aos dados/modelos/provas que os sustentam; validar links estruturados.

**Aceite:** Resultado numérico publicado é reconstituído da evidência; hash válido não é tratado como prova da narrativa.

### F05-04

**Arquivos:** `documents/latex_exporter.py; documents/typst_exporter.py; documents/html_exporter.py`.

**Codificar:** Completar paridade dos blocos, referências, unidades, Unicode e acessibilidade nos três formatos.

**Aceite:** Mesmo documento mantém conteúdo científico, numeração e referências em todos os formatos.

### F05-05

**Arquivos:** `documents/pdf_builder.py`.

**Codificar:** Fixar perfil de compiladores, fontes e dependências; impor limites de recursos e política de inclusão de arquivos ao compilar conteúdo externo.

**Aceite:** Bundle reconstrói offline no ambiente declarado; falhas e timeout conservam diagnóstico e não retornam PDF antigo.

### F05-06

**Arquivos:** `templates/research_paper/; templates/engineering_report/ [novo]; templates/teaching/ [novo]`.

**Codificar:** Criar templates funcionais dos três usos previstos com exemplos rastreáveis, avisos de dados sintéticos e limitações.

**Aceite:** Todos compilam pelos backends suportados sem referências quebradas ou alegações sem fonte.

### F05-07

**Arquivos:** `tests/test_phase5_studio.py; tests/visual/documents/ [novo]`.

**Codificar:** Testar conteúdo extraído do PDF e páginas de referência, incluindo tabelas largas, fórmulas longas e figuras.

**Aceite:** Truncamento, caracteres ausentes e referências inválidas são detectados; revisão visual humana registrada.

### F05-08

**Arquivos:** `documents/publication.py; benchmarks/results/publication-review/ [novo]`.

**Codificar:** Criar checklist de publicação e pacote de revisão ligando cada afirmação verificável à evidência e separando revisão editorial de científica.

**Aceite:** Revisor consegue recompilar e seguir os dados até as conclusões; alegações não demonstradas permanecem marcadas.


## F6 — Datasets científicos: 55%

**Implementado:** Schema versionado, JSONL/Parquet, bundles, licenças, curation, gates, splits e multimodalidade canônica.

**Justificativa da nota:** Perfis são restritos; generalização, contaminação semântica e utilidade externa continuam sem validação suficiente.

**Fontes principais:** `tests/test_phase6_datasets.py` e os módulos abaixo.

### F06-01

**Arquivos:** `datasets/schema.py; datasets/serializer.py`.

**Codificar:** Generalizar perfis de registros para simulações, observações, provas e tentativas além das tarefas construtivas atuais; criar migrações explícitas.

**Aceite:** Cada perfil tem campos obrigatórios, limites e verificadores; migração preserva IDs de origem e não fabrica evidência.

### F06-02

**Arquivos:** `datasets/semantic_fingerprint.py; datasets/split_policy.py`.

**Codificar:** Deduplicar por significado, template e origem; bloquear vazamento entre modalidades e partições, inclusive artefatos derivados.

**Aceite:** Uma figura ou trace equivalente não reaparece no holdout com outro nome; colisões são reportadas.

### F06-03

**Arquivos:** `datasets/curation.py; datasets/quality_gate.py`.

**Codificar:** Aplicar gates por perfil para correção, licença, proveniência, dificuldade, defeitos, completude e versões de verificadores.

**Aceite:** Registros incompatíveis são rejeitados com razão reproduzível; amostra de auditoria independente mede falsos aceites.

### F06-04

**Arquivos:** `datasets/serializer.py; export/parquet.py; export/jsonl.py; export/bundle.py`.

**Codificar:** Implementar processamento em lotes/streaming e retomada transacional onde os limites atuais impeçam o volume declarado.

**Aceite:** Roundtrip sem perda e exportação interrompida não produzem release aparentemente íntegro; consumo de memória é medido.

### F06-05

**Arquivos:** `datasets/model_card.py; export/huggingface.py`.

**Codificar:** Completar ficha por versão, inventário de licenças e origem, defeitos conhecidos, splits e verificadores; testar preparo e publicação em destino de teste autorizado.

**Aceite:** Download do release reconfere hashes e card; teste mock não é descrito como upload real.

### F06-06

**Arquivos:** `datasets/quality_gate.py; benchmarks/datasets/ [novo]`.

**Codificar:** Criar avaliação externa de correção, diversidade, ineditismo e dificuldade com protocolo e amostra dimensionados.

**Aceite:** Resultados por família/template e intervalos de confiança são publicados, incluindo falhas.

### F06-07

**Arquivos:** `training/controlled_experiment.py; training/ablation.py`.

**Codificar:** Integrar avaliação de utilidade downstream com modelos capazes, controles de volume/compute e ablação de componentes do dataset.

**Aceite:** Dado correto e dado útil têm relatórios separados; resultados negativos não são filtrados.

### F06-08

**Arquivos:** `tests/test_phase6_datasets.py; benchmarks/results/`.

**Codificar:** Publicar release candidato acompanhado de auditoria externa e reprodução por consumidor independente.

**Aceite:** Critérios de qualidade definidos no card passam em problemas reservados; a tese de melhoria continua aberta enquanto o ganho não for demonstrado.


## F7 — Worlds e simulações: 40%

**Implementado:** EDOs delimitadas, calor 1D FTCS, conservação, convergência, sensibilidade e comparação com observações.

**Justificativa da nota:** Convergência do calor não valida outras equações; dados reais e métodos com tolerância adaptativa são limitados.

**Fontes principais:** `tests/test_phase7_worlds.py` e os módulos abaixo.

### F07-01

**Arquivos:** `worlds/model_spec.py; worlds/ode/; worlds/pde/`.

**Codificar:** Definir perfil executável de modelos, estados, unidades, condições iniciais/de contorno, parâmetros e tolerâncias.

**Aceite:** Modelo mal posto, unidades incompatíveis e condições não suportadas falham antes da integração.

### F07-02

**Arquivos:** `worlds/integrators/; worlds/ode/`.

**Codificar:** Adicionar controle adaptativo de erro e eventos no perfil não rígido; declarar/rejeitar rigidez ou suportar método adequado com validação.

**Aceite:** Tolerâncias são verificadas contra solução analítica e solver independente; exaustão de passos gera falha explícita.

### F07-03

**Arquivos:** `worlds/pde/; worlds/mesh/`.

**Codificar:** Separar o solver de calor da condição seno fixa e suportar condições declaradas; acrescentar outra classe selecionada apenas com contrato e oráculo.

**Aceite:** Condições e estabilidade são verificadas; refinamento espacial/temporal mede erro para cada configuração suportada.

### F07-04

**Arquivos:** `worlds/conservation.py; worlds/convergence.py`.

**Codificar:** Automatizar estudos independentes de erro espacial, temporal, estabilidade e balanços por modelo.

**Aceite:** Relatório distingue erro de discretização e de modelo; regressão de ordem ou conservação bloqueia release do perfil afetado.

### F07-05

**Arquivos:** `worlds/validation.py; adapters/instruments/`.

**Codificar:** Ingerir observações reais com unidades, incerteza, origem, calibração e separação calibração/validação.

**Aceite:** Previsões são comparadas com dados não usados no ajuste; incompatibilidades e discrepâncias permanecem no relatório.

### F07-06

**Arquivos:** `worlds/sensitivity.py`.

**Codificar:** Expandir análise para múltiplos parâmetros e propagação de incerteza com domínio de validade e controle de erro.

**Aceite:** Casos analíticos verificam sensibilidade; análise registra não identificabilidade e parâmetros correlacionados.

### F07-07

**Arquivos:** `worlds/animation.py; graphics/artifacts.py`.

**Codificar:** Vincular frames a estados, tempos, malha e escala; exportar trajetória e metadados suficientes para replay.

**Aceite:** Animação não suaviza ou esconde instabilidade; cada frame pode ser reconstruído dos dados.

### F07-08

**Arquivos:** `tests/test_phase7_worlds.py; benchmarks/worlds/ [novo]`.

**Codificar:** Publicar suíte analítica, comparação com solver externo e ao menos um estudo experimental apropriado por perfil físico que alegue validade observacional.

**Aceite:** Cada alegação tem convergência, limites e validação aplicável; perfis exclusivamente matemáticos são identificados como tais.


## F8 — Multimodalidade e agentes: 30%

**Implementado:** Alinhamento de modalidades, agentes restritos, currículo, ablações, nearest-neighbor e MLP numérico aberto.

**Justificativa da nota:** Nenhum treinamento multimodal profundo demonstrado; o estudo GSM8K teve ganho médio zero.

**Fontes principais:** `tests/test_phase8_agents_training.py` e os módulos abaixo.

### F08-01

**Arquivos:** `datasets/multimodal.py; datasets/alignments.py`.

**Codificar:** Generalizar alinhamentos entre texto, equações, diagramas, estados temporais e provas com granularidade e validade por modalidade.

**Aceite:** Cada alinhamento reconduz ao mesmo problema; respostas e certificados ficam fora da entrada quando são alvos.

### F08-02

**Arquivos:** `training/multimodal_model.py [novo]; training/registry.py`.

**Codificar:** Implementar adaptador de modelo aberto capaz de consumir imagem/texto/equações, com checkpoints, licença e configurações reproduzíveis.

**Aceite:** Modelo realmente aprende de pixels e símbolos, em vez de apenas hash de texto SVG; inferência limpa reconstrói previsões salvas.

### F08-03

**Arquivos:** `training/curriculum.py; training/controlled_experiment.py`.

**Codificar:** Suportar treinamento/ajuste com orçamento explícito, retomada e controles pareados de dados, compute, inicialização e tuning.

**Aceite:** Controle e tratamento diferem somente pelo fator estudado; protocolo é congelado antes do holdout final.

### F08-04

**Arquivos:** `training/contamination.py; training/evaluation.py`.

**Codificar:** Auditar templates, equivalência semântica, imagens derivadas e contaminação conhecida dos modelos; avaliar benchmarks externos reservados.

**Aceite:** Relatório declara contaminação desconhecida e separa familiaridade do modelo de generalização inédita.

### F08-05

**Arquivos:** `training/ablation.py; training/evaluation.py`.

**Codificar:** Comparar modalidades, currículo e qualidade dos dados com múltiplas sementes, efeito, intervalos e correção de comparações.

**Aceite:** Resultados por seed e previsões são publicados; ganho zero/negativo não é convertido em sucesso científico.

### F08-06

**Arquivos:** `agents/planner.py; agents/proposals.py`.

**Codificar:** Adicionar ligação tipada de resultados entre ações, planejamento delimitado, estado persistente, retomada e diagnóstico de falhas.

**Aceite:** Agente executa tarefa inédita em múltiplas etapas e seus dados de entrada/saída são reexecutáveis; não apenas sequência fixa demonstrativa.

### F08-07

**Arquivos:** `agents/permissions.py; agents/tool_registry.py`.

**Codificar:** Separar ferramentas locais confiáveis de plugins/código externos; executar estes últimos em isolamento de sistema com capacidades explícitas.

**Aceite:** Timeout de subprocesso não é vendido como sandbox; testes mostram limites de arquivos, rede e recursos do perfil externo.

### F08-08

**Arquivos:** `tests/test_phase8_agents_training.py; benchmarks/agents_multimodal/ [novo]`.

**Codificar:** Realizar estudo externo de generalização e ablações e avaliação de agentes por tarefa completa, correção e custo.

**Aceite:** Pipeline de avaliação está completo mesmo com resultado negativo; a tese adicional de aumentar capacidade só fecha com ganho robusto e reprodução independente.


## F9 — Discovery: 30%

**Implementado:** Hipóteses unitárias, regressão polinomial, holdout, desenho experimental finito, busca formal e novidade local.

**Justificativa da nota:** Bibliografia é fornecida localmente; não há descoberta nova nem reprodução científica independente demonstrada.

**Fontes principais:** `tests/test_phase9_discovery.py` e os módulos abaixo.

### F09-01

**Arquivos:** `discovery/hypothesis.py; discovery/symbolic_regression.py`.

**Codificar:** Criar busca de candidatos em gramática declarada além de polinômios univariados, com unidades, hipóteses, complexidade e orçamento.

**Aceite:** Modelos de dimensões inválidas são rejeitados; recuperação de leis conhecidas e falhas é medida em corpus reservado.

### F09-02

**Arquivos:** `discovery/symbolic_regression.py; worlds/validation.py`.

**Codificar:** Separar ajuste, seleção e teste; tratar ruído, incerteza, identificabilidade e extrapolação explicitamente.

**Aceite:** Escolha de modelo não consulta holdout; intervalo de validade e comparação com alternativas acompanham a hipótese.

### F09-03

**Arquivos:** `knowledge/literature.py; discovery/novelty_screen.py`.

**Codificar:** Implementar importação consultável de fontes bibliográficas verificáveis, snapshots, consultas, datas, licenças e vínculos aos documentos.

**Aceite:** Antecedentes relevantes de um corpus de referência são recuperados; ausência na busca não implica novidade global.

### F09-04

**Arquivos:** `discovery/theorem_search.py; knowledge/claim_graph.py`.

**Codificar:** Indexar teoremas e mapear condições, unidades e equivalências entre hipóteses e resultados conhecidos.

**Aceite:** Conexão conserva hipóteses; exemplo com domínio diferente não é declarado mesmo teorema.

### F09-05

**Arquivos:** `discovery/experimental_design.py`.

**Codificar:** Planejar experiências com custo, segurança operacional do domínio, viabilidade, ruído e informação esperada; persistir propostas e resultados.

**Aceite:** Plano discrimina modelos em dados reservados; propor experimento não é registrado como executá-lo.

### F09-06

**Arquivos:** `falsifier/counterexample_miner.py`.

**Codificar:** Integrar busca adversarial por fronteiras, casos fora da distribuição e inconsistências com medições, mantendo redução e escopo.

**Aceite:** Refutação é reproduzível na hipótese original; orçamento esgotado permanece inconclusivo.

### F09-07

**Arquivos:** `discovery/research_program.py; documents/publication.py`.

**Codificar:** Orquestrar hipótese→antecedentes→experimento→refutação→revisão, com decisões versionadas e critérios de parada.

**Aceite:** Histórico permite reconstruir escolhas e hipóteses abandonadas; relatório não seleciona apenas descobertas aparentes.

### F09-08

**Arquivos:** `tests/test_phase9_discovery.py; benchmarks/discovery/ [novo]`.

**Codificar:** Criar benchmarks de redescoberta e casos negativos, e executar investigação externa revisável com reprodução independente quando pertinente.

**Aceite:** Novidade é avaliada por pesquisadores e antecedentes; código só registra o resultado, não concede novidade a si mesmo.


## F10 — RSI controlado: 35%

**Implementado:** Busca Euler/RK4, contratos, holdouts consumíveis, teste estatístico, duas gerações, lineage, rejeição e rollback.

**Justificativa da nota:** O espaço de políticas é estreito; independência do avaliador e isolamento não resistem a proponente hostil com acesso ao mesmo processo/disco.

**Fontes principais:** `tests/test_phase10_evolution.py` e os módulos abaixo.

### F10-01

**Arquivos:** `evolution/policy_genome.py; evolution/proposal_validator.py`.

**Codificar:** Definir genomas tipados para estratégias de solver, sequências de regras, seleção de problemas e geração de candidatos, com limites.

**Aceite:** Propostas fora do contrato são rejeitadas; cada família de política possui interpretador e invariantes verificáveis.

### F10-02

**Arquivos:** `evolution/search.py; evolution/evaluator.py`.

**Codificar:** Generalizar busca e avaliação para correção/capacidade/custo em tarefas de múltiplas famílias, preservando baselines e regressões.

**Aceite:** Melhoria não depende somente de reduzir erro em EDOs; correção perdida bloqueia promoção.

### F10-03

**Arquivos:** `evolution/holdout_manager.py`.

**Codificar:** Separar armazenamento reservado da identidade do proponente; criar alocação persistente de holdouts com prevenção de reutilização entre processos e campanhas.

**Aceite:** Reabrir outro gerente não permite reutilizar conjunto conhecido; acessos e consumo ficam auditados.

### F10-04

**Arquivos:** `evolution/evaluator.py; evolution/release_gate.py`.

**Codificar:** Executar avaliador em processo/ambiente com autoridade independente e contratos imutáveis, com recibos autenticados.

**Aceite:** Proponente não consegue modificar avaliador e depois obter promoção válida; recibo forjado ou contrato diferente é rejeitado.

### F10-05

**Arquivos:** `evolution/statistical_tests.py`.

**Codificar:** Tratar múltiplas propostas e gerações, avaliações sequenciais, ruído e efeito mínimo de utilidade; dimensionar amostras pelo protocolo.

**Aceite:** Taxa de falsos positivos é verificada em controles nulos; aceitação exige significância e efeito prático definidos antes da seleção.

### F10-06

**Arquivos:** `evolution/code_sandbox.py [novo]; evolution/proposal_validator.py`.

**Codificar:** Adicionar caminho de propostas de código somente com isolamento, limites, testes, análise das alterações e revisão registrada.

**Aceite:** Código candidato não acessa segredos/holdouts/avaliador; testes adversariais verificam fronteiras e nenhum código é promovido só por autodeclaração.

### F10-07

**Arquivos:** `evolution/lineage.py; evolution/rollback.py; evolution/release_gate.py`.

**Codificar:** Integrar promoção atômica, canário, monitoramento e rollback das versões de estratégia/código e seus artefatos.

**Aceite:** Falha após promoção restaura estado e dependências verificadas; revisão e decisão permanecem no histórico.

### F10-08

**Arquivos:** `tests/test_phase10_evolution.py; benchmarks/evolution/ [novo]`.

**Codificar:** Demonstrar ciclos sucessivos em mais de uma família com novos holdouts e avaliação externa, publicando ganhos, custos e regressões.

**Aceite:** Melhoria de eficiência/capacidade reproduzida fora da campanha; não se exige nem se afirma autoaperfeiçoamento irrestrito.


## F11 — Outras disciplinas: 25%

**Implementado:** Dez modelos disciplinares delimitados, circuitos DC, acoplamento eletrotérmico e CSV de instrumento.

**Justificativa da nota:** Modelos são idealizados e predominantemente sintéticos; existência de um exemplo não equivale a uma biblioteca disciplinar validada.

**Fontes principais:** `tests/test_phase11_domains.py` e os módulos abaixo.

### F11-01

**Arquivos:** `domains/contracts.py; domains/engineering/`.

**Codificar:** Definir perfis por disciplina com unidades, leis, hipóteses e limites; ampliar engenharia com geometria/CAD paramétrico e verificações de carregamento no perfil escolhido.

**Aceite:** Cada saída declara regime de validade e tem referência independente; não promete engenharia universal.

### F11-02

**Arquivos:** `domains/circuits/`.

**Codificar:** Ampliar perfil DC para elementos e análises dinâmicas selecionadas com validação de topologia, balanços e condições iniciais.

**Aceite:** Benchmarks conferidos com simulador de circuitos independente; circuitos singulares têm diagnóstico.

### F11-03

**Arquivos:** `domains/materials/`.

**Codificar:** Adicionar modelos constitutivos selecionados, parâmetros com origem e ensaios de validação, além da relação termoelástica unidimensional atual.

**Aceite:** Curvas e incertezas são comparadas com referências/ensaios; extrapolação de regime é identificada.

### F11-04

**Arquivos:** `domains/chemistry/`.

**Codificar:** Definir perfil químico além do balanceamento neutro: espécies/cargas e equilíbrio ou cinética selecionados com conservação e unidades.

**Aceite:** Casos de referência preservam massa/carga; resultados termodinâmicos usam parâmetros e bases rastreáveis.

### F11-05

**Arquivos:** `domains/control/`.

**Codificar:** Ampliar dimensão e configuração de sistemas no perfil escolhido, análise de estabilidade e resposta com unidades e robustez.

**Aceite:** Respostas e propriedades são comparadas com biblioteca de controle independente; instabilidade não é ocultada por horizonte curto.

### F11-06

**Arquivos:** `domains/earth/; domains/biology/`.

**Codificar:** Implementar estudos delimitados adicionais com parâmetros observados e calibração/validação separadas, além de hidrostática/logística/SIR ideais.

**Aceite:** Limites de identificação, incerteza e viés de observações constam dos resultados; especialistas revisam a adequação dos modelos.

### F11-07

**Arquivos:** `worlds/multiphysics/; adapters/instruments/`.

**Codificar:** Generalizar interfaces de acoplamento conservativo e ingestão de medições com relógio, calibração, qualidade, unidades e proveniência.

**Aceite:** Acoplamento fecha balanços e estudo de convergência; dados de instrumento são distinguíveis de fixtures sintéticas.

### F11-08

**Arquivos:** `tests/test_phase11_domains.py; benchmarks/domains/ [novo]`.

**Codificar:** Criar suíte por disciplina, comparações com ferramentas externas e estudos observacionais apropriados, com revisão de especialistas.

**Aceite:** Cada perfil reivindicado possui validação específica; expansão de domínio cria novo contrato em vez de elevar artificialmente a cobertura de toda a ciência.


## F12 — Conhecimento científico vivo: 35%

**Implementado:** Claims versionados, relações, impacto, replay, snapshots/HMAC, conflitos preservados, revisores e equipes locais.

**Justificativa da nota:** Federação é offline; identidades e revisões são declarações locais; integridade não garante verdade nem revisão independente.

**Fontes principais:** `tests/test_phase12_knowledge.py` e os módulos abaixo.

### F12-01

**Arquivos:** `knowledge/versioned_claims.py; knowledge/claim_graph.py`.

**Codificar:** Completar contrato de claims estruturados com hipóteses, escopo, incerteza e vínculos explícitos entre evidência e afirmação.

**Aceite:** Mesma conclusão sob hipóteses distintas não é fundida; evidência de integridade não vira automaticamente evidência científica.

### F12-02

**Arquivos:** `knowledge/federation.py; knowledge/identity.py [novo]`.

**Codificar:** Implementar identidade de pares e assinaturas verificáveis, confiança configurável, revogação e rotação de chaves.

**Aceite:** Importador autentica autor/versão e rejeita alterações, replay inadequado e chave revogada; HMAC compartilhado não é chamado assinatura de autoria individual.

### F12-03

**Arquivos:** `knowledge/federation.py; knowledge/storage.py [novo]`.

**Codificar:** Implementar sincronização incremental, transporte opcional, armazenamento de evidências por conteúdo, quarentena e recuperação.

**Aceite:** Dois pares independentes sincronizam após desconexão sem perder histórico; conteúdo inválido não entra no conjunto confiável.

### F12-04

**Arquivos:** `knowledge/semantic_reconciliation.py`.

**Codificar:** Ampliar reconciliação com condições/unidades e decisões explícitas de merge; manter forks e modelos concorrentes.

**Aceite:** Não equivalente permanece separado; disputa não desaparece por escolher a revisão mais recente.

### F12-05

**Arquivos:** `knowledge/dependency_impact.py`.

**Codificar:** Propagar invalidação/revisão por dependência com índices, notificações locais e planos de reconferência, sem reescrever a história.

**Aceite:** Refutação chega a todos os claims afetados; rerun registra novas revisões e conserva evidências anteriores.

### F12-06

**Arquivos:** `knowledge/peer_review.py; agents/scientific_teams.py`.

**Codificar:** Autenticar revisores/participantes, papéis, conflitos, decisões, recursos e revisão por versão; separar opinião de promoção editorial.

**Aceite:** Revisor não aprova a própria alegação; revisão antiga não aprova automaticamente nova versão; agentes locais não se passam por especialistas externos.

### F12-07

**Arquivos:** `knowledge/provenance_audit.py; discovery/research_program.py`.

**Codificar:** Criar auditoria incremental de origem/licença/ambiente e execução de programas com estados, decisões e artefatos duráveis.

**Aceite:** Terceiro recupera cadeia de evidências e reconfere claims computacionais; observações e revisões externas mantêm seus limites de autenticação.

### F12-08

**Arquivos:** `tests/test_phase12_knowledge.py; benchmarks/federation/ [novo]`.

**Codificar:** Validar federação com múltiplos pares, conflitos, refutações, falhas de transporte e revisão independente real de um programa.

**Aceite:** Reprodução externa percorre dependências e contradições; sistema preserva incertezas e não anuncia banco infalível de verdades.


## Dependências, ordem de execução e trabalho transversal

A ordem abaixo evita aumentar módulos sobre contratos incompatíveis. Itens de
uma mesma etapa podem avançar independentemente quando seus contratos estiverem
estáveis; isto é uma sequência de implementação, não um cronograma.

1. **Contrato de aceitação e núcleo:** F01-01/02/07, F02-01 e F06-01. Fixar catálogo público de operações, schemas, modelos e perfis disciplinares antes de ampliar cobertura. Registrar em `docs/acceptance/phase_profiles.md` [novo] os limites de cada perfil, casos suportados e critérios de release.
2. **Correção e evidência matemática:** restante de F1, F03-01/04/07, F04-01/02/06 e F06-02/03. Obrigações, IDs e vinculação pergunta–resultado precisam atravessar os artefatos.
3. **Desafio e datasets:** restante de F2, F3, F4 e F6. Não usar holdout final para selecionar templates ou calibrar dificuldade.
4. **Publicação e simulações:** F5 e F7; F11-01 define perfis, F11-07 conecta medições e acoplamentos. PDF e figura dependem dos artefatos verificados.
5. **Aprendizado e agentes:** F8 depende de splits/gates F6, tarefas F2, modalidades F4 e estados F7. Ganho externo não é pré-condição para implementar a avaliação; é pré-condição para alegar melhoria.
6. **Discovery e disciplinas:** F9 depende de F3/F7/F11 e fontes bibliográficas; completar F11 com especialistas e validação apropriada. Sem observações confiáveis, limitar alegações a modelos matemáticos/sintéticos.
7. **Evolution:** F10 depende de avaliadores independentes F2/F6/F8, contratos de correção F3 e separação de autoridade. Não liberar propostas de código antes do isolamento e revisão.
8. **Federação e colaboração:** F12 pode preparar identidade/armazenamento antes, mas o estudo integrado exige claims/evidências dos módulos anteriores e pesquisadores independentes.

Trabalho transversal também obrigatório para o perfil de release:

| ID | Arquivos propostos/existentes | Implementação e aceite |
|---|---|---|
| T-01 | `docs/acceptance/phase_profiles.md` [novo]; `tools/assess_vision.py` | Codificar manifesto de critérios por fase e vincular cada check a artefatos, versão e limites. Relatório deve distinguir falhou, não executado, inconclusivo e não aplicável com justificativa; presença de arquivo não aprova fase. |
| T-02 | `core/`; `datasets/schema.py`; `knowledge/` | Política comum de versão, migração, IDs, ambiente e compatibilidade. Fixtures antigas continuam legíveis ou recebem erro de migração explícito; nenhuma mudança silenciosa do significado de um ID. |
| T-03 | `.github/workflows/`; `tests/integration/` | Executar conformidade dos perfis em Linux/Windows, toolchains formais e dependências opcionais relevantes. Jobs científicos caros podem ser agendados; ausência deles bloqueia alegação de validação daquele release. |
| T-04 | `benchmarks/protocols/` [novo]; `benchmarks/results/` | Protocolos congelados, seleção de amostra, seeds, orçamento, baselines e critérios estatísticos antes dos testes finais. Registrar todos os resultados e revisões de protocolo; rerun no mesmo holdout não é novo teste independente. |
| T-05 | `tests/integration/test_scientific_artifact.py` [novo] | Exercitar o artefato completo do vision.md: problema, hipóteses, modelo, solução, trace, verificação, contraexemplos, SVG/PNG, trajetória, certificado aplicável, documento e manifesto. Adulteração de cada ligação deve falhar. Ausência de prova/observação aplicável precisa ficar explícita. |
| T-06 | `pyproject.toml`; ferramentas de build/instalador; `docs/` | Versionar dependências/ambientes e procedimentos de reconstrução; validar wheel e instalador em ambiente limpo. Preservar compatibilidade pública e limites documentados. Não refazer a correção Windows já aprovada sem nova falha. |
| T-07 | `benchmarks/resources/` [novo]; ferramentas de avaliação | Medir memória, disco, tempo, cancelamento e retomada em volumes do perfil; falha por orçamento não gera artefato aceito ou truncado silenciosamente. |
| T-08 | `docs/audits/`; `tools/assess_vision.py` | Registrar revisão independente e rastrear correções dos achados por versão. O software valida assinaturas e conteúdo estruturado; não inventa identidade, independência ou aprovação dos revisores. |

## O que não pode ser concluído apenas codificando

| Evidência pendente | Fases afetadas | O que depende de fora do código |
|---|---|---|
| Dificuldade relevante e diversidade | F2/F6 | Corpus inédito e avaliação por solvers/pessoas independentes; desenhar gerador não garante problemas difíceis. |
| Utilidade de dados | F6/F8 | Modelo adequado, compute, licenças, protocolo e experimento reservado. Hoje o ganho observado é zero. Novo experimento também pode dar resultado negativo. |
| Qualidade editorial | F4/F5 | Inspeção visual humana, registro dos defeitos e correção; compilar não substitui leitura do PDF. |
| Correspondência de formalização | F3 | Revisão da relação entre pergunta original e enunciado formal, além da checagem do kernel. |
| Validação de fenômenos | F7/F11 | Dados observados, calibração, incertezas e especialistas adequados. Solução analítica só valida o solver dentro do modelo. |
| Antecedência e descoberta | F9 | Consulta bibliográfica suficiente, julgamento de novidade e reprodução quando pertinente. Não existe verificador universal de novidade global. |
| Ganho recursivo controlado | F10 | Melhoria medida em novos holdouts, sem regressões inadmissíveis e sem domínio do avaliador pelo proponente. Não há garantia de que toda geração melhore. |
| Colaboração científica real | F12 | Pares/revisores independentes com identidade e conflitos verificáveis; revisão local sintética não basta. |

O vision.md não fixa tamanhos de amostra, número de sementes, efeito mínimo,
modelos ou número de disciplinas validadas. Esses parâmetros devem ser definidos
por perfil e análise de poder/risco no protocolo T-04, antes de olhar o resultado.
Não imponho números arbitrários como se fossem requisitos já aprovados da visão.

Há duas decisões diferentes: **software de avaliação concluído** pode publicar
resultado negativo corretamente; **tese de ganho científico demonstrada** continua
aberta com resultado negativo. As duas devem aparecer separadamente no relatório.
A F8 exige medir e publicar, inclusive negativos; não exige falsificar um ganho
positivo para passar a avaliação. A ambição geral de elevar capacidade continua
sem demonstração até que haja evidência positiva apropriada.

## Regra para marcar uma fase como 100%

1. Fixar o perfil finito de aceitação e sua versão; não diminuir o perfil depois de observar falhas para fabricar aprovação.
2. Concluir todos os itens Fxx aplicáveis e dependências transversais, com código real e documentação dos limites.
3. Executar os critérios com artefatos reproduzíveis, casos negativos e avaliadores independentes onde exigidos; nenhuma pendência vira sucesso por ausência de teste.
4. Obter as revisões/medições externas pertinentes e registrar contradições e falhas.
5. Publicar relatório por eixo e por requisito. “100% do perfil v1” deve sempre vir acompanhado do perfil; nunca substituir por “100% da ciência prevista até 2056”.

## Inventário do trabalho listado

São **96 itens de fase** (oito por fase), mais **8 itens transversais**: **104 itens**
de implementação/integração/validação. A contagem não estima horas nem importância;
um item de treinamento ou federação pode custar muito mais que uma alteração de
schema. As atividades externas da tabela anterior são pré-requisitos adicionais,
não tarefas resolvidas criando arquivos.

A decomposição é detalhada o suficiente para abrir issues e planejar entregas,
mas poderá revelar novas subtarefas ao implementar. “Exatamente tudo” só passa a
ser verificável depois de fechar os perfis e os protocolos; esta auditoria não
promete uma lista imutável para pesquisa científica aberta.

<!-- nabla:contracts:start -->
## Contratos executáveis e pendências atuais

A matriz registra 213 requisitos com perfis parciais, 0 planejados e 0 integralmente validados. Uma referência de implementação não equivale à aceitação integral.

- [Matriz original dos 213 requisitos](../acceptance/evidence_matrix.json).
- [Rastreabilidade de fases, requisitos, testes e evidências](../acceptance/vision_traceability.json).
- [Domínios, operações, recusas e tolerâncias](../acceptance/scientific_capabilities.yaml).

F0 explicita contratos e infraestrutura; F13 continua horizonte aberto. Os perfis de software não demonstram autonomia científica geral. Provas formais exigem kernel e auditoria de hipóteses; GPU exige execução identificada; observações e revisão externa não são substituídas por fixtures ou identidade declarada.

Verificar: `python tools/check_roadmap.py` e `python tools/check_public_contracts.py`, na raiz do repositório.
<!-- nabla:contracts:end -->
