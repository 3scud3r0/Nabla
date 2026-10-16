# Benchmark permanente da visão

```bash
python tools/vision_readiness.py
```

Esse é o comando padrão antes de entregar alterações. Executa os checks de
rastreabilidade, contratos, preservação, os dois bundles e contrato local 1.0; toda a suíte pytest; Longley;
o laboratório original (`--per-family 24 --seed 951017`); e calibração com 10.000
comparações diferenciais e 512 identidades de integração. Cada etapa preserva
seu log, inclusive falhas e indisponibilidades. Não interrompe outras etapas
apenas porque uma falhou. Cada subprocesso tem limite de 900 segundos.

A saída fica num diretório novo em `.nabla/vision-readiness/`. `REPORT.md` é um
arquivo grande com uma seção para cada um dos 213 requisitos. `report.json`
permite análise automática e contém resultados individuais do pytest. O
relatório registra o código e os contratos medidos por hash, HEAD e horário;
se os arquivos do projeto mudarem durante a execução, ela não é considerada
verificação de engenharia aprovada. Não sobrescreve relatórios anteriores.

- `--inventory-only`: consulta rápida; declara explicitamente que não executou
  testes nem benchmarks.
- `--output .nabla/minha-execucao`: escolhe um diretório novo.
- `--require-complete`: retorna código 2 enquanto aceitação científica integral
  não estiver estabelecida. Esse runner não autentica evidência externa e,
  portanto, não concede sozinho esse selo, mesmo com matriz toda verde.

No modo normal, código 0 significa que as verificações locais executaram e
passaram; não significa 100% da visão. Código 1 indica falha de engenharia,
indisponibilidade de etapa obrigatória ou mudança do código durante a medição.
Testes pulados são listados e permanecem lacunas; não são convertidos em passes.

As lacunas vêm literalmente de `evidence_matrix.json`: não são inferidas de
nomes de arquivos ou da quantidade de código. Atualize critérios e evidências
com revisão quando uma capacidade avançar. Os testes associados à matriz são
relacionados aos resultados JUnit desta execução; uma referência não encontrada
é marcada como não observada. Testes novos fora desses vínculos ainda fazem
parte da suíte global. Aprovação desses testes não encerra automaticamente o
critério original.

A visão inclui pesquisa aberta, experimentos, especialistas e hardware real.
Uma campanha sintética nova não substitui a medição do laboratório original.
O relatório nunca promete AGI, novidade científica ou prazo para o horizonte F13.

[Primeiro relatório completo, com todos os 213 itens](../audits/vision-readiness-20261016/REPORT.md):
2.060 testes aprovados, 5 pulados, calibração e Longley aprovados. Laboratório
completo bloqueado pela ausência de Mathlib; baselines aprendidos 0/48.
Esse snapshot não é atualizado silenciosamente: cada execução nova preserva
seu próprio resultado e sua identificação de código. O CI prepara Lean/Mathlib
antes do comando; essa preparação remota ainda depende da execução do workflow.
