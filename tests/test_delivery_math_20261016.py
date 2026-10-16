"""Exact mathematical certificates, adversarial replay and independent references."""
from dataclasses import replace
from fractions import Fraction as F
import copy
import random

import pytest

from nablamath.math.polynomials.univariate import Polynomial as P
from nablamath.math.polynomials.real_roots import (
    square_free_decomposition, sturm_sequence, count_real_roots, sign_variations,
    cauchy_bound, isolate_real_roots, verify_root_isolation, RootIsolation,
)
from nablamath.math.polynomials.exact_algebra import (
    polynomial_power, extended_polynomial_gcd, QuotientElement,
    polynomial_crt, resultant, discriminant,
)
from nablamath.math.linear_algebra.matrices import Matrix,identity
from nablamath.math.linear_algebra.exact_spectral import (
    minimal_polynomial, spectral_certificate, verify_spectral_certificate,
    evaluate_matrix_polynomial, nullspace, generalized_eigenspace,
    eigenvalue_multiplicity, rational_diagonalization,
)
from nablamath.core.semantic_ir import fingerprint


def rehash(data):
    data['certificate_id']=fingerprint({k:v for k,v in data.items() if k!='certificate_id'})
    return data


@pytest.mark.parametrize('factors',[
    ((P((-1,1)),1),(P((2,1)),2)),
    ((P((0,1)),4),(P((1,0,1)),3)),
    ((P((-2,0,1)),2),(P((-3,0,1)),1)),
    ((P((1,)),1),),
])
def test_square_free_factorization_reconstructs_and_tracks_multiplicity(factors):
    original=P((F(-3,7),))
    for factor,multiplicity in factors:
        original=original*polynomial_power(factor,multiplicity)
    leading,decomposition=square_free_decomposition(original)
    reconstructed=P((leading,))
    for factor,multiplicity in decomposition:
        assert factor.leading==1
        assert extended_polynomial_gcd(factor,factor.derivative()).gcd==P((1,))
        reconstructed=reconstructed*polynomial_power(factor,multiplicity)
    assert reconstructed==original
    for i,(left,_) in enumerate(decomposition):
        for right,_ in decomposition[i+1:]:
            assert extended_polynomial_gcd(left,right).gcd==P((1,))


def test_sturm_counts_repeated_roots_and_rejects_endpoint_ambiguity():
    polynomial=polynomial_power(P((-1,1)),3)*polynomial_power(P((2,1)),2)
    assert count_real_roots(polynomial,-3,3)==2
    assert count_real_roots(polynomial,-3,0)==1
    assert count_real_roots(polynomial,0,3)==1
    assert count_real_roots(polynomial,2,3)==0
    for lower,upper in [(-2,3),(-3,1),(3,-3),(1,1)]:
        with pytest.raises(ValueError):
            count_real_roots(polynomial,lower,upper)


@pytest.mark.parametrize('coefficients,expected',[
    ((-2,0,1),2),((1,0,1),0),((0,0,0,1),1),
    ((0,-1,0,1),3),((1,),0),((-6,11,-6,1),3),
    ((1,0,0,0,1),0),((4,-4,-3,2,1),2),
])
def test_isolator_coverage_width_and_roundtrip(coefficients,expected):
    polynomial=P(coefficients)
    result=isolate_real_roots(polynomial,precision_bits=12)
    assert len(result.intervals)==expected
    assert verify_root_isolation(result.to_data())
    assert RootIsolation.from_data(result.to_data())==result
    assert all(interval.width<=F(1,4096) for interval in result.intervals)
    assert all(count_real_roots(polynomial,i.lower,i.upper)==1 for i in result.intervals)
    assert sum(i.multiplicity for i in result.intervals)<=polynomial.degree or polynomial.degree==0
    assert result==isolate_real_roots(polynomial,precision_bits=12)


def test_isolation_handles_close_roots_without_merging_them():
    left=F(1,3)
    right=left+F(1,2**20)
    result=isolate_real_roots(P((-left,1))*P((-right,1)),precision_bits=24)
    assert len(result.intervals)==2
    assert result.intervals[0].lower<left<result.intervals[0].upper
    assert result.intervals[1].lower<right<result.intervals[1].upper
    assert result.intervals[0].upper<=result.intervals[1].lower


