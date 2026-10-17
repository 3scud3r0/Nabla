"""Exact finite extension fields, elliptic curves and reduced Tate pairings.

Reference/research algebra only: Python arithmetic is not constant-time, no key
management is supplied, and these routines are not a production cryptosystem.
Pairing inputs must avoid Miller divisors; an exceptional evaluation is rejected
rather than silently returning zero. Heavy polynomial algorithms use SymPy.
"""
from dataclasses import dataclass

from ..math._structured import sympy, expression, names
from .lie_groups import matrix_group


@dataclass(frozen=True)
class GaloisField:
    """GF(p)[x]/(monic irreducible modulus), coefficients in ascending order."""
    p: int
    modulus: tuple

    def __post_init__(self):
        sp = sympy()
        if type(self.p) is not int or not 2 <= self.p < 2**31 or not sp.isprime(self.p):
            raise ValueError('Prime characteristic below 2^31 required')
        if not isinstance(self.modulus, (list, tuple)) or not 2 <= len(self.modulus) <= 17:
            raise ValueError('Extension degree must be 1–16')
        if any(type(v) is not int for v in self.modulus):
            raise ValueError('Integer polynomial coefficients required')
        modulus = tuple(v % self.p for v in self.modulus)
        if modulus[-1] != 1:
            raise ValueError('A monic modulus is required')
        x = sp.Symbol('x')
        if not sp.Poly(sum(v*x**i for i,v in enumerate(modulus)), x,
                       modulus=self.p).is_irreducible:
            raise ValueError('Reducible modulus does not define a field')
        object.__setattr__(self, 'modulus', modulus)

    @property
    def degree(self):
        return len(self.modulus)-1

    @property
    def order(self):
        return self.p**self.degree

    def element(self, value=0):
        if isinstance(value, FieldElement):
            if value.field != self:
                raise ValueError('Cannot mix different fields')
            return value
        if type(value) is int:
            value = [value]
        if not isinstance(value, (list, tuple)) or len(value) > 64 or any(type(v) is not int for v in value):
            raise ValueError('Bounded integer coefficient vector required')
        coefficients = [v % self.p for v in value] or [0]
        while len(coefficients) > self.degree:
            high = coefficients.pop()
            offset = len(coefficients)-self.degree
            for i in range(self.degree):
                coefficients[offset+i] = (coefficients[offset+i]-high*self.modulus[i]) % self.p
        coefficients += [0]*(self.degree-len(coefficients))
        return FieldElement(self, tuple(coefficients))


@dataclass(frozen=True)
class FieldElement:
    field: GaloisField
    coefficients: tuple

    def __post_init__(self):
        if (not isinstance(self.coefficients, tuple) or len(self.coefficients) != self.field.degree or
                any(type(v) is not int or not 0 <= v < self.field.p for v in self.coefficients)):
            raise ValueError('Noncanonical field element')

    def __bool__(self):
        return any(self.coefficients)

    def __add__(self, other):
        other = self.field.element(other)
        return self.field.element([a+b for a,b in zip(self.coefficients, other.coefficients)])

    __radd__ = __add__

    def __neg__(self):
        return self.field.element([-v for v in self.coefficients])

    def __sub__(self, other):
        return self + -self.field.element(other)

    def __rsub__(self, other):
        return self.field.element(other) + -self

    def __mul__(self, other):
        other = self.field.element(other)
        result = [0]*(2*self.field.degree-1)
        for i,a in enumerate(self.coefficients):
            for j,b in enumerate(other.coefficients):
                result[i+j] += a*b
        return self.field.element(result)

    __rmul__ = __mul__

    def __pow__(self, exponent):
        if type(exponent) is not int or abs(exponent).bit_length() > 4096:
            raise ValueError('Bounded integer exponent required')
        if exponent < 0:
            return self.inverse()**(-exponent)
        result, base = self.field.element(1), self
        while exponent:
            if exponent & 1:
                result = result*base
            base = base*base
            exponent >>= 1
        return result

    def inverse(self):
        if not self:
            raise ZeroDivisionError('Zero has no field inverse')
        return self**(self.field.order-2)

    def __truediv__(self, other):
        return self*self.field.element(other).inverse()

    def __rtruediv__(self, other):
        return self.field.element(other)*self.inverse()

    def to_data(self):
        return list(self.coefficients)


