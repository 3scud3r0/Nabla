# vision1 — Plano executável para o Nabla 1.0

Este documento define um **perfil proposto de versão 1.0 local e delimitada** e
lista individualmente os arquivos que precisam participar de sua implementação,
revisão, teste ou distribuição. Ele não declara a versão pronta nem substitui a
visão científica de longo prazo do `vision.md`.

## O que significa atingir 1.0

Entregar um laboratório local em CPU, instalável e utilizável por CLI/desktop,
com operações matemáticas explicitamente suportadas, hipóteses e erros claros,
notebooks reexecutáveis, armazenamento/backup, artefatos e exportação verificáveis.
O conjunto público de APIs, formatos e plataformas deve ser congelado para 1.0.

GPU, pesquisa autônoma geral, ganhos de aprendizado não demonstrados, federação
pública resistente a Sybil e execução de código hostil não são promessas desta
1.0. SDKs e backends opcionais só entram como estáveis no subconjunto realmente
validado. A documentação precisa declarar todo o restante como experimental ou
indisponível, sem mascarar falhas conhecidas.

**A lista é fechada para este perfil de planejamento.** Novas falhas durante os
ensaios podem exigir correções ou arquivos auxiliares; nenhum inventário antecipa
com certeza todos os defeitos. Reutilizar módulos existentes é a regra: não criar
arquivos vazios ou implementações paralelas para preencher esta lista.

## Estimativa e estado observado

- Maturidade de engenharia restante estimada: **cerca de 40%, faixa 30–50%**,
  para o perfil local proposto. Julgamento de planejamento, não tempo ou código.
- A rubrica detalhada é 59/100 disponíveis e 41/100 restantes em
  `docs/audits/RELEASE_1_0_AND_VISION_2026_10_16.md`.
- Evidência local recente: 2.269 testes e 316 subtestes passaram; 8 testes
  opcionais pulados. O corpus público Std passou em 30.000 teoremas.
- Wheel isolado e bundles foram verificados. O laboratório Mathlib falha por
  timeout e sua assurance depende dos artefatos científicos ausentes.
- A versão declarada ainda é **0.1.0a1**. CI remota e aceite de release da versão
  alterada não foram demonstrados.
- A visão completa conserva 213 requisitos parciais. Seu horizonte aberto não
  permite uma porcentagem total defensável.

## Como ler o plano por arquivo

“Existente” significa apenas presença no checkout. Não significa função completa,
segurança auditada ou aceite científico. “Proposto/ausente” é trabalho documental
ou de implementação ainda necessário; este plano não criou esses arquivos.
O conteúdo esperado descreve o papel final, e o aceite explica como verificá-lo.
Não se exige reescrever um componente cujo contrato já passe nos gates pertinentes.


## 01 — Produto, versão e contratos públicos

| Arquivo | Situação atual | O que deve conter | Aceite para 1.0 |
|---|---|---|---|
| `vision1.md` | existente | Plano da versão 1.0, escopo fechado, arquivos e gates de entrega. | Revisar e aprovar escopo e responsáveis; manter coerência com a documentação publicada. |
| `pyproject.toml` | existente | Versão, metadados, entrypoints e extras do pacote Python. | Mudar para 1.0 somente após os gates; build isolado, dependências e SBOM coerentes. |
| `src/nablamath/__init__.py` | existente | Versão pública e superfície de importação do pacote. | Versão alinhada ao wheel e política de importação compatível. |
| `src/nablamath/compatibility.json` | existente | Faixa suportada de Python, SO e integrações. | Coincidir com a matriz realmente executada para o commit do release. |
| `src/nablamath/compatibility.py` | existente | Diagnóstico de compatibilidade e integrações opcionais. | Distinguir disponível, indisponível, incompatível e não verificado. |
| `README.md` | existente | Instalação, primeiros usos, escopo e limitações da 1.0. | Receita reproduzida em ambiente limpo; sem números históricos apresentados como atuais. |
| `docs/COMPATIBILITY.md` | existente | Matriz de plataformas, versões e evidências CI. | Links dos jobs do commit exato; backends opcionais separados. |
| `docs/API_STABILITY.md` | existente | Política proposta de estabilidade de APIs, formatos, erros e depreciações. | Publicar o conjunto estável e política de quebra/migração; reaproveitar contratos existentes. |
| `CHANGELOG.md` | existente | Notas propostas de release: funcionalidades, correções, migração e limitações. | Descrever diferenças reais, incompatibilidades e problemas conhecidos da 1.0. |
| `SECURITY.md` | existente | Política de reporte e limites operacionais de segurança. | Revisão do escopo local, dependências, ameaças e caminho de reporte. |
| `LICENSE` | existente | Licença do código distribuído. | Preservar avisos e identificar licenças dos componentes/artefatos de terceiros. |

## 02 — Núcleo semântico e precisão

