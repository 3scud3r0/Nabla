# Nabla — o que falta para concluir a visão

Snapshot da execução local de 16/10/2026. Gere uma nova execução com
`python tools/vision_readiness.py`; este arquivo preserva resultados históricos.
O CI recebeu posteriormente a preparação de Lean/Mathlib; sua execução remota
ainda não foi verificada nesta medição.

Execução UTC: 2026-10-16T12:53:28.818460+00:00

**Prontidão científica integral não estabelecida.** Não existe percentual confiável calculado por linhas de código ou quantidade de testes.

Testes observados: {"skipped": 5, "passed": 2060}.
Estados declarados na matriz: {"partial": 213}.

## Execução atual

| Etapa | Resultado | Registro |
|---|---|---|
| roadmap | passed | [roadmap.log](roadmap.log.json) |
| contracts | passed | [contracts.log](contracts.log.json) |
| preservation | passed | [preservation.log](preservation.log.json) |
| bundle | passed | [bundle.log](bundle.log.json) |
| pytest | passed | [pytest.log](pytest.log.json) |
| longley | passed | [longley.log](longley.log.json) |
| laboratory | failed | [laboratory.log](laboratory.log.json) |
| calibration | passed | [calibration.log](calibration.log.json) |

## Benchmarks medidos nesta execução

- longley: `{"passed": true, "coefficient_relative_errors": [4.809301313616032e-16, 3.339565919448882e-16, 1.6616857752536018e-17, 2.432568075499757e-15, 1.9119660494962588e-15, 1.447066426569869e-17, 1.0087900331830022e-15], "sse_relative_error": 4.513231906092073e-16}`
- calibration: `{"finite_checks_passed": true, "fully_calibrated_and_ready": false}`
- laboratory: `{"all_jobs_passed": false, "selected_phase_profiles_passed": 2, "vision_completion_percent": null}`
- original_workload: `{"test-exact-reference": {"accuracy": 1.0, "evaluation_id": "b31a8168cb05e46a8e435ecf6ef734d74c28190e2a3d8ce4d95e2788aa0f889a", "successes": 48, "total": 48}, "test-nearest-all": {"accuracy": 0.0, "evaluation_id": "c6349bcf13c61a43631d8a4bbae3b5cad9fe06274c27a43d301ddc6205131035", "successes": 0, "total": 48}, "test-nearest-text": {"accuracy": 0.0, "evaluation_id": "f5e41e9fba719195ca13ca910ed6d0dd97d575215ecbea843b64021252db615c", "successes": 0, "total": 48}, "validation-exact-reference": {"accuracy": 1.0, "evaluation_id": "673a083067fcbfb7e5a6bfbe17cb421fc2115290dbce0c84be39968934304b88", "successes": 48, "total": 48}, "validation-nearest-all": {"accuracy": 0.0, "evaluation_id": "4d578caea2bededb8342aeb6a9298349b524d504599adda925bba924d71afbfb", "successes": 0, "total": 48}, "validation-nearest-text": {"accuracy": 0.0, "evaluation_id": "589b114ab7e1730e3f72a38750c59359b8435db73c73761acb071a32964ab65f", "successes": 0, "total": 48}}`

Testes pulados não são aprovação. Referências ausentes não são testes executados. Rótulos de revisão não autenticam identidade.

## Todos os 213 critérios e lacunas

### 001 — `src/nablamath/core/`

**P0 · F1–F12**: unificar AST/IR, tipos, unidades, precisão, domínios e contratos semânticos; garantir serialização canônica, invariantes e migração. **Concluído quando:** testes de propriedades, unidades, condições de domínio, compatibilidade e round-trip.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_scientific_artifact.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 002 — `src/nablamath/schema/`

**P0 · F0–F12**: versionar e validar esquemas de problema, expressão, experimento, etapa, evidência e artefato; rejeitar ambiguidades e mudanças silenciosas. **Concluído quando:** golden fixtures, migrações, validação adversarial e interop.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_semantic_contracts.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 003 — `src/nablamath/calc/`

**P1 · F1**: ampliar catálogo e sessão científica com operações gerais, diferenciação, rastreamento e erros certificados. **Concluído quando:** comparações externas, exemplos adversariais e especificações por operação.

**Estado declarado:** partial.

**Escopo restante registrado:** Existing audited calculator catalog/session provides exact operations, domain obligations, request/result hashing and declared limitations; mapped with regression tests this round. Broad external per-operation certification remains incomplete.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_phase1_calculator.py`: {"passed": 15}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 004 — `src/nablamath/symbolic/`

**P1 · F1–F3**: expandir parser/reescrita/e-graphs, funções transcendentes, hipóteses, integrais e certificados de transformação. **Concluído quando:** provas ou verificação independente de regras, preservação de domínio e benchmarks.

**Estado declarado:** partial.

**Escopo restante registrado:** New independent finite exact-rational rewrite rule falsifier checks domain mismatch and value mismatch with adversarial tests. Finite scalar grid is not proof for composite expressions or all transcendental rules.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_math_compiler.py`: {"passed": 42}
- `tests/test_declarative_egraph.py`: {"passed": 4}
- `tests/test_egraph.py`: {"passed": 7}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 005 — `src/nablamath/numeric/`

**P1 · F1/F7**: implementar solvers numéricos modernos, condicionamento, tolerâncias, intervalos, limites de recursos e diagnósticos. **Concluído quando:** convergência, referências NIST/analíticas, escalonamento e precisão.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 006 — `src/nablamath/math/`

**P1 · F1–F3/F11**: aprofundar a área matemática do módulo, documentar domínio e limitações, adicionar algoritmos gerais e referências competitivas. **Concluído quando:** propriedades matemáticas, benchmarks independentes, provas quando cabíveis e testes de fronteira.

**Estado declarado:** partial.

**Escopo restante registrado:** Existing bounded rational integration certificates, Lambert W, exact PLU and bounded factorization now explicitly mapped with regression evidence. Not arbitrary Risch nor general competitive mathematics suite.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_math_extensions.py`: {"passed": 32}
- `tests/test_roadmap_integration_mesh.py`: {"passed": 56}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 007 — `src/nablamath/autodiff/`

**P1 · F1/F7/F8**: expandir forward/reverse AD para tensores e aplicações, broadcasting, controle de gradiente, jacobianas e Hessianas. **Concluído quando:** grad-check, precisão, memória, comparação com JAX/PyTorch e exemplos físicos.

**Estado declarado:** partial.

**Escopo restante registrado:** New analytic dense second-order tensor AD includes broadcasting, reductions, matrix products, transcendental functions and stop-gradient; SymPy32 Hessian comparisons and reverse-gradient finite differences. Limit64 input coordinates; O(n²m) memory; no PyTorch/JAX comparison claim.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_math_compiler.py`: {"passed": 42}
- `tests/benchmark/test_math_comparison.py`: {"passed": 2}
- `tests/test_tensor_autodiff.py`: {"passed": 3}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 008 — `src/nablamath/forge/`

**P1 · F2**: ampliar construção inversa, deduplicação, diversidade, geração composicional, controle de dificuldade e verificação. **Concluído quando:** corpus inédito, solvers competidores, taxas de validade, novidade estrutural e dificuldade calibrada.

**Estado declarado:** partial.

**Escopo restante registrado:** Local deterministic construction, composition and difficulty evidence; genuinely novel external corpus and competing solver calibration remain external acceptance.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_forge_discovery.py`: {"passed": 13}
- `tests/test_phase2_forge.py`: {"passed": 11}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 009 — `src/nablamath/verify/`

**P0 · F2–F12**: separar proponente e verificador, reexecutar provas/testemunhos, integrar obrigações e linhagem de evidências. **Concluído quando:** falsificações induzidas rejeitadas e evidências reexecutáveis em ambiente limpo.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_scientific_artifact.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 010 — `src/nablamath/formal/`

**P1 · F3**: expandir cobertura Lean/SMT, autoformalização assistida revisada, certificados, lógica e rastreio de axiomas. **Concluído quando:** kernel independente, hipóteses explícitas, correspondência humana auditada e replay.

**Estado declarado:** partial.

**Escopo restante registrado:** Existing reviewed controlled-language autoformalization and bounded Lean/SMT portfolios/replay explicitly mapped with tests. No arbitrary natural-language translation; external human correspondence audit and Mathlib compilation remain unfulfilled.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_formal_workflows.py`: {"passed": 46}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 011 — `src/nablamath/falsifier/`