class ExtensionCurve:
    """Short Weierstrass y²=x³+ax+b over characteristic >3."""
    def __init__(self, field, a, b):
        if not isinstance(field, GaloisField) or field.p <= 3:
            raise ValueError('Short Weierstrass curve requires characteristic >3')
        self.field, self.a, self.b = field, field.element(a), field.element(b)
        if not 4*self.a**3 + 27*self.b**2:
            raise ValueError('Singular elliptic curve')

    def point(self, value):
        if value is None:
            return None
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError('Point is null or an (x,y) pair')
        x,y = map(self.field.element, value)
        if y*y != x*x*x+self.a*x+self.b:
            raise ValueError('Point is not on this curve')
        return x,y

    def add(self, left, right):
        left, right = self.point(left), self.point(right)
        if left is None:
            return right
        if right is None:
            return left
        x,y = left
        u,v = right
        if x == u and not y+v:
            return None
        slope = (3*x*x+self.a)/(2*y) if left == right else (v-y)/(u-x)
        out_x = slope*slope-x-u
        return out_x, slope*(x-out_x)-y

    def multiply(self, scalar, point):
        if type(scalar) is not int or abs(scalar).bit_length() > 4096:
            raise ValueError('Bounded integer scalar required')
        point = self.point(point)
        if scalar < 0:
            return self.multiply(-scalar, None if point is None else (point[0], -point[1]))
        result = None
        while scalar:
            if scalar & 1:
                result = self.add(result, point)
            point = self.add(point, point)
            scalar >>= 1
        return result

    def _miller_step(self, left, right, evaluation):
        """g_{A,B}(Q)=line(A,B)(Q)/vertical(A+B)(Q)."""
        if left is None or right is None:
            return self.field.element(1)
        x,y = left
        u,v = right
        qx,qy = evaluation
        if x == u and not y+v:
            value = qx-x
        else:
            slope = (3*x*x+self.a)/(2*y) if left == right else (v-y)/(u-x)
            total = self.add(left, right)
            line = qy-y-slope*(qx-x)
            value = line if total is None else line/(qx-total[0])
        if not value:
            raise ValueError('Evaluation intersects a Miller divisor; choose another point')
        return value

    def tate_pairing(self, left, right, r):
        """Reduced Tate pairing f_{r,P}(Q)^((q-1)/r), nonexceptional Q.

P is nonzero r-torsion and r is prime, coprime to the characteristic. Q is
any nonzero curve point outside the Miller divisors (a representative modulo
rE). The caller chooses a field with a suitable embedding degree. No claim of
security or nondegeneracy is made for arbitrary field/subgroup parameters.
"""
        if type(r) is not int or not 2 <= r <= 1000000 or not sympy().isprime(r):
            raise ValueError('Prime subgroup order up to 10^6 required')
        if r == self.field.p or (self.field.order-1) % r:
            raise ValueError('Subgroup must divide q-1 and be prime to characteristic')
        left, right = self.point(left), self.point(right)
        if left is None or right is None or self.multiply(r, left) is not None:
            raise ValueError('Nonzero r-torsion P and nonzero evaluation Q required')
        value, running = self.field.element(1), left
        for bit in bin(r)[3:]:
            value = value*value*self._miller_step(running, running, right)
            running = self.add(running, running)
            if bit == '1':
                value = value*self._miller_step(running, left, right)
                running = self.add(running, left)
        return value**((self.field.order-1)//r)


def finite_field(p, modulus, left, right=0, operation='add', exponent=1):
    field = GaloisField(p, tuple(modulus))
    a,b = field.element(left), field.element(right)
    operations = {'add': lambda: a+b, 'subtract': lambda: a-b,
                  'multiply': lambda: a*b, 'divide': lambda: a/b,
                  'power': lambda: a**exponent, 'inverse': a.inverse}
    if operation not in operations:
        raise ValueError('Unknown field operation')
    return {'coefficients': operations[operation]().to_data(), 'order': field.order,
            'modulus': list(field.modulus), 'arithmetic': 'exact finite field'}


def elliptic(p, modulus, a, b, left, right=None, scalar=1, operation='add', r=None):
    curve = ExtensionCurve(GaloisField(p, tuple(modulus)), a, b)
    if operation == 'pairing':
        result = curve.tate_pairing(left, right, r)
        return {'value': result.to_data(), 'kind': 'reduced Tate', 'subgroup_order': r,
                'security': 'research arithmetic; not constant-time'}
    if operation == 'add':
        result = curve.add(left, right)
    elif operation == 'multiply':
        result = curve.multiply(scalar, left)
    else:
        raise ValueError('Unknown elliptic operation')
    return {'point': None if result is None else [v.to_data() for v in result]}


def groebner_basis(equations, variables, order='grevlex', prime=None):
    """Delegate bounded polynomial elimination to SymPy, exact over QQ/GF(p)."""
    variables = names(variables, 8)
    if not isinstance(equations, (list, tuple)) or not 1 <= len(equations) <= 32:
        raise ValueError('1–32 polynomial equations required')
    if order not in ('lex', 'grlex', 'grevlex'):
        raise ValueError('Unsupported monomial order')
    sp = sympy()
    symbols = tuple(map(sp.Symbol, variables))
    values = [expression(v, variables, functions=False, degree_limit=32)[0] for v in equations]
    if any(not v.is_polynomial(*symbols) or v.has(sp.I, sp.pi) for v in values):
        raise ValueError('Polynomials over rational coefficients required')
    if prime is not None and (type(prime) is not int or not 2 <= prime < 2**31 or not sp.isprime(prime)):
        raise ValueError('Prime modulus required')
    basis = sp.groebner(values, *symbols, order=order,
                        **({'modulus': prime} if prime else {'domain': sp.QQ}))
    return {'basis': [str(v) for v in basis], 'order': order,
            'domain': 'QQ' if prime is None else f'GF({prime})',
            'inconsistent': any(v == 1 for v in basis)}


def calculate(action, **parameters):
    from .advanced_math import calculate as audited
    return audited('algebra_crypto.'+action, **parameters)


__all__ = ['GaloisField', 'FieldElement', 'ExtensionCurve', 'finite_field',
           'elliptic', 'groebner_basis', 'matrix_group', 'calculate']

# Polynomial arithmetic over extension fields, independent of SymPy's domains.
from itertools import product
from math import isqrt, gcd


class FieldPolynomial:
    """Immutable ascending-coefficient polynomial over a declared finite field.

    The zero polynomial has one zero coefficient and degree -1. Arithmetic
    carries the field identity throughout; coercing coefficients from another
    field is rejected even when their byte representation happens to coincide.
    """
    def __init__(self, field, coefficients):
        if not isinstance(field,GaloisField):
            raise ValueError('An extension field is required')
        if not isinstance(coefficients,(list,tuple)) or not 1<=len(coefficients)<=4097:
            raise ValueError('Polynomial coefficient budget exceeded')
        values=[field.element(v) for v in coefficients]
        while len(values)>1 and not values[-1]:values.pop()
        self.field=field
        self.coefficients=tuple(values)

    @property
    def degree(self):
        return len(self.coefficients)-1 if any(self.coefficients) else -1

    @property
    def leading(self):
        return self.coefficients[-1]

    def __bool__(self):
        return self.degree>=0

    def __eq__(self, other):
        return isinstance(other,FieldPolynomial) and self.field==other.field and self.coefficients==other.coefficients

    def _coerce(self, other):
        if isinstance(other,FieldPolynomial):
            if other.field!=self.field:raise ValueError('Polynomial coefficient fields differ')
            return other
        return FieldPolynomial(self.field,[other])

    def __add__(self, other):
        other=self._coerce(other)
        values=[];zero=self.field.element(0)
        for i in range(max(len(self.coefficients),len(other.coefficients))):
            left=self.coefficients[i] if i<len(self.coefficients) else zero
            right=other.coefficients[i] if i<len(other.coefficients) else zero
            values.append(left+right)
        return FieldPolynomial(self.field,values)

    __radd__=__add__

    def __neg__(self):
        return FieldPolynomial(self.field,[-v for v in self.coefficients])

    def __sub__(self, other):
        return self+-self._coerce(other)

    def __rsub__(self, other):
        return self._coerce(other)+-self

    def __mul__(self, other):
        other=self._coerce(other)
        if self.degree+other.degree>4096:
            raise ValueError('Polynomial product degree budget exceeded')
        values=[self.field.element(0)]*(len(self.coefficients)+len(other.coefficients)-1)
        for i,a in enumerate(self.coefficients):
            for j,b in enumerate(other.coefficients):values[i+j]=values[i+j]+a*b
        return FieldPolynomial(self.field,values)

    __rmul__=__mul__

    def divmod(self, divisor):
        divisor=self._coerce(divisor)
        if not divisor:raise ZeroDivisionError('Polynomial division by zero')
        if self.degree<divisor.degree:
            return FieldPolynomial(self.field,[0]),self
        remainder=list(self.coefficients)
        quotient=[self.field.element(0)]*(self.degree-divisor.degree+1)
        inverse=divisor.leading.inverse()
        while len(remainder)>=len(divisor.coefficients) and any(remainder):
            offset=len(remainder)-len(divisor.coefficients)
            factor=remainder[-1]*inverse
            quotient[offset]=factor
            for i,value in enumerate(divisor.coefficients):
                remainder[offset+i]=remainder[offset+i]-factor*value
            while len(remainder)>1 and not remainder[-1]:remainder.pop()
        return FieldPolynomial(self.field,quotient),FieldPolynomial(self.field,remainder)

    def __mod__(self, divisor):
        return self.divmod(divisor)[1]

    def monic(self):
        if not self:return self
        return self*self.leading.inverse()

    def derivative(self):
        if self.degree<1:return FieldPolynomial(self.field,[0])
        return FieldPolynomial(self.field,[i*self.coefficients[i] for i in range(1,len(self.coefficients))])

    def evaluate(self, value):
        value=self.field.element(value)
        result=self.field.element(0)
        for coefficient in reversed(self.coefficients):result=result*value+coefficient
        return result

    def gcd(self, other):
        a,b=self,self._coerce(other)
        while b:a,b=b,a%b
        return a.monic()

    def extended_gcd(self, other):
        """Return monic d,s,t with s*self+t*other=d."""
        other=self._coerce(other)
        r0,r1=self,other
        s0,s1=FieldPolynomial(self.field,[1]),FieldPolynomial(self.field,[0])
        t0,t1=FieldPolynomial(self.field,[0]),FieldPolynomial(self.field,[1])
        while r1:
            quotient,remainder=r0.divmod(r1)
            r0,r1=r1,remainder
            s0,s1=s1,s0-quotient*s1
            t0,t1=t1,t0-quotient*t1
        if not r0:return r0,s0,t0
        inverse=r0.leading.inverse()
        return r0*inverse,s0*inverse,t0*inverse

    def powmod(self, exponent, modulus):
        if type(exponent) is not int or exponent<0 or exponent.bit_length()>4096:
            raise ValueError('Nonnegative bounded modular exponent required')
        modulus=self._coerce(modulus)
        if modulus.degree<1:raise ValueError('Positive-degree modulus required')
        result=FieldPolynomial(self.field,[1]);base=self%modulus
        while exponent:
            if exponent&1:result=(result*base)%modulus
            base=(base*base)%modulus
            exponent>>=1
        return result

    def inverse_mod(self, modulus):
        divisor,s,_=self.extended_gcd(modulus)
        if divisor.degree!=0:
            raise ZeroDivisionError('Polynomial is not invertible modulo this modulus')
        return s%modulus

    def is_irreducible(self):
        """Rabin irreducibility criterion over GF(q), bounded to degree 128."""
        if not 1<=self.degree<=128:
            raise ValueError('Irreducibility test supports degrees 1–128')
        f=self.monic();x=FieldPolynomial(self.field,[0,1]);power=x%f
        prime_divisors=set();remaining=f.degree;candidate=2
        while candidate*candidate<=remaining:
            if remaining%candidate==0:
                prime_divisors.add(candidate)
                while remaining%candidate==0:remaining//=candidate
            candidate+=1
        if remaining>1:prime_divisors.add(remaining)
        checkpoints={f.degree//r for r in prime_divisors}
        for i in range(1,f.degree+1):
            power=power.powmod(self.field.order,f)
            if i in checkpoints and (power-x).gcd(f).degree>0:return False
        return not (power-x)%f

    def square_free(self):
        """Square-freeness only; inseparable nonconstant polynomials return false."""
        if self.degree<1:return True
        return self.gcd(self.derivative()).degree==0

    def roots(self, *, maximum_order=65536):
        """Exhaust all elements only when q is within the explicit work budget."""
        if self.field.order>maximum_order or self.field.order*max(self.degree,1)>1000000:
            raise ValueError('Root enumeration budget exceeded')
        if not self:raise ValueError('Zero polynomial has every field element as root')
        roots=[]
        for coefficients in product(range(self.field.p),repeat=self.field.degree):
            value=self.field.element(coefficients)
            if not self.evaluate(value):roots.append(value)
        return roots

    def to_data(self):
        return [v.to_data() for v in self.coefficients]


def field_trace(field, value):
    """Trace GF(pⁿ)->GF(p), returned in the declared extension representation."""
    if not isinstance(field,GaloisField):raise ValueError('Finite field required')
    value=field.element(value);result=field.element(0);power=value
    for _ in range(field.degree):
        result=result+power
        power=power**field.p
    if any(result.coefficients[1:]):
        raise ArithmeticError('Trace failed the prime-subfield invariant')
    return result


def field_norm(field, value):
    """Norm GF(pⁿ)->GF(p), with norm(0)=0."""
    if not isinstance(field,GaloisField):raise ValueError('Finite field required')
    result=field.element(value)**((field.order-1)//(field.p-1))
    if any(result.coefficients[1:]):
        raise ArithmeticError('Norm failed the prime-subfield invariant')
    return result


def frobenius_orbit(field, value):
    """Distinct conjugates under x->x^p, in deterministic order."""
    value=field.element(value);current=value;orbit=[]
    for _ in range(field.degree):
        if current in orbit:break
        orbit.append(current);current=current**field.p
    if current!=value:
        raise ArithmeticError('Frobenius orbit did not close within extension degree')
    return orbit


def minimal_polynomial(field, value):
    """Minimal polynomial over the prime field from the Frobenius orbit."""
    polynomial=FieldPolynomial(field,[1])
    for conjugate in frobenius_orbit(field,value):
        polynomial=polynomial*FieldPolynomial(field,[-conjugate,1])
    if any(any(c.coefficients[1:]) for c in polynomial.coefficients):
        raise ArithmeticError('Minimal polynomial coefficients did not descend to GF(p)')
    return [c.coefficients[0] for c in polynomial.coefficients]


def multiplicative_order(field, value, *, factor_limit=1000000):
    """Exact order if trial factorization of q−1 completes within the budget."""
    value=field.element(value)
    if not value:raise ValueError('Zero has no multiplicative group order')
    if type(factor_limit) is not int or not 2<=factor_limit<=10000000:
        raise ValueError('Invalid factorization work budget')
    order=field.order-1;remaining=order;factors=[];candidate=2
    while candidate*candidate<=remaining and candidate<=factor_limit:
        if remaining%candidate==0:
            factors.append(candidate)
            while remaining%candidate==0:remaining//=candidate
        candidate+=1
    if remaining>1:
        if candidate*candidate<=remaining and not sympy().isprime(remaining):
            raise ArithmeticError('Order factorization incomplete within budget')
        factors.append(remaining)
    for prime in factors:
        while order%prime==0 and value**(order//prime)==field.element(1):order//=prime
    return order


def finite_field_logarithm(field, generator, target, order=None, max_table=100000):
    """Baby-step/giant-step discrete log in a declared finite cyclic subgroup.

    This is an algebraic research algorithm, not a side-channel-safe primitive.
    A missing result means the target is outside the searched subgroup when
    the declared generator order was verified, rather than a numerical failure.
    """
    generator=field.element(generator);target=field.element(target)
    if not generator or not target:raise ValueError('Nonzero multiplicative elements required')
    order=multiplicative_order(field,generator) if order is None else order
    if type(order) is not int or not 1<=order<=field.order-1 or generator**order!=field.element(1):
        raise ValueError('Invalid subgroup order')
    width=isqrt(order)+1
    if type(max_table) is not int or not 1<=width<=max_table<=1000000:
        raise ValueError('Discrete-log table budget exceeded')
    table={};value=field.element(1)
    for i in range(width):
        table.setdefault(value,i);value=value*generator
    step=generator**(-width);value=target
    for j in range(width+1):
        if value in table:
            exponent=j*width+table[value]
            if exponent<order and generator**exponent==target:
                return {'found':True,'exponent':exponent,'order_multiple':order}
        value=value*step
    return {'found':False,'exponent':None,'order_multiple':order}


def finite_field_matrix(matrix, field, rhs=None):
    """Gauss–Jordan elimination over GF(pⁿ) with optional simultaneous RHS.

    Returns RREF, pivot columns, determinant for square matrices and an affine
    solution description for a single RHS. No floating-point arithmetic enters
    the elimination, including rank and inconsistency decisions.
    """
    if not isinstance(field,GaloisField):raise ValueError('A finite field is required')
    if not isinstance(matrix,(list,tuple)) or not 1<=len(matrix)<=256:
        raise ValueError('Matrix row budget exceeded')
    rows=len(matrix);columns=len(matrix[0])
    if not 1<=columns<=256 or any(len(row)!=columns for row in matrix):
        raise ValueError('Bounded rectangular matrix required')
    augmented=rhs is not None
    if augmented and len(rhs)!=rows:raise ValueError('RHS dimension mismatch')
    values=[[field.element(v) for v in row]+([field.element(rhs[i])] if augmented else []) for i,row in enumerate(matrix)]
    pivot_row=0;pivots=[];determinant=field.element(1);swaps=0
    for column in range(columns):
        pivot=next((i for i in range(pivot_row,rows) if values[i][column]),None)
        if pivot is None:continue
        if pivot!=pivot_row:
            values[pivot],values[pivot_row]=values[pivot_row],values[pivot];swaps+=1
        divisor=values[pivot_row][column];determinant=determinant*divisor
        values[pivot_row]=[v/divisor for v in values[pivot_row]]
        for i in range(rows):
            if i!=pivot_row and values[i][column]:
                factor=values[i][column]
                values[i]=[a-factor*b for a,b in zip(values[i],values[pivot_row])]
        pivots.append(column);pivot_row+=1
        if pivot_row==rows:break
    if rows==columns:
        determinant=determinant*((-1)**swaps) if len(pivots)==rows else field.element(0)
    else:determinant=None
    result={'rref':[[v.to_data() for v in row[:columns]] for row in values],
            'pivots':pivots,'rank':len(pivots),
            'determinant':None if determinant is None else determinant.to_data()}
    if augmented:
        inconsistent=any(not any(row[:columns]) and bool(row[-1]) for row in values)
        result['consistent']=not inconsistent
        if not inconsistent:
            particular=[field.element(0) for _ in range(columns)]
            for i,column in enumerate(pivots):particular[column]=values[i][-1]
            nullspace=[]
            for free in (j for j in range(columns) if j not in pivots):
                vector=[field.element(0) for _ in range(columns)];vector[free]=field.element(1)
                for i,column in enumerate(pivots):vector[column]=-values[i][free]
                nullspace.append([v.to_data() for v in vector])
            result['particular']=[v.to_data() for v in particular]
            result['nullspace']=nullspace
    return result


def tonelli_shanks(value, prime):
    """A square root modulo an odd prime, or None for a nonresidue."""
    if type(prime) is not int or not 3<=prime<2**64 or not sympy().isprime(prime):
        raise ValueError('Odd prime below 2^64 required')
    if type(value) is not int:raise ValueError('Integer quadratic residue required')
    value%=prime
    if value==0:return 0
    if pow(value,(prime-1)//2,prime)!=1:return None
    if prime%4==3:return pow(value,(prime+1)//4,prime)
    q=prime-1;s=0
    while q%2==0:q//=2;s+=1
    z=2
    while pow(z,(prime-1)//2,prime)!=prime-1:z+=1
    c=pow(z,q,prime);root=pow(value,(q+1)//2,prime);t=pow(value,q,prime);m=s
    while t!=1:
        power=t;i=0
        while power!=1 and i<m:
            power=power*power%prime;i+=1
        if i==m:raise ArithmeticError('Tonelli–Shanks invariant failed')
        b=pow(c,1<<(m-i-1),prime)
        root=root*b%prime;t=t*b*b%prime;c=b*b%prime;m=i
    if root*root%prime!=value:raise ArithmeticError('Square-root verification failed')
    return min(root,prime-root)


def count_curve_prime_field(prime, a, b, *, max_prime=1000000):
    """Exact point count by Legendre symbols; intended for bounded references."""
    if type(max_prime) is not int or not 5<=max_prime<=1000000 or not 5<=prime<=max_prime:
        raise ValueError('Point-count prime budget exceeded')
    curve=ExtensionCurve(GaloisField(prime,(0,1)),a,b)
    if any(v.coefficients[1:] for v in (curve.a,curve.b)):
        raise ValueError('Prime field coefficients required')
    aa,bb=curve.a.coefficients[0],curve.b.coefficients[0]
    count=1
    for x in range(prime):
        rhs=(x*x*x+aa*x+bb)%prime
        count+=1 if rhs==0 else 2 if pow(rhs,(prime-1)//2,prime)==1 else 0
    trace=prime+1-count
    if trace*trace>4*prime:raise ArithmeticError('Point count violates Hasse bound')
    return {'points':count,'frobenius_trace':trace,'hasse_bound_verified':True}


def curve_point_order(curve, point, group_order=None, max_order=1000000):
    """Order of a point by bounded enumeration, or factor reduction of known #E."""
    if not isinstance(curve,ExtensionCurve):raise ValueError('Extension elliptic curve required')
    point=curve.point(point)
    if point is None:return 1
    if type(max_order) is not int or not 1<=max_order<=1000000:
        raise ValueError('Point-order budget exceeded')
    if group_order is None:
        value=None
        for i in range(1,max_order+1):
            value=curve.add(value,point)
            if value is None:return i
        raise ArithmeticError('Point order exceeds the declared enumeration budget')
    if type(group_order) is not int or not 1<=group_order<=10**12 or curve.multiply(group_order,point) is not None:
        raise ValueError('Declared group-order multiple does not annihilate the point')
    order=group_order
    for prime in sympy().factorint(group_order):
        while order%prime==0 and curve.multiply(order//prime,point) is None:order//=prime
    return order


def elliptic_discrete_log(curve, generator, target, order, max_table=100000):
    """Exact baby-step/giant-step in an elliptic subgroup with bounded storage."""
    generator,target=curve.point(generator),curve.point(target)
    if generator is None or type(order) is not int or not 1<=order<=10**12 or curve.multiply(order,generator) is not None:
        raise ValueError('Generator and annihilating order required')
    width=isqrt(order)+1
    if not 1<=width<=max_table<=1000000:raise ValueError('Elliptic logarithm table budget exceeded')
    table={};value=None
    for i in range(width):
        table.setdefault(value,i);value=curve.add(value,generator)
    step=curve.multiply(-width,generator);value=target
    for j in range(width+1):
        if value in table:
            exponent=j*width+table[value]
            if exponent<order and curve.multiply(exponent,generator)==target:
                return {'found':True,'exponent':exponent}
        value=curve.add(value,step)
    return {'found':False,'exponent':None}


def sec1_compress(prime, a, b, point):
    """SEC1 compressed point encoding for a short prime-field curve.

    Encoding provides canonical representation only, not a certificate that the
    curve parameters define a secure cryptographic group.
    """
    curve=ExtensionCurve(GaloisField(prime,(0,1)),a,b);point=curve.point(point)
    if point is None:return b'\x00'
    size=(prime.bit_length()+7)//8
    x,y=(v.coefficients[0] for v in point)
    return bytes([2+(y&1)])+x.to_bytes(size,'big')


def sec1_decompress(prime, a, b, encoded):
    """Decode canonical SEC1 compressed points, rejecting noncanonical x."""
    curve=ExtensionCurve(GaloisField(prime,(0,1)),a,b)
    if not isinstance(encoded,bytes):raise ValueError('SEC1 input must be bytes')
    if encoded==b'\x00':return None
    size=(prime.bit_length()+7)//8
    if len(encoded)!=size+1 or encoded[0] not in (2,3):raise ValueError('Invalid compressed SEC1 encoding')
    x=int.from_bytes(encoded[1:],'big')
    if x>=prime:raise ValueError('Noncanonical SEC1 x coordinate')
    rhs=(x*x*x+curve.a.coefficients[0]*x+curve.b.coefficients[0])%prime
    y=tonelli_shanks(rhs,prime)
    if y is None:raise ValueError('Compressed point is not on this curve')
    if y&1!=encoded[0]&1:y=(-y)%prime
    if y&1!=encoded[0]&1:raise ValueError('Impossible SEC1 parity for a zero ordinate')
    curve.point([x,y])
    return [x,y]


__all__ += ['FieldPolynomial','field_trace','field_norm','frobenius_orbit',
            'minimal_polynomial','multiplicative_order','finite_field_logarithm',
            'finite_field_matrix','tonelli_shanks','count_curve_prime_field',
            'curve_point_order','elliptic_discrete_log','sec1_compress','sec1_decompress']


@dataclass(frozen=True, eq=False)
class EllipticCurvePoint:
    """Jacobian Weierstrass point (X:Y:Z), x=X/Z² and y=Y/Z³.

    Addition and doubling use multiplication-only projective formulas. Field
    inversions occur only when converting a finite point to affine form. This
    reduces operation cost but does not make Python arithmetic constant-time.
    """
    curve: ExtensionCurve
    x: FieldElement
    y: FieldElement
    z: FieldElement

    def __post_init__(self):
        if not isinstance(self.curve,ExtensionCurve):raise ValueError('An extension curve is required')
        field=self.curve.field
        x,y,z=(field.element(v) for v in (self.x,self.y,self.z))
        if not z:
            if x!=field.element(1) or y!=field.element(1):
                raise ValueError('Infinity must use canonical Jacobian coordinates (1,1,0)')
        elif y*y!=x*x*x+self.curve.a*x*z**4+self.curve.b*z**6:
            raise ValueError('Jacobian point does not satisfy the curve equation')
        object.__setattr__(self,'x',x);object.__setattr__(self,'y',y);object.__setattr__(self,'z',z)

    @classmethod
    def infinity(cls, curve):
        return cls(curve,curve.field.element(1),curve.field.element(1),curve.field.element(0))

    @classmethod
    def affine(cls, curve, point):
        value=curve.point(point)
        return cls.infinity(curve) if value is None else cls(curve,*value,curve.field.element(1))

    @property
    def is_infinity(self):
        return not self.z

    def _compatible(self, other):
        if not isinstance(other,EllipticCurvePoint) or (self.curve.field,self.curve.a,self.curve.b)!=(other.curve.field,other.curve.a,other.curve.b):
            raise ValueError('Points belong to different curves')

    def __eq__(self, other):
        if not isinstance(other,EllipticCurvePoint):return False
        try:self._compatible(other)
        except ValueError:return False
        if self.is_infinity or other.is_infinity:return self.is_infinity and other.is_infinity
        return self.x*other.z**2==other.x*self.z**2 and self.y*other.z**3==other.y*self.z**3

    def __neg__(self):
        return self if self.is_infinity else EllipticCurvePoint(self.curve,self.x,-self.y,self.z)

    def double(self):
        if self.is_infinity or not self.y:return self.infinity(self.curve)
        xx=self.x*self.x;yy=self.y*self.y;yyyy=yy*yy;zz=self.z*self.z
        s=2*((self.x+yy)**2-xx-yyyy)
        m=3*xx+self.curve.a*zz*zz
        x=m*m-2*s
        y=m*(s-x)-8*yyyy
        z=(self.y+self.z)**2-yy-zz
        return EllipticCurvePoint(self.curve,x,y,z)

    def add(self, other):
        self._compatible(other)
        if self.is_infinity:return other
        if other.is_infinity:return self
        z1z1=self.z*self.z;z2z2=other.z*other.z
        u1=self.x*z2z2;u2=other.x*z1z1
        s1=self.y*other.z*z2z2;s2=other.y*self.z*z1z1
        if u1==u2:return self.double() if s1==s2 else self.infinity(self.curve)
        h=u2-u1;i=(2*h)**2;j=h*i;r=2*(s2-s1);v=u1*i
        x=r*r-j-2*v
        y=r*(v-x)-2*s1*j
        z=((self.z+other.z)**2-z1z1-z2z2)*h
        return EllipticCurvePoint(self.curve,x,y,z)

    def multiply(self, scalar):
        if type(scalar) is not int or abs(scalar).bit_length()>4096:
            raise ValueError('Bounded integer scalar required')
        if scalar<0:return (-self).multiply(-scalar)
        result=self.infinity(self.curve);value=self
        while scalar:
            if scalar&1:result=result.add(value)
            value=value.double();scalar>>=1
        return result

    def to_affine(self):
        if self.is_infinity:return None
        inverse=self.z.inverse()
        return self.x*inverse**2,self.y*inverse**3

    def to_data(self):
        return {'x':self.x.to_data(),'y':self.y.to_data(),'z':self.z.to_data(),
                'infinity':self.is_infinity,'coordinates':'Jacobian'}


class BilinearPairing:
    """Validated pairing adapter for BN254/BLS12-381 and research Tate curves.

    Named large curves use py_ecc's optimized Miller loop and final
    exponentiation, with on-curve and subgroup checks before every evaluation.
    This class supplies algebraic verification and serialization, not a SNARK
    protocol, trusted setup, key handling or side-channel certification.
    """
    def __init__(self, curve='BN254'):
        if curve not in ('BN254','BLS12-381'):
            raise ValueError('Pairing curve is BN254 or BLS12-381')
        try:
            if curve=='BN254':from py_ecc import optimized_bn128 as backend
            else:from py_ecc import optimized_bls12_381 as backend
        except ImportError as error:
            raise ImportError('Install nablamath[pairing] for BN254/BLS12-381 pairings') from error
        self.curve=curve;self.backend=backend

    @staticmethod
    def _integer(value, prime):
        if type(value) is str:
            if not value.isdecimal() or len(value)>160:raise ValueError('Canonical decimal field coordinate required')
            value=int(value)
        if type(value) is not int or not 0<=value<prime:
            raise ValueError('Field coordinate outside canonical prime-field range')
        return value

    def g1(self, point=None):
        backend=self.backend
        if point is None:return backend.G1
        if not isinstance(point,(list,tuple)) or len(point) not in (2,3):raise ValueError('G1 affine/projective coordinates required')
        values=[backend.FQ(self._integer(v,backend.field_modulus)) for v in point]
        if len(values)==2:values.append(backend.FQ.one())
        value=tuple(values)
        if backend.is_inf(value) or not backend.is_on_curve(value,backend.b) or not backend.is_inf(backend.multiply(value,backend.curve_order)):
            raise ValueError('G1 point is infinite, off-curve or outside the prime-order subgroup')
        return value

    def g2(self, point=None):
        backend=self.backend
        if point is None:return backend.G2
        if not isinstance(point,(list,tuple)) or len(point) not in (2,3):raise ValueError('G2 affine/projective coordinates required')
        values=[]
        for coordinate in point:
            if not isinstance(coordinate,(list,tuple)) or len(coordinate)!=2:
                raise ValueError('G2 coordinates need two prime-field coefficients')
            values.append(backend.FQ2([self._integer(v,backend.field_modulus) for v in coordinate]))
        if len(values)==2:values.append(backend.FQ2.one())
        value=tuple(values)
        if backend.is_inf(value) or not backend.is_on_curve(value,backend.b2) or not backend.is_inf(backend.multiply(value,backend.curve_order)):
            raise ValueError('G2 point is infinite, off-curve or outside the prime-order subgroup')
        return value

    def miller(self, g1=None, g2=None):
        return self.backend.pairing(self.g2(g2),self.g1(g1),final_exponentiate=False)

    def evaluate(self, g1=None, g2=None):
        value=self.backend.final_exponentiate(self.miller(g1,g2))
        if value**self.backend.curve_order!=self.backend.FQ12.one():
            raise ArithmeticError('Pairing output failed target-subgroup check')
        return {'curve':self.curve,'coefficients':[int(c) for c in value.coeffs],
                'subgroup_order':str(self.backend.curve_order),
                'pairing':'Optimal Ate via validated py_ecc backend',
                'side_channel_resistance':'Not established for this Python implementation'}

    def verify_product(self, pairs):
        if not isinstance(pairs,(list,tuple)) or not 1<=len(pairs)<=32:
            raise ValueError('Pairing product supports 1–32 pairs')
        value=self.backend.FQ12.one()
        for pair in pairs:
            if not isinstance(pair,dict) or set(pair)-{'g1','g2','sign'}:
                raise ValueError('Pair requires g1, g2 and optional sign')
            sign=pair.get('sign',1)
            if type(sign) is not int or sign not in (-1,1):raise ValueError('Pairing sign is +/-1')
            point=self.g1(pair.get('g1'))
            if sign==-1:point=self.backend.neg(point)
            value*=self.backend.pairing(self.g2(pair.get('g2')),point,final_exponentiate=False)
        result=self.backend.final_exponentiate(value)
        return {'identity':result==self.backend.FQ12.one(),'curve':self.curve,
                'pairs':len(pairs),'verification':'Subgroup-checked algebraic pairing identity'}


class PolynomialIdeal:
    """Bounded rational polynomial ideal with explicit generators and order."""
    def __init__(self, generators, variables, order='grevlex'):
        self.variables=names(variables,6);self.symbols=tuple(map(sympy().Symbol,self.variables))
        if not isinstance(generators,(list,tuple)) or not 1<=len(generators)<=32:
            raise ValueError('Ideal supports 1–32 generators')
        if order not in ('lex','grlex','grevlex'):raise ValueError('Unsupported monomial order')
        self.order=order;self.generators=[]
        for source in generators:
            value=expression(source,self.variables,functions=False,degree_limit=16)[0]
            try:polynomial=sympy().Poly(value,*self.symbols,domain=sympy().QQ)
            except (sympy().PolynomialError,sympy().CoercionFailed) as error:
                raise ValueError('Ideal generators must be rational polynomials') from error
            if len(polynomial.terms())>4096:raise ValueError('Ideal term budget exceeded')
            self.generators.append(polynomial.as_expr())
        self.generators=tuple(self.generators)

    def basis(self, **budgets):
        return BuchbergerAlgorithm(self,**budgets).run()

    def contains(self, polynomial, **budgets):
        result=self.basis(**budgets)
        value=expression(polynomial,self.variables,functions=False,degree_limit=32)[0]
        if not value.is_polynomial(*self.symbols):raise ValueError('Polynomial membership input required')
        _,remainder=sympy().reduced(value,[sympy().Poly(v,*self.symbols,domain=sympy().QQ).as_expr()
                                          for v in result['_polynomials']],*self.symbols,order=self.order,domain=sympy().QQ)
        return {'member':remainder==0,'remainder':str(remainder),'basis':[str(v) for v in result['_polynomials']]}


class BuchbergerAlgorithm:
    """Classical Buchberger with product criterion and exact S-remainders.

    Pair scheduling uses lcm degree then deterministic indices. Coprime leading
    monomials invoke Buchberger's product criterion. An unprocessed pair is
    never called solved when a work budget is exhausted: the algorithm raises
    with the count, preserving the distinction from a valid Gröbner basis.
    """
    def __init__(self, ideal, *, max_pairs=2048, max_basis=128, max_terms=8192):
        if not isinstance(ideal,PolynomialIdeal):raise ValueError('PolynomialIdeal required')
        if any(type(v) is not int for v in (max_pairs,max_basis,max_terms)) or not 1<=max_pairs<=100000 or not 1<=max_basis<=512 or not 1<=max_terms<=100000:
            raise ValueError('Invalid Buchberger resource budgets')
        self.ideal=ideal;self.max_pairs=max_pairs;self.max_basis=max_basis;self.max_terms=max_terms

    def run(self):
        sp=sympy();symbols=self.ideal.symbols;order=self.ideal.order
        def polynomial(value):
            result=sp.Poly(value,*symbols,domain=sp.QQ)
            if len(result.terms())>self.max_terms or result.total_degree()>128:
                raise ArithmeticError('Buchberger polynomial size budget exceeded')
            return result
        def leading(value):
            terms=polynomial(value).terms(order=order)
            return terms[0]
        def monomial(powers):return sp.prod(x**e for x,e in zip(symbols,powers))
        def monic(value):
            _,coefficient=leading(value)
            return sp.expand(value/coefficient)
        basis=[]
        for generator in self.ideal.generators:
            if generator==0:continue
            remainder=sp.reduced(generator,basis,*symbols,order=order,domain=sp.QQ)[1] if basis else generator
            if remainder!=0:
                basis.append(monic(polynomial(remainder).as_expr()))
                if basis[-1]==1:break
        if not basis:return {'basis':[],'pairs_processed':0,'product_criterion_skips':0,'_polynomials':[]}
        pairs={(i,j) for j in range(len(basis)) for i in range(j)}
        processed=skipped=0
        while pairs:
            if processed>=self.max_pairs:raise ArithmeticError('Buchberger pair budget exhausted without completion')
            def score(pair):
                a,b=(leading(basis[k])[0] for k in pair)
                return sum(max(x,y) for x,y in zip(a,b)),pair
            i,j=min(pairs,key=score);pairs.remove((i,j));processed+=1
            left,lc_left=leading(basis[i]);right,lc_right=leading(basis[j])
            if all(min(a,b)==0 for a,b in zip(left,right)):
                skipped+=1;continue
            lcm=tuple(max(a,b) for a,b in zip(left,right))
            first=monomial(tuple(c-a for c,a in zip(lcm,left)))*basis[i]/lc_left
            second=monomial(tuple(c-b for c,b in zip(lcm,right)))*basis[j]/lc_right
            s_polynomial=polynomial(sp.expand(first-second)).as_expr()
            remainder=sp.reduced(s_polynomial,basis,*symbols,order=order,domain=sp.QQ)[1]
            if remainder==0:continue
            value=monic(polynomial(remainder).as_expr())
            if value==1:
                basis=[sp.Integer(1)];pairs.clear();break
            if len(basis)>=self.max_basis:raise ArithmeticError('Buchberger basis budget exhausted')
            pairs.update((k,len(basis)) for k in range(len(basis)))
            basis.append(value)
        reduced=[]
        for i,value in enumerate(basis):
            others=basis[:i]+basis[i+1:]
            remainder=sp.reduced(value,others,*symbols,order=order,domain=sp.QQ)[1] if others else value
            if remainder!=0:
                candidate=monic(polynomial(remainder).as_expr())
                if candidate not in reduced:reduced.append(candidate)
        # Verify the final S-polynomial criterion independently of pair skips.
        verified=True
        for j in range(len(reduced)):
            for i in range(j):
                a,ca=leading(reduced[i]);b,cb=leading(reduced[j]);lcm=tuple(max(x,y) for x,y in zip(a,b))
                s=monomial(tuple(c-x for c,x in zip(lcm,a)))*reduced[i]/ca-monomial(tuple(c-y for c,y in zip(lcm,b)))*reduced[j]/cb
                if sp.reduced(sp.expand(s),reduced,*symbols,order=order,domain=sp.QQ)[1]!=0:verified=False
        if not verified:raise ArithmeticError('Final Buchberger criterion verification failed')
        return {'basis':list(map(str,reduced)),'pairs_processed':processed,
                'product_criterion_skips':skipped,'s_criterion_verified':verified,
                'order':order,'_polynomials':reduced}


class LieAlgebra:
    """Exact matrix commutator algebras so(3), su(2), su(3).

    su(n) bases are anti-Hermitian i*sigma/2 and i*lambda/2; structure constants
    are extracted from matrix entries by an exact linear solve and verified by
    reconstruction. The convention fixes signs that differ between Hermitian
    physics generators and anti-Hermitian mathematical generators.
    """
    def __init__(self, kind):
        sp=sympy();i=sp.I
        if kind=='so3':
            basis=[sp.Matrix([[0,0,0],[0,0,-1],[0,1,0]]),
                   sp.Matrix([[0,0,1],[0,0,0],[-1,0,0]]),
                   sp.Matrix([[0,-1,0],[1,0,0],[0,0,0]])]
        elif kind=='su2':
            basis=[i*sp.Matrix([[0,1],[1,0]])/2,
                   i*sp.Matrix([[0,-i],[i,0]])/2,
                   i*sp.Matrix([[1,0],[0,-1]])/2]
        elif kind=='su3':
            hermitian=[sp.Matrix([[0,1,0],[1,0,0],[0,0,0]]),
                       sp.Matrix([[0,-i,0],[i,0,0],[0,0,0]]),
                       sp.diag(1,-1,0),
                       sp.Matrix([[0,0,1],[0,0,0],[1,0,0]]),
                       sp.Matrix([[0,0,-i],[0,0,0],[i,0,0]]),
                       sp.Matrix([[0,0,0],[0,0,1],[0,1,0]]),
                       sp.Matrix([[0,0,0],[0,0,-i],[0,i,0]]),
                       sp.diag(1,1,-2)/sp.sqrt(3)]
            basis=[i*matrix/2 for matrix in hermitian]
        else:raise ValueError('Lie algebra kind is so3, su2 or su3')
        self.kind=kind;self.basis=tuple(basis);self.matrix_dimension=basis[0].rows
        self._design=sp.Matrix.hstack(*(matrix.reshape(matrix.rows**2,1) for matrix in basis))

    @staticmethod
    def commutator(left,right):
        return left*right-right*left

    def structure_constants(self):
        sp=sympy();result=[]
        for left in self.basis:
            rows=[]
            for right in self.basis:
                commutator=self.commutator(left,right)
                solution,parameters=self._design.gauss_jordan_solve(commutator.reshape(commutator.rows**2,1))
                if parameters.rows:raise ArithmeticError('Lie basis is linearly dependent')
                reconstructed=sp.zeros(self.matrix_dimension)
                for coefficient,matrix in zip(solution,self.basis):reconstructed+=coefficient*matrix
                if any(sp.simplify(v)!=0 for v in reconstructed-commutator):raise ArithmeticError('Lie structure reconstruction failed')
                rows.append(list(map(lambda v:str(sp.simplify(v)),solution)))
            result.append(rows)
        return {'kind':self.kind,'constants':result,'convention':'[T_a,T_b]=sum_c f_ab^c T_c; anti-Hermitian su generators'}

    def element(self, coefficients):
        if not isinstance(coefficients,(list,tuple)) or len(coefficients)!=len(self.basis):
            raise ValueError('One coefficient per Lie generator required')
        sp=sympy();result=sp.zeros(self.matrix_dimension)
        for value,matrix in zip(coefficients,self.basis):
            scalar=expression(value,['scalar'])[0]
            if scalar.free_symbols:raise ValueError('Constant coefficients required')
            result+=scalar*matrix
        return result

    def killing_form(self):
        constants=self.structure_constants()['constants'];sp=sympy();n=len(constants)
        parsed=[[[expression(v,['scalar'])[0] for v in row] for row in layer] for layer in constants]
        matrix=[[sp.simplify(sum(parsed[a][i][j]*parsed[b][j][i] for i in range(n) for j in range(n)))
                 for b in range(n)] for a in range(n)]
        return {'components':[[str(v) for v in row] for row in matrix],'kind':self.kind}


class MatrixExponentialBCH:
    """BCH through homogeneous degree four with exact commutator arithmetic."""
    @staticmethod
    def bch(left, right, order=4):
        sp=sympy()
        if not isinstance(left,sp.MatrixBase):left=sp.Matrix(left)
        if not isinstance(right,sp.MatrixBase):right=sp.Matrix(right)
        if left.shape!=right.shape or left.rows!=left.cols or not 1<=left.rows<=8:
            raise ValueError('Matching square matrices of size <=8 required')
        if type(order) is not int or not 1<=order<=4:raise ValueError('BCH degree must be 1–4')
        comm=lambda a,b:a*b-b*a
        result=left+right
        if order>=2:result+=comm(left,right)/2
        if order>=3:result+=(comm(left,comm(left,right))+comm(right,comm(right,left)))/12
        if order>=4:result-=comm(right,comm(left,comm(left,right)))/24
        return result.applyfunc(sp.simplify)

    @staticmethod
    def exponential(matrix):
        import numpy as np
        from scipy.linalg import expm
        value=np.asarray(matrix,dtype=complex)
        if value.ndim!=2 or value.shape[0]!=value.shape[1] or not 1<=len(value)<=64 or not np.isfinite(value).all():
            raise ValueError('Finite square matrix of size <=64 required')
        result=expm(value)
        if not np.isfinite(result).all():raise ArithmeticError('Matrix exponential overflow')
        return [[[float(v.real),float(v.imag)] for v in row] for row in result]

    @classmethod
    def lie(cls, kind, left, right, order=4):
        algebra=LieAlgebra(kind)
        a,b=algebra.element(left),algebra.element(right)
        result=cls.bch(a,b,order)
        return {'kind':kind,'bch':[[str(v) for v in row] for row in result.tolist()],
                'order':order,'scope':'Truncated formal Lie series; no convergence claim for arbitrary inputs'}


def galois_field_op(p, modulus, left, right=0, field_operation='add', exponent=1):
    return finite_field(p,modulus,left,right,field_operation,exponent)


def elliptic_curve_pairing(curve='BN254', g1=None, g2=None):
    return BilinearPairing(curve).evaluate(g1,g2)


def grobner_basis_solve(generators, variables, order='grevlex', max_pairs=2048):
    result=PolynomialIdeal(generators,variables,order).basis(max_pairs=max_pairs)
    return {key:value for key,value in result.items() if key!='_polynomials'}


def lie_algebra_bch(kind, left, right, order=4):
    return MatrixExponentialBCH.lie(kind,left,right,order)


__all__ += ['EllipticCurvePoint','BilinearPairing','PolynomialIdeal','BuchbergerAlgorithm',
            'LieAlgebra','MatrixExponentialBCH','galois_field_op','elliptic_curve_pairing',
            'grobner_basis_solve','lie_algebra_bch']


def extended_euclidean(left, right):
    """Integer Bezout coefficients, with nonnegative gcd.

    This Euclidean algorithm has logarithmic iteration complexity in operand
    magnitude, but is VARIABLE-TIME. Python big integers, branches and memory
    allocation do not provide side-channel resistance.
    """
    if type(left) is not int or type(right) is not int or max(abs(left).bit_length(),abs(right).bit_length())>4096:
        raise ValueError('Integer Bezout inputs must fit the 4096-bit budget')
    old_r,r=left,right;old_s,s=1,0;old_t,t=0,1
    while r:
        quotient=old_r//r
        old_r,r=r,old_r-quotient*r
        old_s,s=s,old_s-quotient*s
        old_t,t=t,old_t-quotient*t
    if old_r<0:old_r,old_s,old_t=-old_r,-old_s,-old_t
    return {'gcd':old_r,'left_coefficient':old_s,'right_coefficient':old_t,
            'identity_verified':old_s*left+old_t*right==old_r,
            'timing':'variable-time; O(log magnitude) does not mean constant-time'}


def modular_inverse_euclidean(value, modulus):
    if type(modulus) is not int or modulus<=1:raise ValueError('Integer modulus greater than one required')
    result=extended_euclidean(value,modulus)
    if result['gcd']!=1:raise ZeroDivisionError('Value is not invertible modulo this modulus')
    inverse=result['left_coefficient']%modulus
    return {'inverse':inverse,'modulus':modulus,'verified':value*inverse%modulus==1,
            'timing':result['timing']}


def extension_square_root(field, value, *, search_limit=256):
    """Tonelli–Shanks in GF(q), or the inverse Frobenius in characteristic two."""
    import random
    value=field.element(value);one=field.element(1);zero=field.element(0)
    if not value:return zero
    if field.p==2:
        root=value**(field.order//2)
        if root*root!=value:raise ArithmeticError('Characteristic-two square root failed verification')
        return root
    q=field.order
    if value**((q-1)//2)!=one:return None
    if q%4==3:return value**((q+1)//4)
    odd=q-1;power=0
    while odd%2==0:odd//=2;power+=1
    if type(search_limit) is not int or not 1<=search_limit<=10000:raise ValueError('Square-root search budget invalid')
    rng=random.Random(0);nonresidue=None
    for _ in range(search_limit):
        candidate=field.element([rng.randrange(field.p) for _ in range(field.degree)])
        if candidate and candidate**((q-1)//2)!=one:nonresidue=candidate;break
    if nonresidue is None:raise ArithmeticError('Quadratic-nonresidue search budget exhausted')
    c=nonresidue**odd;root=value**((odd+1)//2);t=value**odd;m=power
    while t!=one:
        u=t;i=0
        while u!=one and i<m:u=u*u;i+=1
        if i==m:raise ArithmeticError('Extension Tonelli–Shanks invariant failed')
        b=c**(1<<(m-i-1));root=root*b;t=t*b*b;c=b*b;m=i
    if root*root!=value:raise ArithmeticError('Extension square-root verification failed')
    return root


def field_interpolate(field, nodes, values):
    """Lagrange interpolation with an exact reconstruction check at every node."""
    if not isinstance(nodes,(list,tuple)) or not 1<=len(nodes)<=256 or len(values)!=len(nodes):
        raise ValueError('1–256 paired interpolation samples required')
    x=[field.element(v) for v in nodes];y=[field.element(v) for v in values]
    if len(set(x))!=len(x):raise ValueError('Interpolation nodes must be distinct in the field')
    result=FieldPolynomial(field,[0])
    for i,node in enumerate(x):
        numerator=FieldPolynomial(field,[1]);denominator=field.element(1)
        for j,other in enumerate(x):
            if j!=i:
                numerator=numerator*FieldPolynomial(field,[-other,1]);denominator=denominator*(node-other)
        result=result+numerator*(y[i]/denominator)
    if any(result.evaluate(node)!=value for node,value in zip(x,y)):
        raise ArithmeticError('Finite-field interpolation failed reconstruction')
    return result


class ReedSolomonCode:
    """Evaluation Reed–Solomon code with exact Berlekamp–Welch error correction.

    This is coding theory over the same GF(pⁿ) implementation, not an encrypted
    communication scheme. Unique decoding corrects up to floor((n-k)/2)
    arbitrary symbol errors. The decoder verifies all recovered codeword symbols
    and refuses words outside its error budget rather than guessing a message.
    """
    def __init__(self, field, nodes, message_length):
        if not isinstance(field,GaloisField) or not isinstance(nodes,(list,tuple)) or not 1<=len(nodes)<=256:
            raise ValueError('Finite field and 1–256 evaluation nodes required')
        if type(message_length) is not int or not 1<=message_length<=len(nodes):
            raise ValueError('Message dimension must lie between one and code length')
        self.field=field;self.nodes=tuple(field.element(v) for v in nodes);self.k=message_length
        if len(set(self.nodes))!=len(self.nodes):raise ValueError('Reed–Solomon nodes must be distinct')

    @property
    def correction_radius(self):return (len(self.nodes)-self.k)//2

    def encode(self, message):
        if not isinstance(message,(list,tuple)) or len(message)!=self.k:raise ValueError('Message coefficient vector has wrong length')
        polynomial=FieldPolynomial(self.field,message)
        return [polynomial.evaluate(node).to_data() for node in self.nodes]

    def syndrome(self, word):
        """Interpolation-based parity residuals relative to the first k symbols."""
        if len(word)!=len(self.nodes):raise ValueError('Codeword length differs from code')
        values=[self.field.element(v) for v in word]
        polynomial=field_interpolate(self.field,self.nodes[:self.k],values[:self.k])
        residual=[values[i]-polynomial.evaluate(self.nodes[i]) for i in range(self.k,len(values))]
        return {'residuals':[v.to_data() for v in residual],'is_codeword':not any(residual)}

    def decode(self, word, errors=None):
        if not isinstance(word,(list,tuple)) or len(word)!=len(self.nodes):raise ValueError('Codeword length differs from code')
        radius=self.correction_radius if errors is None else errors
        if type(radius) is not int or not 0<=radius<=self.correction_radius:raise ValueError('Error budget exceeds unique decoding radius')
        values=[self.field.element(v) for v in word];f=self.field
        # Try the actual error count from zero upward. Monic E avoids the
        # homogeneous all-zero solution and makes exact division unambiguous.
        for t in range(radius+1):
            matrix=[];rhs=[]
            for x,y in zip(self.nodes,values):
                matrix.append([x**j for j in range(self.k+t)]+[-y*x**j for j in range(t)])
                rhs.append(y*x**t)
            solution=finite_field_matrix(matrix,f,rhs)
            if not solution['consistent']:continue
            coefficients=[f.element(v) for v in solution['particular']]
            q=FieldPolynomial(f,coefficients[:self.k+t]);e=FieldPolynomial(f,coefficients[self.k+t:]+[f.element(1)])
            message,remainder=q.divmod(e)
            if remainder or message.degree>=self.k:continue
            recovered=[message.evaluate(x) for x in self.nodes]
            mismatch=[i for i,(a,b) in enumerate(zip(recovered,values)) if a!=b]
            if len(mismatch)>t:continue
            padded=list(message.coefficients)+[f.element(0)]*(self.k-len(message.coefficients))
            return {'decoded':True,'message':[v.to_data() for v in padded],
                    'codeword':[v.to_data() for v in recovered],'error_positions':mismatch,
                    'errors_corrected':len(mismatch),'unique_radius':self.correction_radius}
        return {'decoded':False,'message':None,'reason':'No verified codeword within the requested unique decoding radius'}


def miller_function(curve, point, evaluation, order):
    """Raw f_{order,P}(Q), with explicit divisor and torsion validation."""
    if not isinstance(curve,ExtensionCurve):raise ValueError('Extension curve required')
    point=curve.point(point);evaluation=curve.point(evaluation)
    if point is None or evaluation is None or type(order) is not int or not 2<=order<=1000000:
        raise ValueError('Nonzero points and bounded positive Miller order required')
    if curve.multiply(order,point) is not None:raise ValueError('Miller point is not annihilated by the declared order')
    value=curve.field.element(1);running=point
    for bit in bin(order)[3:]:
        value=value*value*curve._miller_step(running,running,evaluation);running=curve.add(running,running)
        if bit=='1':
            value=value*curve._miller_step(running,point,evaluation);running=curve.add(running,point)
    return value


def weil_pairing(curve, left, right, order, *, shift=None, attempts=128):
    """Weil pairing by disjoint translated divisors, exact in the supplied field.

    A successful result verifies e^r=1. If no admissible shift is found within
    the bounded deterministic search, evaluation fails explicitly; no zero or
    guessed identity is returned. This is separate from the optimal-Ate backend
    used for BN254/BLS12-381 and does not claim cryptographic efficiency.
    """
    import random
    if not isinstance(curve,ExtensionCurve):raise ValueError('Extension curve required')
    left,right=curve.point(left),curve.point(right)
    if type(order) is not int or not 2<=order<=1000000 or gcd(order,curve.field.p)!=1:
        raise ValueError('Pairing order must be bounded and prime to the characteristic')
    if left is None or right is None:return curve.field.element(1)
    if curve.multiply(order,left) is not None or curve.multiply(order,right) is not None:
        raise ValueError('Both Weil pairing points must be r-torsion')
    if type(attempts) is not int or not 1<=attempts<=10000:raise ValueError('Invalid shift search budget')
    rng=random.Random(0)
    def candidates():
        if shift is not None:
            yield curve.point(shift);return
        for _ in range(attempts):
            x=curve.field.element([rng.randrange(curve.field.p) for _ in range(curve.field.degree)])
            y=extension_square_root(curve.field,x*x*x+curve.a*x+curve.b)
            if y is not None:yield x,y
    for s in candidates():
        if s is None:continue
        minus_s=s[0],-s[1]
        q_plus_s=curve.add(right,s);p_minus_s=curve.add(left,minus_s)
        if q_plus_s is None or p_minus_s is None:continue
        try:
            value=miller_function(curve,left,q_plus_s,order)/miller_function(curve,left,s,order)
            value=value*miller_function(curve,right,minus_s,order)/miller_function(curve,right,p_minus_s,order)
        except (ZeroDivisionError,ValueError):continue
        if value**order!=curve.field.element(1):raise ArithmeticError('Weil target-subgroup invariant failed')
        return value
    raise ArithmeticError('No divisor-disjoint Weil pairing shift found within the declared budget')


class VeluIsogeny:
    """Explicit separable Velu quotient by a small rational cyclic kernel.

    The kernel is enumerated and checked in the supplied finite field. This
    implementation is a reference for small-degree exact isogenies, not a
    post-quantum cryptosystem or a supersingular-isogeny security claim.
    """
    def __init__(self, curve, generator, degree, *, max_degree=128):
        if not isinstance(curve,ExtensionCurve):raise ValueError('Extension curve required')
        if type(degree) is not int or not 2<=degree<=max_degree<=512 or degree%curve.field.p==0:
            raise ValueError('Separable bounded kernel degree required')
        generator=curve.point(generator)
        if generator is None or curve_point_order(curve,generator,group_order=degree)!=degree:
            raise ValueError('Kernel generator does not have the declared exact order')
        self.domain=curve;self.degree=degree
        self.kernel=tuple(curve.multiply(i,generator) for i in range(1,degree))
        t=sum((3*x*x+curve.a for x,y in self.kernel),curve.field.element(0))
        w=sum((5*x*x*x+3*curve.a*x+2*curve.b for x,y in self.kernel),curve.field.element(0))
        self.codomain=ExtensionCurve(curve.field,curve.a-5*t,curve.b-7*w)

    def evaluate(self, point):
        point=self.domain.point(point)
        if point is None or point in self.kernel:return None
        x,y=point;out_x=x;out_y=y
        for kernel_point in self.kernel:
            shifted=self.domain.add(point,kernel_point)
            if shifted is None:return None
            out_x=out_x+shifted[0]-kernel_point[0]
            out_y=out_y+shifted[1]-kernel_point[1]
        return self.codomain.point((out_x,out_y))

    def to_data(self):
        return {'degree':self.degree,'codomain_a':self.codomain.a.to_data(),
                'codomain_b':self.codomain.b.to_data(),
                'kernel':[[v.to_data() for v in point] for point in self.kernel],
                'scope':'Exact rational-kernel separable isogeny in the declared finite field'}


def curve_invariants(curve):
    """Discriminant and j-invariant of y²=x³+ax+b in characteristic >3."""
    if not isinstance(curve,ExtensionCurve):raise ValueError('Extension curve required')
    denominator=4*curve.a**3+27*curve.b**2
    return {'discriminant':(-16*denominator).to_data(),
            'j_invariant':(1728*4*curve.a**3/denominator).to_data(),
            'nonsingular':bool(denominator)}


def curve_scale_isomorphism(curve, scale, point):
    """(x,y)->(u²x,u³y), a' = u⁴a and b' = u⁶b for u != 0."""
    scale=curve.field.element(scale)
    if not scale:raise ValueError('Nonzero curve-isomorphism scale required')
    target=ExtensionCurve(curve.field,scale**4*curve.a,scale**6*curve.b)
    value=curve.point(point)
    mapped=None if value is None else target.point((scale**2*value[0],scale**3*value[1]))
    return {'curve_a':target.a.to_data(),'curve_b':target.b.to_data(),
            'point':None if mapped is None else [v.to_data() for v in mapped],
            'j_invariant_preserved':curve_invariants(curve)['j_invariant']==curve_invariants(target)['j_invariant']}


__all__ += ['extended_euclidean','modular_inverse_euclidean','extension_square_root',
            'field_interpolate','ReedSolomonCode','miller_function','weil_pairing',
            'VeluIsogeny','curve_invariants','curve_scale_isomorphism']


def _polynomial_exact_quotient(left, right):
    quotient,remainder=left.divmod(right)
    if remainder:raise ArithmeticError('Expected an exact finite-field polynomial division')
    return quotient


def square_free_factorization(polynomial):
    """Square-free decomposition over GF(pⁿ), including inseparable p-th powers."""
    if not isinstance(polynomial,FieldPolynomial) or not 0<=polynomial.degree<=128:
        raise ValueError('Nonzero polynomial of degree at most 128 required')
    field=polynomial.field;one=FieldPolynomial(field,[1]);f=polynomial.monic()
    if f.degree==0:return []
    c=f.gcd(f.derivative());w=_polynomial_exact_quotient(f,c);i=1;result=[]
    while w!=one:
        y=w.gcd(c);factor=_polynomial_exact_quotient(w,y)
        if factor.degree>0:result.append((factor,i))
        w=y;c=_polynomial_exact_quotient(c,y);i+=1
        if i>polynomial.degree+1:raise ArithmeticError('Square-free decomposition did not decrease degree')
    if c!=one:
        p=field.p
        if any(coefficient and index%p for index,coefficient in enumerate(c.coefficients)):
            raise ArithmeticError('Inseparable polynomial contains a non-p-divisible exponent')
        root=FieldPolynomial(field,[c.coefficients[index]**(field.order//p) for index in range(0,len(c.coefficients),p)])
        for factor,multiplicity in square_free_factorization(root):result.append((factor,multiplicity*p))
    reconstructed=one
    for factor,multiplicity in result:
        for _ in range(multiplicity):reconstructed=reconstructed*factor
    if reconstructed!=f:raise ArithmeticError('Square-free decomposition reconstruction failed')
    return result


def distinct_degree_factorization(polynomial):
    """Group square-free factors by irreducible degree using Frobenius gcds."""
    if not isinstance(polynomial,FieldPolynomial) or not 1<=polynomial.degree<=128 or not polynomial.square_free():
        raise ValueError('Square-free polynomial of degree 1–128 required')
    field=polynomial.field;remaining=polynomial.monic();x=FieldPolynomial(field,[0,1]);power=x%remaining
    degree=1;result=[]
    while remaining.degree>=2*degree:
        power=power.powmod(field.order,remaining)
        factor=(power-x).gcd(remaining)
        if factor.degree>0:
            result.append((factor,degree));remaining=_polynomial_exact_quotient(remaining,factor)
            if remaining.degree>0:power=power%remaining
        degree+=1
    if remaining.degree>0:result.append((remaining,remaining.degree))
    return result


def equal_degree_factorization(polynomial, degree, *, seed=0, attempts=256):
    """Cantor–Zassenhaus splitting, with trace splitting in characteristic two."""
    import random
    if not isinstance(polynomial,FieldPolynomial) or type(degree) is not int or not 1<=degree<=polynomial.degree<=128 or polynomial.degree%degree:
        raise ValueError('Polynomial degree must be a positive multiple of factor degree')
    if type(seed) is not int or not 0<=seed<2**64 or type(attempts) is not int or not 1<=attempts<=10000:
        raise ValueError('Invalid deterministic factor splitting budget/seed')
    field=polynomial.field;rng=random.Random(seed);pending=[polynomial.monic()];result=[];work=0
    while pending:
        factor=pending.pop()
        if factor.degree==degree:
            if not factor.is_irreducible():raise ValueError('Input is not a product of irreducibles of the declared degree')
            result.append(factor);continue
        split=None
        while work<attempts and split is None:
            work+=1
            candidate=FieldPolynomial(field,[field.element([rng.randrange(field.p) for _ in range(field.degree)]) for _ in range(factor.degree)])
            common=candidate.gcd(factor)
            if 0<common.degree<factor.degree:split=common;break
            if field.p==2:
                trace=FieldPolynomial(field,[0]);power=candidate%factor
                for _ in range(field.degree*degree):
                    trace=(trace+power)%factor;power=power.powmod(2,factor)
                common=trace.gcd(factor)
            else:common=(candidate.powmod((field.order**degree-1)//2,factor)-1).gcd(factor)
            if 0<common.degree<factor.degree:split=common
        if split is None:raise ArithmeticError('Equal-degree splitting budget exhausted without complete factorization')
        pending.extend((split,_polynomial_exact_quotient(factor,split)))
    return sorted(result,key=lambda f:repr(f.to_data()))


def factor_field_polynomial(polynomial, *, seed=0, attempts=256):
    """Complete bounded factorization over the supplied finite extension field."""
    if not isinstance(polynomial,FieldPolynomial) or polynomial.degree<0:raise ValueError('Nonzero finite-field polynomial required')
    unit=polynomial.leading;factors=[]
    for squarefree,multiplicity in square_free_factorization(polynomial):
        for block,degree in distinct_degree_factorization(squarefree):
            factors.extend((factor,multiplicity) for factor in equal_degree_factorization(block,degree,seed=seed,attempts=attempts))
    reconstruction=FieldPolynomial(polynomial.field,[unit])
    for factor,multiplicity in factors:
        for _ in range(multiplicity):reconstruction=reconstruction*factor
    if reconstruction!=polynomial:raise ArithmeticError('Finite-field factorization failed exact reconstruction')
    return {'unit':unit.to_data(),'factors':[{'coefficients':factor.to_data(),'multiplicity':multiplicity}
                                          for factor,multiplicity in factors],
            'reconstruction_verified':True,'seed':seed}


def number_theoretic_transform(values, prime, *, inverse=False, root=None):
    """Vectorized radix-two NTT with exact int64 modular products, p<2^31.

    The prime must admit a primitive n-th root of unity. Multiplication of two
    canonical residues fits signed int64 under the prime bound, so NumPy does
    not silently overflow before modular reduction. This is research arithmetic,
    not a constant-time implementation of a post-quantum encryption scheme.
    """
    import numpy as np
    if type(prime) is not int or not 2<=prime<2**31 or not sympy().isprime(prime):
        raise ValueError('Prime below 2^31 required for exact int64 NTT')
    if not isinstance(values,(list,tuple)) or not 1<=len(values)<=65536 or len(values)&(len(values)-1):
        raise ValueError('NTT length must be a power of two up to 65536')
    if any(type(v) is not int or abs(v).bit_length()>4096 for v in values):raise ValueError('Bounded integer transform coefficients required')
    n=len(values)
    if (prime-1)%n:raise ValueError('Transform length must divide p-1')
    if type(inverse) is not bool:raise ValueError('inverse must be boolean')
    root=pow(int(sympy().primitive_root(prime)),(prime-1)//n,prime) if root is None else root
    if type(root) is not int or not 0<root<prime or pow(root,n,prime)!=1 or (n>1 and pow(root,n//2,prime)==1):
        raise ValueError('Root does not have the required exact power-of-two order')
    if inverse:root=pow(root,-1,prime)
    width=n.bit_length()-1
    permutation=[int(f'{i:0{width}b}'[::-1],2) if width else 0 for i in range(n)]
    array=np.asarray([values[i]%prime for i in permutation],dtype=np.int64)
    length=2
    while length<=n:
        step=pow(root,n//length,prime)
        powers=np.asarray([pow(step,j,prime) for j in range(length//2)],dtype=np.int64)
        blocks=array.reshape(-1,length);left=blocks[:,:length//2].copy()
        right=(blocks[:,length//2:]*powers)%prime
        blocks[:,:length//2]=(left+right)%prime;blocks[:,length//2:]=(left-right)%prime
        length*=2
    if inverse:array=(array*pow(n,-1,prime))%prime
    return {'values':[int(v) for v in array],'prime':prime,'inverse':inverse,
            'arithmetic':'Exact modular int64 within the declared prime bound'}


def negacyclic_convolution(left, right, prime):
    """Polynomial product modulo x^n+1 using a twisted NTT of length n."""
    if not isinstance(left,(list,tuple)) or not isinstance(right,(list,tuple)) or len(left)!=len(right):
        raise ValueError('Equal-length coefficient vectors required')
    n=len(left)
    if not n or n&(n-1) or n>65536 or type(prime) is not int or not 2<=prime<2**31 or not sympy().isprime(prime) or (prime-1)%(2*n):
        raise ValueError('Power-of-two n and prime p with 2n dividing p-1 required')
    if any(type(v) is not int for v in list(left)+list(right)):raise ValueError('Integer polynomial coefficients required')
    generator=int(sympy().primitive_root(prime));twist=pow(generator,(prime-1)//(2*n),prime)
    powers=[pow(twist,i,prime) for i in range(n)]
    a=number_theoretic_transform([(v%prime)*p%prime for v,p in zip(left,powers)],prime,root=twist*twist%prime)['values']
    b=number_theoretic_transform([(v%prime)*p%prime for v,p in zip(right,powers)],prime,root=twist*twist%prime)['values']
    product=number_theoretic_transform([x*y%prime for x,y in zip(a,b)],prime,inverse=True,root=twist*twist%prime)['values']
    result=[v*pow(p,-1,prime)%prime for v,p in zip(product,powers)]
    return {'coefficients':result,'modulus':prime,'polynomial_modulus':'x^'+str(n)+'+1',
            'scope':'Exact negacyclic ring arithmetic; not an encryption or signature protocol'}


__all__ += ['square_free_factorization','distinct_degree_factorization',
            'equal_degree_factorization','factor_field_polynomial',
            'number_theoretic_transform','negacyclic_convolution']


def algebra_field_factorization(p, modulus, coefficients, seed=0):
    field=GaloisField(p,tuple(modulus))
    return factor_field_polynomial(FieldPolynomial(field,coefficients),seed=seed)


def algebra_reed_solomon(p, modulus, nodes, message_length, values, kind='encode', errors=None):
    field=GaloisField(p,tuple(modulus));code=ReedSolomonCode(field,nodes,message_length)
    if kind=='encode':return {'codeword':code.encode(values),'correction_radius':code.correction_radius}
    if kind=='decode':return code.decode(values,errors)
    if kind=='syndrome':return code.syndrome(values)
    raise ValueError('Reed–Solomon operation is encode, decode or syndrome')


class PrimeFieldLinearAlgebra:
    """Vectorized exact modular elimination with explicit overflow-safe products.

    p<2^31 bounds each int64 residue product below 2^62. Matrix products reduce
    after every rank-one update; ordinary NumPy matmul would sum enough such
    products to overflow and is deliberately not used for certificate checking.
    """
    def __init__(self, prime):
        if type(prime) is not int or not 2<=prime<2**31 or not sympy().isprime(prime):
            raise ValueError('Prime below 2^31 required')
        self.prime=prime

    def _matrix(self, matrix):
        import numpy as np
        if not isinstance(matrix,(list,tuple)) or not 1<=len(matrix)<=256 or any(not isinstance(row,(list,tuple)) for row in matrix):
            raise ValueError('Bounded matrix rows required')
        width=len(matrix[0])
        if not 1<=width<=256 or any(len(row)!=width for row in matrix):raise ValueError('Bounded rectangular matrix required')
        if any(type(v) is not int or abs(v).bit_length()>4096 for row in matrix for v in row):
            raise ValueError('Bounded integer matrix entries required')
        return np.asarray([[v%self.prime for v in row] for row in matrix],dtype=np.int64)

    def multiply(self, left, right):
        import numpy as np
        a=self._matrix(left);b=self._matrix(right)
        if a.shape[1]!=b.shape[0]:raise ValueError('Modular matrix multiplication dimensions differ')
        output=np.zeros((len(a),b.shape[1]),dtype=np.int64)
        for k in range(a.shape[1]):output=(output+a[:,k,None]*b[k,None,:])%self.prime
        return output.tolist()

    def rref(self, matrix, *, certificate=True):
        import numpy as np
        if type(certificate) is not bool:raise ValueError('certificate must be boolean')
        original=self._matrix(matrix);a=original.copy();rows,columns=a.shape
        transform=np.eye(rows,dtype=np.int64);pivots=[];pivot_row=0;determinant=1
        for column in range(columns):
            choices=np.flatnonzero(a[pivot_row:,column])
            if not len(choices):continue
            pivot=pivot_row+int(choices[0])
            if pivot!=pivot_row:
                a[[pivot,pivot_row]]=a[[pivot_row,pivot]];transform[[pivot,pivot_row]]=transform[[pivot_row,pivot]]
                determinant=-determinant%self.prime
            divisor=int(a[pivot_row,column]);determinant=determinant*divisor%self.prime
            inverse=pow(divisor,-1,self.prime)
            a[pivot_row]=(a[pivot_row]*inverse)%self.prime;transform[pivot_row]=(transform[pivot_row]*inverse)%self.prime
            factors=a[:,column].copy();factors[pivot_row]=0
            a=(a-factors[:,None]*a[pivot_row])%self.prime
            transform=(transform-factors[:,None]*transform[pivot_row])%self.prime
            pivots.append(column);pivot_row+=1
            if pivot_row==rows:break
        determinant=determinant if rows==columns and len(pivots)==rows else 0 if rows==columns else None
        result={'rref':a.tolist(),'rank':len(pivots),'pivots':pivots,'prime':self.prime,'determinant':determinant}
        if certificate:
            result['row_transform']=transform.tolist()
            result['transform_verified']=self.multiply(result['row_transform'],original.tolist())==result['rref']
            if not result['transform_verified']:raise ArithmeticError('Exact modular row-transform certificate failed')
        return result

    def inverse(self, matrix):
        import numpy as np
        a=self._matrix(matrix)
        if a.shape[0]!=a.shape[1]:raise ValueError('Square modular matrix required')
        result=self.rref(matrix)
        if result['rank']!=len(a):raise ZeroDivisionError('Singular modular matrix')
        inverse=result['row_transform']
        if self.multiply(matrix,inverse)!=np.eye(len(a),dtype=int).tolist():raise ArithmeticError('Modular inverse verification failed')
        return {'inverse':inverse,'determinant':result['determinant'],'prime':self.prime}

    def nullspace(self, matrix):
        result=self.rref(matrix,certificate=False);rows=result['rref'];pivots=result['pivots'];columns=len(rows[0]);basis=[]
        for free in range(columns):
            if free in pivots:continue
            vector=[0]*columns;vector[free]=1
            for row,pivot in enumerate(pivots):vector[pivot]=-rows[row][free]%self.prime
            basis.append(vector)
        if basis:
            transposed=[list(row) for row in zip(*basis)]
            if any(any(row) for row in self.multiply(matrix,transposed)):raise ArithmeticError('Modular nullspace certificate failed')
        return {'basis':basis,'nullity':len(basis),'rank':result['rank'],'prime':self.prime}


def chinese_remainder_system(residues, moduli):
    """Generalized CRT, including compatible noncoprime moduli."""
    if not isinstance(residues,(list,tuple)) or not 1<=len(residues)<=256 or len(residues)!=len(moduli):
        raise ValueError('1–256 residue/modulus pairs required')
    if any(type(v) is not int or abs(v).bit_length()>4096 for v in list(residues)+list(moduli)) or any(v<1 for v in moduli):
        raise ValueError('Bounded integer residues and positive moduli required')
    value=0;modulus=1
    for index,(residue,current) in enumerate(zip(residues,moduli)):
        common=gcd(modulus,current);difference=residue-value
        if difference%common:return {'consistent':False,'conflict_index':index,'common_divisor':common}
        reduced=current//common
        multiplier=(difference//common)*pow(modulus//common,-1,reduced)%reduced
        value+=modulus*multiplier;modulus*=reduced;value%=modulus
        if modulus.bit_length()>16384:raise ValueError('Combined CRT modulus exceeds arithmetic budget')
    if any(value%m!=r%m for r,m in zip(residues,moduli)):raise ArithmeticError('CRT reconstruction verification failed')
    return {'consistent':True,'residue':value,'modulus':modulus,'verified':True}


def rational_reconstruction(residue, modulus, numerator_bound, denominator_bound):
    """Unique bounded rational reconstruction when 2*N*D < modulus."""
    if any(type(v) is not int or abs(v).bit_length()>4096 for v in (residue,modulus,numerator_bound,denominator_bound)):
        raise ValueError('Bounded integer reconstruction parameters required')
    if modulus<=1 or numerator_bound<0 or denominator_bound<1 or 2*numerator_bound*denominator_bound>=modulus:
        raise ValueError('Uniqueness requires modulus>1, N>=0, D>=1 and 2ND<modulus')
    residue%=modulus
    if residue==0:return {'found':True,'numerator':0,'denominator':1}
    old_r,r=modulus,residue;old_t,t=0,1
    while abs(r)>numerator_bound:
        if r==0:return {'found':False,'numerator':None,'denominator':None}
        quotient=old_r//r;old_r,r=r,old_r-quotient*r;old_t,t=t,old_t-quotient*t
    numerator,denominator=r,t
    if denominator<0:numerator,denominator=-numerator,-denominator
    valid=(1<=denominator<=denominator_bound and abs(numerator)<=numerator_bound
           and gcd(abs(numerator),denominator)==1 and gcd(denominator,modulus)==1
           and (residue*denominator-numerator)%modulus==0)
    return {'found':valid,'numerator':numerator if valid else None,'denominator':denominator if valid else None,
            'unique_under_declared_bounds':True}


class IntegerLattice:
    """Exact rational Gram–Schmidt, LLL reduction and Babai nearest plane.

    These are bounded research algorithms. LLL certifies its reduction
    inequalities and unimodular basis change; Babai returns an approximate
    closest lattice point, not a proof of globally minimal Euclidean distance.
    """
    def __init__(self, basis):
        from fractions import Fraction
        if not isinstance(basis,(list,tuple)) or not 1<=len(basis)<=16 or not basis[0] or not len(basis)<=len(basis[0])<=32:
            raise ValueError('Full-row-rank integer basis with 1–16 vectors in dimension <=32 required')
        width=len(basis[0])
        if any(len(row)!=width or any(type(v) is not int or abs(v).bit_length()>256 for v in row) for row in basis):
            raise ValueError('Bounded rectangular integer lattice basis required')
        self.basis=tuple(tuple(row) for row in basis)
        self.gram_schmidt()

    @staticmethod
    def _nearest(value):
        from fractions import Fraction
        value=Fraction(value)
        return (2*value.numerator+value.denominator)//(2*value.denominator)

    def gram_schmidt(self, basis=None):
        from fractions import Fraction
        rows=self.basis if basis is None else basis;n=len(rows);orthogonal=[];norms=[];mu=[[Fraction(0) for _ in range(n)] for _ in range(n)]
        for i,row in enumerate(rows):
            vector=list(map(Fraction,row))
            for j,prior in enumerate(orthogonal):
                coefficient=sum(Fraction(a)*b for a,b in zip(row,prior))/norms[j];mu[i][j]=coefficient
                vector=[a-coefficient*b for a,b in zip(vector,prior)]
            norm=sum(v*v for v in vector)
            if norm==0:raise ValueError('Lattice basis is linearly dependent')
            orthogonal.append(vector);norms.append(norm)
        return orthogonal,norms,mu

    def lll(self, delta='3/4', max_iterations=10000):
        from fractions import Fraction
        delta=Fraction(delta)
        if not Fraction(1,4)<delta<1 or type(max_iterations) is not int or not 1<=max_iterations<=100000:
            raise ValueError('LLL needs 1/4<delta<1 and a bounded iteration budget')
        basis=[list(row) for row in self.basis];n=len(basis);transform=[[int(i==j) for j in range(n)] for i in range(n)]
        k=1;iterations=0
        while k<n:
            iterations+=1
            if iterations>max_iterations:raise ArithmeticError('LLL work budget exhausted before reduction completed')
            _,norms,mu=self.gram_schmidt(basis)
            for j in range(k-1,-1,-1):
                coefficient=self._nearest(mu[k][j])
                if coefficient:
                    basis[k]=[a-coefficient*b for a,b in zip(basis[k],basis[j])]
                    transform[k]=[a-coefficient*b for a,b in zip(transform[k],transform[j])]
                    if any(abs(v).bit_length()>4096 for row in basis+transform for v in row):raise ArithmeticError('LLL integer growth budget exceeded')
                    _,norms,mu=self.gram_schmidt(basis)
            if norms[k]>=(delta-mu[k][k-1]**2)*norms[k-1]:k+=1
            else:
                basis[k],basis[k-1]=basis[k-1],basis[k];transform[k],transform[k-1]=transform[k-1],transform[k];k=max(1,k-1)
        _,norms,mu=self.gram_schmidt(basis)
        size_reduced=all(abs(mu[i][j])<=Fraction(1,2) for i in range(n) for j in range(i))
        lovasz=all(norms[i]>=(delta-mu[i][i-1]**2)*norms[i-1] for i in range(1,n))
        sp=sympy();matrix=sp.Matrix(transform)
        verified=matrix*sp.Matrix(self.basis)==sp.Matrix(basis) and abs(matrix.det())==1
        if not size_reduced or not lovasz or not verified:raise ArithmeticError('LLL exact reduction certificate failed')
        return {'basis':basis,'unimodular_transform':transform,'delta':str(delta),'iterations':iterations,
                'size_reduced':size_reduced,'lovasz_verified':lovasz,'basis_change_verified':bool(verified),
                'gram_schmidt_squared_norms':list(map(str,norms))}

    def babai(self, target):
        from fractions import Fraction
        if not isinstance(target,(list,tuple)) or len(target)!=len(self.basis[0]):raise ValueError('Target dimension differs from lattice')
        residual=[Fraction(v) for v in target]
        if any(max(v.numerator.bit_length(),v.denominator.bit_length())>4096 for v in residual):raise ValueError('Target arithmetic budget exceeded')
        orthogonal,norms,_=self.gram_schmidt();coefficients=[0]*len(self.basis)
        for i in range(len(self.basis)-1,-1,-1):
            coefficient=self._nearest(sum(a*b for a,b in zip(residual,orthogonal[i]))/norms[i]);coefficients[i]=coefficient
            residual=[a-coefficient*b for a,b in zip(residual,self.basis[i])]
        point=[sum(coefficients[i]*self.basis[i][j] for i in range(len(self.basis))) for j in range(len(self.basis[0]))]
        return {'point':point,'basis_coefficients':coefficients,'squared_distance':str(sum(v*v for v in residual)),
                'scope':'Babai nearest-plane approximation; closest-vector optimality not certified'}


__all__ += ['PrimeFieldLinearAlgebra','chinese_remainder_system','rational_reconstruction','IntegerLattice']


def hensel_lift_root(coefficients, prime, root, precision):
    """Newton–Hensel lift of a simple root to modulus p^precision."""
    if not isinstance(coefficients,(list,tuple)) or not 1<=len(coefficients)<=65 or any(type(v) is not int or abs(v).bit_length()>4096 for v in coefficients):
        raise ValueError('Bounded integer polynomial coefficients required')
    if type(prime) is not int or not 2<=prime<2**31 or not sympy().isprime(prime) or type(precision) is not int or not 1<=precision<=128:
        raise ValueError('Prime below 2^31 and p-adic precision 1–128 required')
    if type(root) is not int:raise ValueError('Integer initial residue required')
    def evaluate(x,modulus):
        value=0
        for coefficient in reversed(coefficients):value=(value*x+coefficient)%modulus
        return value
    derivative=[i*coefficients[i] for i in range(1,len(coefficients))]
    def slope(x,modulus):
        value=0
        for coefficient in reversed(derivative):value=(value*x+coefficient)%modulus
        return value
    root%=prime
    if evaluate(root,prime)!=0 or slope(root,prime)==0:raise ValueError('Initial residue must be a simple polynomial root modulo p')
    digits=1;history=[{'precision':1,'root':root}]
    while digits<precision:
        digits=min(2*digits,precision);modulus=prime**digits
        root=(root-evaluate(root,modulus)*pow(slope(root,modulus),-1,modulus))%modulus
        if evaluate(root,modulus)!=0:raise ArithmeticError('Newton–Hensel root verification failed')
        history.append({'precision':digits,'root':root})
    return {'root':root,'modulus':prime**precision,'precision':precision,'history':history,
            'scope':'Unique lift of this simple residue root, not all roots of the p-adic polynomial'}


@dataclass(frozen=True)
class PadicInteger:
    """A residue in Z/p^N Z with honest finite-precision valuation semantics."""
    prime: int
    precision: int
    residue: int

    def __post_init__(self):
        if type(self.prime) is not int or not 2<=self.prime<2**31 or not sympy().isprime(self.prime):raise ValueError('Prime below 2^31 required')
        if type(self.precision) is not int or not 1<=self.precision<=128:raise ValueError('P-adic precision must be 1–128 digits')
        if type(self.residue) is not int or abs(self.residue).bit_length()>16384:raise ValueError('Bounded integer p-adic residue required')
        object.__setattr__(self,'residue',self.residue%self.modulus)

    @property
    def modulus(self):return self.prime**self.precision

    def _coerce(self, other):
        if type(other) is int:return PadicInteger(self.prime,self.precision,other)
        if not isinstance(other,PadicInteger) or other.prime!=self.prime:raise ValueError('P-adic characteristics differ')
        return other

    def __add__(self, other):
        other=self._coerce(other)
        return PadicInteger(self.prime,min(self.precision,other.precision),self.residue+other.residue)

    __radd__=__add__

    def __neg__(self):return PadicInteger(self.prime,self.precision,-self.residue)

    def __sub__(self, other):return self+-self._coerce(other)

    def __mul__(self, other):
        other=self._coerce(other)
        return PadicInteger(self.prime,min(self.precision,other.precision),self.residue*other.residue)

    __rmul__=__mul__

    def inverse(self):
        if self.residue%self.prime==0:raise ZeroDivisionError('Only p-adic units are invertible in Z/p^N Z')
        return PadicInteger(self.prime,self.precision,pow(self.residue,-1,self.modulus))

    def __truediv__(self, other):return self*self._coerce(other).inverse()

    def __pow__(self, exponent):
        if type(exponent) is not int or abs(exponent).bit_length()>4096:raise ValueError('Bounded integer p-adic exponent required')
        if exponent<0:return self.inverse()**(-exponent)
        return PadicInteger(self.prime,self.precision,pow(self.residue,exponent,self.modulus))

    def valuation(self):
        value=self.residue;valuation=0
        if value==0:return {'value':self.precision,'is_lower_bound':True}
        while value%self.prime==0:value//=self.prime;valuation+=1
        return {'value':valuation,'is_lower_bound':False}

    def digits(self):
        value=self.residue;digits=[]
        for _ in range(self.precision):digits.append(value%self.prime);value//=self.prime
        return digits

    def truncate(self, precision):
        if type(precision) is not int or not 1<=precision<=self.precision:raise ValueError('Truncation cannot invent unknown p-adic digits')
        return PadicInteger(self.prime,precision,self.residue)

    def congruent(self, other, precision=None):
        other=self._coerce(other);known=min(self.precision,other.precision)
        precision=known if precision is None else precision
        if type(precision) is not int or not 1<=precision<=known:raise ValueError('Congruence precision exceeds known digits')
        return (self.residue-other.residue)%self.prime**precision==0

    def teichmuller(self):
        value=self.residue%self.prime
        for _ in range(self.precision+1):
            next_value=pow(value,self.prime,self.modulus)
            if next_value==value:
                return PadicInteger(self.prime,self.precision,value)
            value=next_value
        raise ArithmeticError('Teichmuller iteration did not reach its finite-precision fixed point')

    def _divide_integer_term(self, numerator, denominator):
        valuation=0
        while denominator%self.prime==0:denominator//=self.prime;valuation+=1
        divisor=self.prime**valuation
        if numerator%divisor:raise ArithmeticError('Series term has a nonintegral p-adic denominator')
        return (numerator//divisor)*pow(denominator,-1,self.modulus)%self.modulus

    def logarithm(self):
        if (self.residue-1)%self.prime!=0:raise ValueError('P-adic logarithm requires x in 1+p Z_p')
        z=self.residue-1;total=0;cutoff=2*self.precision+8
        for n in range(1,cutoff):
            denominator=n;valuation=0
            while denominator%self.prime==0:denominator//=self.prime;valuation+=1
            numerator=pow(z,n,self.modulus*self.prime**valuation)
            term=self._divide_integer_term(numerator,n)
            total=(total+term if n%2 else total-term)%self.modulus
        return PadicInteger(self.prime,self.precision,total)

    def exponential(self):
        minimum=2 if self.prime==2 else 1
        if self.residue%self.prime**minimum!=0:raise ValueError('P-adic exponential requires pZ_p, or 4Z_2 at p=2')
        total=1;factorial=1;cutoff=2*self.precision+4
        for n in range(1,cutoff):
            factorial*=n;denominator=factorial;valuation=0
            while denominator%self.prime==0:denominator//=self.prime;valuation+=1
            numerator=pow(self.residue,n,self.modulus*self.prime**valuation)
            total=(total+self._divide_integer_term(numerator,factorial))%self.modulus
        return PadicInteger(self.prime,self.precision,total)

    def to_data(self):
        return {'prime':self.prime,'precision':self.precision,'residue':self.residue,
                'digits':self.digits(),'valuation':self.valuation(),
                'scope':'Finite precision Z/p^N Z; zero residue does not prove an exact p-adic zero'}


__all__ += ['hensel_lift_root','PadicInteger']


def batch_field_inverse(field, values, *, allow_zero=False):
    """Montgomery batch inversion with one field inverse and linear products."""
    if not isinstance(field,GaloisField) or not isinstance(values,(list,tuple)) or not 1<=len(values)<=4096 or type(allow_zero) is not bool:
        raise ValueError('Finite field, 1–4096 values and boolean zero policy required')
    elements=[field.element(v) for v in values]
    if not allow_zero and any(not v for v in elements):raise ZeroDivisionError('Batch includes a noninvertible zero')
    prefixes=[];product_value=field.element(1)
    for value in elements:
        prefixes.append(product_value)
        if value:product_value=product_value*value
    inverse=product_value.inverse();result=[None]*len(elements)
    for index in range(len(elements)-1,-1,-1):
        value=elements[index]
        if value:
            result[index]=inverse*prefixes[index];inverse=inverse*value
            if result[index]*value!=field.element(1):raise ArithmeticError('Batch inverse verification failed')
    return {'inverses':[None if value is None else value.to_data() for value in result],
            'zero_positions':[i for i,value in enumerate(elements) if not value],
            'field_inversions':1,'timing':'Variable-time research arithmetic'}


__all__ += ['batch_field_inverse']


class ShamirSecretSharing:
    """Exact polynomial threshold sharing over a bounded finite field.

    Randomness is supplied as explicit coefficients so experiments can be
    reproduced. This educational interface does not generate cryptographic
    randomness, authenticate shares, or implement verifiable secret sharing.
    Never derive secret coefficients from a public experiment seed.
    """

    def __init__(self, field, threshold):
        if not isinstance(field, GaloisField):
            raise ValueError('Finite field required')
        if type(threshold) is not int or not 2 <= threshold <= 64:
            raise ValueError('Threshold must be between 2 and 64')
        if threshold >= field.order:
            raise ValueError('Field must contain enough distinct nonzero abscissae')
        self.field = field
        self.threshold = threshold

    def split(self, secret, coefficients, abscissae):
        if not isinstance(coefficients, (list, tuple)) or len(coefficients) != self.threshold-1:
            raise ValueError('Supply exactly threshold minus one random coefficients')
        if not isinstance(abscissae, (list, tuple)) or not self.threshold <= len(abscissae) <= 256:
            raise ValueError('Share count must be between threshold and 256')
        xs = [self.field.element(x) for x in abscissae]
        if any(not x for x in xs) or len(set(xs)) != len(xs):
            raise ValueError('Share abscissae must be distinct nonzero field elements')
        polynomial = [self.field.element(secret)] + [self.field.element(c) for c in coefficients]
        shares = []
        for x in xs:
            value = self.field.element(0)
            for coefficient in reversed(polynomial):
                value = value*x + coefficient
            shares.append((x, value))
        return tuple(shares)

    def recover(self, shares):
        if not isinstance(shares, (list, tuple)) or not self.threshold <= len(shares) <= 256:
            raise ValueError('At least threshold shares required')
        converted = []
        for item in shares:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError('Each share must be an (abscissa, ordinate) pair')
            converted.append(tuple(self.field.element(value) for value in item))
        xs = [x for x, _ in converted]
        if any(not x for x in xs) or len(set(xs)) != len(xs):
            raise ValueError('Duplicate or zero share abscissa')
        selected = converted[:self.threshold]
        def evaluate(point):
            result = self.field.element(0)
            for i, (xi, yi) in enumerate(selected):
                numerator = self.field.element(1)
                denominator = self.field.element(1)
                for j, (xj, _) in enumerate(selected):
                    if i != j:
                        numerator *= point-xj
                        denominator *= xi-xj
                result += yi*numerator/denominator
            return result
        for x, y in converted[self.threshold:]:
            if evaluate(x) != y:
                raise ValueError('Extra shares are inconsistent with the threshold polynomial')
        return evaluate(self.field.element(0))


__all__ += ['ShamirSecretSharing']


def lagrange_weights_at_zero(field, abscissae):
    """Exact interpolation weights; useful for threshold share recombination."""
    if not isinstance(field, GaloisField):
        raise ValueError('Finite field required')
    if not isinstance(abscissae, (list, tuple)) or not 1 <= len(abscissae) <= 256:
        raise ValueError('1–256 interpolation abscissae required')
    xs = [field.element(x) for x in abscissae]
    if len(set(xs)) != len(xs):
        raise ValueError('Distinct interpolation abscissae required')
    weights = []
    for i, x in enumerate(xs):
        value = field.element(1)
        for j, y in enumerate(xs):
            if i != j:
                value *= -y/(x-y)
        weights.append(value)
    if sum(weights, field.element(0)) != field.element(1):
        raise ArithmeticError('Interpolation partition-of-unity verification failed')
    return tuple(weights)


__all__ += ['lagrange_weights_at_zero']
