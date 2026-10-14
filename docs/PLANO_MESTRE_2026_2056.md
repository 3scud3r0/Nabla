# ∇ NABLA — PLANO MESTRE 2026–2056+

**Natureza:** proposta de arquitetura e roteiro; não é implementação.  
**Data da proposta:** 14/10/2026.  
**Fonte principal:** materiais anexados pelo mantenedor: briefing de engenharia, contexto e roteiro, capacidades e hospedagem, incentivos, scripts de rede, RSI e deploy, transcrição de visão sobre Nabla Data/Calc.  
**Escopo desta proposta:** arquitetura e roteiro, sem implementar fases, executar deploy ou publicar datasets.

## 0. Tese e produto

Nabla é uma infraestrutura local-first de raciocínio e produção científica verificável. Seu objetivo é operar o ciclo: representar → compilar a especificação → explorar/gerar → resolver → refutar/verificar → simular → visualizar → documentar → publicar com revisão → aprender com os resultados. A calculadora de luxo, a forja de dados, o assistente científico, as simulações e a publicação são modos de um mesmo motor. O nome principal permanece **Nabla**; `calc`, `forge`, `prove`, `studio`, `worlds`, `discover`, `evolve` e `publish` são experiências/subcomandos, não produtos desconectados. O nome do pacote `nablamath` é preservado até migração formal.

**Duas assimetrias úteis:** (i) gerar um problema a partir de uma solução conhecida pode ser mais barato que resolver o problema apresentado na direção usual; (ii) verificar um certificado pode ser bem mais barato do que descobrir sua prova. Nenhuma delas é universal: uma solução gerada não implica dificuldade, novidade, relevância nem generalização de modelos.

**Limite científico:** matemática exata, prova formal, métodos numéricos e observação experimental fornecem espécies diferentes de evidência. É inaceitável convertê-las automaticamente umas nas outras. Dados sintéticos podem aumentar a qualidade do treinamento de IA, mas não garantem sistemas de nível humano geral nem superinteligência.

## 1. Critérios não negociáveis de engenharia

1. Inspecionar o checkout e o `HEAD` antes de criar módulo ou substituir implementação; compatibilidade de `import nablamath`, CLI e bancos SQLite.
2. Uma API semântica canônica. Interfaces são adaptadores; exportadores nunca recalculam a matemática silenciosamente.
3. Entradas tipadas: expressão, domínio, hipóteses, unidades, restrições, objetivo, tolerância, custo, versão do oráculo.
4. Testes diretos e diferenciais, property-based, metamórficos, prova formal quando aplicável e benchmarks externos.
5. Registro de estados **ortogonais**, e não uma única pontuação de 'verdade': construção sintética, igualdade exata, prova formal, convergência numérica, validação experimental, revisão humana, novidade bibliográfica.
6. Separar gerador, solver, verificador, validador e curador; fixar conjuntos de avaliação e impedir otimização oportunista sobre o holdout.
7. Limites de memória, CPU, GPU, espaço, tempo, energia; execução externa não confiável isolada; sem publicar dados automaticamente.
8. Metadados de autoria, licenças, consentimento, proveniência, reproducibilidade e política de retratação.
9. Diferenciar qualidade tipográfica de veracidade da alegação; PDFs sintéticos jamais se apresentarão como pesquisas empíricas reais.
10. Cada fase exige critério de saída observável, com comandos, commit, ambiente, relatórios, aprovação e limites.

## 2. O objeto central: ScientificArtifact

Toda capacidade deve gerar ou consumir um objeto estável com: `artifact_id`, `schema_version`, `kind`, `formal_spec`, `semantic_ir`, `variables`, `types`, `units`, `assumptions`, `domain`, `constraints`, `objective`, `generator`, `seed`, `solver_trace`, `witness`, `verification`, `validation`, `counterexamples`, `source_refs`, `environment`, `cost`, `lineage`, `license`, `consent`, `review`, `representations`, `outputs` e `limitations`. Nem todos os campos são obrigatórios em todos os domínios: perfis de schema estabelecem exigências por tarefa.

Relações: `derived_from`, `tested_by`, `refuted_by`, `proved_by`, `rendered_as`, `simulated_by`, `trained_on`, `supersedes`, `retracted_by`. Hashes asseguram detecção de alteração de bytes, não prova de verdade/autoria. Grafo epistêmico aceita ciclos em relações semânticas; apenas linhagem e dependência técnica devem obedecer DAG onde adequado.

