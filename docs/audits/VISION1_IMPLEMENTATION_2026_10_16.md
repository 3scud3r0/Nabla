# Implementação local do plano vision1 — 2026-10-16

A versão permanece **0.1.0a1**. Todos os **212 caminhos** do plano estão presentes:
152 arquivos de produto/aceite e 60 unidades Lean geradas. Este inventário não
aprova individualmente os critérios de aceite nem declara o produto pronto.

## Entrega concreta

- Adicionados os três arquivos antes ausentes: política de estabilidade, changelog
  e testes de cadeia de distribuição. Módulos existentes foram reaproveitados.
- JSON compartilhado aceita orçamentos explícitos sem relaxar os limites padrão.
  Notebooks recusam duplicatas, schemas booleanos, campos extras e mudanças de
  tipos/resultados mesmo quando o remetente recalcula hashes.
- Diagnóstico formal verifica o compilador fixado com timeout e separa sua versão
  da disponibilidade Mathlib, conservada como não verificada.
- Backup usa temporários exclusivos e lock entre escritores. Restore valida
  manifesto estrito, hash, integridade e schema SQLite dos bytes publicados,
  recusando sobrescrita concorrente por publicação atômica sem substituição.
- Readiness inclui inventário dos 212 caminhos e atualidade do NABLA.TXT.
  math.txt e NABLA.TXT foram regenerados e conferidos.

## Evidência desta execução

Suíte completa: **2296 passaram e 9 foram pulados**; 316 subtestes e 17 avisos SymPy. As fontes ficaram estáveis durante a execução final.

O wheel foi construído com isolamento, teve 606 arquivos verificados pelo RECORD
 e foi instalado em venv vazio sem dependências. Python -I executou CLI, notebook,
replay, recusa de domínio inválido, backup/restore e replay de artefato científico
usando exclusivamente o pacote instalado. Integridade RECORD não autentica autor
nem garante segurança das dependências.

Os nove skips da suíte são GPU (2), Rust (2), Mathlib (3), Lean ausente do PATH (1)
e SciPy (1). O subconjunto de compilador foi executado depois com o Lean fixado
no PATH: 42 passaram; isso não apaga o skip original. GPU/Rust/SciPy são opcionais
ao perfil CPU local. Os três skips Mathlib permanecem bloqueio para esse backend.

A conferência do corpus preserva 30.000 teoremas e o protocolo original; não foi
necessário gerar mais código nem repetir a compilação integral já registrada.

| Etapa | Resultado |
|---|---|
| roadmap | passed |
| contracts | passed |
| preservation | passed |
| bundle | passed |
| source-bundle | passed |
| vision1-files | passed |
| pytest | passed |
| longley | passed |
| laboratory | failed |
| calibration | passed |

O laboratório Mathlib continua falhando por timeout. Longley e a calibração finita
passaram, sem estabelecer prontidão universal. A execução intermediária está
preservada e registra mudanças de fontes; a execução final valida as correções.
Não houve retry para escolher um resultado favorável de benchmark.

## O que ainda impede concluir o pedido como release 1.0

Resolver preparo/execução Mathlib para o backend declarado, executar CI e instalador
Windows no commit exato, revisar significado dos enunciados e segurança de forma
independente, conferir licenças/procedência e obter autorização/identidade de
assinatura do publicador. Essas evidências não são produzidas pela criação de
arquivos. Os gates de vision1.md permanecem abertos.

O JSON acompanhante lista individualmente cada arquivo, tamanho, hash, conteúdo
esperado e critério pendente. Sua fotografia é das fontes testadas, antes da
adição deste próprio registro documental. Nenhum requisito científico foi promovido.
