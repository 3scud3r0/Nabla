# Todos os 213 requisitos da visão

Transcrição organizada da matriz atual; não altera seus estados nem aceita requisitos.
Os termos históricos “CRIAR” não significam que um caminho ainda esteja ausente: a existência foi conferida no checkout.
Pastas são escopos de trabalho, não um único arquivo. Consulte o inventário de arquivos para a expansão individual.

## Requisito 001 — `src/nablamath/core/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · F1–F12: unificar AST/IR, tipos, unidades, precisão, domínios e contratos semânticos; garantir serialização canônica, invariantes e migração. Concluído quando: testes de propriedades, unidades, condições de domínio, compatibilidade e round-trip.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/core/scientific_artifact.py`
**Testes vinculados:** `tests/integration/test_scientific_artifact.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 002 — `src/nablamath/schema/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · F0–F12: versionar e validar esquemas de problema, expressão, experimento, etapa, evidência e artefato; rejeitar ambiguidades e mudanças silenciosas. Concluído quando: golden fixtures, migrações, validação adversarial e interop.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/core/semantic_contracts.py`
**Testes vinculados:** `tests/test_semantic_contracts.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 003 — `src/nablamath/calc/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F1: ampliar catálogo e sessão científica com operações gerais, diferenciação, rastreamento e erros certificados. Concluído quando: comparações externas, exemplos adversariais e especificações por operação.

**Pendência registrada:** Existing audited calculator catalog/session provides exact operations, domain obligations, request/result hashing and declared limitations; mapped with regression tests this round. Broad external per-operation certification remains incomplete.

**Implementações vinculadas:** `src/nablamath/calc/catalog.py`, `src/nablamath/calc/session.py`
**Testes vinculados:** `tests/test_phase1_calculator.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 004 — `src/nablamath/symbolic/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F1–F3: expandir parser/reescrita/e-graphs, funções transcendentes, hipóteses, integrais e certificados de transformação. Concluído quando: provas ou verificação independente de regras, preservação de domínio e benchmarks.

**Pendência registrada:** New independent finite exact-rational rewrite rule falsifier checks domain mismatch and value mismatch with adversarial tests. Finite scalar grid is not proof for composite expressions or all transcendental rules.

**Implementações vinculadas:** `src/nablamath/symbolic/rule_audit.py`, `src/nablamath/symbolic/proof.py`, `src/nablamath/symbolic/assumptions.py`
**Testes vinculados:** `tests/test_remaining_math_compiler.py`, `tests/test_declarative_egraph.py`, `tests/test_egraph.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 005 — `src/nablamath/numeric/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F1/F7: implementar solvers numéricos modernos, condicionamento, tolerâncias, intervalos, limites de recursos e diagnósticos. Concluído quando: convergência, referências NIST/analíticas, escalonamento e precisão.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/numeric/intervals.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 006 — `src/nablamath/math/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F1–F3/F11: aprofundar a área matemática do módulo, documentar domínio e limitações, adicionar algoritmos gerais e referências competitivas. Concluído quando: propriedades matemáticas, benchmarks independentes, provas quando cabíveis e testes de fronteira.

**Pendência registrada:** Existing bounded rational integration certificates, Lambert W, exact PLU and bounded factorization now explicitly mapped with regression evidence. Not arbitrary Risch nor general competitive mathematics suite.

**Implementações vinculadas:** `src/nablamath/math/calculus/risch.py`, `src/nablamath/math/calculus/transcendentals.py`, `src/nablamath/math/linear_algebra/exact_decompositions.py`, `src/nablamath/math/number_theory/factorization_advanced.py`
**Testes vinculados:** `tests/test_roadmap_math_extensions.py`, `tests/test_roadmap_integration_mesh.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 007 — `src/nablamath/autodiff/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F1/F7/F8: expandir forward/reverse AD para tensores e aplicações, broadcasting, controle de gradiente, jacobianas e Hessianas. Concluído quando: grad-check, precisão, memória, comparação com JAX/PyTorch e exemplos físicos.

**Pendência registrada:** New analytic dense second-order tensor AD includes broadcasting, reductions, matrix products, transcendental functions and stop-gradient; SymPy32 Hessian comparisons and reverse-gradient finite differences. Limit64 input coordinates; O(n²m) memory; no PyTorch/JAX comparison claim.

**Implementações vinculadas:** `src/nablamath/autodiff/second_order.py`, `src/nablamath/autodiff/tensor.py`
**Testes vinculados:** `tests/test_remaining_math_compiler.py`, `tests/benchmark/test_math_comparison.py`, `tests/test_tensor_autodiff.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 008 — `src/nablamath/forge/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F2: ampliar construção inversa, deduplicação, diversidade, geração composicional, controle de dificuldade e verificação. Concluído quando: corpus inédito, solvers competidores, taxas de validade, novidade estrutural e dificuldade calibrada.

**Pendência registrada:** Local deterministic construction, composition and difficulty evidence; genuinely novel external corpus and competing solver calibration remain external acceptance.

**Implementações vinculadas:** `src/nablamath/forge/compositional_generator.py`, `src/nablamath/forge/difficulty_calibration.py`, `src/nablamath/forge/novelty_index.py`
**Testes vinculados:** `tests/test_roadmap_forge_discovery.py`, `tests/test_phase2_forge.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 009 — `src/nablamath/verify/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · F2–F12: separar proponente e verificador, reexecutar provas/testemunhos, integrar obrigações e linhagem de evidências. Concluído quando: falsificações induzidas rejeitadas e evidências reexecutáveis em ambiente limpo.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/pipeline/scientific_cycle.py`
**Testes vinculados:** `tests/integration/test_scientific_artifact.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 010 — `src/nablamath/formal/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F3: expandir cobertura Lean/SMT, autoformalização assistida revisada, certificados, lógica e rastreio de axiomas. Concluído quando: kernel independente, hipóteses explícitas, correspondência humana auditada e replay.

**Pendência registrada:** Existing reviewed controlled-language autoformalization and bounded Lean/SMT portfolios/replay explicitly mapped with tests. No arbitrary natural-language translation; external human correspondence audit and Mathlib compilation remain unfulfilled.

**Implementações vinculadas:** `src/nablamath/formal/autoformalization.py`, `src/nablamath/formal/proof_search_planner.py`, `src/nablamath/formal/proof_repair.py`
**Testes vinculados:** `tests/test_roadmap_formal_workflows.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 011 — `src/nablamath/falsifier/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F3/F9: expandir busca/minimização de contraexemplos, propriedades, domínio e diagnósticos verificáveis. Concluído quando: falsificações conhecidas recuperadas e ausência de falso teorema.

**Pendência registrada:** Bounded property/counterexample checks are not completeness for arbitrary theorem falsification.

**Implementações vinculadas:** `src/nablamath/falsifier/property_engine.py`, `src/nablamath/falsifier/counterexample_miner.py`, `src/nablamath/falsifier/shrink.py`
**Testes vinculados:** `tests/test_roadmap_forge_discovery.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 012 — `src/nablamath/gpu/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F1–F10: substituir caminhos de referência por kernels reais opcionais, com fallback CPU, profiling, uso de VRAM e verificação numérica. Concluído quando: benchmarks em hardware identificado, equivalência e provas de ganho custo/energia.

**Pendência registrada:** CUDA hardware absent; kernel compilation/execution, speedup and energy require independent real-device runs. Exact CPU oracle checks every device result.

**Implementações vinculadas:** `src/nablamath/gpu/kernels/f4_cuda.py`, `src/nablamath/gpu/cuda_f4_reduction.py`
**Testes vinculados:** `tests/benchmark/test_gpu_real_hardware.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 013 — `src/nablamath/compiler/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F1–F10: estabilizar IR/compilação, otimização semântica, backends e agendamento distribuído. Concluído quando: equivalência entre backends, determinismo e custos mensurados.

**Pendência registrada:** New strict versioned IR decoder validates canonical rational literals, instruction order, bounds and literal integer exponents, preventing silent fractional exponent truncation. Exact Python interpreter equivalence checked128 independent SymPy cases. Optional JAX remains separately declared; distributed scheduling/performance not validated.

**Implementações vinculadas:** `src/nablamath/compiler/ir.py`, `src/nablamath/compiler/backends.py`
**Testes vinculados:** `tests/test_remaining_math_compiler.py`, `tests/test_compiler_backends.py`, `tests/benchmark/test_math_comparison.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 014 — `src/nablamath/physics/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F7/F11: ampliar modelos físicos além das referências, incluindo condições de contorno, incerteza, calibração e validação observacional. Concluído quando: casos manufaturados, séries de convergência, dados reais e revisão disciplinar.

**Pendência registrada:** Stationary no-slip channel reduction and existing 1D Euler reference only; general 2D nonperiodic Navier-Stokes, laboratory data and disciplinary review remain.

**Implementações vinculadas:** `src/nablamath/physics/fluids/channel.py`, `src/nablamath/physics/fluids/compressible.py`, `src/nablamath/physics/fluids/turbulence.py`
**Testes vinculados:** `tests/test_remaining_physics_gpu.py`, `tests/test_roadmap_physics_extensions.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 015 — `src/nablamath/worlds/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F7: generalizar modelos de EDO/EDP, malhas, eventos, rigidez, multiphysics, controle de erro e replay. Concluído quando: benchmarks por fenômeno, estabilidade/conservação, confronto com medidas e reproducibilidade.

**Pendência registrada:** Existing bounded adaptive integration/mesh profiles; stiff general multiphysics and independent observations remain.

**Implementações vinculadas:** `src/nablamath/worlds/integrators/adaptive.py`, `src/nablamath/worlds/mesh/adaptive.py`, `src/nablamath/worlds/validation_observational.py`
**Testes vinculados:** `tests/test_roadmap_worlds_observations.py`, `tests/test_phase7_worlds.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 016 — `src/nablamath/graphics/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F4: implementar cenas e geometria mais gerais, renderizações científicas auditáveis, qualidade visual e exportação multimodal. Concluído quando: validação geométrica, inspeção de imagens, performance e semântica das figuras.

**Pendência registrada:** Multimodal exact sample exports with semantic replay; geometry, pixel fidelity, performance and external visual inspection remain bounded to existing profiles.

**Implementações vinculadas:** `src/nablamath/graphics/scientific_export.py`, `src/nablamath/graphics/scientific_renderer.py`
**Testes vinculados:** `tests/test_remaining_product.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 017 — `src/nablamath/viz/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F4/F5: unificar gráficos e animações com dados, escalas, unidades, acessibilidade e metadados de incerteza. Concluído quando: replay pixel/semântico, revisão visual e testes de legibilidade.

**Pendência registrada:** Accessible sample tables, exact units and declared uncertainty; discrete-frame animation only; human legibility and continuous interpolation unvalidated.

**Implementações vinculadas:** `src/nablamath/viz/accessible.py`, `src/nablamath/graphics/scientific_export.py`
**Testes vinculados:** `tests/test_remaining_product.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 018 — `src/nablamath/documents/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F5: completar AST editorial, bibliografia, referências, tabelas, figuras e exportações sem alegações sem evidência. Concluído quando: compilação dos formatos, inspeção de páginas e revisão editorial externa.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/pipeline/scientific_cycle.py`
**Testes vinculados:** `tests/integration/test_scientific_artifact.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 019 — `src/nablamath/reports/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F5: consolidar relatórios com documentos canônicos, tabelas, passos, provas e vínculos verificáveis. Concluído quando: PDF/LaTeX com numeração e integridade reexecutável.