| Arquivo | Situação atual | O que deve conter | Aceite para 1.0 |
|---|---|---|---|
| `src/nablamath/expression.py` | existente | Parser e AST restritos para expressões matemáticas. | Recusar sintaxe não suportada; preservar hipóteses e limites de custo. |
| `src/nablamath/core/semantic_ir.py` | existente | Representação canônica de pedidos/valores e IDs semânticos. | Roundtrip e hashes estáveis sob o contrato versionado. |
| `src/nablamath/core/semantic_contracts.py` | existente | JSON canônico, validação de campos, limites e contratos compartilhados. | Rejeitar dados ambíguos, não finitos, excessivos ou incompatíveis. |
| `src/nablamath/core/types.py` | existente | Tipos científicos e compatibilidade entre operações. | Distinguir escalares/vetores/matrizes e domínios sem conversões silenciosas. |
| `src/nablamath/core/units.py` | existente | Unidades, dimensões e quantidades. | Propagação dimensional e rejeição de combinações incompatíveis. |
| `src/nablamath/core/precision.py` | existente | Política de precisão e apresentação de aproximações. | Precisão solicitada satisfeita ou falha explícita, sem confundir aproximação com exatidão. |
| `src/nablamath/core/obligations.py` | existente | Obrigações de domínio independentes da simplificação. | Preservar polos removíveis, restrições de denominadores e potências. |
| `src/nablamath/core/uncertainty.py` | existente | Incerteza e propagação rastreável. | Explicitar pressupostos, dependências e diferença entre erro estimado e limite rigoroso. |
| `src/nablamath/core/migration_registry.py` | existente | Migrações explícitas de formatos e versões. | Fixtures antigas migradas ou recusadas com mensagem clara; sem downgrade silencioso. |
| `src/nablamath/core/scientific_artifact.py` | existente | Grafo de artefatos científicos e vínculos por conteúdo. | Rejeitar pais ausentes, adulterações, nós órfãos e conteúdo fora do perfil. |
| `src/nablamath/core/capabilities.py` | existente | Capacidades declaradas e consultas de suporte. | Contrato corresponder ao que é executável; recusas honestas. |
| `src/nablamath/core/resource_profiles.py` | existente | Orçamentos e perfis de execução. | Tempo, memória, volume e cancelamento definidos para as operações do release. |
| `src/nablamath/schema/expression.py` | existente | Serialização versionada da AST. | Leitura/validação de fixtures normativas e rejeição de estruturas inválidas. |
| `src/nablamath/schema/units.py` | existente | Serialização e validação de unidades. | Preservar significado dimensional no roundtrip e no replay. |

## 03 — Calculadora, matemática e certificados numéricos

| Arquivo | Situação atual | O que deve conter | Aceite para 1.0 |
|---|---|---|---|
| `src/nablamath/calc/catalog.py` | existente | Catálogo público de operações com argumentos e domínios. | Congelar schemas, limites e erros de todas as operações declaradas estáveis. |
| `src/nablamath/calc/session.py` | existente | Sessões, bindings, execução e recibos. | Replay determinístico dos contratos exatos e tolerâncias explícitas dos aproximados. |
| `src/nablamath/calc/notebook.py` | existente | Notebooks, cadeia de células e reexecução. | Compatibilidade de formatos, adulterações detectadas e migração documentada. |
| `src/nablamath/symbolic/differentiate.py` | existente | Diferenciação simbólica no fragmento declarado. | Hipóteses preservadas e comparação independente por classe de expressão. |
| `src/nablamath/symbolic/integrate.py` | existente | Primitivas no fragmento declarado. | Certificados por diferenciação e recusas fora do domínio. |
| `src/nablamath/symbolic/egraph.py` | existente | Simplificação por e-graph sob orçamento. | Preservar domínios e informar saturação incompleta/limite de recursos. |
| `src/nablamath/math/calculus/polynomial.py` | existente | API pública de cálculo polinomial. | Consistência entre derivadas, integrais, limites e séries suportados. |
| `src/nablamath/math/calculus/rational_functions.py` | existente | Normalização de funções racionais e comparação de domínios. | Identidade algébrica separada da equivalência dos domínios originais. |
| `src/nablamath/math/calculus/limits.py` | existente | Limites laterais e no infinito para racionais. | Sinais, inexistência bilateral, domínio e replay conferidos. |
| `src/nablamath/math/calculus/risch.py` | existente | Integração racional delimitada e certificados de derivada. | Publicar fragmento realmente suportado; não declarar Risch geral implementado. |
| `src/nablamath/math/analysis/intervals.py` | existente | Intervalos racionais e enclosures polinomiais de Bernstein. | Revisar majorantes, custo e compatibilidade com os intervalos numéricos existentes. |
| `src/nablamath/math/analysis/quadrature.py` | existente | Quadratura polinomial com resto certificado. | Intervalo conter a integral; orçamento insuficiente produzir falha, não sucesso parcial. |
| `src/nablamath/math/analysis/certified_functions.py` | existente | Enclosures delimitados de exp/log/sin/cos. | Domínios e restos revisados; certificados Python identificados como não Lean. |
| `src/nablamath/numeric/intervals.py` | existente | Operações intervalares do backend numérico existente. | Definir interoperabilidade e arredondamento sem semânticas concorrentes. |
| `src/nablamath/math/linear_algebra/matrices.py` | existente | Matrizes e operações racionais básicas. | Dimensões, singularidade e invariantes conferidos. |
| `src/nablamath/math/linear_algebra/solvers.py` | existente | Sistemas, decomposições e condicionamento do perfil público. | Resíduos/reconstrução e distinção entre solução única, infinita e inconsistente. |
| `src/nablamath/math/probability/absorption.py` | existente | Primeira entrada, estacionariedade e recompensas em Markov. | Momentos condicionais/incondicionais separados; resíduos exatos e periodicidade explícita. |
| `src/nablamath/math/statistics/multivariate.py` | existente | Mínimos quadrados multivariados e hipóteses. | Referência NIST, rank, pesos e graus de liberdade verificados. |
| `docs/acceptance/scientific_capabilities.yaml` | existente | Domínios, operações, tolerâncias e recusas científicas. | Refletir o catálogo suportado; não promover aceitação sem evidência. |
| `docs/CERTIFIED_MATHEMATICS.md` | existente | Contratos de análise certificada e cadeias finitas. | Exemplos reproduzidos e fronteiras das garantias explícitas. |

