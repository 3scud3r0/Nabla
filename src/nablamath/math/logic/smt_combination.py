"""Version 1: bounded conjunctions of rational linear arithmetic and flat EUF.

The optional Z3 backend decides the combined formula. SAT models are checked
again with Fraction arithmetic and finite congruence. UNSAT is a backend result,
not a portable formal certificate. Nested calls can be flattened through named
result variables. This API has no quantifiers, Boolean disjunction or arrays.
"""
from dataclasses import dataclass
from fractions import Fraction
from itertools import islice
from typing import Iterable, Literal
from .smt_linear import LinearInequality

CONTRACT_VERSION = 1


@dataclass(frozen=True)
class FunctionApplication:
    function: str
    arguments: tuple[str, ...]
    result: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", tuple(islice(self.arguments, 9)))
        if (not isinstance(self.function, str) or not self.function.isidentifier()
                or not isinstance(self.result, str) or not self.result.isidentifier()
                or not 1 <= len(self.arguments) <= 8
                or any(not isinstance(arg, str) or not arg.isidentifier() for arg in self.arguments)):
            raise ValueError("invalid function application")


@dataclass(frozen=True)
class CombinedSMTResult:
    status: Literal["sat", "unsat", "unknown", "unavailable"]
    model: tuple[tuple[str, Fraction], ...] = ()
    reason: str = ""


def verify_combined_model(inequalities: Iterable[LinearInequality],
                          applications: Iterable[FunctionApplication],
                          model: Iterable[tuple[str, Fraction]]) -> bool:
    """Check LRA and EUF congruence without invoking the SMT backend."""
    rows = tuple(islice(model, 257))
    constraints = tuple(islice(inequalities, 1025))
    calls = tuple(islice(applications, 129))
    if len(rows) > 256 or len(constraints) > 1024 or len(calls) > 128:
        return False
    assignment = dict(rows)
    if len(rows) != len(assignment) or any(type(v) not in (int, Fraction) for v in assignment.values()):
        return False
    required = {name for c in constraints for name, _ in c.coefficients}
    required.update(name for app in calls for name in (*app.arguments, app.result))
    if not required <= assignment.keys():
        return False
    if any(sum(coef * assignment[name] for name, coef in c.coefficients) > c.bound
           for c in constraints):
        return False
    values, arities = {}, {}
    for call in calls:
        if call.function in arities and arities[call.function] != len(call.arguments):
            return False
        arities[call.function] = len(call.arguments)
        key = call.function, tuple(assignment[name] for name in call.arguments)
        output = assignment[call.result]
        if key in values and values[key] != output:
            return False
        values[key] = output
    return True


def solve_combined_rational(inequalities: Iterable[LinearInequality],
                            applications: Iterable[FunctionApplication] = (), *,
                            timeout_ms: int = 5000) -> CombinedSMTResult:
    """Return explicit sat/unsat/unknown/unavailable with a rechecked SAT model.

    Bounds: 1024 inequalities, 128 applications, 256 variables, 4096-bit rational
    coefficients and a backend timeout of at most 60 seconds.
    """
    if type(timeout_ms) is not int or not 1 <= timeout_ms <= 60000:
        raise ValueError("invalid solver timeout")
    constraints = tuple(islice(inequalities, 1025))
    calls = tuple(islice(applications, 129))
    if len(constraints) > 1024 or len(calls) > 128:
        raise ValueError("constraint budget exceeded")
    if any(not isinstance(c, LinearInequality) for c in constraints):
        raise ValueError("expected linear inequalities")
    if any(not isinstance(c, FunctionApplication) for c in calls):
        raise ValueError("expected function applications")
    names = {name for c in constraints for name, _ in c.coefficients}
    names.update(name for call in calls for name in (*call.arguments, call.result))
    if len(names) > 256:
        raise ValueError("variable budget exceeded")
    if any(max(abs(v.numerator).bit_length(), v.denominator.bit_length()) > 4096
           for c in constraints for v in (c.bound, *(v for _, v in c.coefficients))):
        raise ValueError("coefficient bit budget exceeded")
    arities = {}
    for call in calls:
        if call.function in arities and arities[call.function] != len(call.arguments):
            raise ValueError("function arity mismatch")
        arities[call.function] = len(call.arguments)
    try:
        import z3
    except ImportError:
        return CombinedSMTResult("unavailable", reason="Install optional z3-solver backend")
    solver = z3.Solver()
    solver.set(timeout=timeout_ms)
    variables = {name: z3.Real("nabla_var_" + name) for name in names}
    real_sort = z3.RealSort()
    functions = {name: z3.Function("nabla_fun_" + name, *([real_sort] * (arity + 1)))
                 for name, arity in arities.items()}
    def rational(value: Fraction):
        return z3.RealVal(f"{value.numerator}/{value.denominator}")
    for constraint in constraints:
        solver.add(z3.Sum([rational(v) * variables[name] for name, v in constraint.coefficients])
                   <= rational(constraint.bound))
    for call in calls:
        solver.add(functions[call.function](*(variables[name] for name in call.arguments))
                   == variables[call.result])
    status = solver.check()
    if status == z3.unsat:
        return CombinedSMTResult("unsat", reason="Z3 result; no independent UNSAT certificate")
    if status != z3.sat:
        return CombinedSMTResult("unknown", reason=solver.reason_unknown())
    backend_model = solver.model()
    assignment = []
    for name in sorted(names):
        value = backend_model.eval(variables[name], model_completion=True)
        if not z3.is_rational_value(value):
            return CombinedSMTResult("unknown", reason="backend model is not rational")
        assignment.append((name, Fraction(value.numerator_as_long(), value.denominator_as_long())))
    model = tuple(assignment)
    if not verify_combined_model(constraints, calls, model):
        return CombinedSMTResult("unknown", reason="independent model verification failed")
    return CombinedSMTResult("sat", model)
