"""Spawn-safe SMT worker. Only controlled rational expressions cross the pipe."""
from fractions import Fraction
import json
import re
import time


def statement_from_conjecture(data):
    from ..formal.statement import FormalStatement,Predicate
    from ..expression import parse_expr
    if isinstance(data,dict) and 'schema_version' in data:
        return FormalStatement.from_data(data)
    if isinstance(data,str):
        data = {'goal':data,'assumptions':[]}
    if not isinstance(data,dict) or not {'goal'} <= set(data) <= {'goal','assumptions'}:
        raise ValueError('Use a structured statement or a controlled relation, not natural language')
    def predicate(source):
        if not isinstance(source,str) or not 1 <= len(source) <= 4096:
            raise ValueError('A bounded controlled relation is required')
        parts = re.split(r'(==|!=|<=|>=|=|<|>)',source)
        if len(parts) != 3:
            raise ValueError('Conjectures require exactly one relation')
        left,relation,right = parts
        relations = {'=':'eq','==':'eq','!=':'ne','<':'lt','<=':'le','>':'gt','>=':'ge'}
        return Predicate(parse_expr(left.strip()),relations[relation],parse_expr(right.strip()))
    assumptions = data.get('assumptions',[])
    if not isinstance(assumptions,list) or len(assumptions) > 32:
        raise ValueError('At most 32 explicit assumptions are allowed')
    return FormalStatement(predicate(data['goal']),tuple(predicate(p) for p in assumptions))


def _solve(data, timeout_ms, logic):
    statement = statement_from_conjecture(data)
    if logic == 'QF_LRA':
        from ..formal.smt_bridge import solve_statement
        return solve_statement(statement,timeout_ms=timeout_ms)
    try:
        import z3
    except ImportError:
        return {'status':'unavailable','backend':'z3','formal_proof':False}
    from ..expression import Number,Symbol
    context = z3.Context()
    variables = {name:z3.Real('nabla_'+name,ctx=context) for name in statement.variables}
    def term(expression):
        if isinstance(expression,Number):
            return z3.RealVal(f'{expression.value.numerator}/{expression.value.denominator}',ctx=context)
        if isinstance(expression,Symbol):
            return variables[expression.name]
        left,right = term(expression.left),term(expression.right)
        if expression.op == '+': return left+right
        if expression.op == '-': return left-right
        if expression.op == '*': return left*right
        if expression.op == '/': return left/right
        if expression.op == '**' and isinstance(expression.right,Number) and expression.right.value.denominator == 1 and abs(expression.right.value.numerator) <= 32:
            return left**expression.right.value.numerator
        raise ValueError('outside_rational_polynomial_fragment')
    def predicate(p):
        a,b = term(p.left),term(p.right)
        return {'eq':lambda:a==b,'ne':lambda:a!=b,'lt':lambda:a<b,'le':lambda:a<=b,
                'gt':lambda:a>b,'ge':lambda:a>=b}[p.relation]()
    base = {'backend':'z3','logic':'QF_NRA','solver_version':z3.get_version_string(),
            'statement':statement.to_data(),'statement_id':statement.content_id,
            'formal_proof':False,'trust':'Z3 result in the declared rational-expression fragment, not a Lean kernel certificate'}
    try:
        assumptions = [predicate(p) for p in statement.hypotheses]
        goal = predicate(statement.goal)
    except ValueError as error:
        return {**base,'status':'unsupported','reason':str(error)}
    solver = z3.Solver(ctx=context)
    deadline = time.monotonic()+timeout_ms/1000
    def check():
        remaining = max(1,int((deadline-time.monotonic())*1000))
        solver.set(timeout=remaining)
        return solver.check()
    solver.add(*assumptions)
    consistent = check()
    if consistent == z3.unsat:
        return {**base,'status':'inconsistent_assumptions','reason':'Vacuous claims are rejected'}
    if consistent == z3.unknown:
        return {**base,'status':'unknown','reason':solver.reason_unknown()}
    solver.add(z3.Not(goal))
    status = check()
    if status == z3.unsat:
        return {**base,'status':'unsat','interpretation':'No real counterexample under the explicit hypotheses; therefore no rational counterexample'}
    if status == z3.unknown:
        return {**base,'status':'unknown','reason':solver.reason_unknown()}
    model = solver.model(); witness = {}
    for name,symbol in variables.items():
        value = model.eval(symbol,model_completion=True)
        if not z3.is_rational_value(value):
            return {**base,'status':'unknown','reason':'An algebraic real model is not an independently replayed rational counterexample',
                    'solver_model':str(model)[:4096]}
        witness[name] = str(Fraction(value.numerator_as_long(),value.denominator_as_long()))
    values = {name:Fraction(value) for name,value in witness.items()}
    if not all(p.evaluate(values) for p in statement.hypotheses) or statement.goal.evaluate(values):
        return {**base,'status':'replay_failed','witness':witness}
    return {**base,'status':'counterexample','witness':witness,'exact_replay':True}


def verify_worker(connection, data, timeout_ms, logic):
    try:
        result = _solve(data,timeout_ms,logic)
        raw = json.dumps(result,allow_nan=False,separators=(',',':')).encode()
        if len(raw) > 1048576:
            raw = b'{"status":"error","reason":"SMT response exceeds byte budget"}'
        connection.send_bytes(raw)
    except Exception as error:
        connection.send_bytes(json.dumps({'status':'error','reason':str(error)[:1000]}).encode())
    finally:
        connection.close()