Exemplo de família sintética multimodal: especificação geométrica formal → pontos e relações → problema → prova no sistema de referência → figura SVG/PNG com mesmo sistema de coordenadas → fontes TeX/Typst → PDF → JSONL/Parquet de treino e teste de percepção → manifesto e certificados ligados ao mesmo `artifact_id`.

## 3. Visão da árvore-alvo (não criar agora)

Caminhos **existentes a preservar/verificar**: `pyproject.toml`, `src/nablamath/`, `src/nablamath/expression.py`, `src/nablamath/symbolic/`, `src/nablamath/math/`, `src/nablamath/storage.py`, `src/nablamath/knowledge/`, `src/nablamath/pipeline/`, `src/nablamath/cli.py`, `src/nablamath/desktop/`, `tests/`, `lean/`, `website/`, `docs/`, `legacy/`, `services/`, `tools/`. Presença e APIs definitivas dependem da auditoria do checkout; os arquivos avulsos `nabla_network.py`, `nabla_improve.py` e `nabla_deploy.py` são protótipos de referência anexados, não automaticamente partes do pacote instalado.

**Áreas de extensibilidade a consolidar/criar gradualmente** (nomes sugestivos sujeitos à auditoria):

```
Nabla/
├── pyproject.toml                         # distribuição e extras opcionais
├── README.md / LICENSE / SECURITY.md / CITATION.cff
├── src/nablamath/
│   ├── expression.py                      # AST já existente: preservar se canônica
│   ├── symbolic/                          # parser, e-graph, regras, derivadas e integração
│   ├── math/                              # álgebra, probabilidade, análise, física existente
│   ├── core/                              # semantic_ir, types, units, assumptions, obligations
│   ├── calc/                              # sessões, notebooks e resultados de cálculo
│   ├── forge/                             # construção inversa e geração por domínio
│   ├── verify/                            # certificados, conferência independente e oráculos
│   ├── falsifier/                         # exploração de casos-limite e contraexemplos
│   ├── formal/                            # interface Lean/SMT e auditoria de formalização
│   ├── datasets/                          # schemas, splits, curadoria, empacotamento
│   ├── graphics/                          # cena semântica, diagrama, gráfico, renderização
│   ├── documents/                         # TeX, Typst, Markdown, HTML, PDF
│   ├── worlds/                            # matemática numérica, simulações e validação
│   ├── discovery/                         # hipóteses, busca e planejamento de experimentos
│   ├── knowledge/                         # ligações semânticas e revisão de evidência
│   ├── evolution/                         # busca de políticas e RSI contido
│   ├── agents/                            # ferramentas e interfaces de agentes locais
│   ├── runtime/                           # limites de recursos e execução isolada
│   ├── adapters/                          # integrações com bibliotecas externas
│   ├── export/                            # empacotadores e publicação consentida
│   ├── cli.py                             # CLI antiga, ampliada sem quebra
│   └── desktop/                           # interface local já existente, evolutiva
├── schemas/                               # ScientificArtifact, Task, Evidence, Dataset
├── lean/Nabla/                            # namespaces e teoremas formais versionados
├── tests/                                 # unit, property, differential, integration, security
├── benchmarks/                            # baselines, calibração, OOD e desempenho
├── examples/                              # experimentos completos pequenos
├── docs/                                  # arquitetura, guias, decisões, auditorias
├── templates/                             # relatórios, figuras, posters, manuscritos
├── configs/                               # perfis CPU/GPU, recursos, políticas, publicação
├── tools/                                 # migração, schema, checkers, CI
├── packages/                              # opcionais: Rust e integrações externas
├── datasets/                              # apenas amostras e manifests versionáveis
├── legacy/                                # legado conservado e documentado
├── services/                              # rede opcional arquivada, não pré-requisito
└── website/                               # site estático de documentação/exemplos
```

Não realizar refatoração maciça desta árvore. Cada adição depende dos critérios de aceite da etapa e da existência real de implementações similares.

## 4. Etapas de evolução: entregas, arquivos, critérios de fechamento

### F0 — Outubro–dezembro de 2026: diagnóstico e preservação da base

