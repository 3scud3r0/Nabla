# Contribuir com NablaMath

Comece pelo [índice](docs/README.md), pelo [backlog F1–F12](docs/audits/PHASES_1_12_COMPLETION_BACKLOG.md)
e pela [estrutura](docs/architecture/repository-layout.md). Desenvolva alterações
com hipótese explícita, domínio, unidades quando físicas, comparação independente
e limites documentados.

Em um ambiente Python ativado, na raiz:

```sh
python -m pip install -e ".[test,formal,graphics,documents,data,research,federation]"
python -m pytest -q
python tools/build_math_bundle.py --check
```

O núcleo suporta Python 3.10–3.14; os perfis completos são exercitados em Python
3.12. Lean usa a toolchain fixada em `lean/lean-toolchain`; consulte
`scripts/setup_formal.sh` antes de `lake build` em `lean/`. Preserve os lockfiles;
`lake update` não é preparação rotineira.

Após mudar fontes matemáticas, regenere `math.txt` com
`python tools/build_math_bundle.py`. Após adicionar arquivos ao índice, atualize
o inventário com `python tools/project_inventory.py --base origin/main`.
Bundles auditados conservam nomes, bytes e manifestos; saídas locais ficam em
`.nabla/`. Veja os requisitos do [laboratório](docs/FRONTIER_LAB_SIMULATION.md).

Para proposições Lean, deixe claros axiomas e hipóteses; nunca use `sorry`, `admit` ou axiomas novos para declarar uma prova pronta. Compare o enunciado formal com o problema original antes de interpretá-lo. Para dados, mantenha origem, licença, divisões e versão; não envie chaves, prompts privados nem dados de terceiros sem direito de uso. Resultados negativos e falhas são contribuições úteis.

O código está sob [MIT](LICENSE). Dados, referências e dependências têm licenças
próprias; registre origem e direitos antes de redistribuir. Pendências operacionais
estão no [registro de decisões](docs/DECISIONS/README.md). Descreva no PR o
comportamento final, a validação executada e os limites; estados de CI e conclusões
científicas não se transferem entre snapshots sem nova evidência.