## 04 — Provas, formalização e refutação

| Arquivo | Situação atual | O que deve conter | Aceite para 1.0 |
|---|---|---|---|
| `src/nablamath/formal/statement.py` | existente | Proposições tipadas, relações e obrigações de domínio. | Hipóteses explícitas e serialização sem perda de significado. |
| `src/nablamath/formal/lean_std.py` | existente | Provas Std por AST, lemas auxiliares e auditoria do kernel. | Toolchain fixada, ausência de admissions e rejeição de certificados adulterados. |
| `src/nablamath/formal/lean_bridge.py` | existente | Tradução tipada para o backend Mathlib existente. | Fonte regenerável e coerência estrutural com o enunciado. |
| `src/nablamath/formal/lean_checker.py` | existente | Execução Lean/Mathlib com timeout e auditoria de axiomas. | Resolver o timeout atual e preservar diagnóstico de pré-requisito/erro real. |
| `src/nablamath/formal/translation_review.py` | existente | Vínculo entre pergunta, enunciado, domínio e revisão. | Revisão humana do significado; identidade declarada não é autenticação independente. |
| `src/nablamath/formal/smt_bridge.py` | existente | Consultas SMT do fragmento suportado. | Contraexemplo reexecutado exatamente; status SMT separado de prova pelo kernel Lean. |
| `src/nablamath/falsifier/search.py` | existente | Busca de refutações nos domínios declarados. | Distinguir contraexemplo encontrado de busca inconclusiva. |
| `src/nablamath/falsifier/shrink.py` | existente | Redução de contraexemplos com verificação. | Caso reduzido ainda refutar o enunciado original sob as hipóteses. |
| `src/nablamath/verify/certificate.py` | existente | Construção e revalidação de certificados. | Reexecutar o backend e vincular fonte, versão, hipóteses e resultado. |
| `lean/lean-toolchain` | existente | Versão exata do compilador. | Fixação consistente com instaladores e CI. |
| `lean/lakefile.toml` | existente | Bibliotecas e dependências formais declaradas. | Build dos alvos do release sem mudar semântica ou dependências silenciosamente. |
| `lean/lake-manifest.json` | existente | Commits exatos das dependências Lean/Mathlib. | Instalação congelada e reproduzível; não usar atualização livre para esconder falhas. |
| `scripts/setup_formal.sh` | existente | Preparação completa do perfil Mathlib. | Checksum e build concluídos no orçamento suportado. |
| `scripts/setup_lean_std.sh` | existente | Preparação independente do perfil Std. | Repetibilidade com checksum e sem reinstalação concorrente durante execução. |
| `tools/rational_proof_corpus.py` | existente | Geração e compilação/auditoria das 60 unidades do corpus público. | 30.000 nomes esperados verificados; falhas/timeouts preservados. |
| `lean/Conformance/manifest.json` | existente | Protocolo e hashes dos 30.000 teoremas. | Corresponder às fontes emitidas e à evidência do kernel. |
| `docs/LEAN_STD.md` | existente | Instalação, tradução e limites do backend Std. | Distinguir teorema condicionado, hipóteses satisfatíveis e evidência científica. |

## 05 — Artefatos, dados e exportação

