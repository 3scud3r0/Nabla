"""Algorithmic judge for structured rational claims, not an OS code sandbox."""
from ..formal.statement import FormalStatement
from ..formal.smt_bridge import solve_statement
from ..calc.receipt import receipt


def verify_claim(statement, *, timeout_ms=5000):
    if isinstance(statement,dict):
        statement = FormalStatement.from_data(statement)
    if not isinstance(statement,FormalStatement):
        raise TypeError('A structured FormalStatement is required; free text is not a theorem')
    result = solve_statement(statement,timeout_ms=timeout_ms)
    status = result['status']
    verdict = ('supported_in_fragment' if status == 'unsat' else
               'refuted' if status == 'counterexample' and result.get('exact_replay') else 'unverified')
    return receipt('ai.verify_claim',statement.to_data(),{'verdict':verdict,'verification':result},
                   backend='z3',metadata={'timeout_ms':timeout_ms,'trust':'SMT result, not a Lean kernel proof'})


class SandboxVerifier:
    def verify(self, statement, **options):
        return verify_claim(statement,**options)

    def require_supported(self, statement, **options):
        record = self.verify(statement,**options)
        if record['result']['verdict'] != 'supported_in_fragment':
            raise ValueError('Mathematical claim rejected: '+record['result']['verdict'])
        return record
