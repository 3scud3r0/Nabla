"""Bounded univariate hypotheses and exact observations with declared SI dimensions."""
from dataclasses import dataclass, asdict
from fractions import Fraction
from ..core.semantic_ir import canonical_json, fingerprint, rational, SemanticExpression
from ..core.units import ONE, Unit, infer_unit
from ..expression import parse_expr, render, evaluate


@dataclass(frozen=True)
class Hypothesis:
    expression: str
    scope: str
    input_unit: Unit = ONE
    output_unit: Unit = ONE
    lower: Fraction = Fraction(-100)
    upper: Fraction = Fraction(100)

    def __post_init__(self):
        if not self.scope.strip() or len(self.expression)>512:
            raise ValueError('Escopo e expressão limitada obrigatórios')
        expression = parse_expr(self.expression)
        unit = infer_unit(expression, {'x':self.input_unit})
        if unit.dimensions != self.output_unit.dimensions or unit.scale != self.output_unit.scale:
            raise ValueError('Dimensões da hipótese incompatíveis')
        SemanticExpression(expression)
        low, high = rational(self.lower), rational(self.upper)
        if low >= high or max(abs(low),abs(high))>1000000:
            raise ValueError('Domínio limitado obrigatório')
        object.__setattr__(self,'lower',low); object.__setattr__(self,'upper',high)
        object.__setattr__(self,'expression',render(expression))

    def predict(self, x):
        x = rational(x)
        if not self.lower <= x <= self.upper:
            raise ValueError('Entrada fora do domínio declarado')
        return evaluate(parse_expr(self.expression), {'x':x})

    def to_data(self):
        return {'expression':self.expression,'scope':self.scope,'input_unit':self.input_unit.to_data(),
                'output_unit':self.output_unit.to_data(),'lower':str(self.lower),'upper':str(self.upper)}

    @property
    def hypothesis_id(self):
        return fingerprint(self.to_data())


@dataclass(frozen=True)
class Observation:
    x: Fraction
    y: Fraction
    uncertainty: Fraction = Fraction(0)

    def __post_init__(self):
        for name in ('x','y','uncertainty'):
            object.__setattr__(self,name,rational(getattr(self,name)))
        if self.uncertainty<0 or max(abs(self.x),abs(self.y),self.uncertainty)>1000000:
            raise ValueError('Observação fora dos limites')

    def to_data(self):
        return {name:str(getattr(self,name)) for name in ('x','y','uncertainty')}


@dataclass(frozen=True)
class ObservationSet:
    observations: tuple[Observation,...]
    provenance: str
    role: str
    input_unit: Unit = ONE
    output_unit: Unit = ONE
    synthetic: bool = True

    def __post_init__(self):
        object.__setattr__(self,'observations',tuple(self.observations))
        if not 1<=len(self.observations)<=128 or not self.provenance.strip() or self.role not in {'calibration','holdout'}:
            raise ValueError('Dados, procedência e papel válidos obrigatórios')
        if type(self.synthetic) is not bool or len({o.x for o in self.observations})!=len(self.observations):
            raise ValueError('Origem inválida ou entradas repetidas')

    def to_data(self):
        return {'observations':[o.to_data() for o in self.observations],'provenance':self.provenance,
                'role':self.role,'input_unit':self.input_unit.to_data(),'output_unit':self.output_unit.to_data(),
                'synthetic':self.synthetic}

    @property
    def dataset_id(self):
        return fingerprint(self.to_data())


def assess(hypothesis, observations):
    if (hypothesis.input_unit.to_data()!=observations.input_unit.to_data()
            or hypothesis.output_unit.to_data()!=observations.output_unit.to_data()):
        raise ValueError('Unidades incompatíveis com observações')
    rows=[]
    for row in observations.observations:
        try:
            predicted=hypothesis.predict(row.x)
            residual=abs(predicted-row.y)
            rows.append({'x':str(row.x),'predicted':str(predicted),'observed':str(row.y),
                         'absolute_residual':str(residual),'within_uncertainty':residual<=row.uncertainty})
        except (ValueError,ArithmeticError):
            rows.append({'x':str(row.x),'predicted':None,'observed':str(row.y),
                         'absolute_residual':None,'within_uncertainty':False})
    return {'hypothesis_id':hypothesis.hypothesis_id,'dataset_id':observations.dataset_id,'role':observations.role,
            'matches_all':all(r['within_uncertainty'] for r in rows),'rows':rows,'formal_proof':False,
            'scope':'agreement on supplied observations, not universal truth or experimental authentication'}
