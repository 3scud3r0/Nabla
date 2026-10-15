# Estrutura e responsabilidades

Na raiz, `README.md` apresenta instalação e uso; `description.md` resume o produto;
`vision.md` define a ambição. Licença, contribuição, segurança, metadados e scripts
de instalação ficam na raiz por serem entradas padrão de usuários e automação.

| Caminho | Responsabilidade |
|---|---|
| `src/nablamath/` | Fonte canônica e APIs instaláveis; veja o [mapa dos módulos](current-modules.md) |
| `tests/`, `lean/` | Verificações Python e projeto formal com dependências fixadas |
| `docs/` | Guias e governança, acessíveis pelo [índice](../README.md) |
| `docs/architecture/`, `docs/adr/` | Arquitetura e decisões técnicas |
| `docs/DECISIONS/` | Decisões e pendências de produto, distintas dos ADRs |
| `docs/audits/` | Relatórios por snapshot, critérios e inventário gerado |
| `docs/history/`, `legacy/` | Documentação histórica e código antigo, respectivamente |
| `benchmarks/fixtures/` | Referências fixadas com licença e procedência |
| `benchmarks/results/` | Bundles auditados; caminhos e bytes fazem parte de manifestos |
| `examples/`, `templates/` | Exemplos de uso e perfis de documentos |
| `tools/`, `scripts/` | Reprodução/auditoria e preparação/importação, respectivamente |
| `protocol/`, `sdk/`, `services/` | Contratos e protótipos de interoperabilidade |
| `packaging/`, `website/`, `.github/` | Distribuição, site e automação |
| `math.txt` | Bundle matemático gerado, sem edição manual |

## Convenções

Módulos de compatibilidade, inclusive `dataset/` e `datasets/`, não devem ser
fundidos apenas pelo nome: existem contratos e consumidores distintos. Mudanças
em caminhos importáveis, CI ou instaladores exigem migração e verificação.

Execuções novas ficam em `.nabla/`; ambiente em `.venv/`; saídas de build em
`build/` e `dist/`. Esses diretórios e caches ficam fora do PR. Um resultado só
entra em `benchmarks/results/` com protocolo, licença, métricas, limitações,
falhas preservadas e manifestos conferidos.

Não reorganize o interior de um bundle fechado apenas por estética: referências
e hashes fazem parte do contrato. Preserve o snapshot publicado e produza uma
nova versão. Novos guias entram no índice de documentação e novas ferramentas no
índice de `tools/`. Material de conversa vai para `docs/history/`, separado da
apresentação atual e do código canônico.
