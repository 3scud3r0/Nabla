# Auditoria de contaminação e controles adversariais

Estado: mecanismos locais e procedimento de avaliação; ausência de achado não
prova ausência de vazamento em fontes desconhecidas.

Congelar inventários de treino, validação e teste com IDs por conteúdo, ancestrais,
famílias, fonte, licença e transformações. Incluir geração sintética, recuperação
bibliográfica, checkpoints anteriores e exemplos de prompts. Fixar o momento em
que cada componente teve acesso aos dados de avaliação.

[audit_contamination](../../src/nablamath/training/contamination.py) verifica
sobreposição local e linhagem fornecida. [snapshot_lineage](../../src/nablamath/training/lineage.py)
fornece inventário rastreável. Executar o teste antes da avaliação e novamente após
qualquer mudança de mistura, geração ou checkpoint. O contrato não conhece fontes
omitidas e não certifica contaminação zero.

Controles obrigatórios no protocolo:

- Inserir duplicata exata conhecida em cópia descartável: a auditoria deve detectar.
- Inserir transformação com ancestral registrado: exigir detecção por linhagem.
- Repartir exemplos da mesma família quando o holdout exige famílias distintas:
  exigir falha da política de partição.
- Remover linhagem para simular origem desconhecida: reportar cobertura incompleta,
  sem transformar falta de metadados em independência.
- Separar treino e avaliação genuinamente sem sobreposição conhecida: conservar o
  controle negativo e informar quais classes de transformação não foram examinadas.

Paráfrase e equivalência semântica não se resolvem por hash de bytes. Definir
verificador específico ao domínio, falsos positivos e revisão dos casos ambíguos.
Guardar inventários, comandos, recibos e decisões de exclusão. Se houver vazamento,
isolar itens, reconstruir partições ou obter holdout novo, executar protocolo novo
e reportar tanto o resultado contaminado quanto o corrigido. Não apagar o incidente.
Para custódia externa, aplicar também o [processo privado](../private/README.md).
