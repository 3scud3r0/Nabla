# Caminho para Nabla 1.0 e para a visão completa

## Resposta quantitativa e limites

**Para a 1.0 delimitada abaixo, estimo cerca de 40% de maturidade de engenharia
restante, com faixa prudente de 30–50%.** A rubrica resulta em 59/100 disponíveis
e 41/100 restantes; arredondo para evitar precisão indevida. É julgamento de
planejamento, não porcentagem de código faltante, tempo restante ou uma aprovação
de release. Todos os gates obrigatórios precisam passar, mesmo com pontuação alta.

**Para o `vision.md` inteiro, não há porcentagem total defensável.** F13 é um
horizonte aberto, e F1–F12 também dependem de resultados e validações externas.
Na métrica estrita de aceite da matriz, **213/213 requisitos ainda têm pendências
(100%) e 0/213 estão integralmente aceitos (0%)**. Isso não significa que não
exista implementação: todos estão declarados `partial` e há software executável.

A estimativa histórica de 70,32% em
[PHASES_1_12_PROGRESS_70.md](PHASES_1_12_PROGRESS_70.md) pertence a outro snapshot,
à rubrica de maturidade de F1–F12 e exclui F13. Não é uma medição atual da visão
inteira nem da versão 1.0. O corpus de 30 mil teoremas não altera esses denominadores.

## Perfil 1.0 proposto para esta avaliação

Release local em CPU: CLI e desktop, matemática delimitada por contratos,
notebooks com replay, persistência/backup, artefatos e exportação, wheel e
instalador suportado. Python 3.10–3.14 em Linux/Windows precisa de CI da versão
exata. Integrações opcionais devem declarar disponibilidade e falhar explicitamente.
APIs/SDKs só são estáveis nos endpoints e formatos explicitamente congelados.

GPU, descoberta científica geral, treino de fronteira, execução de código hostil,
federação pública resistente a Sybil e conclusão científica de F1–F13 ficam fora
desse perfil 1.0. O produto precisa comunicar essa fronteira ao usuário.
Este é um **perfil proposto**, não uma mudança aprovada da política de release.

| Eixo da 1.0 | Peso | Pontos atribuídos | Evidência e falta concreta |
|---|---:|---:|---|
| Cálculo delimitado e contratos | 10 | 8 | Testes/oráculos e recusas existem; faltam congelamento e revisão dos contratos |
| CLI, notebooks e artefatos | 10 | 8 | Replay e smokes passam; falta aceite público do fluxo inteiro e migração de versões |
| Desktop e experiência de uso | 10 | 5 | HTTP, cálculo e exportação verificados; falta revisão de usabilidade/acessibilidade e erros |
| Integração formal | 10 | 5 | Std verifica 30 mil instâncias; laboratório Mathlib falha por timeout |
| Persistência, migração e backup | 5 | 3 | APIs/testes existem; falta matriz de upgrade/restore entre releases suportadas |
| Dados, licença e proveniência | 5 | 3 | Gates e formatos delimitados existem; falta auditoria externa e aceite do perfil |
| Distribuição e instalação | 10 | 5 | Wheel isolado passa; instalador da versão alterada ainda não foi validado/publicado |
| Compatibilidade | 10 | 4 | Execução atual Linux/Python 3.12; falta matriz da versão exata em SOs/Pythons suportados |
| Segurança operacional | 10 | 4 | Código arbitrário é recusado; falta revisão independente do perfil e dependências |
| Versionamento e API estável | 5 | 2 | Versão atual 0.1.0a1; falta política 1.0 e congelamento formal dos contratos públicos |
| CI e aceite do release | 5 | 1 | Verificações locais registradas; CI da branch/commit e aprovação do release pendentes |
| Documentação e suporte | 5 | 3 | Guias e limites existem; falta documentação congelada e revisada para 1.0 |
| Desempenho e orçamento | 5 | 3 | Benchmarks finitos passam; falta perfil representativo por hardware e limites publicados |
| **Total** | **100** | **59** | **41 pontos restantes; faixa de planejamento 30–50** |

Os pontos foram atribuídos manualmente com base nos resultados observados e nas
lacunas acima. Não há fórmula automática que converta testes ou linhas em maturidade.

Plano autossuficiente na raiz: [vision1.md](../../vision1.md), com 152 arquivos de produto/aceite e 60 unidades Lean geradas.

## Arquivos da trilha 1.0: o que cada um deve conter

Os caminhos existentes devem ser ampliados; não se propõe duplicá-los. Caminhos
marcados como propostos não foram criados por este documento.

