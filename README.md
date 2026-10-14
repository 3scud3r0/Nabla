# ∇ NablaMath

**Um laboratório local para cálculos rastreáveis, dados curados e pesquisa matemática aberta.** O pacote Python já executa um subconjunto de aritmética racional, registra as etapas no SQLite e oferece experimentos físicos bem delimitados. A rede científica global descrita no roteiro continua em desenvolvimento.

**Direção de longo prazo:** [Visão científica 2026–2056+](vision.md) · [Plano mestre de arquitetura e execução](docs/PLANO_MESTRE_2026_2056.md).

[Instalação](#instalação) · [Aplicativo local](#aplicativo-local) · [Verificação](#verificação) · [Roteiro](docs/ROADMAP_GLOBAL_RESEARCH.md) · [Contribuir](CONTRIBUTING.md)

## O que funciona hoje

| Função | Escopo comprovável | Limite atual |
| --- | --- | --- |
| Cálculo e etapas | Avaliação racional exata, condições de domínio, e-graph limitado, SQLite e relatório `.tex` | Conjunto inicial de regras; não é álgebra computacional geral |
| Lean 4 | Provas de instâncias racionais específicas, com Lake/Mathlib opcionais | Não formaliza automaticamente qualquer identidade ou teoria física |
| Física | Órbita ideal de dois corpos, propagação radial reduzida e fluxo laminar analítico | Não é CFD ou dinâmica orbital perturbada validada experimentalmente |
| Dados | Exportação/importação reexecutáveis, SHA-256, deduplicação, card e aprovação para upload | Não há snapshot científico público confirmado nem avaliação de ganho em treino |
| Aplicativo pessoal | Interface no navegador local, banco próprio, botões, loop com limite e upload opcional | Não é serviço multiusuário nem computador global |
| Site | Site estático publicado via GitHub Pages | Métricas versionadas; não há API pública de participantes em tempo real |

## Instalação

Requer **Python 3.10+**. Na pasta do projeto (para publicar no Hub, instale `python -m pip install ".[cloud]"`):

```bash
python -m pip install .
nabla doctor
nabla desktop
```

Em Windows, a [compilação Windows](https://github.com/3scud3r0/Nabla-Math/actions/workflows/windows-installer.yml) constrói e testa o instalador. Depois da primeira execução bem-sucedida no branch principal, baixe o `.exe` na [versão alpha](https://github.com/3scud3r0/Nabla-Math/releases/tag/v0.1.0-alpha.1). O instalador ainda não possui assinatura de código. Veja o [guia do aplicativo](docs/DESKTOP.md) e os scripts de desenvolvimento `setup.cmd`, `setup.ps1` e `setup.sh`.

## Aplicativo local

`nabla desktop` abre uma página acessível **somente neste computador**, vinculada a `127.0.0.1`. O banco e os arquivos ficam em `~/NablaMath`, inclusive depois da desinstalação. Você pode:

1. Calcular `(x+x)/x` para `x=3`, inspecionar a condição `x ≠ 0` e gerar LaTeX.
2. Iniciar e interromper um loop de até 1.000 exemplos racionais por sessão. Ele repete quatro famílias explícitas com diferentes valores; quantidade não significa descoberta científica.
3. Consultar uma órbita circular ideal e um caso analítico de fluxo em tubo.
4. Exportar o banco como JSONL com manifesto, importar um snapshot local revalidado e preparar um lote curado.
5. Publicar um lote no **seu** dataset Hugging Face somente após informar destino, token e declarar os direitos sobre os dados. O token não é salvo no banco.

O [site público](https://3scud3r0.github.io/Nabla-Math/) mostra métricas de um snapshot versionado e oferece um worker opt-in no navegador para gerar exemplos aritméticos demonstrativos e baixar um JSONL. Esse trabalho **não é enviado ao global**: não há backend público implantado. O worker não produz novas descobertas nem provas Lean.

## Terminal e Python

```bash
nabla run "(x+x)/x" --value x=3 --tex report.tex
nabla orbit --altitude-m 400000 --svg orbit.svg
nabla fluid --radius-m .01 --length-m 2 --pressure-pa 5 --viscosity-pa-s 1 --density-kg-m3 1000
nabla export lote.jsonl --db minha.sqlite3
nabla import lote.jsonl --db outro.sqlite3
nabla backup backup.sqlite3 --db minha.sqlite3
nabla restore backup.sqlite3 --db restaurado.sqlite3
```

```python
from nablamath.research import calculate
result = calculate("(x+x)/x", {"x": 3})
print(result.value)            # 2, exatamente
print(result.to_data()["assumptions"])  # ['x != 0']
```

O módulo simbólico também oferece **saturação de igualdades auditável**. Em vez de
reescrever uma árvore destrutivamente, ele preserva formas equivalentes em um
e-graph, registra cada união e extrai a forma de menor custo para o backend:

```python
from nablamath.symbolic import parse, saturate

optimized = saturate(
    parse("a*b + a*c"),
    operation_costs={"*": 10, "+": 1, "symbol": 0},
    iteration_limit=8,
    node_limit=2_000,
)
print(optimized.expression)  # a * (b + c), em AST tipada
print(optimized.proof)       # trilha das igualdades aplicadas
print(optimized.stop_reason) # saturated, node_limit ou iteration_limit
print(optimized.content_id)  # SHA-256 do registro de auditoria reproduzível
```

`node_limit` é um teto rígido, inclusive durante uma passagem de regras; custos
negativos, infinitos ou `NaN` são rejeitados para manter a extração bem definida.
Os limites evitam explosão combinatória. As regras padrão são conservadoras com
o domínio: por exemplo, não reduzem `0 * (1/x)` a zero, pois isso esconderia a
singularidade em `x=0`.

O primeiro exemplo simplifica `x+x` para `2x` e cancela `x` **somente se `x ≠ 0`**. A avaliação para `x=3` é exata; isso não prova uma lei universal sem hipóteses.

## Verificação

```bash
python -m unittest discover -s tests -v
python tools/roadmap_status.py
```

O segundo comando mostra o checklist F0–F6; não mede maturidade científica. Cada modelo físico requer comparação com referência independente antes de qualquer alegação aplicada. Consulte o [estado das implementações](docs/IMPLEMENTATION_STATUS.md), o [protocolo de publicação](docs/PUBLISHING.md), as [decisões pendentes](docs/DECISIONS/README.md) e a [estimativa do roteiro](docs/ESTIMATIVA_EXECUCAO.md).

Para concatenar fontes e configurações atuais em um arquivo legível (exclui `legacy/`, ambientes, dependências instaladas e dados), execute `python tools/export_source_bundle.py`. O resultado padrão é `NablaMath_current_sources.txt`.

O arquivo versionado [`math.txt`](math.txt) aglutina, em ordem determinística, todo
o código matemático canônico em Python e Lean deste recorte. Cada seção contém
caminho, número de linhas e SHA-256. Regenere-o com
`python tools/build_math_bundle.py` e verifique sincronização com
`python tools/build_math_bundle.py --check`; o bundle é artefato de distribuição,
não uma segunda fonte editável nem uma alegação de que “toda a matemática” acabou.

O [laboratório autônomo limitado](docs/AUTONOMOUS_RESEARCH_LAB.md) materializa a
arquitetura de planejador, memória, agentes, experimentos, crítica, avaliação e
orquestração em componentes declarativos. `nablamath.gpu` acrescenta pontos de
integração para redução modular/F4, e-graphs compactados, MCTS em lote, guia INT8 e
buffers de dispositivo, sempre com fallback CPU explicitamente identificado. Não
há alegação de singularidade nem execução CUDA sem um backend real e benchmark.

## Estrutura

| Diretório | Responsabilidade |
| --- | --- |
| `src/nablamath/` | Pacote instalável; núcleo, física, desktop, publicação opcional |
| `lean/` | Projetos e exemplos formais em Lean/Mathlib |
| `tests/` | Testes de unidade, integração, física e interoperabilidade |
| `website/` | Site estático público GitHub Pages; métricas versionadas |
| `services/` | Protótipos de coordenação e utilitários de serviço |
| `sdk/`, `protocol/` | Contratos de interoperabilidade em evolução |
| `packaging/windows/` | Receita reproduzível do instalador Windows |
| `docs/` | Roteiro, governança, guias de operação e limites |
| `archive/` | Acervo histórico, quando presente no clone |

## Roteiro e status

O [roadmap global](docs/ROADMAP_GLOBAL_RESEARCH.md) lista os arquivos restantes, critérios de aceite e dependências externas para cada fase F0–F6. **Arquivos presentes não significam fases concluídas.** Lean geral, descoberta científica autônoma, coordenação pública resistente a fraude, sincronização entre máquinas e ganho mensurável em treino de IA permanecem metas de pesquisa. Não há prazo científico garantido nem resultados físicos certificados.

Licença do código: [MIT](LICENSE). Dados e dependências têm direitos próprios: revise a procedência antes de redistribuir. Consulte [segurança](SECURITY.md) e [política de dados](docs/DATA_GOVERNANCE.md).
