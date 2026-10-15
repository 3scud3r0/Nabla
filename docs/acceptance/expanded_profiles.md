# Perfis delimitados de dados, evidência e coordenação v1

Estes módulos ampliam o roteiro sem declarar aceite integral de fases ou
validação científica externa. Não executam código de modelos ou de participantes.

| Capacidade | Contrato e limites | Verificação |
|---|---|---|
| Intervalos | `numeric/intervals.py` reutiliza `RationalInterval`; subtração, quadrado, interseção e raiz não negativa com limites por grade decimal exata, 1–32 dígitos | desigualdades racionais em 100 casos, fronteiras e quadrados perfeitos |
| Incerteza | `core/uncertainty.py` propaga intervalos conservadores com unidades SI e conversões exatas | distância/tempo, conversão km→m, dependência e divisor contendo zero |
| Calibração | `evaluation/calibration.py` calcula bins de confiabilidade binária, Brier e ECE em racionais; até 10.000 observações e 100 bins | valores analíticos, bins vazios, p=0/1, entradas inválidas e adulteração |
| Ablações | `evaluation/ablation.py` compara 2–32 variantes no mesmo protocolo congelado, sem seleção automática | comparação pareada e replay de relatórios |
| Monitoramento | `evolution/longitudinal_monitor.py` reexecuta até 128 avaliações de snapshots distintos em passos crescentes; sinaliza queda acima do limite declarado | regressão/recuperação, ordem e relatório falsificado |
| Linhagem | `knowledge/lineage.py` valida DAG imutável, até 4.096 nós, 256 pais/nó e 32.768 vínculos, sujeito também ao orçamento JSON | cadeia de 1.100 nós sem recursão, ciclo, pai ausente e duplicata |
| Retrações | `knowledge/retraction_index.py` propaga alertas a descendentes de alvos declarados; até 1.024 recibos | conjunto exato de afetados, preservação de conteúdo e adulteração |
| Referências editoriais | `documents/reference_graph.py` resolve IDs explícitos das seções contra nós do artefato e registra o documento no DAG | referência existente, ausente e duplicada |
| Corpus | `datasets/corpus_registry.py` registra manifests imutáveis com split, licença, origem e 1–10.000 hashes; verificação opcional dos bytes de todos os registros | round-trip, adulteração e direitos/origem obrigatórios |
| Mistura | `training/mixture.py` aloca quotas por maiores restos com pesos racionais positivos; amostra sem reposição, seed explícito, até 128 fontes e 10.000 seleções | quotas conhecidas, determinismo independente da ordem, duplicação entre fontes, split e capacidade |
| Snapshot | `training/snapshot.py` guarda pesos e datasets como bytes opacos em blobs verificados; até 64 MiB/blob e 256 MiB/snapshot; manifesto publicado por último | idempotência, corrupção, versão de pesos e pais |
| Linhagem de treino | `training/lineage.py` expande snapshots referenciados e verifica o DAG completo | cadeia pai/filho e integridade dos datasets |
| Recursos | `training/compute_accounting.py` registra duração, pico de memória e energia opcional fornecidos pelo operador | valores inválidos recusados; energia ausente permanece ausente |
| Recibos | `verification/consensus.py` conta acordo com resultado previamente verificado, sem votos repetidos da mesma etiqueta | quorum, dissenso e duplicatas; integrado ao coordenador local |

Os orçamentos JSON compartilhados também limitam manifests e relatórios: 1 MB,
profundidade 32 e 20.000 valores; limites combinados podem ser atingidos antes
dos máximos individuais da tabela. Limites racionais do núcleo continuam valendo: entradas exatas de até 256 bits;
operações que ultrapassam a representação suportada falham, não retornam um limite
inventado. Intervalos não são distribuições ou intervalos de confiança, e repetir
uma variável pode alargar um enclosure conservador. Calibração descreve somente
as observações fornecidas. Variantes de ablação, medições, licenças, identidades,
linhagem e retrações são declarações, sem autenticação ou revisão externa.
Snapshots nunca desserializam pickle ou executam pesos. Uma falha pode deixar
blobs sem referência, mas não publica um manifesto incompleto. Verifique toda a
linhagem para auditar ancestrais. Misturas detectam hashes repetidos, não equivalência
semântica oculta, e não resolvem compatibilidade jurídica entre licenças.