@pytest.mark.parametrize('change',[
    'chain','drop','duplicate','multiplicity','width','variations','proof','scope','float','bool','noncanonical',
])
def test_root_certificate_rejects_rehashed_forgery(change):
    data=isolate_real_roots(P((-2,0,1)),precision_bits=5).to_data()
    if change=='chain':data['sturm_sequence'][-1]=['-1']
    elif change=='drop':data['intervals'].pop();data['distinct_real_roots']=1;data['real_roots_with_multiplicity']=1
    elif change=='duplicate':data['intervals'][1]=copy.deepcopy(data['intervals'][0])
    elif change=='multiplicity':data['intervals'][0]['multiplicity']=2
    elif change=='width':data['intervals'][0]['lower']='-3'
    elif change=='variations':data['intervals'][0]['lower_variations']+=1
    elif change=='proof':data['formal_proof']=True
    elif change=='scope':data['scope']='A theorem checked by Lean'
    elif change=='float':data['intervals'][0]['lower']=-1.5
    elif change=='bool':data['precision_bits']=True
    else:data['polynomial']=['-4/2','0','1']
    assert not verify_root_isolation(rehash(data))
    with pytest.raises(ValueError):RootIsolation.from_data(data)


@pytest.mark.parametrize('kwargs',[{'precision_bits':True},{'precision_bits':129},{'max_nodes':0},{'max_nodes':1}])
def test_root_isolation_budgets_fail_without_partial_certificate(kwargs):
    with pytest.raises(ValueError):
        isolate_real_roots(P((-2,0,1)),**kwargs)


def test_polynomial_input_bounds_and_exact_endpoint_types():
    for polynomial in [P((0,)),P((0,)*33+(1,)),P((2**513,1))]:
        with pytest.raises(ValueError):isolate_real_roots(polynomial)
    for value in [True,.2,'1/2']:
        with pytest.raises(ValueError):sign_variations(sturm_sequence(P((-2,0,1))),value)
    assert cauchy_bound(P((F(-1,3),F(2,5),1)))>=2


@pytest.mark.parametrize('left,right',[
    (P((-1,0,1)),P((-1,1))),
    (P((2,3,1)),P((1,0,1))),
    (P((0,)),P((2,4))),
    (P((0,)),P((0,))),
    (P((F(2,3),F(-1,4),1)),P((3,1))),
])
def test_extended_euclidean_certificates(left,right):
    certificate=extended_polynomial_gcd(left,right)
    assert certificate.verify()
    assert left*certificate.left_multiplier+right*certificate.right_multiplier==certificate.gcd
    if not certificate.gcd.is_zero:
        assert not replace(certificate,left_multiplier=certificate.left_multiplier+P((1,))).verify() or left.is_zero


def test_quotient_sqrt_two_exact_arithmetic_and_unit_witness():
    alpha=QuotientElement.generator(P((-2,0,1)))
    assert (alpha**2).representative==P((2,))
    assert (alpha+1)*(alpha-1)==alpha._coerce(1)
    inverse,certificate=(alpha+1).inverse_with_certificate()
    assert certificate.verify()
    assert inverse==alpha-1
    assert (alpha**-3)*(alpha**3)==alpha._coerce(1)
    assert alpha.trace()==0
    assert alpha.norm()==-2
    assert (alpha+1).norm()==-1
    assert (alpha+F(1,2)).trace()==1


def test_reducible_quotient_rejects_nonunits_without_field_claim():
    alpha=QuotientElement.generator(P((-1,0,1)))
    assert ((alpha-1)*(alpha+1)).representative.is_zero
    with pytest.raises(ZeroDivisionError):
        (alpha-1).inverse()
    assert alpha.inverse()==alpha
    assert alpha.norm()==-1
    with pytest.raises(ValueError):alpha+QuotientElement.generator(P((-2,0,1)))
    for exponent in [True,.2,10001]:
        with pytest.raises(ValueError):alpha**exponent


def test_polynomial_chinese_remainder_replays_every_congruence():
    moduli=(P((-1,1)),P((1,0,1)),P((2,1)))
    residues=(P((3,)),P((1,2)),P((-4,)))
    result,product=polynomial_crt(residues,moduli)
    assert product==moduli[0]*moduli[1]*moduli[2]
    assert result.degree<product.degree
    for residue,modulus in zip(residues,moduli):
        assert result.divmod(modulus)[1]==residue.divmod(modulus)[1]
    with pytest.raises(ValueError,match='coprime'):
        polynomial_crt((P((1,)),P((2,))),(P((-1,1)),P((-1,0,1))))


