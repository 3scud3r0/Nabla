"""Bounded exact rational spectral analysis with independently checked identities.

Rational eigenspaces are computed only for caller-supplied rational eigenvalues.
Irrational and complex spectral decompositions are not inferred. Minimal and
characteristic polynomials apply to every square rational matrix in the budget.
"""
from dataclasses import dataclass
from fractions import Fraction

from .matrices import Matrix,identity
from .solvers import characteristic_polynomial
from ..polynomials.univariate import Polynomial
from ...core.semantic_ir import fingerprint
from ...core.semantic_contracts import canonical_payload


def _matrix(matrix):
    if not isinstance(matrix,Matrix) or matrix.shape[0]!=matrix.shape[1] or matrix.shape[0]>8:
        raise ValueError('Spectral analysis requires square rational matrix dimension <=8')
    if any(max(abs(v.numerator).bit_length(),v.denominator.bit_length())>512 for row in matrix.rows for v in row):
        raise ValueError('Matrix input coefficients exceed 512-bit budget')
    return matrix


def _bounded(matrix):
    if any(max(abs(v.numerator).bit_length(),v.denominator.bit_length())>16384 for row in matrix.rows for v in row):
        raise ValueError('Spectral arithmetic exceeded bit budget')
    return matrix


def _add(left,right):
    if left.shape!=right.shape:
        raise ValueError('Matrix shapes differ')
    return _bounded(Matrix(tuple(tuple(a+b for a,b in zip(lrow,rrow)) for lrow,rrow in zip(left.rows,right.rows))))


def _scale(matrix,value):
    return _bounded(Matrix(tuple(tuple(value*v for v in row) for row in matrix.rows)))


def evaluate_matrix_polynomial(polynomial,matrix):
    """Horner evaluation with exact arithmetic; coefficients are scalar matrices."""
    _matrix(matrix)
    if not isinstance(polynomial,Polynomial) or polynomial.degree>16:
        raise ValueError('Matrix polynomial degree budget exceeded')
    size=matrix.shape[0]
    unit=identity(size)
    current=_scale(unit,0)
    for coefficient in reversed(polynomial.coefficients):
        current=_add(_bounded(current@matrix),_scale(unit,coefficient))
    return current


def _rref(rows):
    data=[list(row) for row in rows]
    if not data or not data[0]:
        raise ValueError('Nonempty rational matrix required')
    pivot_row=0
    pivots=[]
    for column in range(len(data[0])):
        candidate=next((r for r in range(pivot_row,len(data)) if data[r][column]),None)
        if candidate is None:
            continue
        data[pivot_row],data[candidate]=data[candidate],data[pivot_row]
        scale=data[pivot_row][column]
        data[pivot_row]=[v/scale for v in data[pivot_row]]
        for row in range(len(data)):
            if row!=pivot_row and data[row][column]:
                multiple=data[row][column]
                data[row]=[v-multiple*p for v,p in zip(data[row],data[pivot_row])]
        if any(max(abs(v.numerator).bit_length(),v.denominator.bit_length())>16384 for row in data for v in row):
            raise ValueError('Elimination exceeded arithmetic bit budget')
        pivots.append(column)
        pivot_row+=1
        if pivot_row==len(data):
            break
    return tuple(tuple(row) for row in data),tuple(pivots)


def nullspace(matrix):
    """Canonical rational nullspace basis; empty tuple for the zero kernel."""
    if not isinstance(matrix,Matrix) or max(matrix.shape)>64:
        raise ValueError('Nullspace matrix dimensions must be <=64')
    _bounded(matrix)
    reduced,pivots=_rref(matrix.rows)
    free=[column for column in range(matrix.shape[1]) if column not in pivots]
    basis=[]
    for column in free:
        vector=[Fraction()]*matrix.shape[1]
        vector[column]=Fraction(1)
        for row,pivot in enumerate(pivots):
            vector[pivot]=-reduced[row][column]
        basis.append(tuple(vector))
    if any(any(sum(a*b for a,b in zip(row,vector)) for row in matrix.rows) for vector in basis):
        raise ArithmeticError('Nullspace exact replay failed')
    return tuple(basis)


def _flatten(matrix):
    return tuple(v for row in matrix.rows for v in row)


