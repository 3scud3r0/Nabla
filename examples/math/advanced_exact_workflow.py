"""Run: python examples/math/advanced_exact_workflow.py (editable install required)."""
from nablamath.calc import CalculationSession, Notebook
from nablamath.math.exact import FiniteField, ModPolynomial, ExactInterval
from nablamath.math.exact import Polynomial, subdivision_extrema

session = CalculationSession(precision=40)
notebook = Notebook("Nabla: matemática exata integrada")

workloads = (
    ("nt_primality", {"n": 97}),
    ("nt_modular_roots", {"a": 2, "prime": 7}),
    ("ff_extension", {"prime": 2, "modulus": [1, 1, 1],
                      "element": [0, 1]}),
    ("analysis_integral", {"coefficients": [0, 0, 1],
                           "lower": 0, "upper": 1}),
    ("graph_max_flow", {"vertices": ["s", "a", "t"],
                        "edges": [["s", "a", "3/2"], ["a", "t", "1"]],
                        "source": "s", "sink": "t"}),
    ("prob_stationary", {"transition": [["1/2", "1/2"], ["1/4", "3/4"]]}),
)

for operation, kwargs in workloads:
    calculation = session.execute(operation, **kwargs)
    notebook.append(calculation)
    print(operation, calculation.to_data()["result"])

assert notebook.replay() == len(workloads)
print("Reexecuted notebook cells:", len(workloads))

# Direct library APIs are also available, without the CLI.
field = FiniteField(ModPolynomial((1, 1, 1), 2))
x = field.element((0, 1))
assert x * x.inverse() == field.one()

enclosure = subdivision_extrema(
    Polynomial((0, 0, 1)), ExactInterval(-1, 1),
    tolerance="1/8", max_segments=128,
)
print("Certified extremum enclosures:", enclosure)
