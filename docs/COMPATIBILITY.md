# Compatibilidade suportada

A fonte normativa é o arquivo instalado `nablamath/compatibility.json`; `nabla
doctor` compara o ambiente corrente com esse contrato sem acessar a rede. Alterar
a matriz exige alterar o contrato, executar a CI correspondente e seguir
[`RELEASE_POLICY.md`](RELEASE_POLICY.md).

| Componente | Estado |
| --- | --- |
| Python | `>=3.10,<3.15`; matriz de núcleo configurada em 3.10, 3.11, 3.12, 3.13 e 3.14 |
| Windows/Linux | Suportados; instalação limpa deve passar na matriz de release |
| macOS | Experimental; não faz parte da garantia de release atual |
| Lean/Mathlib | 4.34.0 fixado em `lean/`; preparo pinado/cache e provas reais; aprovação depende dos jobs do SHA exato |
| LaTeX | `.tex` gerado; PDF depende de distribuição TeX externa e não foi validado em todos os SOs |
| Numérico | Referências locais pequenas em Python; sem backends GPU nem garantia de desempenho/precisão industrial |
| Serviço global | Ausente; coordenador disponível apenas como classe SQLite local |

Na troca de versão major do Lean ou formato de registro, criar revisão e teste explícito antes de misturar datasets.

## Evidência do candidato

A matriz descreve o alvo de suporte, não prova a execução de um commit novo.
Consulte [Python core](https://github.com/3scud3r0/Nabla/actions/workflows/python-core.yml),
[instalador](https://github.com/3scud3r0/Nabla/actions/workflows/windows-installer.yml)
e [Lean](https://github.com/3scud3r0/Nabla/actions/workflows/lean-core.yml); selecione
o SHA do candidato. Cada artefato inclui esse SHA no nome. A evidência Linux
local não aprova Windows, macOS ou outras versões de Python.

`nabla doctor` informa `unverified` para executáveis apenas descobertos.
`nabla doctor --probe` testa a versão com timeout: `available`, `unavailable` ou
`incompatible`. Lean disponível ainda precisa dos imports Mathlib compilados e
do replay das provas. Versão de `pdflatex` disponível não comprova a revisão
visual de um PDF. Os SDKs e backends opcionais permanecem experimentais.
