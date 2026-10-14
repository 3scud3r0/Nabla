"""Nodal analysis over rationals. No AC, nonlinear devices or parasitic effects."""
from dataclasses import dataclass
from fractions import Fraction

from ...core.semantic_ir import rational
from ...math.linear_algebra.matrices import Matrix


@dataclass(frozen=True)
class Resistor:
    a: str
    b: str
    ohms: Fraction

    def __post_init__(self):
        if not self.a or not self.b or self.a == self.b:
            raise ValueError('Resistor requer dois nos distintos')
        resistance = rational(self.ohms)
        if resistance <= 0:
            raise ValueError('Resistencia deve ser positiva')
        object.__setattr__(self, 'ohms', resistance)


@dataclass(frozen=True)
class DCResult:
    voltages: tuple[tuple[str, Fraction], ...]
    branch_currents: tuple[Fraction, ...]
    kcl_residuals: tuple[tuple[str, Fraction], ...]
    dissipated_power: Fraction
    supplied_power: Fraction
    units: tuple[str, ...] = ('V', 'A', 'ohm', 'W')

    @property
    def verified(self):
        return not any(v for _, v in self.kcl_residuals) and self.dissipated_power == self.supplied_power


def solve_dc(resistors: tuple[Resistor, ...], injections: dict[str, Fraction], *, ground: str = '0') -> DCResult:
    if not 1 <= len(resistors) <= 128:
        raise ValueError('Circuito requer de 1 a 128 resistores')
    nodes = sorted({n for r in resistors for n in (r.a, r.b)})
    if ground not in nodes or len(nodes) > 33 or any(n not in nodes for n in injections):
        raise ValueError('Referencia ou nos invalidos; maximo 32 nos livres')
    currents = {n: rational(injections.get(n, 0)) for n in nodes}
    if ground in injections and sum(currents.values(), Fraction()):
        raise ValueError('Corrente total injetada deve ser zero quando a referencia e explicita')
    currents[ground] = -sum((v for n, v in currents.items() if n != ground), Fraction())
    # Require every node to be connected to the reference before linear solving.
    reached = {ground}
    for _ in nodes:
        for r in resistors:
            if r.a in reached or r.b in reached:
                reached.update((r.a, r.b))
    if reached != set(nodes):
        raise ValueError('Componente flutuante sem referencia')
    free = [n for n in nodes if n != ground]
    index = {n: i for i, n in enumerate(free)}
    data = [[Fraction() for _ in free] for _ in free]
    for r in resistors:
        conductance = 1/r.ohms
        for a, b in ((r.a, r.b), (r.b, r.a)):
            if a != ground:
                data[index[a]][index[a]] += conductance
                if b != ground:
                    data[index[a]][index[b]] -= conductance
    solution = Matrix(tuple(tuple(row) for row in data)).inverse() @ Matrix(tuple((currents[n],) for n in free))
    voltage = {ground: Fraction(), **{n: solution.rows[index[n]][0] for n in free}}
    branch = tuple((voltage[r.a]-voltage[r.b])/r.ohms for r in resistors)
    residual = {n: -currents[n] for n in nodes}
    dissipated = Fraction()
    for r, current in zip(resistors, branch):
        residual[r.a] += current
        residual[r.b] -= current
        dissipated += r.ohms * current**2
    supplied = sum((voltage[n]*currents[n] for n in nodes), Fraction())
    result = DCResult(tuple(sorted(voltage.items())), branch, tuple(sorted(residual.items())), dissipated, supplied)
    if not result.verified:
        raise ArithmeticError('Circuito falhou nas leis de Kirchhoff ou balanco de potencia')
    return result