| Arquivo | Situação atual | O que deve conter | Aceite para 1.0 |
|---|---|---|---|
| `src/nablamath/forge/task_spec.py` | existente | Schema de tarefas sintéticas e hipóteses. | Versão, origem, semente e domínio definidos. |
| `src/nablamath/forge/reverse_builder.py` | existente | Construção inversa dos problemas do perfil. | Problema resolvido/verificado sem depender do testemunho do construtor. |
| `src/nablamath/verify/trace.py` | existente | Trace e conferência das etapas de solução. | Rejeitar vínculos e passos adulterados. |
| `src/nablamath/pipeline/scientific_cycle.py` | existente | Ciclo público completo de artefato científico. | Reexecução e detecção de adulteração de cada ligação. |
| `src/nablamath/pipeline/artifact_store.py` | existente | Publicação local atômica de artefatos aceitos. | Nenhum destino aceito parcialmente em caso de falha. |
| `src/nablamath/pipeline/provenance.py` | existente | Linhas de origem e dependência. | Identificar fontes e separar declaração de procedência de autenticação. |
| `src/nablamath/datasets/schema.py` | existente | Schema dos registros do perfil estável. | Versões, campos e migrações congelados. |
| `src/nablamath/datasets/serializer.py` | existente | Serialização limitada e verificável. | Leitura/escrita com limites, erros e hashes coerentes. |
| `src/nablamath/datasets/semantic_fingerprint.py` | existente | Identidade semântica para deduplicação. | Casos equivalentes conhecidos e limitações documentados. |
| `src/nablamath/datasets/split_policy.py` | existente | Separação de treino/validação/teste. | Não usar avaliação reservada para selecionar geração ou parâmetros. |
| `src/nablamath/datasets/curation.py` | existente | Curadoria com origem, licença e decisões rastreáveis. | Rejeitar conteúdo sem requisitos de redistribuição satisfeitos. |
| `src/nablamath/datasets/quality_gate.py` | existente | Gates de qualidade antes de exportar/publicar. | Casos negativos e adulterações não produzirem artefato aceito. |
| `src/nablamath/datasets/model_card.py` | existente | Ficha de dados e limitações. | Descrever origem, finalidade, partições e limites reais. |
| `src/nablamath/export/jsonl.py` | existente | Exportação JSONL do perfil. | Roundtrip, limites e falha atômica. |
| `src/nablamath/export/parquet.py` | existente | Exportação Parquet opcional. | Mesmo significado dos registros e recusa clara sem dependência instalada. |
| `src/nablamath/export/bundle.py` | existente | Bundle com conteúdo, manifesto e verificadores. | Importação revalidada e proteção contra adulteração. |
| `src/nablamath/export/huggingface.py` | existente | Integração opcional de publicação. | Destino/licença/consentimento explícitos; valores secretos não persistidos indevidamente. |

## 06 — Persistência, CLI, desktop e operação segura

| Arquivo | Situação atual | O que deve conter | Aceite para 1.0 |
|---|---|---|---|
| `src/nablamath/cli.py` | existente | Comandos públicos, validação e status de saída. | Fluxo principal reproduzível e erros estáveis para automação. |
| `src/nablamath/storage.py` | existente | Compatibilidade de armazenamento e importação existentes. | Preservar registros anteriores ou fornecer migração explícita. |
| `src/nablamath/store/migrations/__init__.py` | existente | Migrações transacionais da base. | Upgrade de todas as versões declaradas suportadas e recusa de banco inválido. |
| `src/nablamath/store/backup.py` | existente | Backup e restauração com integridade. | Restauração exercitada com fixtures de versões anteriores. |
| `src/nablamath/desktop/app.py` | existente | Servidor local, autenticação de sessão e fluxos públicos. | Cálculo, histórico, exportação, erros e consentimento testados por HTTP. |
| `src/nablamath/desktop/index.html` | existente | Interface local, estados de execução e avisos de domínio. | Revisão de usabilidade/acessibilidade e prevenção de alegações científicas indevidas. |
| `src/nablamath/desktop/launcher.py` | existente | Inicialização e ciclo de vida do aplicativo. | Instalação/inicialização/encerramento nos SOs suportados. |
| `src/nablamath/desktop/workflows.py` | existente | Fluxos integrados do desktop. | Histórico, artefatos e consentimento coerentes com o backend. |
| `src/nablamath/agents/sandbox.py` | existente | Recusa de código arbitrário no perfil local. | Preservar recusa até existir sandbox real validado; não substituir por eval/subprocess irrestrito. |
| `src/nablamath/agents/permissions.py` | existente | Permissões explícitas de ferramentas confiáveis. | Sem escalada implícita de autoridade ou acesso. |
| `src/nablamath/agents/tool_registry.py` | existente | Registro de ferramentas locais permitidas. | Schemas, limites, efeitos e versões declarados. |
| `configs/profiles/cpu_conservative.yaml` | existente | Perfil de recursos de CPU acessível. | Limites medidos, cancelamento e mensagens de orçamento documentados. |
| `configs/profiles/cpu_balanced.yaml` | existente | Perfil de CPU intermediário. | Mesmo contrato científico e diferenças de recurso declaradas. |

