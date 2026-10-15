# Nabla ∇ — roteiro de engenharia para toda a ambição 2026–2056+

## Escopo e interpretação

### Diretrizes e marcos
O plano cobre 2026–2056+ e cada requisito recebe ID, contrato, teste, evidência, versão e revisão. A visão aberta exige avaliação recorrente: não será fingido 100% da ciência futura. A arquitetura deve servir a CPU doméstica, GPU opcional e infraestrutura de laboratório sem alegar desempenho não medido. F0 estabelece núcleo/qualidade, F1–F6 cálculo, verificação e datasets; F7–F9 simulações/aprendizado/descoberta; F10 evolução controlada; F11 disciplinas; F12 conhecimento científico; F13 permanece como pesquisa aberta.

### Levantamento confirmado
Base: Git tree `494172023cb97ada45133a7a868344fc2215c53c` de 15/10/2026. Total identificado por API: 1.070 arquivos, incluindo 726 `.py`, 124 `.json`, 81 `.md` e diversos modelos/artefatos. Pontos concretos: CI principal falhava devido a falta de pytest no ambiente do unittest; `gpu/cuda_f4_reduction.py` usa CPU por padrão; o coordenador HTTP só disponibiliza `/health`; a interface de desktop cobre apenas parte das APIs; benchmarks de aprendizado atuais não demonstraram generalização externa. Evidências de F1–F12 são parciais e a rubrica 70,32% é julgamento subjetivo com incerteza de ~10 pontos. Não há validação externa da visão integral.

### Regra de mudança
Os critérios abaixo são **tarefas-alvo/inspeções necessárias**, não alegações de falha comprovada em cada arquivo. Em arquivos gerados e históricos, a ação correta é preservar e reexecutar, não sobrescrever. O script `gerar_inventario_nabla_2056.py` gera uma lista numerada por CADA arquivo da árvore remota, mais todos os novos arquivos propostos. O presente roteiro é um mapa de programas de trabalho por responsabilidade.

### Condições de aceitação universais
Cada requisito deve incluir: semântica e domínio, hipóteses, método, correção ou erro, proveniência, orçamento, casos negativos, comparação independente, replay, versão de APIs, segurança e revisão. Dados sintéticos não substituem experimentos; hashes não substituem correção matemática; prova Lean não substitui correspondência entre linguagem natural e teorema; texto da IA não substitui evidência; resultado negativo tem de ser preservado. Nenhuma fase é concluída somente por muitos arquivos ou testes.

## Lista numerada — todos os setores da árvore, arquivos críticos e novos componentes

1. **`src/nablamath/core/`** — **P0 · F1–F12**: unificar AST/IR, tipos, unidades, precisão, domínios e contratos semânticos; garantir serialização canônica, invariantes e migração. **Concluído quando:** testes de propriedades, unidades, condições de domínio, compatibilidade e round-trip.

2. **`src/nablamath/schema/`** — **P0 · F0–F12**: versionar e validar esquemas de problema, expressão, experimento, etapa, evidência e artefato; rejeitar ambiguidades e mudanças silenciosas. **Concluído quando:** golden fixtures, migrações, validação adversarial e interop.

3. **`src/nablamath/calc/`** — **P1 · F1**: ampliar catálogo e sessão científica com operações gerais, diferenciação, rastreamento e erros certificados. **Concluído quando:** comparações externas, exemplos adversariais e especificações por operação.

4. **`src/nablamath/symbolic/`** — **P1 · F1–F3**: expandir parser/reescrita/e-graphs, funções transcendentes, hipóteses, integrais e certificados de transformação. **Concluído quando:** provas ou verificação independente de regras, preservação de domínio e benchmarks.

5. **`src/nablamath/numeric/`** — **P1 · F1/F7**: implementar solvers numéricos modernos, condicionamento, tolerâncias, intervalos, limites de recursos e diagnósticos. **Concluído quando:** convergência, referências NIST/analíticas, escalonamento e precisão.

6. **`src/nablamath/math/`** — **P1 · F1–F3/F11**: aprofundar a área matemática do módulo, documentar domínio e limitações, adicionar algoritmos gerais e referências competitivas. **Concluído quando:** propriedades matemáticas, benchmarks independentes, provas quando cabíveis e testes de fronteira.

7. **`src/nablamath/autodiff/`** — **P1 · F1/F7/F8**: expandir forward/reverse AD para tensores e aplicações, broadcasting, controle de gradiente, jacobianas e Hessianas. **Concluído quando:** grad-check, precisão, memória, comparação com JAX/PyTorch e exemplos físicos.

8. **`src/nablamath/forge/`** — **P1 · F2**: ampliar construção inversa, deduplicação, diversidade, geração composicional, controle de dificuldade e verificação. **Concluído quando:** corpus inédito, solvers competidores, taxas de validade, novidade estrutural e dificuldade calibrada.

9. **`src/nablamath/verify/`** — **P0 · F2–F12**: separar proponente e verificador, reexecutar provas/testemunhos, integrar obrigações e linhagem de evidências. **Concluído quando:** falsificações induzidas rejeitadas e evidências reexecutáveis em ambiente limpo.

