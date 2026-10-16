# Fases 3 e 4 — provas, refutação e cenas científicas

Todos os caminhos nomeados nas fases 3 e 4 de `vision.md` têm implementação
funcional, integração pela CLI e testes. O escopo é explícito: proposições
racionais delimitadas, SMT linear e geometria/sistemas dinâmicos planares. Isso
não transforma uma igualdade numérica, uma imagem ou uma busca finita em teorema
universal. A execução dos verificadores é parte do fluxo, não apenas a geração
de arquivos de prova.

## Preparação reproduzível

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[test,formal,graphics]'
bash scripts/setup_formal.sh
```

O script foi exercitado em Linux x86_64. Ele usa Lean **4.34.0**, o toolchain já
fixado no projeto, com download HTTPS e checksum fixo do arquivo de distribuição;
a Mathlib e dependências ficam fixadas por commit em `lean/lake-manifest.json`.
O script não desativa TLS, checksums ou verificações de pacotes. Requer `curl`,
`tar`, `zstd`, Git e Python. Para outras plataformas, instale o toolchain indicado
por `lean/lean-toolchain` e execute `lake build Nabla NablaMath
NablaMath.Examples.FirstProblem` dentro de `lean/`.

O cache binário oficial da Mathlib respondeu 403 nesta máquina pela política de
rede. A instalação foi concluída compilando as dependências necessárias a partir
das fontes fixadas, sem ampliar a rede. A primeira compilação é custosa;
instalações seguintes reutilizam os outputs válidos em `lean/.lake/`.
`MATHLIB_NO_CACHE_ON_UPDATE=1` desativa somente o download automático do cache,
não a verificação ou compilação das provas.

A CLI encontra `lake` no PATH ou no toolchain gerenciado em
`/workspace/.tools/lean/lean-4.34.0-linux/bin/`. Para usar `lake` diretamente:

```bash
export PATH=/workspace/.tools/lean/lean-4.34.0-linux/bin:$PATH
cd lean
lake build Nabla NablaMath NablaMath.Examples.FirstProblem
```

Os extras são opcionais para os fluxos antigos: `formal` instala Z3 e `graphics`
instala Pillow para o novo raster anotado. O raster v1 anterior continua sem
Pillow. Bibliotecas/CLI antigas foram preservadas.

## Fase 3: arquivos solicitados

| Caminho | Comportamento implementado |
|---|---|
| `formal/lean_bridge.py` | Traduz AST racional e hipóteses para Lean com táticas de lista fechada e identificadores seguros |
| `formal/lean_checker.py` | Executa Lean isolado com limite de tempo/heartbeats; examina axiomas e rejeita traduções alteradas/admissões |
| `formal/smt_bridge.py` | Consultas Z3 QF_LRA, consistência de hipóteses, prova UNSAT, modelos racionais reexecutados e estados de falha |
| `formal/translation_review.py` | Regenera a tradução para conferir AST, variáveis e domínio; distingue revisão estrutural de revisão humana |
| `falsifier/search.py` | Busca limitada existente mais relatório reproduzível de investigação, incluindo ausência de evidência e limites |
| `falsifier/shrink.py` | Reduz testemunhos em grade inteira preservando o tipo de falha e informa se a minimalidade foi estabelecida no domínio |
| `verify/certificate.py` | Mantém certificados exatos v1; acrescenta certificados Lean/SMT conferidos por nova execução do verificador |
| `lean/Nabla/` | Bibliotecas `Algebra.lean`, `Geometry.lean`, `Certificates.lean` e módulo raiz `lean/Nabla.lean`, compilados de fato |

`formal/statement.py` acrescenta o contrato compartilhado `FormalStatement` e
`Predicate`: igualdade, desigualdades e hipóteses sobre racionais, com condições
explícitas de definição das expressões. Exemplos de propriedades provadas em
Lean incluem distributividade, cancelamento condicionado, implicação linear,
equidistância do ponto médio e Pitágoras sob ortogonalidade.

### Provar, refutar e conferir recibos

```bash
.venv/bin/nabla prove '(x+x)/x' '2' --output .nabla/prova-nova.json
.venv/bin/nabla check-formal .nabla/prova-nova.json

