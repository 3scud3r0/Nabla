# Registro de riscos científicos — versão 1

Estado inicial: riscos abertos, sem responsáveis pessoais ou aceites inventados.
O responsável por uma execução deve registrar proprietário, data de avaliação,
probabilidade, impacto, mitigação e evidência residual antes de aceitar um risco.

| Risco | Gatilho verificável | Controle disponível | Evidência necessária para reduzir risco |
| --- | --- | --- | --- |
| Vazamento de avaliação | ancestral ou família compartilhada | auditoria de contaminação e linhagem | inventário de treino e teste, controles adversariais e auditor externo |
| Novidade indevida | ausência em corpus local tratada como descoberta | novidade relativa com corpus fixado | busca bibliográfica curada e parecer independente |
| Replicação circular | mesmo autor, código ou fonte no replicador | conflitos declarados e protocolo congelado | execução independente documentada e resultados negativos |
| Parecer sem identidade | chave ou nome autodeclarado | chaves fixadas e assinatura de parecer | verificação externa de identidade, especialidade e conflitos |
| Erro numérico | resultado sem tolerância ou convergência | requisitos de evidência numérica | referência independente, refinamento e orçamento de erro |
| Promoção indevida | fixture descrita como observação externa | origem e escopo explícitos | dados reais licenciados e ensaio pré-registrado |
| Seleção de tentativas | somente melhor semente publicada | protocolo e recibos identificados por conteúdo | registro completo de tentativas e regra de parada |
| Falha operacional | timeout, falta de memória ou dependência | limites e resultados de falha explícitos | inventário de hardware e replay em ambiente equivalente |
| Capacidade exagerada | teste local chamado de autonomia geral | avaliações delimitadas | novas tarefas externas, intervenções registradas e análise de falhas |

Controles: [contaminação](../../benchmarks/contamination/README.md),
[protocolos](../../benchmarks/protocols/README.md),
[revisão](../governance/independent_review_policy.md).
Cada ocorrência deve ter ID, artefato afetado e revisão, severidade justificada,
medida corretiva e verificação da correção. Não apagar ocorrências encerradas.
Risco sem evidência permanece aberto; falta de dados não recebe probabilidade
zero. Reavaliar em nova versão, incidente ou [revisão anual](annual_reassessment.md).
