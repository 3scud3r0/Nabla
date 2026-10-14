"""Normalized continuous-time state-space systems up to dimension two."""
from dataclasses import dataclass
import math
from ...core.semantic_ir import rational
from ...math.linear_algebra import Matrix
from ...math.equations.ode import integrate
from ..contracts import result


@dataclass(frozen=True)
class StateSpace:
    a: tuple[tuple,...]
    b: tuple
    c: tuple
    d: object = 0

    def __post_init__(self):
        a=tuple(tuple(rational(v) for v in row) for row in self.a);b=tuple(rational(v) for v in self.b);c=tuple(rational(v) for v in self.c)
        n=len(a)
        if n not in (1,2) or any(len(row)!=n for row in a) or len(b)!=n or len(c)!=n:
            raise ValueError('Sistema SISO de dimensão 1 ou 2 obrigatório')
        object.__setattr__(self,'a',a);object.__setattr__(self,'b',b);object.__setattr__(self,'c',c);object.__setattr__(self,'d',rational(self.d))

    def analyze(self):
        n=len(self.a);a=Matrix(self.a);trace=sum(self.a[i][i] for i in range(n));det=a.determinant()
        stable=self.a[0][0]<0 if n==1 else trace<0 and det>0
        ab=tuple(sum(self.a[i][j]*self.b[j] for j in range(n)) for i in range(n))
        controllability=Matrix(tuple((self.b[i],ab[i])[:n] for i in range(n)))
        ca=tuple(sum(self.c[i]*self.a[i][j] for i in range(n)) for j in range(n))
        observability=Matrix((self.c,ca)[:n])
        rank=controllability.echelon()[1]; observable=observability.echelon()[1]
        return result('control','normalized_continuous_siso',{'A':self.a,'B':self.b,'C':self.c,'D':self.d},
                      {'asymptotically_stable':stable,'controllability_rank':rank,'observability_rank':observable,'trace':trace,'determinant':det},
                      {'A':'1/s','B':'1/s','C':'1','D':'1','state':'1','input':'1','output':'1'},
                      {'rank_bounds':0<=rank<=n and 0<=observable<=n},
                      'Exact Hurwitz criterion for 1D/2D normalized linear systems; no delays, saturation or experimental validation.')

    def simulate_step(self,*,amplitude=1,duration=1.,steps=100):
        amplitude=rational(amplitude)
        if not math.isfinite(duration) or not 0<duration<=100 or type(steps) is not int or not 2<=steps<=100000:
            raise ValueError('Intervalo ou passos inválidos')
        n=len(self.a)
        def derivative(t,state):
            return tuple(sum(float(self.a[i][j])*state[j] for j in range(n))+float(self.b[i]*amplitude) for i in range(n))
        trajectory=integrate(derivative,(0.,)*n,0.,duration,steps,'rk4')
        outputs=tuple(sum(float(c)*x for c,x in zip(self.c,state))+float(self.d*amplitude) for _,state in trajectory)
        return {'model':'normalized_continuous_siso','method':'rk4','trajectory':trajectory,'outputs':outputs,
                'duration_unit':'s','state_unit':'1','input':str(amplitude),'experimental_validation':False}