**Capacidades:** identificar o estado real, estabilizar instalação e testes, corrigir sintaxe/API, separar histórico de produto, decidir política de versionamento. Mapear módulos existentes de álgebra, Markov, domínio, Lean, e-graph, dados, proveniência, visualização e CLI. Conferir inconsistências do `symbolic/__init__.py` e `differentiate.py` observadas na leitura pública. **Não começar um novo CAS paralelo.**

**Pastas/arquivos:** `docs/audits/BASELINE_2026_10.md` (HEAD e testes), `docs/adr/0001-product-scope.md` (local-first), `docs/adr/0002-canonical-ast.md` (única semântica), `docs/architecture/current-modules.md` (mapa), `docs/compatibility.md` (contratos), `tools/check_imports.py` (diagnóstico, planejado), `tests/regression/test_public_api.py` (regressão), `.github/workflows/ci.yml` (CI).

**Portão:** instalação limpa; imports/CLI compatíveis; compilação e testes em Python suportados; lista de dependências/licenças; diff revisável; nenhum teste relatado sem execução.

### F1 — 2026–2027: núcleo matemático confiável, calculadora científica

**Capacidades:** inteiros grandes, racionais, aritmética simbólica, polinômios, matrizes, funções e hipóteses, diferenciação/integração em domínios explicitamente suportados; expressões complexas e intervalos controlados; domínio, singularidades, unidades, precisão, séries e estatística básica. Completar **matemática principal útil** por incrementos, não 'toda matemática'. CLI calculadora; desktop local e histórico de sessões.

**Pastas/arquivos (candidatos):** `src/nablamath/core/semantic_ir.py` (representação comum), `core/types.py` (tipagem), `core/assumptions.py` (hipóteses), `core/units.py` (dimensão), `core/precision.py` (exato/numérico), `core/obligations.py` (condições para valer), `calc/session.py` (sessão), `calc/notebook.py` (células), `calc/result.py` (resultado), `math/linear_algebra/` (matrizes), `math/calculus/` (derivadas e integrais), `tests/math/` (corpus de regressão). A localização final depende do núcleo existente; não duplicar `symbolic/assumptions.py` sem motivo.

**Portão:** identidades comparadas com implementações independentes; contraexemplos de perda de domínio; testes de unidades; corpus reproduzível; UX offline utilizável por terceiros.

### F2 — 2027–2028: Forge v1 — matemática inversa em grande escala

**Capacidades:** gerar solução/estrutura primeiro e derivar problemas com complexidade controlada; integração por derivação inversa, fatoração por produto de fatores, equações com raízes plantadas, matrizes com propriedades fixadas, cadeias Markov com comportamento conhecido, provas por reescrita inversa, casos adversariais de domínio. Resolver novamente em pipeline separado, conferir, registrar trajetórias e rejeições. Separar treino/validação/teste por família estrutural, não só por seed.

**Pastas/arquivos:** `forge/task_spec.py` (contrato), `forge/sampling.py` (parâmetros), `forge/constructors/polynomial.py`, `forge/constructors/integration.py`, `forge/constructors/linear_systems.py`, `forge/constructors/markov.py`, `forge/constructors/domain_traps.py`, `forge/reverse_builder.py`, `forge/difficulty.py`, `forge/deduplicate.py`, `verify/polynomial.py`, `verify/trace.py`, `datasets/splits.py`, `benchmarks/forge_baselines/`, `tests/forge/`.

**Portão:** reconstrução por seed; verificação independente; corrupção induzida rejeitada; deduplicação; benchmarks com dificuldade relativa a famílias de solvers e recursos declarados; diversidade semântica medida. Tempo maior do Z3 ou caracteres maiores não bastam.

### F3 — 2028–2029: prova formal, falsificação e certificados

**Capacidades:** interface para Lean 4/Mathlib e SMT (Z3/CVC5); especificação e prova fiel, sem axiomas inesperados; rastrear hipóteses e traduções; criar formal proof tasks e proof states; encontrar/encolher contraexemplos quando uma propriedade falha; guardar provas alternativas e impossibilidades locais.

