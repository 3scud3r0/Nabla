# Holdouts privados sob custódia externa

Estado: processo especificado, sem custodiante nomeado ou holdout externo entregue.
"Privado" no nome de um diretório público não protege dados. Não versionar os
exemplos, respostas, tokens, credenciais ou chaves do avaliador neste repositório.

Antes do ensaio, o custodiante efetivamente designado deve verificar sua
independência e autorização para os dados, fixar população e partições e publicar
um compromisso de integridade do conjunto. Dados de baixa entropia podem ser
recuperados de hashes simples; usar compromisso com segredo aleatório mantido
pelo custodiante e revelar apenas quando a política permitir. Essa custódia
criptográfica e temporal é externa aos contratos locais.

O proponente congela modelo/checkpoint, linhagem de treino, código, dependências,
protocolo, número máximo de consultas e orçamento antes de receber resultados.
O avaliador executa em ambiente isolado, registra acessos e publica recibos sem
expor dados restritos. Devolver somente o nível de detalhe pré-registrado para
impedir adaptação por respostas. Manter também recibos de falha e timeout.

Exigir nova coorte para alterações motivadas pelo resultado. A reutilização de
holdout deve ter limite explícito e auditoria; não chamá-lo de novo após troca de
semente de apresentação. Auditar ancestrais, famílias e fontes conforme
[contaminação](../contamination/README.md). Proveniência incompleta mantém o risco
aberto, mesmo que nenhuma duplicata seja detectada.

A publicação deve informar custodiante verificado, conflitos, compromisso inicial,
protocolo, tentativas totais, ambiente, métricas e incertezas, sem expor exemplos
protegidos. [Replicação local](../../src/nablamath/discovery/independent_replication.py)
registra declarações e evidências; ela não cria custódia externa nem valida a
identidade real. O aceite externo permanece pendente até executar esse processo.