10. **`src/nablamath/formal/`** — **P1 · F3**: expandir cobertura Lean/SMT, autoformalização assistida revisada, certificados, lógica e rastreio de axiomas. **Concluído quando:** kernel independente, hipóteses explícitas, correspondência humana auditada e replay.

11. **`src/nablamath/falsifier/`** — **P1 · F3/F9**: expandir busca/minimização de contraexemplos, propriedades, domínio e diagnósticos verificáveis. **Concluído quando:** falsificações conhecidas recuperadas e ausência de falso teorema.

12. **`src/nablamath/gpu/`** — **P2 · F1–F10**: substituir caminhos de referência por kernels reais opcionais, com fallback CPU, profiling, uso de VRAM e verificação numérica. **Concluído quando:** benchmarks em hardware identificado, equivalência e provas de ganho custo/energia.

13. **`src/nablamath/compiler/`** — **P2 · F1–F10**: estabilizar IR/compilação, otimização semântica, backends e agendamento distribuído. **Concluído quando:** equivalência entre backends, determinismo e custos mensurados.

14. **`src/nablamath/physics/`** — **P1 · F7/F11**: ampliar modelos físicos além das referências, incluindo condições de contorno, incerteza, calibração e validação observacional. **Concluído quando:** casos manufaturados, séries de convergência, dados reais e revisão disciplinar.

15. **`src/nablamath/worlds/`** — **P1 · F7**: generalizar modelos de EDO/EDP, malhas, eventos, rigidez, multiphysics, controle de erro e replay. **Concluído quando:** benchmarks por fenômeno, estabilidade/conservação, confronto com medidas e reproducibilidade.

16. **`src/nablamath/graphics/`** — **P2 · F4**: implementar cenas e geometria mais gerais, renderizações científicas auditáveis, qualidade visual e exportação multimodal. **Concluído quando:** validação geométrica, inspeção de imagens, performance e semântica das figuras.

17. **`src/nablamath/viz/`** — **P2 · F4/F5**: unificar gráficos e animações com dados, escalas, unidades, acessibilidade e metadados de incerteza. **Concluído quando:** replay pixel/semântico, revisão visual e testes de legibilidade.

18. **`src/nablamath/documents/`** — **P1 · F5**: completar AST editorial, bibliografia, referências, tabelas, figuras e exportações sem alegações sem evidência. **Concluído quando:** compilação dos formatos, inspeção de páginas e revisão editorial externa.

19. **`src/nablamath/reports/`** — **P2 · F5**: consolidar relatórios com documentos canônicos, tabelas, passos, provas e vínculos verificáveis. **Concluído quando:** PDF/LaTeX com numeração e integridade reexecutável.

20. **`src/nablamath/dataset/`** — **P1 · F6**: migrar APIs antigas para contrato canônico, governar licenças, splits, qualidade, deduplicação e proveniência. **Concluído quando:** migrações compatíveis, integridade por amostra, testes de contaminação.

21. **`src/nablamath/datasets/`** — **P1 · F6/F8**: unificar modelos de registros e alinhar modalidades, linhagem, licenças, política de splits e evidência multimodal. **Concluído quando:** auditoria independente de corpora e ganho ou resultado negativo reproduzível.

22. **`src/nablamath/export/`** — **P1 · F5/F6/F12**: publicar bundles interoperáveis versionados com manifestos, integridade, licenças, privacidade e reversibilidade. **Concluído quando:** import/export/verify em ambiente isolado e controles de adulteração.

23. **`src/nablamath/training/`** — **P1 · F8**: treinar modelos mais capazes, estabelecer avaliações externas, ablações, curricula, contaminação e custo de treino. **Concluído quando:** comparação com/sem Nabla em holdouts verdadeiramente inéditos e ICs pré-especificados.

24. **`src/nablamath/evaluation/`** — **P0 · F6/F8/F10**: criar avaliador congelado independente de proponente, impedir vazamento transitivo e fornecer decisão estatística auditável. **Concluído quando:** testes adversariais com adulteração e holdout inacessível ao proponente.

25. **`src/nablamath/agents/`** — **P1 · F8**: planejamento científico mais capaz, permissões por capacidade, orçamentos, checkpoints, orquestração e isolamento real. **Concluído quando:** ataques simulados, replay, falha segura e custos por tarefa.

26. **`src/nablamath/discovery/`** — **P1 · F9**: ampliar gramáticas, busca de leis/teoremas, experimentos discriminantes e revisão bibliográfica. **Concluído quando:** novidade avaliada externamente, reprodução e registro de descobertas nulas/refutadas.

27. **`src/nablamath/evolution/`** — **P1 · F10**: permitir propostas de algoritmos novos sob gates isolados, rollback, estatística e autoridade distinta. **Concluído quando:** ganhos contra baseline forte em avaliações congeladas e monitoramento de regressões.

28. **`src/nablamath/domains/`** — **P1 · F11**: aprofundar modelos disciplinares e suas integrações com instrumentação, medições e especialistas. **Concluído quando:** validação com observações reais e critérios próprios por disciplina.

29. **`src/nablamath/knowledge/`** — **P1 · F9/F12**: reconciliar claims, evidências, versões, revisão, retração, federação, identidades e conflitos. **Concluído quando:** replay institucional multioperador, reconciliação correta e autenticação independente.