**Pastas/arquivos:** `formal/lean_bridge.py`, `formal/lean_checker.py`, `formal/smt_bridge.py`, `formal/translation_review.py`, `formal/proof_obligations.py`, `falsifier/search.py`, `falsifier/shrink.py`, `falsifier/metamorphic.py`, `verify/certificate.py`, `verify/evidence_status.py`, `lean/Nabla/Algebra/`, `lean/Nabla/Geometry/`, `schemas/evidence.schema.json`, `tests/formal/`.

**Portão:** certificados checados em executável oficial configurado por versão; demonstrações adversariais rejeitadas; nenhum `sorry`/`admit`/axioma oculto; equivalência entre formulação natural e formal revisada em amostras; estado 'formal' restrito ao enunciado provado.

### F4 — 2028–2030: geometria, diagramas, gráficos e imagens verificáveis

**Capacidades:** construir pontos, retas, cônicas, polígonos, transformações, cortes, interseções, diagramas analíticos, planos cartesianos, campos vetoriais, gráficos estatísticos, retratos de fase. Mesmo objeto geométrico alimenta predicados, prova, SVG e imagem raster. Imagens generativas são camada estética opcional, não prova geométrica.

**Pastas/arquivos:** `graphics/scene_graph.py`, `graphics/geometry_constraints.py`, `graphics/coordinate_system.py`, `graphics/plot.py`, `graphics/svg_renderer.py`, `graphics/raster_renderer.py`, `graphics/annotations.py`, `graphics/layout.py`, `forge/constructors/geometry.py`, `verify/geometry.py`, `templates/figures/`, `tests/graphics/`.

**Portão:** transformações preservam propriedades declaradas; erros geométricos testados; SVGs acessíveis e comparações visuais sem texto cortado; figuras rastreáveis até o modelo; nenhuma imagem conta como prova.

### F5 — 2029–2030: estúdio editorial científico e PDF profissional

**Capacidades:** criação de relatórios de cálculo, aulas, provas, livros, artigos, relatórios técnicos, posters, apresentações e documentação de datasets; equações numeradas, bibliografia, citações, referências cruzadas, diagramas, tabelas, legendas, apêndices, arquivos fonte e PDFs compilados localmente. Imagens renderizadas em resolução adequada, exportação sem depender de serviços online.

**Pastas/arquivos:** `documents/document_model.py`, `documents/equation_blocks.py`, `documents/citations.py`, `documents/figures.py`, `documents/latex_exporter.py`, `documents/typst_exporter.py`, `documents/pdf_builder.py`, `documents/html_exporter.py`, `documents/accessibility.py`, `templates/research_paper/`, `templates/engineering_report/`, `templates/textbook/`, `templates/poster/`, `tests/documents/`.

**Portão:** compilação TeX/Typst em ambientes suportados; PDF bem diagramado (margens, fórmulas, fontes, índices e figuras); conformidade documental verificável quando solicitada; fontes de números e alegações rastreáveis; relatórios sintéticos rotulados.

### F6 — 2029–2031: Nabla Dataset v1 e publicação científica

**Capacidades:** um objeto gera diferentes vistas sincronizadas: JSON/JSONL, Arrow/Parquet, CSV, LaTeX, Typst, PDF, SVG, PNG, Lean e, conforme domínio, formatos científicos especializados. Data cards, manifests, licenças, identidade de família, lineage, deduplicação semântica, contaminação e splits por geradores/teoremas/base de conhecimento. Publicação aprovada para GitHub, Hugging Face, Zenodo ou armazenamento selecionado, sem automatismo oculto.

**Pastas/arquivos:** `datasets/schema.py`, `datasets/serializer.py`, `datasets/semantic_fingerprint.py`, `datasets/split_policy.py`, `datasets/curation.py`, `datasets/quality_gate.py`, `datasets/model_card.py`, `datasets/license_review.py`, `export/parquet.py`, `export/jsonl.py`, `export/bundle.py`, `export/huggingface.py`, `export/zenodo.py`, `schemas/scientific_artifact.schema.json`, `schemas/dataset_manifest.schema.json`, `tests/datasets/`.

**Portão:** reimportação idêntica no contrato científico, schema validado, nenhuma informação privada sem autorização, datasets com baselines/difficulty distribution/holdouts; testes de melhoria de desempenho em modelos independentes, incluindo caso nulo.

### F7 — 2030–2033: modelagem de mundos e simulação científica validada

