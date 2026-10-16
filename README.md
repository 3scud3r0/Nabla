# ∇ Nabla

Laboratório científico local em Python para cálculo rastreável, geração de problemas, verificação matemática, datasets, simulações e publicação reproduzível.

[Começar](#começar) · [Documentação](docs/README.md) · [Estrutura](docs/architecture/repository-layout.md) · [Resultados](benchmarks/README.md) · [Contribuir](CONTRIBUTING.md)

## Estado do projeto

**Versão 1.0.0 para uso pessoal local CPU.** O proprietário dispensou os gates externos de revisão e aceite para seu uso individual; isso não constitui validação independente ou conclusão da visão científica. Consulte o [escopo pessoal](docs/acceptance/PERSONAL_USE_1_0.md). Há componentes executáveis para F1–F12 do [vision.md](vision.md), com escopos delimitados e artefatos verificáveis. As fases científicas não estão declaradas concluídas.

As capacidades e recusas atuais são registradas na [matriz de aceitação](docs/acceptance/evidence_matrix.json) e nos [contratos científicos](docs/acceptance/scientific_capabilities.yaml). Os baselines aprendidos da campanha congelada continuam em **0/48** no teste reservado. A execução histórica do laboratório registrada em 15/10 falhou na etapa Mathlib; resultados e falhas estão na [auditoria](docs/audits/FIVE_THOUSAND_LINES_2026_10_15.md). A estimativa técnica de 70,32% pertence a um snapshot histórico e não mede o estado atual ou conclusão científica.

| Área | Implementação disponível | Guia |
|---|---|---|
| F1–F2: cálculo e Forge | Catálogo versionado de operações, unidades, replay, oito famílias inversas e primitivas racionais | [Cálculo/Forge](docs/phases/PHASES_1_2.md) |
| F3–F4: provas e imagens | Lean/SMT em fragmentos definidos, contraexemplos, cenas SVG/PNG e curvas adaptativas | [Provas/cenas](docs/phases/PHASES_3_4.md) |
| F5–F6: publicação e dados | AST editorial, Typst/LaTeX/PDF, SQLite, JSONL/Parquet e controle de partições | [Perfis atuais](docs/PHASES_MATURITY_EXPANSION.md) |
| F7–F8: simulação e agentes | EDO adaptativa, difusão explícita/implícita, agentes retomáveis e aprendizado | [Fases 5–8](docs/phases/PHASES_5_8.md) |
| F9–F10: descoberta e evolução | Busca de leis em gramática limitada, holdout, portfólios, gates e rollback | [Fases 9–12](docs/phases/PHASES_9_12.md) |
| F11–F12: disciplinas e conhecimento | Modelos SI idealizados, evidências, claims, assinaturas e revogação | [Perfis atuais](docs/PHASES_MATURITY_EXPANSION.md) |

O preparo da versão local 1.0 está em [vision1.md](vision1.md), com
[contrato de API](docs/API_STABILITY.md), [gates de aceite](docs/acceptance/version_1_0.md)
e [changelog](CHANGELOG.md). A entrega pessoal 1.0 usa o escopo e as dispensas registrados no documento de aceite pessoal. Os gates de distribuição pública continuam separados. Para conferir todos os 212 caminhos e o contrato instalado,
execute `python tools/release_readiness.py`.

Novo [laboratório de matemática exata](docs/math/EXACT_LABORATORY.md), com [extensões algébricas, numéricas, combinatórias e probabilísticas integradas ao cálculo](docs/math/ADVANCED_EXACT_EXPANSION.md): implementação independente de dependências externas, com contratos finitos e testes específicos.

## Primeira experiência coesa

O [perfil local de primeira versão](docs/acceptance/COHESIVE_LOCAL_ALPHA.md) organiza **69 operações** sob o mesmo catálogo `nabla catalog`, acessível na CLI, no motor de notebooks e no cartão científico do desktop. A entrega pessoal exige agregados consistentes e smoke do wheel no SHA final. Não equivale à certificação da visão científica inteira.

```sh
nabla catalog
nabla calc analysis_integral --arguments '{"coefficients":[0,0,1],"lower":0,"upper":1}' --notebook primeiro-nabla.json
nabla replay-notebook primeiro-nabla.json
python tools/cohesion_smoke.py
```

## Começar

O núcleo requer **Python 3.10–3.14**. Em um ambiente Python ativado, na raiz do checkout:

```sh
python -m pip install -e .
nabla doctor
nabla catalog
nabla run "(x+x)/x" --value x=3
nabla desktop
```

`nabla desktop` oferece a interface local no navegador, vinculada a `127.0.0.1`. Dados do aplicativo ficam em `~/NablaMath`. O cartão de catálogo permite executar também as operações matemáticas avançadas e consultar os recibos. O banco antigo de expressões permanece separado desses recibos até uma migração tipada explícita; veja o [guia do aplicativo](docs/DESKTOP.md). Windows tem receita de [instalador](packaging/windows/) e scripts `setup.cmd`/`setup.ps1`; Linux/macOS têm `setup.sh`. Consulte o workflow antes de considerar um instalador disponível e validado.

```python
from nablamath.calc.session import CalculationSession

receipt = CalculationSession().execute(
    'least_squares', predictors=[[0], [1], [2]], response=[1, 3, 5]
)
print(receipt.to_data())
```

Para os fluxos científicos completos:

```sh
python -m pip install -e ".[test,formal,graphics,documents,data,research,federation]"
```

Lean/Mathlib e compiladores PDF têm preparação própria. O laboratório completo foi executado em Python 3.12; veja [contribuição](CONTRIBUTING.md) e [reprodução](docs/FRONTIER_LAB_SIMULATION.md) para requisitos opcionais.

O perfil integrado racional liga problema, solução, certificado, dataset, figura
e relatório em um artefato reexecutável, sem serviços externos:

```sh
nabla artifact .nabla/artifact.json --license MIT --provenance "synthetic local experiment"
nabla check-artifact .nabla/artifact.json
python tools/check_roadmap.py
```

Use um destino novo. O [contrato do perfil](docs/acceptance/phase_profiles.md)
documenta limites e a [matriz dos 213 requisitos](docs/acceptance/evidence_matrix.json)
mantém pendências explícitas. Esse perfil não conclui as fases científicas.

## Reproduzir e verificar

```sh
OPENBLAS_NUM_THREADS=1 python -m pytest -q
python tools/build_math_bundle.py --check
python tools/validate_longley.py --output .nabla/nist.json
python tools/simulate_frontier_lab.py .nabla/laboratory-run --per-family 24 --seed 951017
```

No PowerShell, configure `$env:OPENBLAS_NUM_THREADS='1'` antes dos comandos Python. Use destino novo para cada campanha. A simulação é local e não publica dados.

O snapshot científico `5aca9ba` foi validado com **468 testes e 312 subtestes**, wheel isolado e controles de contaminação, adulteração e revogação. Esses números se referem ao snapshot auditado; consulte o estado atual nas [Actions](https://github.com/3scud3r0/Nabla/actions). Os [artefatos](benchmarks/results/frontier-lab-951017/summary.json) incluem protocolo, dados, modelos, avaliações, PDFs, logs e hashes.

## Organização

| Caminho | Conteúdo |
|---|---|
| `src/nablamath/` | Fonte canônica do pacote Python e suas APIs |
| `tests/`, `lean/` | Testes Python e projeto formal fixado |
| `docs/` | Guias, arquitetura, governança, histórico e auditorias |
| `benchmarks/` | Protocolos, fixtures, resultados e evidências versionadas |
| `examples/`, `templates/` | Exemplos e perfis de documentos |
| `tools/`, `scripts/` | Auditoria/reprodução e preparação/importação |
| `protocol/`, `sdk/`, `services/` | Contratos, interoperabilidade e protótipos |
| `packaging/`, `website/` | Empacotamento e site estático |
| `legacy/`, `docs/history/` | Código e documentos históricos preservados |
| `math.txt` | Bundle gerado; não editar à mão |

Veja o [mapa completo](docs/architecture/repository-layout.md) e o [inventário de arquivos e linhas](docs/audits/FILE_INVENTORY.md). Ambientes, caches, builds e execuções locais ficam fora do controle de versão.

## Visão, limites e participação

A [visão 2026–2056+](vision.md), o [plano mestre](docs/PLANO_MESTRE_2026_2056.md) e o [backlog das 12 fases](docs/audits/PHASES_1_12_COMPLETION_BACKLOG.md) orientam a evolução. O [resumo do projeto](description.md) distingue entrega e ambição; o material original está preservado no [histórico](docs/history/README.md).

Simulações são modelos delimitados, sem validação física geral. Assinaturas autenticam chaves configuradas, não expertise. Provas Lean certificam enunciados sob hipóteses; sua correspondência com texto exige revisão. Publicação no Hub é opcional e depende de destino, direitos e credenciais.

Código sob [MIT](LICENSE); dados e dependências têm licenças próprias. [Contribuição](CONTRIBUTING.md) · [Segurança](SECURITY.md) · [Política de dados](docs/DATA_GOVERNANCE.md).

<!-- nabla:contracts:start -->
## Contratos executáveis e pendências atuais

A matriz registra 213 requisitos com perfis parciais, 0 planejados e 0 integralmente validados. Uma referência de implementação não equivale à aceitação integral.

- [Matriz original dos 213 requisitos](docs/acceptance/evidence_matrix.json).
- [Rastreabilidade de fases, requisitos, testes e evidências](docs/acceptance/vision_traceability.json).
- [Domínios, operações, recusas e tolerâncias](docs/acceptance/scientific_capabilities.yaml).

F0 explicita contratos e infraestrutura; F13 continua horizonte aberto. Os perfis de software não demonstram autonomia científica geral. Provas formais exigem kernel e auditoria de hipóteses; GPU exige execução identificada; observações e revisão externa não são substituídas por fixtures ou identidade declarada.

Verificar: `python tools/check_roadmap.py` e `python tools/check_public_contracts.py`, na raiz do repositório.
<!-- nabla:contracts:end -->