## 07 — Distribuição e superfície opcional dos SDKs

| Arquivo | Situação atual | O que deve conter | Aceite para 1.0 |
|---|---|---|---|
| `packaging/offline_release.py` | existente | Preparação de distribuição e dependências offline do perfil. | Instalação sem downloads inesperados e integridade do conjunto. |
| `packaging/staged_release.py` | existente | Gates e promoção de release com evidência preservada. | Não promover release com gate obrigatório falho. |
| `packaging/signed_release.py` | existente | Assinatura e proveniência dos artefatos. | Autoridade real configurada e verificação pelo destinatário; não inventar assinatura. |
| `packaging/windows/nablamath.iss` | existente | Instalador Windows da versão exata. | Instalar/atualizar/desinstalar em máquina limpa e preservar dados pessoais. |
| `setup.sh` | existente | Receita suportada de instalação Linux/macOS quando declarada. | Não prometer suporte a SO não exercitado. |
| `setup.ps1` | existente | Receita PowerShell. | Dependências e erros diagnósticos coerentes com o instalador. |
| `setup.cmd` | existente | Entrada Windows para preparação. | Delegação previsível e propagação do exit status. |
| `protocol/schema/nabla-object-v1.json` | existente | Schema público selecionado de objetos. | Fixtures normativas e migração de versão sem quebra silenciosa. |
| `protocol/schema/nabla-task-v1.json` | existente | Schema público selecionado de tarefas. | Validação equivalente entre implementações suportadas. |
| `protocol/schema/nabla-receipt-v1.json` | existente | Schema público selecionado de recibos. | Hipóteses, status e versões preservados entre linguagens. |
| `sdk/python/client.py` | existente | Cliente Python dos endpoints que forem declarados estáveis. | Conformidade, erros e timeout; endpoints não congelados permanecem experimentais. |
| `sdk/typescript/client.ts` | existente | Cliente TypeScript do mesmo subconjunto. | Executar no runtime suportado e comparar fixtures comuns. |
| `sdk/rust/src/client.rs` | existente | Cliente Rust do subconjunto selecionado. | Execução real Rust; auditoria de API/ABI antes de alegar estabilidade. |
| `sdk/c/nabla_fraction.c` | existente | Semântica racional interoperável em C. | Golden vectors iguais aos demais bindings. |
| `sdk/c/nabla_fraction.h` | existente | Cabeçalho do contrato C selecionado. | Contrato de memória/erros e compatibilidade explícitos. |
| `sdk/cpp/nabla_fraction.hpp` | existente | Binding racional C++. | Mesmo contrato matemático e casos de erro. |

## 08 — Documentos e recursos visuais do perfil local

| Arquivo | Situação atual | O que deve conter | Aceite para 1.0 |
|---|---|---|---|
| `src/nablamath/documents/document_model.py` | existente | Modelo editorial estruturado. | Vínculos entre afirmações, equações, tabelas, figuras e evidências. |
| `src/nablamath/documents/html_exporter.py` | existente | Exportação HTML. | Escapamento, links e conteúdo coerentes com os artefatos originais. |
| `src/nablamath/documents/latex_exporter.py` | existente | Exportação LaTeX delimitada. | Conteúdo reproduzível e erros de backend explícitos. |
| `src/nablamath/documents/typst_exporter.py` | existente | Exportação Typst delimitada. | Semântica editorial coerente com HTML/LaTeX. |
| `src/nablamath/documents/pdf_builder.py` | existente | Compilação PDF opcional do perfil. | Compilação real e revisão visual separadas; ausência de compilador não vira sucesso. |
| `src/nablamath/graphics/scene_graph.py` | existente | Cenas científicas e metadados. | Figuras vinculadas ao cálculo e às suas unidades/hipóteses. |
| `src/nablamath/graphics/svg_renderer.py` | existente | Renderização SVG. | Determinismo, escaping e limites do formato. |
| `src/nablamath/graphics/raster_renderer.py` | existente | Renderização raster opcional. | Comparação com cena de origem e disponibilidade explícita do backend. |
| `docs/DESKTOP.md` | existente | Guia do aplicativo local. | Explicar armazenamento, ações, exportação, consentimento e limites. |

## 09 — Testes de aceite e CI do commit exato