**Pendência registrada:** Evidence hashes, deterministic object numbering and byte-bound HTML/LaTeX/Typst exports; tests compile real templates via available Typst and pdflatex; scientific endorsement and visual inspection not inferred.

**Implementações vinculadas:** `src/nablamath/reports/canonical_bundle.py`
**Testes vinculados:** `tests/test_remaining_product.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 020 — `src/nablamath/dataset/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F6: migrar APIs antigas para contrato canônico, governar licenças, splits, qualidade, deduplicação e proveniência. Concluído quando: migrações compatíveis, integridade por amostra, testes de contaminação.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/pipeline/scientific_cycle.py`
**Testes vinculados:** `tests/integration/test_scientific_artifact.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 021 — `src/nablamath/datasets/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F6/F8: unificar modelos de registros e alinhar modalidades, linhagem, licenças, política de splits e evidência multimodal. Concluído quando: auditoria independente de corpora e ganho ou resultado negativo reproduzível.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/datasets/corpus_registry.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 022 — `src/nablamath/export/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F5/F6/F12: publicar bundles interoperáveis versionados com manifestos, integridade, licenças, privacidade e reversibilidade. Concluído quando: import/export/verify em ambiente isolado e controles de adulteração.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/core/scientific_artifact.py`
**Testes vinculados:** `tests/integration/test_scientific_artifact.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 023 — `src/nablamath/training/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F8: treinar modelos mais capazes, estabelecer avaliações externas, ablações, curricula, contaminação e custo de treino. Concluído quando: comparação com/sem Nabla em holdouts verdadeiramente inéditos e ICs pré-especificados.

**Pendência registrada:** Real bounded supervised numerical reasoning fit and synthetic family transfer; no frontier model gain or independently authored unseen benchmark established.

**Implementações vinculadas:** `src/nablamath/training/reasoning_finetune.py`, `src/nablamath/training/cross_domain_eval.py`
**Testes vinculados:** `tests/test_remaining_learning.py`, `tests/benchmark/test_holdout_generalization.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 024 — `src/nablamath/evaluation/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · F6/F8/F10: criar avaliador congelado independente de proponente, impedir vazamento transitivo e fornecer decisão estatística auditável. Concluído quando: testes adversariais com adulteração e holdout inacessível ao proponente.

**Pendência registrada:** External operator isolation, authenticated independent review, private holdout administration and full original acceptance remain required.

**Implementações vinculadas:** `src/nablamath/evaluation/frozen.py`
**Testes vinculados:** `tests/evaluation/test_frozen.py`
**Evidências vinculadas:** `docs/audits/FROZEN_EVALUATION_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 025 — `src/nablamath/agents/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F8: planejamento científico mais capaz, permissões por capacidade, orçamentos, checkpoints, orquestração e isolamento real. Concluído quando: ataques simulados, replay, falha segura e custos por tarefa.

**Pendência registrada:** Existing consented trusted-tool checkpoints, cancellation and process deadlines are tested. Hostile-code OS isolation and externally authenticated authority remain unavailable; arbitrary code stays disabled.

**Implementações vinculadas:** `src/nablamath/agents/secure_execution.py`, `src/nablamath/agents/permissions.py`
**Testes vinculados:** `tests/security/test_agent_sandbox.py`, `tests/test_roadmap_agent_controls.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 026 — `src/nablamath/discovery/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F9: ampliar gramáticas, busca de leis/teoremas, experimentos discriminantes e revisão bibliográfica. Concluído quando: novidade avaliada externamente, reprodução e registro de descobertas nulas/refutadas.

**Pendência registrada:** Curated supplied snapshots; reviewer identity and global scientific novelty are not authenticated.

**Implementações vinculadas:** `src/nablamath/discovery/literature_search.py`, `src/nablamath/discovery/research_program.py`, `src/nablamath/discovery/independent_replication.py`
**Testes vinculados:** `tests/test_remaining_learning.py`, `tests/science/test_independent_discovery.py`, `tests/test_phase9_discovery.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 027 — `src/nablamath/evolution/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F10: permitir propostas de algoritmos novos sob gates isolados, rollback, estatística e autoridade distinta. Concluído quando: ganhos contra baseline forte em avaliações congeladas e monitoramento de regressões.

**Pendência registrada:** Closed declarative proposals and local rollback; not arbitrary untrusted code sandboxing or externally measured robust algorithmic advances.

**Implementações vinculadas:** `src/nablamath/evolution/code_proposals.py`, `src/nablamath/evolution/secure_trials.py`, `src/nablamath/evolution/rollback.py`
**Testes vinculados:** `tests/test_phase10_evolution.py`, `tests/security/test_agent_sandbox.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 028 — `src/nablamath/domains/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F11: aprofundar modelos disciplinares e suas integrações com instrumentação, medições e especialistas. Concluído quando: validação com observações reais e critérios próprios por disciplina.

**Pendência registrada:** Historical rounded Mercury reference and caller-supplied measurements are not independent provenance authentication, discipline-wide validation, or specialist review.

**Implementações vinculadas:** `src/nablamath/worlds/validation_observational.py`, `src/nablamath/domains/chemistry/kinetics.py`, `src/nablamath/domains/materials/elasticity.py`, `src/nablamath/physics/relativity/general.py`
**Testes vinculados:** `tests/test_roadmap_worlds_observations.py`, `tests/science/test_observational_validation.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 029 — `src/nablamath/knowledge/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F9/F12: reconciliar claims, evidências, versões, revisão, retração, federação, identidades e conflitos. Concluído quando: replay institucional multioperador, reconciliação correta e autenticação independente.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/knowledge/retraction_index.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 030 — `src/nablamath/network/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F12: consolidar objetos, manifestos, recibos e protocolos P2P com limites e consistência. Concluído quando: testes de rede real, falhas parciais e compatibilidade retroativa.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `src/nablamath/network/framing.py`
**Testes vinculados:** `tests/test_remaining_federation.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 031 — `src/nablamath/p2p/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F12: implementar transporte autenticado, descoberta, rate limits, quarentena e recuperação de peers. Concluído quando: rede adversarial e latência/perda medidas.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `src/nablamath/p2p/resilient_peers.py`
**Testes vinculados:** `tests/network/test_eclipse.py`, `tests/network/test_sybil.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 032 — `src/nablamath/node/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F12: operacionalizar nó consentido, controle de recursos, tarefas, verificação e workspace. Concluído quando: reprodução em máquinas distintas e telemetria auditável.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `src/nablamath/node/federated_session.py`
**Testes vinculados:** `tests/test_remaining_federation.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 033 — `src/nablamath/coordination/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F12: unificar coordenação local/Merkle com serviços distribuídos e provas de consistência. Concluído quando: invariantes sob concorrência, reconexão e restauração.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/coordination/local.py`
**Testes vinculados:** `tests/integration/test_coordinator_api.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 034 — `src/nablamath/pipeline/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · F0–F12: ligar todos os estágios científicos em pipeline transacional, versionado e reexecutável com cache seguro. Concluído quando: um ScientificArtifact ponta a ponta com adulteração de cada vínculo rejeitada.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/pipeline/scientific_cycle.py`
**Testes vinculados:** `tests/integration/test_scientific_artifact.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 035 — `src/nablamath/singularity/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P3 · F8–F13: converter protótipos de cognição/memória/engenharia/agentes em componentes mensuráveis, governados e testáveis sem alegar AGI. Concluído quando: benchmarks abertos/fechados, segurança, ganhos transferíveis e avaliações independentes.

**Pendência registrada:** Transfer threshold gate recomputes reported outcomes; local synthetic cases do not establish AGI, independent evaluation, or domain transfer in real science.

**Implementações vinculadas:** `src/nablamath/singularity/evaluation/generalization.py`, `src/nablamath/singularity/evaluation/safety.py`, `src/nablamath/singularity/evaluation/long_horizon.py`
**Testes vinculados:** `tests/test_singularity_lab.py`, `tests/benchmark/test_holdout_generalization.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 036 — `src/nablamath/adapters/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F1/F7/F11: tornar integração NumPy/SciPy/SymPy/Blender/instrumentos explícita, compatível, segura e bidirecional. Concluído quando: testes com versões fixadas e coerência de unidades/dados.

**Pendência registrada:** Bounded numeric NumPy wire validation and optional SciPy interoperability; full cross-tool compatibility and upstream version matrix remain.

