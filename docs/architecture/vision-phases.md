# Caminhos para as fases 0–13

Gerado de `vision.md` por `python tools/project_inventory.py --phases`. Existência de arquivo não comprova conclusão de fase. Fases 1–8 têm implementações delimitadas e testes; as fases seguintes possuem bases parciais ou permanecem planejadas. A fase 13 é um horizonte aberto, sem lista fechada de arquivos.

## Regras de organização

- `src/nablamath/`: API canônica; `tests/`: verificações independentes; `lean/Nabla/`: provas.
- `legacy/current_scripts/`: acervo preservado; fora da descoberta de testes e do pacote instalado.
- `lean/lakefile.toml`: configuração única; `lake-manifest.json`: dependências fixadas.
- `dataset/` permanece compatível com a API anterior; `datasets/` recebe a nova política de partições.
- `math.txt` é regenerado das fontes; não deve ser editado diretamente.
- Novos módulos das fases futuras devem ocupar os caminhos abaixo quando tiverem implementação e testes.
- Contratos compartilhados: IR em `core/`, recibos em `verify/`, cenas em `graphics/` e documentos em `documents/`.
- Serviços, SDKs, protocolo, site e empacotamento existentes continuam nos seus diretórios próprios.

## Fase 0 — Auditoria, recuperação e arquitetura (2026)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `docs/audits/BASELINE_2026_10.md` | Presente: `docs/audits/BASELINE_2026_10.md` |
| `docs/architecture/current-modules.md` | Presente: `docs/architecture/current-modules.md` |
| `docs/adr/0001-product-scope.md` | Presente: `docs/adr/0001-product-scope.md` |
| `docs/adr/0002-canonical-ast.md` | Presente: `docs/adr/0002-canonical-ast.md` |
| `tests/regression/test_public_api.py` | Presente: `tests/regression/test_public_api.py` |
| `.github/workflows/ci.yml` | Presente: `.github/workflows/ci.yml` |

## Fase 1 — Calculadora científica de alto nível (2026–2027)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `core/semantic_ir.py` | Presente: `src/nablamath/core/semantic_ir.py` |
| `core/types.py` | Presente: `src/nablamath/core/types.py` |
| `core/units.py` | Presente: `src/nablamath/core/units.py` |
| `core/precision.py` | Presente: `src/nablamath/core/precision.py` |
| `core/obligations.py` | Presente: `src/nablamath/core/obligations.py` |
| `calc/session.py` | Presente: `src/nablamath/calc/session.py` |
| `calc/notebook.py` | Presente: `src/nablamath/calc/notebook.py` |
| `math/linear_algebra/` | Presente: `src/nablamath/math/linear_algebra` |
| `math/calculus/` | Presente: `src/nablamath/math/calculus` |

## Fase 2 — Nabla Forge: fábrica científica inversa (2027–2028)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `forge/task_spec.py` | Presente: `src/nablamath/forge/task_spec.py` |
| `forge/reverse_builder.py` | Presente: `src/nablamath/forge/reverse_builder.py` |
| `forge/sampling.py` | Presente: `src/nablamath/forge/sampling.py` |
| `forge/difficulty.py` | Presente: `src/nablamath/forge/difficulty.py` |
| `forge/deduplicate.py` | Presente: `src/nablamath/forge/deduplicate.py` |
| `forge/constructors/integration.py` | Presente: `src/nablamath/forge/constructors/integration.py` |
| `forge/constructors/polynomial.py` | Presente: `src/nablamath/forge/constructors/polynomial.py` |
| `forge/constructors/linear_systems.py` | Presente: `src/nablamath/forge/constructors/linear_systems.py` |
| `verify/trace.py` | Presente: `src/nablamath/verify/trace.py` |
| `datasets/splits.py` | Presente: `src/nablamath/datasets/splits.py` |

