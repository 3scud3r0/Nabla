# Ecossistema científico rastreável

A implementação segue o layout real `src/nablamath`. Os novos caminhos reutilizam
os motores existentes e acrescentam operações executáveis, bibliotecas opcionais
e transportes explícitos. O catálogo passa de 69 para **103 operações**. A CLI,
o desktop e os notebooks usam a mesma `CalculationSession`.

## Instalação e execução

```bash
python -m pip install -e '.[test]'
nabla calc beta_binomial --arguments '{"successes":2,"trials":3}'
nabla calc tensor --arguments '{"kind":"matmul","values":[[1,2]],"other":[[3],[4]]}'
nabla calc autograd --arguments '{"inputs":{"x":3},"nodes":[{"op":"input","name":"x"},{"op":"multiply","args":[0,0]}],"output":1}'
python examples/science/reproduce.py .nabla/ecosystem-demo
```

O último comando compara todas as 103 operações com referências explícitas,
persiste e reexecuta um notebook, e compara os recibos da CLI e do servidor HTTP.

| Caminho | Implementação e limites |
|---|---|
| `calc/session.py`, `calc/receipt.py`, `calc/catalog.py` | Sessão existente, catálogo aditivo e recibos canônicos SHA-256. Recibos de cálculo têm replay fechado; observações externas declaram `replayable=false`. |
| `ops/linear_algebra.py`, `ops/calculus.py`, `ops/ode.py`, `ops/pde.py` | Adaptadores dos motores existentes: racionais, quadratura certificada, EDO fixa/adaptativa e calor FTCS com condição de estabilidade. |
| `ops/tensor_math.py`, `ops/autograd.py` | Tensor N-D de referência com broadcasting, reduções, reshape, transposição e matmul 2D; DAG escalar com até 256 nós e 32 entradas, sem `eval`. Limite de 10.000 elementos por operação de catálogo. |
| `ops/mcmc.py` | Metropolis-Hastings com densidade logarítmica fornecida por código confiável; catálogo oferece normal univariada. Seed obrigatório por contrato, padrão 0; burn-in e thinning explícitos. Convergência não é inferida da taxa de aceitação. |
| `ops/bayesian_inference.py` | Bayes finito e posterior Beta-Binomial exata, com hipótese Bernoulli iid e parâmetros positivos. |
| `ops/convex_optimization.py` | SciPy HiGHS LP/MILP com restrições e resíduo de viabilidade; L-BFGS-B para funções não lineares confiáveis. Instalar `.[scipy]`; API Python opcional, fora do catálogo sem dependências. Solução local não implica ótimo global. |
| `data/distributed_dataframe.py` | Partições JSON imutáveis, projeção, soma e map com proveniência. Threads locais por padrão ou executor explícito, inclusive `distributed.Client`. Snapshot limitado a 16 MiB por lote; armazenamento externo e streaming permanecem responsabilidade do chamador. |
| `domain/bioinformatics.py` | Needleman-Wunsch global com penalidade linear de gaps, desempate determinístico e conteúdo GC para DNA sem ambiguidades; até um milhão de células de alinhamento. |
| `domain/geospatial.py` | Haversine em esfera de raio médio, conversões WGS84/Web Mercator e NDVI com nodata. Distância em metros, coordenadas em graus; não inclui geodésia elipsoidal nem pipelines completos de satélite. |
| `domain/quantum.py` | Vetores de estado até 12 qubits, X/Y/Z/H/S/T/RZ/CX, amostragem com seed, densidade pura até 8 qubits e canais de Kraus com validação de positividade e traço. Ângulos em radianos; qubit 0 é o mais significativo. |
| `artifacts/bundle.py`, `artifacts/notebook.py` | Bundles JSON de recibos, provas e datasets, criação exclusiva e verificação; notebook preserva a cadeia de hashes e o replay existente. Anexos de prova exigem verificação própria. |
| `formal/smt_verifier.py`, `server/desktop.py`, `cli/main.py` | Caminhos públicos para implementações já existentes; `nabla`, `python -m nablamath.cli` e `from nablamath.cli import main` continuam disponíveis. |

Os limites são contratos de software, não cobertura universal de cada disciplina.
Seeds permitem repetir o algoritmo no mesmo runtime; versões, hardware e kernels
externos podem alterar resultados em ponto flutuante.

## Interoperabilidade e extensões

Instalar `.[interop]` habilita Pandas, Polars e NumPy. `compat.pandas_bridge.to_numpy`
retorna `ArrayView(array, owner, copied)` e recusa cópias por padrão; a view é
somente leitura, mas alterações no proprietário ainda podem ser observadas.
`to_tensor` e `from_tensor` copiam, pois o tensor de referência mantém floats
Python. Não há promessa de zero-copy para uma representação incompatível.

```python
from nablamath.compat.pandas_bridge import to_numpy, to_tensor
view = to_numpy(frame, allow_copy=False)
tensor = to_tensor(frame, requires_grad=True)
```

Instalar `.[torch]` habilita `compat.pytorch_bridge.trace_execution(sink=...)`:
o decorator registra inputs/outputs, dtype, device, versão e operadores executados,
mantendo o tensor retornado e seu grafo de gradientes. Tensores reais densos com
até 100.000 elementos são aceitos; parâmetros escondidos em closures e estados
aleatórios externos não tornam a observação reexecutável.

```python
from nablamath.compat.pytorch_bridge import trace_execution
records = []
@trace_execution(sink=records.append)
def loss(x):
    return (x*x).sum()
```

A extensão Jupyter é um pacote instalável separado:

```bash
python -m pip install -e plugins/jupyter_nabla
```

