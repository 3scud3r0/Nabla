# Changelog

## Não publicado — coesão do perfil local alpha

- Entrada unificada e verificável para biblioteca Python, CLI, catálogo, notebook e desktop: `nabla catalog`, `nabla calc` e rotas locais `/api/catalog` / `/api/calculate` partilham o mesmo `CalculationSession`.
- Novo conjunto de 29 operações científicas exatas experimentais agrupadas por teoria dos números, álgebra de corpos finitos, análise rigorosa, grafos e probabilidade; 69 operações no catálogo total. A cobertura de domínio é finita.
- O desktop mostra recibos multidomínio sem gravá-los indevidamente no SQLite legado de expressões, preservando semântica de reexecução.
- Smoke offline do fluxo CLI–sessão–notebook–desktop (`tools/cohesion_smoke.py`) e testes HTTP de autenticação/origem; CI focada em Linux/Windows e cancelamento de workflows obsoletos por branch.
- [Critérios de aceite do primeiro alpha coeso](docs/acceptance/COHESIVE_LOCAL_ALPHA.md); bundles consolidados, CI, wheel e revisão ainda requerem evidência antes de merge/release. A versão do pacote continua `0.1.0a1` até aprovação explícita.

## Não publicado — preparação do perfil local 1.0

- Contrato de API/catálogo e schemas congelado, incluído no wheel e verificado
  automaticamente; inventário individual dos 212 caminhos do `vision1.md`.
- Promoção de versões finais 1.x exige checklist completo no SBOM coberto pela
  assinatura de uma autoridade previamente configurada; flags locais não aprovam gates.
- Smoke do wheel em venv limpo e offline: cálculo certificado, notebook/replay,
  persistência, importação/exportação, backup/restore e artefato científico.
- Migração SQLite por savepoint, preservando transações do chamador e recusando
  bancos cuja estrutura não corresponda à versão declarada.
- Backup deixa a origem intacta. Restore valida a estrutura e os bytes da cópia
  efetivamente publicada e aceita migração do schema alpha 0 para 1.
- Publicação de notebooks e restaurações atômica, sem sobrescrita. Notebooks
  rejeitam chaves duplicadas, versões booleanas e campos inesperados no replay.
- Laboratório compara o catálogo inteiro ao contrato congelado, corrigindo o
  contador histórico de 33 operações que reprovava o catálogo atual de 40.
- `doctor --probe` distingue disponibilidade, versão incompatível e descoberta
  sem teste. Mathlib recebe cache da revisão fixada antes das provas; o setup
  preserva o manifesto em vez de executar atualização livre de dependências.
- CI registra resultados por commit, cobre cada Python da faixa declarada e
  exercita instalação/reinstalação/desinstalação Windows preservando dados.

Migração: use destinos novos para backups; um backup existente não é mais
sobrescrito. Os formatos persistidos continuam no schema 1; o restore aceita
schema 0 conhecido. SDKs e backends opcionais continuam experimentais.

Os gates e evidências restantes são publicados em
[aceite 1.0](docs/acceptance/version_1_0.md). Esta seção não representa publicação,
assinatura por mantenedor, revisão independente ou CI já aprovada.

## 0.1.0a1 — linha alpha anterior

Laboratório local delimitado com CLI/desktop, matemática racional, notebooks,
artefatos, dados e backends opcionais. Os resultados históricos e as limitações
científicas são preservados nos diretórios `docs/audits` e `benchmarks/results`.