**Implementações vinculadas:** `src/nablamath/adapters/numpy.py`, `src/nablamath/adapters/scipy.py`, `src/nablamath/adapters/registry.py`
**Testes vinculados:** `tests/test_remaining_physics_gpu.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 037 — `src/nablamath/store/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · F0–F12: fortalecer migrations, backups, armazenamento de blobs, integridade e política de retenção. Concluído quando: restauração/falha de energia/concorrrência, recovery e compatibilidade.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/pipeline/artifact_store.py`
**Testes vinculados:** `tests/integration/test_scientific_artifact.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 038 — `src/nablamath/publisher/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F5/F6: governar publicação autorizada e assinada com direitos por artefato e política de revogação. Concluído quando: dry-run, idempotência e testes em destino de homologação.

**Pendência registrada:** Ed25519 authorization binds exact artifact bytes and destination; opt-in rights declaration, revocation, dry-run idempotency. State is process-local; no remote staging publication performed and rights are operator declarations.

**Implementações vinculadas:** `src/nablamath/publisher/authorization.py`
**Testes vinculados:** `tests/test_remaining_product.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 039 — `src/nablamath/benchmarks/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · F1–F12: pré-registrar protocolos e incluir baselines independentes, métricas e falhas reexecutáveis. Concluído quando: replicação por terceiros, holdouts novos e relatórios negativos.

**Pendência registrada:** Preregistered fixed model/cohort/metric/stopping-rule ledger and exact descriptive paired comparisons. Third-party replication, private novel holdout, inferential independence and model execution identity are not established.

**Implementações vinculadas:** `src/nablamath/benchmarks/preregistration.py`
**Testes vinculados:** `tests/test_registered_comparison.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 040 — `src/nablamath/desktop/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F1–F12: expor workflows científicos completos, revisão humana, datasets e rastreio em UX local segura. Concluído quando: testes acessibilidade/usabilidade e equivalência CLI/API.

**Pendência registrada:** Complete exact-instance experiment/evidence/report workflow in loopback UI with consent. Existing UI covers more bounded operations, not all scientific subsystems; human accessibility/usability review outstanding.

**Implementações vinculadas:** `src/nablamath/desktop/workflows.py`, `src/nablamath/desktop/app.py`, `src/nablamath/desktop/index.html`
**Testes vinculados:** `tests/test_remaining_product.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 041 — `src/nablamath/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F0–F12: manter contratos, CLI, compatibilidade e workflows integrados; eliminar caminhos paralelos sem migração. Concluído quando: smokes da API pública, documentação e integração de ponta a ponta.

**Pendência registrada:** CLI exposes finite contracts and refusals; Lean support pin aligned. The open-ended public workflow and compatibility matrix still require releases and cross-platform external verification.

**Implementações vinculadas:** `src/nablamath/cli.py`, `src/nablamath/core/capabilities.py`, `src/nablamath/compatibility.json`
**Testes vinculados:** `tests/test_public_contracts.py`, `tests/integration/test_scientific_artifact.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 042 — `tests/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · F0–F13: expandir o teste deste componente para casos positivos/negativos, propriedade, integração, segurança e benchmarks. Concluído quando: CI em Linux/Windows/macOS, fixture congelado e evidência em release.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `tests/integration/test_scientific_artifact.py`
**Testes vinculados:** `tests/test_semantic_contracts.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 043 — `lean/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F3: ampliar demonstrações Lean além dos fragmentos atuais; pin da toolchain, livre de sorry/admit e revisão de tradução. Concluído quando: compilação reproduzível, kernel verificando teoremas e auditoria de axiomas.

**Pendência registrada:** Six new kernel-only Lean4.34.0 theorems compiled successfully and #print axioms reports zero dependencies for each. Full imported Mathlib project still unavailable; no Python translator correspondence proof.

**Implementações vinculadas:** `lean/Nabla/KernelContracts.lean`, `lean/Nabla.lean`, `lean/lean-toolchain`
**Testes vinculados:** `tests/test_remaining_math_compiler.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 044 — `protocol/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · F0/F12: padronizar codificação canônica, schemas de objetos/recibos e interop de clientes. Concluído quando: golden vectors e testes cruzados C/C++/Rust/Python.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `protocol/fixtures/cross-language/rational-v1.json`
**Testes vinculados:** `tests/network/test_interop.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 045 — `sdk/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F12: evoluir parsers de frações para SDKs científicos e transporte autenticado interoperáveis. Concluído quando: conformidade protocolar, ABI/API estáveis e fuzzing.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `sdk/python/rational.py`, `sdk/typescript/rational.ts`, `sdk/rust/src/client.rs`
**Testes vinculados:** `tests/network/test_interop.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 046 — `services/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F12: evoluir protótipos locais para serviços autenticados, escaláveis e tolerantes a falhas. Concluído quando: testes de rede entre hosts, segurança e monitoramento.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `services/coordinator/api.py`
**Testes vinculados:** `tests/integration/test_coordinator_api.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 047 — `.github/workflows/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · F0–F13: corrigir dependências, pin/atualizar actions, garantir CI matriz, segurança de supply chain e releases condicionadas. Concluído quando: nenhum check obrigatório falho e atestados por commit/release.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `.github/workflows/ci.yml`
**Testes vinculados:** `tests/integration/test_scientific_artifact.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 048 — `docs/audits/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · F0–F13: registrar baseline, falhas, incertezas, remediações e evidências separando medições de opiniões. Concluído quando: auditoria independente e referências imutáveis por commit.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `docs/acceptance/evidence_matrix.json`
**Testes vinculados:** `tests/test_roadmap_contract.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 049 — `docs/history/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P3 · Histórico: preservar material original sem confundir aspiração histórica com implementação. Concluído quando: hash e índice de origem validados.

**Pendência registrada:** Historical bytes and declared repository commit pinned; original claims not treated as delivered behavior.

**Implementações vinculadas:** `tools/preserve_evidence.py`, `docs/history/preservation-index.json`
**Testes vinculados:** `tests/test_remaining_release.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 050 — `docs/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F0–F13: atualizar especificação, critérios, instruções e limites após mudanças verificadas. Concluído quando: links, exemplos e status verificáveis por versão.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `docs/acceptance/phase_profiles.md`
**Testes vinculados:** `tests/test_roadmap_contract.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 051 — `benchmarks/results/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · Evidência: preservar resultado congelado, inclusive falhas e modelos negativos; criar novos resultados em campanhas distintas. Concluído quando: SHA-256, protocolo, licença, replay semântico e cadeia de custódia.

**Pendência registrada:** Frozen result bytes include negative results; campaign hash chain and canonical JSON semantic check do not reexecute scientific experiment or authenticate custodian.

**Implementações vinculadas:** `tools/preserve_evidence.py`, `docs/history/preservation-index.json`
**Testes vinculados:** `tests/test_remaining_release.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 052 — `benchmarks/fixtures/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · Evidência: manter fixture original e fonte licenciada; incluir novas referências identificadas e imutáveis. Concluído quando: hash, proveniência e correspondência com referências independentes.

**Pendência registrada:** Longley mirror commit, three SHA256 files, source paths, license and reference checked offline; no new independent publisher retrieval.

**Implementações vinculadas:** `tools/preserve_evidence.py`, `docs/history/preservation-index.json`
**Testes vinculados:** `tests/test_remaining_release.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 053 — `benchmarks/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F1–F12: definir protocolos e baselines comparativos novos sem reescrever resultados históricos. Concluído quando: reexecução, métricas estatísticas e replicação.

**Pendência registrada:** Preregistered fixed model/cohort/metric/stopping-rule ledger and exact descriptive paired comparisons. Third-party replication, private novel holdout, inferential independence and model execution identity are not established.

**Implementações vinculadas:** `src/nablamath/benchmarks/preregistration.py`
**Testes vinculados:** `tests/test_registered_comparison.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 054 — `legacy/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P3 · Histórico: congelar e catalogar código legado; migrar somente funcionalidades comprovadas para src/ com testes. Concluído quando: arquivos preservados por hash e nenhuma fonte dupla em produção.

**Pendência registrada:** Legacy bytes frozen; AST audit rejects explicit production legacy/archive imports; dynamic imports not comprehensively audited.

**Implementações vinculadas:** `tools/preserve_evidence.py`, `docs/history/preservation-index.json`
**Testes vinculados:** `tests/test_remaining_release.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 055 — `website/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · Produto: substituir indicadores promocionais por status derivado das evidências, melhorar transparência e documentação. Concluído quando: testes de interface, métricas rastreáveis, privacidade e acessibilidade.

**Pendência registrada:** Built site status derived from actual213 matrix, no promotional completion inference. No live deployment or human accessibility review performed.

**Implementações vinculadas:** `website/src/evidence.js`, `website/build.mjs`, `website/app.js`, `website/index.html`
**Testes vinculados:** `tests/test_remaining_product.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 056 — `tools/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P0 · F0–F13: ampliar auditoria e automação de reprodução, sem atribuir completude por quantidade de arquivos. Concluído quando: reexecução em ambiente limpo, tratamento de falha e relatórios versionados.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `tools/check_roadmap.py`
**Testes vinculados:** `tests/test_roadmap_contract.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 057 — `scripts/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · F0: tornar instalação/importação idempotentes, reexecutáveis e seguros em todas as plataformas. Concluído quando: testes de recuperação e compatibilidade de arquivos históricos.

**Pendência registrada:** Pinned bounded ZIP import is idempotent, refuses historical overwrite, case/path/symlink collisions and preserves destination on failure; tested on current Linux only.

**Implementações vinculadas:** `scripts/preserved_archive.py`
**Testes vinculados:** `tests/test_remaining_release.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 058 — `examples/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · Documentação: criar exemplos reproduzíveis de pipelines completos e documentar limites. Concluído quando: execução automatizada de cada exemplo publicado.

**Pendência registrada:** All five published Python examples auto-executed in isolated temporary outputs; fixtures are synthetic and not evidence of scientific discovery.

**Implementações vinculadas:** `examples/audited_local_experiment.py`
**Testes vinculados:** `tests/test_remaining_product.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 059 — `templates/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P2 · F5: ampliar modelos de relatórios com origem de cada alegação, dados e revisão editorial. Concluído quando: compilação de todos os templates e conferência visual.

**Pendência registrada:** Three canonical report templates exported and compiled with available real Typst and LaTeX compilers; external visual/editorial review not performed.

**Implementações vinculadas:** `templates/engineering_report/example.document.json`, `templates/teaching/example.document.json`
**Testes vinculados:** `tests/test_remaining_product.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 060 — `packaging/`

**Estado declarado:** partial. **Caminho:** diretório existente.

**Conteúdo/aceite pretendido:** P1 · Produto: assegurar instaladores assinados quando possível, atestados, atualização segura e desinstalação reversível. Concluído quando: instalação/upgrade/downgrade em máquinas limpas.

**Pendência registrada:** Real offline clean-venv synthetic package install, upgrade, downgrade, repair, uninstall and restoration tested on current Linux; no Windows/macOS, signed installer or publisher authenticity claim.

**Implementações vinculadas:** `packaging/offline_release.py`
**Testes vinculados:** `tests/test_remaining_release.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 061 — `.github/workflows/ci.yml`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: corrigir falha confirmada: instalar .[test] antes do unittest/pytest; executar também lint/build website. Aceite: job NablaMath CI aprovado no commit auditado.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `.github/workflows/ci.yml`
**Testes vinculados:** `tests/integration/test_scientific_artifact.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 062 — `pyproject.toml`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: alinhar dependências opcionais, versões, entrypoints, perfis Python, metadados, SBOM e origem do wheel. Aceite: build e importação isolada, matriz de versões e release alinhada.

