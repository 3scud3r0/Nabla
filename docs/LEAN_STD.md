# Provas racionais com Lean Std

`lean-std` acrescenta uma rota de provas pelo kernel Lean 4.34.0, usando a
biblioteca padrão da toolchain fixada em `lean/lean-toolchain`. Não requer
Mathlib nem substitui a integração Mathlib existente.

```sh
.venv/bin/nabla prove '(x+1)*(x-1)' 'x*x-1' --backend lean-std --output .nabla/polynomial-proof.json
.venv/bin/nabla check-formal .nabla/polynomial-proof.json
.venv/bin/nabla prove 'x/x' '1' --backend lean-std --output .nabla/division-proof.json
.venv/bin/nabla prove 'x' '2*x' --relation le --assumption 'x >= 0' --backend lean-std
```

Use destinos novos para preservar evidências. A API Python é
`nablamath.formal.prove_with_std(FormalStatement, project, timeout=30)`.
`std_source(statement)` permite inspecionar a fonte gerada. O certificado salva
o enunciado, a fonte, hashes, versão do compilador e lista de axiomas. A checagem
regenera a fonte e executa novamente o Lean; um hash recalculado ou um campo
`formal_proof=true` não substitui a execução.

A tradução aceita somente ASTs racionais tipadas. Variáveis tornam-se `Rat`;
relações e hipóteses conservam o contrato `FormalStatement`. Divisões e potências
não positivas carregam as obrigações de domínio da expressão original. Em
`x/x=1`, o teorema exige explicitamente `x ≠ 0`.

Enunciados fechados usam `decide +kernel`; enunciados com variáveis usam `grind`.
Para desigualdades, o gerador pode fornecer fatos auxiliares de não negatividade
de quadrados, produtos e diferenças dos extremos de um intervalo. Cada fato é
um lema provado no Lean, não uma hipótese nova ou um resultado aceito do Python.
Há no máximo 128 fatos auxiliares por tradução, em ordem determinística.
Ambos geram provas verificadas pelo kernel. Não há `native_decide`, snippets
Lean fornecidos pelo usuário, axiomas adicionados ou admissions. A saída de
`#print axioms` precisa existir e conter somente `propext`, `Classical.choice`
e `Quot.sound` quando necessários. A ausência da auditoria impede sucesso.

O compilador deve corresponder à versão fixada; `LEAN_PATH` e `LEAN_SRC_PATH`
herdados não são usados. Timeouts são de 1–300 segundos, há limites de heartbeats
e recursão, e o encerramento por timeout termina o grupo de processos em POSIX.
Esses controles não são um sandbox para código Lean arbitrário, que a API não
aceita.

Resultados distinguem `proved`, `failed`, `timeout`, `unavailable` e
`rejected_axioms`. Uma falha de busca não demonstra falsidade. Uma prova com
hipóteses contraditórias prova somente a implicação exibida: não comprova que
as hipóteses sejam satisfatíveis. Não há alegação de correspondência automática
com texto natural, prova de limites analíticos ou conclusão de F3.

Instale a distribuição oficial indicada em `scripts/setup_formal.sh`, mantendo
a checagem SHA-256 do arquivo. Para este backend, basta extrair a toolchain;
o build Mathlib desse script não é necessário. O backend encontra o executável
retido em `/workspace/.tools/lean/lean-4.34.0-linux/bin/` ou junto ao `lake`
disponível no PATH. Não substitua checksums para contornar falhas.

```sh
OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_lean_std.py
```

Os testes executam o kernel em aritmética fechada, identidades polinomiais,
divisão sob hipóteses e implicações lineares; também verificam rejeição de
enunciados falsos, fontes adulteradas, recibos rehasheados, axiomas não permitidos
e timeouts. Sem a toolchain, testes de kernel são explicitamente pulados.
