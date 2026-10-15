import copy

import pytest

from nablamath.core.semantic_contracts import canonical_payload, load_json
from nablamath.core.migration_registry import MigrationRegistry
from nablamath.verification.evidence import EvidenceRequirement, REQUIRED
from nablamath.verification.independence import IndependencePolicy


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "coerced"}, (1, 2), {"set"}, 2**4097])
def test_reject_noncanonical_values(value):
    with pytest.raises(ValueError):
        canonical_payload(value)


@pytest.mark.parametrize("raw", ['{"a":1,"a":2}', '{"n":NaN}', '{"n":Infinity}', '[' * 100 + '0' + ']' * 100])
def test_reject_ambiguous_or_unbounded_json(raw):
    with pytest.raises(ValueError):
        load_json(raw)


def test_json_budgets_and_roundtrip():
    data = {"text": "ação", "nested": [1, True, None, 0.5]}
    assert load_json(canonical_payload(data)) == data
    assert canonical_payload({"b": 2, "a": 1}) == canonical_payload({"a": 1, "b": 2})
    for value in [[None] * 20001, {"text": "x" * 1_000_001}]:
        with pytest.raises(ValueError):
            canonical_payload(value)


def test_migration_is_explicit_forward_only_and_preserves_input():
    registry = MigrationRegistry()
    registry.register(1, lambda d: {**d, "schema_version": 2, "units": "SI"})
    original = {"schema_version": 1, "nested": [1]}
    before = copy.deepcopy(original)
    assert registry.migrate(original, 2)["units"] == "SI"
    assert original == before
    for target in [True, 0, 3, 100]:
        with pytest.raises(ValueError):
            registry.migrate(original, target)
    with pytest.raises(ValueError):
        registry.register(1, lambda d: d)
    registry.register(2, lambda d: {**d, "schema_version": True})
    with pytest.raises(ValueError):
        registry.migrate(original, 3)


def test_mutating_migration_never_mutates_callers_data():
    registry = MigrationRegistry()
    def step(data):
        data["nested"].append(2)
        data["schema_version"] = 2
        return data
    registry.register(1, step)
    data = {"schema_version": 1, "nested": [1]}
    assert registry.migrate(data, 2)["nested"] == [1, 2]
    assert data["nested"] == [1]


@pytest.mark.parametrize("kind", list(REQUIRED))
def test_evidence_requirements_and_unavailable_links(kind):
    roles = REQUIRED[kind]
    evidence = EvidenceRequirement(kind, "bounded claim", tuple((r, "a" * 64) for r in roles))
    evidence.validate_references({"a" * 64})
    with pytest.raises(ValueError):
        evidence.validate_references(set())
    with pytest.raises(ValueError):
        EvidenceRequirement(kind, "claim", tuple(evidence.links[:-1]))
    with pytest.raises(ValueError):
        EvidenceRequirement(kind, "claim", (*evidence.links, evidence.links[0]))


def test_actor_separation_is_explicit_and_not_authentication():
    policy = IndependencePolicy("proposer", "solver", "evaluator", "reviewer")
    assert len(set(policy.to_data().values())) == 4
    with pytest.raises(ValueError):
        IndependencePolicy("same", "solver", "same", "reviewer")
    with pytest.raises(ValueError):
        IndependencePolicy("", "solver", "evaluator", "reviewer")