**Pendência registrada:** SPDX 2.3 wheel SBOM source commit declaration, metadata, optional requirement and SHA binding reuse existing wheel verifier; source origin is caller-declared, Python version matrix not run.

**Implementações vinculadas:** `packaging/offline_release.py`
**Testes vinculados:** `tests/test_remaining_release.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 063 — `README.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: documentar limites reais, quickstart, módulos avaliados, indicadores reproduzíveis e diferença visão/entrega. Aceite: todos os links e comandos revisados por CI.

**Pendência registrada:** Current evidence and historical estimates distinguished, contract/link checks added to CI. Interactive browser startup, every optional external service and all platform commands require independent runtime review.

**Implementações vinculadas:** `README.md`, `tools/check_public_contracts.py`, `.github/workflows/ci.yml`
**Testes vinculados:** `tests/test_public_contracts.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 064 — `vision.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: converter aspirações 2026–2056+ em perfis versionados sem apagar o horizonte aberto; explicitar hipóteses e critérios de fechamento. Aceite: matriz bidirecional visão→requisitos→testes→evidência.

**Pendência registrada:** Machine-checked original requirement/phase/evidence references and finite-domain contract. This is consistent local traceability, not proof of all original algorithms, external review, costs, closed issues, or scientific phase completion. Historical backlog items remain individually unresolved where acceptance evidence is missing.

**Implementações vinculadas:** `vision.md`, `tools/update_public_contracts.py`, `tools/check_public_contracts.py`, `docs/acceptance/vision_traceability.json`
**Testes vinculados:** `tests/test_public_contracts.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 065 — `description.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: sincronizar a descrição atual com evidências e release; evitar alegar avanços futuros como atuais. Aceite: toda alegação inclui versão e comprovação.

**Pendência registrada:** Machine-checked original requirement/phase/evidence references and finite-domain contract. This is consistent local traceability, not proof of all original algorithms, external review, costs, closed issues, or scientific phase completion. Historical backlog items remain individually unresolved where acceptance evidence is missing.

**Implementações vinculadas:** `description.md`, `tools/update_public_contracts.py`, `tools/check_public_contracts.py`, `docs/acceptance/vision_traceability.json`
**Testes vinculados:** `tests/test_public_contracts.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 066 — `docs/PLANO_MESTRE_2026_2056.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: manter contrato integrado, dependências, perfis de recursos e decisões por fase; atualizar custos e riscos. Aceite: alinhamento verificável entre metas, issues e entregas.

**Pendência registrada:** Machine-checked original requirement/phase/evidence references and finite-domain contract. This is consistent local traceability, not proof of all original algorithms, external review, costs, closed issues, or scientific phase completion. Historical backlog items remain individually unresolved where acceptance evidence is missing.

**Implementações vinculadas:** `docs/PLANO_MESTRE_2026_2056.md`, `tools/update_public_contracts.py`, `tools/check_public_contracts.py`, `docs/acceptance/vision_traceability.json`
**Testes vinculados:** `tests/test_public_contracts.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 067 — `docs/audits/PHASES_1_12_COMPLETION_BACKLOG.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: mapear os 104 itens aos módulos responsáveis, testes e evidências; adicionar fases F0/F13 e perfis de avanço posteriores. Aceite: cada requisito tem estado e prova de aceite.

**Pendência registrada:** Machine-checked original requirement/phase/evidence references and finite-domain contract. This is consistent local traceability, not proof of all original algorithms, external review, costs, closed issues, or scientific phase completion. Historical backlog items remain individually unresolved where acceptance evidence is missing.

**Implementações vinculadas:** `docs/audits/PHASES_1_12_COMPLETION_BACKLOG.md`, `tools/update_public_contracts.py`, `tools/check_public_contracts.py`, `docs/acceptance/vision_traceability.json`
**Testes vinculados:** `tests/test_public_contracts.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 068 — `docs/ARCHITECTURE_AND_ACCEPTANCE.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: materializar os critérios de render, física, relatórios, formalização e estabilidade em testes automatizados. Aceite: nenhum requisito crítico pendente sem sinalização.

**Pendência registrada:** Machine-checked original requirement/phase/evidence references and finite-domain contract. This is consistent local traceability, not proof of all original algorithms, external review, costs, closed issues, or scientific phase completion. Historical backlog items remain individually unresolved where acceptance evidence is missing.

**Implementações vinculadas:** `docs/ARCHITECTURE_AND_ACCEPTANCE.md`, `tools/update_public_contracts.py`, `tools/check_public_contracts.py`, `docs/acceptance/vision_traceability.json`
**Testes vinculados:** `tests/test_public_contracts.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 069 — `docs/MATHEMATICS_COMPLETION_AUDIT.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: verificar algoritmos matemáticos gerais faltantes e manter recusas explícitas em domínios não cobertos. Aceite: matriz por classe de problema, benchmark e prova.

**Pendência registrada:** Machine-checked original requirement/phase/evidence references and finite-domain contract. This is consistent local traceability, not proof of all original algorithms, external review, costs, closed issues, or scientific phase completion. Historical backlog items remain individually unresolved where acceptance evidence is missing.

**Implementações vinculadas:** `docs/MATHEMATICS_COMPLETION_AUDIT.md`, `tools/update_public_contracts.py`, `tools/check_public_contracts.py`, `docs/acceptance/vision_traceability.json`
**Testes vinculados:** `tests/test_public_contracts.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 070 — `src/nablamath/agents/sandbox.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: preservar proibição de código não confiável até existir sandbox real; não trocar bloqueio por eval/subprocess sem isolamento. Aceite: ataques e escapes bloqueados em ambiente isolado.

**Pendência registrada:** The existing complete prohibition of arbitrary code is preserved and verified; this is not execution of hostile code in a real OS sandbox. Escape-resistance certification remains blocked by that missing capability.

**Implementações vinculadas:** `src/nablamath/agents/sandbox.py`, `services/worker/isolation.py`
**Testes vinculados:** `tests/test_agents.py`, `tests/security/test_agent_sandbox.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 071 — `services/coordinator/app.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: expandir HTTP além de /health com auth, filas, quotas, auditoria, retries e cancelamentos. Aceite: integração inter-host, concorrência e testes de segurança.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `services/coordinator/app.py`
**Testes vinculados:** `tests/integration/test_coordinator_api.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 072 — `src/nablamath/desktop/app.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: migrar UI local limitada para interface integrada de todos os workflows sem abrir serviços inseguros. Aceite: E2E de um experimento completo com consentimento.

**Pendência registrada:** Real loopback HTTP E2E exact experiment with explicit consent and byte-identical API/direct receipt. No unrestricted execution, remote publishing, or claim of all-workflow UI coverage.

**Implementações vinculadas:** `src/nablamath/desktop/app.py`, `src/nablamath/desktop/workflows.py`, `src/nablamath/desktop/index.html`
**Testes vinculados:** `tests/test_remaining_product.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 073 — `src/nablamath/physics/fluids/navier_stokes.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: ultrapassar solver 2D periódico de referência com fronteiras, discretizações robustas e validação experimental. Aceite: benchmarks CFD, convergência e erro verificado.

**Pendência registrada:** Stationary no-slip channel reduction and existing 1D Euler reference only; general 2D nonperiodic Navier-Stokes, laboratory data and disciplinary review remain.

**Implementações vinculadas:** `src/nablamath/physics/fluids/channel.py`, `src/nablamath/physics/fluids/compressible.py`, `src/nablamath/physics/fluids/turbulence.py`
**Testes vinculados:** `tests/test_remaining_physics_gpu.py`, `tests/test_roadmap_physics_extensions.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 074 — `src/nablamath/physics/relativity/general.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: ampliar geometria Schwarzschild para tensores, geodésicas e perfis de GR definidos, não declarar solver geral prematuramente. Aceite: invariantes, testes de limite e confronto com referências.

**Pendência registrada:** Bounded analytic spatially-flat perfect-fluid FLRW plus Schwarzschild; not general numerical Einstein solver; historical rounded Mercury comparison is not new experimental validation.

**Implementações vinculadas:** `src/nablamath/physics/relativity/einstein_solver.py`, `src/nablamath/physics/relativity/general.py`
**Testes vinculados:** `tests/test_remaining_physics_gpu.py`, `tests/science/test_observational_validation.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 075 — `src/nablamath/gpu/cuda_f4_reduction.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: implementar backend CUDA/Triton verdadeiro e não atribuir aceleração ao fallback CPU. Aceite: speedup, hardware, exatidão e memória medidos.

**Pendência registrada:** CUDA hardware absent; kernel compilation/execution, speedup and energy require independent real-device runs. Exact CPU oracle checks every device result.

**Implementações vinculadas:** `src/nablamath/gpu/kernels/f4_cuda.py`, `src/nablamath/gpu/cuda_f4_reduction.py`
**Testes vinculados:** `tests/benchmark/test_gpu_real_hardware.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 076 — `src/nablamath/discovery/novelty_screen.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: integrar busca bibliográfica externa curada e revisão independente; não equiparar ausência local à novidade. Aceite: rastreio de referências, falsos positivos e revisão.

**Pendência registrada:** Traceable curated source/retrieval metadata and false-positive review; operator declarations only, no live comprehensive search or authenticated independent reviewers.

**Implementações vinculadas:** `src/nablamath/discovery/literature_search.py`, `src/nablamath/discovery/novelty_screen.py`
**Testes vinculados:** `tests/test_remaining_learning.py`, `tests/science/test_independent_discovery.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 077 — `src/nablamath/training/baselines.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: adicionar baselines fortes e métricas; manter vizinhos próximos como referência pequena, não como prova de ganho científico. Aceite: reprodução entre sementes, dados separados por família e comparação externa.

**Pendência registrada:** Actual deterministic fitted linear baseline; stronger LLM baselines and real external benchmark comparisons remain unfulfilled.

**Implementações vinculadas:** `src/nablamath/training/reasoning_finetune.py`, `src/nablamath/training/baselines.py`
**Testes vinculados:** `tests/test_remaining_learning.py`, `tests/benchmark/test_holdout_generalization.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 078 — `src/nablamath/training/multimodal_network.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: evoluir demonstração de equações/imagens para tarefas multimodais científicas relevantes com ablações. Aceite: ganho fora da distribuição em benchmarks congelados.

**Pendência registrada:** Existing multimodal neural fit plus generic transfer protocol; no claimed OOD scientific multimodal gain.

