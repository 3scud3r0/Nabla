"""Procedural worked solutions, counterexamples and correction datasets.

No model inference or imitation of private neural deliberations. Every accepted
calculation has a replayable Nabla receipt. Reexecution checks implementation
consistency; only explicit residual certificates provide additional mathematical
checks. Hashes certify bytes, not mathematical truth or training usefulness.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
import hashlib
from importlib.metadata import version, PackageNotFoundError
import json
import math
from pathlib import Path
import random
import platform
import shutil
import tempfile

from ..calc.session import CalculationSession, AREAS, EXTENDED_OPERATIONS
from ..core.semantic_ir import canonical_json, fingerprint
from .synthetic_recipes import RECIPES, NUMERICAL_FAMILIES
from .synthetic_certificates import reference_certificate

VERSION = 'procedural-trajectories-v1'
NOTICE = ('Trajetórias sintéticas de soluções matemáticas, produzidas por regras. '
          'Não são pensamentos internos de redes neurais nem reproduções de o1/o3. '
          'Reexecução não é verificação independente; hashes não são provas. '
          'Dificuldade não calibrada; utilidade de treino não avaliada.')
SPECIAL = {
    'chain_rule': ('Regra da cadeia e derivadas sucessivas', 'calculus'),
    'lyapunov': ('Lyapunov discreto e resíduos matriciais exatos', 'linear_algebra'),
    'ito_stratonovich': ('Conversão Itô–Stratonovich e sinal da correção', 'probability'),
    'lorentz_signature': ('Contração tensorial e assinatura lorentziana', 'geometry'),
    'matrix_noncommutativity': ('Produtos não comutativos e comutador', 'linear_algebra'),
    'rational_domain': ('Identidades racionais com domínio parcial', 'algebra'),
}
FAMILIES = tuple(SPECIAL) + tuple(RECIPES)
MAX_DEPTH = 256


def _integer(value, lower, upper, name):
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f'{name}: inteiro entre {lower} e {upper} requerido')
    return value


@dataclass(frozen=True)
class GenerationConfig:
    seed: int = 20261017
    difficulty: int = 4
    depth: int = 8
    error_rate: float = 0.35

    def __post_init__(self):
        _integer(self.seed, 0, 2**63-1, 'seed')
        _integer(self.difficulty, 1, 8, 'difficulty')
        _integer(self.depth, 1, MAX_DEPTH, 'depth')
        if isinstance(self.error_rate, bool) or not isinstance(self.error_rate, (int, float)) or not math.isfinite(self.error_rate) or not 0 <= self.error_rate <= 1:
            raise ValueError('error_rate deve estar em [0,1]')

    def data(self):
        return dict(seed=self.seed, difficulty=self.difficulty, depth=self.depth, error_rate=self.error_rate)


def _leaves(value, path=()):
    if isinstance(value, dict):
        for key, child in sorted(value.items()):
            if key not in {'hypotheses','limitations','scope','backend','backend_version','domain','arithmetic','method','formal_proof'}:
                yield from _leaves(child, path+(key,))
    elif isinstance(value, list):
        for i, child in enumerate(value):
            yield from _leaves(child, path+(i,))
    else:
        yield path, value


def _set(value, path, replacement):
    if not path:
        return replacement
    result = deepcopy(value)
    node = result
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = replacement
    return result


def _expression_source(node):
    """Render only the closed expression AST returned by CalculationSession."""
    if node['kind'] == 'number':
        value = Fraction(node['numerator'],node['denominator'])
        return str(value.numerator) if value.denominator == 1 else f'({value})'
    if node['kind'] == 'symbol':
        return node['name']
    if node['kind'] != 'binary' or node['op'] not in {'+','-','*','/','**'}:
        raise ValueError('AST aritmética desconhecida')
    return f"({_expression_source(node['left'])}{node['op']}{_expression_source(node['right'])})"


class ErrorInjectionEngine:
    """Explicit result corruption; conceptual mutations live in special recipes."""
    @staticmethod
    def corrupt(result, rng):
        candidates = []
        for path, value in _leaves(result):
            if isinstance(value, bool):
                candidates.append((path, not value, 'boolean_inversion'))
            elif type(value) is int:
                candidates.append((path, value+1, 'integer_off_by_one'))
            elif type(value) is float and math.isfinite(value):
                replacement = value+max(1., abs(value)/10)
                if math.isfinite(replacement):
                    candidates.append((path, replacement, 'numeric_perturbation'))
            elif isinstance(value, str) and len(value) < 128:
                try:
                    q = Fraction(value)
                    candidates.append((path, str(q+Fraction(1, q.denominator)), 'rational_numerator_perturbation'))
                except (ValueError, ZeroDivisionError):
                    pass
        if not candidates:
            # This is explicitly a structural mismatch, not an invented theorem.
            return {'corrupted_result': result}, {'kind':'structural_corruption','path':[]}
        path, replacement, kind = rng.choice(candidates)
        return _set(result, path, replacement), {'kind':kind,'path':list(path)}


class ContradictionDetector:
    """Replay a closed calculation; distinguish disagreement from a proof."""
    @staticmethod
    def check(audit, candidate):
        actual = CalculationSession.replay_request(audit['request']).to_data()
        if actual != audit:
            raise ArithmeticError('Recibo diverge da reexecução')
        differences = []
        if candidate != actual['result']:
            good = dict(_leaves(actual['result']))
            bad = dict(_leaves(candidate))
            for path in sorted(set(good)|set(bad), key=repr):
                if path not in good or path not in bad or good[path] != bad[path]:
                    row = {'path':list(path),'expected':good.get(path),'observed':bad.get(path)}
                    try:
                        row['rational_delta'] = str(Fraction(str(bad[path]))-Fraction(str(good[path])))
                    except (ValueError, ZeroDivisionError, KeyError):
                        pass
                    differences.append(row)
        return {'accepted':candidate == actual['result'], 'method':'catalog_reexecution',
                'independent':False,'differences':differences,
                'scope':'Concordância com o cálculo reexecutado; não valida prosa nem prova verdade universal.'}


class TextualReasoningFormatter:
    """Portuguese technical derivations, without fictional introspective prose."""
    @staticmethod
    def solution(record, *, include_errors=False):
        lines = [record['prompt'], '', 'Hipóteses e método: '+record['method'],
                 'Natureza: solução procedural; verificações têm escopo local.']
        for step in record['steps']:
            lines += ['', f"Etapa {step['index']}: {step['description']}",
                      'Requisição: '+canonical_json(step['receipt']['request']),
                      'Resultado aceito: '+canonical_json(step['receipt']['result'])]
            if include_errors and step.get('error'):
                e = step['error']
                lines += ['Candidato deliberadamente incorreto ['+e['mutation']['kind']+']: '+canonical_json(e['candidate']),
                          'Diagnóstico observado: '+canonical_json(e['detection']),
                          'Correção: descartar o candidato reprovado e usar o resultado aceito acima.']
            if step.get('certificate'):
                lines += ['Certificado adicional: '+canonical_json(step['certificate'])]
            lines += ['Contrato da operação: '+step['contract'],
                      'Recibo de cálculo: '+step['receipt']['content_id']]
        lines += ['', 'Resposta final: '+canonical_json(record['answer']),
                  'Limites: '+NOTICE]
        return '\n'.join(lines)

    @classmethod
    def sample(cls, record, number):
        return (f"{'='*88}\nAMOSTRA {number:03d} | {record['family']} | {record['id']}\n"
                f"Área: {record['area']} | partição por família: {record['split']}\n"
                +cls.solution(record, include_errors=True)+'\n\n')


class _Builder:
    def __init__(self, config, family, index):
        self.config, self.family, self.index = config, family, index
        self.rng = random.Random(int(fingerprint([VERSION,config.seed,family,index]),16))
        self.session = CalculationSession()
        self.steps = []

    def calc(self, operation, description, *, wrong=None, mutation=None, certificate=None, **arguments):
        audit = self.session.execute(operation, **arguments).to_data()
        contract = EXTENDED_OPERATIONS[operation][3] if operation in EXTENDED_OPERATIONS else 'Cálculo racional no domínio limitado da operação; sem prova formal.'
        step = {'index':len(self.steps)+1,'description':description,'receipt':audit,
                'depends_on': [], 'contract':contract}
        # Receipts express ordering; actual data dependencies are declared by
        # special builders, never invented between independent subproblems.
        additional = reference_certificate(operation,arguments,audit['result'])
        if additional is not None:
            step['certificate'] = additional
        if certificate is not None:
            step['certificate'] = certificate
        if self.rng.random() < self.config.error_rate:
            if wrong is None:
                wrong, mutation = ErrorInjectionEngine.corrupt(audit['result'], self.rng)
            if wrong != audit['result']:
                detection = ContradictionDetector.check(audit, wrong)
                if detection['accepted']:
                    raise ArithmeticError('Mutação não detectada')
                step['error'] = {'synthetic':True,'candidate':wrong,'mutation':mutation,
                                 'detection':detection,'label':-1,'corrected_label':1}
        self.steps.append(step)
        return audit['result']

    def equality(self, left, right, description, *, valid=True):
        result = self.calc('rational_compare', description, left=left, right=right)
        actual = result['equal_on_common_domain'] and result['domain_equivalence_established']
        if actual != valid:
            raise ArithmeticError('Identidade ou domínio inesperado')
        return result

    def zero(self, expression, description):
        result = self.calc('evaluate', description, source=expression)
        if Fraction(result['value']) != 0:
            raise ArithmeticError('Resíduo não nulo')
        self.steps[-1]['certificate'] = {'kind':'exact_residual','value':'0','independent':False,
                                           'scope':'Substituição explícita; mesma biblioteca aritmética do Nabla.'}
        return result


def _polynomial(b):
    d = b.config.difficulty
    a, c = b.rng.randint(2,7), b.rng.randint(1,5)
    n = d+2
    current = f'({a}*x**2+{c})**{n}'
    initial = current
    for order in range(1, min(b.config.depth, 2*n)+1):
        result = b.calc('differentiate',f'Derivada de ordem {order}; aplicar produto e cadeia.',source=current)
        derivative = _expression_source(result['expression'])
        if order == 1:
            expected = f'{n}*({a}*x**2+{c})**{n-1}*{2*a}*x'
            b.equality(derivative,expected,'Conferir a derivada composta com fator interno explícito.')
            wrong = f'{n}*({a}*x**2+{c})**{n-1}'
            evidence = b.equality(wrong,expected,'Contraexemplo algébrico à omissão da regra da cadeia.',valid=False)
            b.steps[-1]['certificate'] = {'kind':'deliberate_false_identity','mutation':'missing_chain_factor','accepted':False,'evidence':evidence}
        # Canonical coefficient expansion prevents exponential AST growth on
        # repeated derivatives while checking equivalence with Nabla arithmetic.
        coefficients = [math.comb(n,k)*a**k*c**(n-k) for k in range(n+1)]
        current = '+'.join(f'({coefficient*math.factorial(2*k)//math.factorial(2*k-order)})*x**{2*k-order}'
                           for k,coefficient in enumerate(coefficients) if 2*k >= order) or '0'
        b.equality(derivative,current,f'Conferir expansão binomial da derivada de ordem {order}.')
    return f'Derive sucessivamente f(x)={initial}, em R, até ordem {min(b.config.depth,2*n)}. Identifique a omissão da regra da cadeia.', {'derivative':current,'order':min(b.config.depth,2*n)}, 'Polinômios em R; regra da cadeia, diferenciação sucessiva e identidade racional.'


def _lyapunov(b):
    from ..math.linear_algebra import Matrix
    n = min(5, b.config.difficulty+1)
    q = Fraction
    a = [[q((i+1) if i==j else (1 if j==i+1 else 0), 8*n) for j in range(n)] for i in range(n)]
    A = Matrix(tuple(tuple(row) for row in a))
    # Construct SPD P independently; derive Q from the requested equation.
    p = [[q((i+2)*2) if i==j else q(1) for j in range(n)] for i in range(n)]
    P = Matrix(tuple(tuple(row) for row in p))
    product = (A.transpose()@P@A).rows
    Q = Matrix(tuple(tuple(p[i][j]-product[i][j] for j in range(n)) for i in range(n)))
    coefficient = [[(q(i==k and j==l)-a[k][i]*a[l][j]) for k in range(n) for l in range(n)] for i in range(n) for j in range(n)]
    result = b.calc('solve_linear','Vetorizar P-A^T P A=Q, preservando a ordem dos fatores.',matrix=coefficient,rhs=[v for row in Q.rows for v in row])
    solution = result['particular']
    solved = [[Fraction(solution[i*n+j]) for j in range(n)] for i in range(n)]
    if solved != p:
        raise ArithmeticError('Solução inversa de Lyapunov inconsistente')
    for i in range(n):
        for j in range(n):
            expression = str(solved[i][j])+'-('+ '+'.join(f'({a[k][i]})*({solved[k][l]})*({a[l][j]})' for k in range(n) for l in range(n))+f')-({Q.rows[i][j]})'
            b.zero(expression,f'Resíduo exato R[{i},{j}] após substituição na equação original.')
    for k in range(1,n+1):
        r = b.calc('matrix_properties',f'Menor principal de ordem {k}; critério de Sylvester.',matrix=[row[:k] for row in solved[:k]])
        if Fraction(r['determinant']) <= 0:
            raise ArithmeticError('P não definida positiva')
    dirty = [row.copy() for row in solved];dirty[0][0] += 1
    dirty_product = (A.transpose()@Matrix(tuple(tuple(row) for row in dirty))@A).rows
    witness = dirty[0][0]-dirty_product[0][0]-Q.rows[0][0]
    if witness == 0:
        raise ArithmeticError('Erro não observável')
    b.calc('evaluate','Rejeitar uma perturbação racional de P: resíduo R[0,0] não nulo.',source=str(witness),certificate={'kind':'counterexample','mutation':'matrix_entry_perturbation','residual':str(witness),'candidate':[[str(v) for v in row] for row in dirty],'accepted':False})
    return f'Resolva P-A^T P A=Q e certifique P positiva definida. A={[[str(v) for v in row] for row in a]}; Q={[[str(v) for v in row] for row in Q.rows]}.', {'P':[[str(v) for v in row] for row in solved],'all_residuals_zero':True}, 'Dados racionais; A triangular com |lambda|<1. Vetorização, substituição e Sylvester; sem hipótese de comutatividade.'


def _ito(b):
    a, s = b.rng.randint(2,6), b.rng.randint(1,4)
    mu, sigma = f'{a}*x-x**3', f'{s}*x**2'
    b.calc('advanced_math','Calcular o gerador de Itô para f=x².',action='stochastic.ito',parameters={'function':'x**2','drift':[mu],'diffusion':[[sigma]],'variables':['x']})
    derivative = b.calc('differentiate','Diferenciar a difusão multiplicativa.',source=sigma)
    ds = _expression_source(derivative['expression'])
    correct = f'({mu})-({sigma})*({ds})/2'
    wrong = f'({mu})+({sigma})*({ds})/2'
    b.equality(wrong,correct,'Testar a inversão de sinal na correção Itô–Stratonovich.',valid=False)
    b.equality(f'({correct})+({sigma})*({ds})/2',mu,'Reconstruir a deriva de Itô a partir da deriva de Stratonovich.')
    for stage in range(b.config.depth):
        power = 2+stage%30
        observable = f'{1+stage//30}*x**{power}+{stage}*x'
        b.calc('advanced_math',f'Gerador de Itô sobre o observável {observable}.',action='stochastic.ito',parameters={'function':observable,'drift':[mu],'diffusion':[[sigma]],'variables':['x']})
    return f'Converta dX=({mu})dt+({sigma})dW de Itô para Stratonovich e calcule o gerador em {b.config.depth} observáveis polinomiais. Trabalhe localmente, sem alegar existência global da SDE.', {'stratonovich_drift':correct}, 'Um Browniano padrão; coeficientes suaves localmente. b_S=mu-sigma sigma\'/2. Não inferir normalização de densidade ou não explosão.'


def _lorentz(b):
    dimension = min(15,b.config.difficulty+3)
    vector = [b.rng.randint(1,8) for _ in range(dimension)]
    terms = [-vector[0]**2]+[v*v for v in vector[1:]]
    total = 0
    for i, term in enumerate(terms):
        previous = total;total += term
        b.calc('evaluate',f'Contração parcial até coordenada {i}; sinal temporal negativo.',source=f'({previous})+({term})')
    euclidean = sum(v*v for v in vector)
    b.zero(f'({euclidean})-({total})-2*{vector[0]}**2','Conferir diferença entre assinatura euclidiana e lorentziana.')
    for i in range(b.config.depth):
        scale = i+2
        b.zero(f'({scale}**2)*({total})-('+ '+'.join(str((scale*v)**2*(-1 if j==0 else 1)) for j,v in enumerate(vector))+')',f'Conferir homogeneidade quadrática para fator {scale}.')
    return f'Contraia v={vector} com eta=diag(-1,+1,...,+1) em dimensão {dimension}. Detecte a troca indevida por métrica euclidiana.', {'lorentz_norm_squared':str(total),'euclidean_wrong_value':str(euclidean),'difference':str(2*vector[0]**2)}, 'Espaço vetorial plano com assinatura (-,+,...,+), c=1; não é cálculo de curvatura nem verificação de modelo físico.'


def _noncommuting(b):
    t = b.rng.randint(2,20)
    A,B = [[1,t],[0,1]], [[1,0],[t+1,1]]
    products = []
    for left,right,label in ((A,B,'AB'),(B,A,'BA')):
        matrix = []
        for i in range(2):
            row = []
            for j in range(2):
                r = b.calc('evaluate',f'Entrada ({i},{j}) de {label}; ordem preservada.',source='+'.join(f'{left[i][k]}*{right[k][j]}' for k in range(2)))
                row.append(r['value'])
            matrix.append(row)
        products.append(matrix)
    commutator = [[str(Fraction(products[0][i][j])-Fraction(products[1][i][j])) for j in range(2)] for i in range(2)]
    if not any(Fraction(v) for row in commutator for v in row):
        raise ArithmeticError('Comutador degenerado')
    b.calc('matrix_properties','Classificar o comutador obtido, sem substituir AB por BA.',matrix=commutator)
    return f'Calcule AB, BA e [A,B] para A={A}, B={B}; refute a comutatividade com uma entrada explícita.', {'AB':products[0],'BA':products[1],'commutator':commutator}, 'Matrizes racionais 2x2; multiplicação associativa, em geral não comutativa.'


def _domain(b):
    t = b.rng.randint(1,10)
    left = f'(x**2-{t*t})/(x-{t})'
    b.equality(left,f'x+{t}','Separar igualdade no domínio comum e equivalência de funções parciais.',valid=False)
    # Keep the same excluded point on both sides, making domains equivalent.
    b.equality(left,f'(x+{t})*(x-{t})/(x-{t})','Identidade válida com o denominador original preservado.')
    for k in range(1,b.config.depth+1):
        x = t+k
        b.zero(f'(({x}**2-{t*t})/({x}-{t}))-({x}+{t})',f'Substituição admissível x={x}; não substitui a análise do domínio.')
    return f'Analise a simplificação de ({left}) para x+{t}, preservando domínio e singularidade removível.', {'simplified':f'x+{t}','domain':f'x != {t}','extension_is_different_partial_function':True}, 'Funções parciais racionais reais; cancelamento não autoriza reinserir ponto excluído.'


BUILDERS = {'chain_rule':_polynomial,'lyapunov':_lyapunov,'ito_stratonovich':_ito,
            'lorentz_signature':_lorentz,'matrix_noncommutativity':_noncommuting,'rational_domain':_domain}


def _split(family):
    # Entire constructor families stay together, including fixed canonical tasks.
    bucket = int(fingerprint([VERSION,'split',family])[:8],16)%10
    return 'test' if bucket == 0 else 'validation' if bucket == 1 else 'train'


class SimulatedReasoningTrace:
    """Bounded deterministic generation, resumable by seed/family/index.

    depth means sequential derivatives or an explicitly labeled exercise suite;
    it never pads an answer with fabricated doubts or claims of model fidelity.
    """
    def __init__(self, config=None):
        self.config = config or GenerationConfig()

    def generate(self, family='lyapunov', index=0):
        if family not in FAMILIES:
            raise ValueError('Família desconhecida: '+str(family))
        _integer(index,0,100_000_000,'index')
        b = _Builder(self.config,family,index)
        if family in BUILDERS:
            prompt, answer, method = BUILDERS[family](b)
            title,area = SPECIAL[family]
        else:
            recipe = RECIPES[family];title,area = recipe.title,recipe.area
            tasks,answer,seen_requests = [],[],set()
            for attempt in range(self.config.depth*20):
                stage = len(tasks)
                if stage == self.config.depth:
                    break
                parameter = b.rng.randint(2,40)+attempt
                request = recipe.make(parameter,self.config.difficulty)
                identifier = fingerprint(request)
                if identifier in seen_requests:
                    continue
                seen_requests.add(identifier)
                tasks.append(request)
                answer.append(b.calc(request['operation'],f'Subproblema {stage+1}: {title}. '+recipe.method,**request['arguments']))
            prompt = f'Resolva a suíte de {len(tasks)} subproblemas de {title}. As instâncias são exercícios distintos do mesmo construtor, não etapas de uma única prova. Requisições: '+canonical_json(tasks)
            method = recipe.method
        record = {'schema_version':1,'generator_version':VERSION,'synthetic':True,
                  'private_model_reasoning':False,'formal_proof':False,'family':family,
                  'title':title,'area':area,'config':self.config.data(),'index':index,
                  'prompt':prompt,'method':method,'steps':b.steps,'answer':answer,
                  'split':_split(family),'difficulty':'uncalibrated','notice':NOTICE,
                  'arithmetic':'numerical_not_enclosed' if family in NUMERICAL_FAMILIES else 'exact_or_symbolic_bounded',
                  'verification_independent':False}
        record['task_id'] = fingerprint([family,prompt])
        record['id'] = fingerprint(record)
        b.session.close()
        return record

    def stream(self, count=100, families=None, start_index=0):
        _integer(count,1,100_000_000,'count')
        _integer(start_index,0,100_000_000-count,'start_index')
        families = tuple(families or FAMILIES)
        if not families or len(set(families)) != len(families) or any(f not in FAMILIES for f in families):
            raise ValueError('Famílias válidas e distintas requeridas')
        for i in range(start_index,start_index+count):
            yield self.generate(families[i%len(families)],i)


def verify_record(record):
    """Regenerate the full task, errors, certificates and answer; never trust flags."""
    try:
        config = GenerationConfig(**record['config'])
        return SimulatedReasoningTrace(config).generate(record['family'],record['index']) == record
    except (ValueError,TypeError,KeyError,ArithmeticError,RuntimeError,ImportError,RecursionError):
        return False


def coverage_report(families):
    from ..ops.advanced_math import ACTIONS
    coverage = {}
    selected = set(families)
    for operation in sorted(AREAS):
        coverage[operation] = {'area':AREAS[operation], 'status':'recipe_available' if operation in RECIPES else 'no_recipe',
                               'sampled':operation in selected}
    actions = {name:{'status':'recipe_available' if name in RECIPES else 'no_recipe','sampled':name in selected} for name in sorted(ACTIONS)}
    return {'catalog_operations':coverage,'advanced_actions':actions,'special_families':list(SPECIAL),
            'available_families':list(FAMILIES),'sampled_families':sorted(selected),
            'scope':'Inventário das operações registradas, não de todas as funções Python. no_recipe não significa indisponibilidade matemática.'}


def _sft(record):
    return {'id':record['id'],'task_id':record['task_id'],'family':record['family'],'split':record['split'],
            'messages':[{'role':'user','content':record['prompt']},
                        {'role':'assistant','content':TextualReasoningFormatter.solution(record)}]}


def _preferences(record):
    for step in record['steps']:
        if 'error' not in step:
            continue
        yield {'record_id':record['id'],'family':record['family'],'split':record['split'],
               'prompt':step['description']+'\n'+canonical_json(step['receipt']['request']),
               'chosen':canonical_json(step['receipt']['result']),
               'rejected':canonical_json(step['error']['candidate']),
               'verification':step['error']['detection'],
               'scope':'Preferência computacional sintética local; não preferência humana nem prova independente.'}


def _digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def _runtime():
    dependencies = {}
    for package in ('sympy','numpy','scipy','mpmath'):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = None
    sources = {name:_digest(Path(__file__).with_name(name)) for name in
               ('synthetic_cot_unroller.py','synthetic_recipes.py','synthetic_certificates.py')}
    return {'python':platform.python_version(),'dependencies':dependencies,'generator_sources_sha256':sources}


def export_dataset(destination, *, count=100, config=None, families=None, start_index=0):
    """Streaming, deduplicated, atomic export into a new directory; no overwrite."""
    config = config or GenerationConfig()
    generator = SimulatedReasoningTrace(config)
    families = tuple(families or FAMILIES)
    # Validate before creating output; stream validation otherwise runs lazily.
    _integer(count,1,100_000_000,'count')
    _integer(start_index,0,100_000_000-count,'start_index')
    if not families or len(set(families)) != len(families) or any(f not in FAMILIES for f in families):
        raise ValueError('Famílias válidas e distintas requeridas')
    destination = Path(destination).absolute()
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.nabla-trajectories-',dir=destination.parent))
    names = ('dataset.jsonl','sft.jsonl','dpo.jsonl','amostras.txt','amostras.md','train.jsonl','validation.jsonl','test.jsonl')
    streams = {}
    try:
        for name in names:
            streams[name] = (stage/name).open('w',encoding='utf-8',newline='\n')
        for name in ('amostras.txt','amostras.md'):
            streams[name].write('NABLA — SOLUÇÕES PROCEDURAIS E CORREÇÕES AUDITÁVEIS\n'+NOTICE+'\n\n')
        counts,areas,splits = Counter(),Counter(),Counter()
        seen,errors,total_steps = set(),0,0
        # SQLite keeps exact deduplication bounded in RAM for large exports.
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(stage/'.dedup.sqlite')) as db:
            db.execute('CREATE TABLE seen (id TEXT PRIMARY KEY)')
            attempt,accepted = start_index,0
            while accepted < count:
                if attempt-start_index >= count*20+len(families):
                    raise ValueError('Espaço de receitas esgotado: reduza count ou amplie famílias')
                family = families[attempt%len(families)]
                record = generator.generate(family,attempt);attempt += 1
                try:
                    db.execute('INSERT INTO seen VALUES (?)',(record['task_id'],))
                except sqlite3.IntegrityError:
                    continue
                accepted += 1;seen.add(family)
                counts[family] += 1;areas[record['area']] += 1;splits[record['split']] += 1
                total_steps += len(record['steps'])
                raw = canonical_json(record)+'\n'
                streams['dataset.jsonl'].write(raw);streams[record['split']+'.jsonl'].write(raw)
                streams['sft.jsonl'].write(canonical_json(_sft(record))+'\n')
                for pair in _preferences(record):
                    errors += 1;streams['dpo.jsonl'].write(canonical_json(pair)+'\n')
                sample = TextualReasoningFormatter.sample(record,accepted)
                streams['amostras.txt'].write(sample);streams['amostras.md'].write(sample)
        (stage/'.dedup.sqlite').unlink()
        for stream in streams.values():
            stream.close()
        coverage = coverage_report(seen)
        (stage/'coverage.json').write_text(canonical_json(coverage)+'\n',encoding='utf-8')
        card = {'schema_version':1,'generator_version':VERSION,'config':config.data(),'count':count,
                'families_requested':list(families),'start_index':start_index,'next_index':attempt,
                'families':dict(counts),'areas':dict(areas),'splits':dict(splits),
                'steps':total_steps,'rejected_candidates':errors,'neural_inference':False,
                'verification':'Replayable catalog calculations; explicit certificates where available; no independent oracle for generic recipes.',
                'split_policy':'constructor_family_hash_v1','deduplication':'exact task_id; no claim of semantic novelty',
                'license_id':'MIT','provenance':'Procedural Nabla recipes, no external model outputs.',
                'notice':NOTICE,'formal_proofs':0,'difficulty':'uncalibrated',
                'training_utility_evaluated':False,'full_mathematical_coverage':False,
                'runtime':_runtime()}
        (stage/'card.json').write_text(canonical_json(card)+'\n',encoding='utf-8')
        manifest = {'schema_version':1,'files':{p.name:_digest(p) for p in sorted(stage.iterdir()) if p.is_file()}}
        (stage/'manifest.json').write_text(canonical_json(manifest)+'\n',encoding='utf-8')
        if destination.exists():
            raise FileExistsError(destination)
        stage.rename(destination)
        return card
    finally:
        for stream in streams.values():
            stream.close()
        if stage.exists():
            shutil.rmtree(stage)


def verify_dataset(directory):
    """Check file integrity, reconstruct every record, and check all projections.

    Dependencies and machine floating-point behavior must match for replay.
    """
    root = Path(directory)
    try:
        manifest_path = root/'manifest.json'
        if manifest_path.is_symlink() or manifest_path.stat().st_size > 1_000_000:
            return False
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        expected_names = {'dataset.jsonl','sft.jsonl','dpo.jsonl','amostras.txt','amostras.md','train.jsonl','validation.jsonl','test.jsonl','coverage.json','card.json'}
        if manifest['schema_version'] != 1 or set(manifest['files']) != expected_names or {p.name for p in root.iterdir()} != expected_names|{'manifest.json'}:
            return False
        for name,digest in manifest['files'].items():
            path = root/name
            if path.is_symlink() or not path.is_file() or _digest(path) != digest:
                return False
        card = json.loads((root/'card.json').read_text(encoding='utf-8'))
        # Regeneration also validates deduplication, splits, every export and card.
        with tempfile.TemporaryDirectory(prefix='nabla-verify-') as temporary:
            target = Path(temporary)/'regenerated'
            export_dataset(target,count=card['count'],config=GenerationConfig(**card['config']),
                           families=card['families_requested'],start_index=card['start_index'])
            return (target/'manifest.json').read_bytes() == manifest_path.read_bytes()
    except (OSError,ValueError,KeyError,TypeError,ArithmeticError,RuntimeError,ImportError,RecursionError):
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--count',type=int,default=100)
    parser.add_argument('--seed',type=int,default=20261017)
    parser.add_argument('--difficulty',type=int,default=4)
    parser.add_argument('--depth',type=int,default=8,help='Derivadas sucessivas ou tamanho da suíte de subproblemas, 1..256')
    parser.add_argument('--error-rate',type=float,default=.35)
    parser.add_argument('--families',nargs='+',choices=FAMILIES)
    parser.add_argument('--start-index',type=int,default=0)
    parser.add_argument('--output',type=Path,default=Path('nabla_synthetic_dataset'))
    parser.add_argument('--list-families',action='store_true')
    parser.add_argument('--verify',type=Path)
    args = parser.parse_args(argv)
    try:
        if args.list_families:
            print('\n'.join(FAMILIES));return 0
        if args.verify:
            valid = verify_dataset(args.verify)
            print('Verificação: '+('APROVADA (escopo computacional)' if valid else 'REPROVADA'))
            return 0 if valid else 1
        config = GenerationConfig(args.seed,args.difficulty,args.depth,args.error_rate)
        card = export_dataset(args.output,count=args.count,config=config,families=args.families,start_index=args.start_index)
        print(canonical_json({'output':str(args.output),'count':card['count'],'families':len(card['families']),'steps':card['steps'],'rejected_candidates':card['rejected_candidates']}))
        return 0
    except (ValueError,ArithmeticError,FileExistsError,ImportError,RuntimeError) as exc:
        parser.exit(2,str(exc)+'\n')


if __name__ == '__main__':
    raise SystemExit(main())
