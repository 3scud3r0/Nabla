"""Bounded, reviewable experiment plans containing registered tool data only."""
from dataclasses import dataclass
from ..core.semantic_ir import canonical_json, fingerprint
from .proposals import Action, Proposal


@dataclass(frozen=True)
class ExperimentPlan:
    proposal: Proposal
    owner: str
    hypothesis: str
    expected_observation: str
    protocol_version: str = '1'

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip() or len(v) > 4096
               for v in (self.owner, self.hypothesis, self.expected_observation, self.protocol_version)):
            raise ValueError('Explicit owner, hypothesis, observation and version required')
        if not isinstance(self.proposal, Proposal):
            raise ValueError('Declarative proposal required')

    def to_data(self):
        return dict(proposal=self.proposal.to_data(), owner=self.owner,
                    hypothesis=self.hypothesis, expected_observation=self.expected_observation,
                    protocol_version=self.protocol_version)

    @property
    def content_id(self):
        return fingerprint(self.to_data())

    def preflight(self, registry, permissions):
        if len(self.proposal.actions) > permissions.max_calls:
            raise ValueError('Experiment exceeds call budget')
        if len(canonical_json(self.to_data()).encode()) > permissions.max_input_bytes:
            raise ValueError('Experiment exceeds input budget')
        for action in self.proposal.actions:
            registry.validate(action.tool, action.arguments, permissions)
        return self.content_id


def plan_experiment(*, question, owner, hypothesis, expected_observation, trials,
                    registry, permissions):
    """Preserve trial order; validate the entire plan before any execution."""
    actions = []
    for trial in trials:
        if len(actions) >= permissions.max_calls:
            raise ValueError('Experiment exceeds call budget')
        actions.append(Action(trial['id'], trial['tool'], canonical_json(trial['arguments']),
                              tuple(trial.get('depends_on', ()))))
    plan = ExperimentPlan(Proposal(question, tuple(actions),
                          'Registered trusted tools only; observations require independent review.'),
                          owner, hypothesis, expected_observation)
    plan.preflight(registry, permissions)
    return plan
