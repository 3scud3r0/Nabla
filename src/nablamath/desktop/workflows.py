"""Local consent-bound experiment workflow; no sockets, shell, or publication."""
import json
from pathlib import Path
from fractions import Fraction
from ..core.semantic_contracts import canonical_payload
from ..expression import parse_expr, Number, Symbol
from ..core.semantic_ir import fingerprint
from ..research import calculate
from ..storage import verify_record
from ..documents.document_model import Document, Section, Table
from ..reports.canonical_bundle import report_bundle


def _bounded_request(expression, values):
    """Check each exact arithmetic intermediate before expensive exponentiation."""
    if any(not isinstance(key, str) or not key.isidentifier() for key in values):
        raise ValueError('Assignment names must be identifiers')
    assigned = {}
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, str, Fraction)):
            raise ValueError('Exact rational assignments required')
        if isinstance(value, str) and len(value) > 256:
            raise ValueError('Assignment text exceeds budget')
        if isinstance(value, int) and value.bit_length() > 4096:
            raise ValueError('Assignment exceeds arithmetic budget')
        assigned[key] = Fraction(value)
    def checked(value):
        if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > 4096:
            raise ValueError('Exact arithmetic exceeds bit budget')
        return value
    def walk(node):
        if isinstance(node, Number):
            return checked(node.value)
        if isinstance(node, Symbol):
            return checked(assigned[node.name])
        left, right = walk(node.left), walk(node.right)
        if node.op == '**':
            if right.denominator != 1 or abs(right.numerator) > 32:
                raise ValueError('Bounded integer powers required')
            if max(abs(left.numerator).bit_length(), left.denominator.bit_length()) * abs(right.numerator) > 4096:
                raise ValueError('Power exceeds arithmetic bit budget')
            return checked(left ** right.numerator)
        if node.op == '+': return checked(left + right)
        if node.op == '-': return checked(left - right)
        if node.op == '*': return checked(left * right)
        if node.op == '/': return checked(left / right)
        raise ValueError('Unsupported exact operation')
    try:
        walk(parse_expr(expression))
    except (KeyError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("Invalid assignment or undefined arithmetic") from exc


def _canonical_report(result):
    evidence_id = fingerprint(result)
    document = Document('Local exact experiment', (Section('Result',
        'Exact evaluation of the submitted expression at declared rational assignments.',
        (evidence_id,), tables=(Table('Submitted assignments',('Variable','Value'),
            tuple((key,str(value)) for key,value in sorted(result['values'].items())) or (('none','constant'),),
            (evidence_id,)),)),), limitations='An exact instance is not a universally proved theorem or a learned generalization.')
    return report_bundle(document,{evidence_id:result})


class ExperimentWorkflow:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def execute(self, expression, values, *, consent=False, reviewer=''):
        if consent is not True or not isinstance(reviewer,str) or not reviewer.strip() or len(reviewer)>256:
            raise ValueError('Explicit local computation consent and reviewer required')
        if not isinstance(expression,str) or len(expression)>256 or type(values) is not dict or len(values)>32:
            raise ValueError('Bounded expression and assignments required')
        _bounded_request(expression, values)
        result = calculate(expression, values).to_data()
        if not verify_record(result):
            raise ValueError('Independent exact record replay failed')
        bundle = _canonical_report(result)
        payload = dict(schema_version=1, reviewer=reviewer, consent='local_compute_only',
            record=result, report=bundle, status='exact_instance_replayed',
            published=False, formal_proof=False)
        receipt = {**payload,'workflow_id':fingerprint(payload)}
        target = self.directory/(receipt['workflow_id']+'.json')
        raw = json.dumps(receipt,sort_keys=True,ensure_ascii=False)+'\n'
        # Content-addressed file, exclusive creation; retries verify existing bytes.
        try:
            with target.open('x',encoding='utf-8') as stream:
                stream.write(raw)
        except FileExistsError:
            if target.is_symlink() or target.read_text(encoding='utf-8') != raw:
                raise ValueError('Existing workflow record conflicts')
        return receipt

    @staticmethod
    def replay(receipt):
        try:
            canonical_payload(receipt)
            _bounded_request(receipt['record']['source'], receipt['record']['values'])
            payload = {key:value for key,value in receipt.items() if key!='workflow_id'}
            return (set(receipt)=={'schema_version','reviewer','consent','record','report','status','published','formal_proof','workflow_id'}
                and receipt['workflow_id']==fingerprint(payload)
                and type(receipt['schema_version']) is int and receipt['schema_version']==1
                and isinstance(receipt['reviewer'],str) and bool(receipt['reviewer'].strip())
                and len(receipt['reviewer'])<=256
                and receipt['consent']=='local_compute_only' and receipt['published'] is False
                and receipt['formal_proof'] is False and receipt['status']=='exact_instance_replayed'
                and verify_record(receipt['record'])
                and receipt['report']==_canonical_report(receipt['record']))
        except (ValueError,TypeError,KeyError,AttributeError,ZeroDivisionError,OverflowError):
            return False
