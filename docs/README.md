# Documentação do NablaMath

## Começar e desenvolver

- [Instalação e uso](../README.md), [aplicativo local](DESKTOP.md) e [contribuição](../CONTRIBUTING.md).
- [Estrutura do repositório](architecture/repository-layout.md) e [módulos canônicos](architecture/current-modules.md).
- [Ferramentas de reprodução](../tools/README.md) e [exemplos](../examples/README.md).

## Implementação científica

| Tema | Guia |
|---|---|
| Calculadora e Forge | [Fases 1–2](PHASES_1_2.md) |
| Provas, refutação e cenas | [Fases 3–4](PHASES_3_4.md) |
| Studio, datasets, simulação e aprendizado | [Fases 5–8](PHASES_5_8.md) |
| Discovery, evolução, disciplinas e conhecimento | [Fases 9–12](PHASES_9_12.md) |
| APIs ampliadas e reprodução integrada | [Perfis de maturidade](PHASES_MATURITY_EXPANSION.md) |
| Simulação de uso laboratorial | [Protocolo e comandos](FRONTIER_LAB_SIMULATION.md) |

## Evidências e limites

- [Auditoria mais recente](audits/FRONTIER_LAB_SIMULATION_2026_10_15.md): execução simulada, resultados negativos e estimativa das 12 fases.
- [Benchmarks e resultados](../benchmarks/README.md): dados, protocolos e artefatos reexecutáveis.
- [Backlog F1–F12](audits/PHASES_1_12_COMPLETION_BACKLOG.md) e [inventário de arquivos/linhas](audits/FILE_INVENTORY.md).
- Auditorias anteriores ficam em `audits/`, com seus snapshots próprios. Seus resultados não se transferem automaticamente para versões posteriores.

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
