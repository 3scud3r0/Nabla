"""Versioned inverse construction; old generate() keeps its exact v1 contract."""
from dataclasses import dataclass
from fractions import Fraction
from importlib import import_module
from ..core.semantic_ir import ScientificTask,canonical_json
from .task_spec import GeneratedProblem
from .sampling import rng_for

CONSTRUCTORS={'polynomial_integral':'integration','factored_polynomial':'polynomial',
              'linear_system':'linear_systems','prescribed_spectrum':'spectrum',
              'convex_quadratic':'optimization','stationary_markov':'markov',
              'polynomial_identity':'identities','counterexample':'counterexamples'}


@dataclass(frozen=True)
class GeneratedTask:
    task: ScientificTask
    witness: tuple[Fraction,...]
    seed: int
    generator_version: str='inverse-v1'


def generate_task(family,seed,size=3):
    rng_for(seed,size)
    if family not in CONSTRUCTORS:
        raise ValueError('Familia nao suportada')
    module=import_module(f'.constructors.{CONSTRUCTORS[family]}',__package__)
    task,witness=module.construct(seed,size)
    return GeneratedProblem(task,canonical_json(witness),seed)


def generate(family,seed,size=3):
    if family not in {'polynomial_integral','linear_system'}:
        raise ValueError('Use generate_task para as novas familias v2')
    generated=generate_task(family,seed,size)
    key='coefficients' if family=='polynomial_integral' else 'solution'
    return GeneratedTask(generated.task.legacy(),tuple(Fraction(v) for v in generated.witness[key]),seed)
