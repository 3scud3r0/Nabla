"""Exact bounded rational functions; normalization retains original domain guards."""
from dataclasses import dataclass
from ..polynomials.univariate import Polynomial,polynomial_gcd
from ...core.semantic_ir import SemanticExpression,PolynomialSpec,fingerprint
from ...core.obligations import domain_obligations
from ...expression import Number,Symbol,parse_expr,render


def _bounded(poly):
    if poly.degree>64 or any(max(v.numerator.bit_length(),v.denominator.bit_length())>4096 for v in poly.coefficients):
        raise ValueError('Forma racional excede grau/custo de coeficientes')
    return poly


@dataclass(frozen=True)
class RationalFunction:
    numerator: Polynomial
    denominator: Polynomial

    def __post_init__(self):
        n,d=_bounded(self.numerator),_bounded(self.denominator)
        if d.is_zero:raise ValueError('Denominador identicamente nulo')
        common=polynomial_gcd(n,d);n=n.divmod(common)[0];d=d.divmod(common)[0]
        scale=d.leading
        object.__setattr__(self,'numerator',Polynomial(tuple(v/scale for v in n.coefficients)))
        object.__setattr__(self,'denominator',Polynomial(tuple(v/scale for v in d.coefficients)))

    def derivative(self):
        n,d=self.numerator,self.denominator
        return RationalFunction(_bounded(n.derivative()*d-n*d.derivative()),_bounded(d*d))

    def to_data(self):
        return {'numerator':[str(v) for v in self.numerator.coefficients],'denominator':[str(v) for v in self.denominator.coefficients]}

    def expression(self):
        from ...expression import Binary
        return Binary('/',PolynomialSpec(self.numerator.coefficients).to_expr(),PolynomialSpec(self.denominator.coefficients).to_expr())


def rational_form(source):
    semantic=SemanticExpression.parse(source)
    if set(n for n,_ in semantic.variable_types)-{'x'}:raise ValueError('Forma racional aceita apenas x')
    one=Polynomial((1,))
    def combine(n,d):return RationalFunction(_bounded(n),_bounded(d))
    def visit(expr):
        if isinstance(expr,Number):return RationalFunction(Polynomial((expr.value,)),one)
        if isinstance(expr,Symbol):return RationalFunction(Polynomial((0,1)),one)
        if expr.op=='**':
            if not isinstance(expr.right,Number) or expr.right.value.denominator!=1:raise ValueError('Potência inteira obrigatória')
            power=int(expr.right.value)
            if abs(power)>16:raise ValueError('Potência fora do limite')
            base=visit(expr.left);n,d=one,one
            for _ in range(abs(power)):
                n=_bounded(n*(base.numerator if power>=0 else base.denominator))
                d=_bounded(d*(base.denominator if power>=0 else base.numerator))
            return combine(n,d)
        a,b=visit(expr.left),visit(expr.right)
        if expr.op=='+':return combine(a.numerator*b.denominator+b.numerator*a.denominator,a.denominator*b.denominator)
        if expr.op=='-':return combine(a.numerator*b.denominator-b.numerator*a.denominator,a.denominator*b.denominator)
        if expr.op=='*':return combine(a.numerator*b.numerator,a.denominator*b.denominator)
        if expr.op=='/':return combine(a.numerator*b.denominator,a.denominator*b.numerator)
        raise ValueError('Operador fora do fragmento racional')
    return visit(semantic.expression)


def compare_rational(left,right):
    a,b=rational_form(left),rational_form(right)
    # Conservative domain comparison; no blanket extension through canceled poles.
    def guards(source):
        rows=[]
        for obligation in domain_obligations(parse_expr(source)):
            polynomial=rational_form(render(obligation.expression)).numerator
            if polynomial.is_zero:raise ValueError('Domínio vazio')
            if polynomial.degree<=0:continue
            polynomial=polynomial.monic()
            squarefree=polynomial.divmod(polynomial_gcd(polynomial,polynomial.derivative()))[0].monic()
            rows.append(tuple(str(v) for v in squarefree.coefficients))
        return sorted(set(rows))
    equal=a.to_data()==b.to_data();left_guards,right_guards=guards(left),guards(right)
    payload={'left':left,'right':right,'equal_on_common_domain':equal,'domain_equivalence_established':left_guards==right_guards,
             'left_domain_guards':left_guards,'right_domain_guards':right_guards,'normal_left':a.to_data(),'normal_right':b.to_data(),
             'formal_proof':False,'scope':'univariate rational functions; conservative guard matching, not unrestricted domain decision'}
    return {**payload,'comparison_id':fingerprint(payload)}
