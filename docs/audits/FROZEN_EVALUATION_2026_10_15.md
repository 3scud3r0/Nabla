# Avaliador congelado racional — 15/10/2026

Continuação dos fundamentos P0 sobre o commit
`613966537717b8e740497057626e4c132634a5c9`, no PR #14.

Entrega: `evaluation/frozen.py` fixa um protocolo por conteúdo, com tarefas
racionais, baseline completo, política e papéis declarados. Pontua somente
respostas JSON, verificadas por resíduos/determinantes ou identidade de
coeficientes, sem executar código do candidato. Recusa protocolos com sistemas
lineares sem solução única, contaminação transitiva declarada, submissões
incompletas ou versões desconhecidas. Exige o ID previamente registrado para
carregar um protocolo pela CLI.

Relatórios têm contagem pareada candidato/baseline, intervalos Wilson nominais
de 95%, hash da submissão e compromisso do protocolo. `verify_report` reexecuta
a pontuação completa; recalcular um hash não torna um relatório falso válido.
O módulo canônico fica em `evaluation/`, compartilhável com evolução; não há
outro avaliador paralelo em `evolution/`.

## Verificação

- 30 novos testes de avaliação: contratos, pontuação analítica conhecida,
  primitivas equivalentes, contaminação por ancestral externo/grupos, substituição
  de protocolo com hash recalculado, relatório adulterado, versões, limites e CLI.
- Exemplo `examples/frozen_evaluation.py` executado: duas respostas analíticas
  corretas contra dois erros do baseline escrito à mão; nenhum modelo treinado.
- CLI `freeze-evaluation`, `evaluate-frozen` e `check-evaluation` executada;
  reexecução concordou com o relatório e saídas existentes foram preservadas.
- Suíte completa Python 3.12/Linux: 545 passaram, 3 ignorados (Lean/Mathlib
  opcional ausente), 309 subtestes passaram.
- Wheel atualizado, perfil mínimo sem extras científicos: 526 passaram,
  22 ignorados, 300 subtestes passaram.
- Compromisso do exemplo:
  `34918c853ea6a10bbe83aaded4ac35af12ddcf8ad440d72d0cbc56cce956dd7d`.

Os resultados globais desta revisão constam na descrição atualizada do PR.
Resultados do relatório P0 anterior continuam associados àquela revisão.

## Limites

O avaliador não autentica pessoas, isola processos ou oculta dados de quem
controla o mesmo processo/checkout. Não detecta linhagem omitida. Wilson pressupõe
ensaios independentes, hipótese não estabelecida neste exemplo. A decisão é
descritiva; não demonstra generalização, ganho de treino, calibração preditiva,
avaliação de modelos de fronteira ou aceite científico dos requisitos 24/140.