**Capacidades:** EDOs, EDPs selecionadas, dinâmica de corpos, mecânica, fluidos em regimes delimitados, termodinâmica, fenômenos eletromagnéticos, transporte, caos, controle e estatística de experimentos. Formulação simbólica → discretização → condições de contorno → solver → análise de estabilidade/convergência → visualização 2D/3D/animação → relatório de erro. Múltiplas estratégias numéricas (adaptativo, simplético quando apropriado, intervalar em casos suportados). GPU opcional para volumes maiores.

**Pastas/arquivos:** `worlds/model_spec.py`, `worlds/ode/`, `worlds/pde/`, `worlds/mesh/`, `worlds/integrators/`, `worlds/boundary_conditions.py`, `worlds/conservation.py`, `worlds/convergence.py`, `worlds/validation.py`, `worlds/sensitivity.py`, `worlds/visualize.py`, `worlds/animation.py`, `adapters/scipy_backend.py`, `adapters/jax_backend.py`, `adapters/fenics_backend.py` (somente após avaliação), `tests/worlds/`.

**Portão:** comparação com soluções conhecidas, convergência de malha/passo, unidades consistentes, limite do regime físico declarado e, onde alegar fidelidade ao mundo, validação experimental independente. **RK4 não é exato e não conserva invariantes arbitrariamente.**

### F8 — 2032–2035: laboratórios multimodais e treino de modelos de raciocínio

**Capacidades:** tarefas de imagem→geometria, PDF→estrutura, código→comportamento, simulação→estimativa, enunciado→formalização, texto→equação→gráfico, vídeo→estado e vice-versa. Modelos locais opcionais propõem soluções sem autoridade final; tool-use com oráculos. Treinar/adaptar modelos pequenos, comparar com baselines, curriculum, curriculum adversarial, OOD e generalização cruzada entre representações.

**Pastas/arquivos:** `agents/tool_registry.py`, `agents/planner.py`, `agents/proposals.py`, `agents/permissions.py`, `datasets/multimodal.py`, `datasets/alignments.py`, `training/curriculum.py`, `training/evaluation.py`, `training/contamination.py`, `training/ablation.py`, `adapters/local_llm.py`, `benchmarks/multimodal/`, `tests/agents/`.

**Portão:** métricas de transferência para tarefas inéditas, não apenas memorização; custo do treino relatado; testes de falsa confiança e de alucinação; vedação de dados sensíveis. Ganho em treinamento não é presumido.

### F9 — 2033–2037: descoberta, conjecturas e ciência assistida

**Capacidades:** minerar conjecturas, fazer regressão simbólica, comparar modelos com parcimônia, programar experimentos, buscar refutações e explicações, propor condições mais fortes ou fracas, produzir manuscritos com estado de evidência explícito. Integrar dados experimentais com protocolos de origem e intervalos de incerteza. Grafo de hipóteses, provas, retractions e replicações.

**Pastas/arquivos:** `discovery/hypothesis.py`, `discovery/symbolic_regression.py`, `discovery/experimental_design.py`, `discovery/theorem_search.py`, `discovery/novelty_screen.py`, `discovery/causal_models.py` (domínios delimitados), `knowledge/claim_graph.py`, `knowledge/literature.py`, `knowledge/retractions.py`, `falsifier/counterexample_miner.py`, `benchmarks/discovery/`, `tests/discovery/`.

**Portão:** encontrar resultados verificáveis em benchmarks ocultos; comparação bibliográfica para afirmações de novidade; reprodução independente; nenhum artigo sintético afirma experimento real inexistente.

### F10 — 2037–2042: RSI — melhoria recursiva científica controlada

**Capacidades:** detectar gargalos do próprio pipeline; propor genomas de parâmetros, estratégias de busca, regras de simplificação e arquiteturas de solver; experimentar em ambiente isolado; comparar com baseline congelado; reverter regressões; submeter revisões humanas antes de alterar verificadores e regras de segurança. Extensão gradual de mudança de parâmetros para módulos gerados verificáveis, com isolamento e revisão técnica.

**Pastas/arquivos:** `evolution/policy_genome.py`, `evolution/search.py`, `evolution/proposal_validator.py`, `evolution/evaluator.py`, `evolution/holdout_manager.py`, `evolution/statistical_tests.py`, `evolution/lineage.py`, `evolution/rollback.py`, `evolution/release_gate.py`, `runtime/sandbox.py`, `runtime/resource_budget.py`, `benchmarks/rsi/`, `tests/evolution/`.

