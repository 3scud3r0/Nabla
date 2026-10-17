# ∇ Nabla 1.0

**Laboratório científico local para calcular, auditar, visualizar e publicar experimentos reproduzíveis.**

O Nabla reúne matemática simbólica e numérica, recibos verificáveis, notebooks
reexecutáveis, ferramentas para agentes e documentos científicos reativos.
A versão 1 oferece **134 operações no catálogo**, incluindo **30 operações novas**
e a macro experimental [OMNI_ENGINE](docs/OMNI_ENGINE.md),
e **156 ações especializadas de `advanced_math`**. As ações aninhadas não devem
ser somadas às operações como se fossem áreas matemáticas completas.

[Instalação](#instalação) · [Contrato da versão 1](docs/releases/V1.md) ·
[Documentação](docs/README.md) · [Resultados da validação](docs/releases/V1_VALIDATION.md)

O [gerador procedural de trajetórias matemáticas](docs/SYNTHETIC_TRAJECTORIES.md)
oferece 120 famílias, incluindo 20 desafios compostos de subáreas distintas,
erros rotulados e correções auditáveis. A gramática procedural gera explicações
em português, com exportação TXT/MD, JSONL, SFT e DPO, sem inferência neural.

## Instalação

Python **3.10–3.14**. O núcleo não tem dependências obrigatórias; instale extras
conforme os motores que for utilizar:

```sh
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[test,advanced,scipy,formal,publishing,graphics,pairing,editorial]"
nabla doctor
nabla catalog
nabla desktop
```

`publishing` instala Typst, pypdf, qrcode e Pillow; `pairing` instala py-ecc;
`editorial` instala a inspeção PDF com PyMuPDF. O extra `animation` exige também
os requisitos do Manim: Cairo/Pango, FFmpeg e, para MathTex, LaTeX e dvisvgm.
CUDA, MPI, PyTorch, XLA, MCP e Jupyter têm extras próprios. Veja
[instalação e interface](docs/DESKTOP.md) e [compatibilidade](docs/API_STABILITY.md).

## Calcular, registrar e conferir

```python
from nablamath.calc import CalculationSession
from nablamath.calc.receipt import verify_receipt

session = CalculationSession()
calculation = session.execute(
    "manifold_ricci", coordinates=["theta", "phi"],
    metric=[[1, 0], [0, "sin(theta)**2"]])
audit = calculation.to_data()
assert verify_receipt(audit)
print(audit["result"])
```

```sh
nabla calc analysis_integral --arguments '{"coefficients":[0,0,1],"lower":0,"upper":1}' --notebook experimento.json
nabla replay-notebook experimento.json
```

Cada recibo vincula entradas, resultados, backend e metadados por hash. Usar
`CalculationSession.execute` também permite replay das operações novas. As
schemas de tool calling são fechadas e verificadas contra suas assinaturas.
O perfil de reprodução sem extras conserva as 103 operações anteriores;
o [exemplo completo da versão 1](examples/v1/reproduce.py) usa os motores opcionais.

## Cinco módulos científicos densos

Os cinco arquivos contêm mais de **10 mil linhas de código-fonte Python**,
com algoritmos novos e integração aos motores existentes. Seus caminhos
canônicos são:

| Módulo em `src/nablamath/` | Implementações principais |
|---|---|
| `ops/advanced_calculus_manifold.py` | Tensores mistos, Christoffel, Riemann/Ricci/Einstein/Weyl, geodésicas adaptativas, transporte paralelo, Jacobi, formas/Hodge/Stokes, Euler–Lagrange, Hamilton, Cartan, spin local, ADM e FEM em superfícies |
| `ops/abstract_algebra_crypto.py` | GF(pⁿ), polinômios/fatoração, Reed–Solomon, NTT, curvas jacobianas, Miller/Tate/Weil, isogenias de Vélu, BN254/BLS12-381 via py-ecc, Buchberger, Lie/BCH, LLL, Hensel e aritmética p-ádica finita |
| `ops/stochastic_and_information.py` | Itô/Stratonovich, Euler–Maruyama/Milstein, Fokker–Planck conservativo, GP, cópulas, transporte ótimo, filtros Kalman/partículas, CTMC, sobrevivência e inferência reamostrada |
| `publishing/living_papers_compiler.py` | AST editorial, equações nativas, citações, tabelas, Typst/LaTeX/MathML, watch, PDF com JSON/XMP, QR/SVG, arquivos portáveis e inspeção de layout |
| `graphics/spatial_engine_3d.py` | Three.js/OrbitControls offline, GLB/glTF binário com animações/texturas, malhas e volumes, BVH, clipping, campos/tensores, orbitais e cenas Manim |

As classes podem ser utilizadas diretamente. Operações catalogadas passam pela
sessão para emitir recibos; APIs auxiliares retornam resultados e diagnósticos
sem inventar certificações. O [inventário](docs/MATHEMATICAL_EXPANSION.md) e o
[mapa MSC 2020](docs/MSC2020_COVERAGE.md) documentam os demais ramos.

## Artigos vivos com matemática nativa

```python
from nablamath.artifacts.bundle import create_bundle
from nablamath.publishing.living_papers_compiler import (
    ScientificPaper, ScientificPaperProject, VerifiablePDFWriter,
)

paper = ScientificPaper(
    "Curvatura da esfera", authors=["Meu laboratório"],
    abstract="Cálculo simbólico em uma carta local da esfera unitária.")
paper.section("Geometria", "sec:geometry")
paper.equation("sin(theta)**2", ["theta"], "eq:metric")
paper.paragraph("O resultado auditado está anexado ao documento.")
project = ScientificPaperProject(paper, create_bundle([audit]), "artigo")
built = project.build()
assert VerifiablePDFWriter.inspect(built.pdf)["bundle"]["receipts"][0] == audit
```

O projeto produz PDF tipografado pelo Typst, HTML com MathML offline, fontes
Typst/LaTeX, figuras e dados. Revisões preservam os bytes anteriores; bindings
JSON Pointer atualizam valores a partir dos recibos. Os perfis editoriais
oferecem hierarquia, tipografia, legendas e referências; não representam
aprovação de uma revista. A inspeção mede fontes, limites de texto e rodapés.

```sh
nabla living-paper build template.typ --artifact run.json --output paper.pdf
nabla living-paper inspect paper.pdf --extract experiment.json
```

Templates locais confiáveis aceitam `#nabla-val("nome")` e
`#nabla-calc("operacao", {"argumento": "valor"})`. São documentos executáveis
Typst; a entrada estruturada é a opção para conteúdo não confiável. O modo
`--watch` recompila mudanças com timeout e estado de erro observável.
O PDF incorpora os dados e hashes em anexos e XMP. Criptografia opcional e
assinaturas de laboratório têm políticas explícitas; anexos/XMP não conferem
conformidade PDF/A nem constituem assinatura digital PDF.

## Visualização offline e exportação

```python
from nablamath.graphics.spatial_engine_3d import (
    MeshData, Standalone3DViewer, GLTFExporter,
)

mesh = MeshData(((0., 0., 0.), (1., 0., 0.), (0., 1., 0.)), ((0, 1, 2),))
Standalone3DViewer().write(mesh, "scene.html", audit_receipt=audit)
GLTFExporter().write(mesh, "scene.glb", audit_receipt=audit)
```

Three.js e OrbitControls estão incorporados, com licença MIT e hash conferido:
sem CDN, Node ou servidor para abrir a cena. Há órbita, zoom, cores, controle
temporal e download do recibo. `SpatialExperiment` empacota HTML, GLB, amostras
e proveniência em um diretório verificável. Amostras vinculadas a recibos podem
ser conferidas por JSON Pointer. Uma visualização associada a um recibo não é,
por isso só, uma solução científica comprovada. A taxa de quadros depende da cena
e do dispositivo; vídeos exigem o renderizador Manim.

## Validação e limites

```sh
python -m pytest -q
python tools/vision_readiness.py
python tools/build_math_bundle.py --check
python tools/build_nabla_bundle.py --check
```

Veja os resultados executados, falhas corrigidas e bloqueios em
[V1_VALIDATION.md](docs/releases/V1_VALIDATION.md). A versão 1 entrega um
laboratório local com contratos delimitados. Não há porcentagem universal de
cobertura matemática. Recibos provam integridade; correção matemática,
adequação física e revisão científica exigem evidências próprias.

Aritmética criptográfica Python é variável no tempo e voltada a pesquisa.
Milstein multidimensional exige ruído comutativo; cálculos de variedades usam
cartas regulares; estimativas estatísticas dependem de suas hipóteses.
Testes CPU não certificam GPU ou clusters. Lean/Mathlib requer seu ambiente
formal preparado; a matriz de aceitação abaixo conserva as pendências.

## Organização

| Caminho | Responsabilidade |
|---|---|
| `src/nablamath/` | Fonte canônica do pacote instalável |
| `tests/` | Referências independentes, propriedades, contratos e integrações |
| `docs/`, `examples/`, `templates/` | Guias, relatórios e experimentos |
| `benchmarks/`, `lean/` | Referências científicas e projeto formal |
| `tools/`, `scripts/` | Geração, auditoria e preparação |
| `plugins/`, `sdk/`, `protocol/`, `services/` | Integrações e contratos |
| `packaging/`, `website/`, `legacy/` | Distribuição, site e fontes históricas |
| `NABLA.TXT`, `math.txt` | Bundles gerados; fontes individuais continuam canônicas |

Ambientes e resultados de execução ficam em diretórios ignorados. Os antigos
imports dos compiladores na raiz são compatíveis com os módulos canônicos em
`publishing/` e `graphics/`. Veja o [mapa de pastas](docs/architecture/repository-layout.md).

Código sob [MIT](LICENSE). [Contribuir](CONTRIBUTING.md) · [Segurança](SECURITY.md) ·
[Changelog](CHANGELOG.md).

<!-- nabla:contracts:start -->
## Contratos executáveis e pendências atuais

A matriz registra 213 requisitos com perfis parciais, 0 planejados e 0 integralmente validados. Uma referência de implementação não equivale à aceitação integral.

- [Matriz original dos 213 requisitos](docs/acceptance/evidence_matrix.json).
- [Rastreabilidade de fases, requisitos, testes e evidências](docs/acceptance/vision_traceability.json).
- [Domínios, operações, recusas e tolerâncias](docs/acceptance/scientific_capabilities.yaml).

F0 explicita contratos e infraestrutura; F13 continua horizonte aberto. Os perfis de software não demonstram autonomia científica geral. Provas formais exigem kernel e auditoria de hipóteses; GPU exige execução identificada; observações e revisão externa não são substituídas por fixtures ou identidade declarada.

Verificar: `python tools/check_roadmap.py` e `python tools/check_public_contracts.py`, na raiz do repositório.
<!-- nabla:contracts:end -->
