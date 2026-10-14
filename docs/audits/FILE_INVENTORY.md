# Inventário completo dos arquivos

Base de comparação: `f57b0465d10586edce0eca9aa815260289044d21`. Inventário de todos os arquivos versionados presentes, incluindo os existentes.

**721 arquivos; 76,846 linhas físicas; 21,074 linhas de código fora do histórico.**

Novos: 96; alterações/movimentações: {'alterado': 31, 'novo': 96, 'movido': 80}. Removidos: 1.

Linhas físicas incluem comentários e espaços. Código Python conta linhas com tokens, incluindo docstrings; outros formatos de código contam linhas não vazias sem comentários de linha inteira (estimativa). “—” significa formato não código/binário. O bundle `math.txt` duplica fontes e não entra no total de código. Histórico movido não representa código novo. Os dois relatórios deste inventário são excluídos para evitar autocontagem. Caches, ambientes virtuais, builds e amostras locais ignoradas não são arquivos do PR.

Reproduzir após adicionar arquivos ao índice:

```sh
python tools/project_inventory.py --base f57b0465d10586edce0eca9aa815260289044d21
```

## Arquivos removidos

- `lean/lakefile.lean`

## Todos os arquivos, por caminho

| Arquivo | Situação | Categoria | Linhas | Código |
| --- | --- | --- | ---: | ---: |
| `.github/ISSUE_TEMPLATE/feature.yml` | existente | infraestrutura/outros | 22 | — |
| `.github/ISSUE_TEMPLATE/science.yml` | existente | infraestrutura/outros | 21 | — |
| `.github/PULL_REQUEST_TEMPLATE.md` | existente | infraestrutura/outros | 11 | — |
| `.github/workflows/accelerator-optional.yml` | existente | infraestrutura/outros | 38 | — |
| `.github/workflows/archive-audit.yml` | existente | infraestrutura/outros | 44 | — |
| `.github/workflows/ci.yml` | existente | infraestrutura/outros | 21 | — |
| `.github/workflows/dataset-publish.yml` | existente | infraestrutura/outros | 36 | — |
| `.github/workflows/interop.yml` | existente | infraestrutura/outros | 15 | — |
| `.github/workflows/lean-core.yml` | alterado | infraestrutura/outros | 32 | — |
| `.github/workflows/lean.yml` | alterado | infraestrutura/outros | 22 | — |
| `.github/workflows/pages.yml` | existente | infraestrutura/outros | 27 | — |
| `.github/workflows/python-core.yml` | existente | infraestrutura/outros | 20 | — |
| `.github/workflows/windows-installer.yml` | existente | infraestrutura/outros | 77 | — |
| `.gitignore` | alterado | infraestrutura/outros | 14 | — |
| `CITATION.cff` | existente | infraestrutura/outros | 7 | — |
| `CODE_OF_CONDUCT.md` | existente | infraestrutura/outros | 3 | — |
| `CONTRIBUTING.md` | existente | infraestrutura/outros | 7 | — |
| `LICENSE` | existente | infraestrutura/outros | 25 | — |
| `README.md` | alterado | infraestrutura/outros | 159 | — |
| `SECURITY.md` | existente | infraestrutura/outros | 5 | — |
| `benchmarks/baselines/README.md` | existente | infraestrutura/outros | 8 | — |
| `benchmarks/tasks/README.md` | existente | infraestrutura/outros | 6 | — |
| `description.md` | existente | infraestrutura/outros | 3362 | — |
| `docs/AI_HANDOFF.md` | existente | documentação | 55 | — |
| `docs/ARCHITECTURE_AND_ACCEPTANCE.md` | existente | documentação | 35 | — |
| `docs/AUTONOMOUS_RESEARCH_LAB.md` | existente | documentação | 48 | — |
| `docs/COMPATIBILITY.md` | existente | documentação | 18 | — |
| `docs/CONTENT_INDEX.md` | existente | documentação | 189 | — |
| `docs/CONVERSATION_FOR_NEXT_AI.md` | existente | documentação | 92 | — |
| `docs/CORE_ALPHA.md` | existente | documentação | 37 | — |
| `docs/DATA_GOVERNANCE.md` | existente | documentação | 5 | — |
| `docs/DECISIONS/README.md` | existente | documentação | 3 | — |
| `docs/DESKTOP.md` | existente | documentação | 22 | — |
| `docs/ESTIMATIVA_EXECUCAO.md` | existente | documentação | 27 | — |
| `docs/GUIA_DA_IMPLEMENTACAO.md` | existente | documentação | 45 | — |
| `docs/IMPLEMENTATION_STATUS.md` | existente | documentação | 29 | — |
| `docs/INCIDENT_RESPONSE.md` | existente | documentação | 20 | — |
| `docs/INTEGRATIONS_ALPHA.md` | existente | documentação | 17 | — |
| `docs/MATHEMATICS_COMPLETION_AUDIT.md` | existente | documentação | 34 | — |
| `docs/MATHEMATICS_COVERAGE.md` | existente | documentação | 253 | — |
| `docs/MIGRATION_STATUS.md` | alterado | documentação | 18 | — |
| `docs/MODEL_GOVERNANCE.md` | existente | documentação | 16 | — |
| `docs/NETWORK_GOVERNANCE.md` | existente | documentação | 20 | — |
| `docs/OPERATIONS.md` | existente | documentação | 7 | — |
| `docs/PHASES_1_2.md` | novo | documentação | 243 | — |
| `docs/PHASES_3_4.md` | novo | documentação | 227 | — |
| `docs/PLANO_MESTRE_2026_2056.md` | existente | documentação | 300 | — |
| `docs/PUBLISHING.md` | existente | documentação | 10 | — |
| `docs/RELEASE_POLICY.md` | existente | documentação | 46 | — |
| `docs/ROADMAP_GLOBAL_RESEARCH.md` | alterado | documentação | 179 | — |
| `docs/SCIENTIFIC_CYCLE.md` | novo | documentação | 152 | — |
| `docs/THREAT_MODEL.md` | existente | documentação | 12 | — |
| `docs/UPLOAD_REMAINING_ARCHIVE.md` | existente | documentação | 37 | — |
| `docs/adr/0001-product-scope.md` | novo | documentação | 16 | — |
| `docs/adr/0002-canonical-ast.md` | novo | documentação | 19 | — |
| `docs/architecture/current-modules.md` | novo | documentação | 23 | — |
| `docs/architecture/vision-phases.md` | novo | documentação | 200 | — |
| `docs/audits/BASELINE_2026_10.md` | novo | documentação | 66 | — |
| `examples/first_problem.py` | existente | infraestrutura/outros | 19 | 14 |
| `examples/orbit_report.py` | existente | infraestrutura/outros | 13 | 9 |
| `lean/Nabla.lean` | novo | Lean | 3 | 3 |
| `lean/Nabla/Algebra.lean` | novo | Lean | 17 | 12 |
| `lean/Nabla/Certificates.lean` | novo | Lean | 16 | 5 |
| `lean/Nabla/Geometry.lean` | novo | Lean | 30 | 22 |
| `lean/NablaMath.lean` | existente | Lean | 2 | 2 |
| `lean/NablaMath/Algebra.lean` | alterado | Lean | 14 | 10 |
| `lean/NablaMath/Algebra/Rules.lean` | alterado | Lean | 41 | 29 |
| `lean/NablaMath/Examples/FirstProblem.lean` | alterado | Lean | 16 | 12 |
| `lean/NablaMath/Prelude.lean` | existente | Lean | 13 | 8 |
| `lean/lake-manifest.json` | novo | Lean | 96 | — |
| `lean/lakefile.toml` | alterado | Lean | 13 | — |
| `lean/lean-toolchain` | existente | Lean | 1 | — |
| `legacy/current_scripts/NablaMath_All_In_One_Professional_FULL.py` | movido de current scripts/NablaMath_All_In_One_Professional_FULL.py | histórico | 656 | 550 |
| `legacy/current_scripts/NablaMath_All_Modules_LaTeX_Professional.py` | movido de current scripts/NablaMath_All_Modules_LaTeX_Professional.py | histórico | 1154 | 1043 |
| `legacy/current_scripts/README.md` | movido de current scripts/README.md | histórico | 5 | — |
| `legacy/current_scripts/nablamath/examples/demo_ml.py` | movido de current scripts/nablamath/examples/demo_ml.py | histórico | 11 | 8 |
| `legacy/current_scripts/nablamath/examples/demo_research.py` | movido de current scripts/nablamath/examples/demo_research.py | histórico | 23 | 17 |
| `legacy/current_scripts/nablamath/examples/demo_v02.py` | movido de current scripts/nablamath/examples/demo_v02.py | histórico | 56 | 46 |
| `legacy/current_scripts/nablamath/nablamath/__init__.py` | movido de current scripts/nablamath/nablamath/__init__.py | histórico | 51 | 50 |
| `legacy/current_scripts/nablamath/nablamath/algebra.py` | movido de current scripts/nablamath/nablamath/algebra.py | histórico | 169 | 145 |
| `legacy/current_scripts/nablamath/nablamath/analysis.py` | movido de current scripts/nablamath/nablamath/analysis.py | histórico | 56 | 49 |
| `legacy/current_scripts/nablamath/nablamath/autodiff.py` | movido de current scripts/nablamath/nablamath/autodiff.py | histórico | 128 | 108 |
| `legacy/current_scripts/nablamath/nablamath/autodiff_tensor.py` | movido de current scripts/nablamath/nablamath/autodiff_tensor.py | histórico | 174 | 148 |
| `legacy/current_scripts/nablamath/nablamath/core.py` | movido de current scripts/nablamath/nablamath/core.py | histórico | 459 | 328 |
| `legacy/current_scripts/nablamath/nablamath/ml.py` | movido de current scripts/nablamath/nablamath/ml.py | histórico | 88 | 69 |
| `legacy/current_scripts/nablamath/nablamath/optimize.py` | movido de current scripts/nablamath/nablamath/optimize.py | histórico | 374 | 336 |
| `legacy/current_scripts/nablamath/nablamath/parser.py` | movido de current scripts/nablamath/nablamath/parser.py | histórico | 58 | 50 |
| `legacy/current_scripts/nablamath/nablamath/plotting.py` | movido de current scripts/nablamath/nablamath/plotting.py | histórico | 239 | 218 |
| `legacy/current_scripts/nablamath/nablamath/recursive.py` | movido de current scripts/nablamath/nablamath/recursive.py | histórico | 100 | 84 |
| `legacy/current_scripts/nablamath/nablamath/tensor.py` | movido de current scripts/nablamath/nablamath/tensor.py | histórico | 103 | 84 |
| `legacy/current_scripts/nablamath/tests/test_basic.py` | movido de current scripts/nablamath/tests/test_basic.py | histórico | 22 | 16 |
| `legacy/current_scripts/nablamath/tests/test_v02.py` | movido de current scripts/nablamath/tests/test_v02.py | histórico | 33 | 27 |
| `legacy/current_scripts/nablamath_all_in_one_professional.py` | movido de current scripts/nablamath_all_in_one_professional.py | histórico | 1267 | 1042 |
| `legacy/current_scripts/nablamath_orbital_professional_single.py` | movido de current scripts/nablamath_orbital_professional_single.py | histórico | 1348 | 1118 |
| `legacy/current_scripts/nablamath_src/nablamath/examples/demo_ml.py` | movido de current scripts/nablamath_src/nablamath/examples/demo_ml.py | histórico | 11 | 8 |
| `legacy/current_scripts/nablamath_src/nablamath/examples/demo_research.py` | movido de current scripts/nablamath_src/nablamath/examples/demo_research.py | histórico | 23 | 17 |
| `legacy/current_scripts/nablamath_src/nablamath/examples/demo_v02.py` | movido de current scripts/nablamath_src/nablamath/examples/demo_v02.py | histórico | 56 | 46 |
| `legacy/current_scripts/nablamath_src/nablamath/nablamath/__init__.py` | movido de current scripts/nablamath_src/nablamath/nablamath/__init__.py | histórico | 51 | 50 |
| `legacy/current_scripts/nablamath_src/nablamath/nablamath/algebra.py` | movido de current scripts/nablamath_src/nablamath/nablamath/algebra.py | histórico | 169 | 145 |
| `legacy/current_scripts/nablamath_src/nablamath/nablamath/analysis.py` | movido de current scripts/nablamath_src/nablamath/nablamath/analysis.py | histórico | 56 | 49 |
| `legacy/current_scripts/nablamath_src/nablamath/nablamath/autodiff.py` | movido de current scripts/nablamath_src/nablamath/nablamath/autodiff.py | histórico | 128 | 108 |
| `legacy/current_scripts/nablamath_src/nablamath/nablamath/autodiff_tensor.py` | movido de current scripts/nablamath_src/nablamath/nablamath/autodiff_tensor.py | histórico | 174 | 148 |
| `legacy/current_scripts/nablamath_src/nablamath/nablamath/core.py` | movido de current scripts/nablamath_src/nablamath/nablamath/core.py | histórico | 459 | 328 |
| `legacy/current_scripts/nablamath_src/nablamath/nablamath/ml.py` | movido de current scripts/nablamath_src/nablamath/nablamath/ml.py | histórico | 88 | 69 |
| `legacy/current_scripts/nablamath_src/nablamath/nablamath/optimize.py` | movido de current scripts/nablamath_src/nablamath/nablamath/optimize.py | histórico | 374 | 336 |
| `legacy/current_scripts/nablamath_src/nablamath/nablamath/parser.py` | movido de current scripts/nablamath_src/nablamath/nablamath/parser.py | histórico | 58 | 50 |
| `legacy/current_scripts/nablamath_src/nablamath/nablamath/plotting.py` | movido de current scripts/nablamath_src/nablamath/nablamath/plotting.py | histórico | 239 | 218 |
| `legacy/current_scripts/nablamath_src/nablamath/nablamath/recursive.py` | movido de current scripts/nablamath_src/nablamath/nablamath/recursive.py | histórico | 100 | 84 |
| `legacy/current_scripts/nablamath_src/nablamath/nablamath/tensor.py` | movido de current scripts/nablamath_src/nablamath/nablamath/tensor.py | histórico | 103 | 84 |
| `legacy/current_scripts/nablamath_src/nablamath/tests/test_basic.py` | movido de current scripts/nablamath_src/nablamath/tests/test_basic.py | histórico | 22 | 16 |
| `legacy/current_scripts/nablamath_v03_work/examples/demo_ml.py` | movido de current scripts/nablamath_v03_work/examples/demo_ml.py | histórico | 11 | 8 |
| `legacy/current_scripts/nablamath_v03_work/examples/demo_research.py` | movido de current scripts/nablamath_v03_work/examples/demo_research.py | histórico | 23 | 17 |
| `legacy/current_scripts/nablamath_v03_work/examples/demo_v02.py` | movido de current scripts/nablamath_v03_work/examples/demo_v02.py | histórico | 56 | 46 |
| `legacy/current_scripts/nablamath_v03_work/examples/demo_v03_pdf.py` | movido de current scripts/nablamath_v03_work/examples/demo_v03_pdf.py | histórico | 21 | 20 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/__init__.py` | movido de current scripts/nablamath_v03_work/nablamath/__init__.py | histórico | 72 | 63 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/algebra.py` | movido de current scripts/nablamath_v03_work/nablamath/algebra.py | histórico | 169 | 145 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/autodiff_tensor.py` | movido de current scripts/nablamath_v03_work/nablamath/autodiff_tensor.py | histórico | 174 | 148 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/core.py` | movido de current scripts/nablamath_v03_work/nablamath/core.py | histórico | 459 | 328 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/latex_report.py` | movido de current scripts/nablamath_v03_work/nablamath/latex_report.py | histórico | 206 | 181 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/ml.py` | movido de current scripts/nablamath_v03_work/nablamath/ml.py | histórico | 88 | 69 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/optimize.py` | movido de current scripts/nablamath_v03_work/nablamath/optimize.py | histórico | 374 | 336 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/parser.py` | movido de current scripts/nablamath_v03_work/nablamath/parser.py | histórico | 58 | 50 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/plotting.py` | movido de current scripts/nablamath_v03_work/nablamath/plotting.py | histórico | 239 | 218 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/recursive.py` | movido de current scripts/nablamath_v03_work/nablamath/recursive.py | histórico | 100 | 84 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/reports.py` | movido de current scripts/nablamath_v03_work/nablamath/reports.py | histórico | 317 | 275 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/tensor.py` | movido de current scripts/nablamath_v03_work/nablamath/tensor.py | histórico | 103 | 84 |
| `legacy/current_scripts/nablamath_v03_work/nablamath/viz_enterprise.py` | movido de current scripts/nablamath_v03_work/nablamath/viz_enterprise.py | histórico | 383 | 334 |
| `legacy/current_scripts/nablamath_v03_work/tests/test_v02.py` | movido de current scripts/nablamath_v03_work/tests/test_v02.py | histórico | 33 | 27 |
| `legacy/current_scripts/nablamath_v03_work/tests/test_v03.py` | movido de current scripts/nablamath_v03_work/tests/test_v03.py | histórico | 21 | 17 |
| `legacy/current_scripts/nablamath_v04_work/examples/demo_orbital_v06_professional.py` | movido de current scripts/nablamath_v04_work/examples/demo_orbital_v06_professional.py | histórico | 152 | 143 |
| `legacy/current_scripts/nablamath_v04_work/nablamath/__init__.py` | movido de current scripts/nablamath_v04_work/nablamath/__init__.py | histórico | 98 | 84 |
| `legacy/current_scripts/nablamath_v04_work/nablamath/orbital.py` | movido de current scripts/nablamath_v04_work/nablamath/orbital.py | histórico | 2256 | 2039 |
| `legacy/current_scripts/nablarender_single_test/blender_export/rocket_blender_cycles_export.py` | movido de current scripts/nablarender_single_test/blender_export/rocket_blender_cycles_export.py | histórico | 36 | 35 |
| `legacy/current_scripts/nablarender_v07/nablarender/__init__.py` | movido de current scripts/nablarender_v07/nablarender/__init__.py | histórico | 10 | 10 |
| `legacy/current_scripts/nablarender_v07/nablarender/api.py` | movido de current scripts/nablarender_v07/nablarender/api.py | histórico | 26 | 24 |
| `legacy/current_scripts/nablarender_v07/nablarender/blender/export_blender.py` | movido de current scripts/nablarender_v07/nablarender/blender/export_blender.py | histórico | 34 | 34 |
| `legacy/current_scripts/nablarender_v07/nablarender/core/bvh.py` | movido de current scripts/nablarender_v07/nablarender/core/bvh.py | histórico | 44 | 44 |
| `legacy/current_scripts/nablarender_v07/nablarender/core/math3d.py` | movido de current scripts/nablarender_v07/nablarender/core/math3d.py | histórico | 30 | 29 |
| `legacy/current_scripts/nablarender_v07/nablarender/core/mesh.py` | movido de current scripts/nablarender_v07/nablarender/core/mesh.py | histórico | 26 | 26 |
| `legacy/current_scripts/nablarender_v07/nablarender/core/meshlet.py` | movido de current scripts/nablarender_v07/nablarender/core/meshlet.py | histórico | 23 | 23 |
| `legacy/current_scripts/nablarender_v07/nablarender/examples/demo_v07_full.py` | movido de current scripts/nablarender_v07/nablarender/examples/demo_v07_full.py | histórico | 8 | 8 |
| `legacy/current_scripts/nablarender_v07/nablarender/generated_demo_v07/blender/rocket_blender_cycles_export.py` | movido de current scripts/nablarender_v07/nablarender/generated_demo_v07/blender/rocket_blender_cycles_export.py | histórico | 41 | 33 |
| `legacy/current_scripts/nablarender_v07/nablarender/native/camera.py` | movido de current scripts/nablarender_v07/nablarender/native/camera.py | histórico | 9 | 9 |
| `legacy/current_scripts/nablarender_v07/nablarender/native/pathtracer.py` | movido de current scripts/nablarender_v07/nablarender/native/pathtracer.py | histórico | 37 | 36 |
| `legacy/current_scripts/nablarender_v07/nablarender/native/rasterizer.py` | movido de current scripts/nablarender_v07/nablarender/native/rasterizer.py | histórico | 27 | 26 |
| `legacy/current_scripts/nablarender_v07/nablarender/native/renderer.py` | movido de current scripts/nablarender_v07/nablarender/native/renderer.py | histórico | 33 | 33 |
| `legacy/current_scripts/nablarender_v07/nablarender/native/scene.py` | movido de current scripts/nablarender_v07/nablarender/native/scene.py | histórico | 11 | 11 |
| `legacy/current_scripts/nablarender_v07/nablarender/procedural/rocket_factory.py` | movido de current scripts/nablarender_v07/nablarender/procedural/rocket_factory.py | histórico | 39 | 35 |
| `legacy/current_scripts/nablarender_v07/nablarender/report/__init__.py` | movido de current scripts/nablarender_v07/nablarender/report/__init__.py | histórico | 2 | 2 |
| `legacy/current_scripts/nablarender_v07/nablarender/report/pro_report.py` | movido de current scripts/nablarender_v07/nablarender/report/pro_report.py | histórico | 64 | 60 |
| `legacy/current_scripts/nablarender_v07/nablarender/web/web_renderer.py` | movido de current scripts/nablarender_v07/nablarender/web/web_renderer.py | histórico | 14 | 14 |
| `legacy/current_scripts/nablarender_v07_single_file_report.py` | movido de current scripts/nablarender_v07_single_file_report.py | histórico | 933 | 764 |
| `legacy/latex/NablaMath_Calculator_Professional_Report.tex` | existente | histórico | 948 | — |
| `legacy/latex/NablaMath_Orbital_Professional_Report.tex` | existente | histórico | 611 | — |
| `legacy/latex/NablaMath_Relativity_Professional_Report.tex` | existente | histórico | 626 | — |
| `legacy/latex/nablamath_v03_extreme_latex_report.tex` | existente | histórico | 325 | — |
| `legacy/nablamath_v03_work/examples/demo_v03_pdf.py` | existente | histórico | 21 | 20 |
| `legacy/nablamath_v03_work/nablamath/__init__.py` | existente | histórico | 72 | 63 |
| `legacy/nablamath_v03_work/nablamath/algebra.py` | existente | histórico | 169 | 145 |
| `legacy/nablamath_v03_work/nablamath/autodiff_tensor.py` | existente | histórico | 174 | 148 |
| `legacy/nablamath_v03_work/nablamath/core.py` | existente | histórico | 459 | 328 |
| `legacy/nablamath_v03_work/nablamath/latex_report.py` | existente | histórico | 206 | 181 |
| `legacy/nablamath_v03_work/nablamath/ml.py` | existente | histórico | 88 | 69 |
| `legacy/nablamath_v03_work/nablamath/optimize.py` | existente | histórico | 374 | 336 |
| `legacy/nablamath_v03_work/nablamath/parser.py` | existente | histórico | 58 | 50 |
| `legacy/nablamath_v03_work/nablamath/plotting.py` | existente | histórico | 239 | 218 |
| `legacy/nablamath_v03_work/nablamath/recursive.py` | existente | histórico | 100 | 84 |
| `legacy/nablamath_v03_work/nablamath/reports.py` | existente | histórico | 317 | 275 |
| `legacy/nablamath_v03_work/nablamath/tensor.py` | existente | histórico | 103 | 84 |
| `legacy/nablamath_v03_work/nablamath/viz_enterprise.py` | existente | histórico | 383 | 334 |
| `legacy/nablamath_v03_work/tests/test_v02.py` | existente | histórico | 33 | 27 |
| `legacy/nablamath_v03_work/tests/test_v03.py` | existente | histórico | 21 | 17 |
| `legacy/nablamath_v04_work/examples/demo_orbital_v06_professional.py` | existente | histórico | 152 | 143 |
| `legacy/nablamath_v04_work/nablamath/orbital.py` | existente | histórico | 2256 | 2039 |
| `legacy/nablarender_v07/nablarender/__init__.py` | existente | histórico | 10 | 10 |
| `legacy/nablarender_v07/nablarender/api.py` | existente | histórico | 26 | 24 |
| `legacy/nablarender_v07/nablarender/blender/export_blender.py` | existente | histórico | 34 | 34 |
| `legacy/nablarender_v07/nablarender/core/bvh.py` | existente | histórico | 44 | 44 |
| `legacy/nablarender_v07/nablarender/core/math3d.py` | existente | histórico | 30 | 29 |
| `legacy/nablarender_v07/nablarender/core/mesh.py` | existente | histórico | 26 | 26 |
| `legacy/nablarender_v07/nablarender/core/meshlet.py` | existente | histórico | 23 | 23 |
| `legacy/nablarender_v07/nablarender/examples/demo_v07_full.py` | existente | histórico | 8 | 8 |
| `legacy/nablarender_v07/nablarender/native/camera.py` | existente | histórico | 9 | 9 |
| `legacy/nablarender_v07/nablarender/native/pathtracer.py` | existente | histórico | 37 | 36 |
| `legacy/nablarender_v07/nablarender/native/rasterizer.py` | existente | histórico | 27 | 26 |
| `legacy/nablarender_v07/nablarender/native/renderer.py` | existente | histórico | 33 | 33 |
| `legacy/nablarender_v07/nablarender/native/scene.py` | existente | histórico | 11 | 11 |
| `legacy/nablarender_v07/nablarender/procedural/rocket_factory.py` | existente | histórico | 39 | 35 |
| `legacy/nablarender_v07/nablarender/report/__init__.py` | existente | histórico | 2 | 2 |
| `legacy/nablarender_v07/nablarender/report/pro_report.py` | existente | histórico | 64 | 60 |
| `legacy/nablarender_v07/nablarender/web/web_renderer.py` | existente | histórico | 14 | 14 |
| `legacy/single_file/NablaMath_All_In_One_Professional_FULL.py` | existente | histórico | 656 | 550 |
| `legacy/single_file/NablaMath_All_Modules_LaTeX_Professional.py` | existente | histórico | 1154 | 1043 |
| `legacy/single_file/nablamath_all_in_one_professional.py` | existente | histórico | 1267 | 1042 |
| `legacy/single_file/nablamath_orbital_professional_single.py` | existente | histórico | 1348 | 1118 |
| `legacy/single_file/nablarender_v07_single_file_report.py` | existente | histórico | 933 | 764 |
| `math.txt` | alterado | bundle gerado | 15096 | — |
| `packaging/windows/nablamath.iss` | existente | infraestrutura/outros | 24 | — |
| `protocol/__init__.py` | existente | infraestrutura/outros | 1 | 1 |
| `protocol/canonical/encoding.md` | existente | infraestrutura/outros | 6 | — |
| `protocol/canonical/numbers.md` | existente | infraestrutura/outros | 6 | — |
| `protocol/fixtures/README.md` | existente | infraestrutura/outros | 5 | — |
| `protocol/fixtures/golden/problem.json` | existente | infraestrutura/outros | 1 | — |
| `protocol/fixtures/golden/problem.sha256` | existente | infraestrutura/outros | 1 | — |
| `protocol/schema/README.md` | existente | infraestrutura/outros | 7 | — |
| `protocol/schema/nabla-model-v1.json` | existente | infraestrutura/outros | 16 | — |
| `protocol/schema/nabla-object-v1.json` | existente | infraestrutura/outros | 21 | — |
| `protocol/schema/nabla-receipt-v1.json` | existente | infraestrutura/outros | 17 | — |
| `protocol/schema/nabla-task-v1.json` | existente | infraestrutura/outros | 24 | — |
| `pyproject.toml` | alterado | infraestrutura/outros | 34 | — |
| `scripts/import_archive.py` | existente | infraestrutura/outros | 113 | 105 |
| `scripts/setup_formal.sh` | novo | infraestrutura/outros | 31 | 28 |
| `sdk/c/README.md` | existente | infraestrutura/outros | 4 | — |
| `sdk/c/nabla_fraction.c` | existente | infraestrutura/outros | 42 | — |
| `sdk/c/nabla_fraction.h` | existente | infraestrutura/outros | 15 | — |
| `sdk/cpp/README.md` | existente | infraestrutura/outros | 4 | — |
| `sdk/cpp/nabla_fraction.hpp` | existente | infraestrutura/outros | 12 | — |
| `sdk/rust/Cargo.toml` | existente | infraestrutura/outros | 7 | — |
| `sdk/rust/README.md` | existente | infraestrutura/outros | 4 | — |
| `sdk/rust/src/lib.rs` | existente | infraestrutura/outros | 49 | — |
| `services/__init__.py` | existente | infraestrutura/outros | 1 | 1 |
| `services/coordinator/__init__.py` | existente | infraestrutura/outros | 3 | 2 |
| `services/coordinator/app.py` | existente | infraestrutura/outros | 49 | 39 |
| `services/coordinator/auth.py` | existente | infraestrutura/outros | 28 | 18 |
| `services/coordinator/db/README.md` | existente | infraestrutura/outros | 6 | — |
| `services/coordinator/events.py` | existente | infraestrutura/outros | 45 | 36 |
| `services/coordinator/metrics.py` | existente | infraestrutura/outros | 18 | 13 |
| `services/coordinator/review.py` | existente | infraestrutura/outros | 22 | 17 |
| `services/coordinator/scheduler.py` | existente | infraestrutura/outros | 22 | 14 |
| `services/coordinator/snapshots.py` | existente | infraestrutura/outros | 27 | 20 |
| `services/publisher/__init__.py` | existente | infraestrutura/outros | 3 | 2 |
| `services/publisher/cli.py` | existente | infraestrutura/outros | 25 | 20 |
| `services/publisher/huggingface.py` | existente | infraestrutura/outros | 5 | 3 |
| `services/publisher/manifest.py` | existente | infraestrutura/outros | 5 | 3 |
| `services/worker/__init__.py` | existente | infraestrutura/outros | 3 | 2 |
| `services/worker/agent.py` | existente | infraestrutura/outros | 17 | 13 |
| `services/worker/checkpoint.py` | existente | infraestrutura/outros | 20 | 15 |
| `setup.cmd` | existente | infraestrutura/outros | 3 | 3 |
| `setup.ps1` | existente | infraestrutura/outros | 21 | 21 |
| `setup.sh` | existente | infraestrutura/outros | 6 | 5 |
| `src/nablamath/__init__.py` | existente | fonte | 9 | 7 |
| `src/nablamath/adapters/__init__.py` | existente | fonte | 3 | 2 |
| `src/nablamath/adapters/blender.py` | existente | fonte | 18 | 12 |
| `src/nablamath/adapters/numpy.py` | existente | fonte | 25 | 17 |
| `src/nablamath/adapters/registry.py` | existente | fonte | 37 | 25 |
| `src/nablamath/adapters/scipy.py` | existente | fonte | 35 | 27 |
| `src/nablamath/adapters/sympy.py` | existente | fonte | 45 | 34 |
| `src/nablamath/agents/__init__.py` | existente | fonte | 4 | 3 |
| `src/nablamath/agents/budget.py` | existente | fonte | 13 | 9 |
| `src/nablamath/agents/protocol.py` | existente | fonte | 21 | 15 |
| `src/nablamath/agents/sandbox.py` | existente | fonte | 5 | 3 |
| `src/nablamath/agents/selector.py` | existente | fonte | 31 | 22 |
| `src/nablamath/agents/trajectory.py` | existente | fonte | 23 | 18 |
| `src/nablamath/autodiff/__init__.py` | existente | fonte | 8 | 7 |
| `src/nablamath/autodiff/api.py` | existente | fonte | 240 | 213 |
| `src/nablamath/autodiff/tensor.py` | existente | fonte | 283 | 265 |
| `src/nablamath/calc/__init__.py` | novo | fonte | 5 | 4 |
| `src/nablamath/calc/notebook.py` | novo | fonte | 62 | 54 |
| `src/nablamath/calc/session.py` | novo | fonte | 226 | 210 |
| `src/nablamath/cli.py` | alterado | fonte | 368 | 359 |
| `src/nablamath/compatibility.json` | existente | fonte | 21 | — |
| `src/nablamath/compatibility.py` | existente | fonte | 95 | 80 |
| `src/nablamath/compiler/__init__.py` | existente | fonte | 15 | 14 |
| `src/nablamath/compiler/backends.py` | existente | fonte | 170 | 140 |
| `src/nablamath/compiler/distributed.py` | existente | fonte | 254 | 226 |
| `src/nablamath/compiler/ir.py` | existente | fonte | 122 | 102 |
| `src/nablamath/config.py` | existente | fonte | 21 | 15 |
| `src/nablamath/coordination/__init__.py` | existente | fonte | 3 | 2 |
| `src/nablamath/coordination/local.py` | existente | fonte | 86 | 76 |
| `src/nablamath/coordination/merkle.py` | existente | fonte | 20 | 17 |
| `src/nablamath/core/__init__.py` | novo | fonte | 8 | 7 |
| `src/nablamath/core/obligations.py` | novo | fonte | 56 | 47 |
| `src/nablamath/core/precision.py` | novo | fonte | 57 | 46 |
| `src/nablamath/core/semantic_ir.py` | novo | fonte | 177 | 149 |
| `src/nablamath/core/types.py` | novo | fonte | 28 | 22 |
| `src/nablamath/core/units.py` | novo | fonte | 106 | 85 |
| `src/nablamath/curation.py` | existente | fonte | 52 | 46 |
| `src/nablamath/dataset/__init__.py` | existente | fonte | 9 | 8 |
| `src/nablamath/dataset/alignments.py` | novo | fonte | 24 | 21 |
| `src/nablamath/dataset/cards.py` | existente | fonte | 26 | 23 |
| `src/nablamath/dataset/deduplicate.py` | existente | fonte | 11 | 7 |
| `src/nablamath/dataset/export.py` | existente | fonte | 35 | 26 |
| `src/nablamath/dataset/licenses.py` | existente | fonte | 25 | 18 |
| `src/nablamath/dataset/quality.py` | existente | fonte | 10 | 7 |
| `src/nablamath/dataset/schema.py` | existente | fonte | 34 | 25 |
| `src/nablamath/dataset/scientific.py` | novo | fonte | 81 | 69 |
| `src/nablamath/dataset/splits.py` | existente | fonte | 17 | 9 |
| `src/nablamath/datasets/__init__.py` | novo | fonte | 4 | 3 |
| `src/nablamath/datasets/splits.py` | novo | fonte | 53 | 43 |
| `src/nablamath/desktop/__init__.py` | existente | fonte | 1 | 1 |
| `src/nablamath/desktop/app.py` | existente | fonte | 243 | 208 |
| `src/nablamath/desktop/index.html` | existente | fonte | 26 | 25 |
| `src/nablamath/desktop/launcher.py` | existente | fonte | 7 | 4 |
| `src/nablamath/documents/__init__.py` | novo | fonte | 5 | 4 |
| `src/nablamath/documents/document_model.py` | novo | fonte | 43 | 33 |
| `src/nablamath/documents/exporters.py` | novo | fonte | 57 | 46 |
| `src/nablamath/documents/pdf_builder.py` | novo | fonte | 46 | 43 |
| `src/nablamath/domains/__init__.py` | novo | fonte | 1 | 1 |
| `src/nablamath/domains/circuits/__init__.py` | novo | fonte | 4 | 3 |
| `src/nablamath/domains/circuits/resistive.py` | novo | fonte | 79 | 69 |
| `src/nablamath/entity.py` | existente | fonte | 93 | 75 |
| `src/nablamath/errors.py` | existente | fonte | 8 | 6 |
| `src/nablamath/evaluation/__init__.py` | existente | fonte | 3 | 3 |
| `src/nablamath/evaluation/contamination.py` | existente | fonte | 46 | 34 |
| `src/nablamath/evaluation/sealed.py` | existente | fonte | 23 | 16 |
| `src/nablamath/evolution/__init__.py` | novo | fonte | 4 | 3 |
| `src/nablamath/evolution/evaluator.py` | novo | fonte | 82 | 66 |
| `src/nablamath/expression.py` | existente | fonte | 143 | 115 |
| `src/nablamath/falsifier/__init__.py` | novo | fonte | 4 | 3 |
| `src/nablamath/falsifier/search.py` | novo | fonte | 102 | 89 |
| `src/nablamath/falsifier/shrink.py` | novo | fonte | 66 | 59 |
| `src/nablamath/forge/__init__.py` | novo | fonte | 5 | 4 |
| `src/nablamath/forge/constructors/__init__.py` | novo | fonte | 1 | 1 |
| `src/nablamath/forge/constructors/counterexamples.py` | novo | fonte | 14 | 12 |
| `src/nablamath/forge/constructors/geometry.py` | novo | fonte | 49 | 45 |
| `src/nablamath/forge/constructors/identities.py` | novo | fonte | 15 | 13 |
| `src/nablamath/forge/constructors/integration.py` | novo | fonte | 12 | 10 |
| `src/nablamath/forge/constructors/linear_systems.py` | novo | fonte | 16 | 14 |
| `src/nablamath/forge/constructors/markov.py` | novo | fonte | 13 | 11 |
| `src/nablamath/forge/constructors/optimization.py` | novo | fonte | 14 | 12 |
| `src/nablamath/forge/constructors/polynomial.py` | novo | fonte | 17 | 15 |
| `src/nablamath/forge/constructors/spectrum.py` | novo | fonte | 15 | 13 |
| `src/nablamath/forge/deduplicate.py` | novo | fonte | 48 | 42 |
| `src/nablamath/forge/difficulty.py` | novo | fonte | 112 | 100 |
| `src/nablamath/forge/factory.py` | novo | fonte | 145 | 140 |
| `src/nablamath/forge/pipeline.py` | novo | fonte | 162 | 157 |
| `src/nablamath/forge/reverse_builder.py` | novo | fonte | 37 | 30 |
| `src/nablamath/forge/sampling.py` | novo | fonte | 23 | 19 |
| `src/nablamath/forge/solvers.py` | novo | fonte | 115 | 107 |
| `src/nablamath/forge/task_spec.py` | novo | fonte | 119 | 106 |
| `src/nablamath/formal/__init__.py` | alterado | fonte | 21 | 18 |
| `src/nablamath/formal/check.py` | alterado | fonte | 50 | 45 |
| `src/nablamath/formal/lean_bridge.py` | novo | fonte | 42 | 35 |
| `src/nablamath/formal/lean_checker.py` | novo | fonte | 111 | 97 |
| `src/nablamath/formal/obligations.py` | existente | fonte | 26 | 18 |
| `src/nablamath/formal/review.py` | existente | fonte | 20 | 14 |
| `src/nablamath/formal/search.py` | existente | fonte | 118 | 95 |
| `src/nablamath/formal/smt_bridge.py` | novo | fonte | 72 | 70 |
| `src/nablamath/formal/statement.py` | novo | fonte | 88 | 71 |
| `src/nablamath/formal/translate.py` | alterado | fonte | 76 | 66 |
| `src/nablamath/formal/translation_review.py` | novo | fonte | 29 | 24 |
| `src/nablamath/formal_ci.py` | existente | fonte | 26 | 19 |
| `src/nablamath/gpu/__init__.py` | existente | fonte | 17 | 15 |
| `src/nablamath/gpu/batch_mcts_kernel.py` | existente | fonte | 129 | 113 |
| `src/nablamath/gpu/cuda_f4_reduction.py` | existente | fonte | 115 | 99 |
| `src/nablamath/gpu/neural_guide.py` | existente | fonte | 69 | 57 |
| `src/nablamath/gpu/tensor_egraph.py` | existente | fonte | 100 | 85 |
| `src/nablamath/gpu/vram_buffer_manager.py` | existente | fonte | 132 | 105 |
| `src/nablamath/graphics/__init__.py` | novo | fonte | 10 | 8 |
| `src/nablamath/graphics/artifacts.py` | novo | fonte | 79 | 73 |
| `src/nablamath/graphics/coordinate_system.py` | novo | fonte | 61 | 51 |
| `src/nablamath/graphics/geometry_constraints.py` | novo | fonte | 31 | 26 |
| `src/nablamath/graphics/layout.py` | novo | fonte | 90 | 84 |
| `src/nablamath/graphics/raster_renderer.py` | novo | fonte | 53 | 46 |
| `src/nablamath/graphics/rendering.py` | novo | fonte | 41 | 37 |
| `src/nablamath/graphics/sampling.py` | novo | fonte | 108 | 100 |
| `src/nablamath/graphics/scene_graph.py` | novo | fonte | 177 | 143 |
| `src/nablamath/graphics/svg_renderer.py` | novo | fonte | 25 | 22 |
| `src/nablamath/knowledge/__init__.py` | existente | fonte | 5 | 3 |
| `src/nablamath/knowledge/graph.py` | existente | fonte | 76 | 63 |
| `src/nablamath/knowledge/versioned_claims.py` | novo | fonte | 97 | 82 |
| `src/nablamath/math/__init__.py` | existente | fonte | 1 | 1 |
| `src/nablamath/math/algebra/__init__.py` | alterado | fonte | 13 | 12 |
| `src/nablamath/math/algebra/extensions.py` | existente | fonte | 187 | 147 |
| `src/nablamath/math/algebra/f4.py` | existente | fonte | 233 | 205 |
| `src/nablamath/math/algebra/f5.py` | existente | fonte | 181 | 148 |
| `src/nablamath/math/algebra/fields.py` | existente | fonte | 38 | 26 |
| `src/nablamath/math/algebra/groebner.py` | existente | fonte | 326 | 278 |
| `src/nablamath/math/algebra/groups.py` | existente | fonte | 60 | 47 |
| `src/nablamath/math/algebra/rings.py` | existente | fonte | 62 | 49 |
| `src/nablamath/math/analysis/__init__.py` | existente | fonte | 6 | 6 |
| `src/nablamath/math/analysis/complex.py` | existente | fonte | 27 | 18 |
| `src/nablamath/math/analysis/laurent.py` | existente | fonte | 67 | 53 |
| `src/nablamath/math/analysis/numerical.py` | existente | fonte | 117 | 98 |
| `src/nablamath/math/analysis/real.py` | existente | fonte | 37 | 29 |
| `src/nablamath/math/analysis/sequences.py` | existente | fonte | 41 | 32 |
| `src/nablamath/math/arithmetic/__init__.py` | existente | fonte | 2 | 2 |
| `src/nablamath/math/arithmetic/continued_fractions.py` | existente | fonte | 39 | 30 |
| `src/nablamath/math/calculus/__init__.py` | novo | fonte | 4 | 3 |
| `src/nablamath/math/calculus/polynomial.py` | novo | fonte | 28 | 18 |
| `src/nablamath/math/category_theory/__init__.py` | existente | fonte | 5 | 5 |
| `src/nablamath/math/category_theory/categories.py` | existente | fonte | 70 | 57 |
| `src/nablamath/math/category_theory/functors.py` | existente | fonte | 54 | 44 |
| `src/nablamath/math/category_theory/limits.py` | existente | fonte | 27 | 16 |
| `src/nablamath/math/category_theory/products.py` | existente | fonte | 37 | 29 |
| `src/nablamath/math/combinatorics/__init__.py` | existente | fonte | 2 | 2 |
| `src/nablamath/math/combinatorics/enumerative.py` | existente | fonte | 35 | 26 |
| `src/nablamath/math/control/__init__.py` | existente | fonte | 2 | 2 |
| `src/nablamath/math/control/linear.py` | existente | fonte | 23 | 21 |
| `src/nablamath/math/cryptography/__init__.py` | existente | fonte | 2 | 2 |
| `src/nablamath/math/cryptography/classical.py` | existente | fonte | 31 | 27 |
| `src/nablamath/math/dynamical_systems/__init__.py` | existente | fonte | 2 | 2 |
| `src/nablamath/math/dynamical_systems/discrete.py` | existente | fonte | 35 | 25 |
| `src/nablamath/math/equations/__init__.py` | existente | fonte | 2 | 2 |
| `src/nablamath/math/equations/ode.py` | existente | fonte | 37 | 31 |
| `src/nablamath/math/formal_languages/__init__.py` | existente | fonte | 2 | 2 |
| `src/nablamath/math/formal_languages/automata.py` | existente | fonte | 42 | 33 |
| `src/nablamath/math/game_theory/__init__.py` | existente | fonte | 2 | 2 |
| `src/nablamath/math/game_theory/normal_form.py` | existente | fonte | 41 | 32 |
| `src/nablamath/math/geometry/__init__.py` | alterado | fonte | 6 | 6 |
| `src/nablamath/math/geometry/conics.py` | novo | fonte | 52 | 42 |
| `src/nablamath/math/geometry/convex.py` | existente | fonte | 26 | 22 |
| `src/nablamath/math/geometry/differential.py` | existente | fonte | 95 | 76 |
| `src/nablamath/math/geometry/euclidean.py` | existente | fonte | 30 | 19 |
| `src/nablamath/math/geometry/riemannian.py` | existente | fonte | 122 | 106 |
| `src/nablamath/math/graph_theory/__init__.py` | existente | fonte | 6 | 6 |
| `src/nablamath/math/graph_theory/algorithms.py` | existente | fonte | 38 | 31 |
| `src/nablamath/math/graph_theory/directed.py` | existente | fonte | 128 | 110 |
| `src/nablamath/math/graph_theory/flows.py` | existente | fonte | 40 | 35 |
| `src/nablamath/math/graph_theory/structural.py` | existente | fonte | 47 | 38 |
| `src/nablamath/math/graph_theory/weighted.py` | existente | fonte | 36 | 29 |
| `src/nablamath/math/information/__init__.py` | existente | fonte | 3 | 3 |
| `src/nablamath/math/information/coding.py` | existente | fonte | 37 | 25 |
| `src/nablamath/math/information/entropy.py` | existente | fonte | 90 | 72 |
| `src/nablamath/math/linear_algebra/__init__.py` | alterado | fonte | 5 | 4 |
| `src/nablamath/math/linear_algebra/matrices.py` | existente | fonte | 78 | 64 |
| `src/nablamath/math/linear_algebra/solvers.py` | novo | fonte | 123 | 106 |
| `src/nablamath/math/logic/__init__.py` | existente | fonte | 20 | 19 |
| `src/nablamath/math/logic/cdcl.py` | existente | fonte | 130 | 113 |
| `src/nablamath/math/logic/first_order.py` | existente | fonte | 110 | 89 |
| `src/nablamath/math/logic/propositional.py` | existente | fonte | 71 | 51 |
| `src/nablamath/math/logic/resolution.py` | existente | fonte | 78 | 65 |
| `src/nablamath/math/logic/sat.py` | existente | fonte | 118 | 102 |
| `src/nablamath/math/logic/smt_linear.py` | existente | fonte | 82 | 66 |
| `src/nablamath/math/logic/smt_theories.py` | existente | fonte | 194 | 155 |
| `src/nablamath/math/logic/superposition.py` | existente | fonte | 280 | 226 |
| `src/nablamath/math/number_theory/__init__.py` | existente | fonte | 5 | 5 |
| `src/nablamath/math/number_theory/congruences.py` | existente | fonte | 32 | 25 |
| `src/nablamath/math/number_theory/elementary.py` | existente | fonte | 43 | 32 |
| `src/nablamath/math/number_theory/elliptic_curves.py` | existente | fonte | 73 | 61 |
| `src/nablamath/math/number_theory/primality.py` | existente | fonte | 125 | 107 |
| `src/nablamath/math/operations_research/__init__.py` | existente | fonte | 3 | 3 |
| `src/nablamath/math/operations_research/queues.py` | existente | fonte | 24 | 22 |
| `src/nablamath/math/operations_research/scheduling.py` | existente | fonte | 98 | 75 |
| `src/nablamath/math/optimization/__init__.py` | alterado | fonte | 3 | 3 |
| `src/nablamath/math/optimization/linear.py` | existente | fonte | 41 | 34 |
| `src/nablamath/math/optimization/quadratic.py` | novo | fonte | 46 | 42 |
| `src/nablamath/math/polynomials/__init__.py` | existente | fonte | 3 | 3 |
| `src/nablamath/math/polynomials/factorization.py` | novo | fonte | 54 | 50 |
| `src/nablamath/math/polynomials/interpolation.py` | existente | fonte | 87 | 70 |
| `src/nablamath/math/polynomials/univariate.py` | existente | fonte | 70 | 53 |
| `src/nablamath/math/probability/__init__.py` | existente | fonte | 7 | 7 |
| `src/nablamath/math/probability/continuous.py` | existente | fonte | 88 | 65 |
| `src/nablamath/math/probability/finite.py` | existente | fonte | 36 | 25 |
| `src/nablamath/math/probability/ito.py` | existente | fonte | 46 | 36 |
| `src/nablamath/math/probability/joint.py` | existente | fonte | 33 | 20 |
| `src/nablamath/math/probability/markov.py` | existente | fonte | 30 | 28 |
| `src/nablamath/math/probability/stochastic.py` | existente | fonte | 44 | 35 |
| `src/nablamath/math/set_theory/__init__.py` | existente | fonte | 2 | 2 |
| `src/nablamath/math/set_theory/finite.py` | existente | fonte | 48 | 34 |
| `src/nablamath/math/statistics/__init__.py` | alterado | fonte | 6 | 6 |
| `src/nablamath/math/statistics/bayesian.py` | existente | fonte | 19 | 16 |
| `src/nablamath/math/statistics/descriptive.py` | existente | fonte | 33 | 22 |
| `src/nablamath/math/statistics/inference.py` | novo | fonte | 35 | 29 |
| `src/nablamath/math/statistics/regression.py` | existente | fonte | 33 | 24 |
| `src/nablamath/math/statistics/time_series.py` | existente | fonte | 96 | 78 |
| `src/nablamath/math/topology/__init__.py` | existente | fonte | 4 | 4 |
| `src/nablamath/math/topology/general.py` | existente | fonte | 27 | 21 |
| `src/nablamath/math/topology/homology.py` | existente | fonte | 112 | 94 |
| `src/nablamath/math/topology/operations.py` | existente | fonte | 30 | 17 |
| `src/nablamath/network/__init__.py` | existente | fonte | 24 | 22 |
| `src/nablamath/network/bundle.py` | existente | fonte | 63 | 51 |
| `src/nablamath/network/chunks.py` | existente | fonte | 42 | 31 |
| `src/nablamath/network/consensus.py` | existente | fonte | 61 | 49 |
| `src/nablamath/network/manifest.py` | existente | fonte | 47 | 37 |
| `src/nablamath/network/migrations.py` | existente | fonte | 41 | 32 |
| `src/nablamath/network/objects.py` | existente | fonte | 162 | 136 |
| `src/nablamath/network/peer.py` | existente | fonte | 152 | 128 |
| `src/nablamath/network/protocol.py` | existente | fonte | 107 | 85 |
| `src/nablamath/network/receipts.py` | existente | fonte | 52 | 40 |
| `src/nablamath/network/retractions.py` | existente | fonte | 27 | 20 |
| `src/nablamath/network/store.py` | existente | fonte | 71 | 59 |
| `src/nablamath/node/__init__.py` | existente | fonte | 12 | 10 |
| `src/nablamath/node/consent.py` | existente | fonte | 54 | 43 |
| `src/nablamath/node/daemon.py` | existente | fonte | 69 | 54 |
| `src/nablamath/node/local.py` | existente | fonte | 46 | 34 |
| `src/nablamath/node/policies.py` | existente | fonte | 33 | 25 |
| `src/nablamath/node/resources.py` | existente | fonte | 29 | 22 |
| `src/nablamath/node/tasks.py` | existente | fonte | 41 | 30 |
| `src/nablamath/node/verifier.py` | existente | fonte | 36 | 26 |
| `src/nablamath/node/workspace.py` | existente | fonte | 32 | 23 |
| `src/nablamath/numeric/__init__.py` | existente | fonte | 1 | 1 |
| `src/nablamath/numeric/evaluate.py` | existente | fonte | 24 | 18 |
| `src/nablamath/numeric/linear.py` | existente | fonte | 26 | 23 |
| `src/nablamath/numeric/ode.py` | existente | fonte | 34 | 29 |
| `src/nablamath/optimization.py` | existente | fonte | 258 | 219 |
| `src/nablamath/orbit_svg.py` | existente | fonte | 41 | 34 |
| `src/nablamath/orbits.py` | existente | fonte | 60 | 45 |
| `src/nablamath/p2p/__init__.py` | existente | fonte | 8 | 8 |
| `src/nablamath/p2p/discovery.py` | existente | fonte | 39 | 27 |
| `src/nablamath/p2p/peer.py` | existente | fonte | 26 | 20 |
| `src/nablamath/p2p/quarantine.py` | existente | fonte | 39 | 30 |
| `src/nablamath/p2p/rate_limits.py` | existente | fonte | 27 | 21 |
| `src/nablamath/p2p/replication.py` | existente | fonte | 33 | 24 |
| `src/nablamath/p2p/transport.py` | existente | fonte | 41 | 32 |
| `src/nablamath/physics/__init__.py` | existente | fonte | 11 | 9 |
| `src/nablamath/physics/differentiable.py` | existente | fonte | 143 | 119 |
| `src/nablamath/physics/fea/__init__.py` | existente | fonte | 13 | 12 |
| `src/nablamath/physics/fea/bar.py` | existente | fonte | 114 | 95 |
| `src/nablamath/physics/fea/truss2d.py` | existente | fonte | 203 | 179 |
| `src/nablamath/physics/fluids/__init__.py` | existente | fonte | 8 | 7 |
| `src/nablamath/physics/fluids/burgers.py` | existente | fonte | 84 | 71 |
| `src/nablamath/physics/fluids/model.py` | existente | fonte | 47 | 37 |
| `src/nablamath/physics/fluids/navier_stokes.py` | existente | fonte | 225 | 195 |
| `src/nablamath/physics/fluids/validation.py` | existente | fonte | 13 | 9 |
| `src/nablamath/physics/orbital/__init__.py` | existente | fonte | 6 | 5 |
| `src/nablamath/physics/orbital/dynamics.py` | existente | fonte | 62 | 48 |
| `src/nablamath/physics/orbital/state.py` | existente | fonte | 26 | 19 |
| `src/nablamath/physics/orbital/validation.py` | existente | fonte | 38 | 27 |
| `src/nablamath/physics/plasma/__init__.py` | existente | fonte | 3 | 2 |
| `src/nablamath/physics/plasma/mhd.py` | existente | fonte | 144 | 128 |
| `src/nablamath/physics/relativity/__init__.py` | existente | fonte | 13 | 11 |
| `src/nablamath/physics/relativity/general.py` | existente | fonte | 68 | 51 |
| `src/nablamath/physics/relativity/special.py` | existente | fonte | 93 | 68 |
| `src/nablamath/pipeline/__init__.py` | existente | fonte | 3 | 2 |
| `src/nablamath/pipeline/cache.py` | existente | fonte | 29 | 23 |
| `src/nablamath/pipeline/engine.py` | existente | fonte | 40 | 32 |
| `src/nablamath/pipeline/provenance.py` | existente | fonte | 13 | 10 |
| `src/nablamath/publisher/__init__.py` | existente | fonte | 1 | 1 |
| `src/nablamath/publisher/huggingface.py` | existente | fonte | 97 | 89 |
| `src/nablamath/publisher/manifest.py` | existente | fonte | 30 | 22 |
| `src/nablamath/report.py` | existente | fonte | 76 | 65 |
| `src/nablamath/reports/__init__.py` | existente | fonte | 7 | 6 |
| `src/nablamath/reports/compile.py` | existente | fonte | 24 | 19 |
| `src/nablamath/reports/latex.py` | existente | fonte | 20 | 12 |
| `src/nablamath/reports/model.py` | existente | fonte | 29 | 19 |
| `src/nablamath/reports/solution.py` | existente | fonte | 89 | 77 |
| `src/nablamath/research.py` | existente | fonte | 119 | 106 |
| `src/nablamath/schema/__init__.py` | existente | fonte | 7 | 5 |
| `src/nablamath/schema/artifact.py` | existente | fonte | 17 | 13 |
| `src/nablamath/schema/evidence.py` | existente | fonte | 25 | 19 |
| `src/nablamath/schema/experiment.py` | existente | fonte | 15 | 11 |
| `src/nablamath/schema/expression.py` | existente | fonte | 23 | 17 |
| `src/nablamath/schema/problem.py` | existente | fonte | 17 | 13 |
| `src/nablamath/schema/step.py` | existente | fonte | 16 | 12 |
| `src/nablamath/schema/units.py` | existente | fonte | 71 | 52 |
| `src/nablamath/schema/version.py` | existente | fonte | 8 | 5 |
| `src/nablamath/singularity/__init__.py` | existente | fonte | 6 | 4 |
| `src/nablamath/singularity/agents/__init__.py` | existente | fonte | 8 | 7 |
| `src/nablamath/singularity/agents/base.py` | existente | fonte | 35 | 23 |
| `src/nablamath/singularity/agents/coder.py` | existente | fonte | 14 | 9 |
| `src/nablamath/singularity/agents/critic.py` | existente | fonte | 15 | 10 |
| `src/nablamath/singularity/agents/mathematician.py` | existente | fonte | 14 | 9 |
| `src/nablamath/singularity/agents/researcher.py` | existente | fonte | 14 | 9 |
| `src/nablamath/singularity/agents/scientist.py` | existente | fonte | 14 | 9 |
| `src/nablamath/singularity/core/__init__.py` | existente | fonte | 6 | 5 |
| `src/nablamath/singularity/core/cognition.py` | existente | fonte | 64 | 50 |
| `src/nablamath/singularity/core/memory.py` | existente | fonte | 54 | 40 |
| `src/nablamath/singularity/core/planner.py` | existente | fonte | 59 | 47 |
| `src/nablamath/singularity/core/self_model.py` | existente | fonte | 41 | 29 |
| `src/nablamath/singularity/engineering/__init__.py` | existente | fonte | 7 | 6 |
| `src/nablamath/singularity/engineering/code_generator.py` | existente | fonte | 29 | 20 |
| `src/nablamath/singularity/engineering/optimizer.py` | existente | fonte | 38 | 28 |
| `src/nablamath/singularity/engineering/simulator.py` | existente | fonte | 25 | 18 |
| `src/nablamath/singularity/engineering/test_generator.py` | existente | fonte | 28 | 20 |
| `src/nablamath/singularity/infrastructure/__init__.py` | existente | fonte | 5 | 4 |
| `src/nablamath/singularity/infrastructure/distributed_runtime.py` | existente | fonte | 39 | 26 |
| `src/nablamath/singularity/infrastructure/resource_manager.py` | existente | fonte | 33 | 23 |
| `src/nablamath/singularity/infrastructure/sandbox.py` | existente | fonte | 5 | 3 |
| `src/nablamath/singularity/infrastructure/scheduler.py` | existente | fonte | 26 | 16 |
| `src/nablamath/singularity/interfaces/__init__.py` | existente | fonte | 4 | 3 |
| `src/nablamath/singularity/interfaces/api.py` | existente | fonte | 18 | 11 |
| `src/nablamath/singularity/interfaces/terminal.py` | existente | fonte | 27 | 20 |
| `src/nablamath/singularity/interfaces/visualization.py` | existente | fonte | 17 | 12 |
| `src/nablamath/singularity/learning/__init__.py` | existente | fonte | 6 | 5 |
| `src/nablamath/singularity/learning/curriculum.py` | existente | fonte | 29 | 21 |
| `src/nablamath/singularity/learning/evaluator.py` | existente | fonte | 29 | 21 |
| `src/nablamath/singularity/learning/experiment.py` | existente | fonte | 41 | 30 |
| `src/nablamath/singularity/learning/knowledge_graph.py` | existente | fonte | 5 | 3 |
| `src/nablamath/singularity/system/__init__.py` | existente | fonte | 4 | 3 |
| `src/nablamath/singularity/system/configuration.py` | existente | fonte | 26 | 19 |
| `src/nablamath/singularity/system/main.py` | existente | fonte | 5 | 3 |
| `src/nablamath/singularity/system/orchestrator.py` | existente | fonte | 72 | 61 |
| `src/nablamath/solution.py` | existente | fonte | 104 | 90 |
| `src/nablamath/storage.py` | existente | fonte | 118 | 104 |
| `src/nablamath/store/__init__.py` | existente | fonte | 3 | 2 |
| `src/nablamath/store/backup.py` | existente | fonte | 97 | 83 |
| `src/nablamath/store/blobs.py` | existente | fonte | 46 | 39 |
| `src/nablamath/store/migrations/0001_initial.py` | existente | fonte | 10 | 9 |
| `src/nablamath/store/migrations/README.md` | existente | fonte | 8 | — |
| `src/nablamath/store/migrations/__init__.py` | existente | fonte | 29 | 20 |
| `src/nablamath/store/sqlite.py` | existente | fonte | 5 | 3 |
| `src/nablamath/symbolic/__init__.py` | alterado | fonte | 18 | 17 |
| `src/nablamath/symbolic/assumptions.py` | alterado | fonte | 57 | 49 |
| `src/nablamath/symbolic/derive.py` | existente | fonte | 10 | 6 |
| `src/nablamath/symbolic/differentiate.py` | alterado | fonte | 167 | 141 |
| `src/nablamath/symbolic/egraph.py` | alterado | fonte | 369 | 333 |
| `src/nablamath/symbolic/integrate.py` | existente | fonte | 55 | 44 |
| `src/nablamath/symbolic/parser.py` | existente | fonte | 7 | 4 |
| `src/nablamath/symbolic/patterns.py` | alterado | fonte | 119 | 106 |
| `src/nablamath/symbolic/proof.py` | alterado | fonte | 118 | 108 |
| `src/nablamath/symbolic/rules.py` | alterado | fonte | 59 | 45 |
| `src/nablamath/symbolic/series.py` | existente | fonte | 99 | 81 |
| `src/nablamath/training/__init__.py` | existente | fonte | 2 | 2 |
| `src/nablamath/training/registry.py` | existente | fonte | 40 | 32 |
| `src/nablamath/verify/__init__.py` | novo | fonte | 4 | 3 |
| `src/nablamath/verify/certificate.py` | novo | fonte | 122 | 106 |
| `src/nablamath/verify/geometry.py` | novo | fonte | 51 | 44 |
| `src/nablamath/verify/trace.py` | novo | fonte | 136 | 121 |
| `src/nablamath/viz/__init__.py` | existente | fonte | 4 | 3 |
| `src/nablamath/viz/plot.py` | existente | fonte | 24 | 18 |
| `src/nablamath/viz/render.py` | existente | fonte | 17 | 11 |
| `src/nablamath/viz/spec.py` | existente | fonte | 32 | 23 |
| `src/nablamath/worlds/__init__.py` | novo | fonte | 4 | 3 |
| `src/nablamath/worlds/validation.py` | novo | fonte | 79 | 68 |
| `tests/evaluation/test_contamination.py` | existente | testes | 20 | 14 |
| `tests/integration/__init__.py` | existente | testes | 1 | 1 |
| `tests/integration/test_agent_limits.py` | existente | testes | 20 | 14 |
| `tests/integration/test_backup_restore.py` | alterado | testes | 62 | 54 |
| `tests/integration/test_cli_local.py` | existente | testes | 21 | 17 |
| `tests/integration/test_coordinator.py` | existente | testes | 27 | 22 |
| `tests/integration/test_dataset_pipeline.py` | existente | testes | 18 | 13 |
| `tests/integration/test_desktop.py` | existente | testes | 62 | 58 |
| `tests/integration/test_lean_bridge.py` | existente | testes | 20 | 14 |
| `tests/integration/test_publisher.py` | existente | testes | 84 | 77 |
| `tests/interop/README.md` | existente | testes | 3 | — |
| `tests/knowledge/test_graph.py` | existente | testes | 23 | 16 |
| `tests/math/test_advanced_foundations.py` | existente | testes | 41 | 31 |
| `tests/math/test_advanced_requested_algorithms.py` | existente | testes | 138 | 126 |
| `tests/math/test_applied_expansion.py` | existente | testes | 49 | 39 |
| `tests/math/test_categories.py` | existente | testes | 15 | 11 |
| `tests/math/test_discrete_expansion.py` | existente | testes | 48 | 38 |
| `tests/math/test_extended_domains.py` | existente | testes | 51 | 39 |
| `tests/math/test_foundations.py` | existente | testes | 48 | 36 |
| `tests/math/test_groebner.py` | existente | testes | 73 | 63 |
| `tests/math/test_linear_algebra.py` | existente | testes | 16 | 12 |
| `tests/math/test_numerical_information_expansion.py` | existente | testes | 42 | 34 |
| `tests/math/test_polynomials_automata_optimization.py` | existente | testes | 32 | 26 |
| `tests/math/test_requested_expansion.py` | existente | testes | 120 | 108 |
| `tests/math/test_sat_resolution_integration.py` | existente | testes | 43 | 35 |
| `tests/math/test_scheduling_graph_timeseries.py` | existente | testes | 38 | 30 |
| `tests/math/test_structural_expansion.py` | existente | testes | 47 | 37 |
| `tests/network/test_content_protocol.py` | existente | testes | 64 | 50 |
| `tests/network/test_receipts_retractions.py` | existente | testes | 34 | 25 |
| `tests/network/test_replication.py` | existente | testes | 48 | 35 |
| `tests/node/test_consent_audit.py` | existente | testes | 22 | 18 |
| `tests/node/test_local_node.py` | existente | testes | 59 | 43 |
| `tests/node/test_workspace.py` | existente | testes | 11 | 9 |
| `tests/p2p/test_primitives.py` | existente | testes | 38 | 30 |
| `tests/p2p/test_transport.py` | existente | testes | 25 | 21 |
| `tests/protocol/test_golden.py` | existente | testes | 18 | 14 |
| `tests/regression/__init__.py` | novo | testes | 1 | 1 |
| `tests/regression/test_public_api.py` | novo | testes | 48 | 40 |
| `tests/science/__init__.py` | existente | testes | 1 | 1 |
| `tests/science/test_fluids_reference.py` | existente | testes | 15 | 10 |
| `tests/science/test_orbital_reference.py` | existente | testes | 17 | 12 |
| `tests/test_agents.py` | existente | testes | 19 | 16 |
| `tests/test_compatibility.py` | existente | testes | 32 | 24 |
| `tests/test_compiler_backends.py` | existente | testes | 46 | 38 |
| `tests/test_coordinator_local.py` | existente | testes | 25 | 22 |
| `tests/test_core.py` | existente | testes | 104 | 88 |
| `tests/test_curation.py` | existente | testes | 25 | 22 |
| `tests/test_dataset_card.py` | existente | testes | 25 | 21 |
| `tests/test_declarative_egraph.py` | existente | testes | 40 | 34 |
| `tests/test_deep_autodiff.py` | existente | testes | 26 | 20 |
| `tests/test_differentiable_pde_fea.py` | existente | testes | 48 | 38 |
| `tests/test_differentiable_physics.py` | existente | testes | 49 | 41 |
| `tests/test_distributed_planner.py` | existente | testes | 54 | 46 |
| `tests/test_egraph.py` | existente | testes | 61 | 50 |
| `tests/test_entity.py` | existente | testes | 40 | 32 |
| `tests/test_exchange.py` | existente | testes | 32 | 28 |
| `tests/test_fluids.py` | existente | testes | 23 | 19 |
| `tests/test_formal.py` | existente | testes | 19 | 15 |
| `tests/test_formal_search.py` | existente | testes | 37 | 30 |
| `tests/test_gpu_acceleration.py` | existente | testes | 62 | 53 |
| `tests/test_incompressible_cfd.py` | existente | testes | 67 | 59 |
| `tests/test_interop.py` | existente | testes | 35 | 31 |
| `tests/test_linear_mhd.py` | existente | testes | 49 | 41 |
| `tests/test_math_bundle.py` | alterado | testes | 48 | 39 |
| `tests/test_merkle.py` | existente | testes | 12 | 9 |
| `tests/test_numeric.py` | existente | testes | 28 | 23 |
| `tests/test_optimization.py` | existente | testes | 45 | 35 |
| `tests/test_orbital_dynamics.py` | existente | testes | 37 | 32 |
| `tests/test_orbits.py` | existente | testes | 35 | 28 |
| `tests/test_peer_transport.py` | existente | testes | 53 | 43 |
| `tests/test_phase1_calculator.py` | novo | testes | 232 | 211 |
| `tests/test_phase2_forge.py` | novo | testes | 164 | 147 |
| `tests/test_phase3_formal.py` | novo | testes | 161 | 141 |
| `tests/test_phase4_graphics.py` | novo | testes | 156 | 140 |
| `tests/test_pipeline.py` | existente | testes | 29 | 25 |
| `tests/test_planar_truss_fea.py` | existente | testes | 71 | 63 |
| `tests/test_relativity.py` | existente | testes | 55 | 44 |
| `tests/test_reverse_autodiff.py` | existente | testes | 29 | 24 |
| `tests/test_schema.py` | existente | testes | 20 | 17 |
| `tests/test_scientific_cycle.py` | novo | testes | 243 | 217 |
| `tests/test_scientific_extensions.py` | novo | testes | 180 | 158 |
| `tests/test_singularity_lab.py` | existente | testes | 67 | 57 |
| `tests/test_solution_bundle.py` | existente | testes | 26 | 20 |
| `tests/test_solution_report.py` | existente | testes | 21 | 16 |
| `tests/test_symbolic_differentiation.py` | existente | testes | 40 | 32 |
| `tests/test_tensor_autodiff.py` | existente | testes | 27 | 23 |
| `tests/test_units.py` | existente | testes | 21 | 17 |
| `tests/test_universal_lean_translation.py` | existente | testes | 19 | 17 |
| `tests/test_visualization.py` | existente | testes | 21 | 18 |
| `tests/training/test_registry.py` | existente | testes | 10 | 8 |
| `tests/unit/__init__.py` | existente | testes | 1 | 1 |
| `tests/unit/test_domain_rules.py` | existente | testes | 18 | 12 |
| `tests/unit/test_schema_roundtrip.py` | existente | testes | 18 | 12 |
| `tests/unit/test_units.py` | existente | testes | 22 | 15 |
| `tests/website/test_lab.mjs` | existente | testes | 20 | 17 |
| `tests/website/test_worker.mjs` | existente | testes | 34 | 29 |
| `tools/build_math_bundle.py` | alterado | infraestrutura/outros | 121 | 108 |
| `tools/export_source_bundle.py` | existente | infraestrutura/outros | 67 | 57 |
| `tools/project_inventory.py` | novo | infraestrutura/outros | 163 | 149 |
| `tools/roadmap_status.py` | existente | infraestrutura/outros | 25 | 18 |
| `tools/singlefile/README.md` | existente | infraestrutura/outros | 5 | — |
| `vision.md` | existente | infraestrutura/outros | 442 | — |
| `website/.nojekyll` | existente | infraestrutura/outros | 1 | — |
| `website/app.js` | existente | infraestrutura/outros | 104 | 98 |
| `website/data/status.json` | existente | infraestrutura/outros | 11 | — |
| `website/index.html` | existente | infraestrutura/outros | 111 | 111 |
| `website/package.json` | existente | infraestrutura/outros | 9 | — |
| `website/public/.nojekyll` | existente | infraestrutura/outros | 1 | — |
| `website/src/community.js` | existente | infraestrutura/outros | 3 | 3 |
| `website/src/data.js` | existente | infraestrutura/outros | 5 | 5 |
| `website/src/explorer.js` | existente | infraestrutura/outros | 4 | 4 |
| `website/src/index.js` | existente | infraestrutura/outros | 2 | 1 |
| `website/src/lab.js` | existente | infraestrutura/outros | 105 | 99 |
| `website/src/roadmap.js` | existente | infraestrutura/outros | 5 | 5 |
| `website/styles.css` | existente | infraestrutura/outros | 6 | 3 |
| `website/worker.js` | existente | infraestrutura/outros | 55 | 49 |