@pytest.mark.parametrize('polynomial,expected',[
    (P((-2,0,1)),8),(P((1,0,1)),-4),(P((1,-2,1)),0),
    (P((-6,11,-6,1)),4),(P((3,)),1),
])
def test_discriminant_known_values(polynomial,expected):
    assert discriminant(polynomial)==expected


def test_resultant_detects_common_roots_and_obeys_swap_sign():
    left,right=P((1,2,3)),P((-1,0,0,1))
    assert resultant(left,right)==(-1)**(left.degree*right.degree)*resultant(right,left)
    assert resultant(P((-1,1))*left,P((-1,1))*right)==0
    assert resultant(P((2,)),right)==8
    assert resultant(left,P((2,)))==4


@pytest.mark.parametrize('rows,expected',[
    (((2,0),(0,2)),P((-2,1))),
    (((2,1),(0,2)),P((4,-4,1))),
    (((0,1),(-2,0)),P((2,0,1))),
    (((1,0,0),(0,2,0),(0,0,3)),P((-6,11,-6,1))),
    (((0,),),P((0,1))),
])
def test_minimal_polynomial_annihilates_and_spectral_certificate_roundtrips(rows,expected):
    matrix=Matrix(rows)
    assert minimal_polynomial(matrix)==expected
    certificate=spectral_certificate(matrix)
    assert verify_spectral_certificate(certificate.to_data())
    assert not any(v for row in evaluate_matrix_polynomial(expected,matrix).rows for v in row)


@pytest.mark.parametrize('change',['characteristic','minimal','nonminimal','matrix','proof','scope','schema','encoding'])
def test_spectral_certificate_rejects_rehashed_forgery(change):
    data=spectral_certificate(Matrix(((2,0),(0,2)))).to_data()
    if change=='characteristic':data['characteristic']=['3','-4','1']
    elif change=='minimal':data['minimal']=['-3','1']
    elif change=='nonminimal':data['minimal']=list(data['characteristic'])
    elif change=='matrix':data['matrix'][0][1]='1'
    elif change=='proof':data['formal_proof']=True
    elif change=='scope':data['scope']='Independent Lean proof'
    elif change=='schema':data['schema_version']=True
    else:data['matrix'][0][0]='4/2'
    assert not verify_spectral_certificate(rehash(data))


def test_jordan_generalized_eigenspaces_and_multiplicity():
    matrix=Matrix(((2,1,0),(0,2,1),(0,0,2)))
    assert eigenvalue_multiplicity(matrix,2)==3
    assert eigenvalue_multiplicity(matrix,3)==0
    assert [len(generalized_eigenspace(matrix,2,order=k)) for k in (1,2,3)]==[1,2,3]
    with pytest.raises(ValueError,match='not rationally'):
        rational_diagonalization(matrix,(2,))


def test_exact_diagonalization_and_tampered_basis():
    matrix=Matrix(((1,1),(0,2)))
    result=rational_diagonalization(matrix,(2,1))
    assert result.verify(matrix)
    assert result==rational_diagonalization(matrix,(1,2))
    assert not replace(result,inverse_basis=identity(2)).verify(matrix)
    with pytest.raises(ValueError):rational_diagonalization(matrix,(1,))
    with pytest.raises(ValueError):rational_diagonalization(matrix,(1,3))
    assert rational_diagonalization(Matrix(((2,0),(0,2))),(2,)).verify(Matrix(((2,0),(0,2))))


def test_rational_nullspace_and_matrix_budget_rejections():
    matrix=Matrix(((1,2,3),(2,4,6)))
    basis=nullspace(matrix)
    assert basis==((F(-2),F(1),F(0)),(F(-3),F(0),F(1)))
    assert nullspace(identity(3))==()
    for matrix in [Matrix(((1,2),)),identity(9),Matrix(((2**513,),))]:
        with pytest.raises(ValueError):spectral_certificate(matrix)
    for order in [True,0,3]:
        with pytest.raises(ValueError):generalized_eigenspace(identity(2),1,order=order)
    with pytest.raises(ValueError):generalized_eigenspace(identity(2),1.0)