30. **`src/nablamath/network/`** — **P2 · F12**: consolidar objetos, manifestos, recibos e protocolos P2P com limites e consistência. **Concluído quando:** testes de rede real, falhas parciais e compatibilidade retroativa.

31. **`src/nablamath/p2p/`** — **P2 · F12**: implementar transporte autenticado, descoberta, rate limits, quarentena e recuperação de peers. **Concluído quando:** rede adversarial e latência/perda medidas.

32. **`src/nablamath/node/`** — **P2 · F12**: operacionalizar nó consentido, controle de recursos, tarefas, verificação e workspace. **Concluído quando:** reprodução em máquinas distintas e telemetria auditável.

33. **`src/nablamath/coordination/`** — **P2 · F12**: unificar coordenação local/Merkle com serviços distribuídos e provas de consistência. **Concluído quando:** invariantes sob concorrência, reconexão e restauração.

34. **`src/nablamath/pipeline/`** — **P0 · F0–F12**: ligar todos os estágios científicos em pipeline transacional, versionado e reexecutável com cache seguro. **Concluído quando:** um ScientificArtifact ponta a ponta com adulteração de cada vínculo rejeitada.

35. **`src/nablamath/singularity/`** — **P3 · F8–F13**: converter protótipos de cognição/memória/engenharia/agentes em componentes mensuráveis, governados e testáveis sem alegar AGI. **Concluído quando:** benchmarks abertos/fechados, segurança, ganhos transferíveis e avaliações independentes.

36. **`src/nablamath/adapters/`** — **P2 · F1/F7/F11**: tornar integração NumPy/SciPy/SymPy/Blender/instrumentos explícita, compatível, segura e bidirecional. **Concluído quando:** testes com versões fixadas e coerência de unidades/dados.

37. **`src/nablamath/store/`** — **P0 · F0–F12**: fortalecer migrations, backups, armazenamento de blobs, integridade e política de retenção. **Concluído quando:** restauração/falha de energia/concorrrência, recovery e compatibilidade.

38. **`src/nablamath/publisher/`** — **P2 · F5/F6**: governar publicação autorizada e assinada com direitos por artefato e política de revogação. **Concluído quando:** dry-run, idempotência e testes em destino de homologação.

39. **`src/nablamath/benchmarks/`** — **P0 · F1–F12**: pré-registrar protocolos e incluir baselines independentes, métricas e falhas reexecutáveis. **Concluído quando:** replicação por terceiros, holdouts novos e relatórios negativos.

40. **`src/nablamath/desktop/`** — **P2 · F1–F12**: expor workflows científicos completos, revisão humana, datasets e rastreio em UX local segura. **Concluído quando:** testes acessibilidade/usabilidade e equivalência CLI/API.

41. **`src/nablamath/`** — **P1 · F0–F12**: manter contratos, CLI, compatibilidade e workflows integrados; eliminar caminhos paralelos sem migração. **Concluído quando:** smokes da API pública, documentação e integração de ponta a ponta.

42. **`tests/`** — **P0 · F0–F13**: expandir o teste deste componente para casos positivos/negativos, propriedade, integração, segurança e benchmarks. **Concluído quando:** CI em Linux/Windows/macOS, fixture congelado e evidência em release.

43. **`lean/`** — **P1 · F3**: ampliar demonstrações Lean além dos fragmentos atuais; pin da toolchain, livre de sorry/admit e revisão de tradução. **Concluído quando:** compilação reproduzível, kernel verificando teoremas e auditoria de axiomas.

44. **`protocol/`** — **P0 · F0/F12**: padronizar codificação canônica, schemas de objetos/recibos e interop de clientes. **Concluído quando:** golden vectors e testes cruzados C/C++/Rust/Python.

45. **`sdk/`** — **P2 · F12**: evoluir parsers de frações para SDKs científicos e transporte autenticado interoperáveis. **Concluído quando:** conformidade protocolar, ABI/API estáveis e fuzzing.

46. **`services/`** — **P2 · F12**: evoluir protótipos locais para serviços autenticados, escaláveis e tolerantes a falhas. **Concluído quando:** testes de rede entre hosts, segurança e monitoramento.

47. **`.github/workflows/`** — **P0 · F0–F13**: corrigir dependências, pin/atualizar actions, garantir CI matriz, segurança de supply chain e releases condicionadas. **Concluído quando:** nenhum check obrigatório falho e atestados por commit/release.

48. **`docs/audits/`** — **P0 · F0–F13**: registrar baseline, falhas, incertezas, remediações e evidências separando medições de opiniões. **Concluído quando:** auditoria independente e referências imutáveis por commit.

49. **`docs/history/`** — **P3 · Histórico**: preservar material original sem confundir aspiração histórica com implementação. **Concluído quando:** hash e índice de origem validados.

50. **`docs/`** — **P1 · F0–F13**: atualizar especificação, critérios, instruções e limites após mudanças verificadas. **Concluído quando:** links, exemplos e status verificáveis por versão.

51. **`benchmarks/results/`** — **P0 · Evidência**: preservar resultado congelado, inclusive falhas e modelos negativos; criar novos resultados em campanhas distintas. **Concluído quando:** SHA-256, protocolo, licença, replay semântico e cadeia de custódia.