| Arquivo | Situação atual | O que deve conter | Aceite para 1.0 |
|---|---|---|---|
| `tests/regression/test_public_api.py` | existente | Compatibilidade de API e formatos públicos. | Fixtures reais de versões anteriores e casos de quebra rejeitada. |
| `tests/regression/test_portable_io.py` | existente | Portabilidade de caminhos e bytes. | Resultados coerentes em Linux/Windows. |
| `tests/integration/test_cli_local.py` | existente | Fluxo CLI com dados e saídas reais. | Exit status e efeitos esperados, inclusive falhas. |
| `tests/integration/test_desktop.py` | existente | Fluxos HTTP do desktop. | Requisição funcional, persistência e proteção de sessão/origem. |
| `tests/integration/test_backup_restore.py` | existente | Ciclo de backup/restore. | Integridade e compatibilidade das versões suportadas. |
| `tests/integration/test_scientific_artifact.py` | existente | Ciclo do artefato e adulterações de vínculos. | Reexecução de todos os nós e recusa de conteúdo inconsistente. |
| `tests/integration/test_global_scientific_cycle.py` | existente | Integração de componentes públicos. | Perfil 1.0 executado sem simular aprovação de módulos indisponíveis. |
| `tests/security/test_agent_sandbox.py` | existente | Recusas e limites de ferramentas. | Não declarar resistência a escapes de sandbox inexistente. |
| `tests/security/test_supply_chain.py` | existente | Integridade da cadeia de distribuição. | Adulteração de fonte/artefato/dependência detectada. |
| `tests/math/test_certified_analysis.py` | existente | Enclosures e quadratura contra referências independentes. | Casos-limite, orçamento e adulterações com hash recalculado. |
| `tests/math/test_markov_analysis.py` | existente | Probabilidades e momentos contra leis e oráculos. | Distinguir condicionamento, recorrência, período e divergência. |
| `tests/test_rational_sided_limits.py` | existente | Limites laterais/infinito e replay. | Polos, buracos de domínio e casos fora do perfil. |
| `tests/test_lean_std.py` | existente | Provas reais, enunciados falsos e recibos adulterados. | Executar kernel e auditoria; skips não são aprovação. |
| `tests/test_proof_corpus_sharding.py` | existente | Partição do corpus e limites dos índices. | Nenhum teorema omitido/duplicado entre unidades. |
| `tests/test_nabla_bundle.py` | existente | Arquivo completo de fontes e hashes. | Bytes, CRLF, mudanças, dados excluídos e recusa de symlinks. |
| `tests/test_math_bundle.py` | existente | Atualidade do bundle matemático. | Bundle idêntico ao gerado das fontes canônicas. |
| `.github/workflows/python-core.yml` | existente | Matriz de SO/Python suportados. | Execução verde no commit do release, com resultados preservados. |
| `.github/workflows/windows-installer.yml` | existente | Build/teste do instalador Windows. | Artefato exato e ciclo real de instalação validados. |
| `.github/workflows/lean.yml` | existente | Preparação e testes Mathlib. | Dependências fixadas; resolver o timeout conhecido. |
| `.github/workflows/lean-core.yml` | existente | Contratos Lean sem dependências científicas opcionais. | Compilar e auditar os alvos declarados. |
| `.github/workflows/rational-conformance.yml` | existente | Corpus Std e análise certificada. | 60 unidades e 30.000 auditorias aprovadas. |
| `.github/workflows/security.yml` | existente | Revisões automatizadas de segurança do perfil. | Relatar limites e completar revisão humana apropriada. |
| `.github/workflows/full-integration.yml` | existente | Integração dos componentes do release. | Não encobrir módulos pulados nem pré-requisitos ausentes. |
| `.github/workflows/release-attestation.yml` | existente | Proveniência e atestação do release. | Vincular commit, build, SBOM e artefato publicado. |

## 10 — Ferramentas, evidências e arquivos finais

| Arquivo | Situação atual | O que deve conter | Aceite para 1.0 |
|---|---|---|---|
| `tools/check_roadmap.py` | existente | Consistência dos 213 requisitos e seus vínculos. | Preservar estados parciais até haver aceite pertinente. |
| `tools/check_public_contracts.py` | existente | Coerência dos contratos e links públicos. | Sem alegações incompatíveis entre README, documentação e matriz. |
| `tools/vision_readiness.py` | existente | Relatório completo de testes, benchmarks e lacunas. | Ler falhas, skips e bloqueios; não usar inventory-only como aprovação. |
| `tools/validate_longley.py` | existente | Referência numérica NIST do perfil estatístico. | Resultados e tolerâncias preservados com proveniência. |
| `tools/calibrate_readiness.py` | existente | Calibração finita de matemática e integração. | Publicar denominadores e recusar conclusão universal a partir do recorte. |
| `tools/build_math_bundle.py` | existente | Geração e conferência de math.txt. | Fontes canônicas e índice coerentes; não contar cópias como código novo. |
| `tools/build_nabla_bundle.py` | existente | Geração completa de NABLA.TXT. | Bytes e hashes por arquivo, sem dependências/cache e sem recursão dos bundles. |
| `.gitattributes` | existente | Política de bytes e marcação de fontes geradas. | NABLA.TXT preservado byte a byte; histórico não normalizado indevidamente. |
| `math.txt` | existente | Fontes matemáticas consolidadas na raiz. | Regenerar das fontes e verificar antes de distribuir. |
| `NABLA.TXT` | existente | Fontes/configurações consolidadas de todo o projeto. | Hash e conteúdo corresponderem ao commit distribuído. |
| `docs/SOURCE_BUNDLES.md` | existente | Instruções de regeneração e escopo dos TXT. | Explicar que são agregações de fontes, não executáveis binários. |

