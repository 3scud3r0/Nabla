"""Exact invariant projectors and additive semisimple/nilpotent decomposition.

All identities are rational matrix identities with explicit witnesses. No root
finding, floating-point eigensolver, or assumption of rational eigenvalues is
needed. Supplied coprime factors need not be irreducible; consequently projectors
are called invariant projectors, not necessarily primary spectral projectors.
"""
from dataclasses import dataclass
from fractions import Fraction

from .matrices import Matrix,identity
from .exact_spectral import (
    _matrix,_bounded,_add,_scale,_matrix_data,_decode_rational,
    evaluate_matrix_polynomial,minimal_polynomial,
)
from ..polynomials.univariate import Polynomial
from ..polynomials.exact_algebra import (
    polynomial_crt,polynomial_power,QuotientElement,extended_polynomial_gcd,
)
from ..polynomials.real_roots import square_free_decomposition
from ...core.semantic_contracts import canonical_payload
from ...core.semantic_ir import fingerprint

_ONE=Polynomial((1,))
_ZERO=Polynomial((0,))


def _is_zero(matrix):
    return not any(v for row in matrix.rows for v in row)


def _matrix_power(matrix,exponent):
    result=identity(matrix.shape[0])
    base=matrix
    while exponent:
        if exponent&1:
            result=_bounded(result@base)
        exponent >>= 1
        if exponent:
            base=_bounded(base@base)
    return result


@dataclass(frozen=True)
class InvariantProjector:
    factor: Polynomial
    polynomial: Polynomial
    matrix: Matrix
    dimension: int


@dataclass(frozen=True)
class InvariantDecomposition:
    matrix: Matrix
    minimal: Polynomial
    projectors: tuple[InvariantProjector,...]

    def verify(self):
        try:
            _matrix(self.matrix)
            if self.minimal!=minimal_polynomial(self.matrix):
                return False
            if not 1<=len(self.projectors)<=self.matrix.shape[0]:
                return False
            product=_ONE
            total=_scale(identity(self.matrix.shape[0]),0)
            for i,projector in enumerate(self.projectors):
                if (not isinstance(projector.factor,Polynomial) or projector.factor.degree<1
                        or projector.factor.leading!=1 or projector.matrix.shape!=self.matrix.shape):
                    return False
                product=product*projector.factor
                if projector.matrix!=evaluate_matrix_polynomial(projector.polynomial,self.matrix):
                    return False
                if projector.matrix@projector.matrix!=projector.matrix:
                    return False
                if self.matrix@projector.matrix!=projector.matrix@self.matrix:
                    return False
                if not _is_zero(evaluate_matrix_polynomial(projector.factor,self.matrix)@projector.matrix):
                    return False
                # Idempotent trace equals image dimension over Q.
                trace=sum(projector.matrix.rows[j][j] for j in range(self.matrix.shape[0]))
                if type(projector.dimension) is not int or trace!=projector.dimension or not 1<=trace<=self.matrix.shape[0]:
                    return False
                for other in self.projectors[i+1:]:
                    if not _is_zero(projector.matrix@other.matrix) or not _is_zero(other.matrix@projector.matrix):
                        return False
                    if extended_polynomial_gcd(projector.factor,other.factor).gcd!=_ONE:
                        return False
                total=_add(total,projector.matrix)
            return product==self.minimal and total==identity(self.matrix.shape[0])
        except (ValueError,TypeError,AttributeError,ArithmeticError):
            return False

    def split_vector(self,vector):
        """Split a rational vector into components in mutually invariant images."""
        if not self.verify():
            raise ValueError('Invalid invariant decomposition')
        if not isinstance(vector,(tuple,list)) or len(vector)!=self.matrix.shape[0]:
            raise ValueError('Vector must match matrix dimension')
        if any(isinstance(v,bool) or not isinstance(v,(int,Fraction)) for v in vector):
            raise ValueError('Vector coefficients must be exact rationals')
        vector=Matrix(tuple((Fraction(value),) for value in vector))
        _bounded(vector)
        return tuple(tuple(row[0] for row in (projector.matrix@vector).rows) for projector in self.projectors)


def invariant_decomposition(matrix,factors=None):
    """Use polynomial CRT to construct commuting orthogonal invariant projectors.

    By default square-free multiplicity groups of the minimal polynomial provide
    pairwise-coprime factors. Explicit factors must multiply exactly to minimal(A).
    """
    _matrix(matrix)
    minimal=minimal_polynomial(matrix)
    if factors is None:
        factors=tuple(polynomial_power(factor,multiplicity)
                      for factor,multiplicity in square_free_decomposition(minimal)[1])
    if not isinstance(factors,(tuple,list)) or not 1<=len(factors)<=matrix.shape[0]:
        raise ValueError('Finite nonempty coprime factors required')
    product=_ONE
    for factor in factors:
        if not isinstance(factor,Polynomial) or factor.degree<1 or factor.leading!=1:
            raise ValueError('Positive-degree monic factors required')
        product=product*factor
    if product!=minimal:
        raise ValueError('Factors must multiply to the exact minimal polynomial')
    projectors=[]
    for index,factor in enumerate(factors):
        residues=tuple(_ONE if j==index else _ZERO for j in range(len(factors)))
        polynomial,modulus=polynomial_crt(residues,factors)
        if modulus!=minimal:
            raise ArithmeticError('Projector modulus mismatch')
        projection=evaluate_matrix_polynomial(polynomial,matrix)
        trace=sum(projection.rows[i][i] for i in range(matrix.shape[0]))
        if trace.denominator!=1:
            raise ArithmeticError('Nonintegral projector rank')
        projectors.append(InvariantProjector(factor,polynomial,projection,trace.numerator))
    result=InvariantDecomposition(matrix,minimal,tuple(projectors))
    if not result.verify():
        raise ArithmeticError('Invariant projector replay failed')
    return result


