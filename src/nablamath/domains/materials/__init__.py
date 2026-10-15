"""One-dimensional thermoelastic constitutive model with declared temperature change."""
from ..contracts import si,result,PASCAL,KELVIN,ONE


def thermoelastic(young_modulus,expansion,temperature_change,total_strain):
    e=si(young_modulus,PASCAL,positive=True);alpha=si(expansion,ONE/KELVIN)
    dt=si(temperature_change,KELVIN);strain=si(total_strain,ONE)
    thermal=alpha*dt; elastic=strain-thermal;stress=e*elastic
    if abs(strain)>1/100 or abs(thermal)>1/100:
        raise ValueError('Deformação térmica/total excede hipótese linear')
    return result('materials','linear_thermoelasticity',
                  {'young_modulus':young_modulus,'expansion':expansion,'temperature_change':temperature_change,'total_strain':total_strain},
                  {'stress':stress,'thermal_strain':thermal,'elastic_strain':elastic},
                  {'stress':'Pa','thermal_strain':'1','elastic_strain':'1'},
                  {'strain_decomposition':elastic+thermal==strain,'constitutive_residual':stress-e*(strain-alpha*dt)==0},
                  'Homogeneous small-strain material; no plasticity, damage, phase change or experimental validation.')

from .elasticity import isotropic_elasticity
