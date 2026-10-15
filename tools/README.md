# Ferramentas de desenvolvimento e reprodução

Execute os comandos na raiz do checkout, com o ambiente Python ativado.
As ferramentas usam o pacote em `src/nablamath/`; não são uma segunda implementação.

| Ferramenta | Uso |
|---|---|
| `simulate_frontier_lab.py` | Campanha local com dados, avaliações, ciência, portfólios e controles |
| `reproduce_maturity.py` | Fluxo integrado com Lean, modelos, cenas, datasets e publicações |
| `reproduce_completion.py` | Reprodução dos perfis de hardening, sem exigir todo o laboratório |
| `reproduce_portfolio.py` | Dois baselines, resultados reservados, promoção e rollback |
| `validate_longley.py` | Comparação numérica contra dados/referências fixados do NIST |
| `assess_vision.py` | Critérios de evidência; não infere conclusão científica pela presença de arquivos |
| `project_inventory.py` | Inventário de arquivos rastreados e linhas; adicionar novos arquivos ao índice antes |
| `build_math_bundle.py` | Gera `math.txt`; `--check` verifica sincronização |
| `export_source_bundle.py` | Exportação local das fontes atuais, excluindo histórico e dependências |
| `roadmap_status.py` | Checklist do roadmap inicial F0–F6; não cobre sozinho a visão atual |
| `fetch_learning_benchmark.py` | Aquisição do benchmark segundo protocolo e procedência |

Reprodução: [guia laboratorial](../docs/FRONTIER_LAB_SIMULATION.md) e
[perfis científicos](../docs/PHASES_MATURITY_EXPANSION.md).
Preparação e importação ficam em `scripts/`; empacotamento fica em `packaging/`.
Os helpers de distribuição standalone estão em [singlefile/](singlefile/README.md).
