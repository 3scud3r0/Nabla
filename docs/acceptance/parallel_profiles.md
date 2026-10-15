# Perfis implementados em paralelo — contratos e limites

Seis agentes trabalharam em paralelo em frentes separadas, com revisões cruzadas
de código e integração pelo agente principal. Isso é revisão de engenharia por
agentes, não revisão científica externa, aprovação institucional ou autenticação
de pessoas. Cada módulo declara um domínio finito; não extrapolar para a fase inteira.

| Grupo | Implementação executável | Limites essenciais |
|---|---|---|
| Matemática | Lambert W real nos ramos 0/−1, LU racional pivotada e certificado `PA=LU`, primalidade determinística de 64 bits e Pollard rho limitado | aproximações de Lambert W; orçamento de fatoração pode esgotar; matrizes quadradas até ordem 128 |
| Álgebra/lógica | classificação e aritmética de extensões quadráticas sobre ℚ; LRA + funções não interpretadas via Z3 opcional, com modelo SAT rechecado em frações | não atende Galois geral; UNSAT não tem certificado independente |
| Numérico | Euler implícito escalar com Newton e evento terminal interpolado; Poisson 1D Dirichlet O(n) | passo fixo, Jacobiana fornecida; não é solver geral de EDO/EDP |
| Observações | contratos Dirichlet/Neumann/Robin; resíduos e cobertura com conversão SI; movimento com aceleração constante e intervalos | observações e origem fornecidas pelo operador; fixtures não validam fenômenos reais |
| Forge/refutação | composição em blocos, desafios contra respostas antigas, calibração por recursos, índice semântico local, propriedades com contraexemplos e replay | famílias/transformações declaradas; corpus local não estabelece novidade mundial |
| Experimentos/agentes | planos declarativos, ledger de aprovações com CAS e revogação, avaliação offline de segurança e checkpoints de projetos longos | identidade fornecida pelo chamador; sem sandbox de código arbitrário ou autorização externa |
| Workers | executor racional com limite semântico, cotas e cancelamento nas fronteiras; adaptador de lease SQLite; contadores agregados | prazos cooperativos, sem interrupção de cálculo já iniciado ou isolamento do sistema operacional |
| Rede | Ed25519 vinculado a domínio/destinatário/nonce/tempo, rotação/revogação de chaves fixadas, identidade consentida, quarentena e reputação limitada | estado local em memória; sem prova de identidade real, resistência a Sybil ou rede inter-host validada |
| Revisão/conhecimento | revisão editorial por versão/evidência, protocolos de replicação, novidade relativa ao corpus, dificuldade e currículo vinculados a recibos | nomes/afiliações declarados; não há revisão humana real nem replicação externa executada |
| SDKs | clientes Python e TypeScript para a API do coordenador, com limites de resposta, timeout e bloqueio de redirecionamento | distribuição como fonte; TypeScript foi executado no Node 24; runtimes sem suporte nativo ignoram esse teste explicitamente |
| Recursos | cinco perfis versionados e reserva cooperativa concorrente de CPU/memória/VRAM/tarefas | tetos declarados, não hardware detectado ou limite imposto pelo kernel; duração é admissão, não hard timeout |
| Distribuição | verificação de caminhos, tamanho e SHA-256 de cada entrada de wheel contra RECORD, sem extrair/executar | integridade interna não autentica publicador, dependências ou segurança do código |

Os perfis em `configs/profiles/*.yaml` usam JSON, subconjunto de YAML, para
dispensar dependência de parser. `ResourceProfile.load` os valida e
`ResourceReservations.reserve` controla reservas cooperativas, inclusive liberação
após exceção. Escolher um perfil GPU/HPC não cria hardware ou acesso a um cluster.

## Revisões e regressões

As revisões cruzadas encontraram e corrigiram: CAS concorrente de aprovações,
materialização de geradores antes de validar limites, resíduo de Lambert W próximo
do ponto de ramificação, última atualização de Newton, tempos não representáveis,
crescimento aritmético no worker e assinaturas com tamanho não limitado. Foram
adicionados testes de regressão; não se aceitou o primeiro resultado positivo
como comprovação suficiente dos contratos.

## Automação

- `security.yml`: contratos de assinatura/aprovação e integridade do wheel;
  não é auditoria completa de vulnerabilidades, dependências ou segredos.
- `full-integration.yml`: replay integrado e casos de falha com evidência arquivada.
- `scientific-benchmarks.yml`: referências analíticas/NIST finitas em agenda UTC;
  não constitui campanha experimental externa ou medição de GPU.
- `release-attestation.yml`: define build e atestado de proveniência para evento
  de release publicada. Não houve publicação/atestado de release nesta tarefa.

As actions novas são fixadas por SHA consultado nas tags dos repositórios oficiais.
Executar testes locais não valida a execução desses workflows no GitHub.

## Reproduzir

```sh
OPENBLAS_NUM_THREADS=1 python -m pytest -q
python tools/check_roadmap.py
python tools/check_policy_links.py
python tools/build_math_bundle.py --check
python -m pip wheel --no-deps --wheel-dir .nabla/wheels .
python tools/verify_wheel.py .nabla/wheels/nablamath-0.1.0a1-py3-none-any.whl
```

Lean/Mathlib e GPU não estão disponíveis na instância local. Os testes opcionais
correspondentes não podem ser substituídos por flags de sucesso. Permanecem tanto
software ainda não implementado quanto critérios externos sem comprovação no
roteiro completo. A matriz de 213 requisitos distingue esses itens dos perfis acima.
