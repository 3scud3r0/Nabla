# Ampliação matemática: fonte manual e corpus formal

Esta entrega acrescenta seis operações públicas: enclosure polinomial,
quadratura certificada, enclosures transcendentes, primeira entrada em cadeias,
classes estacionárias e recompensas descontadas. Os contratos e comandos estão
em [CERTIFIED_MATHEMATICS.md](../CERTIFIED_MATHEMATICS.md).

## Contagem desta entrega

A base foi registrada antes das alterações desta solicitação. A contagem exclui
as mudanças da entrega anterior, documentação, manifesto JSON e `math.txt`.
O bundle espelha fontes canônicas e não pode ser contado outra vez.

| Categoria | Linhas líquidas novas |
|---|---:|
| Implementação Python | 820 |
| Testes Python | 352 |
| Ferramenta de geração/verificação | 225 |
| Instalação e workflow CI | 56 |
| Fonte Lean gerada | 24.070 |
| **Total** | **25.523** |

O corpus Lean tem 19.040 linhas não vazias e sem comentários. Ele contém 5.000
teoremas, seus passos de prova e auditorias de axiomas. São 500 instâncias por
família, em dez famílias; não são 24 mil linhas de algoritmos escritos à mão nem
5.000 capacidades matemáticas diferentes. A parte fora desse corpus soma 1.453
linhas. O volume de fonte não é uma porcentagem de conclusão científica.

## Evidência executada

- 139 testes direcionados e 23 subtestes passaram após o ajuste do instalador.
- O corpus final foi compilado: 5.000/5.000 teoremas aceitos, com auditoria de
  axiomas e o Lean 4.34.0 fixado.
- O resultado inicial de 3.500/5.000 foi preservado. Ele revelou que o solver
  precisava receber fatos explícitos de positividade. A correção emite lemas
  provados de quadrados, produtos e diferenças dos extremos, sem novas hipóteses.
- Uma reinstalação concorrente provocou falhas transitórias numa rodada de
  testes. O instalador foi ajustado para reutilizar a instalação existente;
  a rodada afetada foi preservada e os testes foram reexecutados com sucesso.

Os registros locais ficam em `.nabla/rational-kernel-corpus/`,
`.nabla/rational-kernel-corpus-with-positivity/` e
`.nabla/rational-kernel-corpus-final/`. Fontes anteriores intactas são preservadas
em `.nabla/proof-corpus-history/`. Esses caminhos são evidência da máquina atual;
o workflow novo ainda precisa executar no GitHub Actions da versão alterada.

`tools/vision_readiness.py` é uma verificação adicional obrigatória para a entrega.
Se o laboratório Mathlib falhar, isso deve ser informado separadamente do corpus
Std aprovado. As provas Std não substituem os perfis científicos do laboratório.

## Estimativa do que falta

Para outro lote finito de seis operações com profundidade semelhante, a
estimativa de planejamento é **1.000–3.000 linhas manuais**, incluindo testes e
adaptação às APIs. Não inclui corpus gerado nem formalização analítica profunda.

Para a visão inteira, **não existe uma estimativa defensável de linhas restantes**.
A matriz conserva 213 requisitos parciais, com revisão independente, evidências
externas e medições ainda necessárias. Adicionar código ou milhares de teoremas
parametrizados não fornece essas evidências e não fecha automaticamente F1/F3.

Entre as próximas capacidades delimitáveis estão integração racional com
quadráticas irredutíveis, interval Newton, funções transcendentes em intervalos
de entrada e formalização dos teoremas analíticos usados pelos certificados.
Cada uma precisa de contrato e validação próprios antes de uma estimativa mais
precisa; nenhuma é declarada implementada por esta entrega.
