# Perfis de entrega — 16 de outubro de 2026

Estes contratos ampliam implementação e testes locais. Não substituem os critérios
originais dos 213 requisitos, revisão independente ou validação experimental.
A matriz original continua com 213 requisitos parciais.

| Perfil | Implementação | Verificação e fronteira |
|---|---|---|
| Álgebra exata | `math/polynomials/{real_roots,exact_algebra,finite_field}.py`; `math/linear_algebra/{exact_spectral,invariant_decomposition}.py` | Sturm, multiplicidades, Bézout/CRT, resultantes, fatoração finita, decomposições espectrais; certificados e comparação diferencial com SymPy. Orçamentos finitos explícitos. |
| Diferenciação matricial | `autodiff/linalg.py` | Solve, inversa, determinante, logdet, Cholesky e perda gaussiana SPD; derivadas e Hessianas com matrizes de ordem até 8. |
| Conservação 2D | `physics/fluids/shallow_water_2d.py`; `numeric/{transport_2d,reaction_diffusion_2d}.py` | Fluxos compartilhados, balanços de fronteira, CFL, positividade e reação linear rígida. Água rasa estritamente molhada, fundo plano; sem validação experimental. |
| Aprendizado simbólico | `training/{symbolic_beam,symbolic_protocol,sparse_symbolic,symbolic_stability,symbolic_derivatives,forge_symbolic}.py` | Gramática fechada, ajuste racional, seleção em validação, reserva durável de teste, ablação e replay. Priors de família declarados; sem inferência de generalização externa. |
| DAG durável | `agents/{durable_dag,dag_contracts,dag_scheduler,dag_replay,dag_recovery,dag_inspection}.py`; `services/worker/dag_executor.py` | Leases com fencing, concorrência SQLite, orçamento, consentimento, revogação, retomada e recursos compartilhados. Ferramentas registradas; não é sandbox de código arbitrário. |
| Federação local | `network/merkle_inventory.py`; `p2p/federation_transport.py`; `services/federation/{inventory,checkpoints,http,access_sessions}.py`; `knowledge/revocation_monitor.py` | Merkle, paginação, HTTP assinado em loopback, cotas, retomada e revogação. Não demonstra WAN ou identidade institucional. |
| Release controlado | `packaging/{signed_release,staged_release}.py` | Ed25519, rotação com limiares, checkpoint externo antirrollback, instalação offline em venv, inventário e ativação recuperável. Chaves de teste; sem publicação real. |
| Revisões de dados | `datasets/{revision_store,revision_quality,revision_release}.py` | Snapshots CAS, linhagem, política de licença declarada, revisão local e exportação atômica. Identidade de revisor e licença não autenticadas externamente. |
| Comparação agrupada | `evaluation/clustered.py` | Perdas racionais pareadas, bootstrap por grupo e randomização; tamanho amostral binomial planejado, sem alegação de ensaios realizados. |
| Ciclo integrado | `pipeline/delivery_cycle.py` | Dados → revisão → release → treino → seleção → teste único → álgebra → conservação → replay imutável. `fully_calibrated_and_ready` permanece falso. |

Todos os caminhos abreviados acima começam em `src/nablamath/`, exceto os
explicitamente iniciados por `services/` e `packaging/`.

## Reprodução

```bash
python -m pytest -q tests/test_delivery*20261016.py
python tools/delivery_cycle.py .nabla/delivery-reproduction
# Use o run_id impresso, fixado fora do diretório verificado:
python tools/delivery_cycle.py .nabla/delivery-reproduction --check SHA256_IMPRESSO
```

Escolha um diretório novo: a execução recusa sobrescrever resultados anteriores.
O replay verifica inventário, bytes, compromissos e semântica dos componentes.
O hash fornecido pelo chamador não autentica a identidade do produtor.

A campanha sintética congelada separada obteve 24/24 contra 0/24 na ablação.
Ela usa sementes de teste 958000–958023; testes de desenvolvimento já observaram
957000–957023. A família e a gramática fornecem priors fortes, com componentes
reutilizados entre divisões. O benchmark reservado original de 48 problemas não
foi usado nem teve seu resultado alterado por essa campanha.