**Implementações vinculadas:** `src/nablamath/training/multimodal_network.py`, `src/nablamath/training/cross_domain_eval.py`
**Testes vinculados:** `tests/test_phase8_agents_training.py`, `tests/benchmark/test_holdout_generalization.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 079 — `src/nablamath/evolution/search.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: substituir busca apenas Euler/RK4 por propostas algorítmicas mais amplas avaliadas isoladamente. Aceite: ganho robusto contra baseline forte e rollback reproduzível.

**Pendência registrada:** Typed bounded proposals only; not general algorithm synthesis or demonstrated robust gain.

**Implementações vinculadas:** `src/nablamath/evolution/code_proposals.py`, `src/nablamath/evolution/secure_trials.py`, `src/nablamath/evolution/rollback.py`
**Testes vinculados:** `tests/security/test_agent_sandbox.py`, `tests/test_phase10_evolution.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 080 — `math.txt`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** intervenção específica: NÃO editar manualmente: reconstruir do gerador canônico após cada alteração do código. Aceite: tools/build_math_bundle.py --check aprovado.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `tools/build_math_bundle.py`
**Testes vinculados:** `tests/test_math_bundle.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`, `docs/audits/DELIVERY_2026_10_16.md`

## Requisito 081 — CRIAR `docs/acceptance/phase_profiles.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Definir perfis finitos F0–F13 e critérios versionados de aceite. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `docs/acceptance/phase_profiles.md`
**Testes vinculados:** `tests/test_roadmap_contract.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 082 — CRIAR `docs/acceptance/evidence_matrix.json`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Vincular requisito→teste→artefato→revisor→release. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `docs/acceptance/evidence_matrix.json`
**Testes vinculados:** `tests/test_roadmap_contract.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 083 — CRIAR `docs/acceptance/scientific_capabilities.yaml`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Especificar domínios suportados, recusados e tolerâncias. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Versioned queryable finite domains, explicit refusals and exact tolerance declarations are validated locally. Independent scientific review and release-specific acceptance remain pending.

**Implementações vinculadas:** `docs/acceptance/scientific_capabilities.yaml`, `src/nablamath/core/capabilities.py`
**Testes vinculados:** `tests/test_public_contracts.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 084 — CRIAR `docs/governance/independent_review_policy.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Estabelecer revisores independentes e conflitos de interesse. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `docs/governance/independent_review_policy.md`
**Testes vinculados:** `tests/test_roadmap_policy_links.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 085 — CRIAR `docs/governance/scientific_claims_policy.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Distinguir formal, numérico, empírico, sintético e hipotético. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `docs/governance/scientific_claims_policy.md`
**Testes vinculados:** `tests/test_roadmap_policy_links.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 086 — CRIAR `docs/strategy/roadmap_2026_2056.json`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Versionar marcos, dependências e mudanças de escopo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `docs/strategy/roadmap_2026_2056.json`
**Testes vinculados:** `tests/test_roadmap_contract.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 087 — CRIAR `docs/strategy/scientific_risk_register.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Gerenciar riscos científicos, operacionais e de segurança. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `docs/strategy/scientific_risk_register.md`
**Testes vinculados:** `tests/test_roadmap_policy_links.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 088 — CRIAR `docs/strategy/annual_reassessment.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Atualizar a visão sem fabricar conclusão. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `docs/strategy/annual_reassessment.md`
**Testes vinculados:** `tests/test_roadmap_policy_links.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 089 — CRIAR `src/nablamath/core/scientific_artifact.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Unificar hipótese, problema, solução, provas, simulações, imagens, datasets e documentos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/core/scientific_artifact.py`
**Testes vinculados:** `tests/integration/test_scientific_artifact.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 090 — CRIAR `src/nablamath/core/semantic_contracts.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Definir invariantes canônicos independentes da representação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/core/semantic_contracts.py`
**Testes vinculados:** `tests/test_semantic_contracts.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 091 — CRIAR `src/nablamath/core/migration_registry.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Versionar migração semântica de objetos científicos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/core/migration_registry.py`
**Testes vinculados:** `tests/test_semantic_contracts.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 092 — CRIAR `src/nablamath/core/uncertainty.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Representar incerteza e sua propagação de modo rastreável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/core/uncertainty.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 093 — CRIAR `src/nablamath/math/calculus/transcendentals.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Generalizar funções elementares e restrições de ramo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/math/calculus/transcendentals.py`
**Testes vinculados:** `tests/test_roadmap_math_extensions.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 094 — CRIAR `src/nablamath/math/calculus/risch.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Pesquisar integração simbólica abrangente sob domínios declarados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** General Risch integration and independent validation are not implemented.

**Implementações vinculadas:** `src/nablamath/math/calculus/risch.py`
**Testes vinculados:** `tests/test_roadmap_integration_mesh.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 095 — CRIAR `src/nablamath/math/linear_algebra/exact_decompositions.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Adicionar decomposições e certificados algébricos mais amplos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/math/linear_algebra/exact_decompositions.py`
**Testes vinculados:** `tests/test_roadmap_math_extensions.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 096 — CRIAR `src/nablamath/math/number_theory/factorization_advanced.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Desenvolver fatoração avançada com validação independente. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/math/number_theory/factorization_advanced.py`
**Testes vinculados:** `tests/test_roadmap_math_extensions.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 097 — CRIAR `src/nablamath/math/algebra/galois.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Implementar estruturas e algoritmos de teoria de Galois delimitados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/math/algebra/galois.py`
**Testes vinculados:** `tests/test_roadmap_algebra_logic.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 098 — CRIAR `src/nablamath/math/logic/smt_combination.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Pesquisar integração de teorias e certificados SMT. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/math/logic/smt_combination.py`
**Testes vinculados:** `tests/test_roadmap_algebra_logic.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 099 — CRIAR `src/nablamath/numeric/intervals.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Aritmética intervalar e limites certificados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/numeric/intervals.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 100 — CRIAR `src/nablamath/numeric/stiff_ode.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Solvers implícitos para EDOs rígidas e eventos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/numeric/stiff_ode.py`
**Testes vinculados:** `tests/test_roadmap_math_extensions.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 101 — CRIAR `src/nablamath/numeric/pde_general.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Contratos para EDPs e condições de contorno extensíveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/numeric/pde_general.py`
**Testes vinculados:** `tests/test_roadmap_worlds_observations.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 102 — CRIAR `src/nablamath/forge/compositional_generator.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Compor famílias de problemas com soluções conhecidas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/forge/compositional_generator.py`
**Testes vinculados:** `tests/test_roadmap_forge_discovery.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 103 — CRIAR `src/nablamath/forge/adversarial_generator.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Gerar problemas difíceis e detectar atalhos indevidos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/forge/adversarial_generator.py`
**Testes vinculados:** `tests/test_roadmap_forge_discovery.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 104 — CRIAR `src/nablamath/forge/difficulty_calibration.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Definir dificuldade condicional a solver e recursos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/forge/difficulty_calibration.py`
**Testes vinculados:** `tests/test_roadmap_forge_discovery.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 105 — CRIAR `src/nablamath/forge/novelty_index.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Deduplicação estrutural e semântica escalável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/forge/novelty_index.py`
**Testes vinculados:** `tests/test_roadmap_forge_discovery.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 106 — CRIAR `src/nablamath/formal/autoformalization.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Pipeline de tradução com verificação humana e kernel. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Controlled grammar only; review identity is caller supplied. Lean/Mathlib execution, human correspondence review and scalable proof search remain unvalidated.

**Implementações vinculadas:** `src/nablamath/formal/autoformalization.py`, `src/nablamath/formal/proof_repair.py`, `src/nablamath/formal/proof_search_planner.py`
**Testes vinculados:** `tests/test_roadmap_formal_workflows.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 107 — CRIAR `src/nablamath/formal/proof_repair.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Correção assistida de demonstrações sem suprimir obrigações. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Controlled grammar only; review identity is caller supplied. Lean/Mathlib execution, human correspondence review and scalable proof search remain unvalidated.

**Implementações vinculadas:** `src/nablamath/formal/autoformalization.py`, `src/nablamath/formal/proof_repair.py`, `src/nablamath/formal/proof_search_planner.py`
**Testes vinculados:** `tests/test_roadmap_formal_workflows.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 108 — CRIAR `src/nablamath/formal/proof_search_planner.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Busca escalável guiada por hipóteses e provas verificáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Controlled grammar only; review identity is caller supplied. Lean/Mathlib execution, human correspondence review and scalable proof search remain unvalidated.

**Implementações vinculadas:** `src/nablamath/formal/autoformalization.py`, `src/nablamath/formal/proof_repair.py`, `src/nablamath/formal/proof_search_planner.py`
**Testes vinculados:** `tests/test_roadmap_formal_workflows.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 109 — CRIAR `src/nablamath/falsifier/property_engine.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Falsificação sistemática por propriedades e domínios. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/falsifier/property_engine.py`
**Testes vinculados:** `tests/test_roadmap_forge_discovery.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 110 — CRIAR `src/nablamath/gpu/kernels/f4_cuda.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Backend de referência para kernel CUDA verificável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** CUDA hardware absent; kernel compilation/execution, speedup and energy require independent real-device runs. Exact CPU oracle checks every device result.

**Implementações vinculadas:** `src/nablamath/gpu/kernels/f4_cuda.py`, `src/nablamath/gpu/cuda_f4_reduction.py`
**Testes vinculados:** `tests/benchmark/test_gpu_real_hardware.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 111 — CRIAR `src/nablamath/gpu/kernels/egraph_triton.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Backend Triton opcional para operações bateladas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Triton execution requires hardware/dependency validation; implements parent canonicalization only, not full GPU e-graph saturation.

**Implementações vinculadas:** `src/nablamath/gpu/kernels/egraph_triton.py`
**Testes vinculados:** `tests/test_remaining_physics_gpu.py`, `tests/benchmark/test_gpu_real_hardware.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 112 — CRIAR `src/nablamath/gpu/profiler.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Telemetria reprodutível de VRAM, tempo e energia. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** No GPU available. Energy integration and peak VRAM absent explicitly null; no speedup claim.

