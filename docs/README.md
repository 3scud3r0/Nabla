# Documentação do NablaMath

## Começar e desenvolver

- [Primeira versão local coesa — guia de uso, limites e critérios de aceite](acceptance/COHESIVE_LOCAL_ALPHA.md).

Consulte as operações instaladas com `nabla catalog`; execute qualquer operação declarada com `nabla calc <operação> --arguments '{"campo":"valor"}'`. A interface desktop local usa o mesmo motor do catálogo e mostra recibos de cálculo; o fluxo de expressão/SQLite anterior permanece disponível.

- [Instalação e uso](../README.md), [aplicativo local](DESKTOP.md) e [contribuição](../CONTRIBUTING.md).
- [Estrutura do repositório](architecture/repository-layout.md) e [módulos canônicos](architecture/current-modules.md).
- [Ferramentas de reprodução](../tools/README.md) e [exemplos](../examples/README.md).

## Implementação científica

- [Camadas de execução, MCP/SMT, matemática adicional, GLTF/Manim e Living Papers Typst](SCIENTIFIC_LAYERS.md).
- [Mapa dos 63 ramos MSC 2020 e 22 módulos adicionais](MSC2020_COVERAGE.md).
- [Expansão matemática: módulos, ações e testes escritos sem execução](MATHEMATICAL_EXPANSION.md).
- [Composição científica dos PDFs e demonstrações editoriais](EDITORIAL_DESIGN.md).

- [Laboratório de matemática racional exata](math/EXACT_LABORATORY.md) e [ampliação integrada com 29 operações](math/ADVANCED_EXACT_EXPANSION.md): álgebra polinomial, Sturm, interpolação, álgebra linear, teoria dos números, cadeias e otimização com limites.


| Tema | Guia |
|---|---|
| Calculadora e Forge | [Fases 1–2](phases/PHASES_1_2.md) |
| Provas, refutação e cenas | [Fases 3–4](phases/PHASES_3_4.md) |
| Studio, datasets, simulação e aprendizado | [Fases 5–8](phases/PHASES_5_8.md) |
| Discovery, evolução, disciplinas e conhecimento | [Fases 9–12](phases/PHASES_9_12.md) |
| APIs ampliadas e reprodução integrada | [Perfis de maturidade](PHASES_MATURITY_EXPANSION.md) |
| Simulação de uso laboratorial | [Protocolo e comandos](FRONTIER_LAB_SIMULATION.md) |

## Evidências e limites

- [Benchmark permanente da visão](acceptance/VISION_READINESS.md): comando obrigatório, 213 lacunas e resultados atuais.

- [Entrega integrada de 16/10/2026](audits/DELIVERY_2026_10_16.md) e
  [contratos e reprodução](acceptance/delivery_profiles_20261016.md).

- [Fundamentos P0 e integração](audits/P0_INTEGRATION_2026_10_15.md),
  [perfil racional executável](acceptance/phase_profiles.md) e
  [matriz dos 213 requisitos](acceptance/evidence_matrix.json).
- [Avaliação congelada racional](acceptance/frozen_evaluation.md): baseline fixo,
  auditoria de linhagem e pontuação de submissões declarativas.
- [Perfis ampliados](acceptance/expanded_profiles.md): incerteza, calibração,
  corpus/snapshots, retrações e API local de coordenação.
- [Perfis implementados em paralelo](acceptance/parallel_profiles.md): matemática,
  simulação, Forge, controle de agentes, assinaturas, SDKs e recursos.
- [Novos perfis delimitados](acceptance/bounded_research_profiles.md): integração racional,
  malhas, física, provas controladas, geração transacional, causalidade e relay local.
- [Auditoria mais recente](audits/FRONTIER_LAB_SIMULATION_2026_10_15.md): execução simulada, resultados negativos e estimativa das 12 fases.
- [Benchmarks e resultados](../benchmarks/README.md): dados, protocolos e artefatos reexecutáveis.
- [Backlog F1–F12](audits/PHASES_1_12_COMPLETION_BACKLOG.md) e [inventário de arquivos/linhas](audits/FILE_INVENTORY.md).
- Auditorias anteriores ficam em `audits/`, com seus snapshots próprios. Seus resultados não se transferem automaticamente para versões posteriores.

- [Perfis locais dos 85 anteriormente planejados](audits/REMAINING_85_2026_10_15.md),
  [disposição individual](acceptance/remaining_85_implementation.json) e
  [contratos consultáveis](acceptance/scientific_capabilities.yaml).

## Arquitetura, visão e governança

- [Visão principal](../vision.md), [plano mestre](PLANO_MESTRE_2026_2056.md), [mapa de fases](architecture/vision-phases.md) e [critérios de arquitetura](ARCHITECTURE_AND_ACCEPTANCE.md).
- Decisões: [escopo do produto](adr/0001-product-scope.md), [AST canônica](adr/0002-canonical-ast.md) e [registro de decisões/pendências](DECISIONS/README.md).
- [Dados](DATA_GOVERNANCE.md), [modelos](MODEL_GOVERNANCE.md), [rede](NETWORK_GOVERNANCE.md), [operações](OPERATIONS.md) e [publicação](PUBLISHING.md).
- [Segurança](../SECURITY.md), [ameaças](THREAT_MODEL.md), [incidentes](INCIDENT_RESPONSE.md) e [releases](RELEASE_POLICY.md).

## Contexto histórico

[Histórico documental](history/README.md), [índice do acervo](CONTENT_INDEX.md) e
[migração](MIGRATION_STATUS.md) preservam o contexto. O roadmap inicial
[F0–F6](ROADMAP_GLOBAL_RESEARCH.md) é um recorte anterior; para F1–F12 consulte o
backlog e a auditoria atuais. Código histórico fica em `legacy/`.

## Uso científico reproduzível

[Experimentos em código](../examples/science/README.md): 76 operações na biblioteca, CLI e HTTP; 176 referências finitas; oito famílias Forge; modelos físicos idealizados, difusão e modo de provas Lean. [Aceite pessoal 1.0.0](acceptance/PERSONAL_USE_1_0.md).

## Entrega 1.0

- [Guia da versão 1](releases/V1.md).
- [Validação executada](releases/V1_VALIDATION.md).
