"""Canonical rational objects; presentation and generator seeds are not semantics."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json

from ..expression import Binary, Expr, Number, Symbol


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def rational(value: object) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, str, Fraction)):
        raise ValueError("Use inteiros ou frações exatas, não floats")
    if isinstance(value, str) and len(value) > 128:
        raise ValueError("Racional excede o limite de representação")
    result = Fraction(value)
    if max(abs(result.numerator).bit_length(), result.denominator.bit_length()) > 256:
        raise ValueError("Racional excede 256 bits")
    return result


@dataclass(frozen=True)
class PolynomialSpec:
    """Coefficients in ascending powers, normalized with no trailing zeroes."""
    coefficients: tuple[Fraction, ...]

    def __post_init__(self) -> None:
        if not 1 <= len(self.coefficients) <= 33:
            raise ValueError("Polinômio requer de 1 a 33 coeficientes")
        values = tuple(rational(value) for value in self.coefficients)
        while len(values) > 1 and not values[-1]:
            values = values[:-1]
        object.__setattr__(self, "coefficients", values)

    def evaluate(self, value: Fraction | int) -> Fraction:
        value = rational(value)
        result = Fraction(0)
        for coefficient in reversed(self.coefficients):
            result = result * value + coefficient
        return result

    def to_expr(self) -> Expr:
        expression: Expr = Number(self.coefficients[-1])
        for coefficient in reversed(self.coefficients[:-1]):
            expression = Binary("+", Binary("*", expression, Symbol("x")), Number(coefficient))
        return expression

    def to_data(self) -> list[str]:
        return [str(value) for value in self.coefficients]


@dataclass(frozen=True)
class ScientificTask:
    family: str
    coefficients: tuple[Fraction, ...] = ()
    matrix: tuple[tuple[Fraction, ...], ...] = ()
    rhs: tuple[Fraction, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("Versão de contrato não suportada")
        if self.family == "polynomial_integral":
            if self.matrix or self.rhs:
                raise ValueError("Integral não admite matriz")
            object.__setattr__(self, "coefficients", PolynomialSpec(self.coefficients).coefficients)
        elif self.family == "linear_system":
            n = len(self.matrix)
            if self.coefficients or not 1 <= n <= 8 or len(self.rhs) != n:
                raise ValueError("Sistema requer dimensão de 1 a 8 e vetor compatível")
            if any(len(row) != n for row in self.matrix):
                raise ValueError("Matriz deve ser quadrada")
            object.__setattr__(self, "matrix", tuple(tuple(rational(v) for v in row) for row in self.matrix))
            object.__setattr__(self, "rhs", tuple(rational(v) for v in self.rhs))
        else:
            raise ValueError("Família científica não suportada")

    def to_data(self) -> dict:
        return {"schema_version": self.schema_version, "family": self.family,
                "coefficients": [str(v) for v in self.coefficients],
                "matrix": [[str(v) for v in row] for row in self.matrix],
                "rhs": [str(v) for v in self.rhs], "domain": "rational", "variable": "x"}

    @property
    def content_id(self) -> str:
        return fingerprint(self.to_data())

    @classmethod
    def from_data(cls, data: dict) -> ScientificTask:
        expected = {"schema_version", "family", "coefficients", "matrix", "rhs", "domain", "variable"}
        if not isinstance(data, dict) or set(data) != expected or data["domain"] != "rational" or data["variable"] != "x":
            raise ValueError("Contrato científico inválido")
        if (not isinstance(data["coefficients"], list) or len(data["coefficients"]) > 33
                or not isinstance(data["matrix"], list) or len(data["matrix"]) > 8
                or not all(isinstance(row, list) and len(row) <= 8 for row in data["matrix"])
                or not isinstance(data["rhs"], list) or len(data["rhs"]) > 8):
            raise ValueError("Dimensoes serializadas invalidas")
        return cls(data["family"], tuple(data["coefficients"]), tuple(tuple(r) for r in data["matrix"]),
                   tuple(data["rhs"]), data["schema_version"])


@dataclass(frozen=True)
class SemanticExpression:
    """Meaning is an AST with declared scalar types; source notation is not identity."""
    expression: Expr
    variable_types: tuple = ()
    schema_version: int = 1

    def __post_init__(self):
        from .types import ScientificType,ScalarDomain
        from .units import infer_unit
        if self.schema_version!=1:
            raise ValueError('Versao semantica nao suportada')
        names=[]
        def visit(node,depth=0):
            if depth>32:
                raise ValueError('Expressao semantica profunda demais')
            if isinstance(node,Symbol):
                names.append(node.name)
                return 256
            if isinstance(node,Number):
                value=rational(node.value)
                return max(1,abs(value.numerator).bit_length(),value.denominator.bit_length())
            if isinstance(node,Binary):
                if node.op=='**' and (not isinstance(node.right,Number) or node.right.value.denominator!=1 or abs(node.right.value)>16):
                    raise ValueError('Expoente semantico limitado a inteiros de -16 a 16')
                left,right=visit(node.left,depth+1),visit(node.right,depth+1)
                bound=left*max(1,abs(node.right.value.numerator)) if node.op=='**' else left+right+2
                if bound>32768:
                    raise ValueError('Orcamento aritmetico semantico excedido')
                return bound
            raise ValueError('No semantico invalido')
        visit(self.expression)
        bindings=tuple(sorted(self.variable_types)) if self.variable_types else tuple((n,ScientificType()) for n in sorted(set(names)))
        if len(bindings)!=len(dict(bindings)) or set(dict(bindings))!=set(names):
            raise ValueError('Tipos devem declarar exatamente os simbolos livres')
        if any(t.shape or t.domain!=ScalarDomain.RATIONAL for _,t in bindings):
            raise ValueError('AST aritmetica requer escalares racionais')
        object.__setattr__(self,'variable_types',bindings)
        infer_unit(self.expression,{n:t.unit for n,t in bindings})

    @classmethod
    def parse(cls,source,variable_types=None):
        from ..expression import parse_expr
        return cls(parse_expr(source),tuple((variable_types or {}).items()))

    @property
    def obligations(self):
        from .obligations import domain_obligations
        return domain_obligations(self.expression)

    @property
    def result_type(self):
        from .types import ScientificType
        from .units import Unit,infer_unit
        unit=infer_unit(self.expression,{n:t.unit for n,t in self.variable_types})
        return ScientificType(unit=Unit(unit.dimensions))

    def to_data(self):
        from ..expression import to_data
        return {'schema_version':1,'expression':to_data(self.expression),
                'variable_types':{n:t.to_data() for n,t in self.variable_types},
                'result_type':self.result_type.to_data(),
                'obligations':[o.to_data() for o in self.obligations]}

    @property
    def content_id(self):
        return fingerprint(self.to_data())