## Arquivos gerados adicionais: cada unidade de prova

O manifesto lista o nome e o hash de cada teorema. As unidades abaixo são fontes
geradas, não algoritmos novos. Cada arquivo deve conter exatamente as 500 provas
e auditorias indicadas, com os índices do protocolo congelado.

| Arquivo | Conteúdo necessário | Aceite |
|---|---|---|
| `lean/Conformance/affine_square.lean` | Família `affine_square`, índices 1–20, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/affine_square_part002.lean` | Família `affine_square`, índices 21–40, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/affine_square_part003.lean` | Família `affine_square`, índices 41–60, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/affine_square_part004.lean` | Família `affine_square`, índices 61–80, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/affine_square_part005.lean` | Família `affine_square`, índices 81–100, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/affine_square_part006.lean` | Família `affine_square`, índices 101–120, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/bounded_square.lean` | Família `bounded_square`, índices 1–20, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/bounded_square_part002.lean` | Família `bounded_square`, índices 21–40, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/bounded_square_part003.lean` | Família `bounded_square`, índices 41–60, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/bounded_square_part004.lean` | Família `bounded_square`, índices 61–80, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/bounded_square_part005.lean` | Família `bounded_square`, índices 81–100, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/bounded_square_part006.lean` | Família `bounded_square`, índices 101–120, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/closed_rational.lean` | Família `closed_rational`, índices 1–20, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/closed_rational_part002.lean` | Família `closed_rational`, índices 21–40, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/closed_rational_part003.lean` | Família `closed_rational`, índices 41–60, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/closed_rational_part004.lean` | Família `closed_rational`, índices 61–80, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/closed_rational_part005.lean` | Família `closed_rational`, índices 81–100, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/closed_rational_part006.lean` | Família `closed_rational`, índices 101–120, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/difference_squares.lean` | Família `difference_squares`, índices 1–20, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/difference_squares_part002.lean` | Família `difference_squares`, índices 21–40, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/difference_squares_part003.lean` | Família `difference_squares`, índices 41–60, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/difference_squares_part004.lean` | Família `difference_squares`, índices 61–80, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/difference_squares_part005.lean` | Família `difference_squares`, índices 81–100, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/difference_squares_part006.lean` | Família `difference_squares`, índices 101–120, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/distributive.lean` | Família `distributive`, índices 1–20, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/distributive_part002.lean` | Família `distributive`, índices 21–40, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/distributive_part003.lean` | Família `distributive`, índices 41–60, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/distributive_part004.lean` | Família `distributive`, índices 61–80, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/distributive_part005.lean` | Família `distributive`, índices 81–100, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/distributive_part006.lean` | Família `distributive`, índices 101–120, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/fraction_sum.lean` | Família `fraction_sum`, índices 1–20, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/fraction_sum_part002.lean` | Família `fraction_sum`, índices 21–40, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/fraction_sum_part003.lean` | Família `fraction_sum`, índices 41–60, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/fraction_sum_part004.lean` | Família `fraction_sum`, índices 61–80, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/fraction_sum_part005.lean` | Família `fraction_sum`, índices 81–100, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/fraction_sum_part006.lean` | Família `fraction_sum`, índices 101–120, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/guarded_inverse.lean` | Família `guarded_inverse`, índices 1–20, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/guarded_inverse_part002.lean` | Família `guarded_inverse`, índices 21–40, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/guarded_inverse_part003.lean` | Família `guarded_inverse`, índices 41–60, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/guarded_inverse_part004.lean` | Família `guarded_inverse`, índices 61–80, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/guarded_inverse_part005.lean` | Família `guarded_inverse`, índices 81–100, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/guarded_inverse_part006.lean` | Família `guarded_inverse`, índices 101–120, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/monotone_affine.lean` | Família `monotone_affine`, índices 1–20, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/monotone_affine_part002.lean` | Família `monotone_affine`, índices 21–40, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/monotone_affine_part003.lean` | Família `monotone_affine`, índices 41–60, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/monotone_affine_part004.lean` | Família `monotone_affine`, índices 61–80, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/monotone_affine_part005.lean` | Família `monotone_affine`, índices 81–100, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/monotone_affine_part006.lean` | Família `monotone_affine`, índices 101–120, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/nonnegative_square.lean` | Família `nonnegative_square`, índices 1–20, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/nonnegative_square_part002.lean` | Família `nonnegative_square`, índices 21–40, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/nonnegative_square_part003.lean` | Família `nonnegative_square`, índices 41–60, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/nonnegative_square_part004.lean` | Família `nonnegative_square`, índices 61–80, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/nonnegative_square_part005.lean` | Família `nonnegative_square`, índices 81–100, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/nonnegative_square_part006.lean` | Família `nonnegative_square`, índices 101–120, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/quadratic_minimum.lean` | Família `quadratic_minimum`, índices 1–20, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/quadratic_minimum_part002.lean` | Família `quadratic_minimum`, índices 21–40, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/quadratic_minimum_part003.lean` | Família `quadratic_minimum`, índices 41–60, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/quadratic_minimum_part004.lean` | Família `quadratic_minimum`, índices 61–80, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/quadratic_minimum_part005.lean` | Família `quadratic_minimum`, índices 81–100, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |
| `lean/Conformance/quadratic_minimum_part006.lean` | Família `quadratic_minimum`, índices 101–120, 500 teoremas | Lean fixado compila; todos os nomes e axiomas são conferidos. |

