# Nabla 1.0.0 — entrega pessoal local CPU

Código e PR: https://github.com/3scud3r0/Nabla/pull/21

Commit validado: `52b5d908f7ccab8766ead10f1cf6ceb6783e4133`. Python 3.12.14, Linux. Checkout limpo.

- Suíte final: **2426 passed, 2 skipped, 17 warnings, 390 subtests passed in 324.18s (0:05:24)**.
- Todos os checks de engenharia do relatório obrigatório passaram no mesmo commit, sem mudança de fontes durante a execução.
- 69 operações verificadas na biblioteca, na CLI instalada e no servidor HTTP real, com referências explícitas; notebook de 69 células reexecutado.
- 176 casos independentes adicionais, oito famílias Forge com duas estratégias, hipótese sintética com oito pontos reservados e nove controles negativos.
- 16 modelos físicos idealizados; equação do calor com razão de convergência 3.997841.
- Três proposições de aplicação provadas por Lean e uma falsa rejeitada; **30.000/30.000** teoremas do corpus passaram no kernel com auditoria de axiomas.
- Wheel verificado e instalado offline em venv isolada; a demonstração completa rodou contra esse pacote instalado.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `nablamath-1.0.0-py3-none-any.whl` | Pacote instalável, CLI e desktop |
| `Nabla-1.0.0-source.zip` | Fontes exatas do commit, incluindo código dos experimentos |
| `Nabla-1.0.0-science.zip` | Notebook, relatórios, dados, provas, SVG/HTML, bancos e código de reprodução |
| `Nabla-1.0.0-evidence.zip` | Relatório completo, JUnit, benchmarks, auditoria dos 30 mil teoremas e falhas originais preservadas |
| `release-manifest.json` | Resultados, escopo, skips e dispensas |
| `wheel-verification.json` | Integridade e instalação limpa do wheel |
| `metadata/` | Inventário SPDX, proveniência local e hashes |
| `SHA256SUMS` | SHA-256 dos arquivos entregues |

## Instalar e usar

Em um ambiente Python 3.10–3.14, baixe o wheel e execute:

```sh
python -m pip install --no-index --no-deps nablamath-1.0.0-py3-none-any.whl
nabla doctor
nabla catalog
nabla desktop
```

Para reproduzir o experimento, extraia as fontes e use o Python em que instalou o wheel:

```sh
python examples/science/reproduce.py resultados-novos
```

O destino deve ser novo. O núcleo não requer bibliotecas opcionais. As provas Lean reais podem ser exigidas com `--formal-project lean` depois de preparar a toolchain fixada; as instruções completas estão em `examples/science/README.md`.

## Escopo e dispensas

O proprietário autorizou a versão pessoal e dispensou aceites externos. Isso está registrado no código. Revisões independentes e assinatura de publicador não foram fabricadas; o campo público `stable_release_accepted` permanece falso sem a autoridade exigida pelo canal público de atualização assinada. A instalação direta deste wheel pessoal funciona sem esse canal.

Os dois skips são os backends opcionais de GPU, fora do perfil CPU. Windows e as outras versões de Python não foram executados neste host; a CI remota enfileirada não é aprovação. Consulte `github-actions.json` para o snapshot remoto.

A matriz científica conserva seus 213 itens parciais e o benchmark aprendido original conserva seu resultado real. Os experimentos e o corpus finito não provam correção universal, descoberta inédita, validação com dados físicos reais nem conclusão de toda a visão científica. Os resultados detalhados estão preservados, inclusive limites, falhas originais e referências.