**P1 · F3/F9**: expandir busca/minimização de contraexemplos, propriedades, domínio e diagnósticos verificáveis. **Concluído quando:** falsificações conhecidas recuperadas e ausência de falso teorema.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded property/counterexample checks are not completeness for arbitrary theorem falsification.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_forge_discovery.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 012 — `src/nablamath/gpu/`

**P2 · F1–F10**: substituir caminhos de referência por kernels reais opcionais, com fallback CPU, profiling, uso de VRAM e verificação numérica. **Concluído quando:** benchmarks em hardware identificado, equivalência e provas de ganho custo/energia.

**Estado declarado:** partial.

**Escopo restante registrado:** CUDA hardware absent; kernel compilation/execution, speedup and energy require independent real-device runs. Exact CPU oracle checks every device result.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded
- Referenced tests skipped; prerequisites or evidence remain missing

**Testes vinculados nesta execução:**

- `tests/benchmark/test_gpu_real_hardware.py`: {"skipped": 2}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 013 — `src/nablamath/compiler/`

**P2 · F1–F10**: estabilizar IR/compilação, otimização semântica, backends e agendamento distribuído. **Concluído quando:** equivalência entre backends, determinismo e custos mensurados.

**Estado declarado:** partial.

**Escopo restante registrado:** New strict versioned IR decoder validates canonical rational literals, instruction order, bounds and literal integer exponents, preventing silent fractional exponent truncation. Exact Python interpreter equivalence checked128 independent SymPy cases. Optional JAX remains separately declared; distributed scheduling/performance not validated.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_math_compiler.py`: {"passed": 42}
- `tests/test_compiler_backends.py`: {"passed": 4}
- `tests/benchmark/test_math_comparison.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 014 — `src/nablamath/physics/`

**P1 · F7/F11**: ampliar modelos físicos além das referências, incluindo condições de contorno, incerteza, calibração e validação observacional. **Concluído quando:** casos manufaturados, séries de convergência, dados reais e revisão disciplinar.

**Estado declarado:** partial.

**Escopo restante registrado:** Stationary no-slip channel reduction and existing 1D Euler reference only; general 2D nonperiodic Navier-Stokes, laboratory data and disciplinary review remain.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_physics_gpu.py`: {"passed": 40}
- `tests/test_roadmap_physics_extensions.py`: {"passed": 93}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 015 — `src/nablamath/worlds/`

**P1 · F7**: generalizar modelos de EDO/EDP, malhas, eventos, rigidez, multiphysics, controle de erro e replay. **Concluído quando:** benchmarks por fenômeno, estabilidade/conservação, confronto com medidas e reproducibilidade.

**Estado declarado:** partial.

**Escopo restante registrado:** Existing bounded adaptive integration/mesh profiles; stiff general multiphysics and independent observations remain.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_worlds_observations.py`: {"passed": 17}
- `tests/test_phase7_worlds.py`: {"passed": 5}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 016 — `src/nablamath/graphics/`

**P2 · F4**: implementar cenas e geometria mais gerais, renderizações científicas auditáveis, qualidade visual e exportação multimodal. **Concluído quando:** validação geométrica, inspeção de imagens, performance e semântica das figuras.

**Estado declarado:** partial.

**Escopo restante registrado:** Multimodal exact sample exports with semantic replay; geometry, pixel fidelity, performance and external visual inspection remain bounded to existing profiles.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_product.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 017 — `src/nablamath/viz/`

**P2 · F4/F5**: unificar gráficos e animações com dados, escalas, unidades, acessibilidade e metadados de incerteza. **Concluído quando:** replay pixel/semântico, revisão visual e testes de legibilidade.

**Estado declarado:** partial.

**Escopo restante registrado:** Accessible sample tables, exact units and declared uncertainty; discrete-frame animation only; human legibility and continuous interpolation unvalidated.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_product.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 018 — `src/nablamath/documents/`

**P1 · F5**: completar AST editorial, bibliografia, referências, tabelas, figuras e exportações sem alegações sem evidência. **Concluído quando:** compilação dos formatos, inspeção de páginas e revisão editorial externa.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_scientific_artifact.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 019 — `src/nablamath/reports/`

**P2 · F5**: consolidar relatórios com documentos canônicos, tabelas, passos, provas e vínculos verificáveis. **Concluído quando:** PDF/LaTeX com numeração e integridade reexecutável.

**Estado declarado:** partial.

**Escopo restante registrado:** Evidence hashes, deterministic object numbering and byte-bound HTML/LaTeX/Typst exports; tests compile real templates via available Typst and pdflatex; scientific endorsement and visual inspection not inferred.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_product.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 020 — `src/nablamath/dataset/`

**P1 · F6**: migrar APIs antigas para contrato canônico, governar licenças, splits, qualidade, deduplicação e proveniência. **Concluído quando:** migrações compatíveis, integridade por amostra, testes de contaminação.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_scientific_artifact.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 021 — `src/nablamath/datasets/`

**P1 · F6/F8**: unificar modelos de registros e alinhar modalidades, linhagem, licenças, política de splits e evidência multimodal. **Concluído quando:** auditoria independente de corpora e ganho ou resultado negativo reproduzível.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 022 — `src/nablamath/export/`

**P1 · F5/F6/F12**: publicar bundles interoperáveis versionados com manifestos, integridade, licenças, privacidade e reversibilidade. **Concluído quando:** import/export/verify em ambiente isolado e controles de adulteração.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_scientific_artifact.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 023 — `src/nablamath/training/`

**P1 · F8**: treinar modelos mais capazes, estabelecer avaliações externas, ablações, curricula, contaminação e custo de treino. **Concluído quando:** comparação com/sem Nabla em holdouts verdadeiramente inéditos e ICs pré-especificados.

**Estado declarado:** partial.

**Escopo restante registrado:** Real bounded supervised numerical reasoning fit and synthetic family transfer; no frontier model gain or independently authored unseen benchmark established.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_learning.py`: {"passed": 15}
- `tests/benchmark/test_holdout_generalization.py`: {"passed": 7}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 024 — `src/nablamath/evaluation/`

**P0 · F6/F8/F10**: criar avaliador congelado independente de proponente, impedir vazamento transitivo e fornecer decisão estatística auditável. **Concluído quando:** testes adversariais com adulteração e holdout inacessível ao proponente.

**Estado declarado:** partial.

**Escopo restante registrado:** External operator isolation, authenticated independent review, private holdout administration and full original acceptance remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/evaluation/test_frozen.py`: {"passed": 30}

**Evidências registradas:** `docs/audits/FROZEN_EVALUATION_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 025 — `src/nablamath/agents/`

**P1 · F8**: planejamento científico mais capaz, permissões por capacidade, orçamentos, checkpoints, orquestração e isolamento real. **Concluído quando:** ataques simulados, replay, falha segura e custos por tarefa.

**Estado declarado:** partial.

**Escopo restante registrado:** Existing consented trusted-tool checkpoints, cancellation and process deadlines are tested. Hostile-code OS isolation and externally authenticated authority remain unavailable; arbitrary code stays disabled.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/security/test_agent_sandbox.py`: {"passed": 42}
- `tests/test_roadmap_agent_controls.py`: {"passed": 9}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 026 — `src/nablamath/discovery/`

**P1 · F9**: ampliar gramáticas, busca de leis/teoremas, experimentos discriminantes e revisão bibliográfica. **Concluído quando:** novidade avaliada externamente, reprodução e registro de descobertas nulas/refutadas.

**Estado declarado:** partial.

**Escopo restante registrado:** Curated supplied snapshots; reviewer identity and global scientific novelty are not authenticated.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_learning.py`: {"passed": 15}
- `tests/science/test_independent_discovery.py`: {"passed": 3}
- `tests/test_phase9_discovery.py`: {"passed": 5}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 027 — `src/nablamath/evolution/`

**P1 · F10**: permitir propostas de algoritmos novos sob gates isolados, rollback, estatística e autoridade distinta. **Concluído quando:** ganhos contra baseline forte em avaliações congeladas e monitoramento de regressões.

**Estado declarado:** partial.

**Escopo restante registrado:** Closed declarative proposals and local rollback; not arbitrary untrusted code sandboxing or externally measured robust algorithmic advances.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_phase10_evolution.py`: {"passed": 4}
- `tests/security/test_agent_sandbox.py`: {"passed": 42}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 028 — `src/nablamath/domains/`

