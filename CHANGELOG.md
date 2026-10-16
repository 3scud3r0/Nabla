# Changelog

## Não lançado — preparação de 1.0

A versão do pacote permanece 0.1.0a1. Não há declaração de release 1.0.

### Capacidades implementadas

- Limites racionais laterais e no infinito com obrigações de domínio e replay.
- Intervalos racionais, limites de Bernstein e quadratura polinomial certificada.
- Enclosures de exp/log/sin/cos no domínio limitado documentado.
- Probabilidades de absorção, momentos condicionais e recompensas de Markov.
- Backend Lean Std fixado com auditoria de axiomas e corpus gerado de 30.000
  instâncias de dez famílias; não são 30.000 algoritmos ou descobertas.
- Agregações reproduzíveis de fontes em math.txt e NABLA.TXT.

### Correções nesta preparação

- Notebooks recusam JSON ambíguo, versões booleanas, campos extras e substituições
  de tipos mesmo quando os hashes são recalculados. Formato válido v1 preservado.
- Diagnóstico formal verifica a versão do compilador fixado, incluindo instalação
  local, e conserva Mathlib como não verificado até prova/replay.
- Testes de distribuição cobrem fontes, metadados de dependências, RECORD,
  caminhos externos, arquivos não registrados e symlinks adulterados.

- Restauração verifica manifesto JSON estrito, schema SQLite real e os bytes que
  serão publicados; publicação atômica recusa destino criado concorrentemente.
  Backups usam temporários exclusivos e lock entre escritores, preservando arquivos
  `.tmp` preexistentes. Um lock remanescente após queda exige investigação antes de
  remoção; não é apagado automaticamente.
- Readiness também confere o bundle completo e inventaria todos os arquivos 1.0.

### Preparo formal congelado e regressão de API

- Instalador de dependências usa commits exatos e fetch raso, preservando clones
  interrompidos apenas por opção explícita. Recusa substituir checkout com outro
  commit ou mudanças locais. As nove dependências foram instaladas e reutilizadas.
- Verificação Mathlib é offline: não executa Lake durante a prova, recusa build
  ausente e versão divergente, e ignora caminhos Lean injetados pelo chamador.
- Workflows Lean usam compilador com checksum e manifesto congelado; removida a
  atualização livre de dependências e o bootstrap pelo branch master do elan.
- Fixture normativa congela a superfície candidata de 40 operações. Notebook
  capturado de wheel alpha anterior tem replay de compatibilidade real.
- Notebook recusa orçamento excedido antes de criar arquivo de saída.

### Migração e limitações

Nenhuma migração automática ou bump para 1.0. Arquivos antes tolerados com contrato
inválido são agora recusados. Backups válidos devem ser preservados antes de edição.
O laboratório Mathlib tem timeout conhecido nesta infraestrutura. CI remota,
instalador Windows, revisão independente e assinatura/proveniência da publicação
continuam gates de release; consulte vision1.md e docs/API_STABILITY.md.
