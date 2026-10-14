# Modelo aberto e estudo controlado

Pesos MIT do regressor numérico de texto usado na comparação com/sem dados Nabla.
Não são pesos de um LLM ou modelo de fronteira. `protocol.json` fixa coortes,
sementes, orçamento e hash do código; `report.json` contém todas as previsões e
resultados negativos. `source-manifest.json` identifica o GSM8K original, cujo
aviso MIT foi preservado em `GSM8K_LICENSE`. A licença MIT do projeto aplica-se ao
código e aos novos pesos; este diretório não redistribui perguntas completas.

Os arquivos `.npz` contêm somente quatro tensores numéricos (`w`, `b`, `v`, `c`).
Use `OpenNumericMLP.load(..., seed=...)` e `verify_experiment_artifacts` para conferir
as previsões contra a mesma versão do conjunto de teste externo. O carregamento
usa `allow_pickle=False`. `runtime.json` registra as versões utilizadas.