**P1 · F11**: aprofundar modelos disciplinares e suas integrações com instrumentação, medições e especialistas. **Concluído quando:** validação com observações reais e critérios próprios por disciplina.

**Estado declarado:** partial.

**Escopo restante registrado:** Historical rounded Mercury reference and caller-supplied measurements are not independent provenance authentication, discipline-wide validation, or specialist review.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_worlds_observations.py`: {"passed": 17}
- `tests/science/test_observational_validation.py`: {"passed": 1}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 029 — `src/nablamath/knowledge/`

**P1 · F9/F12**: reconciliar claims, evidências, versões, revisão, retração, federação, identidades e conflitos. **Concluído quando:** replay institucional multioperador, reconciliação correta e autenticação independente.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 030 — `src/nablamath/network/`

**P2 · F12**: consolidar objetos, manifestos, recibos e protocolos P2P com limites e consistência. **Concluído quando:** testes de rede real, falhas parciais e compatibilidade retroativa.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_federation.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 031 — `src/nablamath/p2p/`

**P2 · F12**: implementar transporte autenticado, descoberta, rate limits, quarentena e recuperação de peers. **Concluído quando:** rede adversarial e latência/perda medidas.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_eclipse.py`: {"passed": 1}
- `tests/network/test_sybil.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 032 — `src/nablamath/node/`

**P2 · F12**: operacionalizar nó consentido, controle de recursos, tarefas, verificação e workspace. **Concluído quando:** reprodução em máquinas distintas e telemetria auditável.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_federation.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 033 — `src/nablamath/coordination/`

**P2 · F12**: unificar coordenação local/Merkle com serviços distribuídos e provas de consistência. **Concluído quando:** invariantes sob concorrência, reconexão e restauração.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_coordinator_api.py`: {"passed": 6}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 034 — `src/nablamath/pipeline/`

**P0 · F0–F12**: ligar todos os estágios científicos em pipeline transacional, versionado e reexecutável com cache seguro. **Concluído quando:** um ScientificArtifact ponta a ponta com adulteração de cada vínculo rejeitada.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_scientific_artifact.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 035 — `src/nablamath/singularity/`

**P3 · F8–F13**: converter protótipos de cognição/memória/engenharia/agentes em componentes mensuráveis, governados e testáveis sem alegar AGI. **Concluído quando:** benchmarks abertos/fechados, segurança, ganhos transferíveis e avaliações independentes.

**Estado declarado:** partial.

**Escopo restante registrado:** Transfer threshold gate recomputes reported outcomes; local synthetic cases do not establish AGI, independent evaluation, or domain transfer in real science.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_singularity_lab.py`: {"passed": 6}
- `tests/benchmark/test_holdout_generalization.py`: {"passed": 7}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 036 — `src/nablamath/adapters/`

**P2 · F1/F7/F11**: tornar integração NumPy/SciPy/SymPy/Blender/instrumentos explícita, compatível, segura e bidirecional. **Concluído quando:** testes com versões fixadas e coerência de unidades/dados.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded numeric NumPy wire validation and optional SciPy interoperability; full cross-tool compatibility and upstream version matrix remain.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_physics_gpu.py`: {"passed": 40}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 037 — `src/nablamath/store/`

**P0 · F0–F12**: fortalecer migrations, backups, armazenamento de blobs, integridade e política de retenção. **Concluído quando:** restauração/falha de energia/concorrrência, recovery e compatibilidade.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_scientific_artifact.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 038 — `src/nablamath/publisher/`

**P2 · F5/F6**: governar publicação autorizada e assinada com direitos por artefato e política de revogação. **Concluído quando:** dry-run, idempotência e testes em destino de homologação.

**Estado declarado:** partial.

**Escopo restante registrado:** Ed25519 authorization binds exact artifact bytes and destination; opt-in rights declaration, revocation, dry-run idempotency. State is process-local; no remote staging publication performed and rights are operator declarations.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_product.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 039 — `src/nablamath/benchmarks/`

**P0 · F1–F12**: pré-registrar protocolos e incluir baselines independentes, métricas e falhas reexecutáveis. **Concluído quando:** replicação por terceiros, holdouts novos e relatórios negativos.

**Estado declarado:** partial.

**Escopo restante registrado:** Preregistered fixed model/cohort/metric/stopping-rule ledger and exact descriptive paired comparisons. Third-party replication, private novel holdout, inferential independence and model execution identity are not established.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_registered_comparison.py`: {"passed": 15}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 040 — `src/nablamath/desktop/`

**P2 · F1–F12**: expor workflows científicos completos, revisão humana, datasets e rastreio em UX local segura. **Concluído quando:** testes acessibilidade/usabilidade e equivalência CLI/API.

**Estado declarado:** partial.

**Escopo restante registrado:** Complete exact-instance experiment/evidence/report workflow in loopback UI with consent. Existing UI covers more bounded operations, not all scientific subsystems; human accessibility/usability review outstanding.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_product.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 041 — `src/nablamath/`

**P1 · F0–F12**: manter contratos, CLI, compatibilidade e workflows integrados; eliminar caminhos paralelos sem migração. **Concluído quando:** smokes da API pública, documentação e integração de ponta a ponta.

**Estado declarado:** partial.

**Escopo restante registrado:** CLI exposes finite contracts and refusals; Lean support pin aligned. The open-ended public workflow and compatibility matrix still require releases and cross-platform external verification.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_public_contracts.py`: {"passed": 28}
- `tests/integration/test_scientific_artifact.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 042 — `tests/`

**P0 · F0–F13**: expandir o teste deste componente para casos positivos/negativos, propriedade, integração, segurança e benchmarks. **Concluído quando:** CI em Linux/Windows/macOS, fixture congelado e evidência em release.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_semantic_contracts.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 043 — `lean/`

**P1 · F3**: ampliar demonstrações Lean além dos fragmentos atuais; pin da toolchain, livre de sorry/admit e revisão de tradução. **Concluído quando:** compilação reproduzível, kernel verificando teoremas e auditoria de axiomas.

**Estado declarado:** partial.

**Escopo restante registrado:** Six new kernel-only Lean4.34.0 theorems compiled successfully and #print axioms reports zero dependencies for each. Full imported Mathlib project still unavailable; no Python translator correspondence proof.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_math_compiler.py`: {"passed": 42}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 044 — `protocol/`

**P0 · F0/F12**: padronizar codificação canônica, schemas de objetos/recibos e interop de clientes. **Concluído quando:** golden vectors e testes cruzados C/C++/Rust/Python.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_interop.py`: {"passed": 6}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 045 — `sdk/`

**P2 · F12**: evoluir parsers de frações para SDKs científicos e transporte autenticado interoperáveis. **Concluído quando:** conformidade protocolar, ABI/API estáveis e fuzzing.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_interop.py`: {"passed": 6}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 046 — `services/`

**P2 · F12**: evoluir protótipos locais para serviços autenticados, escaláveis e tolerantes a falhas. **Concluído quando:** testes de rede entre hosts, segurança e monitoramento.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_coordinator_api.py`: {"passed": 6}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 047 — `.github/workflows/`

**P0 · F0–F13**: corrigir dependências, pin/atualizar actions, garantir CI matriz, segurança de supply chain e releases condicionadas. **Concluído quando:** nenhum check obrigatório falho e atestados por commit/release.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_scientific_artifact.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 048 — `docs/audits/`

**P0 · F0–F13**: registrar baseline, falhas, incertezas, remediações e evidências separando medições de opiniões. **Concluído quando:** auditoria independente e referências imutáveis por commit.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_contract.py`: {"passed": 12}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 049 — `docs/history/`

**P3 · Histórico**: preservar material original sem confundir aspiração histórica com implementação. **Concluído quando:** hash e índice de origem validados.

**Estado declarado:** partial.

**Escopo restante registrado:** Historical bytes and declared repository commit pinned; original claims not treated as delivered behavior.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_release.py`: {"passed": 33}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 050 — `docs/`

**P1 · F0–F13**: atualizar especificação, critérios, instruções e limites após mudanças verificadas. **Concluído quando:** links, exemplos e status verificáveis por versão.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_contract.py`: {"passed": 12}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 051 — `benchmarks/results/`