52. **`benchmarks/fixtures/`** — **P0 · Evidência**: manter fixture original e fonte licenciada; incluir novas referências identificadas e imutáveis. **Concluído quando:** hash, proveniência e correspondência com referências independentes.

53. **`benchmarks/`** — **P1 · F1–F12**: definir protocolos e baselines comparativos novos sem reescrever resultados históricos. **Concluído quando:** reexecução, métricas estatísticas e replicação.

54. **`legacy/`** — **P3 · Histórico**: congelar e catalogar código legado; migrar somente funcionalidades comprovadas para src/ com testes. **Concluído quando:** arquivos preservados por hash e nenhuma fonte dupla em produção.

55. **`website/`** — **P2 · Produto**: substituir indicadores promocionais por status derivado das evidências, melhorar transparência e documentação. **Concluído quando:** testes de interface, métricas rastreáveis, privacidade e acessibilidade.

56. **`tools/`** — **P0 · F0–F13**: ampliar auditoria e automação de reprodução, sem atribuir completude por quantidade de arquivos. **Concluído quando:** reexecução em ambiente limpo, tratamento de falha e relatórios versionados.

57. **`scripts/`** — **P1 · F0**: tornar instalação/importação idempotentes, reexecutáveis e seguros em todas as plataformas. **Concluído quando:** testes de recuperação e compatibilidade de arquivos históricos.

58. **`examples/`** — **P2 · Documentação**: criar exemplos reproduzíveis de pipelines completos e documentar limites. **Concluído quando:** execução automatizada de cada exemplo publicado.

59. **`templates/`** — **P2 · F5**: ampliar modelos de relatórios com origem de cada alegação, dados e revisão editorial. **Concluído quando:** compilação de todos os templates e conferência visual.

60. **`packaging/`** — **P1 · Produto**: assegurar instaladores assinados quando possível, atestados, atualização segura e desinstalação reversível. **Concluído quando:** instalação/upgrade/downgrade em máquinas limpas.

61. **`.github/workflows/ci.yml`** — intervenção específica: corrigir falha confirmada: instalar .[test] antes do unittest/pytest; executar também lint/build website. **Aceite:** job NablaMath CI aprovado no commit auditado.

62. **`pyproject.toml`** — intervenção específica: alinhar dependências opcionais, versões, entrypoints, perfis Python, metadados, SBOM e origem do wheel. **Aceite:** build e importação isolada, matriz de versões e release alinhada.

63. **`README.md`** — intervenção específica: documentar limites reais, quickstart, módulos avaliados, indicadores reproduzíveis e diferença visão/entrega. **Aceite:** todos os links e comandos revisados por CI.

64. **`vision.md`** — intervenção específica: converter aspirações 2026–2056+ em perfis versionados sem apagar o horizonte aberto; explicitar hipóteses e critérios de fechamento. **Aceite:** matriz bidirecional visão→requisitos→testes→evidência.

65. **`description.md`** — intervenção específica: sincronizar a descrição atual com evidências e release; evitar alegar avanços futuros como atuais. **Aceite:** toda alegação inclui versão e comprovação.

66. **`docs/PLANO_MESTRE_2026_2056.md`** — intervenção específica: manter contrato integrado, dependências, perfis de recursos e decisões por fase; atualizar custos e riscos. **Aceite:** alinhamento verificável entre metas, issues e entregas.

67. **`docs/audits/PHASES_1_12_COMPLETION_BACKLOG.md`** — intervenção específica: mapear os 104 itens aos módulos responsáveis, testes e evidências; adicionar fases F0/F13 e perfis de avanço posteriores. **Aceite:** cada requisito tem estado e prova de aceite.

68. **`docs/ARCHITECTURE_AND_ACCEPTANCE.md`** — intervenção específica: materializar os critérios de render, física, relatórios, formalização e estabilidade em testes automatizados. **Aceite:** nenhum requisito crítico pendente sem sinalização.

69. **`docs/MATHEMATICS_COMPLETION_AUDIT.md`** — intervenção específica: verificar algoritmos matemáticos gerais faltantes e manter recusas explícitas em domínios não cobertos. **Aceite:** matriz por classe de problema, benchmark e prova.

70. **`src/nablamath/agents/sandbox.py`** — intervenção específica: preservar proibição de código não confiável até existir sandbox real; não trocar bloqueio por eval/subprocess sem isolamento. **Aceite:** ataques e escapes bloqueados em ambiente isolado.

71. **`services/coordinator/app.py`** — intervenção específica: expandir HTTP além de /health com auth, filas, quotas, auditoria, retries e cancelamentos. **Aceite:** integração inter-host, concorrência e testes de segurança.

72. **`src/nablamath/desktop/app.py`** — intervenção específica: migrar UI local limitada para interface integrada de todos os workflows sem abrir serviços inseguros. **Aceite:** E2E de um experimento completo com consentimento.

73. **`src/nablamath/physics/fluids/navier_stokes.py`** — intervenção específica: ultrapassar solver 2D periódico de referência com fronteiras, discretizações robustas e validação experimental. **Aceite:** benchmarks CFD, convergência e erro verificado.