## Fase 3 — Nabla Prove e Falsifier (2028–2029)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `formal/lean_bridge.py` | Presente: `src/nablamath/formal/lean_bridge.py` |
| `formal/lean_checker.py` | Presente: `src/nablamath/formal/lean_checker.py` |
| `formal/smt_bridge.py` | Presente: `src/nablamath/formal/smt_bridge.py` |
| `formal/translation_review.py` | Presente: `src/nablamath/formal/translation_review.py` |
| `falsifier/search.py` | Presente: `src/nablamath/falsifier/search.py` |
| `falsifier/shrink.py` | Presente: `src/nablamath/falsifier/shrink.py` |
| `verify/certificate.py` | Presente: `src/nablamath/verify/certificate.py` |
| `lean/Nabla/` | Presente: `lean/Nabla` |

## Fase 4 — Geometria, imagens científicas e visualizações (2028–2030)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `graphics/scene_graph.py` | Presente: `src/nablamath/graphics/scene_graph.py` |
| `graphics/geometry_constraints.py` | Presente: `src/nablamath/graphics/geometry_constraints.py` |
| `graphics/coordinate_system.py` | Presente: `src/nablamath/graphics/coordinate_system.py` |
| `graphics/svg_renderer.py` | Presente: `src/nablamath/graphics/svg_renderer.py` |
| `graphics/raster_renderer.py` | Presente: `src/nablamath/graphics/raster_renderer.py` |
| `graphics/layout.py` | Presente: `src/nablamath/graphics/layout.py` |
| `forge/constructors/geometry.py` | Presente: `src/nablamath/forge/constructors/geometry.py` |
| `verify/geometry.py` | Presente: `src/nablamath/verify/geometry.py` |

## Fase 5 — Nabla Studio: LaTeX, Typst, PDF e publicação (2029–2030)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `documents/document_model.py` | Presente: `src/nablamath/documents/document_model.py` |
| `documents/equation_blocks.py` | Presente: `src/nablamath/documents/equation_blocks.py` |
| `documents/citations.py` | Presente: `src/nablamath/documents/citations.py` |
| `documents/figures.py` | Presente: `src/nablamath/documents/figures.py` |
| `documents/latex_exporter.py` | Presente: `src/nablamath/documents/latex_exporter.py` |
| `documents/typst_exporter.py` | Presente: `src/nablamath/documents/typst_exporter.py` |
| `documents/pdf_builder.py` | Presente: `src/nablamath/documents/pdf_builder.py` |
| `documents/html_exporter.py` | Presente: `src/nablamath/documents/html_exporter.py` |
| `templates/research_paper/` | Presente: `templates/research_paper` |

## Fase 6 — Nabla Dataset: dados científicos de treinamento (2029–2031)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `datasets/schema.py` | Presente: `src/nablamath/datasets/schema.py` |
| `datasets/serializer.py` | Presente: `src/nablamath/datasets/serializer.py` |
| `datasets/semantic_fingerprint.py` | Presente: `src/nablamath/datasets/semantic_fingerprint.py` |
| `datasets/split_policy.py` | Presente: `src/nablamath/datasets/split_policy.py` |
| `datasets/curation.py` | Presente: `src/nablamath/datasets/curation.py` |
| `datasets/quality_gate.py` | Presente: `src/nablamath/datasets/quality_gate.py` |
| `datasets/model_card.py` | Presente: `src/nablamath/datasets/model_card.py` |
| `export/parquet.py` | Presente: `src/nablamath/export/parquet.py` |
| `export/jsonl.py` | Presente: `src/nablamath/export/jsonl.py` |
| `export/bundle.py` | Presente: `src/nablamath/export/bundle.py` |
| `export/huggingface.py` | Presente: `src/nablamath/export/huggingface.py` |