**P0 · Evidência**: preservar resultado congelado, inclusive falhas e modelos negativos; criar novos resultados em campanhas distintas. **Concluído quando:** SHA-256, protocolo, licença, replay semântico e cadeia de custódia.

**Estado declarado:** partial.

**Escopo restante registrado:** Frozen result bytes include negative results; campaign hash chain and canonical JSON semantic check do not reexecute scientific experiment or authenticate custodian.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_release.py`: {"passed": 33}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 052 — `benchmarks/fixtures/`

**P0 · Evidência**: manter fixture original e fonte licenciada; incluir novas referências identificadas e imutáveis. **Concluído quando:** hash, proveniência e correspondência com referências independentes.

**Estado declarado:** partial.

**Escopo restante registrado:** Longley mirror commit, three SHA256 files, source paths, license and reference checked offline; no new independent publisher retrieval.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_release.py`: {"passed": 33}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 053 — `benchmarks/`

**P1 · F1–F12**: definir protocolos e baselines comparativos novos sem reescrever resultados históricos. **Concluído quando:** reexecução, métricas estatísticas e replicação.

**Estado declarado:** partial.

**Escopo restante registrado:** Preregistered fixed model/cohort/metric/stopping-rule ledger and exact descriptive paired comparisons. Third-party replication, private novel holdout, inferential independence and model execution identity are not established.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_registered_comparison.py`: {"passed": 15}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 054 — `legacy/`

**P3 · Histórico**: congelar e catalogar código legado; migrar somente funcionalidades comprovadas para src/ com testes. **Concluído quando:** arquivos preservados por hash e nenhuma fonte dupla em produção.

**Estado declarado:** partial.

**Escopo restante registrado:** Legacy bytes frozen; AST audit rejects explicit production legacy/archive imports; dynamic imports not comprehensively audited.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_release.py`: {"passed": 33}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 055 — `website/`

**P2 · Produto**: substituir indicadores promocionais por status derivado das evidências, melhorar transparência e documentação. **Concluído quando:** testes de interface, métricas rastreáveis, privacidade e acessibilidade.

**Estado declarado:** partial.

**Escopo restante registrado:** Built site status derived from actual213 matrix, no promotional completion inference. No live deployment or human accessibility review performed.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_product.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 056 — `tools/`

**P0 · F0–F13**: ampliar auditoria e automação de reprodução, sem atribuir completude por quantidade de arquivos. **Concluído quando:** reexecução em ambiente limpo, tratamento de falha e relatórios versionados.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_contract.py`: {"passed": 12}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 057 — `scripts/`

**P1 · F0**: tornar instalação/importação idempotentes, reexecutáveis e seguros em todas as plataformas. **Concluído quando:** testes de recuperação e compatibilidade de arquivos históricos.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned bounded ZIP import is idempotent, refuses historical overwrite, case/path/symlink collisions and preserves destination on failure; tested on current Linux only.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_release.py`: {"passed": 33}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 058 — `examples/`

**P2 · Documentação**: criar exemplos reproduzíveis de pipelines completos e documentar limites. **Concluído quando:** execução automatizada de cada exemplo publicado.

**Estado declarado:** partial.

**Escopo restante registrado:** All five published Python examples auto-executed in isolated temporary outputs; fixtures are synthetic and not evidence of scientific discovery.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_product.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 059 — `templates/`

**P2 · F5**: ampliar modelos de relatórios com origem de cada alegação, dados e revisão editorial. **Concluído quando:** compilação de todos os templates e conferência visual.

**Estado declarado:** partial.

**Escopo restante registrado:** Three canonical report templates exported and compiled with available real Typst and LaTeX compilers; external visual/editorial review not performed.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_product.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 060 — `packaging/`

**P1 · Produto**: assegurar instaladores assinados quando possível, atestados, atualização segura e desinstalação reversível. **Concluído quando:** instalação/upgrade/downgrade em máquinas limpas.

**Estado declarado:** partial.

**Escopo restante registrado:** Real offline clean-venv synthetic package install, upgrade, downgrade, repair, uninstall and restoration tested on current Linux; no Windows/macOS, signed installer or publisher authenticity claim.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_release.py`: {"passed": 33}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 061 — `.github/workflows/ci.yml`

intervenção específica: corrigir falha confirmada: instalar .[test] antes do unittest/pytest; executar também lint/build website. **Aceite:** job NablaMath CI aprovado no commit auditado.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_scientific_artifact.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 062 — `pyproject.toml`

intervenção específica: alinhar dependências opcionais, versões, entrypoints, perfis Python, metadados, SBOM e origem do wheel. **Aceite:** build e importação isolada, matriz de versões e release alinhada.

**Estado declarado:** partial.

**Escopo restante registrado:** SPDX 2.3 wheel SBOM source commit declaration, metadata, optional requirement and SHA binding reuse existing wheel verifier; source origin is caller-declared, Python version matrix not run.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_release.py`: {"passed": 33}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 063 — `README.md`

intervenção específica: documentar limites reais, quickstart, módulos avaliados, indicadores reproduzíveis e diferença visão/entrega. **Aceite:** todos os links e comandos revisados por CI.

**Estado declarado:** partial.

**Escopo restante registrado:** Current evidence and historical estimates distinguished, contract/link checks added to CI. Interactive browser startup, every optional external service and all platform commands require independent runtime review.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_public_contracts.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 064 — `vision.md`

intervenção específica: converter aspirações 2026–2056+ em perfis versionados sem apagar o horizonte aberto; explicitar hipóteses e critérios de fechamento. **Aceite:** matriz bidirecional visão→requisitos→testes→evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Machine-checked original requirement/phase/evidence references and finite-domain contract. This is consistent local traceability, not proof of all original algorithms, external review, costs, closed issues, or scientific phase completion. Historical backlog items remain individually unresolved where acceptance evidence is missing.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_public_contracts.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 065 — `description.md`

intervenção específica: sincronizar a descrição atual com evidências e release; evitar alegar avanços futuros como atuais. **Aceite:** toda alegação inclui versão e comprovação.

**Estado declarado:** partial.

**Escopo restante registrado:** Machine-checked original requirement/phase/evidence references and finite-domain contract. This is consistent local traceability, not proof of all original algorithms, external review, costs, closed issues, or scientific phase completion. Historical backlog items remain individually unresolved where acceptance evidence is missing.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_public_contracts.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 066 — `docs/PLANO_MESTRE_2026_2056.md`

intervenção específica: manter contrato integrado, dependências, perfis de recursos e decisões por fase; atualizar custos e riscos. **Aceite:** alinhamento verificável entre metas, issues e entregas.

**Estado declarado:** partial.

**Escopo restante registrado:** Machine-checked original requirement/phase/evidence references and finite-domain contract. This is consistent local traceability, not proof of all original algorithms, external review, costs, closed issues, or scientific phase completion. Historical backlog items remain individually unresolved where acceptance evidence is missing.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_public_contracts.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 067 — `docs/audits/PHASES_1_12_COMPLETION_BACKLOG.md`

intervenção específica: mapear os 104 itens aos módulos responsáveis, testes e evidências; adicionar fases F0/F13 e perfis de avanço posteriores. **Aceite:** cada requisito tem estado e prova de aceite.

**Estado declarado:** partial.

**Escopo restante registrado:** Machine-checked original requirement/phase/evidence references and finite-domain contract. This is consistent local traceability, not proof of all original algorithms, external review, costs, closed issues, or scientific phase completion. Historical backlog items remain individually unresolved where acceptance evidence is missing.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_public_contracts.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 068 — `docs/ARCHITECTURE_AND_ACCEPTANCE.md`

intervenção específica: materializar os critérios de render, física, relatórios, formalização e estabilidade em testes automatizados. **Aceite:** nenhum requisito crítico pendente sem sinalização.

**Estado declarado:** partial.

**Escopo restante registrado:** Machine-checked original requirement/phase/evidence references and finite-domain contract. This is consistent local traceability, not proof of all original algorithms, external review, costs, closed issues, or scientific phase completion. Historical backlog items remain individually unresolved where acceptance evidence is missing.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_public_contracts.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 069 — `docs/MATHEMATICS_COMPLETION_AUDIT.md`

intervenção específica: verificar algoritmos matemáticos gerais faltantes e manter recusas explícitas em domínios não cobertos. **Aceite:** matriz por classe de problema, benchmark e prova.

**Estado declarado:** partial.

