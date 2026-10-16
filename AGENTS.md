# Verificação obrigatória da visão do Nabla

Em toda entrega que altere código, testes, contratos ou critérios de aceitação,
execute, antes de concluir:

```bash
python tools/vision_readiness.py
```

Use o Python do ambiente do projeto (`.venv/bin/python` quando aplicável).
O comando produz `.nabla/vision-readiness/<execução>/REPORT.md` e `report.json`,
com todos os 213 critérios, testes atuais, benchmarks e pendências. Leia os
resultados e informe falhas, testes pulados e bloqueios na entrega. Não promova
requisitos nem alegue conclusão científica a partir de testes verdes.

`--inventory-only` serve para consultar lacunas durante o trabalho; não substitui
a execução completa na entrega. Se algum pré-requisito impedir a execução,
registre o impedimento e não declare que a verificação passou. Não faça retries
para selecionar o melhor resultado de benchmark. Correções devem ter sua falha
original preservada e uma nova execução identificada.

Para tarefas apenas explicativas, consulte o relatório disponível e a matriz;
não é necessário repetir a suíte sem alterações. Não crie worktrees durante
onboarding salvo instrução explícita do usuário.
