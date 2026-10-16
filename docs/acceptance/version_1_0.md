# Aceite do perfil local CPU 1.0

> A entrega pessoal 1.0.0 autorizada pelo proprietário segue [PERSONAL_USE_1_0.md](PERSONAL_USE_1_0.md). As condições de manter a versão alpha e de obter aceite externo abaixo permanecem como histórico do contrato de distribuição pública e são dispensadas para uso pessoal. Resultados técnicos não são presumidos.


O escopo de implementação desta entrega é o `vision1.md`: 152 arquivos de
produto/aceite e 60 unidades Lean geradas. A visão de longo prazo continua com
seus 213 requisitos e evidências próprias. A instrução de implementação autoriza
o preparo deste perfil; não constitui assinatura de uma autoridade de release
nem substitui revisores independentes.

O perfil oferece CLI/desktop local, cálculo delimitado, notebooks reexecutáveis,
SQLite com backup/restore e artefatos verificáveis. A superfície congelada está em
[API_STABILITY.md](../API_STABILITY.md) e `nablamath/public_api.json`. Linux e
Windows/Python 3.10–3.14 são a matriz alvo; macOS é experimental. Todas as cinco
versões de Python devem executar na CI do commit candidato. Os SDKs permanecem
experimentais. GPU, federação pública, código hostil e descoberta geral ficam
excluídos. Std e Mathlib só são considerados disponíveis após provas reais na
toolchain fixada, com revisão das hipóteses e auditoria dos axiomas.

## Procedimento reproduzível

```sh
python -m pip install -e '.[test]'
python tools/release_readiness.py --output .nabla/release-inventory.json
python tools/build_math_bundle.py
python tools/build_nabla_bundle.py
python tools/vision_readiness.py
python -m pip wheel --no-deps --wheel-dir .nabla/wheels .
python tools/release_readiness.py --wheel .nabla/wheels/nablamath-0.1.0a1-py3-none-any.whl --output .nabla/release-wheel.json
```

Use `.venv/bin/python` no ambiente do projeto. O nome do wheel acompanha a versão
em `pyproject.toml`; não renomeie o arquivo manualmente. A instalação de teste
usa `--no-index --no-deps`, execução isolada e diretório fora do checkout. A etapa
formal é preparada separadamente por `scripts/setup_formal.sh`; o cache usa os
imports necessários e o manifesto fixado, sem atualização livre. Sem cache,
`NABLA_FORMAL_CACHE=source` faz o build da mesma revisão e pode levar mais tempo.

## Gates e responsáveis

| Gate | Evidência necessária | Responsável pelo aceite |
|---|---|---|
| Fontes e contratos | 212 caminhos, catálogo e schemas conferidos | revisão de código |
| Testes/benchmarks | relatório completo sem falha obrigatória; skips classificados | CI e mantenedor |
| Plataformas | jobs Linux/Windows, Python 3.10/3.11/3.12/3.13/3.14 do SHA exato | CI e mantenedor |
| Formal | compilação fixada, provas reais e auditoria de axiomas | CI e revisor matemático |
| Significado das provas | revisão de enunciados, domínios e hipóteses | revisor matemático independente |
| Wheel | RECORD, instalação limpa e smoke do mesmo artefato | CI |
| Windows | instalar, usar, reinstalar e desinstalar; upgrade entre releases separado; preservar dados pessoais | CI Windows e mantenedor |
| Dados | migração/restore, licença e procedência | testes e revisor de dados |
| Segurança | contratos adversariais e revisão do escopo/dependências | CI e revisor independente |
| Distribuição | SBOM, hashes e proveniência do artefato publicado | autoridade configurada |
| Publicação | todos os gates e aceite nominal registrados | mantenedor autorizado |

`release_readiness.py` registra cada caminho e seu aceite literal. Presença e
SHA-256 não significam implementação correta nem aprovação daquele aceite. Os
checks locais não autenticam revisores. `--require-stable` retorna 2 sem aceite assinado. Após revisão, o mantenedor
prepara uma declaração `nabla.release-acceptance.v1` com os 13 gates, suas
referências HTTPS e hashes, vinculada a commit, versão e wheel. O argumento
`--acceptance` de `build_release_metadata.py` incorpora a declaração ao SBOM.
A assinatura do publicador cobre o hash desse SBOM; `signed_release.py` recusa
a preparação/ativação de versões finais 1.x sem todos os gates aprovados.
`release_readiness.py --signed-release ENVELOPE --trust-store TRUST --artifacts DIR`
verifica uma autoridade já configurada, os artefatos e o checkout limpo do SHA
exato. Não inscreve chaves nem cria aprovações. A assinatura autentica a declaração
do publicador; o programa não refaz uma revisão humana nem consulta as URLs.

A versão permanece alpha até os gates obrigatórios estarem aprovados. Não alterar
para `1.0.0` nem publicar tag estável a partir apenas de uma suíte verde. Após o
aceite, atualizar conjuntamente `pyproject.toml`, `__init__.__version__`,
`compatibility.json` e notas; reconstruir e verificar os artefatos da versão final.
A CI Windows usa essa versão para o instalador e não publica automaticamente uma
alpha ao receber um merge.

Os jobs e revisões devem ser associados ao SHA final do PR/release. Logs de uma
revisão anterior são diagnóstico histórico, não aprovação de bytes posteriores.
Hashes/RECORD detectam corrupção; autenticidade do publicador requer autoridade
configurada e verificação independente pelo destinatário.
