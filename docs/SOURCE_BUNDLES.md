# Fontes consolidadas na raiz

O checkout mantém duas visões textuais do código:

- `math.txt`: fontes matemáticas selecionadas pelo gerador existente.
- `NABLA.TXT`: fontes e configurações de todo o projeto, incluindo runtime,
  serviços, SDKs, testes, ferramentas, site, instalador e fontes legadas.

Esses arquivos são agregações para leitura e distribuição. Não são executáveis
compilados, instaladores nem uma nova fonte canônica para editar o projeto.
Altere os arquivos originais e regenere os bundles. Um PR com alterações de código que não atualize os bundles deve permanecer como rascunho ou ter checks de integridade não aprovados; executar `--check` depois de recriar os arquivos não substitui o commit dos arquivos regenerados. O primeiro perfil coeso tem [critérios de aceite próprios](acceptance/COHESIVE_LOCAL_ALPHA.md).

```sh
.venv/bin/python tools/build_math_bundle.py
.venv/bin/python tools/build_nabla_bundle.py
.venv/bin/python tools/build_math_bundle.py --check
.venv/bin/python tools/build_nabla_bundle.py --check
```

O gerador completo usa o índice Git e arquivos novos não ignorados. Conserva
bytes originais, finais de linha e ausência de newline final. Cada arquivo tem
caminho, tamanho, encoding e SHA-256; um manifesto identifica o conjunto.
Fontes não UTF-8 são representadas em base64, sem perda dos bytes originais.
O enquadramento por tamanho evita confundir um marcador escrito dentro de uma
fonte com o fim de seu bloco. `--check` detecta qualquer diferença em relação
ao checkout atual. A gravação publica o arquivo completo por substituição atômica.
`NABLA.TXT` usa `-text` nos atributos Git para preservar os finais de linha dos
blocos embutidos; uma normalização automática invalidaria seus hashes.

Não são incluídos dependências instaladas, caches, dados locais ignorados,
resultados de benchmarks em formatos de dados, ativos binários ou prosa da
documentação. Fontes de código preservadas em diretórios históricos continuam
incluídas. Licenças e configurações declarativas relevantes acompanham o código.
Links simbólicos de fontes são recusados para evitar seguir arquivos externos
ao conjunto declarado. Os próprios bundles não são embutidos recursivamente.

O workflow `Canonical source bundle integrity` executa os dois checks em pushes
e PRs, inclusive na `main`. Ele valida os arquivos commitados no SHA do candidato,
sem criar commits automáticos posteriores. Regenere e inclua ambos os agregados
no mesmo commit das alterações de fontes.

## Ampliação do corpus formal

O protocolo `rational-kernel-conformance-v2` amplia o corpus público de 5.000 para
30.000 teoremas. As dez famílias permanecem delimitadas: aumentou a cobertura
paramétrica, não o número de famílias ou de algoritmos matemáticos.

São 120 índices do primeiro coeficiente e 25 do segundo, em 60 arquivos Lean
com no máximo 500 teoremas por arquivo. Cada teorema recebe sua auditoria de
axiomas. O runner só aceita uma unidade quando o Lean termina com sucesso,
todos os nomes esperados aparecem e nenhum axioma fora da lista é usado.

```sh
.venv/bin/python tools/rational_proof_corpus.py --check
.venv/bin/python tools/rational_proof_corpus.py --verify .nabla/corpus-30000-novo --workers 4
```

Use um destino de evidência novo. A divisão em unidades menores limita o custo
por processo e conserva falhas separadamente; não descarta teoremas difíceis.
As fontes e manifestos anteriores são arquivados antes de `--refresh` substituir
arquivos gerados intactos. Não há sobrescrita automática de edição manual.

Essa expansão acrescenta mais de 100 mil linhas Lean geradas, excluindo
`math.txt`, `NABLA.TXT`, documentação e manifesto. Linhas agregadas nos bundles
são cópias e não devem ser contadas como implementações novas.

Trinta mil instâncias de dez famílias não demonstram conclusão das 213 exigências
da visão. O estado de engenharia depende dos testes atuais; aceitação científica
também depende das revisões, experimentos e demais evidências apropriadas.
