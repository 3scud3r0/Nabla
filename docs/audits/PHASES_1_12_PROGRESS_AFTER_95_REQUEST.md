# Avanço após a meta de 95% — 15 de outubro de 2026

**Meta solicitada: 95%. Estimativa sustentada mantida: 70,32%.**
Esta rodada entrega prevenção adicional de vazamento; não encerra as lacunas
científicas do [relatório anterior](PHASES_1_12_PROGRESS_70.md) nem os
[104 itens do backlog](PHASES_1_12_COMPLETION_BACKLOG.md).
Não houve nova evidência externa que justifique mudar os eixos E, nem abrangência
adicional suficiente para conceder cinco pontos a uma fase inteira.

| Fase | Estimativa atual |
|---|---:|
| F1 — Calculadora científica | 80% |
| F2 — Forge e geração inversa | 70% |
| F3 — Prove e Falsifier | 70% |
| F4 — Geometria e imagens | 75% |
| F5 — Studio e publicação | 75% |
| F6 — Datasets científicos | 75% |
| F7 — Worlds e simulações | 70% |
| F8 — Multimodalidade e agentes | 60% |
| F9 — Discovery | 65% |
| F10 — RSI controlado | 70% |
| F11 — Outras disciplinas | 60% |
| F12 — Conhecimento científico vivo | 70% |

Mantidos os pesos e a rubrica C/30, I/20, V/20, E/20, O/10. São estimativas por
julgamento, com incerteza agregada aproximada de ±10 pontos, não conclusão
científica certificada. F0 e F13 continuam fora do denominador 95.

## Código entregue nesta rodada

- `evaluation/lineage.py`: auditoria transitiva de derivações, ancestrais e grupos
  declarados de template, semântica, fonte e derivação. Ancestrais ausentes do
  dataset ainda conectam descendentes. Ciclos não causam recursão infinita.
- Grupos têm namespaces: fonte `X` e template `X` não se confundem. Todas as
  partições train/validation/test são confrontadas, inclusive validation–test.
- Manifesto canônico, identificação por hash e reconstrução integral do relatório;
  ordem de entrada não altera o resultado. Limites explícitos de registros,
  identificadores e ligações também se aplicam a iteradores.
- `training/contamination.py`: detecção de duplicatas passa de contagem quadrática
  para contagem por `Counter`. Manifestos opcionais devem cobrir exatamente os
  registros fornecidos e suas partições; vazamento declarado bloqueia avaliação.
- `training/evaluation.py`: o resultado incorpora a auditoria; verificação reexecuta
  o manifesto e confere os registros reservados. Comparações exigem a mesma política
  de contaminação, preservando comparação entre modalidades para ablações.
- `training/ablation.py`: reutiliza o mesmo manifesto em todas as variantes,
  inclusive quando recebido por iterador. A API anterior continua válida.
- Testes negativos, replay, adulteração com hash recalculado, vazamento transitivo,
  ancestrais ausentes, ciclos, namespaces, limites e integração com ablações.
  O workflow de maturidade inclui esses testes em Linux e Windows.

O manifesto contém **declarações fornecidas pelo chamador**. Não autentica sua
origem, não identifica automaticamente toda equivalência ou paráfrase e não prova
ausência de contaminação em corpora externos. Templates muito amplos podem causar
agrupamento conservador excessivo. Esses limites aparecem no próprio resultado.

## Uso

```python
from nablamath.evaluation.lineage import audit_lineage, verify_lineage_report

report = audit_lineage([
    {'id': 'text-task', 'split': 'train', 'parents': ['original'], 'groups': {}},
    {'id': 'image-task', 'split': 'test', 'parents': ['original'], 'groups': {}},
])
assert not report['clean']
assert verify_lineage_report(report)
```

Para integrar com `training.evaluate` ou `run_ablations`, passe `lineage=entries`;
os IDs devem ser `sample.record.content_id`, e não o identificador da tarefa.
Todos os registros fornecidos devem constar exatamente uma vez no manifesto.

## Distância até 95%

Com as evidências externas atuais, mesmo elevar hipoteticamente C, I, V e O ao
máximo em todas as fases produziria **83,68%**. Esse é um teto aritmético
condicional, não o avanço alcançado. Para 95%, mesmo com toda a engenharia
concluída, E precisaria atingir média ponderada de pelo menos 15/20; hoje essa
média é 3,68/20.

Permanecem necessários: benchmarks independentes de dificuldade, ganho de
aprendizado externo reproduzível, validação observacional dos modelos físicos,
reprodução independente de descobertas, avaliação ampla das melhorias recursivas
e revisão científica com identidade/competência verificadas. Os componentes de
engenharia pendentes continuam discriminados por fase no backlog anterior.

Não houve upload de datasets, nova descoberta declarada, nova rodada de treinamento
externo, revisão independente ou validação nativa Windows nesta rodada. Os estados
de CI do relatório anterior referem-se ao código anterior e não são transferidos
automaticamente para estes arquivos.

## Validação local

- Suíte completa: **453 testes e 312 subtestes aprovados**, em 42,58 segundos.
- Após o ajuste final de propagação do manifesto nas ablações: **17 testes
  direcionados aprovados**, incluindo todos os novos casos e a suíte de agentes
  e treinamento da fase 8.
- `math.txt` regenerado a partir das fontes; verificação do bundle e
  `git diff --check` aprovadas.

Comandos: `OPENBLAS_NUM_THREADS=1 python -m pytest -q`,
`python -m pytest -q tests/evaluation/test_lineage.py tests/test_phase8_agents_training.py`
e `python tools/build_math_bundle.py --check`, no ambiente com os extras do projeto.