def test_independent_sympy_polynomial_operations_32_seeded_cases():
    sympy=pytest.importorskip('sympy')
    x=sympy.Symbol('x')
    rng=random.Random(20261016)
    def expression(poly):
        return sum(sympy.Rational(c.numerator,c.denominator)*x**i for i,c in enumerate(poly.coefficients))
    for _ in range(32):
        left=P(tuple(rng.randint(-4,4) for _ in range(4))+(1,))
        right=P(tuple(rng.randint(-4,4) for _ in range(3))+(1,))
        assert resultant(left,right)==int(sympy.resultant(expression(left),expression(right),x))
        assert discriminant(left)==int(sympy.discriminant(expression(left),x))
        certificate=extended_polynomial_gcd(left,right)
        expected=sympy.Poly(sympy.gcd(expression(left),expression(right)),x).monic()
        assert expression(certificate.gcd).expand()==expected.as_expr()
        expected_count=sympy.Poly(expression(left),x).count_roots(-100,100)
        assert count_real_roots(left,-100,100)==expected_count


def test_independent_sympy_spectral_24_seeded_matrices():
    sympy=pytest.importorskip('sympy')
    rng=random.Random(8675309)
    for size in (1,2,3,4):
        for _ in range(6):
            rows=tuple(tuple(F(rng.randint(-3,3),rng.randint(1,4)) for _ in range(size)) for _ in range(size))
            matrix=Matrix(rows)
            result=spectral_certificate(matrix)
            reference=sympy.Matrix([[sympy.Rational(v.numerator,v.denominator) for v in row] for row in rows]).charpoly()
            expected=tuple(F(int(v.p),int(v.q)) for v in reversed(reference.all_coeffs()))
            assert result.characteristic.coefficients==expected
            assert verify_spectral_certificate(result.to_data())


def test_invariant_crt_projectors_split_vectors_and_commute_with_dynamics():
    from nablamath.math.linear_algebra.invariant_decomposition import invariant_decomposition
    matrix=Matrix(((1,1,0),(0,1,0),(0,0,2)))
    result=invariant_decomposition(matrix)
    assert result.verify()
    assert sorted(p.dimension for p in result.projectors)==[1,2]
    components=result.split_vector((3,4,5))
    assert tuple(sum(component[j] for component in components) for j in range(3))==(3,4,5)
    for projector,component in zip(result.projectors,components):
        assert Matrix(tuple((value,) for value in component))==projector.matrix@Matrix(((3,),(4,),(5,)))
    bad=replace(result.projectors[0],matrix=identity(3))
    assert not replace(result,projectors=(bad,*result.projectors[1:])).verify()


def test_invariant_explicit_factors_separate_same_multiplicity_eigenvalues():
    from nablamath.math.linear_algebra.invariant_decomposition import invariant_decomposition
    matrix=Matrix(((1,0,0),(0,2,0),(0,0,3)))
    factors=(P((-1,1)),P((-2,1)),P((-3,1)))
    result=invariant_decomposition(matrix,factors)
    assert result.verify()
    assert [projector.dimension for projector in result.projectors]==[1,1,1]
    assert result.split_vector((4,5,6))==((4,0,0),(0,5,0),(0,0,6))
    with pytest.raises(ValueError):invariant_decomposition(matrix,(P((-1,1)),P((-2,1))))
    with pytest.raises(ValueError):result.split_vector((True,2,3))


@pytest.mark.parametrize('rows,index',[
    (((2,0),(0,3)),1),(((2,1),(0,2)),2),
    (((2,1,0),(0,2,1),(0,0,2)),3),
    (((0,1),(-2,0)),1),
    (((0,1,0,0),(-2,0,1,0),(0,0,0,1),(0,0,-2,0)),2),
    (((0,),),1),
])
def test_additive_semisimple_nilpotent_decomposition(rows,index):
    from nablamath.math.linear_algebra.invariant_decomposition import additive_decomposition,verify_additive_decomposition
    matrix=Matrix(rows)
    result=additive_decomposition(matrix)
    assert result.nilpotency_index==index
    assert result.verify()
    assert verify_additive_decomposition(result.to_data())
    assert result.semisimple@result.nilpotent==result.nilpotent@result.semisimple
    if index==1:
        assert result.semisimple==matrix
        assert not any(v for row in result.nilpotent.rows for v in row)


