# Expansão formal e distribuição integral de fontes

Esta entrega amplia o protocolo público de 5.000 para 30.000 instâncias de
teoremas racionais, mantendo dez famílias estruturais. Foram acrescentadas
**120.350 linhas Lean geradas**, excluindo bundles, manifesto e documentação.
A geração/verificação e o empacotador receberam 227 linhas Python líquidas;
os testes receberam 169. Não houve nova implementação no runtime `src/` nesta
rodada. Quantidade de fonte formal não equivale a novas famílias de algoritmos.

## Resultados executados

- O kernel Lean 4.34.0 verificou **30.000/30.000 teoremas** em 60 unidades.
- Todas as unidades passaram na auditoria dos axiomas esperados.
- Os 17 testes de empacotamento e divisão do corpus passaram.
- Um wheel foi construído, instalado em ambiente isolado e exercitado em quatro
  operações com replay: enclosure polinomial, integral certificada, primeira
  entrada Markov e limite racional.
- `math.txt` e `NABLA.TXT` foram gerados e conferidos contra as fontes atuais.
- Os filtros Git de `NABLA.TXT` preservam os bytes: seu hash com filtros e sem
  filtros coincide. A normalização automática de finais de linha foi desativada
  somente para esse arquivo, que contém blocos com hashes dos bytes originais.

O relatório do corpus desta máquina fica em
`.nabla/rational-kernel-corpus-30000/report.json`, com logs separados, versão do
compilador, protocolo e resultados. Não é uma execução remota de CI.
O workflow de conformidade foi atualizado para a expansão.

## Arquivos entregues na raiz

`math.txt` mantém a seleção matemática do gerador existente. `NABLA.TXT` contém
1.133 arquivos de fonte/configuração, com índice, enquadramento por tamanho e
SHA-256 por arquivo. Ambos são agregações de fontes, não programas binários
compilados nem substitutos dos arquivos canônicos.

O pacote completo cobre serviços, SDKs, testes, ferramentas, site, instalador,
fontes matemáticas e fontes legadas. Exclui dependências instaladas, caches,
dados locais ignorados, ativos binários, prosa documental e arquivos de resultados
em formatos de dados. Não inclui os próprios bundles recursivamente.

Veja [como regenerar e conferir os arquivos](../SOURCE_BUNDLES.md).

## Estado da versão

A expansão é um corpus de regressão e conformidade em parâmetros públicos,
não um holdout privado nem evidência de generalização científica. A matriz
permanece com 213 requisitos parciais. Não se declara a visão inteira concluída.

`tools/vision_readiness.py` deve ser executado para esta entrega. A validação
Mathlib do laboratório original permanece separada das provas Std. Qualquer
timeout ou bloqueio desse laboratório precisa ser informado no relatório final;
o sucesso do corpus não substitui as demais exigências científicas.
