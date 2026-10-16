# Laboratório de matemática exata — escopo e contratos

Código: [laboratory.py](../../src/nablamath/math/exact/laboratory.py) · Testes: [test_exact_laboratory.py](../../tests/math/test_exact_laboratory.py).

Este módulo concentra algoritmos de **matemática exata delimitada** num arquivo de implementação de grande porte, com API pequena e agrupamento por responsabilidades. Amplia a cobertura computacional sem reivindicar resolver toda a matemática, generalizar automaticamente para números reais não racionais ou produzir provas Lean.

## Domínios implementados

| Área | Funções | Garantia declarada |
|---|---|---|
| Álgebra polinomial em Q[x] | Polynomial, gcd, Bézout, divisão euclidiana, fatores square-free | Identidades racionais exatas |
| Álgebra eliminatória | Sylvester/resultante, discriminante | Determinantes exatos para grau dentro do orçamento |
| Raízes reais | Sequência de Sturm, contagem e isolamento | Intervalos racionais com uma raiz real distinta por intervalo; falha explícita se o orçamento acabar |
| Aproximação algébrica | Lagrange, Hermite, forma de Bernstein | Interpolação exata e encerramento rigoroso do intervalo de valores |
| Álgebra linear | RREF, posto, sistema afim, núcleo, inversa, determinante, polinômio característico | Operações sobre matrizes racionais com aritmética exata |
| Teoria dos números | Teorema Chinês dos Restos generalizado | Compatibilidade ou contradição verificável de congruências |
| Sequências e combinatória | Berlekamp–Massey em Q, função geradora racional, matriz-árvore | Recorrência compatível com amostras e contagem exata de árvores de expansão |
| Probabilidade | Matriz fundamental de uma cadeia absorvente | Tempos médios exatos para estados transitórios racionais finitos |
| Otimização | Programação linear com caixa fechada | Ótimo racional e testemunho primal via enumeração de vértices |

## Limites e decisões

- Apenas `int`, `Fraction` e strings racionais são aceitos nas entradas de aritmética exata. `float` e `bool` são recusados.
- Até **129 coeficientes** por polinômio, **32 linhas/colunas** em matrizes, **4096 bits** por racional validado; inversão usa matriz aumentada de até 32 colunas.
- A contagem por Sturm exige extremos que não sejam raízes; a rotina de isolamento escolhe divisões não coincidentes com raízes e gera erro quando ultrapassa o limite de profundidade.
- Resultantes usam uma matriz de Sylvester limitada a 32 dimensões. O algoritmo não cobre polinômios arbitrariamente grandes.
- A enumeração de vértices de programação linear aceita **1–5 variáveis**, até **24 desigualdades explícitas**, caixas finitas e até **200.000 subconjuntos candidatos**. É exponencial e não apresenta certificado dual.
- A recorrência obtida por Berlekamp–Massey descreve a menor relação compatível com a sequência recebida. Não demonstra que o padrão se manterá fora da amostra.
- O módulo é inteiramente offline, não consulta serviços externos, não executa código fornecido como entrada e não introduz dependências de terceiros.

## Exemplo reproduzível

```python
from fractions import Fraction
from nablamath.math.exact import (
    Polynomial, polynomial_extended_gcd, isolate_real_roots,
    RationalMatrix, chinese_remainder, bounded_linear_program,
)

p = Polynomial((-2, 0, 1))           # x² - 2
intervals = isolate_real_roots(p)    # dois intervalos racionais
assert len(intervals) == 2

g, s, t = polynomial_extended_gcd(p, Polynomial((-1, 1)))
assert s * p + t * Polynomial((-1, 1)) == g

a = RationalMatrix(((1, 2), (3, 5)))
assert a @ a.inverse() == RationalMatrix.identity(2)

assert chinese_remainder(((2, 6), (5, 9))) == (14, 18)

optimum = bounded_linear_program(
    (3, 2), (((1, 1), 4),), ((0, 3), (0, 4))
)
assert optimum["optimum"] == "11"
```

## Como verificar

```sh
python -m pip install -e ".[test]"
python -m pytest -q tests/math/test_exact_laboratory.py
python -m pytest -q tests/regression/test_public_api.py
python -m pytest -q
```

O resultado de um teste não equivale a revisão matemática externa nem substitui formalização em Lean para afirmações que a exijam. A API está agrupada sob `nablamath.math.exact` para não alterar os exports globais existentes.