**Escopo restante registrado:** Machine-checked original requirement/phase/evidence references and finite-domain contract. This is consistent local traceability, not proof of all original algorithms, external review, costs, closed issues, or scientific phase completion. Historical backlog items remain individually unresolved where acceptance evidence is missing.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_public_contracts.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 070 — `src/nablamath/agents/sandbox.py`

intervenção específica: preservar proibição de código não confiável até existir sandbox real; não trocar bloqueio por eval/subprocess sem isolamento. **Aceite:** ataques e escapes bloqueados em ambiente isolado.

**Estado declarado:** partial.

**Escopo restante registrado:** The existing complete prohibition of arbitrary code is preserved and verified; this is not execution of hostile code in a real OS sandbox. Escape-resistance certification remains blocked by that missing capability.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_agents.py`: {"passed": 1}
- `tests/security/test_agent_sandbox.py`: {"passed": 42}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 071 — `services/coordinator/app.py`

intervenção específica: expandir HTTP além de /health com auth, filas, quotas, auditoria, retries e cancelamentos. **Aceite:** integração inter-host, concorrência e testes de segurança.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_coordinator_api.py`: {"passed": 6}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 072 — `src/nablamath/desktop/app.py`

intervenção específica: migrar UI local limitada para interface integrada de todos os workflows sem abrir serviços inseguros. **Aceite:** E2E de um experimento completo com consentimento.

**Estado declarado:** partial.

**Escopo restante registrado:** Real loopback HTTP E2E exact experiment with explicit consent and byte-identical API/direct receipt. No unrestricted execution, remote publishing, or claim of all-workflow UI coverage.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_product.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 073 — `src/nablamath/physics/fluids/navier_stokes.py`

intervenção específica: ultrapassar solver 2D periódico de referência com fronteiras, discretizações robustas e validação experimental. **Aceite:** benchmarks CFD, convergência e erro verificado.

**Estado declarado:** partial.

**Escopo restante registrado:** Stationary no-slip channel reduction and existing 1D Euler reference only; general 2D nonperiodic Navier-Stokes, laboratory data and disciplinary review remain.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_physics_gpu.py`: {"passed": 40}
- `tests/test_roadmap_physics_extensions.py`: {"passed": 93}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 074 — `src/nablamath/physics/relativity/general.py`

intervenção específica: ampliar geometria Schwarzschild para tensores, geodésicas e perfis de GR definidos, não declarar solver geral prematuramente. **Aceite:** invariantes, testes de limite e confronto com referências.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded analytic spatially-flat perfect-fluid FLRW plus Schwarzschild; not general numerical Einstein solver; historical rounded Mercury comparison is not new experimental validation.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_physics_gpu.py`: {"passed": 40}
- `tests/science/test_observational_validation.py`: {"passed": 1}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 075 — `src/nablamath/gpu/cuda_f4_reduction.py`

intervenção específica: implementar backend CUDA/Triton verdadeiro e não atribuir aceleração ao fallback CPU. **Aceite:** speedup, hardware, exatidão e memória medidos.

**Estado declarado:** partial.

**Escopo restante registrado:** CUDA hardware absent; kernel compilation/execution, speedup and energy require independent real-device runs. Exact CPU oracle checks every device result.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded
- Referenced tests skipped; prerequisites or evidence remain missing

**Testes vinculados nesta execução:**

- `tests/benchmark/test_gpu_real_hardware.py`: {"skipped": 2}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 076 — `src/nablamath/discovery/novelty_screen.py`

intervenção específica: integrar busca bibliográfica externa curada e revisão independente; não equiparar ausência local à novidade. **Aceite:** rastreio de referências, falsos positivos e revisão.

**Estado declarado:** partial.

**Escopo restante registrado:** Traceable curated source/retrieval metadata and false-positive review; operator declarations only, no live comprehensive search or authenticated independent reviewers.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_learning.py`: {"passed": 15}
- `tests/science/test_independent_discovery.py`: {"passed": 3}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 077 — `src/nablamath/training/baselines.py`

intervenção específica: adicionar baselines fortes e métricas; manter vizinhos próximos como referência pequena, não como prova de ganho científico. **Aceite:** reprodução entre sementes, dados separados por família e comparação externa.

**Estado declarado:** partial.

**Escopo restante registrado:** Actual deterministic fitted linear baseline; stronger LLM baselines and real external benchmark comparisons remain unfulfilled.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_learning.py`: {"passed": 15}
- `tests/benchmark/test_holdout_generalization.py`: {"passed": 7}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 078 — `src/nablamath/training/multimodal_network.py`

intervenção específica: evoluir demonstração de equações/imagens para tarefas multimodais científicas relevantes com ablações. **Aceite:** ganho fora da distribuição em benchmarks congelados.

**Estado declarado:** partial.

**Escopo restante registrado:** Existing multimodal neural fit plus generic transfer protocol; no claimed OOD scientific multimodal gain.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_phase8_agents_training.py`: {"passed": 7}
- `tests/benchmark/test_holdout_generalization.py`: {"passed": 7}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 079 — `src/nablamath/evolution/search.py`

intervenção específica: substituir busca apenas Euler/RK4 por propostas algorítmicas mais amplas avaliadas isoladamente. **Aceite:** ganho robusto contra baseline forte e rollback reproduzível.

**Estado declarado:** partial.

**Escopo restante registrado:** Typed bounded proposals only; not general algorithm synthesis or demonstrated robust gain.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/security/test_agent_sandbox.py`: {"passed": 42}
- `tests/test_phase10_evolution.py`: {"passed": 4}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 080 — `math.txt`

intervenção específica: NÃO editar manualmente: reconstruir do gerador canônico após cada alteração do código. **Aceite:** tools/build_math_bundle.py --check aprovado.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_math_bundle.py`: {"passed": 3}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

### 081 — CRIAR `docs/acceptance/phase_profiles.md`

Definir perfis finitos F0–F13 e critérios versionados de aceite. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_contract.py`: {"passed": 12}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 082 — CRIAR `docs/acceptance/evidence_matrix.json`

Vincular requisito→teste→artefato→revisor→release. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_contract.py`: {"passed": 12}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 083 — CRIAR `docs/acceptance/scientific_capabilities.yaml`

Especificar domínios suportados, recusados e tolerâncias. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Versioned queryable finite domains, explicit refusals and exact tolerance declarations are validated locally. Independent scientific review and release-specific acceptance remain pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_public_contracts.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 084 — CRIAR `docs/governance/independent_review_policy.md`

Estabelecer revisores independentes e conflitos de interesse. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_policy_links.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 085 — CRIAR `docs/governance/scientific_claims_policy.md`

Distinguir formal, numérico, empírico, sintético e hipotético. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_policy_links.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 086 — CRIAR `docs/strategy/roadmap_2026_2056.json`

Versionar marcos, dependências e mudanças de escopo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_contract.py`: {"passed": 12}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 087 — CRIAR `docs/strategy/scientific_risk_register.md`

Gerenciar riscos científicos, operacionais e de segurança. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_policy_links.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 088 — CRIAR `docs/strategy/annual_reassessment.md`

Atualizar a visão sem fabricar conclusão. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_policy_links.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 089 — CRIAR `src/nablamath/core/scientific_artifact.py`

Unificar hipótese, problema, solução, provas, simulações, imagens, datasets e documentos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_scientific_artifact.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 090 — CRIAR `src/nablamath/core/semantic_contracts.py`

Definir invariantes canônicos independentes da representação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_semantic_contracts.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 091 — CRIAR `src/nablamath/core/migration_registry.py`

Versionar migração semântica de objetos científicos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_semantic_contracts.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 092 — CRIAR `src/nablamath/core/uncertainty.py`

Representar incerteza e sua propagação de modo rastreável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 093 — CRIAR `src/nablamath/math/calculus/transcendentals.py`

Generalizar funções elementares e restrições de ramo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_math_extensions.py`: {"passed": 32}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 094 — CRIAR `src/nablamath/math/calculus/risch.py`

Pesquisar integração simbólica abrangente sob domínios declarados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** General Risch integration and independent validation are not implemented.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_integration_mesh.py`: {"passed": 56}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 095 — CRIAR `src/nablamath/math/linear_algebra/exact_decompositions.py`

Adicionar decomposições e certificados algébricos mais amplos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_math_extensions.py`: {"passed": 32}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 096 — CRIAR `src/nablamath/math/number_theory/factorization_advanced.py`

Desenvolver fatoração avançada com validação independente. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_math_extensions.py`: {"passed": 32}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 097 — CRIAR `src/nablamath/math/algebra/galois.py`