.venv/bin/nabla prove 'x*x' '0' --relation ge --strategy nlinarith
.venv/bin/nabla prove 'x' '2*x' --relation le --assumption 'x >= 0' --backend smt
.venv/bin/nabla prove 'x+1' 'x' --backend smt --output .nabla/refutacao-nova.json
```

O último comando retorna 1 e salva um contraexemplo racional, em vez de declarar
uma prova. Os destinos de recibo devem ser novos. `check-formal` informa a
validade do recibo, o estado registrado, se a meta foi estabelecida e se houve
prova Lean. Um recibo de contraexemplo válido não significa que a meta era verdadeira.

Condições de domínio são inferidas de **ambos os lados e das hipóteses**. Assim,
`x/x = 1` é formalizado sob `x ≠ 0`; a divisão totalizada de Lean não apaga a
singularidade do objeto original. Potências não positivas também preservam a
condição sobre a base, conforme a semântica do núcleo. A API legada de tradução
universal passou a preservar essas mesmas obrigações.

O certificado contém AST original, hipóteses/obrigações, identidade do enunciado,
tradução Lean legível com correspondência de variáveis quando aplicável, hash da
fonte, estratégia e recibo do backend. O verificador regenera a fonte e executa
novamente o backend: um campo `verified=true` ou um hash recalculado não bastam.
Reexecutar requer o respectivo toolchain/backend instalado.

```python
from nablamath.formal import FormalStatement, translate_statement, check_lean

