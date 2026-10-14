"""Task-linked modalities with an explicit separation of inputs and target evidence."""
from dataclasses import dataclass
from fractions import Fraction
from html import escape
import json
from ..core.semantic_ir import canonical_json, fingerprint, rational, PolynomialSpec
from .schema import ScientificRecord

INPUT_MODALITIES = ('text', 'equation', 'diagram')


def _diagram(task):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="300" viewBox="0 0 900 300">',
             '<rect width="900" height="300" fill="white"/>',
             '<text x="12" y="22">'+escape(task.family)+' | problem representation</text>']
    if task.family in {'polynomial_integral', 'factored_polynomial'}:
        polynomial = PolynomialSpec(tuple(task.problem['coefficients']))
        values = [polynomial.evaluate(Fraction(i,20)) for i in range(-40,41)]
        scale = max(abs(v) for v in values) or 1
        points = ' '.join(f'{20+860*i/80:.3f},{155-115*float(v/scale):.3f}' for i,v in enumerate(values))
        parts += ['<path d="M20 155H880" stroke="gray"/>',
                  '<polyline fill="none" stroke="#1859a9" stroke-width="2" points="'+points+'"/>',
                  '<text x="12" y="290">x in [-2,2]; p(x) scaled by '+escape(str(scale))+'</text>']
    else:
        problem = task.problem
        matrix = problem.get('matrix', problem.get('transition'))
        if matrix:
            limit = max(abs(rational(v)) for row in matrix for v in row) or 1
            for i,row in enumerate(matrix):
                for j,value in enumerate(row):
                    intensity = int(245-150*float(abs(rational(value))/limit))
                    x,y = 20+100*j, 40+28*i
                    parts += [f'<rect x="{x}" y="{y}" width="96" height="26" fill="rgb({intensity},{intensity},250)"/>',
                              f'<text x="{x+4}" y="{y+19}">'+escape(str(value))+'</text>']
        else:
            parts += ['<text x="12" y="70">'+escape(canonical_json(problem))+'</text>']
    return ''.join(parts+['</svg>'])


def _modalities(record, include_simulation):
    task = record.task
    task_id = task.content_id
    problem = task.problem
    prompt = f'Solve {task.family}: '+canonical_json(problem)
    svg = _diagram(task)
    contents = [('text', 'input', prompt), ('equation', 'input', problem), ('diagram', 'input', svg),
                ('reasoning', 'target', record.to_data()['trace']),
                ('proof', 'target', {'certificates': record.to_data()['formal_certificates'],
                                     'scope': 'associated statements; no inferred equivalence to task'})]
    if include_simulation:
        if task.family != 'polynomial_integral':
            raise ValueError('Simulação multimodal suporta somente integral polinomial')
        from ..math.equations.ode import integrate
        polynomial = PolynomialSpec(tuple(problem['coefficients']))
        trajectory = integrate(lambda x, y: (float(polynomial.evaluate(Fraction(str(x)))),), (0.0,), 0., 1., 100, 'rk4')
        coefficients = [rational(v) for v in record.to_data()['trace']['candidate']['coefficients']]
        reference = float(sum(coefficients[1:]))
        contents.append(('simulation', 'target', {'equation': 'dy/dx=p(x), y(0)=0', 'independent_unit': 'dimensionless',
                          'method': 'rk4', 'trajectory': trajectory, 'reference_final': reference,
                          'absolute_error': abs(trajectory[-1][1][0]-reference), 'experimental_validation': False}))
    return [{'kind': kind, 'role': role, 'task_id': task_id, 'content': content,
             'content_id': fingerprint({'kind': kind, 'role': role, 'task_id': task_id, 'content': content})}
            for kind,role,content in contents]


@dataclass(frozen=True)
class MultimodalSample:
    payload_json: str

    def __post_init__(self):
        data = json.loads(self.payload_json)
        if set(data) != {'schema_version', 'record', 'include_simulation', 'modalities'} or data['schema_version'] != 1:
            raise ValueError('Contrato multimodal inválido')
        record = ScientificRecord.from_data(data['record'])
        if type(data['include_simulation']) is not bool:
            raise ValueError('Flag de simulação inválida')
        expected = _modalities(record, data['include_simulation'])
        if canonical_json(data['modalities']) != canonical_json(expected):
            raise ValueError('Modalidades não correspondem ao problema/solução')
        object.__setattr__(self, 'payload_json', canonical_json(data))

    @property
    def record(self):
        return ScientificRecord.from_data(self.to_data()['record'])

    def to_data(self):
        return json.loads(self.payload_json)

    def inputs(self, modalities=INPUT_MODALITIES):
        if not modalities or len(set(modalities)) != len(modalities) or not set(modalities) <= set(INPUT_MODALITIES):
            raise ValueError('Modalidades de entrada inválidas; evidências alvo são reservadas')
        # Only selected problem representations are exposed, never solution/receipts.
        data = self.to_data()
        return {'task_id': self.record.task.content_id, 'family': self.record.task.family, 'size': self.record.task.size,
                'modalities': [m for m in data['modalities'] if m['role'] == 'input' and m['kind'] in modalities]}


def build_sample(record, *, include_simulation=False):
    return MultimodalSample(canonical_json({'schema_version': 1, 'record': record.to_data(),
                            'include_simulation': include_simulation,
                            'modalities': _modalities(record, include_simulation)}))
