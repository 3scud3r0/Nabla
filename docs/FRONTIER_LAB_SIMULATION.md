# Ensaio local de utilização laboratorial

Este comando representa as responsabilidades de curadoria de dados, avaliação de
modelos, computação científica e revisão de release. Os papéis são **simulados**:
não representam pesquisadores externos, usuários reais de um laboratório ou
modelos de fronteira. A campanha executa código real e preserva resultados
negativos. Não converte aprovação de cenários em conclusão das fases do vision.md.

## Execução

No ambiente preparado do projeto, com Lean/Mathlib fixados e os extras
`test,formal,graphics,documents,data,research,federation` instalados:

```sh
OPENBLAS_NUM_THREADS=1 python tools/simulate_frontier_lab.py .nabla/laboratory-run --per-family 24 --seed 951017
```

Use destino novo. Nenhum dataset é publicado nem se contatam laboratórios reais.
O comando grava protocolo, hashes das fontes Python, versões de dependências,
journal, logs e manifest de artefatos. Cada um dos cinco processos recebe timeout
de 600 segundos; uma falha não impede a execução dos blocos independentes seguintes.
O processo final retorna código diferente de zero se algum bloco ou perfil
selecionado falhar. Não repete avaliações para escolher um resultado favorável.
Timeout limita o processo direto; isto não é isolamento de código hostil nem
garantia de controle de todos os descendentes de um subprocesso.

## Blocos executados

1. **Dados e avaliação:** 24 tarefas únicas em cada uma das oito famílias, com
   tamanhos 2/3/4. As primeiras quatro famílias ficam no treino, duas na validação
   e duas no teste: 96/48/48 registros. Há deduplicação semântica e isolamento por
   família/template. A divisão também muda a família da tarefa; não estima ganho
   dentro da mesma distribuição e favorece uma avaliação difícil para o baseline.
   Os parâmetros e modelos são fixos, sem seleção nos conjuntos reservados.
2. **Fluxo científico:** catálogo, primitivas racionais conferidas com SymPy,
   referência NIST, EDO/EDP, seis cenas, registros mistos, agente com retomada,
   descoberta de lei sintética, prova Lean, três PDFs e troca assinada entre stores.
3. **Solvers independentes:** 32 tarefas novas, tamanhos 2/4/8, Nabla/SymPy/Z3,
   timeout e verificação exata de candidatos. Não suportado é separado de erro.
   Falha de um backend não prova dificuldade avançada para pesquisadores.
4. **Portfólios:** seleção na calibração e avaliação reservada contra dois baselines
   declarados, preservando aceitação/rejeição, promoção e rollback.
5. **Revisão computacional:** replay de certificado, datasets e PDFs; corrupção de
   assinatura, revogação e quarentena; 16 casos de elasticidade, RLC, cinética e
   hidrostática comparados com referências analíticas; unidades e estabilidade.

O bloco de aprendizado treina dois modelos de vizinho mais próximo, um com todas
as entradas e outro textual. O solver exato aparece como **referência de engenharia**,
não como modelo treinado. As seis avaliações preservam acertos, métricas, respostas,
manifestos e comparações pareadas. As classificações multimodais neurais da campanha
anterior também são reproduzidas por seus checkpoints no fluxo científico; não são
novamente treinadas nem passam a constituir um experimento externo.

Os controles adversariais do workload testam ancestral externo compartilhado,
métrica adulterada com hash recalculado, rollback integral de lote com vazamento
e alegação de ganho inserida na ficha do dataset com manifest atualizado.

## Replay da campanha de dados

```python
from nablamath.benchmarks.laboratory import verify_laboratory_workload

assert verify_laboratory_workload('.nabla/laboratory-run/workload')
```

O verificador reconstrói tarefas a partir do protocolo, refaz os modelos,
reexecuta inferência, confere os conjuntos e compromissos, reconstrói métricas e
reexecuta os quatro controles. Rejeita arquivos extras, links simbólicos, artefatos
acima dos limites e relatórios semanticamente adulterados mesmo com hashes novos.
O manifest global da campanha é um inventário de integridade; o replay semântico
é feito pelos verificadores específicos, não apenas por esse inventário.

É possível executar só o workload pela API `run_laboratory_workload(destination,
per_family=24, seed=951017, parquet=True)`, sem Lean/Typst; Parquet exige o extra
`data`, podendo ser desativado. O limite é 64 registros por família, 512 ao todo.
O perfil é deliberadamente limitado, sem alegação de capacidade em escala industrial.

## Limites científicos

Um compromisso SHA-256 comprova correspondência de bytes; não esconde dados do
operador local nem comprova sozinho a ordem histórica dos atos. Os arquivos são
escritos na ordem declarada, mas não há autoridade independente de pré-registro.
Os grupos de contaminação são declarações locais e não verificam a proveniência
de corpora externos. As famílias e construções têm correlações; os intervalos e
testes descritivos não garantem independência populacional.

O relatório mantém `vision_completion_percent: null`,
`vision_target_demonstrated: false` e `whole_phase_completion_established: false`
para cada fase. Aprovar os 12 perfis selecionados mede esse roteiro finito de
aceitação. Não mede 95% da visão nem demonstra adoção externa, ganho de modelos
de fronteira, descoberta nova, validação física observacional ou revisão independente.

A estimativa de maturidade segue a rubrica anterior e deve ser atualizada por
evidências que cubram seus eixos; nenhum campo transforma simulação em evidência
externa. O [relatório anterior](audits/PHASES_1_12_PROGRESS_AFTER_95_REQUEST.md)
explica o teto condicional de 83,68% com a evidência externa hoje disponível.