74. **`src/nablamath/physics/relativity/general.py`** — intervenção específica: ampliar geometria Schwarzschild para tensores, geodésicas e perfis de GR definidos, não declarar solver geral prematuramente. **Aceite:** invariantes, testes de limite e confronto com referências.

75. **`src/nablamath/gpu/cuda_f4_reduction.py`** — intervenção específica: implementar backend CUDA/Triton verdadeiro e não atribuir aceleração ao fallback CPU. **Aceite:** speedup, hardware, exatidão e memória medidos.

76. **`src/nablamath/discovery/novelty_screen.py`** — intervenção específica: integrar busca bibliográfica externa curada e revisão independente; não equiparar ausência local à novidade. **Aceite:** rastreio de referências, falsos positivos e revisão.

77. **`src/nablamath/training/baselines.py`** — intervenção específica: adicionar baselines fortes e métricas; manter vizinhos próximos como referência pequena, não como prova de ganho científico. **Aceite:** reprodução entre sementes, dados separados por família e comparação externa.

78. **`src/nablamath/training/multimodal_network.py`** — intervenção específica: evoluir demonstração de equações/imagens para tarefas multimodais científicas relevantes com ablações. **Aceite:** ganho fora da distribuição em benchmarks congelados.

79. **`src/nablamath/evolution/search.py`** — intervenção específica: substituir busca apenas Euler/RK4 por propostas algorítmicas mais amplas avaliadas isoladamente. **Aceite:** ganho robusto contra baseline forte e rollback reproduzível.

80. **`math.txt`** — intervenção específica: NÃO editar manualmente: reconstruir do gerador canônico após cada alteração do código. **Aceite:** tools/build_math_bundle.py --check aprovado.

81. **CRIAR `docs/acceptance/phase_profiles.md`** — Definir perfis finitos F0–F13 e critérios versionados de aceite. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

82. **CRIAR `docs/acceptance/evidence_matrix.json`** — Vincular requisito→teste→artefato→revisor→release. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

83. **CRIAR `docs/acceptance/scientific_capabilities.yaml`** — Especificar domínios suportados, recusados e tolerâncias. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

84. **CRIAR `docs/governance/independent_review_policy.md`** — Estabelecer revisores independentes e conflitos de interesse. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

85. **CRIAR `docs/governance/scientific_claims_policy.md`** — Distinguir formal, numérico, empírico, sintético e hipotético. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

86. **CRIAR `docs/strategy/roadmap_2026_2056.json`** — Versionar marcos, dependências e mudanças de escopo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

87. **CRIAR `docs/strategy/scientific_risk_register.md`** — Gerenciar riscos científicos, operacionais e de segurança. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

88. **CRIAR `docs/strategy/annual_reassessment.md`** — Atualizar a visão sem fabricar conclusão. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

89. **CRIAR `src/nablamath/core/scientific_artifact.py`** — Unificar hipótese, problema, solução, provas, simulações, imagens, datasets e documentos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

90. **CRIAR `src/nablamath/core/semantic_contracts.py`** — Definir invariantes canônicos independentes da representação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

91. **CRIAR `src/nablamath/core/migration_registry.py`** — Versionar migração semântica de objetos científicos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

92. **CRIAR `src/nablamath/core/uncertainty.py`** — Representar incerteza e sua propagação de modo rastreável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

93. **CRIAR `src/nablamath/math/calculus/transcendentals.py`** — Generalizar funções elementares e restrições de ramo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

94. **CRIAR `src/nablamath/math/calculus/risch.py`** — Pesquisar integração simbólica abrangente sob domínios declarados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

95. **CRIAR `src/nablamath/math/linear_algebra/exact_decompositions.py`** — Adicionar decomposições e certificados algébricos mais amplos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

96. **CRIAR `src/nablamath/math/number_theory/factorization_advanced.py`** — Desenvolver fatoração avançada com validação independente. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

97. **CRIAR `src/nablamath/math/algebra/galois.py`** — Implementar estruturas e algoritmos de teoria de Galois delimitados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

98. **CRIAR `src/nablamath/math/logic/smt_combination.py`** — Pesquisar integração de teorias e certificados SMT. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

99. **CRIAR `src/nablamath/numeric/intervals.py`** — Aritmética intervalar e limites certificados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

100. **CRIAR `src/nablamath/numeric/stiff_ode.py`** — Solvers implícitos para EDOs rígidas e eventos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

101. **CRIAR `src/nablamath/numeric/pde_general.py`** — Contratos para EDPs e condições de contorno extensíveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

102. **CRIAR `src/nablamath/forge/compositional_generator.py`** — Compor famílias de problemas com soluções conhecidas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

103. **CRIAR `src/nablamath/forge/adversarial_generator.py`** — Gerar problemas difíceis e detectar atalhos indevidos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

104. **CRIAR `src/nablamath/forge/difficulty_calibration.py`** — Definir dificuldade condicional a solver e recursos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

105. **CRIAR `src/nablamath/forge/novelty_index.py`** — Deduplicação estrutural e semântica escalável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

106. **CRIAR `src/nablamath/formal/autoformalization.py`** — Pipeline de tradução com verificação humana e kernel. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

