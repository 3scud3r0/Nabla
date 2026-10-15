# NablaMath — descrição do projeto

NablaMath é um laboratório científico local e modular em Python que conecta
formulação, cálculo, verificação, simulação, dados e publicação. Preserva hipóteses,
unidades, condições de domínio, proveniência e evidências ao longo do fluxo.

O pacote oferece cálculo exato e numérico delimitado, construção inversa de
problemas, verificação Lean/SMT, cenas científicas, documentos Typst/LaTeX/PDF,
datasets reexecutáveis, simulações e agentes com orçamento. Inclui investigação
de hipóteses sintéticas, evolução controlada de portfólios e conhecimento versionado
com assinaturas e revogação.

## Estado e evidências

O projeto é alpha de pesquisa. Há componentes para F1–F12; a conclusão científica
das fases não está demonstrada. A estimativa histórica de 70,32% descreve apenas o snapshot então auditado.
O estado atual é derivado dos contratos e da matriz de aceitação. A campanha
laboratorial é simulada, sem participação externa; a última execução completa
ficou bloqueada na etapa Mathlib. Os modelos aprendidos não
demonstraram generalização nas famílias reservadas dessa campanha.

- [Instalação e uso](README.md)
- [Documentação organizada](docs/README.md)
- [Auditoria e resultados](docs/audits/FRONTIER_LAB_SIMULATION_2026_10_15.md)
- [Visão científica e fases](vision.md)
- [Backlog para ampliar a cobertura](docs/audits/PHASES_1_12_COMPLETION_BACKLOG.md)

## Direção de longo prazo

A visão aproxima matemática simbólica e numérica, provas, experimentos,
aprendizado e revisão em um sistema científico auditável. Ganho em modelos de
fronteira, descoberta autônoma geral, validação experimental ampla e revisão
independente continuam objetivos de pesquisa.

## Histórico preservado

O documento anterior misturava apresentação, requisitos e uma transcrição longa.
Foi movido sem alterar seus bytes para
[docs/history/DESCRIPTION_ORIGINAL.md](docs/history/DESCRIPTION_ORIGINAL.md).
Seus avisos e nomes históricos registram a época; este resumo, o README e as
auditorias atuais orientam o uso do checkout presente.

<!-- nabla:contracts:start -->
## Contratos executáveis e pendências atuais

A matriz registra 213 requisitos com perfis parciais, 0 planejados e 0 integralmente validados. Uma referência de implementação não equivale à aceitação integral.

- [Matriz original dos 213 requisitos](docs/acceptance/evidence_matrix.json).
- [Rastreabilidade de fases, requisitos, testes e evidências](docs/acceptance/vision_traceability.json).
- [Domínios, operações, recusas e tolerâncias](docs/acceptance/scientific_capabilities.yaml).

F0 explicita contratos e infraestrutura; F13 continua horizonte aberto. Os perfis de software não demonstram autonomia científica geral. Provas formais exigem kernel e auditoria de hipóteses; GPU exige execução identificada; observações e revisão externa não são substituídas por fixtures ou identidade declarada.

Verificar: `python tools/check_roadmap.py` e `python tools/check_public_contracts.py`, na raiz do repositório.
<!-- nabla:contracts:end -->
