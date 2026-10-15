# Evidências da expansão de maturidade — 15/10/2026

Estes artefatos conservam resultados positivos e negativos. Não demonstram ganho
de um modelo de fronteira, novidade científica ou validação física experimental.

- `longley.json`: regressão racional exata comparada com valores certificados NIST
  de fonte fixada em `benchmarks/fixtures/longley-nist/manifest.json`. Maior erro
  relativo de coeficientes: 2,432568075499757e-15. Dataset observado macroeconômico;
  validação numérica, sem inferência causal ou teste fora da amostra.
- `multimodal/`: rede NumPy de duas torres, diagramas 2×16×16 pixels e seis
  coeficientes de equações; fusão 48→16→1, tanh/sigmoid, Adam. Treino 256 exemplos,
  teste 128, três seeds, 1000 passos por modelo, nove checkpoints NPZ sem pickle.
  O teste exclui soluções equivalentes de treino e usa faixa de coeficientes
  diferente. Não é corpus externo publicado nem treinamento de LLM.
- Acurácias (acertos/128) para equação / imagem / combinação: seed 11: 86/99/97;
  seed 23: 78/99/96; seed 37: 88/101/100. Imagem sozinha supera a combinação nas
  três seeds. O resultado da ablação é preservado, sem alegar superioridade da fusão.
- `portfolio/`: comparações exploratórias, não pré-registro independente. Contra
  baseline uniforme `exact`, seis melhorias/18 empates foram insuficientes e o
  gate rejeitou. Contra baseline uniforme `alternate` (mais fraco explicitamente),
  houve 18 melhorias/seis empates, zero regressões e redução mediana de 36,2454%
  nas linhas Python medidas; p=3,8147e-6, alpha corrigido=0,00625. Promoção e rollback
  foram exercitados. Não equivale a ganho contra o melhor solver nem RSI geral.

As imagens dos dados são calculadas apenas das equações, sem marcador da solução.
O verificador reconstitui pixels, respostas exatas e todas as previsões dos pesos:

```python
from nablamath.training.multimodal_network import verify_multimodal_study
assert verify_multimodal_study('benchmarks/results/maturity-expansion/multimodal')
```

Esse replay confere checkpoints e métricas; não é treinamento independente.
O protocolo foi escrito antes de treinar essa execução, mas o desenho é local e
exploratório. As seeds e faixas não comprovam ausência de toda contaminação.
A arquitetura e o corpus sintético são distribuídos sob a licença MIT do projeto;
a referência Longley conserva proveniência e licença pública declarada pela fonte.

`multimodal/comparisons.json` conserva as seis comparações pareadas exploratórias
(combinação versus cada modalidade, nas três seeds). Nenhuma é significativa após
Bonferroni para seis comparações; não há ganho estatístico demonstrado da fusão.
`integrated.json` registra o laboratório com os três perfis editoriais, figuras
ligadas ao modelo, prova Lean e persistência transacional.