107. **CRIAR `src/nablamath/formal/proof_repair.py`** — Correção assistida de demonstrações sem suprimir obrigações. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

108. **CRIAR `src/nablamath/formal/proof_search_planner.py`** — Busca escalável guiada por hipóteses e provas verificáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

109. **CRIAR `src/nablamath/falsifier/property_engine.py`** — Falsificação sistemática por propriedades e domínios. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

110. **CRIAR `src/nablamath/gpu/kernels/f4_cuda.py`** — Backend de referência para kernel CUDA verificável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

111. **CRIAR `src/nablamath/gpu/kernels/egraph_triton.py`** — Backend Triton opcional para operações bateladas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

112. **CRIAR `src/nablamath/gpu/profiler.py`** — Telemetria reprodutível de VRAM, tempo e energia. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

113. **CRIAR `src/nablamath/worlds/boundary_conditions.py`** — Representar contornos gerais de simulações. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

114. **CRIAR `src/nablamath/worlds/mesh/adaptive.py`** — Refino adaptativo com estimadores de erro. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

115. **CRIAR `src/nablamath/worlds/validation_observational.py`** — Confrontar simulações com medições observadas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

116. **CRIAR `src/nablamath/worlds/uncertainty_quantification.py`** — Propagação de incerteza nos modelos físicos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

117. **CRIAR `src/nablamath/physics/fluids/turbulence.py`** — Modelos de turbulência delimitados e calibrados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

118. **CRIAR `src/nablamath/physics/fluids/compressible.py`** — Fluxos compressíveis e choques com validação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

119. **CRIAR `src/nablamath/physics/relativity/einstein_solver.py`** — Estudo modular de soluções de Einstein sem alegar generalidade automática. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

120. **CRIAR `src/nablamath/physics/fea/nonlinear.py`** — Elementos finitos não lineares e verificação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

121. **CRIAR `src/nablamath/graphics/visual_regression.py`** — Comparar renderização semântica e imagens de referência. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

122. **CRIAR `src/nablamath/graphics/scientific_renderer.py`** — Renderização científica avançada rastreável ao modelo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

123. **CRIAR `src/nablamath/documents/reference_graph.py`** — Referências cruzadas e dependências de alegações em documentos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

124. **CRIAR `src/nablamath/documents/editorial_review.py`** — Fluxo de revisão e qualidade editorial. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

125. **CRIAR `src/nablamath/datasets/corpus_registry.py`** — Registro de corpora e licenças externas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

126. **CRIAR `src/nablamath/datasets/semantic_leakage.py`** — Detecção avançada de contaminação e semelhança. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

127. **CRIAR `src/nablamath/datasets/large_scale_pipeline.py`** — Geração controlada em escala sem degradar qualidade. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

128. **CRIAR `src/nablamath/training/frontier_adapter.py`** — Adaptadores opcionais de modelos de fronteira com consentimento. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

129. **CRIAR `src/nablamath/training/reasoning_finetune.py`** — Treino de raciocínio com protocolos congelados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

130. **CRIAR `src/nablamath/training/cross_domain_eval.py`** — Medir generalização entre famílias e disciplinas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

131. **CRIAR `src/nablamath/training/compute_accounting.py`** — Rastrear custo, energia e recursos por ganho útil. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

132. **CRIAR `src/nablamath/agents/secure_execution.py`** — Sandbox operacional para código não confiável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

133. **CRIAR `src/nablamath/agents/experiment_planner.py`** — Planejamento de experimentos científicos revisáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

134. **CRIAR `src/nablamath/agents/human_approval.py`** — Autorizações explícitas para instrumentos, redes e publicação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

135. **CRIAR `src/nablamath/discovery/literature_search.py`** — Busca de antecedentes em fontes científicas externas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

136. **CRIAR `src/nablamath/discovery/causal_hypothesis.py`** — Hipóteses causais testáveis com pressupostos declarados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

137. **CRIAR `src/nablamath/discovery/lab_protocol.py`** — Protocolos de execução e reprodutibilidade de experimentos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

138. **CRIAR `src/nablamath/discovery/independent_replication.py`** — Registro de replicações independentes. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

139. **CRIAR `src/nablamath/evolution/code_proposals.py`** — Propostas de mudanças algorítmicas versionadas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

140. **CRIAR `src/nablamath/evolution/frozen_evaluator.py`** — Avaliador separado da autoridade do proponente. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

141. **CRIAR `src/nablamath/evolution/secure_trials.py`** — Testes isolados de descendentes candidatos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

142. **CRIAR `src/nablamath/evolution/longitudinal_monitor.py`** — Medição de ganhos sustentados e regressões. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

143. **CRIAR `src/nablamath/knowledge/institutional_identity.py`** — Vínculo de identidade real e competências auditáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

144. **CRIAR `src/nablamath/knowledge/distributed_provenance.py`** — Proveniência multioperador e revogação verificável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

145. **CRIAR `src/nablamath/knowledge/replication_protocol.py`** — Replicação de alegações e revisões externas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

146. **CRIAR `src/nablamath/knowledge/retraction_index.py`** — Retratação propagada a artefatos dependentes. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

147. **CRIAR `services/coordinator/api.py`** — API autenticada de coordenação e quotas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

