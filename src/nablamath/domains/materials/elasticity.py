"""Exact isotropic 3D small-strain elasticity; no plasticity or measured calibration."""
from ..contracts import si,result,PASCAL
from ...core.units import ONE
from ...core.semantic_ir import rational


def isotropic_elasticity(young_modulus,poisson_ratio,strain):
    e=si(young_modulus,PASCAL,positive=True);nu=si(poisson_ratio,ONE)
    if not -1<nu<rational('1/2') or len(strain)!=3 or any(len(row)!=3 for row in strain):raise ValueError('Poisson ou tensor de deformação inválido')
    eps=tuple(tuple(rational(v) for v in row) for row in strain)
    if any(abs(v)>rational('1/100') for row in eps for v in row) or any(eps[i][j]!=eps[j][i] for i in range(3) for j in range(3)):
        raise ValueError('Deformação pequena e simétrica obrigatória')
    mu=e/(2*(1+nu));lam=e*nu/((1+nu)*(1-2*nu));trace=sum(eps[i][i] for i in range(3))
    stress=tuple(tuple(2*mu*eps[i][j]+(lam*trace if i==j else 0) for j in range(3)) for i in range(3))
    energy=sum(stress[i][j]*eps[i][j] for i in range(3) for j in range(3))/2
    return result('materials','isotropic_small_strain_3d',dict(young_modulus=young_modulus,poisson_ratio=poisson_ratio,strain=strain),
                  {'stress':stress,'strain_energy_density':energy,'lame_lambda':lam,'shear_modulus':mu},
                  {'stress':'Pa','strain_energy_density':'J/m^3'},
                  {'symmetric_stress':all(stress[i][j]==stress[j][i] for i in range(3) for j in range(3)), 'nonnegative_energy':energy>=0},
                  'Isotropic linear small strain <= 0.01; no plasticity, anisotropy or experimental calibration.')