Implementar estruturas e algoritmos de teoria de Galois delimitados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_algebra_logic.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 098 — CRIAR `src/nablamath/math/logic/smt_combination.py`

Pesquisar integração de teorias e certificados SMT. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_algebra_logic.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 099 — CRIAR `src/nablamath/numeric/intervals.py`

Aritmética intervalar e limites certificados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 100 — CRIAR `src/nablamath/numeric/stiff_ode.py`

Solvers implícitos para EDOs rígidas e eventos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_math_extensions.py`: {"passed": 32}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 101 — CRIAR `src/nablamath/numeric/pde_general.py`

Contratos para EDPs e condições de contorno extensíveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_worlds_observations.py`: {"passed": 17}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 102 — CRIAR `src/nablamath/forge/compositional_generator.py`

Compor famílias de problemas com soluções conhecidas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_forge_discovery.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 103 — CRIAR `src/nablamath/forge/adversarial_generator.py`

Gerar problemas difíceis e detectar atalhos indevidos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_forge_discovery.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 104 — CRIAR `src/nablamath/forge/difficulty_calibration.py`

Definir dificuldade condicional a solver e recursos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_forge_discovery.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 105 — CRIAR `src/nablamath/forge/novelty_index.py`

Deduplicação estrutural e semântica escalável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_forge_discovery.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 106 — CRIAR `src/nablamath/formal/autoformalization.py`

Pipeline de tradução com verificação humana e kernel. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Controlled grammar only; review identity is caller supplied. Lean/Mathlib execution, human correspondence review and scalable proof search remain unvalidated.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_formal_workflows.py`: {"passed": 46}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 107 — CRIAR `src/nablamath/formal/proof_repair.py`

Correção assistida de demonstrações sem suprimir obrigações. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Controlled grammar only; review identity is caller supplied. Lean/Mathlib execution, human correspondence review and scalable proof search remain unvalidated.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_formal_workflows.py`: {"passed": 46}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 108 — CRIAR `src/nablamath/formal/proof_search_planner.py`

Busca escalável guiada por hipóteses e provas verificáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Controlled grammar only; review identity is caller supplied. Lean/Mathlib execution, human correspondence review and scalable proof search remain unvalidated.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_formal_workflows.py`: {"passed": 46}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 109 — CRIAR `src/nablamath/falsifier/property_engine.py`

Falsificação sistemática por propriedades e domínios. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_forge_discovery.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 110 — CRIAR `src/nablamath/gpu/kernels/f4_cuda.py`

Backend de referência para kernel CUDA verificável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** CUDA hardware absent; kernel compilation/execution, speedup and energy require independent real-device runs. Exact CPU oracle checks every device result.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded
- Referenced tests skipped; prerequisites or evidence remain missing

**Testes vinculados nesta execução:**

- `tests/benchmark/test_gpu_real_hardware.py`: {"skipped": 2}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 111 — CRIAR `src/nablamath/gpu/kernels/egraph_triton.py`

Backend Triton opcional para operações bateladas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Triton execution requires hardware/dependency validation; implements parent canonicalization only, not full GPU e-graph saturation.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded
- Referenced tests skipped; prerequisites or evidence remain missing

**Testes vinculados nesta execução:**

- `tests/test_remaining_physics_gpu.py`: {"passed": 40}
- `tests/benchmark/test_gpu_real_hardware.py`: {"skipped": 2}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 112 — CRIAR `src/nablamath/gpu/profiler.py`

Telemetria reprodutível de VRAM, tempo e energia. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** No GPU available. Energy integration and peak VRAM absent explicitly null; no speedup claim.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded
- Referenced tests skipped; prerequisites or evidence remain missing

**Testes vinculados nesta execução:**

- `tests/test_remaining_physics_gpu.py`: {"passed": 40}
- `tests/benchmark/test_gpu_real_hardware.py`: {"skipped": 2}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 113 — CRIAR `src/nablamath/worlds/boundary_conditions.py`

Representar contornos gerais de simulações. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_worlds_observations.py`: {"passed": 17}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 114 — CRIAR `src/nablamath/worlds/mesh/adaptive.py`

Refino adaptativo com estimadores de erro. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Sampled indicators are not a global error certificate; general multidimensional meshes remain pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_integration_mesh.py`: {"passed": 56}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 115 — CRIAR `src/nablamath/worlds/validation_observational.py`

Confrontar simulações com medições observadas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_worlds_observations.py`: {"passed": 17}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 116 — CRIAR `src/nablamath/worlds/uncertainty_quantification.py`

Propagação de incerteza nos modelos físicos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_worlds_observations.py`: {"passed": 17}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 117 — CRIAR `src/nablamath/physics/fluids/turbulence.py`

Modelos de turbulência delimitados e calibrados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Only declared 1D models and local analytic/synthetic checks; external calibration, experimental provenance and independent validation remain pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_physics_extensions.py`: {"passed": 93}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 118 — CRIAR `src/nablamath/physics/fluids/compressible.py`

Fluxos compressíveis e choques com validação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Only declared 1D models and local analytic/synthetic checks; external calibration, experimental provenance and independent validation remain pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_physics_extensions.py`: {"passed": 93}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 119 — CRIAR `src/nablamath/physics/relativity/einstein_solver.py`

Estudo modular de soluções de Einstein sem alegar generalidade automática. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded analytic spatially-flat perfect-fluid FLRW plus Schwarzschild; not general numerical Einstein solver; historical rounded Mercury comparison is not new experimental validation.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_physics_gpu.py`: {"passed": 40}
- `tests/science/test_observational_validation.py`: {"passed": 1}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 120 — CRIAR `src/nablamath/physics/fea/nonlinear.py`

Elementos finitos não lineares e verificação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Only declared 1D models and local analytic/synthetic checks; external calibration, experimental provenance and independent validation remain pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_physics_extensions.py`: {"passed": 93}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 121 — CRIAR `src/nablamath/graphics/visual_regression.py`

Comparar renderização semântica e imagens de referência. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Declared linear SCM only, no causal discovery from correlation; human visual review and empirical causal validation remain pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_graphics_causality.py`: {"passed": 36}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 122 — CRIAR `src/nablamath/graphics/scientific_renderer.py`

Renderização científica avançada rastreável ao modelo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Declared linear SCM only, no causal discovery from correlation; human visual review and empirical causal validation remain pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_graphics_causality.py`: {"passed": 36}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 123 — CRIAR `src/nablamath/documents/reference_graph.py`

Referências cruzadas e dependências de alegações em documentos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_evidence_integration_expansion.py`: {"passed": 3}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 124 — CRIAR `src/nablamath/documents/editorial_review.py`

Fluxo de revisão e qualidade editorial. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_editorial_governance.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 125 — CRIAR `src/nablamath/datasets/corpus_registry.py`

Registro de corpora e licenças externas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 126 — CRIAR `src/nablamath/datasets/semantic_leakage.py`

Detecção avançada de contaminação e semelhança. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Declared local equivalences and lineage only; no universal semantic detector or independently evaluated production scale.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_dataset_pipeline.py`: {"passed": 55}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 127 — CRIAR `src/nablamath/datasets/large_scale_pipeline.py`

Geração controlada em escala sem degradar qualidade. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Declared local equivalences and lineage only; no universal semantic detector or independently evaluated production scale.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_dataset_pipeline.py`: {"passed": 55}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 128 — CRIAR `src/nablamath/training/frontier_adapter.py`

Adaptadores opcionais de modelos de fronteira com consentimento. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Explicit owner/version/input-digest consent, default disabled, caller-injected transport only. No built-in network or frontier provider evaluation.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_learning.py`: {"passed": 15}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 129 — CRIAR `src/nablamath/training/reasoning_finetune.py`

Treino de raciocínio com protocolos congelados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Content-digest-frozen actual supervised linear fitting, deterministic bounded optimizer. Does not fine tune an LLM or prove learned reasoning.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_learning.py`: {"passed": 15}
- `tests/benchmark/test_holdout_generalization.py`: {"passed": 7}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 130 — CRIAR `src/nablamath/training/cross_domain_eval.py`