**Portão:** ganho estatisticamente defensável em teste inacessível ao proponente; comparação com linha de base original; auditoria de deriva; provas de preservação de contratos onde cabível; rollback documentado; verificador protegido de autossubstituição silenciosa. RSI não equivale a inteligência geral.

### F11 — 2042–2048: expansão para engenharia, química, materiais e instrumentação

**Capacidades condicionais:** circuitos, CAD paramétrico, eletrônica, materiais, química computacional, planejamento experimental, controle e instrumentação, biossistemas em limites seguros; escalas molecular/contínua conectadas quando métodos compatíveis. Problemas inversos físicos, busca por formulações, simulações multiparadigma e projeto assistido. Integrações de laboratório só com autorização, monitoramento e especialistas.

**Pastas/arquivos:** `domains/engineering/`, `domains/circuits/`, `domains/materials/`, `domains/chemistry/`, `domains/control/`, `domains/earth/`, `domains/biology/`, `adapters/instruments/`, `worlds/multiphysics/`, `knowledge/domain_ontologies/`, `schemas/experimental_observation.schema.json`, `tests/domains/`, `benchmarks/scientific_domains/`.

**Portão:** validação por especialistas e dados reais por domínio; limitações físico-químicas e erros explicitados; conformidade regulatória quando aplicável; nenhuma alegação industrial sem testes relevantes.

### F12 — 2048–2056+: biblioteca viva de conhecimento e pesquisa institucional

**Capacidades condicionais:** uma rede de bibliotecas e bases científicas interoperáveis, provas, modelos, dados, documentos, revisões, reproduções e retratações; assistentes que atravessam disciplinas conservando premissas; sistemas de planejamento de pesquisa assistida; indexação de representações formais e informais, colaboração entre laboratórios. Execução distribuída pode ser plug-in opcional, não dependência do software pessoal.

**Pastas/arquivos:** `knowledge/federation.py`, `knowledge/semantic_reconciliation.py`, `knowledge/versioned_claims.py`, `knowledge/dependency_impact.py`, `knowledge/peer_review.py`, `knowledge/provenance_audit.py`, `discovery/research_program.py`, `agents/scientific_teams.py`, `adapters/federation/`, `schemas/claim_version.schema.json`, `schemas/retraction.schema.json`, `docs/governance/`, `benchmarks/cross_domain/`.

**Portão:** interoperabilidade com entidades reais; governança de revisões, conflitos e retratações; participação humana; demonstração pública de utilidade, não marketing de 'verdade universal'.

### F13 — além de 2056: horizonte aberto

**Hipóteses (não promessas):** sistemas com melhores capacidades de abstração, descoberta de algoritmos, desenho de experimentos, modelos multimodais causalmente mais úteis, certificados auditáveis em hardware heterogêneo, modelos científicos composicionais e IA que participe de programas de pesquisa sob supervisão apropriada. A nomenclatura exata dos módulos ainda seria especulativa; a prioridade é manter contratos de evidência, extensibilidade, governança e capacidade de substituir motores sem perder registros históricos.

## 5. Matriz de áreas científicas e geração inversa

| Domínio | Construção inversa | Solução/verificador | Condição crítica |
| --- | --- | --- | --- |
| Aritmética/álgebra | escolhe fatores, raízes, bases e produtos | expansão, divisão, CAS independente | domínios e singularidades |
| Integração | escolhe primitiva e deriva | regra simbólica e derivada independente | constantes, ramos, domínio |
| Álgebra linear | escolhe decomposição/matriz espectral | multiplicação, resíduos, certificados numéricos | condicionamento |
| Otimização convexa | escolhe ótimo/dual e constrói problema | KKT/dualidade, solver externo | convexidade, regularidade |
| Lógica/SMT | escolhe modelo ou prova | solver e verificador de teoria | encoding fiel e decidibilidade |
| Geometria | constrói configuração e dependências | motor dedutivo/Lean em subconjuntos | degenerescência e figura ilustrativa |
| Combinatória | constrói grafos/invariantes/extremos | enumeradores/certificados | explosão combinatória |
| Probabilidade/Markov | escolhe matriz/estado estacionário | transições e identidades racionais | ergodicidade e periodicidade |
| EDOs | escolhe solução, deriva equação | substituição + teste numérico | condições iniciais e singularidades |
| EDPs | escolhe solução/manufatured solution | resíduo e condições de contorno | estabilidade/convergência |
| Física/simulação | escolhe condições iniciais/modelo | solver e métricas de erro | fidelidade do modelo à realidade |
| Código e algoritmos | escolhe contrato/invariante/procedimento | tests, model checking e prova parcial | equivalência implementação-especificação |
| Visão técnica | escolhe cena/objetos e renderiza | geometria/projeção/ground truth | oclusão, ruído, variação real |
| Documentos | escolhe documento estruturado e renderiza | comparação semântica/layout | não produzir ciência fictícia como real |