```python
%load_ext jupyter_nabla
%nabla beta_binomial {"successes":2,"trials":3}
```

```python
%%nabla_trace x y
y = x*x
```

`%%nabla_trace` executa uma célula normal com os privilégios do notebook e captura
somente as variáveis listadas. Erros não geram um recibo de sucesso.
`_nabla_last_receipt` e `_nabla_receipts` guardam os resultados da sessão.

Em `plugins/vscode_nabla`, executar `npm ci && npm test` compila a extensão.
No Extension Development Host do VS Code/Positron, passe o mouse sobre um hash
presente no documento: o preview lê `.nabla/receipts/<hash>.json` no workspace.
O comando **Nabla: Open Receipt** abre um JSON selecionado. Requer workspace
confiável; não executa código e declara que o preview não verifica a matemática.

## Aceleração e clusters

`backends.cuda_dispatcher.CudaDispatcher` usa CuPy e uma GPU real; instalar
`.[cuda12]` e o driver NVIDIA. `matmul` e `diffuse(initial, ratio=..., steps=...)`
retornam observações com device e dtype. Difusão 1D exige fronteiras zero e
`0 <= alpha*dt/dx² <= 0.5`. Ausência de CUDA produz erro explícito.

`backends.xla_compiler.XLACompiler` usa JAX/XLA (`.[accelerate]`) para callables
confiáveis; `compile_ir` reaproveita o compilador IR existente. O recibo identifica
a plataforma realmente usada e a configuração x64. CPU pode ser uma plataforma
XLA válida; isso não constitui evidência de GPU/TPU.

`hpc.mpi_cluster.MPICluster` requer `.[mpi]` e um runtime MPI:

```python
from nablamath.hpc.mpi_cluster import MPICluster
cluster = MPICluster()
result = cluster.map(abs, [-3, 1, -2] if cluster.comm.Get_rank() == 0 else None,
                     operation="absolute")
if result is not None:  # apenas o rank root recebe o agregado
    print(result)
```

Todos os ranks chamam `map`; os dados são particionados por índice. O root
reordena os resultados e inclui recibos de cada rank no agregado. Erros Python
são propagados coletivamente; falha física de um rank depende da política MPI.
Não há alegação de ganho de desempenho sem benchmark do hardware utilizado.

## IA e MCP

`ai.agent_tools.tool_schemas()` gera JSON Schema a partir do catálogo instalado,
com campos obrigatórios, tipos JSON e recusa de argumentos desconhecidos.
Campos sobrecarregados usam o contrato JSON recursivo e a validação de domínio
da operação. `openai_tools()` adapta o envelope para Function Calling.
`AgentTools` valida schemas e permissões e executa somente operações registradas
em processos encerráveis, com timeout, limites de bytes e quantidade de chamadas.

```bash
python -m pip install -e '.[mcp,formal]'
nabla-mcp
# Alternativa: python -m nablamath.ai.mcp_server
```

Configuração de um cliente MCP:

```json
{"mcpServers":{"nabla":{"command":"nabla-mcp","args":[]}}}
```

O servidor usa o SDK oficial e transporte stdio; oferece listagem e execução das
103 operações. Por conexão, o padrão permite até 100 chamadas de até 10 segundos.
Não oferece shell ou execução de Python enviado pelo cliente.

`ai.sandbox_verifier.verify_claim` recebe `FormalStatement`, verifica no fragmento
racional linear QF_LRA e retorna `supported_in_fragment`, `refuted` ou `unverified`.
Contraexemplos são reavaliados com racionais. Fragmento não suportado, hipóteses
inconsistentes, timeout e solver indisponível permanecem não verificados. A API
não interpreta texto livre, não é um sandbox de SO e não substitui o kernel Lean.

## Federação e claims

`federation.crypto_registry` oferece ECDSA P-256/SHA-256 com chaves públicas
explicitamente fixadas por laboratório e revogação irreversível no registro.
Chaves privadas permanecem com o chamador. O protocolo Ed25519 existente continua
separado e compatível. Assinatura autentica a chave fixada, não a verdade científica.

`federation.p2p_node.P2PNode` persiste recibos assinados, valida assinatura e hash,
e expõe GET/POST autenticados por bearer token. `make_server()` escuta loopback por
padrão; `fetch()` contata somente o endpoint fornecido. Não há descoberta ou
publicação automática. Para pares remotos, usar HTTPS e proteção operacional
adequada do serviço. Chaves revogadas deixam de passar na leitura.

`federation.ipfs_storage.IPFSStorage` usa a API HTTP de um daemon IPFS explicitado,
com blocos raw CIDv1/SHA-256 de até 16 MiB. Upload e download recalculam o CID
localmente e recusam conteúdo divergente ou redirecionamentos. O conector não
implica disponibilidade permanente nem privacidade na rede IPFS.

`federation.claims.ClaimRegistry` mantém eventos assinados de proposição,
refutação e retirada. Refutar exige atribuição racional completa que satisfaça
as hipóteses e torne a conclusão falsa; um texto de discordância não é aceito
como contraexemplo. Somente o autor pode retirar a proposição. Eventos e
relações podem ser exportados/recarregados, com assinaturas revalidadas.

## Verificação

```bash
python -m pytest -q tests/test_ecosystem_science.py tests/test_ecosystem_integrations.py tests/test_ecosystem_ai.py tests/test_ecosystem_federation.py
python tools/vision_readiness.py
```

Os testes opcionais informam dependências/hardware ausentes como skips. Verificar
GPU real, TPU, múltiplas máquinas e daemon IPFS exige a infraestrutura específica.
O relatório da visão preserva os 213 critérios originais e suas pendências;
testes locais verdes não promovem requisitos à aceitação científica integral.