## Fase 7 — Nabla Worlds: simulações científicas (2030–2033)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `worlds/model_spec.py` | Presente: `src/nablamath/worlds/model_spec.py` |
| `worlds/ode/` | Presente: `src/nablamath/worlds/ode` |
| `worlds/pde/` | Presente: `src/nablamath/worlds/pde` |
| `worlds/integrators/` | Presente: `src/nablamath/worlds/integrators` |
| `worlds/mesh/` | Presente: `src/nablamath/worlds/mesh` |
| `worlds/conservation.py` | Presente: `src/nablamath/worlds/conservation.py` |
| `worlds/convergence.py` | Presente: `src/nablamath/worlds/convergence.py` |
| `worlds/validation.py` | Presente: `src/nablamath/worlds/validation.py` |
| `worlds/sensitivity.py` | Presente: `src/nablamath/worlds/sensitivity.py` |
| `worlds/animation.py` | Presente: `src/nablamath/worlds/animation.py` |

## Fase 8 — Aprendizado multimodal e agentes científicos (2032–2035)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `agents/tool_registry.py` | Presente: `src/nablamath/agents/tool_registry.py` |
| `agents/planner.py` | Presente: `src/nablamath/agents/planner.py` |
| `agents/proposals.py` | Presente: `src/nablamath/agents/proposals.py` |
| `agents/permissions.py` | Presente: `src/nablamath/agents/permissions.py` |
| `datasets/multimodal.py` | Presente: `src/nablamath/datasets/multimodal.py` |
| `datasets/alignments.py` | Presente: `src/nablamath/datasets/alignments.py` |
| `training/curriculum.py` | Presente: `src/nablamath/training/curriculum.py` |
| `training/evaluation.py` | Presente: `src/nablamath/training/evaluation.py` |
| `training/contamination.py` | Presente: `src/nablamath/training/contamination.py` |
| `training/ablation.py` | Presente: `src/nablamath/training/ablation.py` |

## Fase 9 — Nabla Discovery: investigação de hipóteses (2033–2037)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `discovery/hypothesis.py` | Planejado |
| `discovery/symbolic_regression.py` | Planejado |
| `discovery/experimental_design.py` | Planejado |
| `discovery/theorem_search.py` | Planejado |
| `discovery/novelty_screen.py` | Planejado |
| `knowledge/claim_graph.py` | Planejado |
| `knowledge/literature.py` | Planejado |
| `falsifier/counterexample_miner.py` | Planejado |

## Fase 10 — Nabla Evolution: recursive self-improvement (2037–2042)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `evolution/policy_genome.py` | Planejado |
| `evolution/search.py` | Planejado |
| `evolution/proposal_validator.py` | Planejado |
| `evolution/evaluator.py` | Presente: `src/nablamath/evolution/evaluator.py` |
| `evolution/holdout_manager.py` | Planejado |
| `evolution/statistical_tests.py` | Planejado |
| `evolution/lineage.py` | Planejado |
| `evolution/rollback.py` | Planejado |
| `evolution/release_gate.py` | Planejado |

## Fase 11 — Engenharia e novas disciplinas (2042–2048)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `domains/engineering/` | Planejado |
| `domains/circuits/` | Presente: `src/nablamath/domains/circuits` |
| `domains/materials/` | Planejado |
| `domains/chemistry/` | Planejado |
| `domains/control/` | Planejado |
| `domains/earth/` | Planejado |
| `domains/biology/` | Planejado |
| `worlds/multiphysics/` | Planejado |
| `adapters/instruments/` | Planejado |

## Fase 12 — Conhecimento científico vivo (2048–2056+)

| Caminho previsto | Estado do caminho |
| --- | --- |
| `knowledge/federation.py` | Planejado |
| `knowledge/semantic_reconciliation.py` | Planejado |
| `knowledge/versioned_claims.py` | Presente: `src/nablamath/knowledge/versioned_claims.py` |
| `knowledge/dependency_impact.py` | Planejado |
| `knowledge/peer_review.py` | Planejado |
| `knowledge/provenance_audit.py` | Planejado |
| `discovery/research_program.py` | Planejado |
| `agents/scientific_teams.py` | Planejado |

## Fase 13 — Além de 2056: horizonte aberto

| Caminho previsto | Estado do caminho |
| --- | --- |
| Contratos e compatibilidade de longo prazo | Horizonte aberto |
