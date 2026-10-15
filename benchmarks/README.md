# Benchmarks e evidências

| Pasta | Finalidade |
|---|---|
| `fixtures/` | Referências fixadas e procedência; NIST Longley tem proteção de bytes |
| `tasks/`, `baselines/` | Perfis de tarefas e baselines |
| `results/` | Execuções versionadas, protocolos, modelos, avaliações e limitações |

## Resultados principais

- [Campanha laboratorial simulada](results/FRONTIER_LAB_README.md): 192 tarefas, seis avaliações, solvers independentes e controles adversariais. Ambos os baselines aprendidos tiveram zero acertos no teste reservado.
- [Artefatos completos](results/frontier-lab-951017/summary.json) e [avaliação estruturada](results/frontier-lab-951017/maturity-assessment.json).
- [Expansão de maturidade e aprendizado multimodal](results/maturity-expansion/README.md): checkpoints e ablações com resultados negativos preservados.
- [Experimento controlado anterior](results/controlled-learning-2026-10/README.md): protocolo e limites do experimento externo.

Resultados são do protocolo, corpus e snapshot identificados. Não extrapole
acerto de um solver para ganho de treinamento ou maturidade científica geral.
Dados sintéticos, fontes observadas e declarações de origem permanecem distintos.

Use o [guia de reprodução](../docs/FRONTIER_LAB_SIMULATION.md). Execuções novas ficam
em `.nabla/`; um resultado só deve entrar em `results/` com protocolo, procedência,
licença, métricas, limitações e artefatos verificáveis. Não renomeie ou edite arquivos
de bundles fechados sem reconstruir e verificar seus manifestos.
