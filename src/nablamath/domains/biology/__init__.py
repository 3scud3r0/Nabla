"""Ideal continuous logistic populations and normalized closed SIR dynamics."""
import math
from ...math.equations.ode import integrate
from ..contracts import si,result,ONE,SECOND


def logistic(initial,capacity,rate,duration,*,steps=200):
    p=si(initial,ONE,positive=True);k=si(capacity,ONE,positive=True);r=si(rate,ONE/SECOND,positive=True);t=si(duration,SECOND,positive=True)
    if r*t>50 or type(steps) is not int or not 2<=steps<=100000 or float(r*t)/steps>.1:
        raise ValueError('Integração fora do regime limitado de passo')
    if p>k:
        raise ValueError('Este perfil requer população inicial até a capacidade')
    trajectory=integrate(lambda time,state:(float(r)*state[0]*(1-state[0]/float(k)),),(float(p),),0.,float(t),steps,'rk4')
    reference=float(k)/(1+(float(k/p)-1)*math.exp(-float(r*t)))
    final=trajectory[-1][1][0]
    return result('biology','continuous_logistic_population',{'initial':initial,'capacity':capacity,'rate':rate,'duration':duration,'steps':steps},
                  {'final':final,'analytic_reference':reference,'absolute_error':abs(final-reference),'trajectory':trajectory},
                  {'population':'dimensionless_count','time':'s','rate':'1/s'},
                  {'positive_and_bounded':all(0<s[0]<=float(k)*(1+1e-12) for _,s in trajectory),
                   'analytic_agreement':abs(final-reference)<=1e-6*max(1,abs(reference))},
                  'Continuous ideal population; no stochasticity, spatial effects or empirical biological validation.')


def sir(initial,beta,gamma,duration,*,steps=400):
    from ...core.semantic_ir import rational
    state=tuple(rational(v) for v in initial)
    b=si(beta,ONE/SECOND,positive=True);g=si(gamma,ONE/SECOND,positive=True);t=si(duration,SECOND,positive=True)
    if len(state)!=3 or any(v<0 for v in state) or sum(state)!=1 or type(steps) is not int or not 2<=steps<=100000 or (b+g)*t/steps>1/10:
        raise ValueError('SIR requer frações normalizadas e passo suficientemente pequeno')
    def derivative(time,values):
        s,i,r=values;infection=float(b)*s*i;recovery=float(g)*i
        return -infection,infection-recovery,recovery
    trajectory=integrate(derivative,tuple(float(v) for v in state),0.,float(t),steps,'rk4')
    residual=max(abs(sum(row)-1) for _,row in trajectory)
    return result('biology','closed_normalized_SIR',{'initial':state,'beta':beta,'gamma':gamma,'duration':duration,'steps':steps},
                  {'trajectory':trajectory,'final':trajectory[-1][1],'population_residual':residual},
                  {'state':'population_fraction','time':'s','rates':'1/s'},
                  {'population_conserved':residual<1e-10,'nonnegative':all(min(row)>=-1e-12 for _,row in trajectory)},
                  'Homogeneous closed deterministic SIR, no demographics or interventions; not an epidemic forecast.')