@pytest.mark.parametrize('change',['nilpotent','semisimple','index','polynomial','proof','scope'])
def test_additive_certificate_rejects_rehashed_tampering(change):
    from nablamath.math.linear_algebra.invariant_decomposition import additive_decomposition,verify_additive_decomposition
    data=additive_decomposition(Matrix(((2,1),(0,2)))).to_data()
    if change=='nilpotent':data['nilpotent'][0][1]='0'
    elif change=='semisimple':data['semisimple'][0][0]='3'
    elif change=='index':data['nilpotency_index']=1
    elif change=='polynomial':data['semisimple_polynomial']=['3']
    elif change=='proof':data['formal_proof']=True
    else:data['scope']='Formally proved discovery'
    assert not verify_additive_decomposition(rehash(data))


def test_additive_decomposition_is_covariant_under_exact_similarity():
    from nablamath.math.linear_algebra.invariant_decomposition import additive_decomposition
    original=Matrix(((1,1,0),(0,1,0),(0,0,2)))
    basis=Matrix(((1,2,0),(0,1,3),(0,0,1)))
    transformed=basis@original@basis.inverse()
    left,right=additive_decomposition(original),additive_decomposition(transformed)
    assert right.semisimple==basis@left.semisimple@basis.inverse()
    assert right.nilpotent==basis@left.nilpotent@basis.inverse()
    assert right.nilpotency_index==left.nilpotency_index


def test_finite_field_arithmetic_modular_inversion_and_euclidean_identity():
    from nablamath.math.polynomials.finite_field import FpPolynomial as FP,fp_gcd
    left,right=FP(5,(2,4,0,1)),FP(5,(1,2,1))
    quotient,remainder=left.divmod(right)
    assert quotient*right+remainder==left
    assert remainder.degree<right.degree
    assert FP.from_data(left.to_data())==left
    assert left(3)==(2+4*3+3**3)%5
    assert fp_gcd(left*right,right)==right.monic()
    assert left.powmod(50,right)==(left.powmod(25,right)*left.powmod(25,right))%right
    assert (left-left).is_zero
    with pytest.raises(ValueError):left+FP(7,(1,))
    with pytest.raises(ZeroDivisionError):left.divmod(FP(5,(0,)))


@pytest.mark.parametrize('prime,coefficients,expected',[
    (2,(1,1,1),True),(2,(1,0,1),False),(2,(1,1,0,1),True),
    (3,(1,0,1),True),(5,(1,0,1),False),(7,(1,0,1),True),
    (2,(1,0,0,0,1),False),(3,(0,1),True),(3,(2,),False),
])
def test_rabin_irreducibility_reference_cases(prime,coefficients,expected):
    from nablamath.math.polynomials.finite_field import FpPolynomial,is_irreducible
    assert is_irreducible(FpPolynomial(prime,coefficients)) is expected


def test_berlekamp_basis_dimension_matches_distinct_factors():
    from nablamath.math.polynomials.finite_field import FpPolynomial as FP,berlekamp_basis
    factors=(FP(3,(0,1)),FP(3,(1,1)),FP(3,(1,0,1)))
    polynomial=factors[0]*factors[1]*factors[2]
    basis=berlekamp_basis(polynomial)
    assert len(basis)==3
    assert all((element.powmod(3,polynomial)-element).is_zero for element in basis)
    with pytest.raises(ValueError):berlekamp_basis(factors[0]**2)


@pytest.mark.parametrize('prime',[2,3,5,7,11])
def test_finite_field_repeated_and_inseparable_factors(prime):
    from nablamath.math.polynomials.finite_field import FpPolynomial as FP,factor_finite_field,verify_finite_field_factorization
    x=FP(prime,(0,1))
    first,second=x+1,x+2 if prime>2 else x
    # Characteristic-p derivative zero exercises p-th root recursion.
    exponent=min(prime,7)
    polynomial=2*(first**exponent)*(second**2) if prime>2 else (first**4)*(second**3)
    result=factor_finite_field(polynomial)
    assert verify_finite_field_factorization(result.to_data())
    expected={first.monic():exponent,second.monic():2} if prime>2 else {first:4,second:3}
    assert dict(result.factors)==expected
    assert result==factor_finite_field(polynomial)


def test_characteristic_three_inseparable_leftovers_mixed_multiplicity():
    from nablamath.math.polynomials.finite_field import FpPolynomial as FP,factor_finite_field
    x=FP(3,(0,1))
    polynomial=(x+1)*(x+2)**3*(x*x+1)**6
    result=factor_finite_field(polynomial)
    assert dict(result.factors)=={x+1:1,x+2:3,x*x+1:6}


