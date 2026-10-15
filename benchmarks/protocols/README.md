# Protocolos congelados de avaliação

Estado: procedimento disponível; este diretório não contém um ensaio externo
aprovado. Cada execução deve apontar para um protocolo imutável identificável por
conteúdo, conservado antes do primeiro acesso ao resultado de avaliação.

Registro necessário: hipótese e revisão; autores e responsável efetivo; população,
licença, grupos e exclusões; sementes; baselines e versões; unidade experimental;
métricas e tolerâncias; orçamento de CPU/GPU, memória e tempo; número de tentativas;
regra de parada; hipóteses estatísticas e comparações múltiplas; política de falhas;
partições e compromisso de hashes; conflitos e plano de publicação dos negativos.

[ReplicationProtocol](../../src/nablamath/knowledge/replication_protocol.py)
congela revisão, autoria, procedimento, evidências e intervalo de uma métrica.
Ele não implementa sozinho todo o registro acima, custódia temporal ou estatística
inferencial. Guardar o registro completo como artefato adicional e fixar seu hash
em `evidence_ids`. A assinatura e um recibo temporal independente, quando exigido
pelo ensaio, devem anteceder a abertura do holdout. Um hash isolado não prova data.

Para executar, resolver evidências por conteúdo, registrar ambiente e todas as
saídas, inclusive erro, cancelamento e timeout. Não substituir tentativa malsucedida
por outra com o mesmo identificador. Cada tentativa recebe ID distinto ligado ao
protocolo, semente e motivo. Ajuste posterior exige protocolo novo e conjunto novo;
conservar o anterior e informar a análise como exploratória.

Replay local: `record_replication` e `replay_replication` em
[independent_replication.py](../../src/nablamath/discovery/independent_replication.py).
O valor observado é fornecido pelo operador; estes contratos verificam integridade
e decisão por intervalo, não recalculam a métrica. Para resultados científicos,
anexar comando e avaliador independente que a recalcule dos dados autorizados.
Não confundir intervalo de aceite com intervalo de confiança. Publicar o número
total de tentativas e a regra de seleção, inclusive se nenhuma teve sucesso.