148. **CRIAR `services/coordinator/task_leases.py`** — Leases duráveis, heartbeats e idempotência. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

149. **CRIAR `services/coordinator/telemetry.py`** — Observabilidade preservando privacidade. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

150. **CRIAR `services/worker/executor.py`** — Worker de tarefas tipadas, com limites e cancelamento. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

151. **CRIAR `services/worker/isolation.py`** — Isolamento operacional e política de recursos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

152. **CRIAR `services/federation/reconciliation.py`** — Federação entre organizações e resolução de conflitos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

153. **CRIAR `sdk/python/README.md`** — Contrato público de SDK Python. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

154. **CRIAR `sdk/typescript/README.md`** — Cliente interoperável para UI web. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

155. **CRIAR `sdk/rust/src/client.rs`** — Cliente Rust de protocolo científico completo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

156. **CRIAR `tests/integration/test_scientific_artifact.py`** — Ciclo completo e ataques em cada vínculo do artefato. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

157. **CRIAR `tests/integration/test_global_scientific_cycle.py`** — Integração F1–F12 com avaliação honesta de lacunas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

158. **CRIAR `tests/security/test_agent_sandbox.py`** — Tentativas de escape e falha segura. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

159. **CRIAR `tests/security/test_supply_chain.py`** — Dependências, segredos e provenance de builds. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

160. **CRIAR `tests/benchmark/test_math_comparison.py`** — Benchmarks de solvers especializados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

161. **CRIAR `tests/benchmark/test_gpu_real_hardware.py`** — Aceleração real mensurada e conferida. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

162. **CRIAR `tests/benchmark/test_holdout_generalization.py`** — Generalização fora do treino sem vazamento. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

163. **CRIAR `tests/science/test_observational_validation.py`** — Dados empíricos, calibração e incerteza. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

164. **CRIAR `tests/science/test_independent_discovery.py`** — Reprodução de resultados científicos com revisores externos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

165. **CRIAR `tests/distributed/test_multihost_failures.py`** — Redes reais, perdas, partições e recuperação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

166. **CRIAR `benchmarks/protocols/README.md`** — Registro prévio de métricas, sementes, grupos e baselines. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

167. **CRIAR `benchmarks/resources/hardware_profiles.json`** — Ambientes de referência e budgets documentados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

168. **CRIAR `benchmarks/external/README.md`** — Catálogo de comparações externas com licenças. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

169. **CRIAR `.github/workflows/security.yml`** — Análise estática, dependências e segredos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

170. **CRIAR `.github/workflows/full-integration.yml`** — Perfil integrado e replay end-to-end. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

171. **CRIAR `.github/workflows/scientific-benchmarks.yml`** — Execuções científicas agendadas e diferenciadas dos unit tests. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

172. **CRIAR `.github/workflows/release-attestation.yml`** — Integridade, SBOM e proveniência por release. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

173. **CRIAR `configs/profiles/cpu_conservative.yaml`** — Limites para PCs domésticos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

174. **CRIAR `configs/profiles/cpu_balanced.yaml`** — Perfil doméstico equilibrado. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

175. **CRIAR `configs/profiles/gpu_local.yaml`** — Orçamentos de VRAM/GPU local. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

176. **CRIAR `configs/profiles/research_station.yaml`** — Perfil de estação profissional. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

177. **CRIAR `configs/profiles/hpc_optional.yaml`** — Escalamento opcional, sem pressupor HPC obrigatório. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

178. **CRIAR `src/nablamath/network/signatures.py`** — Assinatura assimétrica, rotação e revogação de chaves no protocolo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

179. **CRIAR `src/nablamath/node/identity.py`** — Identidade local consentida com chaves e política de recuperação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

180. **CRIAR `src/nablamath/p2p/moderation.py`** — Quarentena, limites de abuso e moderação auditáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

181. **CRIAR `src/nablamath/p2p/reputation.py`** — Sinais antiabuso sem equiparar popularidade à verdade científica. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

182. **CRIAR `services/registry/app.py`** — Registro seguro e opt-in de nós e capacidades. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

183. **CRIAR `services/registry/api.py`** — API de descoberta e permissões versionadas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

184. **CRIAR `services/registry/db.py`** — Persistência de peers, chaves e estado de revogação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

185. **CRIAR `services/registry/metrics.py`** — Métricas anonimizadas e limites operacionais. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

186. **CRIAR `services/relay/app.py`** — Relay autenticado com quotas e desligamento seguro. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

187. **CRIAR `services/relay/protocol.py`** — Protocolos para NAT/retransmissão com proteção anti-replay. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

188. **CRIAR `services/relay/abuse.py`** — Prevenção de Sybil/eclipse/poisoning e registros auditáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

189. **CRIAR `tests/network/test_sybil.py`** — Testes de identidades artificiais e resiliência de federação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

190. **CRIAR `tests/network/test_poisoning.py`** — Injeção de resultados, hashes e assinaturas adulteradas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

191. **CRIAR `tests/network/test_eclipse.py`** — Isolamento de peers e respostas resistentes a eclipse. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

192. **CRIAR `tests/network/test_partition.py`** — Partições prolongadas de rede e reconciliação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

