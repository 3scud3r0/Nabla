# Contrato de estabilidade proposto para 1.0

A versão distribuída continua 0.1.0a1. Esta política prepara a versão local em
CPU; sua publicação não equivale a aprovar o release.

## Superfície candidata

- `nablamath.__version__` e os entrypoints declarados em `pyproject.toml`.
- `CalculationSession.execute`, `evaluate` e `bind`; `Calculation.to_data`.
- `Notebook.append`, `cells`, `to_data`, `save`, `load` e `replay`.
- Schemas e argumentos obrigatórios/opcionais do catálogo de cálculo.
- AST e contratos versionados de expressão, unidades, artefatos e recibos.
- Comandos CLI documentados; código 0 indica sucesso e código não zero falha.

Esta lista complementa, sem reduzir, os nomes em `__all__` e os contratos de
`RELEASE_POLICY.md`. A lista de operações, argumentos e precisão deve ser congelada no commit de
release, com testes de regressão. Módulos internos, integrações opcionais, agentes,
SDKs, federação e pesquisa continuam experimentais até validação específica.
Um recibo computacional não passa a ser uma prova formal pelo nome do campo.

## Formatos e erros

Notebooks v1 usam JSON UTF-8 com SHA-256 canônico, cadeia de células e replay.
Leitura rejeita chaves duplicadas, números não finitos, versões booleanas,
campos desconhecidos e limites de recursos excedidos. Recalcular um hash não
autoriza trocar o tipo ou resultado de uma célula. Hashes demonstram integridade,
não identidade do autor. `save` não sobrescreve arquivos existentes.

Erros de domínio, entradas inválidas, orçamento excedido e backend ausente devem
ser distinguíveis nos recibos/diagnósticos pertinentes. Mensagens humanas podem
receber correções; consumidores devem usar schemas e estados documentados.

## Mudanças e migração

Após 1.0, mudança incompatível em API estável exige versão principal, nota de
migração e fixture anterior. Adições compatíveis usam versão secundária; correções
usam versão de patch. Não converter dados silenciosamente nem reinterpretar um
schema antigo. Migrações avançam explicitamente um passo por vez pelo registro;
versão desconhecida ou downgrade são recusados antes de alterar o original.

Depreciações serão documentadas no changelog e mantidas por pelo menos uma versão
secundária antes da remoção em versão principal. Correção de segurança que exija
recusa imediata de entrada terá motivo e instrução de migração documentados.

## Evidência necessária

Uma suíte local verde não demonstra Windows, autenticidade do publicador nem
revisão independente. A estabilidade final depende da matriz CI no commit exato,
instalação dos artefatos, upgrade/restore e aceite dos responsáveis de vision1.md.

## Fixture executável do perfil candidato

`configs/release/local-v1-api.json` congela os exports de cinco módulos candidatos,
assinaturas de sessão/notebook e nomes/argumentos de 40 operações.
`python tools/check_local_api.py` compara o runtime com essa fixture e faz parte
da execução completa de readiness. Não existe opção de sobrescrita automática: uma
alteração requer decisão de compatibilidade e notas de migração. A fixture congela
a superfície; os testes matemáticos continuam necessários para sua semântica.

`tests/fixtures/local-alpha/notebook-v1.json` foi capturado do wheel alpha anterior
instalado, com três cálculos reais. O hash do wheel e a limitação de procedência
estão em `origin.json`. Isso verifica compatibilidade com um build alpha anterior;
não se apresenta como uma versão estável anteriormente publicada.
