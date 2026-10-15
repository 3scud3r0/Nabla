"""Serializable plans contain typed data, never executable code."""
from dataclasses import dataclass
import json
import re
from ..core.semantic_ir import canonical_json, fingerprint


@dataclass(frozen=True)
class Action:
    action_id: str
    tool: str
    arguments_json: str
    depends_on: tuple[str, ...] = ()

    def __post_init__(self):
        for name in (self.action_id, self.tool):
            if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,63}', name):
                raise ValueError('Identificador de ação/ferramenta inválido')
        arguments = json.loads(self.arguments_json)
        if not isinstance(arguments, dict):
            raise ValueError('Argumentos devem ser objeto JSON')
        object.__setattr__(self, 'arguments_json', canonical_json(arguments))
        object.__setattr__(self, 'depends_on', tuple(self.depends_on))

    @property
    def arguments(self):
        return json.loads(self.arguments_json)


@dataclass(frozen=True)
class Proposal:
    question: str
    actions: tuple[Action, ...]
    limitations: str

    def __post_init__(self):
        object.__setattr__(self, 'actions', tuple(self.actions))
        if not self.question.strip() or not self.limitations.strip() or not self.actions:
            raise ValueError('Questão, ações e limites obrigatórios')
        ids = [a.action_id for a in self.actions]
        if len(set(ids)) != len(ids) or len(ids) > 100:
            raise ValueError('Ações duplicadas ou excessivas')
        seen = set()
        for action in self.actions:
            if not set(action.depends_on) <= seen:
                raise ValueError('Dependências devem preceder a ação; ciclos não permitidos')
            from .bindings import references
            if any(ref['action'] not in action.depends_on for ref in references(action.arguments)):
                raise ValueError('Referência requer dependência explícita anterior')
            seen.add(action.action_id)

    def to_data(self):
        return {'question': self.question, 'limitations': self.limitations,
                'actions': [{'id': a.action_id, 'tool': a.tool, 'arguments': a.arguments,
                             'depends_on': list(a.depends_on)} for a in self.actions]}

    @property
    def content_id(self):
        return fingerprint(self.to_data())

    @classmethod
    def from_data(cls, data):
        return cls(data['question'], tuple(Action(a['id'], a['tool'], canonical_json(a['arguments']),
                   tuple(a.get('depends_on', ()))) for a in data['actions']), data['limitations'])