@pytest.mark.parametrize('change',['coefficient','multiplicity','reducible','drop','duplicate','proof','prime','noncanonical','bool'])
def test_finite_field_certificate_rejects_rehashed_forgery(change):
    from nablamath.math.polynomials.finite_field import FpPolynomial as FP,factor_finite_field,verify_finite_field_factorization
    x=FP(5,(0,1))
    data=factor_finite_field((x+1)*(x+2)).to_data()
    if change=='coefficient':data['factors'][0]['polynomial']['coefficients'][0]=4
    elif change=='multiplicity':data['factors'][0]['multiplicity']=2
    elif change=='reducible':data['factors']=[{'polynomial':data['polynomial'],'multiplicity':1}]
    elif change=='drop':data['factors'].pop()
    elif change=='duplicate':data['factors'].append(copy.deepcopy(data['factors'][0]))
    elif change=='proof':data['formal_proof']=True
    elif change=='prime':data['polynomial']['prime']=4
    elif change=='noncanonical':data['polynomial']['coefficients'][0]+=5
    else:data['factors'][0]['multiplicity']=True
    assert not verify_finite_field_factorization(rehash(data))


def test_finite_field_bounds_and_explicit_work_exhaustion():
    from nablamath.math.polynomials.finite_field import FpPolynomial as FP,factor_finite_field
    for prime in [True,1,4,258,65537]:
        with pytest.raises(ValueError):FP(prime,(1,))
    for coefficients in [(True,1),(1.2,1),(),(0,)*66]:
        with pytest.raises(ValueError):FP(3,coefficients)
    for polynomial in [FP(3,(0,)),FP(3,(0,)*17+(1,))]:
        with pytest.raises(ValueError):factor_finite_field(polynomial)
    x=FP(7,(0,1))
    with pytest.raises(ValueError,match='budget'):
        factor_finite_field((x+1)*(x+2)*(x+3),max_work=1)
    for value in [-1,True,1<<300]:
        with pytest.raises(ValueError):x.powmod(value,x*x+1)


def test_finite_field_factorization_exhaustive_small_binary_and_ternary_polynomials():
    from itertools import product
    from nablamath.math.polynomials.finite_field import FpPolynomial as FP,factor_finite_field,verify_finite_field_factorization
    # 182 monic inputs over two fields, including every repeated-root edge case.
    for prime,maximum_degree in [(2,5),(3,4)]:
        for degree in range(1,maximum_degree+1):
            for coefficients in product(range(prime),repeat=degree):
                polynomial=FP(prime,coefficients+(1,))
                result=factor_finite_field(polynomial)
                assert verify_finite_field_factorization(result.to_data())


def test_finite_field_factors_against_independent_sympy_60_cases():
    sympy=pytest.importorskip('sympy')
    from nablamath.math.polynomials.finite_field import FpPolynomial as FP,factor_finite_field
    x=sympy.Symbol('x')
    rng=random.Random(2026101603)
    for prime in (2,3,5,7,11):
        for _ in range(12):
            coefficients=tuple(rng.randrange(prime) for _ in range(6))+(rng.randrange(1,prime),)
            polynomial=FP(prime,coefficients)
            result=factor_finite_field(polynomial)
            expression=sum(value*x**i for i,value in enumerate(coefficients))
            leading,factors=sympy.factor_list(expression,modulus=prime)
            expected={tuple(int(v)%prime for v in reversed(sympy.Poly(factor,x,modulus=prime).monic().all_coeffs())):multiplicity
                      for factor,multiplicity in factors}
            assert result.leading==int(leading)%prime
            assert {factor.coefficients:multiplicity for factor,multiplicity in result.factors}==expected


def test_polynomial_crt_reduces_high_degree_residues_before_products():
    moduli=(P((-1,1)),P((1,0,1)),P((2,1)))
    residues=(P((0,)*32+(1,)),P((1,)*33),P((2,)*33))
    result,_=polynomial_crt(residues,moduli)
    for residue,modulus in zip(residues,moduli):
        assert result.divmod(modulus)[1]==residue.divmod(modulus)[1]


def test_sturm_sign_variations_rejects_infinite_sequence():
    from itertools import repeat
    with pytest.raises(ValueError,match='length'):
        sign_variations(repeat(P((1,))),0)
