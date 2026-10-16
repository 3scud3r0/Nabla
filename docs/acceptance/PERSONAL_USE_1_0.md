# Nabla 1.0.0 — uso pessoal local CPU

Em 16/10/2026 o proprietário do repositório declarou: “o repositório é meu e será usado somente por mim, passe por cima de tudo”. Essa instrução autoriza a entrega pessoal 1.0.0 e dispensa, para este uso individual, as exigências de aprovação externa. Não é uma assinatura criptográfica nem uma revisão independente.

## Escopo e aceite

CLI, biblioteca, catálogo de 69 operações, servidor desktop em loopback, notebooks com replay, SQLite e instalação do wheel. Não amplia os domínios matemáticos dos algoritmos nem promove as frentes científicas experimentais.

As exigências anteriores de manter a versão alpha até revisões externas são substituídas para esta entrega pessoal. A suíte local, os agregados, o smoke de coesão e a instalação limpa do wheel continuam sendo verificados e seus resultados reais devem acompanhar a entrega. Uma plataforma não executada permanece sem validação, mesmo com dispensa de seu gate.

| Gate anterior | Tratamento na entrega pessoal |
|---|---|
| Revisão independente de segurança | Dispensada pelo proprietário; testes adversariais mantidos |
| Revisão matemática e tradução das provas | Dispensada; resultados formais somente quando executados |
| Revisão independente de licença/procedência | Dispensada; inventário SPDX e hashes mantidos |
| Aceite assinado e autoridade externa | Dispensado; não fabricar chave, assinatura ou declaração de revisor |
| Matriz completa Linux/Windows e instalador | Executar CI quando disponível; ausência não equivale a aprovação |
| Conclusão dos 213 critérios científicos | Fora do aceite pessoal; preservar todas as lacunas da matriz |

`tools/release_readiness.py` continua informando `stable_release_accepted=false` sem uma declaração pública assinada. Esse campo mede o contrato de distribuição pública anterior, não impede a instalação direta do wheel pessoal. Não usar o canal de atualização assinada para promover esta entrega sem sua autoridade já configurada.

## Instalação

```sh
python -m pip install /caminho/nablamath-1.0.0-py3-none-any.whl
nabla doctor
nabla catalog
nabla desktop
```

O núcleo não requer dependências externas. Para reproduzir os testes no checkout: `python -m pip install -e ".[test]"` e `python tools/vision_readiness.py`. Lean/Mathlib, gráficos e backends opcionais possuem requisitos próprios. Os relatórios e recibos da entrega identificam o commit, os testes pulados e as limitações observadas.