statement = FormalStatement.equality('(x+x)/x', '2')
translation = translate_statement(statement)
print(translation.source)  # inclui a hipótese x != 0
result = check_lean(translation, project='lean')
assert result.verified
```

### Fronteiras de confiança e estados

- **Lean:** `formal_proof=true` apenas após compilação bem-sucedida e inspeção dos
  axiomas do teorema. `sorry`, `admit`, fontes editadas e axiomas desconhecidos não
  entram no fluxo aceito. São permitidos os axiomas padrão da biblioteca:
  `propext`, `Classical.choice` e `Quot.sound`. Não há afirmação de prova sem axiomas.
- **SMT:** o fragmento é aritmética linear racional quantifier-free, com
  multiplicação por constantes e divisão por constante não nula. Produtos de
  variáveis e denominadores variáveis retornam `unsupported`. UNSAT prova a
  implicação dentro desse fragmento pelo Z3; o recibo continua com
  `formal_proof=false`, distinguindo esse resultado da prova no kernel Lean.
  A prova textual do solver é retida, e modelos SAT são conferidos pela avaliação
  racional do núcleo. Os racionais e reais têm a mesma satisfatibilidade para o
  fragmento linear com coeficientes racionais usado aqui.
- **Hipóteses:** o SMT rejeita uma conclusão meramente vacuosa como
  `inconsistent_assumptions`. Uma prova Lean de uma implicação verifica a
  implicação; não estabelece por si só consistência ou aplicabilidade científica
  das hipóteses.
- **Revisão:** a revisão automática verifica correspondência estrutural entre
  pergunta tipada e fonte. O registro humano anterior `TranslationReview` continua
  disponível; revisão científica humana não é simulada automaticamente.
- **Falhas:** `failed`, `timeout`, `unavailable`, `translation_rejected`,
  `rejected_axioms`, `unknown` e `unsupported` são resultados explícitos. Uma
  tática que não encontra prova não refuta o enunciado. Timeouts encerram o grupo
  de processos criado para o checker.

### Contraexemplos e redução

```bash
.venv/bin/nabla falsify 'x*x' 'x' --radius 4 --shrink --output .nabla/busca-nova.json
.venv/bin/nabla shrink 'x*x' 'x' --assignment '{"x":12}'
.venv/bin/nabla shrink 'x/x' '1' --assignment '{"x":0}'
```

O redutor só aceita um testemunho que realmente falha na reexecução. Ele preserva
`counterexample` versus `domain_counterexample`. A enumeração por norma L1 pode
certificar um testemunho mínimo na caixa inteira determinada pelo testemunho
original; não promete mínimo entre todos os racionais ou conjecturas. Se o
orçamento acabar, preserva um testemunho válido e marca a minimalidade como não
estabelecida. Não encontrar contraexemplo em domínio finito nunca vira prova.

## Fase 4: arquivos solicitados

| Caminho | Comportamento implementado |
|---|---|
| `graphics/scene_graph.py` | Cena v2 imutável com pontos nomeados, segmentos, círculos, curvas, vetores, relações e modelo; cena v1 preservada |
| `graphics/geometry_constraints.py` | Relações tipadas com aridade, referências e valores exatos |
| `graphics/coordinate_system.py` | Transformação racional de coordenadas, unidades, viewport e preservação de proporções |
| `graphics/svg_renderer.py` | SVG v1/v2, textos escapados, modelo exato e layout em metadados |
| `graphics/raster_renderer.py` | PNG v1/v2 com as mesmas primitivas, rótulos e metadados; Pillow apenas para v2 |
| `graphics/layout.py` | Grade/eixos, clipping, transformações comuns aos dois backends e rótulos determinísticos com alertas de colisão |
| `forge/constructors/geometry.py` | Construção inversa de triângulo retângulo, paralelogramo e circuncírculo, com rotação racional e relações verificáveis |
| `verify/geometry.py` | Conferência racional de cada relação e de segmentos não degenerados, independente da aparência dos pixels |

`graphics/sampling.py` liga funções/campos/trajetórias aos respectivos modelos.
`graphics/artifacts.py` salva e revalida bundles editáveis completos.

```bash
.venv/bin/nabla diagram .nabla/triangulo-novo --kind right_triangle --seed 42
.venv/bin/nabla diagram .nabla/paralelogramo-novo --kind parallelogram
.venv/bin/nabla diagram .nabla/circulo-novo --kind circumcircle
.venv/bin/nabla diagram .nabla/curva-nova --kind function --function '1/(x-1/3)'
.venv/bin/nabla diagram .nabla/campo-novo --kind vector_field --dx=-y --dy=x
.venv/bin/nabla diagram .nabla/fase-nova --kind phase_portrait --dx=y --dy=-x --steps 300
.venv/bin/nabla check-diagram .nabla/triangulo-novo
```

Cada diretório novo contém `scene.json`, `scene.svg`, `scene.png`,
`verification.json` e `manifest.json`. A revalidação confere hashes, reconstrói o
modelo declarado, recalcula as relações e renderiza novamente os dois formatos.
Alterar uma figura ou coordenada e recalcular somente o hash não basta.

### Relações, amostras e edição

As relações incluem coincidência/distinção, colinearidade/não colinearidade,
paralelismo, perpendicularidade, igualdade de distâncias, distância quadrada,
pertencimento a círculo, ponto médio e orientação. As comparações são exatas,
sem usar tolerância de pixels como prova. O raio é guardado ao quadrado para não
introduzir irracionais no contrato; o círculo desenhado é uma aproximação
poligonal de 128 segmentos explicitamente identificada no layout.

As cenas geométricas preservam proporções por padrão. Gráficos de função podem
usar escalas independentes declaradas, com limites/unidades nos eixos. Curvas
são amostras: intervalos em que não se consegue excluir zero das obrigações de
domínio por aritmética intervalar conservadora são interrompidos, inclusive
quando um polo não coincide com a grade. Isso pode deixar lacunas conservadoras;
não desenha continuidade garantida através de uma singularidade.

Campos retêm o vetor exato de cada amostra e registram a normalização usada
somente para o comprimento visual da seta. Retratos de fase usam RK4 em ponto
flutuante, guardam equações, condições iniciais, duração, passos e método, e são
rotulados como trajetórias numéricas. Isso não é validação experimental nem
certificado de erro global da integração.

O JSON é um objeto editável, não uma imagem usada como fonte de verdade.
`GeometryScene.from_data` reconstrói as primitivas e verifica o contrato. Uma
cena gerada mantém uma receita reproduzível: alterar coordenadas sem alterar essa
receita será corretamente identificado como divergência. Para uma edição manual,
use `dataclasses.replace(scene, ..., model_json='{}')`, atualize os pontos e as
relações desejadas e exporte novamente; as relações continuam sendo conferidas,
e o recibo marca a origem como cena autoral em vez de reprodução do gerador.

Limites: até 512 pontos/relações, 256 vetores e 20 mil amostras por cena; imagens
entre 128 e 2048 pixels por eixo. Rótulos seguem layout determinístico; colisões
não resolvidas são registradas, não ocultadas como se não existissem.
Construções gerais de geometria euclidiana e todos os possíveis sistemas
científicos não são prometidos pelo recorte implementado.

## Validação executada

- Lean 4.34.0 instalado e dependências de táticas compiladas de fontes fixadas.
- Bibliotecas `Nabla`, `NablaMath` e exemplo `FirstProblem` compilados de fato.
- Provas numéricas, polinomiais, condicionais, lineares e de não negatividade
  verificadas no kernel; igualdade falsa rejeitada; certificados Lean reexecutados.
- Z3 executado em consultas UNSAT/SAT, inconsistência e fragmentos não suportados;
  testemunhos racionais reavaliados pelo núcleo.
- Construções geométricas exercitadas em três tamanhos e três sementes por tipo;
  relações exatas, limites, metadados, clipping e adulteração testados.
- PNGs do triângulo e do retrato de fase inspecionados visualmente; testes também
  conferem pixels de pontos, conteúdo não vazio, metadados SVG/PNG e determinismo.

Testes: `tests/test_phase3_formal.py`, `tests/test_phase4_graphics.py` e regressões
existentes. A CI Lean passou a compilar a nova biblioteca e executar esses fluxos.
O bundle `math.txt` inclui as fontes canônicas e exclui dependências de
`lean/.lake/`; seus hashes/índice foram regenerados pela ferramenta do projeto.
