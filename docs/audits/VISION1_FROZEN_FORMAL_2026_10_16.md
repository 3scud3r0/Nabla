# Continuação da implementação vision1 — ambiente formal congelado

A versão é **0.1.0a1**. Os 212 caminhos estão presentes; isto não equivale ao
aceite dos critérios de cada arquivo nem autoriza declarar release 1.0.

## Correções entregues

- Nove dependências Lean instaladas pelos commits exatos, com fetch raso e sem
  atualizar o manifesto. Instalação repetida reutiliza os mesmos commits; checkout
  divergente ou alterado é recusado e clones interrompidos só são preservados por
  opção explícita. Não se apaga trabalho local.
- Os verificadores tipado e legado e a busca de provas usam somente o compilador
  instalado e caminhos de bibliotecas compiladas, com pinagem de versão e timeout.
  Provar não executa Lake nem inicia resolução/download. O caminho legado agora
  exige auditoria de axiomas e os geradores emitem auditoria para teoremas nomeados.
- Workflows formais substituem atualização livre/bootstrap por branch master pela
  receita com checksum e commits congelados. Execução remota ainda não observada.
- Fixture normativa para exports de cinco módulos, assinaturas e argumentos de
  40 operações. Testes recusam mudanças sem revisão da fixture. Isto é uma
  superfície candidata de API, não garantia científica de cada operação.
- Notebook capturado do wheel alpha anterior tem três células e replay compatível.
  Origem do build é limitada explicitamente; não se inventa uma release anterior.
- Notebook verifica orçamento agregado antes de criar o arquivo.

## Validação final

**2317 testes passaram, 5 foram pulados**; 316 subtestes e
17 avisos SymPy. Os cinco skips são GPU (2) e Mathlib (3). Rust e SciPy foram
instalados e exercitados: 46 testes reais de SDK/interoperabilidade passaram.

As fontes ficaram estáveis durante esta execução final. Execuções intermediárias
e o erro de importação ocorrido durante reinstalação concorrente foram retidos;
a instalação editável foi restaurada antes de repetir a validação. Não foram
selecionados resultados de benchmark para esconder falhas.

O wheel foi construído com isolamento, seu RECORD foi validado, e os bytes de
599 fontes Python coincidem com o checkout. Instalação em venv vazio com Python -I
exercitou CLI, notebook, replay de fixture anterior, backup/restore e diagnóstico
dos dois verificadores sem build Mathlib. Integridade não autentica o publicador.

| Etapa | Resultado |
|---|---|
| roadmap | passed |
| contracts | passed |
| local-api | passed |
| preservation | passed |
| bundle | passed |
| source-bundle | passed |
| vision1-files | passed |
| pytest | passed |
| longley | passed |
| laboratory | failed |
| calibration | passed |

## Bloqueios externos e trabalho restante

O cache oficial Mathlib foi recusado pelo proxy com CONNECT 403. Sem seus objetos
compilados, o laboratório retorna indisponível e assurance continua bloqueada;
não se promove essa recusa para prova válida. A alternativa de compilar todo
Mathlib do zero não foi executada e não é apresentada como pronta.

Os domínios `cache.mathlib.org` e `api.github.com` foram salvos no rascunho,
preservando os presets. O tool retornou `requires_publish: true`. A configuração
ativa ainda é spec 1, sem esses domínios. O tool salva rascunho; sua publicação e
aplicação são ações distintas, realizadas nas configurações do ambiente.

Após ativar o acesso, executar scripts/setup_formal.sh, testes reais Mathlib e
readiness novamente; então criar o PR pela API. Ainda são necessários CI no commit
exato, ensaio Windows, revisão independente e aceite/autenticidade do publicador.
Nenhuma assinatura ou revisão foi inventada e nenhuma versão 1.0 foi declarada.

O JSON acompanhante conserva critérios e hashes dos 212 caminhos na fotografia
validada, anterior à inclusão deste próprio registro documental. Os 213 requisitos
da visão científica permanecem parciais. Esses estados não são uma porcentagem
calculada por linhas de código.
