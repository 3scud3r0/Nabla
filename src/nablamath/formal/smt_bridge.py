"""QF_LRA over rationals, with explicit hypotheses and independently replayed SAT models."""
from fractions import Fraction
from ..core.semantic_ir import fingerprint,rational
from ..expression import Binary,Number,Symbol
from .statement import FormalStatement


def solve_statement(statement,*,timeout_ms=5000):
    if type(timeout_ms) is not int or not 1<=timeout_ms<=60000:
        raise ValueError('Timeout SMT deve estar entre 1 e 60000 ms')
    try:
        import z3
    except ImportError:
        return {'status':'unavailable','backend':'z3','formal_proof':False,'statement_id':statement.content_id}
    context=z3.Context(proof=True)
    variables={name:z3.Real('nabla_'+name,ctx=context) for name in statement.variables}
    def term(expr):
        if isinstance(expr,Number):
            return z3.RealVal(str(expr.value.numerator)+'/'+str(expr.value.denominator),ctx=context),True
        if isinstance(expr,Symbol):
            return variables[expr.name],False
        left,lc=term(expr.left);right,rc=term(expr.right)
        if expr.op=='+':return left+right,lc and rc
        if expr.op=='-':return left-right,lc and rc
        if expr.op=='*' and (lc or rc):return left*right,lc and rc
        if expr.op=='/' and rc:
            constant=z3.simplify(right)
            if not z3.is_rational_value(constant) or constant.numerator_as_long()==0:
                raise ValueError('zero_or_nonrational_constant_divisor')
            return left/right,lc
        if expr.op=='**' and isinstance(expr.right,Number) and expr.right.value in (0,1):
            return (z3.RealVal(1,ctx=context),True) if expr.right.value==0 else (left,lc)
        raise ValueError('outside_QF_LRA_fragment')
    def predicate(p):
        a,_=term(p.left);b,_=term(p.right)
        return {'eq':lambda:a==b,'ne':lambda:a!=b,'le':lambda:a<=b,'lt':lambda:a<b,'ge':lambda:a>=b,'gt':lambda:a>b}[p.relation]()
    base={'backend':'z3','logic':'QF_LRA','solver_version':z3.get_version_string(),
          'statement':statement.to_data(),'statement_id':statement.content_id,'formal_proof':False,
          'trust':'Z3 result; not a Lean kernel proof','timeout_ms':timeout_ms}
    try:
        assumptions=[predicate(p) for p in statement.hypotheses]
        goal=predicate(statement.goal)
    except ValueError as exc:
        return {**base,'status':'unsupported','reason':str(exc)}
    solver=z3.SolverFor('QF_LRA',ctx=context);solver.set(timeout=timeout_ms)
    solver.add(*assumptions)
    consistent=solver.check()
    if consistent==z3.unsat:
        return {**base,'status':'inconsistent_assumptions','reason':'vacuous theorem rejected','query':solver.sexpr()}
    if consistent==z3.unknown:
        return {**base,'status':'unknown','reason':solver.reason_unknown(),'query':solver.sexpr()}
    solver.add(z3.Not(goal))
    query=solver.sexpr();status=solver.check()
    result={**base,'query':query,'query_hash':fingerprint({'query':query})}
    if status==z3.unsat:
        proof=solver.proof().sexpr()
        result.update(status='unsat',proof=proof[:1000000],proof_truncated=len(proof)>1000000,
                      interpretation='goal holds for all rationals satisfying the explicit hypotheses')
    elif status==z3.sat:
        model=solver.model();witness={}
        for name,var in variables.items():
            value=model.eval(var,model_completion=True)
            if not z3.is_rational_value(value):
                return {**result,'status':'unknown','reason':'nonrational_model'}
            witness[name]=str(Fraction(value.numerator_as_long(),value.denominator_as_long()))
        exact={n:rational(v) for n,v in witness.items()}
        if not all(p.evaluate(exact) for p in statement.hypotheses) or statement.goal.evaluate(exact):
            return {**result,'status':'replay_failed','witness':witness}
        result.update(status='counterexample',witness=witness,exact_replay=True)
    else:
        result.update(status='unknown',reason=solver.reason_unknown())
    return {**result,'receipt_id':fingerprint(result)}
