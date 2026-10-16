# Limites racionais laterais

O perfil `rational-sided-limit-v1` calcula limites de expressões racionais em
`x`, em pontos racionais e em `+infinity`/`-infinity`. A API anterior `limit`
permanece disponível com seu contrato original.

```python
from nablamath.calc.session import CalculationSession
from nablamath.math.calculus.limits import verify_rational_limit

session = CalculationSession()
calculation = session.execute('rational_limit', source='1/x', point=0)
receipt = calculation.to_data()['result']
assert receipt['result']['status'] == 'does_not_exist'
assert receipt['left']['status'] == 'negative_infinity'
assert receipt['right']['status'] == 'positive_infinity'
assert verify_rational_limit(receipt)
```

`direction='left'` ou `'right'` seleciona um limite lateral em ponto finito.
`direction='both'` compara ambos; infinitos de sinais opostos não são aceitos
como um limite bilateral. Infinitos iguais são identificados explicitamente,
sem confundi-los com valores reais finitos. Em pontos infinitos, somente `both`
é permitido: o próprio ponto já determina a extremidade.

O resultado distingue `finite`, `positive_infinity`, `negative_infinity` e
`does_not_exist`. Valores finitos são strings racionais exatas. O testemunho
registra a forma racional normalizada e as valorações locais ou os graus e
coeficientes líderes. O verificador reexecuta o cálculo e compara todo o recibo;
recalcular um hash após adulterar um resultado não o valida. Sessões e notebooks
suportam o replay da operação.

As obrigações de domínio da expressão original são conservadas separadamente.
Por exemplo, `(x**2-1)/(x-1)` tem limite 2 em 1, mas `defined_at_point=False`.
Expressões com domínio vazio são recusadas, inclusive `(x-x)**0`. O contrato
de potências zero segue as obrigações conservadoras já adotadas pelo Nabla.

O perfil reutiliza os limites da normalização racional: grau até 64, potências
inteiras de módulo até 16 por nó, coeficientes de até 4096 bits e entrada até
4096 caracteres. Pontos finitos usam o contrato racional de até 256 bits.
Funções transcendentes, pontos irracionais, floats e outras variáveis não são
suportados. Não há sondagem numérica, checagem de kernel Lean nem alegação de
validação externa ou de conclusão de F1/F3.

Verificação e comparação independente de implementação:

```sh
OPENBLAS_NUM_THREADS=1 .venv/bin/python -m pytest -q tests/test_rational_sided_limits.py
.venv/bin/python tools/benchmark_rational_limits.py --output .nabla/limits-conformance.json
```

Use destino novo para preservar resultados anteriores. O benchmark compara 208
pedidos públicos e fixos com SymPy, conserva cada resultado e erro, identifica
protocolo, fontes e versões e retorna falha em qualquer divergência. Não é um
holdout privado, avaliação institucional independente ou medida de dificuldade.
Os testes também cobrem limites bilaterais, domínio, adulteração e replay.