**Implementações vinculadas:** `src/nablamath/gpu/profiler.py`, `benchmarks/resources/hardware_profiles.json`
**Testes vinculados:** `tests/test_remaining_physics_gpu.py`, `tests/benchmark/test_gpu_real_hardware.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 113 — CRIAR `src/nablamath/worlds/boundary_conditions.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Representar contornos gerais de simulações. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/worlds/boundary_conditions.py`
**Testes vinculados:** `tests/test_roadmap_worlds_observations.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 114 — CRIAR `src/nablamath/worlds/mesh/adaptive.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Refino adaptativo com estimadores de erro. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Sampled indicators are not a global error certificate; general multidimensional meshes remain pending.

**Implementações vinculadas:** `src/nablamath/worlds/mesh/adaptive.py`
**Testes vinculados:** `tests/test_roadmap_integration_mesh.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 115 — CRIAR `src/nablamath/worlds/validation_observational.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Confrontar simulações com medições observadas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/worlds/validation_observational.py`
**Testes vinculados:** `tests/test_roadmap_worlds_observations.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 116 — CRIAR `src/nablamath/worlds/uncertainty_quantification.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Propagação de incerteza nos modelos físicos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/worlds/uncertainty_quantification.py`
**Testes vinculados:** `tests/test_roadmap_worlds_observations.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 117 — CRIAR `src/nablamath/physics/fluids/turbulence.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Modelos de turbulência delimitados e calibrados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Only declared 1D models and local analytic/synthetic checks; external calibration, experimental provenance and independent validation remain pending.

**Implementações vinculadas:** `src/nablamath/physics/fluids/turbulence.py`, `src/nablamath/physics/fluids/compressible.py`, `src/nablamath/physics/fea/nonlinear.py`
**Testes vinculados:** `tests/test_roadmap_physics_extensions.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 118 — CRIAR `src/nablamath/physics/fluids/compressible.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Fluxos compressíveis e choques com validação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Only declared 1D models and local analytic/synthetic checks; external calibration, experimental provenance and independent validation remain pending.

**Implementações vinculadas:** `src/nablamath/physics/fluids/turbulence.py`, `src/nablamath/physics/fluids/compressible.py`, `src/nablamath/physics/fea/nonlinear.py`
**Testes vinculados:** `tests/test_roadmap_physics_extensions.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 119 — CRIAR `src/nablamath/physics/relativity/einstein_solver.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Estudo modular de soluções de Einstein sem alegar generalidade automática. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded analytic spatially-flat perfect-fluid FLRW plus Schwarzschild; not general numerical Einstein solver; historical rounded Mercury comparison is not new experimental validation.

**Implementações vinculadas:** `src/nablamath/physics/relativity/einstein_solver.py`, `src/nablamath/physics/relativity/general.py`
**Testes vinculados:** `tests/test_remaining_physics_gpu.py`, `tests/science/test_observational_validation.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 120 — CRIAR `src/nablamath/physics/fea/nonlinear.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Elementos finitos não lineares e verificação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Only declared 1D models and local analytic/synthetic checks; external calibration, experimental provenance and independent validation remain pending.

**Implementações vinculadas:** `src/nablamath/physics/fluids/turbulence.py`, `src/nablamath/physics/fluids/compressible.py`, `src/nablamath/physics/fea/nonlinear.py`
**Testes vinculados:** `tests/test_roadmap_physics_extensions.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 121 — CRIAR `src/nablamath/graphics/visual_regression.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Comparar renderização semântica e imagens de referência. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Declared linear SCM only, no causal discovery from correlation; human visual review and empirical causal validation remain pending.

**Implementações vinculadas:** `src/nablamath/graphics/visual_regression.py`, `src/nablamath/graphics/scientific_renderer.py`, `src/nablamath/discovery/causal_hypothesis.py`
**Testes vinculados:** `tests/test_roadmap_graphics_causality.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 122 — CRIAR `src/nablamath/graphics/scientific_renderer.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Renderização científica avançada rastreável ao modelo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Declared linear SCM only, no causal discovery from correlation; human visual review and empirical causal validation remain pending.

**Implementações vinculadas:** `src/nablamath/graphics/visual_regression.py`, `src/nablamath/graphics/scientific_renderer.py`, `src/nablamath/discovery/causal_hypothesis.py`
**Testes vinculados:** `tests/test_roadmap_graphics_causality.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 123 — CRIAR `src/nablamath/documents/reference_graph.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Referências cruzadas e dependências de alegações em documentos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/documents/reference_graph.py`
**Testes vinculados:** `tests/test_evidence_integration_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 124 — CRIAR `src/nablamath/documents/editorial_review.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Fluxo de revisão e qualidade editorial. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/documents/editorial_review.py`
**Testes vinculados:** `tests/test_roadmap_editorial_governance.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 125 — CRIAR `src/nablamath/datasets/corpus_registry.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Registro de corpora e licenças externas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/datasets/corpus_registry.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 126 — CRIAR `src/nablamath/datasets/semantic_leakage.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Detecção avançada de contaminação e semelhança. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Declared local equivalences and lineage only; no universal semantic detector or independently evaluated production scale.

**Implementações vinculadas:** `src/nablamath/datasets/semantic_leakage.py`, `src/nablamath/datasets/large_scale_pipeline.py`
**Testes vinculados:** `tests/test_roadmap_dataset_pipeline.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 127 — CRIAR `src/nablamath/datasets/large_scale_pipeline.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Geração controlada em escala sem degradar qualidade. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Declared local equivalences and lineage only; no universal semantic detector or independently evaluated production scale.

**Implementações vinculadas:** `src/nablamath/datasets/semantic_leakage.py`, `src/nablamath/datasets/large_scale_pipeline.py`
**Testes vinculados:** `tests/test_roadmap_dataset_pipeline.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 128 — CRIAR `src/nablamath/training/frontier_adapter.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Adaptadores opcionais de modelos de fronteira com consentimento. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Explicit owner/version/input-digest consent, default disabled, caller-injected transport only. No built-in network or frontier provider evaluation.

**Implementações vinculadas:** `src/nablamath/training/frontier_adapter.py`
**Testes vinculados:** `tests/test_remaining_learning.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 129 — CRIAR `src/nablamath/training/reasoning_finetune.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Treino de raciocínio com protocolos congelados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Content-digest-frozen actual supervised linear fitting, deterministic bounded optimizer. Does not fine tune an LLM or prove learned reasoning.

**Implementações vinculadas:** `src/nablamath/training/reasoning_finetune.py`
**Testes vinculados:** `tests/test_remaining_learning.py`, `tests/benchmark/test_holdout_generalization.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 130 — CRIAR `src/nablamath/training/cross_domain_eval.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Medir generalização entre famílias e disciplinas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Task/family/semantic overlap checks and per-domain Wilson intervals on supplied cases. True external unseen cases remain external.

**Implementações vinculadas:** `src/nablamath/training/cross_domain_eval.py`
**Testes vinculados:** `tests/benchmark/test_holdout_generalization.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 131 — CRIAR `src/nablamath/training/compute_accounting.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Rastrear custo, energia e recursos por ganho útil. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/training/compute_accounting.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 132 — CRIAR `src/nablamath/agents/secure_execution.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Sandbox operacional para código não confiável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Arbitrary code is refused. Hostile-code OS sandbox, capability isolation and escape-resistance validation are NOT implemented; this is a trusted-tool operational precursor.

**Implementações vinculadas:** `src/nablamath/agents/secure_execution.py`, `src/nablamath/evolution/code_proposals.py`, `src/nablamath/evolution/secure_trials.py`, `services/worker/isolation.py`
**Testes vinculados:** `tests/security/test_agent_sandbox.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 133 — CRIAR `src/nablamath/agents/experiment_planner.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Planejamento de experimentos científicos revisáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/agents/experiment_planner.py`
**Testes vinculados:** `tests/test_roadmap_agent_controls.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 134 — CRIAR `src/nablamath/agents/human_approval.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Autorizações explícitas para instrumentos, redes e publicação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/agents/human_approval.py`
**Testes vinculados:** `tests/test_roadmap_agent_controls.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 135 — CRIAR `src/nablamath/discovery/literature_search.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Busca de antecedentes em fontes científicas externas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Curated supplied external metadata snapshots; no built-in live fetch, source authentication, comprehensive coverage or novelty guarantee.

**Implementações vinculadas:** `src/nablamath/discovery/literature_search.py`
**Testes vinculados:** `tests/test_remaining_learning.py`, `tests/science/test_independent_discovery.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 136 — CRIAR `src/nablamath/discovery/causal_hypothesis.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Hipóteses causais testáveis com pressupostos declarados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Declared linear SCM only, no causal discovery from correlation; human visual review and empirical causal validation remain pending.

**Implementações vinculadas:** `src/nablamath/graphics/visual_regression.py`, `src/nablamath/graphics/scientific_renderer.py`, `src/nablamath/discovery/causal_hypothesis.py`
**Testes vinculados:** `tests/test_roadmap_graphics_causality.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 137 — CRIAR `src/nablamath/discovery/lab_protocol.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Protocolos de execução e reprodutibilidade de experimentos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/discovery/lab_protocol.py`
**Testes vinculados:** `tests/test_roadmap_forge_discovery.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 138 — CRIAR `src/nablamath/discovery/independent_replication.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Registro de replicações independentes. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/discovery/independent_replication.py`
**Testes vinculados:** `tests/test_roadmap_editorial_governance.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 139 — CRIAR `src/nablamath/evolution/code_proposals.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Propostas de mudanças algorítmicas versionadas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Arbitrary code is refused. Hostile-code OS sandbox, capability isolation and escape-resistance validation are NOT implemented; this is a trusted-tool operational precursor.

**Implementações vinculadas:** `src/nablamath/agents/secure_execution.py`, `src/nablamath/evolution/code_proposals.py`, `src/nablamath/evolution/secure_trials.py`, `services/worker/isolation.py`
**Testes vinculados:** `tests/security/test_agent_sandbox.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 140 — CRIAR `src/nablamath/evolution/frozen_evaluator.py`

**Estado declarado:** partial. **Caminho:** caminho proposto/ausente.

**Conteúdo/aceite pretendido:** Avaliador separado da autoridade do proponente. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** External operator isolation, authenticated independent review, private holdout administration and full original acceptance remain required.

**Implementações vinculadas:** `src/nablamath/evaluation/frozen.py`
**Testes vinculados:** `tests/evaluation/test_frozen.py`
**Evidências vinculadas:** `docs/audits/FROZEN_EVALUATION_2026_10_15.md`

## Requisito 141 — CRIAR `src/nablamath/evolution/secure_trials.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Testes isolados de descendentes candidatos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Arbitrary code is refused. Hostile-code OS sandbox, capability isolation and escape-resistance validation are NOT implemented; this is a trusted-tool operational precursor.

