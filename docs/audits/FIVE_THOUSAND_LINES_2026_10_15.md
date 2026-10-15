# Rodada adicional de implementação — 2026-10-15

Baseline desta rodada: `f0209947c66e163fb9c2bcb50b095ed10e6e13fb`.

O pedido foi acrescentar pelo menos 5.000 linhas de código e trabalhar com muitos
agentes em paralelo. Seis agentes implementaram módulos e testes em frentes
distintas; o agente principal integrou os resultados. Revisões cruzadas por
agentes verificam engenharia local, sem constituir validação científica externa.

Os [contratos e limites](../acceptance/bounded_research_profiles.md) documentam
os perfis. Foram ampliados 25 requisitos, mantendo seus textos originais. A matriz
passa de 103 para 128 parcialmente implementados, com 85 planejados e nenhum
integralmente validado. Em particular, os precursores de execução segura recusam
código arbitrário: não atendem ao requisito de sandbox hostil no sistema operacional.

A contagem exclui documentação, configurações e o bundle gerado `math.txt`.
Linhas físicas incluem linhas em branco; a medição adicional de linhas com tokens
Python exclui comentários e linhas vazias, incluindo docstrings.

## Contagem da rodada

37 arquivos Python novos: **5.166 linhas físicas de implementação** (28 arquivos)
e **2.786 linhas de testes** (9 arquivos), total **7.952**. Excluindo comentários e
linhas vazias, são 4.566 + 2.290 = **6.856 linhas com tokens Python**, incluindo
docstrings. Há ainda 10 linhas adicionadas a uma ferramenta existente; elas não
foram necessárias para atingir a meta anterior de 5.000. O novo pedido de dezenas
de milhares de linhas e conclusão integral dos 213 itens não foi atendido; volume
não constitui evidência de aceitação.

## Verificação executada

- Suíte completa: **1.132 passed, 3 skipped, 309 subtests passed**. Os três skips
  exigem Mathlib compilado. Não foram removidos ou convertidos em sucesso.
- Wheel instalado em ambiente mínimo: **1.026 passed, 109 skipped, 300 subtests**.
  Extras opcionais ausentes explicam os skips; serviços são testados do checkout.
- Campanha diferencial fixa: **10.000/10.000** avaliações exatas concordaram com
  SymPy; protocolo, semente e cadeia de casos registrados. Nenhum modelo foi ajustado.
- Metamorfismos de integração: **512/512**, com certificados de derivada, pontos
  racionais fora dos polos e invariância por escala da fração racional.
- NIST Longley passou: maior erro relativo dos coeficientes
  **2.432568075499757e-15**; erro relativo SSE **4.513231906092073e-16**.
- Os 213 requisitos e links de políticas foram verificados; bundle regenerado.

Os artefatos estão em `benchmarks/results/readiness-2026-10-15/`. O verificador
estrutural de relatório verifica integridade local, não autentica experimentos ou
revisores externos. O campo `fully_calibrated_and_ready` permanece falso.

## Laboratório pedido e resultado negativo

Executado com `--per-family 24 --seed 951017`, em destino novo para preservar
experimentos anteriores. Os baselines `nearest-all` e `nearest-text` continuam em
**0/48** no teste reservado; referência exata **48/48**. O benchmark independente
resolveu **32/32** tarefas construídas, sem demonstrar generalização irrestrita.
Workload, benchmark independente e portfólio passaram. A etapa científica falhou
por falta do backend formal; assurance também falhou. A primeira execução expôs
um diagnóstico ruim: abrir um banco de snapshots ausente criava um banco vazio.
A ferramenta agora registra prerequisite bloqueado sem criar evidência vazia,
com teste de regressão. Não foi alterado o critério de sucesso do laboratório.

Foi instalado Lean **4.34.0**, conferindo o digest SHA-256 da release oficial
`caaa98356098c85dc0fcbbd28e1ec66f39eb6551829972b752ff20e1286b646b`.
O kernel compilou uma identidade proposicional e informou ausência de axiomas;
isso é smoke test do runtime, não prova das traduções do Nabla. Dependências do
`lean/lake-manifest.json` foram obtidas nos commits fixados. O cache Mathlib falhou
com **proxy HTTP403** para `cache.mathlib.org` e `lakecache.blob.core.windows.net`.
A tentativa foi interrompida após confirmar o bloqueio, mantendo verificação TLS.
Uma nova execução foi motivada pela mudança real de pré-requisito (instalação
do Lean), mantendo semente e baselines. Ela também falhou na etapa científica
(`unknown module prefix Mathlib`); assurance registrou bloqueio sem criar o
banco ausente. Os três demais jobs passaram; todos os resultados são preservados.

Foram salvos no rascunho do ambiente `install_script`, `start_skill` e adições aos
domínios permitidos, preservando `api.github.com` e os presets. O bootstrap Python
foi verificado; a etapa de cache adicionada permanece bloqueada e não validada.
Aplicar/publicar o rascunho cabe às configurações do ambiente. Não houve publicação
nesta tarefa. Não há GPU real ou validação científica externa comprovadas.

Seis agentes entregaram implementações em paralelo. A segunda rodada de revisão
cruzada atingiu o limite de uso dos agentes; não é apresentada como concluída.
Integração, inspeção e execução final foram feitas pelo agente principal.