A expansão horizontal só deve ocorrer quando o domínio anterior demonstrar estabilidade, diversidade útil e ganho de desempenho ou utilidade em benchmark externo.

## 6. Tipos de dados e produtos exportáveis

- **Matemática e lógica:** AST/IR canônica, MathML, Lean, SMT-LIB, LaTeX de equação, resultados exatos/intervalares.
- **ML e datasets:** JSONL, CSV, Parquet, Arrow, split manifests, dataset cards, licenses, train/validation/test; formatos de modelos apenas quando houver treino real.
- **Visual e apresentação:** SVG, PNG, PDF vetorial, HTML interativo, gráficos auditáveis, imagens técnicas, diagramas, tabelas, cenas 2D/3D.
- **Documentos:** fonte `.tex`, `.typ`, Markdown, HTML, PDF compilado, bibliografia, anexos e pacotes reprodutíveis; exportações PDF/A quando testes e ferramentas permitirem.
- **Simulação:** dados tabulares/temporais, HDF5/Zarr/NetCDF conforme domínio, VTK para campos/malhas, glTF para cenas 3D quando útil, animações e relatórios de verificação.
- **Compartilhamento:** bundle de experimento com manifesto, checksum, fonte, logs, ambiente, certificado, licensing e status de revisão.

Um artefato tem representações múltiplas, mas elas não recebem automaticamente o mesmo grau de certeza. Exemplo: prova exata para uma equação não comprova que a equação modela corretamente um experimento físico.

## 7. Qualidade do dataset: como evitar milhões de problemas inúteis

Pipeline proposto: (1) enumerar famílias de tarefas; (2) construir instância via gerador versionado; (3) garantir premissas e semântica; (4) verificar o testemunho independentemente; (5) procurar variantes degeneradas/atalhos; (6) medir dificuldade contra vários solvers com recursos calibrados; (7) deduplicar estrutural e semanticamente; (8) impor diversidade e currículo; (9) separar famílias e origens entre splits; (10) comparar treino com e sem os dados; (11) documentar resultados positivos e negativos; (12) revisão humana antes da publicação.

Métricas: taxa de validade; taxa de formalização; diversidade de famílias e estruturas; dificuldade condicional a solver e hardware; fração de problemas resolvidos por baselines; custo por item **útil**; contaminação/near-duplicate; ganho em testes inéditos; robustez a mudança de representação; qualidade de calibração e taxas de falha. Não existe 'score único da verdade'.

## 8. RSI: a arquitetura de controle

`Proponent -> TypedProposal -> StaticChecks -> FrozenEvaluator -> HiddenHoldout -> StatisticalDecision -> HumanApproval -> VersionedRelease -> Monitoring -> Rollback`.

Avaliar sempre melhoria sobre linha de base original, custo e piora em tarefas antigas. O avaliador congelado não pode ser alterado pelo proponente. Autorizar edições de código somente em ambientes isolados e conforme uma política de permissão explícita. `nabla_improve.py` é um antecedente de RSI contido para ajuste de curvas, não RSI generalista; seu legado deve ser reaproveitado por partes após auditoria.

## 9. Perfis de hardware e execução