**Implementações vinculadas:** `src/nablamath/agents/secure_execution.py`, `src/nablamath/evolution/code_proposals.py`, `src/nablamath/evolution/secure_trials.py`, `services/worker/isolation.py`
**Testes vinculados:** `tests/security/test_agent_sandbox.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 142 — CRIAR `src/nablamath/evolution/longitudinal_monitor.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Medição de ganhos sustentados e regressões. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/evolution/longitudinal_monitor.py`
**Testes vinculados:** `tests/test_evidence_integration_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 143 — CRIAR `src/nablamath/knowledge/institutional_identity.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Vínculo de identidade real e competências auditáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `src/nablamath/knowledge/institutional_identity.py`
**Testes vinculados:** `tests/test_remaining_federation.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 144 — CRIAR `src/nablamath/knowledge/distributed_provenance.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Proveniência multioperador e revogação verificável. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `src/nablamath/knowledge/distributed_provenance.py`
**Testes vinculados:** `tests/test_remaining_federation.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 145 — CRIAR `src/nablamath/knowledge/replication_protocol.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Replicação de alegações e revisões externas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/knowledge/replication_protocol.py`
**Testes vinculados:** `tests/test_roadmap_editorial_governance.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 146 — CRIAR `src/nablamath/knowledge/retraction_index.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Retratação propagada a artefatos dependentes. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/knowledge/retraction_index.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 147 — CRIAR `services/coordinator/api.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** API autenticada de coordenação e quotas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `services/coordinator/api.py`
**Testes vinculados:** `tests/integration/test_coordinator_api.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 148 — CRIAR `services/coordinator/task_leases.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Leases duráveis, heartbeats e idempotência. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `services/coordinator/task_leases.py`, `src/nablamath/coordination/local.py`
**Testes vinculados:** `tests/integration/test_coordinator_api.py`, `tests/test_roadmap_worker_execution.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`, `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 149 — CRIAR `services/coordinator/telemetry.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Observabilidade preservando privacidade. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `services/coordinator/telemetry.py`
**Testes vinculados:** `tests/test_roadmap_worker_execution.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 150 — CRIAR `services/worker/executor.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Worker de tarefas tipadas, com limites e cancelamento. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `services/worker/executor.py`
**Testes vinculados:** `tests/test_roadmap_worker_execution.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 151 — CRIAR `services/worker/isolation.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Isolamento operacional e política de recursos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Arbitrary code is refused. Hostile-code OS sandbox, capability isolation and escape-resistance validation are NOT implemented; this is a trusted-tool operational precursor.

**Implementações vinculadas:** `src/nablamath/agents/secure_execution.py`, `src/nablamath/evolution/code_proposals.py`, `src/nablamath/evolution/secure_trials.py`, `services/worker/isolation.py`
**Testes vinculados:** `tests/security/test_agent_sandbox.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 152 — CRIAR `services/federation/reconciliation.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Federação entre organizações e resolução de conflitos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `services/federation/reconciliation.py`
**Testes vinculados:** `tests/network/test_partition.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 153 — CRIAR `sdk/python/README.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Contrato público de SDK Python. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `sdk/python/client.py`
**Testes vinculados:** `tests/interop/test_coordinator_clients.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 154 — CRIAR `sdk/typescript/README.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Cliente interoperável para UI web. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `sdk/typescript/client.ts`
**Testes vinculados:** `tests/interop/test_coordinator_clients.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 155 — CRIAR `sdk/rust/src/client.rs`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Cliente Rust de protocolo científico completo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `sdk/rust/src/client.rs`
**Testes vinculados:** `tests/network/test_interop.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 156 — CRIAR `tests/integration/test_scientific_artifact.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Ciclo completo e ataques em cada vínculo do artefato. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `tests/integration/test_scientific_artifact.py`
**Testes vinculados:** `tests/integration/test_scientific_artifact.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 157 — CRIAR `tests/integration/test_global_scientific_cycle.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Integração F1–F12 com avaliação honesta de lacunas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `tools/expanded_scientific_cycle.py`
**Testes vinculados:** `tests/integration/test_global_scientific_cycle.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 158 — CRIAR `tests/security/test_agent_sandbox.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Tentativas de escape e falha segura. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Arbitrary code is refused. Hostile-code OS sandbox, capability isolation and escape-resistance validation are NOT implemented; this is a trusted-tool operational precursor.

**Implementações vinculadas:** `src/nablamath/agents/secure_execution.py`, `src/nablamath/evolution/code_proposals.py`, `src/nablamath/evolution/secure_trials.py`, `services/worker/isolation.py`
**Testes vinculados:** `tests/security/test_agent_sandbox.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 159 — CRIAR `tests/security/test_supply_chain.py`

**Estado declarado:** partial. **Caminho:** caminho proposto/ausente.

**Conteúdo/aceite pretendido:** Dependências, segredos e provenance de builds. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `tools/verify_wheel.py`
**Testes vinculados:** `tests/test_roadmap_resources_supplychain.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 160 — CRIAR `tests/benchmark/test_math_comparison.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Benchmarks de solvers especializados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Version1 correctness comparison contract records owner, fixed seeds and128 exact rational plus32 analytic Hessian independent SymPy cases. No speed ranking, no external approval asserted; performance benchmarking and independent reviewer remain pending.

**Implementações vinculadas:** `src/nablamath/compiler/ir.py`, `src/nablamath/autodiff/second_order.py`
**Testes vinculados:** `tests/benchmark/test_math_comparison.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 161 — CRIAR `tests/benchmark/test_gpu_real_hardware.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Aceleração real mensurada e conferida. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** No GPU available. Energy integration and peak VRAM absent explicitly null; no speedup claim.

**Implementações vinculadas:** `src/nablamath/gpu/profiler.py`, `benchmarks/resources/hardware_profiles.json`
**Testes vinculados:** `tests/test_remaining_physics_gpu.py`, `tests/benchmark/test_gpu_real_hardware.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 162 — CRIAR `tests/benchmark/test_holdout_generalization.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Generalização fora do treino sem vazamento. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Executed synthetic family holdouts, negative results and contamination rejection, not a measured frontier generalization gain.

**Implementações vinculadas:** `src/nablamath/training/cross_domain_eval.py`
**Testes vinculados:** `tests/benchmark/test_holdout_generalization.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 163 — CRIAR `tests/science/test_observational_validation.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Dados empíricos, calibração e incerteza. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Historical rounded Mercury reference and caller-supplied measurements are not independent provenance authentication, discipline-wide validation, or specialist review.

**Implementações vinculadas:** `src/nablamath/worlds/validation_observational.py`, `src/nablamath/domains/chemistry/kinetics.py`, `src/nablamath/domains/materials/elasticity.py`, `src/nablamath/physics/relativity/general.py`
**Testes vinculados:** `tests/test_roadmap_worlds_observations.py`, `tests/science/test_observational_validation.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 164 — CRIAR `tests/science/test_independent_discovery.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Reprodução de resultados científicos com revisores externos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Actual protocol conformance and negative replication bookkeeping; test fixtures are not external reviewers or independent scientific replication.

**Implementações vinculadas:** `src/nablamath/discovery/independent_replication.py`
**Testes vinculados:** `tests/science/test_independent_discovery.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 165 — CRIAR `tests/distributed/test_multihost_failures.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Redes reais, perdas, partições e recuperação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `services/federation/reconciliation.py`
**Testes vinculados:** `tests/distributed/test_multihost_failures.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 166 — CRIAR `benchmarks/protocols/README.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Registro prévio de métricas, sementes, grupos e baselines. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `benchmarks/protocols/README.md`
**Testes vinculados:** `tests/test_roadmap_policy_links.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 167 — CRIAR `benchmarks/resources/hardware_profiles.json`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Ambientes de referência e budgets documentados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** No GPU available. Energy integration and peak VRAM absent explicitly null; no speedup claim.

