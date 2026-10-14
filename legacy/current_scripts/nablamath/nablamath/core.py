from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Sequence, Tuple, Union
import math

NumberLike = Union[int, float]


def _isclose_zero(v: float, tol: float = 1e-12) -> bool:
    return abs(v) <= tol


class Expr:
    """Base class for symbolic mathematical expressions.

    Every expression supports:
    - symbolic simplification
    - symbolic differentiation
    - numerical evaluation
    - LaTeX rendering
    - gradient and Hessian construction
    - lightweight analysis hooks
    """

    __array_priority__ = 10000

    def simplify(self) -> "Expr":
        return self

    def diff(self, var: "Symbol") -> "Expr":
        raise NotImplementedError(f"diff not implemented for {type(self).__name__}")

    def eval(self, values: Dict[str, float] | None = None, **kwargs: float) -> float:
        raise NotImplementedError(f"eval not implemented for {type(self).__name__}")

    def symbols(self) -> set[str]:
        return set()

    def to_latex(self) -> str:
        return str(self)

    def explain(self) -> str:
        return f"Expressão: {self}\nLaTeX: {self.to_latex()}\nSímbolos: {sorted(self.symbols())}"

    def grad(self, variables: Sequence["Symbol"]) -> List["Expr"]:
        return [self.diff(v).simplify() for v in variables]

    def hessian(self, variables: Sequence["Symbol"]) -> List[List["Expr"]]:
        return [[self.diff(vi).diff(vj).simplify() for vj in variables] for vi in variables]

    def substitute(self, mapping: Dict[str, "Expr" | NumberLike]) -> "Expr":
        return self

    def __add__(self, other: Any) -> "Expr":
        return Add(self, to_expr(other)).simplify()

    def __radd__(self, other: Any) -> "Expr":
        return Add(to_expr(other), self).simplify()

    def __sub__(self, other: Any) -> "Expr":
        return Add(self, Mul(Number(-1), to_expr(other))).simplify()

    def __rsub__(self, other: Any) -> "Expr":
        return Add(to_expr(other), Mul(Number(-1), self)).simplify()

    def __mul__(self, other: Any) -> "Expr":
        return Mul(self, to_expr(other)).simplify()

    def __rmul__(self, other: Any) -> "Expr":
        return Mul(to_expr(other), self).simplify()

    def __truediv__(self, other: Any) -> "Expr":
        return Mul(self, Pow(to_expr(other), Number(-1))).simplify()

    def __rtruediv__(self, other: Any) -> "Expr":
        return Mul(to_expr(other), Pow(self, Number(-1))).simplify()

    def __pow__(self, power: Any) -> "Expr":
        return Pow(self, to_expr(power)).simplify()

    def __neg__(self) -> "Expr":
        return Mul(Number(-1), self).simplify()

    def __eq__(self, other: Any) -> "Equation":  # type: ignore[override]
        return Equation(self, to_expr(other))


@dataclass(frozen=True)
class Number(Expr):
    value: NumberLike

    def simplify(self) -> Expr:
        return self

    def diff(self, var: "Symbol") -> Expr:
        return Number(0)

    def eval(self, values: Dict[str, float] | None = None, **kwargs: float) -> float:
        return float(self.value)

    def to_latex(self) -> str:
        if isinstance(self.value, int) or float(self.value).is_integer():
            return str(int(self.value))
        return str(self.value)

    def __str__(self) -> str:
        return self.to_latex()


@dataclass(frozen=True)
class Symbol(Expr):
    name: str
    real: bool = True
    positive: bool = False

    def diff(self, var: "Symbol") -> Expr:
        return Number(1 if self.name == var.name else 0)

    def eval(self, values: Dict[str, float] | None = None, **kwargs: float) -> float:
        merged = dict(values or {})
        merged.update(kwargs)
        if self.name not in merged:
            raise ValueError(f"Valor não fornecido para o símbolo '{self.name}'.")
        return float(merged[self.name])

    def symbols(self) -> set[str]:
        return {self.name}

    def substitute(self, mapping: Dict[str, Expr | NumberLike]) -> Expr:
        if self.name in mapping:
            return to_expr(mapping[self.name])
        return self

    def to_latex(self) -> str:
        return self.name

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class Add(Expr):
    left: Expr
    right: Expr

    def simplify(self) -> Expr:
        l = self.left.simplify()
        r = self.right.simplify()
        if isinstance(l, Number) and isinstance(r, Number):
            return Number(l.value + r.value)
        if isinstance(l, Number) and _isclose_zero(float(l.value)):
            return r
        if isinstance(r, Number) and _isclose_zero(float(r.value)):
            return l
        # x + x -> 2*x
        if repr(l) == repr(r):
            return Mul(Number(2), l).simplify()
        return Add(l, r)

    def diff(self, var: Symbol) -> Expr:
        return Add(self.left.diff(var), self.right.diff(var)).simplify()

    def eval(self, values: Dict[str, float] | None = None, **kwargs: float) -> float:
        return self.left.eval(values, **kwargs) + self.right.eval(values, **kwargs)

    def symbols(self) -> set[str]:
        return self.left.symbols() | self.right.symbols()

    def substitute(self, mapping: Dict[str, Expr | NumberLike]) -> Expr:
        return Add(self.left.substitute(mapping), self.right.substitute(mapping)).simplify()

    def to_latex(self) -> str:
        return f"{self.left.to_latex()} + {self.right.to_latex()}"

    def __str__(self) -> str:
        return f"({self.left} + {self.right})"


