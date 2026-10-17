"""Finite-field laws and a nontrivial supersingular pairing reference."""
import pytest
pytest.importorskip("sympy")
pytest.importorskip("numpy")
pytest.importorskip("scipy")
from nablamath.ops.abstract_algebra_crypto import (
    GaloisField, FieldElement, ExtensionCurve, finite_field, elliptic,
    groebner_basis, matrix_group, calculate,
)


def test_gf_256_aes_reference():
    field=GaloisField(2,(1,1,0,1,1,0,0,0,1))
    def byte(n):return field.element([(n>>i)&1 for i in range(8)])
    assert byte(0x57)*byte(0x83)==byte(0xc1)
    for n in (1,2,3,0x53,0xff):
        a=byte(n)
        assert a*a.inverse()==field.element(1)
        assert a**256==a
    assert byte(0x53).inverse()==byte(0xca)


def test_small_field_exhaustive_distributivity():
    f=GaloisField(3,(1,0,1))
    elements=[f.element([i,j]) for i in range(3) for j in range(3)]
    for a in elements:
        if a:assert a/a==f.element(1)
        for b in elements:
            for c in elements:
                assert a*(b+c)==a*b+a*c


def test_extension_curve_group_and_reduced_tate_bilinearity():
    f=GaloisField(11,(1,0,1));curve=ExtensionCurve(f,1,0)
    p=(f.element(5),f.element(3))
    q=(f.element(6),f.element([0,3]))
    assert curve.multiply(3,p) is None and curve.multiply(3,q) is None
    assert curve.add(p,curve.multiply(-1,p)) is None
    e=curve.tate_pairing(p,q,3)
    assert e!=f.element(1) and e**3==f.element(1)
    assert curve.tate_pairing(curve.multiply(2,p),q,3)==e**2
    assert curve.tate_pairing(p,curve.multiply(2,q),3)==e**2
    assert curve.multiply(-2,p)==p


def test_field_and_elliptic_serializable_adapters():
    assert finite_field(5,[0,1],[3],right=[4],operation='multiply')['coefficients']==[2]
    assert finite_field(5,[0,1],[3],operation='inverse')['coefficients']==[2]
    assert elliptic(11,[1,0,1],1,0,[5,3],scalar=3,operation='multiply')['point'] is None
    result=elliptic(11,[1,0,1],1,0,[5,3],[[6,0],[0,3]],operation='pairing',r=3)
    assert result['kind']=='reduced Tate' and result['value']!=[1,0]


def test_groebner_ideals_and_lie_matrix():
    result=groebner_basis(['x*y-1','y*y-1'],['x','y'],order='lex')
    assert result['basis']==['x - y','y**2 - 1']
    assert groebner_basis(['x','x-1'],['x'])['inconsistent']
    assert groebner_basis(['x*x+1'],['x'],prime=3)['domain']=='GF(3)'
    import numpy as np
    result=matrix_group('SU',[[[0,0],[0,1]],[[0,1],[0,0]]])
    assert result


@pytest.mark.parametrize('call',[
    lambda:GaloisField(4,(1,0,1)),lambda:GaloisField(3,(2,0,1)),
    lambda:GaloisField(3,(1,2)),lambda:GaloisField(3,(1,)*18),
    lambda:GaloisField(5,(0,1)).element(0).inverse(),
    lambda:ExtensionCurve(GaloisField(5,(0,1)),0,0),
    lambda:ExtensionCurve(GaloisField(11,(0,1)),1,0).point([1,1]),
    lambda:groebner_basis(['1/x'],['x']),lambda:groebner_basis(['x'],['x'],prime=4),
    lambda:finite_field(5,[0,1],1,operation='unknown'),
    lambda:elliptic(11,[0,1],1,0,[5,3],operation='pairing',right=[5,3],r=3),
])
def test_reject_invalid_algebra(call):
    with pytest.raises((ValueError,ZeroDivisionError)):call()


def test_field_coercion_and_canonicality():
    f=GaloisField(5,(0,1));g=GaloisField(7,(0,1))
    assert 2-f.element(3)==f.element(4)
    assert 2/f.element(3)==f.element(4)
    with pytest.raises(ValueError):f.element(g.element(1))
    with pytest.raises(ValueError):FieldElement(f,(5,))


def test_algebra_receipt():
    from nablamath.calc.receipt import verify_receipt
    result=calculate('field',p=5,modulus=[0,1],left=[3],operation='inverse')
    assert verify_receipt(result.to_data())
