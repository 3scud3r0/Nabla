# Expansão dos perfis verificáveis — 15/10/2026

Base desta rodada: `46130eb10ebd332be4f10db81de9bbcb3ff6bc0c`, integrada pelo
PR #14. A árvore é idêntica à `main` no merge `b2231ac`; esta expansão segue em
um novo PR, separado da entrega já integrada.
Contrato e reprodução: [perfis ampliados](../acceptance/expanded_profiles.md).

Foram implementados intervalos/raiz exata, incerteza SI, calibração binária,
ablações congeladas, monitoramento de regressão, DAG de linhagem, retrações
transitivas, referências editoriais, registro de corpus, misturas sem reposição,
snapshots opacos, linhagem de modelos, registro de recursos e consenso de recibos.

O coordenador recebeu API HTTP com permissões explícitas e limites de entrada,
quota SQLite atômica, heartbeat, recuperação de lease expirado, cancelamento e
submissão idempotente. O log passou a serializar append e conferir o vínculo
anterior registrado. As mudanças preservam a recusa de código não confiável.

Validação específica: 30 testes novos passaram, incluindo 100 casos de limites
racionais, DAG de 1.100 nós, blobs adulterados, resultados analíticos de calibração,
HTTP real, 12 solicitações concorrentes de lease, 8 escritores concorrentes de
tarefas e 100 eventos concorrentes. O ciclo integrado foi reproduzido duas vezes
com conteúdo idêntico e rejeitou sobrescrever um destino existente.

O comando `python tools/expanded_scientific_cycle.py .nabla/expanded-cycle-01`
também foi executado. Os resultados são locais e sintéticos; não substituem
holdout independente, experimentos, rede entre hosts, revisão institucional ou
aceite integral dos itens originais. Estados parciais da matriz apontam somente
os perfis delimitados. Nenhum requisito amplo é declarado validado integralmente.

## Validação final local

- Python 3.12/Linux, perfil completo: **575 passaram**, 3 ignorados por ausência
  do Lean/Mathlib opcional; 309 subtestes passaram.
- Wheel atualizado, ambiente mínimo sem extras científicos: **556 passaram**,
  22 ignorados; 300 subtestes passaram.
- Ciclo ampliado executado também com o wheel instalado, fora do checkout.
- Site: 5 testes e build passaram.
- Bundle matemático regenerado e verificado; matriz: 49 requisitos parciais,
  164 planejados, nenhum integralmente validado.
- Instruções reutilizáveis de início ampliadas no rascunho do ambiente; salvar
  instruções não publica uma nova versão do ambiente.