**Implementações vinculadas:** `src/nablamath/gpu/profiler.py`, `benchmarks/resources/hardware_profiles.json`
**Testes vinculados:** `tests/test_remaining_physics_gpu.py`, `tests/benchmark/test_gpu_real_hardware.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 168 — CRIAR `benchmarks/external/README.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Catálogo de comparações externas com licenças. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `benchmarks/external/README.md`
**Testes vinculados:** `tests/test_roadmap_policy_links.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 169 — CRIAR `.github/workflows/security.yml`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Análise estática, dependências e segredos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `.github/workflows/security.yml`
**Testes vinculados:** `tests/test_roadmap_network_security.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 170 — CRIAR `.github/workflows/full-integration.yml`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Perfil integrado e replay end-to-end. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `.github/workflows/full-integration.yml`
**Testes vinculados:** `tests/integration/test_global_scientific_cycle.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 171 — CRIAR `.github/workflows/scientific-benchmarks.yml`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Execuções científicas agendadas e diferenciadas dos unit tests. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `.github/workflows/scientific-benchmarks.yml`
**Testes vinculados:** `tests/test_roadmap_math_extensions.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 172 — CRIAR `.github/workflows/release-attestation.yml`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Integridade, SBOM e proveniência por release. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `.github/workflows/release-attestation.yml`
**Testes vinculados:** `tests/test_roadmap_resources_supplychain.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 173 — CRIAR `configs/profiles/cpu_conservative.yaml`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Limites para PCs domésticos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `configs/profiles/cpu_conservative.yaml`
**Testes vinculados:** `tests/test_roadmap_resources_supplychain.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 174 — CRIAR `configs/profiles/cpu_balanced.yaml`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Perfil doméstico equilibrado. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `configs/profiles/cpu_balanced.yaml`
**Testes vinculados:** `tests/test_roadmap_resources_supplychain.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 175 — CRIAR `configs/profiles/gpu_local.yaml`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Orçamentos de VRAM/GPU local. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `configs/profiles/gpu_local.yaml`
**Testes vinculados:** `tests/test_roadmap_resources_supplychain.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 176 — CRIAR `configs/profiles/research_station.yaml`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Perfil de estação profissional. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `configs/profiles/research_station.yaml`
**Testes vinculados:** `tests/test_roadmap_resources_supplychain.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 177 — CRIAR `configs/profiles/hpc_optional.yaml`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Escalamento opcional, sem pressupor HPC obrigatório. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `configs/profiles/hpc_optional.yaml`
**Testes vinculados:** `tests/test_roadmap_resources_supplychain.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 178 — CRIAR `src/nablamath/network/signatures.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Assinatura assimétrica, rotação e revogação de chaves no protocolo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/network/signatures.py`
**Testes vinculados:** `tests/test_roadmap_network_security.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 179 — CRIAR `src/nablamath/node/identity.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Identidade local consentida com chaves e política de recuperação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/node/identity.py`
**Testes vinculados:** `tests/test_roadmap_network_security.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 180 — CRIAR `src/nablamath/p2p/moderation.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Quarentena, limites de abuso e moderação auditáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/p2p/moderation.py`
**Testes vinculados:** `tests/test_roadmap_network_security.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 181 — CRIAR `src/nablamath/p2p/reputation.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Sinais antiabuso sem equiparar popularidade à verdade científica. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/p2p/reputation.py`
**Testes vinculados:** `tests/test_roadmap_network_security.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 182 — CRIAR `services/registry/app.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Registro seguro e opt-in de nós e capacidades. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Implementações vinculadas:** `services/registry/app.py`, `services/registry/api.py`, `services/registry/db.py`, `services/registry/metrics.py`, `services/relay/app.py`, `services/relay/protocol.py`, `services/relay/abuse.py`
**Testes vinculados:** `tests/network/test_registry_relay.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 183 — CRIAR `services/registry/api.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** API de descoberta e permissões versionadas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Implementações vinculadas:** `services/registry/app.py`, `services/registry/api.py`, `services/registry/db.py`, `services/registry/metrics.py`, `services/relay/app.py`, `services/relay/protocol.py`, `services/relay/abuse.py`
**Testes vinculados:** `tests/network/test_registry_relay.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 184 — CRIAR `services/registry/db.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Persistência de peers, chaves e estado de revogação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Implementações vinculadas:** `services/registry/app.py`, `services/registry/api.py`, `services/registry/db.py`, `services/registry/metrics.py`, `services/relay/app.py`, `services/relay/protocol.py`, `services/relay/abuse.py`
**Testes vinculados:** `tests/network/test_registry_relay.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 185 — CRIAR `services/registry/metrics.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Métricas anonimizadas e limites operacionais. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Implementações vinculadas:** `services/registry/app.py`, `services/registry/api.py`, `services/registry/db.py`, `services/registry/metrics.py`, `services/relay/app.py`, `services/relay/protocol.py`, `services/relay/abuse.py`
**Testes vinculados:** `tests/network/test_registry_relay.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 186 — CRIAR `services/relay/app.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Relay autenticado com quotas e desligamento seguro. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Implementações vinculadas:** `services/registry/app.py`, `services/registry/api.py`, `services/registry/db.py`, `services/registry/metrics.py`, `services/relay/app.py`, `services/relay/protocol.py`, `services/relay/abuse.py`
**Testes vinculados:** `tests/network/test_registry_relay.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 187 — CRIAR `services/relay/protocol.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Protocolos para NAT/retransmissão com proteção anti-replay. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Implementações vinculadas:** `services/registry/app.py`, `services/registry/api.py`, `services/registry/db.py`, `services/registry/metrics.py`, `services/relay/app.py`, `services/relay/protocol.py`, `services/relay/abuse.py`
**Testes vinculados:** `tests/network/test_registry_relay.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 188 — CRIAR `services/relay/abuse.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Prevenção de Sybil/eclipse/poisoning e registros auditáveis. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Loopback deployment only. No NAT traversal, general Sybil/eclipse/poisoning resistance, institutional identity, anonymity proof or independent Internet-scale validation.

**Implementações vinculadas:** `services/registry/app.py`, `services/registry/api.py`, `services/registry/db.py`, `services/registry/metrics.py`, `services/relay/app.py`, `services/relay/protocol.py`, `services/relay/abuse.py`
**Testes vinculados:** `tests/network/test_registry_relay.py`
**Evidências vinculadas:** `docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md`

## Requisito 189 — CRIAR `tests/network/test_sybil.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Testes de identidades artificiais e resiliência de federação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `src/nablamath/p2p/resilient_peers.py`
**Testes vinculados:** `tests/network/test_sybil.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 190 — CRIAR `tests/network/test_poisoning.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Injeção de resultados, hashes e assinaturas adulteradas. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `src/nablamath/knowledge/distributed_provenance.py`
**Testes vinculados:** `tests/network/test_poisoning.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 191 — CRIAR `tests/network/test_eclipse.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Isolamento de peers e respostas resistentes a eclipse. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `src/nablamath/p2p/resilient_peers.py`
**Testes vinculados:** `tests/network/test_eclipse.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 192 — CRIAR `tests/network/test_partition.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Partições prolongadas de rede e reconciliação. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `services/federation/reconciliation.py`
**Testes vinculados:** `tests/network/test_partition.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 193 — CRIAR `tests/network/test_interop.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Interoperabilidade real entre implementações de protocolo. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `sdk/python/rational.py`, `sdk/typescript/rational.ts`
**Testes vinculados:** `tests/network/test_interop.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 194 — CRIAR `src/nablamath/knowledge/lineage.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Dependências entre conhecimento, dados e retratações. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/knowledge/lineage.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 195 — CRIAR `src/nablamath/knowledge/novelty.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Novidade relativa a corpus e revisão bibliográfica independente. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/knowledge/novelty.py`
**Testes vinculados:** `tests/test_roadmap_editorial_governance.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 196 — CRIAR `src/nablamath/knowledge/difficulty.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Dificuldade sustentada por orçamento e solvers observados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/knowledge/difficulty.py`
**Testes vinculados:** `tests/test_roadmap_editorial_governance.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 197 — CRIAR `src/nablamath/knowledge/curriculum.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Currículos científicos com diversidade e utilidade medida. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/knowledge/curriculum.py`
**Testes vinculados:** `tests/test_roadmap_editorial_governance.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 198 — CRIAR `src/nablamath/verification/independence.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Política de independência entre proponente, solver e avaliador. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/verification/independence.py`
**Testes vinculados:** `tests/test_semantic_contracts.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 199 — CRIAR `src/nablamath/verification/evidence.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Tipos e obrigatoriedade de evidência para diferentes alegações. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Full original acceptance, independent review and external evidence remain required.

**Implementações vinculadas:** `src/nablamath/verification/evidence.py`
**Testes vinculados:** `tests/test_semantic_contracts.py`
**Evidências vinculadas:** `docs/audits/P0_INTEGRATION_2026_10_15.md`

## Requisito 200 — CRIAR `src/nablamath/verification/consensus.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Consenso sobre recibos sem confundi-lo com verdade científica. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/verification/consensus.py`
**Testes vinculados:** `tests/test_evidence_integration_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 201 — CRIAR `src/nablamath/evaluation/calibration.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Curvas de calibração, generalização e análise de robustez. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/evaluation/calibration.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 202 — CRIAR `src/nablamath/evaluation/ablation.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Ablation com avaliador congelado e comparação justa. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/evaluation/ablation.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 203 — CRIAR `src/nablamath/training/snapshot.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Snapshots imutáveis de modelos e dados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/training/snapshot.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 204 — CRIAR `src/nablamath/training/mixture.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Misturas de dados e auditoria de contribuição por fonte. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/training/mixture.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 205 — CRIAR `src/nablamath/training/lineage.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Linhagem de checkpoints, pesos e corpus de treinamento. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Bounded local profile only; full original acceptance, external validation and independent review remain outstanding. See docs/acceptance/expanded_profiles.md.

**Implementações vinculadas:** `src/nablamath/training/lineage.py`
**Testes vinculados:** `tests/test_roadmap_expansion.py`
**Evidências vinculadas:** `docs/audits/EXPANDED_PROFILES_2026_10_15.md`

## Requisito 206 — CRIAR `benchmarks/private/README.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Processos para holdouts administrados por avaliadores externos. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `benchmarks/private/README.md`
**Testes vinculados:** `tests/test_roadmap_policy_links.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 207 — CRIAR `benchmarks/contamination/README.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Testes adversariais e padrões de vazamento de dados. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `benchmarks/contamination/README.md`
**Testes vinculados:** `tests/test_roadmap_policy_links.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 208 — CRIAR `protocol/fixtures/cross-language/README.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Vetores normativos verificados por SDKs C/C++/Rust/TS/Python. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Pinned local trust and measured loopback/process tests only; independent institutional verification, independent multihost/WAN deployment, real Sybil resistance and release/API/ABI audit remain unvalidated. Rust canonical-fraction and bounded loopback HTTP client executed; remote TLS/full SDK/API/ABI audit still pending.

**Implementações vinculadas:** `protocol/fixtures/cross-language/README.md`, `protocol/fixtures/cross-language/rational-v1.json`
**Testes vinculados:** `tests/network/test_interop.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 209 — CRIAR `src/nablamath/singularity/evaluation/generalization.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Benchmark multidisciplinar de transferibilidade sem declarar AGI. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Fail-closed report consistency, duplicate-task rejection and declared per-domain thresholds; no AGI or independent benchmark authenticity claim.

**Implementações vinculadas:** `src/nablamath/singularity/evaluation/generalization.py`
**Testes vinculados:** `tests/benchmark/test_holdout_generalization.py`
**Evidências vinculadas:** `docs/audits/REMAINING_85_2026_10_15.md`

## Requisito 210 — CRIAR `src/nablamath/singularity/evaluation/safety.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Avaliar autonomia, permissões e falhas por agente. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/singularity/evaluation/safety.py`
**Testes vinculados:** `tests/test_roadmap_agent_controls.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 211 — CRIAR `src/nablamath/singularity/evaluation/long_horizon.py`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Avaliação de projetos científicos longos com intervenção humana. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `src/nablamath/singularity/evaluation/long_horizon.py`
**Testes vinculados:** `tests/test_roadmap_agent_controls.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 212 — CRIAR `docs/future/F13_OPEN_RESEARCH.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Requisitos prospectivos abertos e governança de descobertas pós-2056. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `docs/future/F13_OPEN_RESEARCH.md`
**Testes vinculados:** `tests/test_roadmap_policy_links.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`

## Requisito 213 — CRIAR `docs/future/2035_2045_2056_criteria.md`

**Estado declarado:** partial. **Caminho:** arquivo existente.

**Conteúdo/aceite pretendido:** Critérios técnicos revisáveis com indicadores de sucesso/falha. Só criar após aprovar contrato e responsável; exigir testes, versionamento, avaliação independente e evidência.

**Pendência registrada:** Finite implementation or proposed policy only; full original acceptance, external review, unsupported domains and unexecuted workflows remain outstanding. See docs/acceptance/parallel_profiles.md.

**Implementações vinculadas:** `docs/future/2035_2045_2056_criteria.md`
**Testes vinculados:** `tests/test_roadmap_policy_links.py`
**Evidências vinculadas:** `docs/audits/PARALLEL_IMPLEMENTATION_2026_10_15.md`
