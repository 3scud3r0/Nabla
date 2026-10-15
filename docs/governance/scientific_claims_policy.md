# Política de alegações científicas — versão 1

Estado: proposta operacional. Toda alegação deve informar domínio, quantificadores,
hipóteses, unidades, versão, evidências e condições que a refutariam. Resultado
sintético permanece sintético nas tabelas, gráficos, resumos e exportações.

| Classe | Evidência mínima | Limite da conclusão |
| --- | --- | --- |
| Computada | entrada, resultado e replay | execução declarada e domínio suportado |
| Numérica | entrada, resultado, referência e limite de erro | tolerâncias, precisão e região avaliadas |
| Formal | enunciado, hipóteses, kernel e certificado | teorema efetivamente aceito pelo kernel indicado |
| Empírica | observações, protocolo, incerteza e calibração | população e instrumento observados |
| Sintética | gerador, semente, versão e procedência | comportamento do gerador, sem validade externa presumida |
| Hipotética | hipótese, motivação e ensaio de refutação | conjectura aberta; sem promoção por plausibilidade |

As quatro primeiras classes têm requisitos executáveis em
[EvidenceRequirement](../../src/nablamath/verification/evidence.py). O contrato
verifica papéis e referências, não a verdade do conteúdo. Sintético é uma
propriedade da origem, compatível com cálculo ou simulação; hipotético é estado
epistêmico, sem certificado de verdade. Não inventar novas classes aceitas pela
API para preencher esses dois rótulos.

[Novidade relativa](../../src/nablamath/knowledge/novelty.py) informa corpus,
consulta e referências declaradamente consultadas. Ausência local de resultado
não estabelece prioridade científica. [Replicação](../../src/nablamath/discovery/independent_replication.py)
registra observação e intervalo pré-registrado; verifica integridade dos
artefatos, mas não recalcula a métrica declarada pelo operador.

Para publicar, ligar cada afirmação verificável à revisão exata e aos artefatos,
separar dados observados de inferências e incluir resultados negativos. Correções
ou retratações devem acrescentar revisão e propagar impacto aos dependentes;
preservar a história. Aplicar a [política de revisão](independent_review_policy.md)
antes de alegar avaliação independente. Testes internos, assinaturas e consenso
entre programas não substituem esse requisito.