| Arquivo | Conteúdo/alteração necessária para o perfil 1.0 |
|---|---|
| `docs/acceptance/version_1_0.md` (proposto) | Escopo fechado, endpoints estáveis, formatos, plataformas, exclusões, responsáveis e gates de release |
| `pyproject.toml` | Versão após aprovação, extras alinhados, metadados e dependências reproduzíveis do release |
| `src/nablamath/compatibility.json` | Matriz suportada coerente com execução CI da versão exata |
| `docs/COMPATIBILITY.md` | Evidências por SO/Python/Lean/backend PDF e instruções de diagnóstico |
| `src/nablamath/calc/catalog.py` | Catálogo congelado com schemas, unidades, domínios, limites e recusas de cada operação |
| `src/nablamath/calc/session.py` | Contrato estável de pedidos, erros estruturados e compatibilidade de replay |
| `src/nablamath/calc/notebook.py` | Migrações explícitas e fixtures de notebooks entre versões suportadas |
| `src/nablamath/core/semantic_contracts.py` | Política de versões, serialização canônica e limites comuns publicados |
| `src/nablamath/core/migration_registry.py` | Migrações registradas e rejeição explícita de saltos sem caminho suportado |
| `src/nablamath/core/uncertainty.py` | Semântica de propagação e distinção entre intervalo rigoroso e aproximação |
| `src/nablamath/math/analysis/intervals.py` | Contrato público do enclosure racional e interoperabilidade com intervalos numéricos existentes |
| `src/nablamath/numeric/intervals.py` | Compatibilidade dos tipos/erros e descrição de arredondamento, sem semânticas conflitantes |
| `src/nablamath/math/analysis/quadrature.py` | Resto, orçamento e domínios suportados revisados e documentados |
| `src/nablamath/math/analysis/certified_functions.py` | Domínios e precisão do perfil revisados; alegações analíticas separadas de provas Lean |
| `src/nablamath/math/probability/absorption.py` | Contrato público de momentos condicionais/incondicionais e resíduos revisado |
| `src/nablamath/formal/lean_std.py` | Backend Std versionado, tradução auditada e política de compatibilidade de certificados |
| `src/nablamath/formal/lean_checker.py` | Diagnóstico do ambiente Mathlib e execução reproduzível da toolchain fixada |
| `src/nablamath/formal/translation_review.py` | Revisão do significado do enunciado, hipóteses e limites da autenticação do revisor |
| `src/nablamath/verify/certificate.py` | Leitura de certificados anteriores e revalidação sem confiar em flags/hashes isolados |
| `lean/lake-manifest.json` | Dependências fixadas e build reproduzível, preservando a pinagem |
| `scripts/setup_formal.sh` | Instalação Mathlib que complete dentro de orçamento, com verificações de integridade |
| `scripts/setup_lean_std.sh` | Instalação Std repetível, checksum e separação de instalação versus processos ativos |
| `src/nablamath/desktop/app.py` | Fluxos de erro/consentimento, prontidão e armazenamento pessoal revisados |
| `src/nablamath/desktop/index.html` | Interface acessível, estados de operação e limites científicos visíveis |
| `src/nablamath/store/migrations/__init__.py` | Migrações transacionais entre versões suportadas e rollback testado |
| `src/nablamath/store/backup.py` | Restore e integridade demonstrados com bases das versões suportadas |
| `src/nablamath/datasets/quality_gate.py` | Contrato estável de integridade, origem, licença e partições |
| `src/nablamath/export/bundle.py` | Exportação/importação compatível e rejeição de adulteração sob formatos congelados |
| `src/nablamath/agents/sandbox.py` | Manter recusa a código arbitrário enquanto não existir isolamento real validado |
| `packaging/staged_release.py` | Gates de build/teste, preservação de evidência e release apenas após aceite |
| `packaging/signed_release.py` | Assinatura/proveniência com autoridade real configurada e verificação pelo destinatário |
| `packaging/windows/nablamath.iss` | Instalador do commit exato e ciclo de instalar/atualizar/desinstalar validado |
| `sdk/python/client.py` | Endpoints selecionados versionados, timeout/erros e fixtures comuns |
| `sdk/typescript/client.ts` | Mesmos contratos públicos e testes no runtime suportado |
| `sdk/rust/src/client.rs` | Conformidade executada em Rust e limites de API/ABI explicitados |
| `.github/workflows/python-core.yml` | Matriz Linux/Windows e Python de toda a faixa suportada |
| `.github/workflows/windows-installer.yml` | Evidência do instalador da versão alterada, não de um snapshot histórico |
| `.github/workflows/lean.yml` | Build fixado de Mathlib e checagem real dos perfis formais |
| `.github/workflows/rational-conformance.yml` | Corpus Std público e auditoria completa das 60 unidades |
| `.github/workflows/security.yml` | Auditoria da versão exata, dependências e políticas do perfil local |
| `.github/workflows/release-attestation.yml` | Proveniência/SBOM/assinatura vinculadas ao artefato publicado |
| `tests/regression/test_public_api.py` | Fixtures de compatibilidade dos contratos declarados estáveis |
| `tests/integration/test_global_scientific_cycle.py` | Ciclo público completo e falhas esperadas para o perfil 1.0 |
| `tests/security/test_supply_chain.py` | Rejeição de artefatos/fontes/dependências adulterados |
| `tools/vision_readiness.py` | Relatório de execução sem ocultar falhas, skips, bloqueios ou lacunas científicas |
| `tools/build_math_bundle.py` | Bundle matemático regenerável e verificação de atualidade |
| `tools/build_nabla_bundle.py` | Bundle completo por arquivo, hashes e preservação de bytes |
| `README.md` | Começar, instalar e usar a 1.0 com o escopo aprovado e limitações atuais |

Nenhum arquivo, sozinho, produz assinatura real, revisão humana independente,
dados observacionais ou execução de CI: são ações/evidências adicionais.

## Visão completa e inventários

- [Todos os 213 requisitos, por alvo, conteúdo e pendência](VISION_REQUIREMENTS_2026_10_16.md).
- [Inventário individual de fontes e arquivos-alvo da visão](VISION_FILES_2026_10_16.md).
- [Cada arquivo da alteração proposta e sua finalidade](PR_FILES_2026_10_16.md).

Os inventários distinguem arquivos existentes de caminhos propostos. A existência
de um arquivo ou de um teste verde não transforma um requisito em validado.

## Evidência usada

Linux/Python 3.12: 2.269 testes e 316 subtestes passaram; 8 opcionais pulados.
O kernel Std aceitou 30.000 teoremas de dez famílias. Wheel isolado e ambos os
bundles foram verificados. Longley e calibração finita passaram. O laboratório
Mathlib falhou por timeout e sua assurance ficou bloqueada. Os resultados são
locais; não demonstram aprovação da CI de um PR ou de um release 1.0.
