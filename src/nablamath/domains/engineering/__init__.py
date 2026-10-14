"""Small-displacement axial bars and cantilever beams in linear elasticity."""
from ..contracts import si,result,PASCAL,NEWTON,METER,Quantity


def axial_bar(force,length,area,young_modulus):
    f=si(force,NEWTON); l=si(length,METER,positive=True)
    a=si(area,METER**2,positive=True); e=si(young_modulus,PASCAL,positive=True)
    stress=f/a; strain=stress/e; extension=strain*l
    if abs(strain)>1/100:
        raise ValueError('Deformação excede regime linear declarado (1%)')
    return result('engineering','linear_axial_bar',locals_input(force=force,length=length,area=area,young_modulus=young_modulus),
                  {'stress':stress,'strain':strain,'extension':extension},
                  {'stress':'Pa','strain':'1','extension':'m'},
                  {'force_balance':stress*a==f,'hooke_law':e*extension/l==stress},
                  'Uniform bar, small strain, no buckling, plasticity or experimental validation.')


def locals_input(**values):
    return values


def cantilever_tip(force,length,young_modulus,second_moment):
    f=si(force,NEWTON);l=si(length,METER,positive=True)
    e=si(young_modulus,PASCAL,positive=True);i=si(second_moment,METER**4,positive=True)
    deflection=f*l**3/(3*e*i); rotation=f*l*l/(2*e*i)
    if abs(deflection)>l/20 or abs(rotation)>1/10:
        raise ValueError('Viga fora da hipótese de pequenas deflexões')
    return result('engineering','euler_bernoulli_cantilever',
                  {'force':force,'length':length,'young_modulus':young_modulus,'second_moment':second_moment},
                  {'tip_deflection':deflection,'tip_rotation':rotation,'root_moment':f*l},
                  {'tip_deflection':'m','tip_rotation':'rad','root_moment':'N*m'},
                  {'tip_compliance':3*e*i*deflection==f*l**3,'rotation_consistency':2*e*i*rotation==f*l*l},
                  'Slender prismatic linear beam; no shear deformation, buckling or experimental validation.')