@dataclass(frozen=True)
class Mul(Expr):
    left: Expr
    right: Expr

    def simplify(self) -> Expr:
        l = self.left.simplify()
        r = self.right.simplify()
        if isinstance(l, Number) and isinstance(r, Number):
            return Number(l.value * r.value)
        if isinstance(l, Number) and _isclose_zero(float(l.value)):
            return Number(0)
        if isinstance(r, Number) and _isclose_zero(float(r.value)):
            return Number(0)
        if isinstance(l, Number) and float(l.value) == 1.0:
            return r
        if isinstance(r, Number) and float(r.value) == 1.0:
            return l
        if isinstance(l, Number) and float(l.value) == -1.0:
            return Neg(r).simplify()
        if isinstance(r, Number) and float(r.value) == -1.0:
            return Neg(l).simplify()
        return Mul(l, r)

    def diff(self, var: Symbol) -> Expr:
        u, v = self.left, self.right
        return Add(Mul(u.diff(var), v), Mul(u, v.diff(var))).simplify()

    def eval(self, values: Dict[str, float] | None = None, **kwargs: float) -> float:
        return self.left.eval(values, **kwargs) * self.right.eval(values, **kwargs)

    def symbols(self) -> set[str]:
        return self.left.symbols() | self.right.symbols()

    def substitute(self, mapping: Dict[str, Expr | NumberLike]) -> Expr:
        return Mul(self.left.substitute(mapping), self.right.substitute(mapping)).simplify()

    def to_latex(self) -> str:
        l = self.left.to_latex()
        r = self.right.to_latex()
        if isinstance(self.left, Add):
            l = f"\\left({l}\\right)"
        if isinstance(self.right, Add):
            r = f"\\left({r}\\right)"
        return f"{l}{r}"

    def __str__(self) -> str:
        return f"({self.left} * {self.right})"


@dataclass(frozen=True)
class Neg(Expr):
    expr: Expr

    def simplify(self) -> Expr:
        e = self.expr.simplify()
        if isinstance(e, Number):
            return Number(-e.value)
        if isinstance(e, Neg):
            return e.expr
        return Neg(e)

    def diff(self, var: Symbol) -> Expr:
        return Neg(self.expr.diff(var)).simplify()

    def eval(self, values: Dict[str, float] | None = None, **kwargs: float) -> float:
        return -self.expr.eval(values, **kwargs)

    def symbols(self) -> set[str]:
        return self.expr.symbols()

    def substitute(self, mapping: Dict[str, Expr | NumberLike]) -> Expr:
        return Neg(self.expr.substitute(mapping)).simplify()

    def to_latex(self) -> str:
        return f"-{self.expr.to_latex()}"

    def __str__(self) -> str:
        return f"(-{self.expr})"


@dataclass(frozen=True)
class Pow(Expr):
    base: Expr
    exponent: Expr

    def simplify(self) -> Expr:
        b = self.base.simplify()
        e = self.exponent.simplify()
        if isinstance(e, Number):
            if _isclose_zero(float(e.value)):
                return Number(1)
            if float(e.value) == 1.0:
                return b
        if isinstance(b, Number) and isinstance(e, Number):
            return Number(b.value ** e.value)
        return Pow(b, e)

    def diff(self, var: Symbol) -> Expr:
        b, e = self.base, self.exponent
        # d(u^n) = n*u^(n-1)*u'
        if isinstance(e, Number):
            return Mul(Mul(e, Pow(b, Number(e.value - 1))), b.diff(var)).simplify()
        # d(u^v) = u^v * (v' ln u + v u'/u)
        return Mul(self, Add(Mul(e.diff(var), Log(b)), Mul(e, b.diff(var) / b))).simplify()

    def eval(self, values: Dict[str, float] | None = None, **kwargs: float) -> float:
        return self.base.eval(values, **kwargs) ** self.exponent.eval(values, **kwargs)

    def symbols(self) -> set[str]:
        return self.base.symbols() | self.exponent.symbols()

    def substitute(self, mapping: Dict[str, Expr | NumberLike]) -> Expr:
        return Pow(self.base.substitute(mapping), self.exponent.substitute(mapping)).simplify()

    def to_latex(self) -> str:
        base = self.base.to_latex()
        if isinstance(self.base, (Add, Mul)):
            base = f"\\left({base}\\right)"
        return f"{base}^{{{self.exponent.to_latex()}}}"

    def __str__(self) -> str:
        return f"({self.base}^{self.exponent})"


