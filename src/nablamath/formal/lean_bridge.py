"""AST-only Lean translation; no user proof snippets, unchecked axioms or source injection."""
from dataclasses import dataclass
from ..core.semantic_ir import fingerprint
from .statement import FormalStatement,RELATIONS
from .translate import lean_term

STRATEGIES=('auto','ring','field','linarith','nlinarith','norm_num')


@dataclass(frozen=True)
class LeanTranslation:
    statement: FormalStatement
    source: str
    strategy: str='auto'

    @property
    def source_hash(self):
        return fingerprint({'source':self.source})

    def to_data(self):
        return {'backend':'lean4','statement':self.statement.to_data(),'statement_id':self.statement.content_id,
                'strategy':self.strategy,'source':self.source,'source_hash':self.source_hash,
                'bindings':{name:'nabla_'+name for name in self.statement.variables},
                'hypotheses':[p.to_data() for p in self.statement.hypotheses]}


def translate_statement(statement: FormalStatement,strategy='auto'):
    if strategy not in STRATEGIES:
        raise ValueError('Estrategia Lean nao permitida')
    def predicate(p):
        return f'{lean_term(p.left)} {RELATIONS[p.relation]} {lean_term(p.right)}'
    variables=' '.join(f'(nabla_{name} : ℚ)' for name in statement.variables)
    hypotheses=' '.join(f'(h{i} : {predicate(p)})' for i,p in enumerate(statement.hypotheses))
    names=', '.join(f'h{i}' for i in range(len(statement.hypotheses)))
    field=f'field_simp [{names}] <;> ring' if names else 'field_simp <;> ring'
    strategies={'ring':'ring','field':field,'linarith':'linarith','nlinarith':'nlinarith','norm_num':'norm_num',
                'auto':f'first | (solve | norm_num) | (solve | ring) | (solve | {field}) | (solve | linarith)'}
    source=('import Mathlib.Tactic.Ring\nimport Mathlib.Tactic.FieldSimp\nimport Mathlib.Tactic.Linarith\nimport Mathlib.Tactic.NormNum\n\nset_option autoImplicit false\nset_option maxHeartbeats 200000\n'
            +f'-- AST statement sha256: {statement.content_id}\n'
            +f'theorem nabla_generated {variables} {hypotheses} : {predicate(statement.goal)} := by\n'
            +f'  {strategies[strategy]}\n\n#print axioms nabla_generated\n')
    return LeanTranslation(statement,source,strategy)
