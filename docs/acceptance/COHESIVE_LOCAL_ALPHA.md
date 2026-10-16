# Primeiro Nabla coeso — perfil local alpha

> A entrega pessoal 1.0.0 autorizada pelo proprietário segue [PERSONAL_USE_1_0.md](PERSONAL_USE_1_0.md). As condições de manter a versão alpha e de obter aceite externo abaixo permanecem como histórico do contrato de distribuição pública e são dispensadas para uso pessoal. Resultados técnicos não são presumidos.


**Estado:** candidato de desenvolvimento **0.1.0a1**, ainda sujeito aos gates de integração, plataforma, segurança e release. Não é versão estável 1.0, produto de descoberta científica geral nem substituto de revisão matemática independente.

Este documento descreve o **caminho único** de uso do Nabla como produto local CPU. O restante do repositório conserva projetos de pesquisa e integrações experimentais sem ampliá-los automaticamente para a primeira versão coesa.

## O que é um produto coeso neste perfil

A interface de linha de comando, o desktop local e os notebooks usam o mesmo motor \`CalculationSession\` e **o mesmo catálogo de operações**. A documentação e o contrato de instalação incluem explicitamente as operações disponíveis. Os recibos de cálculo são serializados com schema 1, \`content_id\` e reexecução independente pelo notebook; \`formal_proof=false\` não confunde evidência computacional com prova Lean. A interface web usa token de sessão aleatório, valida Host/Origin e mantém as operações locais.

| Entrada | Comando/API | Contrato |
|---|---|---|
| Instalação | \`python -m pip install -e .\` | Núcleo sem dependência obrigatória de rede/IA |
| Diagnóstico | \`nabla doctor\` | Ambiente e integrações opcionais, sem alegar operação verificada pelo mero PATH |
| Descoberta | \`nabla catalog\`, \`GET /api/catalog\` | Mesmo catálogo registrado em \`public_api.json\` |
| Cálculo | \`nabla calc OP --arguments JSON\`, \`POST /api/calculate\` | Mesmos argumentos, domínios e resultado exato/reprodutível |
| Notebook | \`--notebook primeiro.json\`, \`nabla replay-notebook primeiro.json\` | Replay determinístico e hash de recibos |
| UI local | \`nabla desktop\` | Roda em \`127.0.0.1\`, calcula sem publicação automática |
| Expressões e SQLite | \`nabla run\`, cartão 01 do desktop | API antiga de expressões e persistência preservada |
| Arquivos agregados | \`tools/build_math_bundle.py\`, \`tools/build_nabla_bundle.py\` | Construídos a partir de fontes canônicas, com índices/hashes verificáveis |
| Aceite técnico rápido | \`python tools/cohesion_smoke.py\` | Verifica instalação, contrato, matemática, CLI, notebook e adapter do desktop |

**Separação intencional de persistência:** o SQLite anterior armazena registros de expressões cuja reexecução conhece esse schema; cálculos científicos multidomínio exibidos no desktop geram recibos, mas **não** são inseridos na tabela antiga. Guardá-los ali falsificaria a capacidade de replay dos registros. Quem deseja persistir e reexecutar cálculos avançados usa \`--notebook\` na CLI; persistência tipada unificada pode ser desenvolvida em uma migração futura.

## Primeiro uso reproduzível (Linux/macOS/Windows com Python)

\`\`\`sh
python -m pip install -e ".[test]"
nabla doctor
nabla catalog
nabla calc analysis_integral --arguments '{"coefficients":[0,0,1],"lower":0,"upper":1}' --notebook primeiro-nabla.json
nabla replay-notebook primeiro-nabla.json
nabla desktop
\`\`\`

No painel local, o cartão **Catálogo científico integrado** consulta as operações instaladas, permite editar argumentos JSON e mostra o recibo completo. Para um exemplo com validação de domínio:

\`\`\`sh
nabla calc ff_extension --arguments '{"prime":2,"modulus":[1,1,1],"element":[0,1]}'
nabla calc graph_max_flow --arguments '{"vertices":["s","t"],"edges":[["s","t","3/2"]],"source":"s","sink":"t"}'
\`\`\`

Se uma operação rejeitar um domínio ou limite, a resposta é um erro explícito; algoritmos de custo exponencial, como atribuição ótima, possuem orçamentos fechados.

## Critérios objetivos de conclusão

O candidato só pode ser chamado de **primeira versão coesa instalada e testada** quando:

1. \`python tools/cohesion_smoke.py --check-source-bundles\` terminar com status 0 no checkout exato.
2. Os testes de contrato, matemática exata, CLI, notebook, HTTP desktop e regressão forem verdes, incluindo os cenários negativos de segurança e domínio.
3. \`python -m pytest -q\` passar na matriz alvo de Python/OS, ou qualquer falha/skipping for documentado sem alegação de suporte que não exista.
4. \`python tools/build_math_bundle.py --check\` e \`python tools/build_nabla_bundle.py --check\` passarem com os **arquivos realmente regenerados e commitados**, sem enfraquecer a auditoria.
5. \`python tools/release_readiness.py\` e smoke de wheel instalado em venv isolada passarem no commit candidato.
6. As dependências opcionais e algoritmos formais só forem anunciados como disponíveis quando as ferramentas fixadas executarem seus testes reais.

**A versão estável 1.0 tem gates adicionais e independentes:** os 212 caminhos de \`vision1.md\`, revisão formal de significado das provas, validação Windows, assinatura/autorização do publicador e demais etapas em [version_1_0.md](version_1_0.md). **Não alterar o versionamento nem publicar uma tag 1.0** apenas por haver integração funcional.

## Como registrar evidência

\`\`\`sh
python tools/cohesion_smoke.py --output .nabla/cohesion.json
python -m pytest -q tests/math/test_exact_laboratory.py tests/math/test_advanced_exact_integration.py tests/integration/test_advanced_exact_notebook.py tests/integration/test_cohesive_cli.py tests/integration/test_scientific_desktop_cohesion.py
python tools/build_math_bundle.py
python tools/build_nabla_bundle.py
python tools/cohesion_smoke.py --check-source-bundles
python tools/release_readiness.py
\`\`\`

O arquivo \`.nabla/cohesion.json\` é local; usar destino novo em cada corrida. O smoke não possui autoridade para certificar o projeto independentemente de CI e revisão externa. Em GitHub Actions, o workflow **Cohesive local alpha** reproduz esse caminho em Linux/Windows e Python 3.10/3.13; a matriz completa de 3.10–3.14 continua em **Python core**. Runners enfileirados não significam testes aprovados.

## Limites explícitos da primeira versão

É um laboratório CPU local com motor de expressões, catálogo finito de cálculo científico e recibos. GPU, pesquisa autônoma geral, P2P, sandbox de código hostil, inferência científica a partir de dados reais e certificados Lean universais **não fazem parte** dessa promessa de produto. Os módulos dessas frentes permanecem disponíveis nos respectivos perfis experimentais, com evidência específica.