## Coordenador HTTP local

`CoordinatorService` agora aceita `http_permissions={participante: {capacidades}}`
e `max_pending_tasks` (padrão 1.000; máximo 10.000). A ausência de configuração
nega todas as operações HTTP de tarefas. O segredo HMAC é fornecido pelo operador
em execução; nunca deve ser versionado. As permissões HTTP são atribuídas pelo
servidor. O método Python direto é uma interface de operador confiável.

| Método/caminho | Capacidade | JSON |
|---|---|---|
| `GET /health` | público | sem corpo |
| `POST /tasks` | `create` | `expression`, `values` |
| `GET /tasks/{id}` | `read` | sem corpo |
| `POST /leases` | `lease` | `seconds` |
| `POST /tasks/{id}/heartbeat` | `heartbeat` | `seconds` |
| `POST /tasks/{id}/submit` | `submit` | `result_id` |
| `POST /tasks/{id}/cancel` | `cancel` | objeto vazio |

Envie `X-Nabla-Participant` e `Authorization: Bearer <token>`. Capacidade `cancel`
é administrativa para a fila inteira. `POST` exige um único `Content-Length`,
até 64 KiB; transferência chunked não é suportada. JSON duplicado/não finito e
campos desconhecidos são recusados. A expressão usa os limites semânticos do
núcleo, expoentes entre -16 e 16 e bindings racionais; não aceita Python.
Erros de autenticação/permissão, rota, tamanho e contrato retornam 401/403, 404,
413 e 400, respectivamente. Cota esgotada é erro de contrato 400 nesta versão.

SQLite serializa aquisição e cotas. Leases de 1–3.600 segundos podem ser renovados
antes de expirar; o mesmo worker pode recuperar um lease expirado. Uma resposta
já aceita pode ser reenviada sem novo voto. Cancelar impede heartbeat/submissão;
tarefa já verificada não pode ser cancelada. O resultado é reexecutado localmente
antes de contar duas etiquetas distintas de worker. Isso não prova duas pessoas
independentes nem fornece resistência a Sybil. Recálculo determinístico permite
retries; não há fencing para efeitos externos, pois esses efeitos não são aceitos.

O log encadeado tem append protegido contra concorrência e verifica também o
hash anterior registrado. Ele permanece em memória: não é log durável, serviço
de consenso distribuído ou telemetria anonimizada. O servidor inicia em loopback;
os testes abrem conexões HTTP reais e encerram o processo de servidor que criam.
Não há implantação inter-host, TLS de produção ou rede federada nesta entrega.

## Reproduzir o conjunto

Na raiz, com o ambiente Python ativado, use destino novo:

```sh
python tools/expanded_scientific_cycle.py .nabla/expanded-cycle
python -m pytest -q tests/test_roadmap_expansion.py tests/test_evidence_integration_expansion.py tests/integration/test_coordinator_api.py tests/integration/test_global_scientific_cycle.py
python tools/check_roadmap.py
python tools/build_math_bundle.py --check
```

O ciclo grava artefato, referências editoriais, corpora, mistura, snapshots,
linhagem, retrações, protocolo/submissões/ablações, monitoramento, calibração,
simulação de decaimento e propagação de incerteza. A integração reexecuta vínculos
e compara a simulação com `exp(-1)`. Pesos e respostas são fixtures declaradas:
nenhum treinamento, descoberta externa, revisão humana real ou medição física
foi demonstrado. As lacunas F7–F13 continuam explícitas nos relatórios.