193. **CRIAR `tests/network/test_interop.py`** — Interoperabilidade real entre implementações de protocolo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

194. **CRIAR `src/nablamath/knowledge/lineage.py`** — Dependências entre conhecimento, dados e retratações. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

195. **CRIAR `src/nablamath/knowledge/novelty.py`** — Novidade relativa a corpus e revisão bibliográfica independente. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

196. **CRIAR `src/nablamath/knowledge/difficulty.py`** — Dificuldade sustentada por orçamento e solvers observados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

197. **CRIAR `src/nablamath/knowledge/curriculum.py`** — Currículos científicos com diversidade e utilidade medida. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

198. **CRIAR `src/nablamath/verification/independence.py`** — Política de independência entre proponente, solver e avaliador. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

199. **CRIAR `src/nablamath/verification/evidence.py`** — Tipos e obrigatoriedade de evidência para diferentes alegações. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

200. **CRIAR `src/nablamath/verification/consensus.py`** — Consenso sobre recibos sem confundi-lo com verdade científica. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

201. **CRIAR `src/nablamath/evaluation/calibration.py`** — Curvas de calibração, generalização e análise de robustez. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

202. **CRIAR `src/nablamath/evaluation/ablation.py`** — Ablation com avaliador congelado e comparação justa. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

203. **CRIAR `src/nablamath/training/snapshot.py`** — Snapshots imutáveis de modelos e dados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

204. **CRIAR `src/nablamath/training/mixture.py`** — Misturas de dados e auditoria de contribuição por fonte. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

205. **CRIAR `src/nablamath/training/lineage.py`** — Linhagem de checkpoints, pesos e corpus de treinamento. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

206. **CRIAR `benchmarks/private/README.md`** — Processos para holdouts administrados por avaliadores externos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

207. **CRIAR `benchmarks/contamination/README.md`** — Testes adversariais e padrões de vazamento de dados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

208. **CRIAR `protocol/fixtures/cross-language/README.md`** — Vetores normativos verificados por SDKs C/C++/Rust/TS/Python. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

209. **CRIAR `src/nablamath/singularity/evaluation/generalization.py`** — Benchmark multidisciplinar de transferibilidade sem declarar AGI. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

210. **CRIAR `src/nablamath/singularity/evaluation/safety.py`** — Avaliar autonomia, permissões e falhas por agente. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

211. **CRIAR `src/nablamath/singularity/evaluation/long_horizon.py`** — Avaliação de projetos científicos longos com intervenção humana. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

212. **CRIAR `docs/future/F13_OPEN_RESEARCH.md`** — Requisitos prospectivos abertos e governança de descobertas pós-2056. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

213. **CRIAR `docs/future/2035_2045_2056_criteria.md`** — Critérios técnicos revisáveis com indicadores de sucesso/falha. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

## Cronograma por janelas

| Janela | Produto verificável | Não confundir com |
|---|---|---|
| 2026–2027 | contratos semânticos, APIs estáveis, suíte de verificação independente, UI básica confiável | matemática universal |
| 2027–2029 | Forge, dificuldade calibrada, Lean/SMT amplos e dataset em escala controlada | ganho em IA já demonstrado |
| 2029–2032 | publicação integrada, datasets avaliados, benchmark de generalização | validade externa não medida |
| 2030–2035 | Worlds, modelos calibrados, agentes e aprendizagem multimodal | simulador universal/AGI |
| 2033–2042 | Discovery, revisão independente, evolução de algoritmos com gates e rollback | descoberta garantida/RSI geral |
| 2042–2048 | múltiplas disciplinas e instrumentação com validação empírica | equivalência a todos os softwares industriais |
| 2048–2056+ | federação institucional, conhecimento vivo, interoperabilidade e continuidade de pesquisa | ciência terminada |

## Como transformar o roteiro em critérios fechados

1. Declarar versão e limites do perfil científico por capacidade (F1...F13).
2. Registrar requisito e arquivo(s) responsáveis, com dono técnico/científico.
3. Construir suíte automatizada e avaliação externa pré-registrada antes de observar os resultados finais.
4. Medir correção, independência, custo, integração, segurança, operação e generalização.
5. Publicar artefatos, falhas, incertezas e revisão por pesquisadores que não controlam a implementação.
6. Concluir somente o **perfil validado**; manter o horizonte 2056+ revisável e aberto.

## Documentos originais e fontes de verificação

- https://github.com/3scud3r0/Nabla/blob/main/vision.md
- https://github.com/3scud3r0/Nabla/blob/main/docs/PLANO_MESTRE_2026_2056.md
- https://github.com/3scud3r0/Nabla/blob/main/docs/audits/PHASES_1_12_COMPLETION_BACKLOG.md
- https://github.com/3scud3r0/Nabla/blob/main/docs/audits/FRONTIER_LAB_SIMULATION_2026_10_15.md
- https://github.com/3scud3r0/Nabla/blob/main/docs/audits/FILE_INVENTORY.md

**Limitação:** o roteiro cobre *todas as áreas/categorias* da árvore com critérios-alvo. O detalhamento enumerado de cada um dos 1.070 arquivos, inclusive resultados e legados, é produzido pelo gerador ligado a este documento; não é uma auditoria linha a linha de cada blob.
