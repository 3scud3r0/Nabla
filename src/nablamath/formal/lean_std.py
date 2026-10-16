"""Lean kernel proofs for typed rational statements using the pinned Std library.

No Mathlib download or Lake build is needed. The backend generates all source
from a FormalStatement and audits the theorem's axioms. Std's grind tactic
constructs proof terms; this module never uses native_decide or user Lean code.
"""

from pathlib import Path
import os
import re
import subprocess
import tempfile

from ..core.semantic_ir import fingerprint
from .lean_checker import ALLOWED_AXIOMS, find_lake, run_lean_process
from .statement import FormalStatement, RELATIONS
from .translate import lean_term
from .translate import free_symbols
from ..expression import Binary, Number, Symbol, evaluate


BACKEND = 'lean4-std'


def _positivity_facts(statement):
    """Build proof terms for explicit squares, positive products and box gaps.

    These are proved Lean lemmas, not extra assumptions. Emitting them makes
    nonlinear facts available to grind's linear/ring solvers without asking
    E-matching to invent expressions absent from the goal's proposition index.
    """
    if statement.goal.relation in ('eq', 'ne'):
        return ''
    facts = {}
    lines = []

    def term(expr):
        return lean_term(expr).replace('ℚ', 'Rat').replace('ℕ', 'Nat')

    def add(expr, proof):
        if expr in facts:
            return facts[expr]
        if len(facts) >= 128:
            raise ValueError('Lean positivity fact budget exceeded')
        name = f'nabla_nonneg_{len(facts)}'
        facts[expr] = name
        lines.append(f'  have {name} : (0 : Rat) ≤ {term(expr)} := by {proof}\n')
        return name

    def visit(expr, required=False):
        if expr in facts:
            return facts[expr]
        if not free_symbols(expr):
            if not required:
                return None
            try:
                if evaluate(expr, {}) >= 0:
                    return add(expr, 'decide +kernel')
            except (ValueError, ArithmeticError):
                pass
            return None
        if isinstance(expr, Binary):
            if expr.op == '**' and isinstance(expr.right, Number) and expr.right.value == 2:
                return add(expr, 'exact Lean.Grind.OrderedRing.sq_nonneg')
            left = visit(expr.left, required=expr.op == '*')
            right = visit(expr.right, required=expr.op == '*')
            if expr.op == '*' and left is not None and right is not None:
                return add(expr, f'exact Lean.Grind.OrderedRing.mul_nonneg {left} {right}')
        return None

    for predicate in (statement.goal, *statement.hypotheses):
        visit(predicate.left)
        visit(predicate.right)
    lower, upper = {}, {}
    for predicate in statement.hypotheses:
        if isinstance(predicate.left, Symbol) and not free_symbols(predicate.right):
            if predicate.relation == 'ge':
                lower.setdefault(predicate.left, []).append(predicate.right)
            elif predicate.relation == 'le':
                upper.setdefault(predicate.left, []).append(predicate.right)
    for variable in sorted(lower.keys() & upper.keys(), key=lambda value: value.name):
        for left in lower[variable]:
            for right in upper[variable]:
                first = Binary('-', variable, left)
                second = Binary('-', right, variable)
                hfirst = add(first, 'grind')
                hsecond = add(second, 'grind')
                add(Binary('*', first, second),
                    f'exact Lean.Grind.OrderedRing.mul_nonneg {hfirst} {hsecond}')
    return ''.join(lines)


def std_source(statement):
    if not isinstance(statement, FormalStatement):
        raise ValueError('Enunciado formal tipado obrigatório')

    def predicate(value):
        left = lean_term(value.left).replace('ℚ', 'Rat').replace('ℕ', 'Nat')
        right = lean_term(value.right).replace('ℚ', 'Rat').replace('ℕ', 'Nat')
        return f'{left} {RELATIONS[value.relation]} {right}'

    variables = ' '.join(f'(nabla_{name} : Rat)' for name in statement.variables)
    hypotheses = ' '.join(f'(h{index} : {predicate(value)})'
                          for index, value in enumerate(statement.hypotheses))
    tactic = 'grind' if statement.variables else 'decide +kernel'
    facts = _positivity_facts(statement) if statement.variables else ''
    return ('import Std\nset_option autoImplicit false\n'
            'set_option maxHeartbeats 200000\nset_option maxRecDepth 1024\n'
            f'-- Typed statement: {statement.content_id}\n'
            f'theorem nabla_std_generated {variables} {hypotheses} : {predicate(statement.goal)} := by\n'
            +facts+f'  {tactic}\n\n#print axioms nabla_std_generated\n')