@dataclass(frozen=True)
class UnaryFunction(Expr):
    arg: Expr
    name: str = "func"
    latex_name: str = "func"
    numeric_fn: Callable[[float], float] | None = None

    def simplify(self) -> Expr:
        a = self.arg.simplify()
        if isinstance(a, Number) and self.numeric_fn:
            return Number(self.numeric_fn(float(a.value)))
        return type(self)(a)  # type: ignore[call-arg]

    def diff(self, var: Symbol) -> Expr:
        raise NotImplementedError

    def eval(self, values: Dict[str, float] | None = None, **kwargs: float) -> float:
        if not self.numeric_fn:
            raise NotImplementedError(f"No numeric function for {self.name}")
        return self.numeric_fn(self.arg.eval(values, **kwargs))

    def symbols(self) -> set[str]:
        return self.arg.symbols()

    def substitute(self, mapping: Dict[str, Expr | NumberLike]) -> Expr:
        return type(self)(self.arg.substitute(mapping)).simplify()  # type: ignore[call-arg]

    def to_latex(self) -> str:
        return f"\\{self.latex_name}\\left({self.arg.to_latex()}\\right)"

    def __str__(self) -> str:
        return f"{self.name}({self.arg})"


@dataclass(frozen=True)
class Sin(UnaryFunction):
    arg: Expr
    name: str = "sin"
    latex_name: str = "sin"
    numeric_fn: Callable[[float], float] = math.sin

    def diff(self, var: Symbol) -> Expr:
        return Mul(Cos(self.arg), self.arg.diff(var)).simplify()


@dataclass(frozen=True)
class Cos(UnaryFunction):
    arg: Expr
    name: str = "cos"
    latex_name: str = "cos"
    numeric_fn: Callable[[float], float] = math.cos

    def diff(self, var: Symbol) -> Expr:
        return Mul(Neg(Sin(self.arg)), self.arg.diff(var)).simplify()


@dataclass(frozen=True)
class Exp(UnaryFunction):
    arg: Expr
    name: str = "exp"
    latex_name: str = "exp"
    numeric_fn: Callable[[float], float] = math.exp

    def diff(self, var: Symbol) -> Expr:
        return Mul(Exp(self.arg), self.arg.diff(var)).simplify()

    def to_latex(self) -> str:
        return f"e^{{{self.arg.to_latex()}}}"


@dataclass(frozen=True)
class Log(UnaryFunction):
    arg: Expr
    name: str = "log"
    latex_name: str = "log"
    numeric_fn: Callable[[float], float] = math.log

    def diff(self, var: Symbol) -> Expr:
        return (self.arg.diff(var) / self.arg).simplify()


@dataclass(frozen=True)
class Sqrt(UnaryFunction):
    arg: Expr
    name: str = "sqrt"
    latex_name: str = "sqrt"
    numeric_fn: Callable[[float], float] = math.sqrt

    def diff(self, var: Symbol) -> Expr:
        return (self.arg.diff(var) / (Number(2) * Sqrt(self.arg))).simplify()

    def to_latex(self) -> str:
        return f"\\sqrt{{{self.arg.to_latex()}}}"


@dataclass(frozen=True)
class Equation:
    left: Expr
    right: Expr

    def residual(self) -> Expr:
        return (self.left - self.right).simplify()

    def to_latex(self) -> str:
        return f"{self.left.to_latex()} = {self.right.to_latex()}"

    def eval_residual(self, values: Dict[str, float]) -> float:
        return self.residual().eval(values)

    def __str__(self) -> str:
        return f"{self.left} = {self.right}"


def to_expr(value: Any) -> Expr:
    if isinstance(value, Expr):
        return value
    if isinstance(value, bool):
        raise TypeError("Boolean não é expressão matemática em NablaMath.")
    if isinstance(value, (int, float)):
        return Number(value)
    raise TypeError(f"Não consigo converter {value!r} para Expr.")


def symbol(name: str, **assumptions: Any) -> Symbol:
    return Symbol(name, **assumptions)


def symbols(names: str, **assumptions: Any) -> Tuple[Symbol, ...]:
    return tuple(Symbol(n.strip(), **assumptions) for n in names.replace(",", " ").split() if n.strip())


def sin(x: Any) -> Expr:
    return Sin(to_expr(x)).simplify()


def cos(x: Any) -> Expr:
    return Cos(to_expr(x)).simplify()


def exp(x: Any) -> Expr:
    return Exp(to_expr(x)).simplify()


def log(x: Any) -> Expr:
    return Log(to_expr(x)).simplify()


def sqrt(x: Any) -> Expr:
    return Sqrt(to_expr(x)).simplify()


def latex(obj: Any) -> str:
    if hasattr(obj, "to_latex"):
        return obj.to_latex()
    return str(obj)
