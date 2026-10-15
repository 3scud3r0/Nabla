# Avaliação congelada racional v1

`FrozenEvaluation` fixa tarefas, baseline, papéis declarados, linhagem de treino/
teste e política antes de receber respostas. A identificação SHA-256 cobre todo
o protocolo. Guarde o ID em um registro confiável antes de avaliar; um hash vindo
do próprio arquivo substituído não protege contra troca do protocolo.

O avaliador aceita somente vetores de respostas racionais em JSON. Não recebe
funções, modelos executáveis, shell ou código do candidato. Cada resposta é
verificada por resíduos/determinantes ou identidade dos coeficientes da derivada,
sem consultar o witness do gerador. Constantes arbitrárias de integração são
aceitas quando matematicamente corretas. São exigidas respostas para todas as
tarefas; duplicatas, IDs extras, campos desconhecidos e protocolo divergente
são recusados. Respostas racionais erradas contam como erro; vetores malformados
invalidam a submissão inteira.

A auditoria de linhagem exige treino declarado e exatamente os IDs das tarefas
de teste, e recusa conexões transitivas entre splits por pais, inclusive externos,
ou grupos de fonte/template/semântica/derivação. Isso não detecta parentesco
omitido ou autentica a procedência. Declare todos os vínculos conhecidos.

O relatório contém acertos por tarefa, pares vitória/derrota/empate contra o
baseline e intervalos Wilson nominais de 95%. Esses intervalos pressupõem ensaios
Bernoulli independentes, hipótese não estabelecida pelo software. A decisão é
sempre `descriptive_only`: o relatório não demonstra ganho de treino, novidade,
generalização externa ou superioridade estatística sob múltiplas tentativas.
Reexecução exige protocolo e submissão originais e rejeita relatórios adulterados,
mesmo com seus hashes recalculados.

## Exemplo reproduzível

Na raiz do checkout, com o pacote instalado, use destinos novos:

```sh
python examples/frozen_evaluation.py .nabla/frozen-demo
# Guarde o protocol_id impresso antes de pontuar novas submissões.
nabla freeze-evaluation .nabla/frozen-demo/spec.json .nabla/frozen-demo/protocol-cli.json
nabla evaluate-frozen .nabla/frozen-demo/protocol-cli.json .nabla/frozen-demo/submission.json --expected-id ID_PREVIAMENTE_REGISTRADO --output .nabla/frozen-demo/report-cli.json
nabla check-evaluation .nabla/frozen-demo/protocol-cli.json .nabla/frozen-demo/submission.json .nabla/frozen-demo/report-cli.json --expected-id ID_PREVIAMENTE_REGISTRADO
python -m pytest -q tests/evaluation/test_frozen.py
```

O exemplo usa respostas analíticas escritas à mão e identidades de fixture;
nenhum modelo foi treinado e nenhum revisor real aprovou resultados. O perfil
aceita até 256 tarefas das duas famílias `ScientificTask` v1 e entrada JSON
limitada a 1 MB. Não exige dependências científicas opcionais.

## Limite operacional

Esta API em processo local não torna o holdout secreto, isola o proponente nem
autentica atores. Para uma avaliação externa, o operador precisa de controle de
acesso fora deste processo, protocolo pré-registrado, administração independente
do holdout e controle das tentativas. Não atribuir essas propriedades à biblioteca.
Os requisitos 24, 140, 162, 198 e 201 continuam parciais ou planejados conforme a
matriz, e não recebem aceite científico integral com esta entrega.
