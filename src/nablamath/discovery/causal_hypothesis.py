"""Exact, bounded linear structural hypotheses and graph-based identification.

Edges and equations are supplied scientific hypotheses. No graph is learned from
correlation here. Interventions remove incoming mechanisms; counterfactuals use
abduction, action and prediction with the same unit-specific disturbance values.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import re

from ..core.semantic_ir import fingerprint, rational
from ..core.units import ONE, Unit


MAX_VARIABLES = 32
MAX_EDGES = 256
ASSUMPTIONS = (
    'supplied directed acyclic graph describes the mechanisms',
    'linear additive structural equations are invariant under interventions',
    'disturbances are held fixed for individual counterfactuals',
    'no causal conclusion is inferred from observational correlation',
)


def _name(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,47}', value):
        raise ValueError('Variable name must be a bounded identifier')
    return value


def _unit_data(unit):
    return {**unit.to_data(), 'symbol': unit.symbol}


def _unit_from_data(data):
    if set(data) != {'dimensions', 'scale', 'symbol'}:
        raise ValueError('Unknown unit representation')
    return Unit(tuple(data['dimensions']), data['scale'], data['symbol'])


@dataclass(frozen=True)
class CausalCoefficient:
    """A linear parent contribution; coefficient units are child/parent."""

    parent: str
    value: Fraction
    unit: Unit = ONE

    def __post_init__(self):
        _name(self.parent)
        object.__setattr__(self, 'value', rational(self.value))
        if not isinstance(self.unit, Unit):
            raise ValueError('Coefficient requires a Unit')

    def to_data(self):
        return {'parent': self.parent, 'value': str(self.value),
                'unit': _unit_data(self.unit)}


@dataclass(frozen=True)
class StructuralEquation:
    """Numeric intercept and disturbance are expressed in the target unit."""

    target: str
    parents: tuple[CausalCoefficient, ...] = ()
    intercept: Fraction = Fraction(0)
    unit: Unit = ONE

    def __post_init__(self):
        _name(self.target)
        object.__setattr__(self, 'parents', tuple(self.parents))
        object.__setattr__(self, 'intercept', rational(self.intercept))
        if not isinstance(self.unit, Unit) or len(self.parents) > MAX_VARIABLES:
            raise ValueError('Invalid equation unit or too many parents')
        if any(not isinstance(parent, CausalCoefficient) for parent in self.parents):
            raise ValueError('Typed coefficients required')
        if len({parent.parent for parent in self.parents}) != len(self.parents):
            raise ValueError('Duplicate parent mechanism')
        if self.target in {parent.parent for parent in self.parents}:
            raise ValueError('Self loop is not a recursive mechanism')

    def to_data(self):
        return {'target': self.target, 'parents': [parent.to_data() for parent in self.parents],
                'intercept': str(self.intercept), 'unit': _unit_data(self.unit)}


class LinearCausalModel:
    """A declared DAG, not an estimated causal model or an identity authority."""

    def __init__(self, equations, *, provenance, causal_sufficiency=False):
        equations = tuple(equations)
        if not 1 <= len(equations) <= MAX_VARIABLES:
            raise ValueError('Model requires 1..32 structural equations')
        if any(not isinstance(row, StructuralEquation) for row in equations):
            raise ValueError('Typed structural equations required')
        if not isinstance(provenance, str) or not provenance.strip() or len(provenance) > 4096:
            raise ValueError('Bounded model provenance required')
        if type(causal_sufficiency) is not bool:
            raise ValueError('Causal sufficiency must be an explicit boolean declaration')
        self.equations = tuple(sorted(equations, key=lambda row: row.target))
        self.provenance = provenance
        self.causal_sufficiency = causal_sufficiency
        mapping = {row.target: row for row in self.equations}
        if len(mapping) != len(equations):
            raise ValueError('Duplicate target variable')
        if sum(len(row.parents) for row in equations) > MAX_EDGES:
            raise ValueError('Too many causal edges')
        for row in equations:
            for coefficient in row.parents:
                if coefficient.parent not in mapping:
                    raise ValueError('Unknown parent variable')
                parent = mapping[coefficient.parent]
                dimensions = tuple(a + b for a, b in zip(coefficient.unit.dimensions, parent.unit.dimensions))
                if dimensions != row.unit.dimensions:
                    raise ValueError('Coefficient times parent must have target dimensions')
        self._topological_order()

    @property
    def variables(self):
        return tuple(row.target for row in self.equations)

    @property
    def model_id(self):
        return fingerprint(self.to_data())

    def to_data(self):
        return {'schema_version': 1, 'model': 'linear_additive_dag',
                'equations': [row.to_data() for row in self.equations],
                'provenance': self.provenance,
                'causal_sufficiency': self.causal_sufficiency,
                'assumptions': list(ASSUMPTIONS)}

    @classmethod
    def from_data(cls, data):
        if set(data) != {'schema_version', 'model', 'equations', 'provenance', 'causal_sufficiency', 'assumptions'} or type(data['schema_version']) is not int or data['schema_version'] != 1 or data['model'] != 'linear_additive_dag' or data['assumptions'] != list(ASSUMPTIONS):
            raise ValueError('Unknown causal model contract')
        equations = []
        for row in data['equations']:
            if set(row) != {'target', 'parents', 'intercept', 'unit'}:
                raise ValueError('Unknown equation fields')
            parents = []
            for parent in row['parents']:
                if set(parent) != {'parent', 'value', 'unit'}:
                    raise ValueError('Unknown coefficient fields')
                parents.append(CausalCoefficient(parent['parent'], parent['value'], _unit_from_data(parent['unit'])))
            equations.append(StructuralEquation(row['target'], tuple(parents), row['intercept'], _unit_from_data(row['unit'])))
        result = cls(equations, provenance=data['provenance'], causal_sufficiency=data['causal_sufficiency'])
        if result.to_data() != data:
            raise ValueError('Causal model data is not canonical')
        return result

    def _parents(self):
        return {row.target: {item.parent for item in row.parents} for row in self.equations}

    def _topological_order(self):
        pending = self._parents()
        order = []
        while pending:
            ready = sorted(name for name, parents in pending.items() if not parents)
            if not ready:
                raise ValueError('Directed causal graph contains a cycle')
            for name in ready:
                order.append(name)
                del pending[name]
            for parents in pending.values():
                parents.difference_update(ready)
        return tuple(order)

    def _values(self, values, *, complete):
        if not isinstance(values, dict) or not set(values) <= set(self.variables):
            raise ValueError('Unknown variable in assignment')
        if complete and set(values) != set(self.variables):
            raise ValueError('Complete assignment required')
        return {name: rational(value) for name, value in values.items()}

    def _weight(self, equation, coefficient):
        parent = next(row for row in self.equations if row.target == coefficient.parent)
        return coefficient.value * coefficient.unit.scale * parent.unit.scale / equation.unit.scale

    def predict(self, disturbances, *, interventions=None):
        """Evaluate exact recursive mechanisms, replacing intervened equations."""
        disturbances = self._values(disturbances, complete=True)
        interventions = self._values({} if interventions is None else interventions, complete=False)
        mapping = {row.target: row for row in self.equations}
        values = {}
        for name in self._topological_order():
            if name in interventions:
                values[name] = interventions[name]
                continue
            row = mapping[name]
            values[name] = row.intercept + disturbances[name] + sum(
                (self._weight(row, parent) * values[parent.parent] for parent in row.parents), Fraction(0))
            rational(values[name])
        return {name: values[name] for name in self.variables}

    def abduct(self, observed):
        """Recover additive disturbances from a fully observed individual."""
        observed = self._values(observed, complete=True)
        disturbances = {}
        for row in self.equations:
            disturbances[row.target] = observed[row.target] - row.intercept - sum(
                (self._weight(row, parent) * observed[parent.parent] for parent in row.parents), Fraction(0))
            rational(disturbances[row.target])
        return disturbances

    def counterfactual(self, observed, interventions):
        """Reuse abducted disturbances; this requires the supplied SCM assumptions."""
        disturbances = self.abduct(observed)
        intervention_values = self._values(interventions, complete=False)
        prediction = self.predict(disturbances, interventions=intervention_values)
        payload = {'schema_version': 1, 'model_id': self.model_id,
                   'observed': {key: str(value) for key, value in self._values(observed, complete=True).items()},
                   'interventions': {key: str(value) for key, value in intervention_values.items()},
                   'disturbances': {key: str(value) for key, value in disturbances.items()},
                   'counterfactual': {key: str(value) for key, value in prediction.items()},
                   'scope': 'exact consequence of supplied linear SCM; no empirical identification established'}
        return {**payload, 'counterfactual_id': fingerprint(payload)}

    def total_effect(self, treatment, outcome):
        """Derivative of supplied linear mechanisms, in outcome-unit/treatment-unit."""
        if treatment not in self.variables or outcome not in self.variables:
            raise ValueError('Unknown treatment or outcome')
        zero = {name: Fraction(0) for name in self.variables}
        low = self.predict(zero, interventions={treatment: 0})
        high = self.predict(zero, interventions={treatment: 1})
        return high[outcome] - low[outcome]

    def ancestors(self, names, *, remove_outgoing=()):
        names = set(names)
        if not names <= set(self.variables) or not set(remove_outgoing) <= set(self.variables):
            raise ValueError('Unknown graph variable')
        parents = self._parents()
        for row in parents.values():
            row.difference_update(remove_outgoing)
        result = set(names)
        pending = list(names)
        while pending:
            for parent in parents[pending.pop()]:
                if parent not in result:
                    result.add(parent)
                    pending.append(parent)
        return result

    def d_separated(self, left, right, *, conditioned=(), remove_outgoing=()):
        """Ancestral moral graph criterion, including collider descendant effects."""
        left, right, conditioned = set(left), set(right), set(conditioned)
        if not left or not right or left & right or (left | right) & conditioned:
            raise ValueError('Nonempty disjoint queried and conditioned sets required')
        if not (left | right | conditioned) <= set(self.variables):
            raise ValueError('Unknown graph variable')
        ancestors = self.ancestors(left | right | conditioned, remove_outgoing=remove_outgoing)
        parents = self._parents()
        for values in parents.values():
            values.difference_update(remove_outgoing)
        adjacency = {name: set() for name in ancestors}
        for child in ancestors:
            family = sorted(parents[child] & ancestors)
            for parent in family:
                adjacency[child].add(parent)
                adjacency[parent].add(child)
            for index, a in enumerate(family):
                for b in family[index + 1:]:
                    adjacency[a].add(b)
                    adjacency[b].add(a)
        reached = set(left)
        pending = list(left)
        while pending:
            name = pending.pop()
            for neighbor in adjacency[name] - conditioned - reached:
                reached.add(neighbor)
                pending.append(neighbor)
        return not bool(reached & right)

    def backdoor_adjustment(self, treatment, outcome, *, adjustment=()):
        """Check a supplied adjustment set; refuse latent-confounding guarantees."""
        if treatment == outcome or treatment not in self.variables or outcome not in self.variables:
            raise ValueError('Distinct known treatment and outcome required')
        adjustment = tuple(adjustment)
        if len(set(adjustment)) != len(adjustment) or set(adjustment) & {treatment, outcome} or not set(adjustment) <= set(self.variables):
            raise ValueError('Invalid adjustment variables')
        descendants = {name for name in self.variables if treatment in self.ancestors({name}) and name != treatment}
        forbidden = sorted(set(adjustment) & descendants)
        blocked = self.d_separated({treatment}, {outcome}, conditioned=adjustment, remove_outgoing={treatment})
        valid = self.causal_sufficiency and not forbidden and blocked
        payload = {'schema_version': 1, 'model_id': self.model_id, 'treatment': treatment,
                   'outcome': outcome, 'adjustment': sorted(adjustment),
                   'descendants_in_adjustment': forbidden, 'backdoor_paths_blocked': blocked,
                   'causal_sufficiency_declared': self.causal_sufficiency,
                   'identified_under_declared_assumptions': valid,
                   'empirical_causal_identification_verified': False,
                   'mechanism_total_effect': str(self.total_effect(treatment, outcome)),
                   'scope': 'graphical backdoor sufficiency only; positivity and measurement require external evidence'}
        return {**payload, 'identification_id': fingerprint(payload)}


def replay_counterfactual(receipt, model):
    try:
        return receipt == model.counterfactual(receipt['observed'], receipt['interventions'])
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return False
