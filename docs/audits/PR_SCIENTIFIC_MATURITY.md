O README e a apresentação do projeto descreviam um núcleo inicial, enquanto a
branch já continha APIs científicas e resultados das fases F1–F12. Este PR conecta
essa implementação a documentação atual, campanhas reproduzíveis e evidências
auditáveis, preservando os limites científicos e os resultados negativos.

## O que mudou

- Amplia o catálogo de cálculo, integração racional, bundles formais, cenas,
  perfis de publicação, datasets mistos e métodos de simulação.
- Acrescenta persistência de agentes, modelos por disciplina, busca racional,
  portfólios sob holdout e conhecimento assinado com revogação/quarentena.
- Inclui auditoria transitiva de contaminação por ancestral/template/fonte,
  modelos multimodais com ablações e campanha laboratorial local nas 12 fases.
- Versiona protocolos, datasets, modelos, avaliações, PDFs, logs e manifestos.
  Preserva o fracasso de generalização dos baselines, os ensaios de desenvolvimento
  e a falha do controle de ordenação encontrada e corrigida no wheel isolado.
- Atualiza README, descrição do pacote, links de metadados e contribuição.
  Move o documento original de 3.362 linhas para `docs/history/` sem alterar bytes.
- Organiza a navegação com índices de documentação, benchmarks, ferramentas e
  exemplos; documenta responsabilidades de pastas e compatibilidade de APIs.
- Atualiza inventário por arquivo/linhas, excluindo artefatos duplicados do total
  de código e identificando formatos binários explicitamente.
- Corrige preservação de bytes no checkout Windows para referências e bundles.

## Evidência

- Suíte Python completa reexecutada após a reorganização: **468 testes e 312
  subtestes aprovados em 47,77 segundos**, sem falhas.
- Campanha fixa seed 951017: 192 tarefas; 96 treino, 48 validação e 48 teste,
  com famílias separadas. Solvers Nabla/SymPy: 32/32 no corpus independente;
  Z3: 24/24 suportadas, oito não suportadas.
- Baselines aprendidos: 0/48 no teste reservado; referência exata: 48/48,
  explicitamente identificada como solver sem treinamento.
- 16 casos de disciplinas com referências analíticas, prova Lean reexecutada,
  três PDFs compilados, controles de contaminação e adulteração, assinaturas e
  revogação; cinco blocos e 12 perfis delimitados aprovados.
- Wheel construído e importado em destino isolado; fontes matemáticas conferidas.
- Links locais da documentação verificados; histórico conferido byte a byte;
  inventário reconstruído contra a main integrada.

Os resultados nativos Windows anteriores estão identificados por seus commits
nos relatórios. O CI desta revisão deve ser consultado nas Actions; não se
transfere aprovação de um snapshot para outro.

## Limites e revisão

Não declara 95% de conclusão científica. A estimativa técnica ponderada permanece
70,32%, com incerteza aproximada de ±10 pontos. Uso de laboratório é simulado;
não houve laboratório externo, ganho comprovado de modelo de fronteira, revisão
independente ou validação física observacional ampla.

Os modelos e buscas são delimitados. Ferramentas registradas são confiáveis;
limites de execução não constituem sandbox para código hostil. Assinaturas
autenticam chaves configuradas, não identidade ou expertise de pessoas.
Bundles publicados conservam caminhos e hashes; APIs e caminhos usados por
instaladores/CI são preservados. Caches, ambientes, builds e execuções locais
não entram no PR.

Comece a revisão em `README.md`, `docs/README.md`,
`docs/audits/FRONTIER_LAB_SIMULATION_2026_10_15.md` e
`benchmarks/results/frontier-lab-951017/summary.json`.
