# ADR 0001 — Execução científica local e verificável

Estado: implementado no recorte local; não declara aprovação externa das fases.

O checkout existente continua sendo a aplicação canônica. O ciclo Forge roda em
uma máquina comum, sem credenciais, serviços externos ou novas dependências
Python. Construtores, solvers e verificadores têm módulos separados. A CLI cria
artefatos em diretório novo e recusa sobrescrever resultados existentes.

Toda amostra gerada é sintética. Igualdade racional e resíduos exatos são
evidência computacional; não são prova Lean nem validação experimental. Upload,
execução de código proposto por agentes e publicação não fazem parte deste ciclo.
A seleção de políticas limita-se aos integradores existentes Euler e RK4.

Resultados de avaliações, inclusive negativos, permanecem explícitos. Nenhum
marcador de fase concluída é derivado de quantidade de arquivos ou testes.
