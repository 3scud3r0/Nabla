"""Nonlinear 1D axial finite elements with a convex cubic elastic material.

The left node is fixed, cross sections are constant per element, and external
nodal dead loads are scaled by continuation. The stress law is
sigma=E*epsilon+H*epsilon**3, with E>0 and H>=0. Strains remain explicitly bounded.
This is a small-strain mathematical model, not geometric nonlinear mechanics,
plasticity, buckling, contact, a general solid solver or experimental validation.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

CONTRACT_VERSION = 1


def _real(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite real number')
    return float(value)


@dataclass(frozen=True)
class CubicElasticMaterial:
    young_pa: float
    hardening_pa: float = 0.0
    maximum_abs_strain: float = 0.1

    def __post_init__(self) -> None:
        for name in ('young_pa', 'hardening_pa', 'maximum_abs_strain'):
            object.__setattr__(self, name, _real(getattr(self, name), name))
        if not 1e-9 <= self.young_pa <= 1e18:
            raise ValueError('Young modulus outside [1e-9,1e18] Pa')
        if not 0 <= self.hardening_pa <= 1e24:
            raise ValueError('hardening outside [0,1e24] Pa')
        if not 1e-9 <= self.maximum_abs_strain <= 0.25:
            raise ValueError('strain bound must lie in [1e-9,0.25]')

    def _strain(self, strain: float) -> float:
        strain = _real(strain, 'strain')
        if abs(strain) > self.maximum_abs_strain:
            raise ValueError('strain outside the declared small-strain domain')
        return strain

    def stress_pa(self, strain: float) -> float:
        strain = self._strain(strain)
        return self.young_pa * strain + self.hardening_pa * strain**3

    def tangent_pa(self, strain: float) -> float:
        strain = self._strain(strain)
        return self.young_pa + 3 * self.hardening_pa * strain**2

    def energy_density_j_m3(self, strain: float) -> float:
        strain = self._strain(strain)
        return self.young_pa * strain**2 / 2 + self.hardening_pa * strain**4 / 4


@dataclass(frozen=True)
class AxialElement:
    length_m: float
    area_m2: float
    material: CubicElasticMaterial

    def __post_init__(self) -> None:
        for name in ('length_m', 'area_m2'):
            object.__setattr__(self, name, _real(getattr(self, name), name))
        if not 1e-9 <= self.length_m <= 1e9 or not 1e-18 <= self.area_m2 <= 1e12:
            raise ValueError('element length or area outside bounds')
        if not isinstance(self.material, CubicElasticMaterial):
            raise ValueError('CubicElasticMaterial required')


@dataclass(frozen=True)
class NonlinearBar:
    elements: tuple[AxialElement, ...]
    nodal_loads_n: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.elements, (tuple, list)) or not 1 <= len(self.elements) <= 10000:
            raise ValueError('one to 10000 elements required')
        if not all(isinstance(e, AxialElement) for e in self.elements):
            raise ValueError('AxialElement entries required')
        if not isinstance(self.nodal_loads_n, (tuple, list)) or len(self.nodal_loads_n) != len(self.elements) + 1:
            raise ValueError('one load per node required')
        loads = tuple(_real(v, 'nodal load') for v in self.nodal_loads_n)
        if any(abs(v) > 1e24 for v in loads):
            raise ValueError('nodal load outside bounded domain')
        if loads[0] != 0:
            raise ValueError('load at the fixed node must be zero; reaction is computed separately')
        object.__setattr__(self, 'elements', tuple(self.elements))
        object.__setattr__(self, 'nodal_loads_n', loads)

    @classmethod
    def uniform(cls, length_m, area_m2, material, end_force_n, *, elements=8):
        if type(elements) is not int or not 1 <= elements <= 10000:
            raise ValueError('one to 10000 elements required')
        length = _real(length_m, 'length')
        force = _real(end_force_n, 'end force')
        element = AxialElement(length / elements, area_m2, material)
        return cls((element,) * elements, (0.0,) * elements + (force,))


@dataclass(frozen=True)
class BarAssembly:
    internal_forces_n: tuple[float, ...]
    free_diagonal_n_m: tuple[float, ...]
    free_offdiagonal_n_m: tuple[float, ...]
    strains: tuple[float, ...]
    stresses_pa: tuple[float, ...]
    strain_energy_j: float


def assemble_nonlinear_bar(bar: NonlinearBar, displacements_m: Sequence[float]) -> BarAssembly:
    """Assemble internal forces and the symmetric reduced tridiagonal tangent."""
    if not isinstance(bar, NonlinearBar):
        raise ValueError('NonlinearBar required')
    n = len(bar.elements)
    if not isinstance(displacements_m, (list, tuple)) or len(displacements_m) != n + 1:
        raise ValueError('one displacement per node required')
    u = tuple(_real(v, 'displacement') for v in displacements_m)
    if u[0] != 0:
        raise ValueError('left node must be fixed exactly')
    forces = [0.0] * (n + 1)
    diagonal = [0.0] * n
    offdiagonal = [0.0] * (n - 1)
    strains, stresses, energies = [], [], []
    for i, element in enumerate(bar.elements):
        strain = (u[i+1] - u[i]) / element.length_m
        stress = element.material.stress_pa(strain)
        axial = element.area_m2 * stress
        tangent = element.area_m2 * element.material.tangent_pa(strain) / element.length_m
        forces[i] -= axial
        forces[i+1] += axial
        diagonal[i] += tangent
        if i > 0:
            diagonal[i-1] += tangent
            offdiagonal[i-1] = -tangent
        strains.append(strain)
        stresses.append(stress)
        energies.append(element.area_m2 * element.length_m * element.material.energy_density_j_m3(strain))
    return BarAssembly(tuple(forces), tuple(diagonal), tuple(offdiagonal),
                       tuple(strains), tuple(stresses), math.fsum(energies))


def _solve_positive_tridiagonal(diagonal, offdiagonal, rhs):
    """LDL-like elimination for a symmetric positive definite tridiagonal matrix."""
    d, b = list(diagonal), list(rhs)
    for i in range(1, len(d)):
        if not math.isfinite(d[i-1]) or d[i-1] <= 0:
            raise ArithmeticError('nonpositive tangent pivot')
        factor = offdiagonal[i-1] / d[i-1]
        d[i] -= factor * offdiagonal[i-1]
        b[i] -= factor * b[i-1]
    if not math.isfinite(d[-1]) or d[-1] <= 0:
        raise ArithmeticError('nonpositive tangent pivot')
    x = [0.0] * len(d)
    x[-1] = b[-1] / d[-1]
    for i in range(len(d)-2, -1, -1):
        x[i] = (b[i] - offdiagonal[i] * x[i+1]) / d[i]
    if not all(math.isfinite(v) for v in x):
        raise ArithmeticError('nonfinite Newton correction')
    return x


@dataclass(frozen=True)
class ContinuationStep:
    load_fraction: float
    newton_iterations: int
    residual_norm_n: float
    accepted_line_search_factors: tuple[float, ...]


@dataclass(frozen=True)
class NonlinearBarResult:
    displacements_m: tuple[float, ...]
    element_strains: tuple[float, ...]
    element_stresses_pa: tuple[float, ...]
    reaction_n: float
    residual_norm_n: float
    strain_energy_j: float
    load_displacement_product_j: float
    continuation: tuple[ContinuationStep, ...]
    assembly_evaluations: int

    @property
    def total_potential_energy_j(self) -> float:
        """Elastic energy minus F dot u; F dot u is not the loading-path work."""
        return self.strain_energy_j - self.load_displacement_product_j

    def to_data(self) -> dict:
        from dataclasses import asdict
        return {
            'schema_version': CONTRACT_VERSION,
            **asdict(self),
            'total_potential_energy_j': self.total_potential_energy_j,
            'model': 'small_strain_cubic_elastic_axial_bar',
            'experimental_validation': False,
            'limitations': '1D convex elastic law; no geometric nonlinearity, plasticity, buckling or experimental validation.',
        }


def solve_nonlinear_bar(
    bar: NonlinearBar,
    *,
    load_steps: int = 8,
    max_newton_iterations: int = 50,
    max_line_searches: int = 30,
    absolute_tolerance_n: float = 1e-9,
    relative_tolerance: float = 1e-10,
    max_element_evaluations: int = 10000000,
) -> NonlinearBarResult:
    """Newton continuation with residual-decreasing backtracking and work caps.

    A returned result satisfies the full-load residual criterion. Failed load
    steps never return partial states as converged results. Tangents are formed
    analytically from the stress law and solved in O(elements) storage/work.
    """
    if not isinstance(bar, NonlinearBar):
        raise ValueError('NonlinearBar required')
    for name, value, maximum in (
        ('load steps', load_steps, 1000),
        ('Newton iterations', max_newton_iterations, 1000),
        ('line searches', max_line_searches, 60),
        ('element evaluations', max_element_evaluations, 100000000),
    ):
        if type(value) is not int or not 1 <= value <= maximum:
            raise ValueError(f'invalid {name} budget')
    atol = _real(absolute_tolerance_n, 'absolute tolerance')
    rtol = _real(relative_tolerance, 'relative tolerance')
    if not 0 < atol <= 1e6 or not 0 <= rtol <= 0.1:
        raise ValueError('invalid nonlinear residual tolerances')
    n = len(bar.elements)
    evaluations = 0

    def assemble(u):
        nonlocal evaluations
        if (evaluations + 1) * n > max_element_evaluations:
            raise ArithmeticError('nonlinear element-evaluation budget exhausted')
        evaluations += 1
        return assemble_nonlinear_bar(bar, u)

    def residual(assembly, fraction):
        values = tuple(assembly.internal_forces_n[i] - fraction * bar.nodal_loads_n[i]
                       for i in range(1, n + 1))
        return values, max(map(abs, values))

    u = (0.0,) * (n + 1)
    history = []
    final = None
    for step in range(1, load_steps + 1):
        fraction = step / load_steps
        threshold = atol + rtol * max(abs(fraction * v) for v in bar.nodal_loads_n)
        factors = []
        current = assemble(u)
        r, norm = residual(current, fraction)
        for iteration in range(max_newton_iterations + 1):
            if norm <= threshold:
                history.append(ContinuationStep(fraction, iteration, norm, tuple(factors)))
                final = current
                break
            if iteration == max_newton_iterations:
                raise ArithmeticError('nonlinear Newton iteration budget exhausted')
            correction = _solve_positive_tridiagonal(current.free_diagonal_n_m,
                                                     current.free_offdiagonal_n_m, tuple(-v for v in r))
            alpha = 1.0
            accepted = False
            for _ in range(max_line_searches):
                trial = (0.0,) + tuple(value + alpha * delta for value, delta in zip(u[1:], correction))
                try:
                    trial_assembly = assemble(trial)
                except ValueError:
                    # Crossing the declared strain bound is a rejected trial.
                    alpha /= 2
                    continue
                trial_r, trial_norm = residual(trial_assembly, fraction)
                if trial_norm <= threshold or trial_norm < (1 - 1e-4 * alpha) * norm:
                    u, current, r, norm = trial, trial_assembly, trial_r, trial_norm
                    factors.append(alpha)
                    accepted = True
                    break
                alpha /= 2
            if not accepted:
                raise ArithmeticError('nonlinear line-search budget exhausted or strain limit reached')
        else:
            raise ArithmeticError('unreachable unconverged continuation state')
    external = math.fsum(force * value for force, value in zip(bar.nodal_loads_n, u))
    return NonlinearBarResult(u, final.strains, final.stresses_pa, final.internal_forces_n[0],
                              history[-1].residual_norm_n, final.strain_energy_j,
                              external, tuple(history), evaluations)