def _quotient_evaluate(polynomial,value):
    result=value._coerce(0)
    for coefficient in reversed(polynomial.coefficients):
        result=result*value+coefficient
    return result


@dataclass(frozen=True)
class AdditiveDecomposition:
    matrix: Matrix
    semisimple: Matrix
    nilpotent: Matrix
    semisimple_polynomial: Polynomial
    nilpotency_index: int

    def verify(self):
        """Verify rational identities and square-free minimal polynomial of S.

        Over characteristic zero a matrix with square-free minimal polynomial is
        semisimple over the algebraic closure. It need not diagonalize over Q.
        """
        try:
            _matrix(self.matrix)
            if self.semisimple.shape!=self.matrix.shape or self.nilpotent.shape!=self.matrix.shape:
                return False
            if _add(self.semisimple,self.nilpotent)!=self.matrix:
                return False
            if self.semisimple@self.nilpotent!=self.nilpotent@self.semisimple:
                return False
            if evaluate_matrix_polynomial(self.semisimple_polynomial,self.matrix)!=self.semisimple:
                return False
            minimal=minimal_polynomial(self.semisimple)
            if extended_polynomial_gcd(minimal,minimal.derivative()).gcd!=_ONE:
                return False
            if type(self.nilpotency_index) is not int or not 1<=self.nilpotency_index<=self.matrix.shape[0]:
                return False
            if not _is_zero(_matrix_power(self.nilpotent,self.nilpotency_index)):
                return False
            if self.nilpotency_index>1 and _is_zero(_matrix_power(self.nilpotent,self.nilpotency_index-1)):
                return False
            return True
        except (ValueError,TypeError,AttributeError,ArithmeticError):
            return False

    def to_data(self):
        body={'schema_version':1,'matrix':_matrix_data(self.matrix),
              'semisimple':_matrix_data(self.semisimple),'nilpotent':_matrix_data(self.nilpotent),
              'semisimple_polynomial':[str(v) for v in self.semisimple_polynomial.coefficients],
              'nilpotency_index':self.nilpotency_index,'formal_proof':False,
              'scope':'Exact rational additive decomposition; semisimple over algebraic closure; algorithmic replay only'}
        return {**body,'certificate_id':fingerprint(body)}


def additive_decomposition(matrix):
    """Jordan-Chevalley additive decomposition by Newton lifting in Q[x]/minimal.

    For square-free q, Newton iteration replaces x by x-q(x)/q'(x). The error
    doubles its multiplicity order, so at most n bounded iterations suffice.
    """
    _matrix(matrix)
    minimal=minimal_polynomial(matrix)
    square_free=_ONE
    for factor,_ in square_free_decomposition(minimal)[1]:
        square_free=square_free*factor
    current=QuotientElement.generator(minimal)
    for _ in range(matrix.shape[0]+1):
        error=_quotient_evaluate(square_free,current)
        if error.representative.is_zero:
            break
        derivative=_quotient_evaluate(square_free.derivative(),current)
        current=current-error/derivative
    else:
        raise ArithmeticError('Semisimple Newton lifting did not converge within dimension bound')
    semisimple=evaluate_matrix_polynomial(current.representative,matrix)
    nilpotent=_add(matrix,_scale(semisimple,-1))
    power=identity(matrix.shape[0])
    for index in range(1,matrix.shape[0]+1):
        power=_bounded(power@nilpotent)
        if _is_zero(power):
            break
    else:
        raise ArithmeticError('Nilpotent component does not vanish')
    result=AdditiveDecomposition(matrix,semisimple,nilpotent,current.representative,index)
    if not result.verify():
        raise ArithmeticError('Additive decomposition replay failed')
    return result


def verify_additive_decomposition(data):
    try:
        canonical_payload(data)
        if type(data) is not dict or set(data)!={'schema_version','matrix','semisimple','nilpotent','semisimple_polynomial','nilpotency_index','formal_proof','scope','certificate_id'}:
            return False
        if type(data['schema_version']) is not int or data['schema_version']!=1 or data['formal_proof'] is not False:
            return False
        if data['scope']!='Exact rational additive decomposition; semisimple over algebraic closure; algorithmic replay only':
            return False
        if data['certificate_id']!=fingerprint({k:v for k,v in data.items() if k!='certificate_id'}):
            return False
        matrices=[]
        for field in ('matrix','semisimple','nilpotent'):
            rows=data[field]
            if not isinstance(rows,list) or not 1<=len(rows)<=8 or any(not isinstance(row,list) or len(row)!=len(rows) for row in rows):
                return False
            matrices.append(Matrix(tuple(tuple(_decode_rational(v) for v in row) for row in rows)))
        coefficients=data['semisimple_polynomial']
        if not isinstance(coefficients,list) or not 1<=len(coefficients)<=8:
            return False
        values=tuple(_decode_rational(v) for v in coefficients)
        polynomial=Polynomial(values)
        if polynomial.coefficients!=values:
            return False
        return AdditiveDecomposition(*matrices,polynomial,data['nilpotency_index']).verify()
    except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError,RecursionError):
        return False


__all__=['InvariantProjector','InvariantDecomposition','invariant_decomposition',
         'AdditiveDecomposition','additive_decomposition','verify_additive_decomposition']