Medir generalização entre famílias e disciplinas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Task/family/semantic overlap checks and per-domain Wilson intervals on supplied cases. True external unseen cases remain external.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/benchmark/test_holdout_generalization.py`: {"passed": 7}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 131 — CRIAR `src/nablamath/training/compute_accounting.py`

Rastrear custo, energia e recursos por ganho útil. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 132 — CRIAR `src/nablamath/agents/secure_execution.py`

Sandbox operacional para código não confiável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Arbitrary code is refused. Hostile-code OS sandbox, capability isolation and escape-resistance validation are NOT implemented; this is a trusted-tool operational precursor.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/security/test_agent_sandbox.py`: {"passed": 42}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 133 — CRIAR `src/nablamath/agents/experiment_planner.py`

Planejamento de experimentos científicos revisáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_agent_controls.py`: {"passed": 9}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 134 — CRIAR `src/nablamath/agents/human_approval.py`

Autorizações explícitas para instrumentos, redes e publicação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_agent_controls.py`: {"passed": 9}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 135 — CRIAR `src/nablamath/discovery/literature_search.py`

Busca de antecedentes em fontes científicas externas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Curated supplied external metadata snapshots; no built-in live fetch, source authentication, comprehensive coverage or novelty guarantee.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_learning.py`: {"passed": 15}
- `tests/science/test_independent_discovery.py`: {"passed": 3}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 136 — CRIAR `src/nablamath/discovery/causal_hypothesis.py`

Hipóteses causais testáveis com pressupostos declarados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Declared linear SCM only, no causal discovery from correlation; human visual review and empirical causal validation remain pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_graphics_causality.py`: {"passed": 36}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 137 — CRIAR `src/nablamath/discovery/lab_protocol.py`

Protocolos de execução e reprodutibilidade de experimentos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_forge_discovery.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 138 — CRIAR `src/nablamath/discovery/independent_replication.py`

Registro de replicações independentes. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_editorial_governance.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 139 — CRIAR `src/nablamath/evolution/code_proposals.py`

Propostas de mudanças algorítmicas versionadas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Arbitrary code is refused. Hostile-code OS sandbox, capability isolation and escape-resistance validation are NOT implemented; this is a trusted-tool operational precursor.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/security/test_agent_sandbox.py`: {"passed": 42}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 140 — CRIAR `src/nablamath/evolution/frozen_evaluator.py`

Avaliador separado da autoridade do proponente. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** External operator isolation, authenticated independent review, private holdout administration and full original acceptance remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/evaluation/test_frozen.py`: {"passed": 30}

**Evidências registradas:** `docs/audits/FROZEN_EVALUATION_2026_10_15.md`

### 141 — CRIAR `src/nablamath/evolution/secure_trials.py`

Testes isolados de descendentes candidatos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Arbitrary code is refused. Hostile-code OS sandbox, capability isolation and escape-resistance validation are NOT implemented; this is a trusted-tool operational precursor.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/security/test_agent_sandbox.py`: {"passed": 42}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 142 — CRIAR `src/nablamath/evolution/longitudinal_monitor.py`

Medição de ganhos sustentados e regressões. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_evidence_integration_expansion.py`: {"passed": 3}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 143 — CRIAR `src/nablamath/knowledge/institutional_identity.py`

Vínculo de identidade real e competências auditáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_federation.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 144 — CRIAR `src/nablamath/knowledge/distributed_provenance.py`

Proveniência multioperador e revogação verificável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_remaining_federation.py`: {"passed": 13}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 145 — CRIAR `src/nablamath/knowledge/replication_protocol.py`

Replicação de alegações e revisões externas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_editorial_governance.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 146 — CRIAR `src/nablamath/knowledge/retraction_index.py`

Retratação propagada a artefatos dependentes. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 147 — CRIAR `services/coordinator/api.py`

API autenticada de coordenação e quotas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_coordinator_api.py`: {"passed": 6}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 148 — CRIAR `services/coordinator/task_leases.py`

Leases duráveis, heartbeats e idempotência. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_coordinator_api.py`: {"passed": 6}
- `tests/test_roadmap_worker_execution.py`: {"passed": 8}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`, `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 149 — CRIAR `services/coordinator/telemetry.py`

Observabilidade preservando privacidade. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_worker_execution.py`: {"passed": 8}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 150 — CRIAR `services/worker/executor.py`

Worker de tarefas tipadas, com limites e cancelamento. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_worker_execution.py`: {"passed": 8}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 151 — CRIAR `services/worker/isolation.py`

Isolamento operacional e política de recursos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Arbitrary code is refused. Hostile-code OS sandbox, capability isolation and escape-resistance validation are NOT implemented; this is a trusted-tool operational precursor.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/security/test_agent_sandbox.py`: {"passed": 42}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 152 — CRIAR `services/federation/reconciliation.py`

Federação entre organizações e resolução de conflitos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_partition.py`: {"passed": 1}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 153 — CRIAR `sdk/python/README.md`

Contrato público de SDK Python. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/interop/test_coordinator_clients.py`: {"passed": 16}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 154 — CRIAR `sdk/typescript/README.md`

Cliente interoperável para UI web. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/interop/test_coordinator_clients.py`: {"passed": 16}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 155 — CRIAR `sdk/rust/src/client.rs`

Cliente Rust de protocolo científico completo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_interop.py`: {"passed": 6}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 156 — CRIAR `tests/integration/test_scientific_artifact.py`

Ciclo completo e ataques em cada vínculo do artefato. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_scientific_artifact.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 157 — CRIAR `tests/integration/test_global_scientific_cycle.py`

Integração F1–F12 com avaliação honesta de lacunas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_global_scientific_cycle.py`: {"passed": 1}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 158 — CRIAR `tests/security/test_agent_sandbox.py`

Tentativas de escape e falha segura. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Arbitrary code is refused. Hostile-code OS sandbox, capability isolation and escape-resistance validation are NOT implemented; this is a trusted-tool operational precursor.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/security/test_agent_sandbox.py`: {"passed": 42}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 159 — CRIAR `tests/security/test_supply_chain.py`

Dependências, segredos e provenance de builds. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_resources_supplychain.py`: {"passed": 4}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 160 — CRIAR `tests/benchmark/test_math_comparison.py`

Benchmarks de solvers especializados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Version1 correctness comparison contract records owner, fixed seeds and128 exact rational plus32 analytic Hessian independent SymPy cases. No speed ranking, no external approval asserted; performance benchmarking and independent reviewer remain pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/benchmark/test_math_comparison.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 161 — CRIAR `tests/benchmark/test_gpu_real_hardware.py`

Aceleração real mensurada e conferida. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** No GPU available. Energy integration and peak VRAM absent explicitly null; no speedup claim.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded
- Referenced tests skipped; prerequisites or evidence remain missing

**Testes vinculados nesta execução:**

- `tests/test_remaining_physics_gpu.py`: {"passed": 40}
- `tests/benchmark/test_gpu_real_hardware.py`: {"skipped": 2}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 162 — CRIAR `tests/benchmark/test_holdout_generalization.py`

Generalização fora do treino sem vazamento. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Executed synthetic family holdouts, negative results and contamination rejection, not a measured frontier generalization gain.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/benchmark/test_holdout_generalization.py`: {"passed": 7}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 163 — CRIAR `tests/science/test_observational_validation.py`

Dados empíricos, calibração e incerteza. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Historical rounded Mercury reference and caller-supplied measurements are not independent provenance authentication, discipline-wide validation, or specialist review.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_worlds_observations.py`: {"passed": 17}
- `tests/science/test_observational_validation.py`: {"passed": 1}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 164 — CRIAR `tests/science/test_independent_discovery.py`

Reprodução de resultados científicos com revisores externos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Actual protocol conformance and negative replication bookkeeping; test fixtures are not external reviewers or independent scientific replication.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/science/test_independent_discovery.py`: {"passed": 3}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 165 — CRIAR `tests/distributed/test_multihost_failures.py`

Redes reais, perdas, partições e recuperação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/distributed/test_multihost_failures.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 166 — CRIAR `benchmarks/protocols/README.md`

Registro prévio de métricas, sementes, grupos e baselines. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_policy_links.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 167 — CRIAR `benchmarks/resources/hardware_profiles.json`

Ambientes de referência e budgets documentados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** No GPU available. Energy integration and peak VRAM absent explicitly null; no speedup claim.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded
- Referenced tests skipped; prerequisites or evidence remain missing

**Testes vinculados nesta execução:**

