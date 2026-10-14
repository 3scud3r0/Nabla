# NablaMath — roadmap de implementação e critérios de conclusão

**Revisado em:** 24/09/2026 · **Estado geral:** protótipo local funcional; fases F0–F6 abertas.  
**Site público:** [3scud3r0.github.io/Nabla-Math](https://3scud3r0.github.io/Nabla-Math/) · **Instalador:** [release alpha para Windows](https://github.com/3scud3r0/Nabla/releases).

Este é o plano de trabalho para evoluir o repositório em biblioteca científica assistida por Lean, agentes opcionais, arquivos de pesquisa reproduzíveis e, se houver governança e operação, colaboração distribuída. A presença de um arquivo, teste ou workflow não significa que a fase esteja concluída. `python tools/roadmap_status.py` apenas mostra o checklist declarado; não mede qualidade, validação científica ou operação.

## Como interpretar o estado

- **Implementado em protótipo:** há código e testes locais para um recorte finito.
- **Parcial:** o código existe, mas falta validação independente, robustez ou integração operacional.
- **Pendente:** faltam código, decisão do mantenedor, infraestrutura externa ou evidência.
- **Concluído:** só depois de cumprir todos os critérios de aceite da fase e anexar evidências reproduzíveis.

O projeto não pode concluir “toda a matemática e toda a ciência”: esse escopo não é finito. Cada entrega científica deve nomear uma família de problemas, domínio de validade, fontes de referência e critério de erro. “Prova Lean”, “resultado numérico” e “evidência experimental” são classes diferentes.

## O que já está no repositório

| Área | Estado real hoje | Próximo limite |
|---|---|---|
| Python e CLI | pacote `nablamath` instalável localmente; CLI e aplicativo pessoal em loopback | estabilizar API/versões e testar instalação limpa em matriz de SOs |
| Persistência | SQLite, JSONL, manifesto/hash, importação reexecutável e LaTeX fonte | migrações/backup testados em releases; publicação de PDF depende de TeX instalado |
| Matemática | parser e regras para expressões racionais em subconjunto documentado | ampliar regras com hipóteses e provas gerais; não é CAS geral |
| Lean 4 | Mathlib fixado; exemplos/instâncias passam na CI | tradução bidirecional ainda limitada; auditar fidelidade enunciado→Lean |
| Física | órbita ideal de dois corpos, RK4 e exemplo analítico de Poiseuille | referências independentes reais, estudo de convergência e novos regimes; sem CFD geral |
| Agentes | contratos declarativos, limites/orçamento e worker local simples | sandbox de segurança efetiva e ciclo de trabalho distribuído completo |
| Dataset | schema, deduplicação, splits, cartão, qualidade e exportadores locais | não há snapshot científico público aprovado nem avaliação de ganho em modelos |
| Site | Site estático publicado no GitHub Pages; worker opt-in gera exemplos aritméticos e permite baixá-los em JSONL | não há backend global, upload em tempo real ou contribuição científica do navegador |
| Coordenação | fila SQLite, HMAC e eventos Merkle em protótipo local | `services/coordinator/app.py` expõe apenas `/health`; não é serviço público multiusuário |
| SDKs | parser de frações em C/C++/Rust e workflows de interoperabilidade | não são bindings dos motores científicos completos |

O workflow de publicação Hugging Face é intencionalmente condicional. Sem lote revisado, repositório de destino e segredo configurado, não publica dados.

## Horizonte de capacidades rumo a sistemas superinteligentes

Este mapa é uma decomposição de pesquisa, não uma previsão aceita nem uma promessa de que haverá superinteligência. “Superinteligência” não tem hoje um teste científico universal. O projeto só pode medir marcos intermediários observáveis:

1. **Computação local reproduzível:** já existe para um subconjunto pequeno; ampliar cobertura requer especificações, testes e compatibilidade.
2. **Rigor formal:** expandir provas Lean e medir fidelidade da formalização; o kernel verifica a prova dentro da teoria formal, não a interpretação física nem a escolha da hipótese.
3. **Validação empírica:** comparar modelos a dados independentes, propagar incerteza e preservar resultados negativos.
4. **Descoberta assistida:** agentes podem propor hipóteses e planos; medir novidade, taxa de validação, custo, reprodutibilidade e revisão humana.
5. **Ciclo experimental:** conectar modelos a experimentos/laboratórios autorizados e calibrados; etapa externa ao protótipo atual.
6. **Generalidade e autonomia:** testar transferência entre domínios, robustez, planejamento longo e supervisão; critérios devem ser definidos por avaliadores independentes.
7. **Superinteligência:** horizonte especulativo sem critério consensual. Nenhuma quantidade de arquivos, provas ou compute, isoladamente, demonstra que foi atingida.

No site, cada estágio precisa exibir seu estado real, evidência, limite e próximo bloqueio. Não desenhar uma seta de progresso como se o resultado final fosse inevitável.

## Dependências comuns a todas as fases

1. Decisões documentadas sobre governança, licenças por tipo de conteúdo, revisão científica e resposta a incidentes.
2. CI verde para os arquivos alterados, reprodução local dos comandos e atualização da documentação.
3. Cada formato persistido deve ter versão, migração e fixtures de compatibilidade.
4. Nenhuma credencial ou dado sem direito de redistribuição vai para o repositório, site ou dataset.
5. Agentes geram propostas; verificadores independentes determinam o estado da evidência.

## Fases e trabalho restante

### F0 — Governança, contratos e compatibilidade

**Estado:** parcial. Código MIT, `CONTRIBUTING.md`, `SECURITY.md`, modelos de issue e políticas iniciais já existem; faltam decisões operacionais aprovadas e uma matriz de suporte sustentada por testes.

**Arquivos a atualizar/criar:**

- Atualizar `docs/DECISIONS/README.md`: registrar decisões aprovadas sobre licença do código (MIT já está no `LICENSE`), direitos de contribuições/datasets, política de retirada, mantenedores e custos.
- Atualizar `docs/DATA_GOVERNANCE.md`: separar dados próprios, externos, prompts/trajectórias e saídas formais; definir revisão, retenção, remoção e atribuição.
- Atualizar `docs/THREAT_MODEL.md` e `SECURITY.md`: ameaças do aplicativo local, dependências, upload e futura rede de workers; processo de incidentes e versões suportadas.
- Atualizar `docs/COMPATIBILITY.md`: matriz real de Python/SO/Lean/Mathlib/TeX e links de execuções CI para cada release.
- Criar `docs/RELEASE_POLICY.md`: versionamento semântico, suporte de schemas, depreciação e checklist de publicação.

**Aceite:** decisões sem campos em aberto para a operação que se pretende ativar; política de dados revisada pelos responsáveis; matriz de compatibilidade exercitada em CI. Aprovação de titulares/organização é ação administrativa, não algo que código possa substituir.

### F1 — Produto local instalável e confiável

**Estado:** protótipo funcional; instalador Windows alpha existe. Falta a garantia de instalação limpa/reprodutível e recuperação de dados nas plataformas anunciadas.

**Arquivos a atualizar/criar:**

- Atualizar `pyproject.toml`, `src/nablamath/__init__.py`, `src/nablamath/cli.py` e `docs/COMPATIBILITY.md`: API pública/versionada, comandos e mensagens de erro compatíveis com documentação.
- Atualizar `src/nablamath/store/sqlite.py`, `src/nablamath/storage.py` e `src/nablamath/store/migrations/README.md`; criar `src/nablamath/store/migrations/0001_initial.py` e migrations incrementais: versão do schema, migração transacional, backup e recuperação.
- Atualizar `setup.ps1`, `setup.cmd`, `setup.sh` e `packaging/windows/`: verificar instalação nova e upgrade, sem privilégios silenciosos; assinar o `.exe` quando houver certificado do mantenedor.
- Criar `.github/workflows/install-matrix.yml` e `tests/integration/test_install_upgrade.py`: instalação e upgrade limpos em Windows/Linux e versões Python suportadas.
- Criar `tests/integration/test_backup_restore.py`: backup, restauração e migração sem perda dos registros nem dos hashes.

**Aceite:** um usuário novo instala por pip e pelo instalador, executa o mesmo exemplo e obtém registros/IDs equivalentes; backup e upgrade passam em ambiente limpo. macOS só entra na matriz quando for declarado suportado.

### F2 — Formalização Lean e relatórios auditáveis

**Estado:** Lean/Mathlib compila exemplos limitados; não existe prova geral para todas as regras do parser nem revisão automática confiável da tradução.

**Arquivos a atualizar/criar:**

- Atualizar `src/nablamath/formal/translate.py`, `check.py`, `obligations.py` e `review.py`: tradução tipada para subconjunto declarado, hipóteses obrigatórias, recusa de casos fora do escopo e recibo reprodutível da checagem.
- Atualizar/criar `lean/NablaMath/Algebra/Rules.lean` e módulos por regra, começando por identidades racionais com condições de domínio; não gerar `sorry` em artefato de aceite.
- Atualizar `lean/lakefile.toml`, `lean/lean-toolchain` e `.github/workflows/lean-core.yml`: versões fixas e CI reproduzível.
- Atualizar `src/nablamath/reports/{model.py,latex.py,compile.py}`; criar `tests/reports/test_pdf_build.py`: testar `.tex` e PDF quando TeX existir; preservar fontes, referências, valores, unidades e limites.
- Criar `tests/formal/test_translation_fidelity.py` e atualizar `tests/integration/test_lean_bridge.py`: casos positivos, negativos e semântica de hipóteses revisada.

**Aceite:** para cada regra incluída, enunciado humano e formal comparados, prova geral checada pelo kernel Lean e casos de fronteira negativos; relatório reproduz o recibo. Compilar uma instância numérica não conta como prova da regra universal.

### F3 — Domínios científicos e agentes seguros

**Estado:** exemplos orbitais/fluido ideal e protocolos de agente existem. Os testes de “referência” atuais comparam propriedades internas/solução analítica; ainda não são validação contra observação ou benchmark de engenharia externo.

**Arquivos a atualizar/criar:**

- Atualizar `src/nablamath/physics/orbital/{state.py,dynamics.py,validation.py}` e `tests/science/test_orbital_reference.py`; criar `tests/science/data/README.md` e fixtures versionadas de efemérides com fonte/licença. Comparar com referência independente e declarar sistema, intervalo, tolerância e erro.
- Atualizar `src/nablamath/physics/fluids/{model.py,validation.py}` e `tests/science/test_fluids_reference.py`; adicionar caso(s) de referência externa para regimes explicitamente delimitados. Manter “CFD” fora da descrição enquanto não houver solver e validação apropriados.
- Criar `src/nablamath/physics/units/` se o domínio exigir integração dimensional em todas as fórmulas; hoje a conversão de unidades não garante cobertura completa do motor.
- Atualizar `src/nablamath/agents/{sandbox.py,budget.py,protocol.py,trajectory.py}`: isolamento de processo/contêiner, limites reais de CPU/memória/tempo, cancelamento e trilha sem segredos.
- Criar `benchmarks/tasks/manifest.json`, `benchmarks/run.py`, `benchmarks/evaluate.py` e `benchmarks/results/README.md`: tarefas versionadas, baseline não-IA/IA opcional, custo, taxa de sucesso, novidade e vazamento.
- Atualizar `tests/integration/test_agent_limits.py` e criar `tests/security/test_generated_code_isolation.py`.

**Aceite:** cada domínio tem benchmark de referência independente e estudo de erro/convergência; agentes não executam código fora do sandbox nem excedem cotas; resultados nulos e falhas ficam registráveis. Só declarar suporte ao recorte efetivamente validado.

### F4 — Dataset científico curado e publicação reproduzível

**Estado:** exportação, cartão e publicador opt-in existem; ainda não existe publicação pública confirmada nem experimento demonstrando valor para treino.

**Arquivos a atualizar/criar:**

- Atualizar `src/nablamath/dataset/{schema.py,deduplicate.py,quality.py,splits.py,export.py,licenses.py,cards.py}`: schema estável, famílias matemáticas contra vazamento, Parquet testado, fontes e estados de evidência completos.
- Atualizar `services/publisher/{huggingface.py,manifest.py,cli.py}` e `.github/workflows/dataset-publish.yml`: publicação idempotente, receipts, teste sem escrita e falha fechada.
- Criar `datasets/README.md` e, quando houver lote elegível, `datasets/approved/data.jsonl`, `datasets/approved/data.jsonl.approval.json` e `datasets/approved/data.jsonl.CARD.md`; criar `tests/dataset/test_leakage.py` e `tests/integration/test_publication_receipt.py`.
- Criar `benchmarks/training/{README.md,prepare.py,train_baseline.py,evaluate.py}`: comparação controlada de modelo/dados NablaMath versus baseline, com splits congelados e métricas pré-registradas.
- Atualizar `website/data/status.json` só a partir de manifestos verificados; nunca inventar números de participantes ou amostras.

**Aceite:** snapshot com licença/proveniência por registro, revisão humana, card, hashes, divisão sem vazamento e reprodução independente; publicação real confirmada pelo Hub; estudo de ablação público, inclusive se não mostrar melhoria. A conta HF e o segredo são configuração externa do responsável.

### F5 — Rede global de computação voluntária

**Estado:** protótipos locais de fila/eventos e worker existem; o HTTP atual em `services/coordinator/app.py` fornece somente `/health`. Não há backend público multiusuário, API operacional ou telemetria live.

**Arquivos a atualizar/criar:**

- Ampliar `services/coordinator/app.py` e criar `services/coordinator/api.py`: API versionada para cadastro opt-in, obter lease, enviar resultado, consultar tarefa e pedir remoção; autenticação/escopos em `auth.py`.
- Atualizar `services/coordinator/{scheduler.py,review.py,events.py,snapshots.py,metrics.py}`: leases com expiração, idempotência, cotas, revisão redundante, assinatura, evento de retratação e métricas com definições auditáveis.
- Atualizar `services/coordinator/db/README.md`; criar `services/coordinator/db/schema.sql`, migrations, `deployment/compose.yaml` e `deployment/README.md`: banco de produção, TLS, segredos, backup, restore, retenção e observabilidade.
- Atualizar `services/worker/{agent.py,checkpoint.py}`: cliente remoto autenticado, consentimento explícito, heartbeat, limites locais, atualização segura e cancelamento.
- Criar `.github/workflows/coordinator-ci.yml`, `tests/integration/test_coordinator_api.py`, `tests/integration/test_two_workers.py` e `tests/security/test_coordinator_abuse.py`.
- Atualizar `website/src/{community.js,data.js,explorer.js}` e criar `website/src/api.js`: consumir somente métricas públicas efetivas, com cache e aviso de data de atualização.
- Criar `docs/INCIDENT_RESPONSE.md` e atualizar `docs/OPERATIONS.md`: on-call, abuso, custo, recuperação e suspensão de workers.

**Aceite:** dois computadores distintos recebem trabalho pelo serviço implantado; um terceiro processo verifica/reexecuta; quedas e duplicatas não corrompem dados; auth, rate limits, retirada e backup são testados. A implantação exige domínio/hosting, responsável operacional, política de privacidade e credenciais. “Blockchain” não é requisito: log assinado/Merkle dá integridade verificável, não verdade científica nem consenso global.

### F6 — Interoperabilidade e evidência de utilidade para IA

**Estado:** parsers de fração em C/C++/Rust e testes de protocolo são recortes de interoperabilidade; não são bindings dos cálculos/Lean completos.

**Arquivos a atualizar/criar:**

- Atualizar `protocol/schema/README.md` e `protocol/fixtures/README.md`; criar `protocol/schema/nablamath-record-v1.json` e fixtures de golden records: semântica, precisão, erros, compatibilidade e hashes normativos.
- Ampliar `sdk/c/`, `sdk/cpp/` e `sdk/rust/` com bindings da API estável selecionada; criar `tests/interop/test_cross_language_golden.py` e ampliar `.github/workflows/interop.yml` para comparar os mesmos vetores em cada linguagem.
- Criar `docs/AI_TRAINING_EVALUATION.md` e completar `benchmarks/training/` (F4): protocolo de treino/avaliação, ablação e limitações.
- Atualizar `tools/singlefile/` apenas se houver usuários; gerador deve derivar do pacote e ter teste de equivalência.

**Aceite:** implementações em linguagens suportadas leem/escrevem os mesmos fixtures com resultado idêntico; release reproduzível; benchmark mostra se dados NablaMath ajudam em tarefas pré-registradas. Não assumir benefício recursivo antes de medir.

## Checklist resumido

- [ ] **F0** decisões de governança, release e matriz de compatibilidade aprovadas e exercitadas.
- [ ] **F1** instalação/upgrade/backup testados em máquinas limpas, em todos os SOs declarados.
- [ ] **F2** regras suportadas provadas em geral, tradução revisada e recibo/report reproduzível.
- [ ] **F3** domínios comparados com referências independentes; agentes isolados e limitados; benchmarks versionados.
- [ ] **F4** dados licenciados e sem vazamento, snapshot publicado, avaliação de treino reproduzível.
- [ ] **F5** serviço implantado e seguro, dois workers reais e verificação independente demonstrados.
- [ ] **F6** SDKs interoperáveis para escopo declarado e utilidade do dataset medida contra baseline.

## Ordem recomendada

1. Fechar F0 e os critérios de lançamento antes de expor dados ou workers.
2. Completar F1 junto com os relatórios de bugs de instalação; congelar o schema inicial.
3. Fechar um recorte pequeno de F2 e um domínio F3 com validação externa, sem ampliar escopo prematuramente.
4. Criar o primeiro dataset pequeno em F4 e auditar sua utilidade antes da escala.
5. Implantar F5 somente após autenticação, segurança, política e plano operacional.
6. Priorizar F6 por demanda demonstrada; SDKs de domínio mais amplo e novas áreas são ciclos sucessivos.

## Estimativa e definição de “todas as fases”

Consulte [`docs/ESTIMATIVA_EXECUCAO.md`](ESTIMATIVA_EXECUCAO.md) para o intervalo de esforço. A estimativa é para uma plataforma de escopo limitado, não para cobrir todas as ciências. Uma versão pode declarar **F0–F6 concluídas para um recorte nomeado** quando cada checklist acima tiver evidência, revisão e operação correspondentes; novos domínios continuam como roadmap evolutivo.