def minimal_polynomial(matrix):
    """First exact linear dependence of I,A,...,A**n (monic and minimal)."""
    _matrix(matrix)
    powers=[identity(matrix.shape[0])]
    for degree in range(1,matrix.shape[0]+1):
        powers.append(_bounded(powers[-1]@matrix))
        columns=tuple(_flatten(power) for power in powers)
        rows=tuple(tuple(column[index] for column in columns) for index in range(len(columns[0])))
        kernel=nullspace(Matrix(rows))
        if kernel:
            vector=kernel[0]
            if not vector[-1]:
                raise ArithmeticError('Earlier power dependence was missed')
            result=Polynomial(tuple(value/vector[-1] for value in vector))
            if any(v for row in evaluate_matrix_polynomial(result,matrix).rows for v in row):
                raise ArithmeticError('Minimal polynomial annihilation failed')
            return result
    raise ArithmeticError('Cayley-Hamilton dependence not found')


def _matrix_data(matrix):
    return [[str(v) for v in row] for row in matrix.rows]


def _poly_data(polynomial):
    return [str(v) for v in polynomial.coefficients]


@dataclass(frozen=True)
class SpectralCertificate:
    matrix: Matrix
    characteristic: Polynomial
    minimal: Polynomial

    def to_data(self):
        payload={'schema_version':1,'matrix':_matrix_data(self.matrix),
                 'characteristic':_poly_data(self.characteristic),'minimal':_poly_data(self.minimal),
                 'formal_proof':False,'scope':'Exact rational matrix identities with independent algorithmic replay'}
        return {**payload,'certificate_id':fingerprint(payload)}


def spectral_certificate(matrix):
    _matrix(matrix)
    result=SpectralCertificate(matrix,Polynomial(characteristic_polynomial(matrix)),minimal_polynomial(matrix))
    if not verify_spectral_certificate(result.to_data()):
        raise ArithmeticError('Spectral certificate replay failed')
    return result


def _decode_rational(text):
    if not isinstance(text,str) or len(text)>6000:
        raise ValueError('Invalid rational encoding')
    result=Fraction(text)
    if str(result)!=text or max(abs(result.numerator).bit_length(),result.denominator.bit_length())>16384:
        raise ValueError('Noncanonical or oversized rational')
    return result


def _decode_polynomial(data):
    if not isinstance(data,list) or not 1<=len(data)<=9:
        raise ValueError('Invalid spectral polynomial')
    values=tuple(_decode_rational(v) for v in data)
    result=Polynomial(values)
    if result.coefficients!=values:
        raise ValueError('Noncanonical spectral polynomial')
    return result


def verify_spectral_certificate(data):
    """Verify characteristic coefficients using n+1 determinant evaluations.

    This checker does not call the Faddeev-LeVerrier producer. The degree-n monic
    polynomial is uniquely determined by n+1 exact evaluations. Minimality is
    checked by independence of I,...,A**(d-1), plus annihilation at degree d.
    """
    try:
        canonical_payload(data)
        if type(data) is not dict or set(data)!={'schema_version','matrix','characteristic','minimal','formal_proof','scope','certificate_id'}:
            return False
        if type(data['schema_version']) is not int or data['schema_version']!=1 or data['formal_proof'] is not False:
            return False
        if data['scope']!='Exact rational matrix identities with independent algorithmic replay':
            return False
        if data['certificate_id']!=fingerprint({k:v for k,v in data.items() if k!='certificate_id'}):
            return False
        rows=data['matrix']
        if not isinstance(rows,list) or not 1<=len(rows)<=8 or any(not isinstance(row,list) or len(row)!=len(rows) for row in rows):
            return False
        matrix=_matrix(Matrix(tuple(tuple(_decode_rational(v) for v in row) for row in rows)))
        characteristic=_decode_polynomial(data['characteristic'])
        minimal=_decode_polynomial(data['minimal'])
        n=matrix.shape[0]
        if characteristic.degree!=n or characteristic.leading!=1 or not 1<=minimal.degree<=n or minimal.leading!=1:
            return False
        unit=identity(n)
        for point in range(n+1):
            shifted=_add(_scale(unit,point),_scale(matrix,-1))
            if characteristic(point)!=shifted.determinant():
                return False
        if any(v for row in evaluate_matrix_polynomial(characteristic,matrix).rows for v in row):
            return False
        if any(v for row in evaluate_matrix_polynomial(minimal,matrix).rows for v in row):
            return False
        powers=[unit]
        for _ in range(1,minimal.degree):
            powers.append(_bounded(powers[-1]@matrix))
        flattened=tuple(_flatten(power) for power in powers)
        power_rows=tuple(tuple(column[index] for column in flattened) for index in range(n*n))
        if nullspace(Matrix(power_rows)):
            return False
        _,remainder=characteristic.divmod(minimal)
        return remainder.is_zero
    except (ValueError,TypeError,KeyError,AttributeError,ArithmeticError,RecursionError):
        return False