- CPU doméstica, 16–32 GB RAM, sem GPU: cálculo exato, problemas de polinômios, alguns SMT/Lean, gráficos vetoriais, documentos, datasets de escala controlada, pequenas simulações.
- CPU moderna + GPU de 8–16 GB: aceleração de trabalhos numéricos compatíveis, render e modelos locais quantizados de porte limitado; compatibilidade/VRAM/contexto devem ser medidos, não presumidos.
- Estação avançada, 64–128 GB RAM, GPU mais forte: lotes maiores, simulações de malhas e modelos mais exigentes; ainda limitada por memória, energia, precisão e velocidade.
- HPC/nuvem por opção: EDPs e treino muito grandes, multimodalidade de alta resolução, pesquisas que realmente requerem escala; não dependência do usuário comum.

Profiles: `configs/profiles/cpu_conservative.yaml`, `cpu_balanced.yaml`, `gpu_local.yaml`, `research_station.yaml`. Aplicar limite de aquecimento, prioridades de processo, pausa, retomada, checkpoint, armazenamento, uso elétrico e consentimento. Não é permitido afirmar que um PC substitui um cluster universalmente.

## 10. Produto e fluxos de usuário (comandos conceituais, ainda não implementados)

- `nabla calc` — cálculo, álgebra, variáveis, domínio, sessões;
- `nabla prove` — formalização e certificado condicionado;
- `nabla forge` — construção inversa com orçamento, tarefa, seed, dificuldade e separações;
- `nabla validate` — revisita registros, faz testes e rejeita corrupção;
- `nabla plot` — imagem gerada dos mesmos dados;
- `nabla studio` — documento profissional editável/compilável e suas fontes;
- `nabla simulate` — roda mundo-modelo com precisão/tolerância declarada;
- `nabla discover` — hipóteses e contraexemplos sob orçamento;
- `nabla evolve` — RSI contido, avaliações congeladas e rollback;
- `nabla publish` — revisão de direitos, licenças e aprovação humana antes de exportar.

Os nomes acima são **interfaces propostas** e não evidência de que qualquer comando existe hoje.

## 11. Exemplo de experiência integrada: um único experimento em oito formatos

Pedido: 'Construa um problema de órbita elíptica delimitado, gere a solução e um desafio reverso, confira o movimento e publique um relatório.'

1. `core`: representa massas, constantes, unidades e hipóteses (problema ideal de dois corpos).
2. `forge`: escolhe parâmetros físicos válidos e constrói condições iniciais correspondentes.
3. `calc`: produz expressões e quantidades físicas.
4. `worlds`: integra órbita numericamente e mede convergência e conservação com tolerâncias.
5. `falsifier`: testa excentricidades extremas, singularidades e passo temporal.
6. `graphics`: desenha trajetória SVG, velocidade e energia versus tempo.
7. `documents`: gera figura e papel LaTeX/Typst, compila PDF, inclui limites.
8. `datasets`: exporta item com problema, solução, texto, PDF, SVG, séries temporais, verificadores, hashes e licença.

Observação: esse item prova propriedades do **modelo idealizado**, não precisão para uma órbita real perturbada sem validação externa.

## 12. Critérios de governança a partir do início

- Licenças por arquivo/dataset; transparência de corpus e fonte.
- Direito a privacidade e revisão antes de qualquer upload.
- Citações e antecedentes para alegar descoberta inédita; reconhecimento/retratação.
- Testes de safety, sandbox e reprodutibilidade; secretos de APIs nunca em datasets.
- Comunidade como possível evolução, mas rede planetária, créditos e token não integram caminho crítico do produto local-first.
- Promessas científicas lastreadas em evidência pública; métricas de aprendizado importam mais que contagem de arquivos/datasets.

## 13. Próxima ordem de execução após aprovação deste documento

1. Auditar o `HEAD` real com checkout, dependências e testes.
2. Corrigir inconsistências de importação/assinatura no módulo simbólico e estabilizar CI.
3. Congelar o contrato `ScientificArtifact` e validar retrocompatibilidade SQLite/JSONL.
4. Integrar o pequeno gerador inverso já entregue ao AST canônico, sem duplicar a matemática.
5. Implementar verificadores independentes, domain-gates e benchmarks adversariais.
6. Entregar primeiro loop completo: **cálculo → geração inversa → solução independente → verificação → exportação `.tex`/`.typ`/PDF e `.jsonl`**.
7. Testar com utilizadores reais, colher defeitos, melhorar UX, só depois ampliar domínios.

**Este documento não implementa as fases descritas.** Todos os arquivos citados são propostas ou caminhos a auditar, salvo quando explicitamente apontados como preexistentes no material.