## Ordem de execução

1. Aprovar e congelar o escopo 1.0, contratos públicos e plataformas suportadas.
2. Corrigir o preparo Mathlib e outros bloqueios do perfil; classificar falhas
   de ambiente separadamente de defeitos do código. Preservar a evidência original.
3. Revisar tipos, unidades, domínios, precisão, migrações e estabilidade do catálogo.
4. Fechar CLI → cálculo → notebook → armazenamento → artefato → exportação → desktop.
5. Validar upgrade/backup/restore, erros de usuário e proteção de operações locais.
6. Executar os testes de cada contrato e a matriz suportada no commit exato.
7. Construir wheel/instalador, instalar em máquina limpa e reexecutar o fluxo completo.
8. Completar revisão de segurança, significado das provas, documentação e licenças.
9. Gerar hashes/SBOM/proveniência, regenerar os dois TXT e aprovar os gates.
10. Somente então versionar/publicar 1.0 com notas e problemas conhecidos.

## Gates finais: todos são obrigatórios no perfil declarado

- [ ] Escopo, APIs/formatos estáveis, plataformas e exclusões aprovados e publicados.
- [ ] Nenhum teste obrigatório falha; todo skip possui justificativa por perfil.
- [ ] Matriz SO/Python do commit do release aprovada em CI.
- [ ] Backend formal declarado suportado funciona com pinagem e auditoria de axiomas.
- [ ] Tradução/enunciados revisados quanto ao significado, não apenas à compilação.
- [ ] Wheel/instalador exatos instalados e usados em ambiente limpo.
- [ ] Migrações e backup/restore preservam dados das versões suportadas.
- [ ] Fluxo público completo funciona, com falhas e cancelamento diagnosticáveis.
- [ ] Revisão de segurança e cadeia de distribuição concluída para o escopo local.
- [ ] Licenças, consentimento e procedência de dados/artefatos conferidos.
- [ ] Documentação e limites coerentes com o software efetivamente entregue.
- [ ] Bundles, hashes, SBOM, proveniência e notas correspondem ao artefato publicado.
- [ ] Responsáveis pelo release aceitam os resultados; a pontuação estimada não
      substitui nenhum desses gates.

## O que não se resolve criando arquivos

Assinatura real exige uma autoridade configurada. CI multiplataforma exige
execução nas plataformas. Revisão independente exige revisores e seu trabalho.
Validação observacional exige dados, protocolo e medições. Ganho de aprendizado
exige experimento reservado e pode continuar negativo. Nenhum placeholder ou
corpus gerado fornece essas evidências por si só.

A decomposição integral da visão de longo prazo está em
`docs/audits/VISION_REQUIREMENTS_2026_10_16.md` (213 requisitos) e
`docs/audits/VISION_FILES_2026_10_16.md` (1.160 caminhos). Esses inventários são
maiores que o perfil 1.0; não é necessário concluir F13 para lançar uma versão
local honestamente delimitada.

Total deste plano: **152 arquivos individuais de produto/aceite e 60 unidades Lean geradas**, sem contar dependências instaladas, caches ou outputs locais.

## Execução da preparação local

Os 212 caminhos estão presentes após a implementação dos arquivos documentais e
dos testes de cadeia de distribuição antes ausentes. Presença não é aceite.
`tools/vision1_inventory.py` confere cada caminho, bytes, hash e critério descrito
acima, recusando duplicatas e caminhos inseguros. Execute com `--output` apontando
para um arquivo novo para preservar a fotografia; o relatório não aprova release.

Nesta preparação, notebooks passaram a validar JSON estrito e comparar replay
canônico com distinção de tipos. O diagnóstico formal separa versão compatível do
compilador de disponibilidade Mathlib ainda não verificada. Consulte CHANGELOG.md
e docs/API_STABILITY.md para contratos e limites. Backup/restore agora valida
manifestos estritos, schema real e concorrência sem sobrescrever um novo destino. Os gates externos acima continuam
pendentes até existir evidência pertinente; a versão permanece 0.1.0a1.