- `tests/test_remaining_physics_gpu.py`: {"passed": 40}
- `tests/benchmark/test_gpu_real_hardware.py`: {"skipped": 2}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 168 — CRIAR `benchmarks/external/README.md`

Catálogo de comparações externas com licenças. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_policy_links.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 169 — CRIAR `.github/workflows/security.yml`

Análise estática, dependências e segredos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_network_security.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 170 — CRIAR `.github/workflows/full-integration.yml`

Perfil integrado e replay end-to-end. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/integration/test_global_scientific_cycle.py`: {"passed": 1}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 171 — CRIAR `.github/workflows/scientific-benchmarks.yml`

Execuções científicas agendadas e diferenciadas dos unit tests. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_math_extensions.py`: {"passed": 32}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 172 — CRIAR `.github/workflows/release-attestation.yml`

Integridade, SBOM e proveniência por release. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_resources_supplychain.py`: {"passed": 4}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 173 — CRIAR `configs/profiles/cpu_conservative.yaml`

Limites para PCs domésticos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_resources_supplychain.py`: {"passed": 4}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 174 — CRIAR `configs/profiles/cpu_balanced.yaml`

Perfil doméstico equilibrado. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_resources_supplychain.py`: {"passed": 4}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 175 — CRIAR `configs/profiles/gpu_local.yaml`

Orçamentos de VRAM/GPU local. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_resources_supplychain.py`: {"passed": 4}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 176 — CRIAR `configs/profiles/research_station.yaml`

Perfil de estação profissional. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_resources_supplychain.py`: {"passed": 4}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 177 — CRIAR `configs/profiles/hpc_optional.yaml`

Escalamento opcional, sem pressupor HPC obrigatório. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_resources_supplychain.py`: {"passed": 4}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 178 — CRIAR `src/nablamath/network/signatures.py`

Assinatura assimétrica, rotação e revogação de chaves no protocolo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_network_security.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 179 — CRIAR `src/nablamath/node/identity.py`

Identidade local consentida com chaves e política de recuperação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_network_security.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 180 — CRIAR `src/nablamath/p2p/moderation.py`

Quarentena, limites de abuso e moderação auditáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_network_security.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 181 — CRIAR `src/nablamath/p2p/reputation.py`

Sinais antiabuso sem equiparar popularidade à verdade científica. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_network_security.py`: {"passed": 28}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 182 — CRIAR `services/registry/app.py`

Registro seguro e opt-in de nós e capacidades. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_registry_relay.py`: {"passed": 44}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 183 — CRIAR `services/registry/api.py`

API de descoberta e permissões versionadas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_registry_relay.py`: {"passed": 44}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 184 — CRIAR `services/registry/db.py`

Persistência de peers, chaves e estado de revogação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_registry_relay.py`: {"passed": 44}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 185 — CRIAR `services/registry/metrics.py`

Métricas anonimizadas e limites operacionais. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_registry_relay.py`: {"passed": 44}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 186 — CRIAR `services/relay/app.py`

Relay autenticado com quotas e desligamento seguro. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_registry_relay.py`: {"passed": 44}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 187 — CRIAR `services/relay/protocol.py`

Protocolos para NAT/retransmissão com proteção anti-replay. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_registry_relay.py`: {"passed": 44}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 188 — CRIAR `services/relay/abuse.py`

Prevenção de Sybil/eclipse/poisoning e registros auditáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_registry_relay.py`: {"passed": 44}

**Evidências registradas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

### 189 — CRIAR `tests/network/test_sybil.py`

Testes de identidades artificiais e resiliência de federação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_sybil.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 190 — CRIAR `tests/network/test_poisoning.py`

Injeção de resultados, hashes e assinaturas adulteradas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_poisoning.py`: {"passed": 3}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 191 — CRIAR `tests/network/test_eclipse.py`

Isolamento de peers e respostas resistentes a eclipse. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_eclipse.py`: {"passed": 1}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 192 — CRIAR `tests/network/test_partition.py`

Partições prolongadas de rede e reconciliação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_partition.py`: {"passed": 1}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 193 — CRIAR `tests/network/test_interop.py`

Interoperabilidade real entre implementações de protocolo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_interop.py`: {"passed": 6}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 194 — CRIAR `src/nablamath/knowledge/lineage.py`

Dependências entre conhecimento, dados e retratações. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 195 — CRIAR `src/nablamath/knowledge/novelty.py`

Novidade relativa a corpus e revisão bibliográfica independente. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_editorial_governance.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 196 — CRIAR `src/nablamath/knowledge/difficulty.py`

Dificuldade sustentada por orçamento e solvers observados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_editorial_governance.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 197 — CRIAR `src/nablamath/knowledge/curriculum.py`

Currículos científicos com diversidade e utilidade medida. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_editorial_governance.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 198 — CRIAR `src/nablamath/verification/independence.py`

Política de independência entre proponente, solver e avaliador. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_semantic_contracts.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 199 — CRIAR `src/nablamath/verification/evidence.py`

Tipos e obrigatoriedade de evidência para diferentes alegações. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Full original acceptance, independent review and external evidence remain required.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_semantic_contracts.py`: {"passed": 18}

**Evidências registradas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

### 200 — CRIAR `src/nablamath/verification/consensus.py`

Consenso sobre recibos sem confundi-lo com verdade científica. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_evidence_integration_expansion.py`: {"passed": 3}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 201 — CRIAR `src/nablamath/evaluation/calibration.py`

Curvas de calibração, generalização e análise de robustez. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 202 — CRIAR `src/nablamath/evaluation/ablation.py`

Ablation com avaliador congelado e comparação justa. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 203 — CRIAR `src/nablamath/training/snapshot.py`

Snapshots imutáveis de modelos e dados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 204 — CRIAR `src/nablamath/training/mixture.py`

Misturas de dados e auditoria de contribuição por fonte. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 205 — CRIAR `src/nablamath/training/lineage.py`

Linhagem de checkpoints, pesos e corpus de treinamento. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_expansion.py`: {"passed": 20}

**Evidências registradas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

### 206 — CRIAR `benchmarks/private/README.md`

Processos para holdouts administrados por avaliadores externos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_policy_links.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 207 — CRIAR `benchmarks/contamination/README.md`

Testes adversariais e padrões de vazamento de dados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_policy_links.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 208 — CRIAR `protocol/fixtures/cross-language/README.md`

Vetores normativos verificados por SDKs C/C++/Rust/TS/Python. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/network/test_interop.py`: {"passed": 6}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 209 — CRIAR `src/nablamath/singularity/evaluation/generalization.py`

Benchmark multidisciplinar de transferibilidade sem declarar AGI. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Fail-closed report consistency, duplicate-task rejection and declared per-domain thresholds; no AGI or independent benchmark authenticity claim.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/benchmark/test_holdout_generalization.py`: {"passed": 7}

**Evidências registradas:** `docs/audits/REMAINING_85_2026_10_15.md`

### 210 — CRIAR `src/nablamath/singularity/evaluation/safety.py`

Avaliar autonomia, permissões e falhas por agente. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_agent_controls.py`: {"passed": 9}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 211 — CRIAR `src/nablamath/singularity/evaluation/long_horizon.py`

Avaliação de projetos científicos longos com intervenção humana. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_agent_controls.py`: {"passed": 9}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 212 — CRIAR `docs/future/F13_OPEN_RESEARCH.md`

Requisitos prospectivos abertos e governança de descobertas pós-2056. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_policy_links.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

### 213 — CRIAR `docs/future/2035_2045_2056_criteria.md`

Critérios técnicos revisáveis com indicadores de sucesso/falha. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Estado declarado:** partial.

**Escopo restante registrado:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Pendências observadas:**

- Original acceptance not closed: partial
- Independent reviewer not recorded
- Accepted release not recorded

**Testes vinculados nesta execução:**

- `tests/test_roadmap_policy_links.py`: {"passed": 2}

**Evidências registradas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Limites que não desaparecem com pytest verde

- Generalização: comparar resultados do laboratório original, sem substituir seu 0/48 por outra campanha.
- Lean/Mathlib: provas e hipóteses precisam do kernel e das dependências reais.
- GPU, múltiplos hosts e plataformas: exigem execução nos ambientes correspondentes.
- Simulação e descoberta: exigem dados experimentais, revisão e reprodução independentes.
- F13 é horizonte de pesquisa aberto; os 213 itens não garantem inteligência geral.