def _eigenvalue(value):
    if isinstance(value,bool) or not isinstance(value,(int,Fraction)):
        raise ValueError('Exact rational eigenvalue required')
    value=Fraction(value)
    if max(abs(value.numerator).bit_length(),value.denominator.bit_length())>512:
        raise ValueError('Eigenvalue bit budget exceeded')
    return value


def generalized_eigenspace(matrix,eigenvalue,*,order=1):
    """Canonical basis of ker((A-lambda I)**order), order<=matrix dimension."""
    _matrix(matrix)
    eigenvalue=_eigenvalue(eigenvalue)
    if type(order) is not int or not 1<=order<=matrix.shape[0]:
        raise ValueError('Generalized eigenspace order must be in [1,n]')
    shifted=_add(matrix,_scale(identity(matrix.shape[0]),-eigenvalue))
    power=identity(matrix.shape[0])
    for _ in range(order):
        power=_bounded(power@shifted)
    return nullspace(power)


def eigenvalue_multiplicity(matrix,eigenvalue):
    _matrix(matrix)
    eigenvalue=_eigenvalue(eigenvalue)
    polynomial=Polynomial(characteristic_polynomial(matrix))
    factor=Polynomial((-eigenvalue,1))
    multiplicity=0
    while polynomial.degree>0:
        quotient,remainder=polynomial.divmod(factor)
        if not remainder.is_zero:
            break
        polynomial=quotient
        multiplicity+=1
    return multiplicity


@dataclass(frozen=True)
class RationalDiagonalization:
    basis: Matrix
    diagonal: Matrix
    inverse_basis: Matrix

    def verify(self,matrix):
        try:
            _matrix(matrix)
            n=matrix.shape[0]
            if any(m.shape!=(n,n) for m in (self.basis,self.diagonal,self.inverse_basis)):
                return False
            if any(self.diagonal.rows[i][j] for i in range(n) for j in range(n) if i!=j):
                return False
            return (self.basis@self.inverse_basis==identity(n)
                    and self.inverse_basis@self.basis==identity(n)
                    and matrix@self.basis==self.basis@self.diagonal)
        except (ValueError,TypeError,AttributeError,ArithmeticError):
            return False


def rational_diagonalization(matrix,eigenvalues):
    """Construct an exact diagonalization from a complete supplied rational spectrum.

    Defective matrices and incomplete/nonrational spectra are explicitly rejected.
    The returned basis is deterministic for a given matrix and value set.
    """
    _matrix(matrix)
    if not isinstance(eigenvalues,(list,tuple)) or not 1<=len(eigenvalues)<=matrix.shape[0]:
        raise ValueError('Finite rational spectrum required')
    values=sorted(set(_eigenvalue(value) for value in eigenvalues))
    basis=[]
    diagonal=[]
    for value in values:
        vectors=generalized_eigenspace(matrix,value)
        if not vectors:
            raise ValueError('Supplied value is not an eigenvalue')
        basis.extend(vectors)
        diagonal.extend([value]*len(vectors))
    n=matrix.shape[0]
    if len(basis)!=n:
        raise ValueError('Spectrum is incomplete or matrix is not rationally diagonalizable')
    basis_matrix=Matrix(tuple(tuple(column[row] for column in basis) for row in range(n)))
    diagonal_matrix=Matrix(tuple(tuple(diagonal[i] if i==j else Fraction() for j in range(n)) for i in range(n)))
    result=RationalDiagonalization(basis_matrix,diagonal_matrix,basis_matrix.inverse())
    if not result.verify(matrix):
        raise ArithmeticError('Diagonalization identity replay failed')
    return result


__all__=['SpectralCertificate','spectral_certificate','verify_spectral_certificate',
         'evaluate_matrix_polynomial','minimal_polynomial','nullspace','generalized_eigenspace',
         'eigenvalue_multiplicity','RationalDiagonalization','rational_diagonalization']
