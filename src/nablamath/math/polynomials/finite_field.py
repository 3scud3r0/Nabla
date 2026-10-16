"""Deterministic Berlekamp factorization over small prime fields.

The producer uses the Frobenius fixed subspace; the independent verifier uses
Rabin's irreducibility criterion and exact product reconstruction. The contract
is primes <=257, degree<=16, explicit split-work budget. Extension fields and
unbounded cryptographic-size prime factorization are outside this module.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isqrt

from ...core.semantic_contracts import canonical_payload
from ...core.semantic_ir import fingerprint


def _prime(value):
    if type(value) is not int or not 2<=value<=257 or any(value%d==0 for d in range(2,isqrt(value)+1)):
        raise ValueError('Prime field modulus must be a prime in [2,257]')
    return value


@dataclass(frozen=True)
class FpPolynomial:
    prime: int
    coefficients: tuple[int,...]

    def __post_init__(self):
        _prime(self.prime)
        if not isinstance(self.coefficients,(tuple,list)) or not 1<=len(self.coefficients)<=65:
            raise ValueError('Finite-field polynomial requires 1..65 coefficients')
        if any(type(v) is not int or abs(v).bit_length()>4096 for v in self.coefficients):
            raise ValueError('Finite-field coefficients must be bounded integers')
        values=[v%self.prime for v in self.coefficients]
        while len(values)>1 and values[-1]==0:
            values.pop()
        object.__setattr__(self,'coefficients',tuple(values))

    @property
    def degree(self):return -1 if self.is_zero else len(self.coefficients)-1

    @property
    def leading(self):return self.coefficients[-1]

    @property
    def is_zero(self):return self.coefficients==(0,)

    def _coerce(self,other):
        if isinstance(other,FpPolynomial):
            if other.prime!=self.prime:
                raise ValueError('Polynomial fields differ')
            return other
        if type(other) is not int:
            raise ValueError('Finite-field polynomial or integer required')
        return FpPolynomial(self.prime,(other,))

    def __add__(self,other):
        other=self._coerce(other)
        n=max(len(self.coefficients),len(other.coefficients))
        return FpPolynomial(self.prime,tuple((self.coefficients[i] if i<len(self.coefficients) else 0)
                            +(other.coefficients[i] if i<len(other.coefficients) else 0) for i in range(n)))

    __radd__=__add__

    def __neg__(self):return FpPolynomial(self.prime,tuple(-v for v in self.coefficients))

    def __sub__(self,other):return self+-self._coerce(other)

    def __rsub__(self,other):return self._coerce(other)-self

    def __mul__(self,other):
        other=self._coerce(other)
        n=len(self.coefficients)+len(other.coefficients)-1
        if n>65:
            raise ValueError('Finite-field multiplication degree budget exceeded')
        values=[0]*n
        for i,left in enumerate(self.coefficients):
            for j,right in enumerate(other.coefficients):
                values[i+j]=(values[i+j]+left*right)%self.prime
        return FpPolynomial(self.prime,tuple(values))

    __rmul__=__mul__

    def monic(self):
        return self if self.is_zero else self*pow(self.leading,-1,self.prime)

    def derivative(self):
        return FpPolynomial(self.prime,tuple(i*v for i,v in enumerate(self.coefficients))[1:] or (0,))

    def __call__(self,value):
        if type(value) is not int:
            raise ValueError('Finite-field evaluation point must be integer')
        result=0
        for coefficient in reversed(self.coefficients):
            result=(result*value+coefficient)%self.prime
        return result

    def divmod(self,other):
        other=self._coerce(other)
        if other.is_zero:
            raise ZeroDivisionError('Division by zero finite-field polynomial')
        remainder=list(self.coefficients)
        quotient=[0]*max(1,self.degree-other.degree+1)
        while len(remainder)-1>=other.degree and any(remainder):
            shift=len(remainder)-1-other.degree
            factor=remainder[-1]*pow(other.leading,-1,self.prime)%self.prime
            quotient[shift]=factor
            for j,value in enumerate(other.coefficients):
                remainder[shift+j]=(remainder[shift+j]-factor*value)%self.prime
            while len(remainder)>1 and remainder[-1]==0:
                remainder.pop()
        return FpPolynomial(self.prime,tuple(quotient)),FpPolynomial(self.prime,tuple(remainder))

    def __mod__(self,modulus):return self.divmod(modulus)[1]

    def __pow__(self,exponent):
        if type(exponent) is not int or not 0<=exponent<=64:
            raise ValueError('Finite-field polynomial exponent must be in [0,64]')
        if self.degree*exponent>64:
            raise ValueError('Finite-field polynomial power degree budget exceeded')
        result=FpPolynomial(self.prime,(1,))
        base=self
        while exponent:
            if exponent&1:result=result*base
            exponent >>= 1
            if exponent:base=base*base
        return result

    def powmod(self,exponent,modulus):
        if type(exponent) is not int or exponent<0 or exponent.bit_length()>256:
            raise ValueError('Finite-field modular exponent budget exceeded')
        modulus=self._coerce(modulus)
        if modulus.degree<1 or modulus.degree>32:
            raise ValueError('Finite-field modular polynomial degree must be in [1,32]')
        result=FpPolynomial(self.prime,(1,))
        base=self%modulus
        while exponent:
            if exponent&1:result=(result*base)%modulus
            exponent >>= 1
            if exponent:base=(base*base)%modulus
        return result%modulus

    def to_data(self):return {'prime':self.prime,'coefficients':list(self.coefficients)}

    @classmethod
    def from_data(cls,data):
        if type(data) is not dict or set(data)!={'prime','coefficients'} or not isinstance(data['coefficients'],list):
            raise ValueError('Invalid finite-field polynomial manifest')
        result=cls(data['prime'],tuple(data['coefficients']))
        if result.to_data()!=data:
            raise ValueError('Finite-field polynomial must use canonical residue coefficients')
        return result


def fp_gcd(left,right):
    right=left._coerce(right)
    while not right.is_zero:
        left,right=right,left%right
    return left.monic()


def _exact_divide(left,right):
    quotient,remainder=left.divmod(right)
    if not remainder.is_zero:
        raise ArithmeticError('Expected exact finite-field division')
    return quotient


def _check_input(polynomial):
    if not isinstance(polynomial,FpPolynomial) or polynomial.is_zero or polynomial.degree>16:
        raise ValueError('Finite-field factorization requires nonzero polynomial degree<=16')


def is_irreducible(polynomial):
    """Rabin criterion: Frobenius congruence plus gcd checks for degree divisors."""
    _check_input(polynomial)
    if polynomial.degree==0:return False
    if polynomial.degree==1:return True
    f=polynomial.monic()
    n=f.degree
    prime_divisors=[]
    remaining=n
    divisor=2
    while divisor*divisor<=remaining:
        if remaining%divisor==0:
            prime_divisors.append(divisor)
            while remaining%divisor==0:remaining//=divisor
        divisor+=1
    if remaining>1:prime_divisors.append(remaining)
    x=FpPolynomial(f.prime,(0,1))
    powers=[x%f]
    for _ in range(n):powers.append(powers[-1].powmod(f.prime,f))
    if powers[n]!=x%f:return False
    return all(fp_gcd(f,powers[n//q]-x).degree==0 for q in prime_divisors)


def _nullspace_mod_prime(rows,prime):
    data=[[v%prime for v in row] for row in rows]
    pivots=[]
    current=0
    for column in range(len(data[0])):
        candidate=next((r for r in range(current,len(data)) if data[r][column]),None)
        if candidate is None:continue
        data[current],data[candidate]=data[candidate],data[current]
        inverse=pow(data[current][column],-1,prime)
        data[current]=[v*inverse%prime for v in data[current]]
        for row in range(len(data)):
            if row!=current and data[row][column]:
                scale=data[row][column]
                data[row]=[(v-scale*w)%prime for v,w in zip(data[row],data[current])]
        pivots.append(column)
        current+=1
        if current==len(data):break
    basis=[]
    for free in range(len(data[0])):
        if free in pivots:continue
        vector=[0]*len(data[0])
        vector[free]=1
        for row,pivot in enumerate(pivots):vector[pivot]=-data[row][free]%prime
        basis.append(tuple(vector))
    return tuple(basis)


def berlekamp_basis(polynomial):
    """Basis of ker(Frobenius-I), dimension equals number of square-free factors."""
    _check_input(polynomial)
    if polynomial.degree<1:
        raise ValueError('Berlekamp requires positive degree')
    f=polynomial.monic()
    if fp_gcd(f,f.derivative()).degree>0:
        raise ValueError('Berlekamp basis requires square-free input')
    n=f.degree
    x=FpPolynomial(f.prime,(0,1))
    columns=[]
    for index in range(n):
        power=x.powmod(f.prime*index,f)
        columns.append(power.coefficients+(0,)*(n-len(power.coefficients)))
    rows=tuple(tuple((columns[j][i]-int(i==j))%f.prime for j in range(n)) for i in range(n))
    return tuple(FpPolynomial(f.prime,vector) for vector in _nullspace_mod_prime(rows,f.prime))


class _Work:
    def __init__(self,maximum):
        if type(maximum) is not int or not 1<=maximum<=1000000:
            raise ValueError('Factorization work budget must be in [1,1000000]')
        self.maximum=maximum
        self.used=0

    def step(self):
        self.used+=1
        if self.used>self.maximum:
            raise ValueError('Finite-field factorization work budget exhausted')


def _factor_square_free(polynomial,work):
    basis=berlekamp_basis(polynomial)
    factors=[polynomial]
    for element in basis:
        if len(factors)==len(basis):break
        if element.degree<=0:continue
        for constant in range(polynomial.prime):
            next_factors=[]
            for factor in factors:
                if factor.degree<=1:
                    next_factors.append(factor)
                    continue
                work.step()
                divisor=fp_gcd(factor,element-constant)
                if 0<divisor.degree<factor.degree:
                    next_factors.extend((divisor,_exact_divide(factor,divisor)))
                else:next_factors.append(factor)
            factors=next_factors
            if len(factors)==len(basis):break
    if len(factors)!=len(basis):
        raise ArithmeticError('Berlekamp basis failed to split expected factors')
    return factors


def _factor_monic(polynomial,work):
    if polynomial.degree<=0:return []
    work.step()
    derivative=polynomial.derivative()
    if derivative.is_zero:
        prime=polynomial.prime
        # In F_p the p-th root is coefficient extraction at multiples of p.
        root=FpPolynomial(prime,tuple(polynomial.coefficients[i] for i in range(0,len(polynomial.coefficients),prime)))
        return [(factor,multiplicity*prime) for factor,multiplicity in _factor_monic(root,work)]
    repeated=fp_gcd(polynomial,derivative)
    square_free=_exact_divide(polynomial,repeated)
    output=[]
    multiplicity=1
    while square_free.degree>0:
        work.step()
        common=fp_gcd(square_free,repeated)
        part=_exact_divide(square_free,common)
        if part.degree>0:
            output.extend((factor,multiplicity) for factor in _factor_square_free(part,work))
        square_free=common
        repeated=_exact_divide(repeated,common)
        multiplicity+=1
    if repeated.degree>0:
        prime=polynomial.prime
        root=FpPolynomial(prime,tuple(repeated.coefficients[i] for i in range(0,len(repeated.coefficients),prime)))
        output.extend((factor,multiplicity*prime) for factor,multiplicity in _factor_monic(root,work))
    return output


@dataclass(frozen=True)
class FiniteFieldFactorization:
    polynomial: FpPolynomial
    leading: int
    factors: tuple[tuple[FpPolynomial,int],...]
    work_units: int

    def to_data(self):
        payload={'schema_version':1,'polynomial':self.polynomial.to_data(),'leading':self.leading,
                 'factors':[{'polynomial':factor.to_data(),'multiplicity':multiplicity} for factor,multiplicity in self.factors],
                 'work_units':self.work_units,'formal_proof':False,
                 'scope':'Exact small-prime finite-field factorization; Rabin irreducibility and product replay'}
        return {**payload,'certificate_id':fingerprint(payload)}


def factor_finite_field(polynomial,*,max_work=100000):
    _check_input(polynomial)
    work=_Work(max_work)
    factors=_factor_monic(polynomial.monic(),work)
    merged={}
    for factor,multiplicity in factors:
        merged[factor]=merged.get(factor,0)+multiplicity
    ordered=tuple(sorted(merged.items(),key=lambda pair:(pair[0].degree,pair[0].coefficients)))
    result=FiniteFieldFactorization(polynomial,polynomial.leading,ordered,work.used)
    if not verify_finite_field_factorization(result.to_data()):
        raise ArithmeticError('Finite-field factorization failed independent replay')
    return result


def verify_finite_field_factorization(data):
    try:
        canonical_payload(data)
        if type(data) is not dict or set(data)!={'schema_version','polynomial','leading','factors','work_units','formal_proof','scope','certificate_id'}:
            return False
        if type(data['schema_version']) is not int or data['schema_version']!=1 or data['formal_proof'] is not False:
            return False
        if data['scope']!='Exact small-prime finite-field factorization; Rabin irreducibility and product replay':
            return False
        if data['certificate_id']!=fingerprint({k:v for k,v in data.items() if k!='certificate_id'}):
            return False
        polynomial=FpPolynomial.from_data(data['polynomial'])
        _check_input(polynomial)
        if type(data['leading']) is not int or data['leading']!=polynomial.leading:
            return False
        if type(data['work_units']) is not int or not 0<=data['work_units']<=1000000:
            return False
        if not isinstance(data['factors'],list) or len(data['factors'])>16:
            return False
        product=FpPolynomial(polynomial.prime,(data['leading'],))
        factors=[]
        total_degree=0
        for row in data['factors']:
            if type(row) is not dict or set(row)!={'polynomial','multiplicity'}:
                return False
            factor=FpPolynomial.from_data(row['polynomial'])
            multiplicity=row['multiplicity']
            if factor.prime!=polynomial.prime or factor.leading!=1 or factor.degree<1:
                return False
            if type(multiplicity) is not int or not 1<=multiplicity<=16:
                return False
            total_degree+=factor.degree*multiplicity
            if total_degree>16 or not is_irreducible(factor):
                return False
            factors.append(factor)
            product=product*(factor**multiplicity)
        if len(set(factors))!=len(factors) or factors!=sorted(factors,key=lambda factor:(factor.degree,factor.coefficients)):
            return False
        return product==polynomial
    except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError,RecursionError):
        return False


__all__=['FpPolynomial','fp_gcd','is_irreducible','berlekamp_basis',
         'FiniteFieldFactorization','factor_finite_field','verify_finite_field_factorization']