def prove_with_std(statement, project=Path('lean'), *, timeout=30):
    """Return proved only after kernel checking and a successful axiom audit.

    A timeout, an unavailable pinned compiler and a failed proof are distinct.
    Contradictory hypotheses prove only the displayed conditional proposition;
    the backend does not claim their satisfiability or a real-world theorem.
    """
    if type(timeout) is not int or not 1 <= timeout <= 300:
        raise ValueError('Timeout Lean deve estar entre 1 e 300 segundos')
    source = std_source(statement)
    project = Path(project).resolve()
    source_hash = fingerprint({'source': source})

    def receipt(status, diagnostics, *, version=None, axioms=(), returncode=None):
        payload = {
            'backend': BACKEND, 'status': status, 'statement_id': statement.content_id,
            'source_hash': source_hash, 'tool_version': version, 'axioms': list(axioms),
            'returncode': returncode, 'formal_proof': status == 'proved',
            'strategy': 'grind' if statement.variables else 'decide-kernel',
            'diagnostics': diagnostics,
            'scope': 'Displayed conditional rational proposition; no satisfiability or natural-language equivalence claim',
        }
        return {**payload, 'receipt_id': fingerprint(payload)}

    pin_file = project/'lean-toolchain'
    if not pin_file.is_file():
        return receipt('unavailable', 'Pinned Lean project missing')
    pin = re.fullmatch(r'leanprover/lean4:v([0-9]+\.[0-9]+\.[0-9]+)',
                       pin_file.read_text(encoding='utf-8').strip())
    if pin is None:
        return receipt('unavailable', 'Unsupported Lean toolchain pin')
    lake = find_lake(project)
    if lake is None:
        return receipt('unavailable', 'Pinned Lean compiler not installed')
    lean = lake.with_name('lean')
    environment = dict(os.environ)
    environment['PATH'] = str(lean.parent)+os.pathsep+environment.get('PATH', '')
    # Prevent a caller's LEAN_PATH from introducing shadow copies of Std.
    environment.pop('LEAN_PATH', None)
    environment.pop('LEAN_SRC_PATH', None)
    version_text = None
    try:
        version = run_lean_process([str(lean), '--version'], cwd=project,
                                  env=environment, timeout=min(timeout, 20))
        version_text = version.stdout.strip()
        if version.returncode or not re.search(r'Lean \(version '+re.escape(pin[1])+r'(?:,|\))', version_text):
            return receipt('unavailable', 'Compiler version does not match project pin', version=version_text)
        with tempfile.TemporaryDirectory(prefix='nabla-std-proof-') as directory:
            path = Path(directory)/'Proof.lean'
            path.write_text(source, encoding='utf-8')
            completed = run_lean_process([str(lean), str(path)], cwd=directory,
                                        env=environment, timeout=timeout)
    except (FileNotFoundError, PermissionError):
        return receipt('unavailable', 'Lean compiler could not be executed')
    except subprocess.TimeoutExpired:
        return receipt('timeout', 'Lean kernel proof timed out', version=version_text)
    output = completed.stdout+'\n'+completed.stderr
    matches = re.findall(r"'nabla_std_generated' depends on axioms:\s*\[([^\]]*)\]", output)
    no_axioms = "'nabla_std_generated' does not depend on any axioms" in output
    axioms = sorted({name.strip() for group in matches for name in group.split(',') if name.strip()})
    if completed.returncode:
        status = 'failed'
    elif 'sorry' in output or set(axioms)-ALLOWED_AXIOMS or not (matches or no_axioms):
        status = 'rejected_axioms'
    else:
        status = 'proved'
    return receipt(status, output[-6000:], version=version_text,
                   axioms=axioms, returncode=completed.returncode)


def std_translation(statement):
    source = std_source(statement)
    return {'backend': BACKEND, 'statement_id': statement.content_id,
            'source': source, 'source_hash': fingerprint({'source': source})}


def verify_std_receipt(statement, saved, *, project=Path('lean')):
    """Reprove the exact statement; never accept a saved success flag alone."""
    try:
        payload = dict(saved)
        digest = payload.pop('receipt_id')
        if digest != fingerprint(payload) or saved['backend'] != BACKEND:
            return False
        if saved['formal_proof'] is not True or saved['status'] != 'proved':
            return False
        fresh = prove_with_std(statement, project)
        fields = ('backend', 'status', 'statement_id', 'source_hash', 'tool_version',
                  'axioms', 'returncode', 'formal_proof', 'strategy', 'scope')
        return (fresh['status'] == 'proved' and all(saved[key] == fresh[key] for key in fields)
                and type(saved['returncode']) is int)
    except (ValueError, TypeError, KeyError):
        return False
