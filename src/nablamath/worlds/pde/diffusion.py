"""Theta-method 1D diffusion with arbitrary finite initial data and fixed boundaries.

Backward Euler and Crank–Nicolson solve a tridiagonal linear system. CN is stable
in the linear L2 sense but may oscillate for large steps; it is not unconditionally
positivity preserving. No physical observations or universal PDE claim.
"""
import math


def _tridiagonal(lower, diagonal, upper, rhs):
    d=list(diagonal);b=list(rhs);n=len(d)
    for i in range(1,n):
        if abs(d[i-1])<1e-300:raise ValueError('Sistema tridiagonal singular')
        multiplier=lower[i-1]/d[i-1];d[i]-=multiplier*upper[i-1];b[i]-=multiplier*b[i-1]
    result=[0.]*n
    for i in range(n-1,-1,-1):
        if abs(d[i])<1e-300:raise ValueError('Sistema tridiagonal singular')
        result[i]=(b[i]-(upper[i]*result[i+1] if i<n-1 else 0))/d[i]
    return tuple(result)


def solve_diffusion(initial, *, length=1., diffusivity=.1, duration=.1, steps=100,
                    boundary=(0.,0.), method='crank_nicolson', snapshot_stride=1):
    initial=tuple(initial);boundary=tuple(boundary)
    if (not 5<=len(initial)<=2001 or len(boundary)!=2 or type(steps) is not int or not 1<=steps<=100000
            or type(snapshot_stride) is not int or not 1<=snapshot_stride<=steps
            or steps*len(initial)>10000000 or (steps//snapshot_stride+2)*len(initial)>2000000):
        raise ValueError('Malha ou orçamento inválido')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e12
           for v in (*initial,*boundary,length,diffusivity,duration)) or min(length,diffusivity,duration)<=0:
        raise ValueError('Parâmetros finitos e positivos obrigatórios')
    if tuple(initial[i] for i in (0,-1))!=boundary:
        raise ValueError('Estado inicial incompatível com contorno')
    theta={'ftcs':0.,'backward_euler':1.,'crank_nicolson':.5}.get(method)
    if theta is None:raise ValueError('Método desconhecido')
    dx=length/(len(initial)-1);dt=duration/steps;r=diffusivity*dt/dx**2
    if theta==0 and r>.5:raise ValueError('FTCS instável')
    n=len(initial)-2;off=[-theta*r]*(n-1);diag=[1+2*theta*r]*n
    state=tuple(float(v) for v in initial);trajectory=[(0.,state)];residual=0.;minvalue=min(state)
    for step in range(1,steps+1):
        rhs=[state[i]+(1-theta)*r*(state[i-1]-2*state[i]+state[i+1]) for i in range(1,n+1)]
        rhs[0]+=theta*r*boundary[0];rhs[-1]+=theta*r*boundary[1]
        interior=_tridiagonal(off,diag,off,rhs)
        new=(float(boundary[0]),*interior,float(boundary[1]))
        for i in range(1,n+1):
            actual=(new[i]-state[i])-r*(theta*(new[i-1]-2*new[i]+new[i+1])+(1-theta)*(state[i-1]-2*state[i]+state[i+1]))
            residual=max(residual,abs(actual))
        if not all(math.isfinite(v) for v in new):raise ValueError('Solução não finita')
        state=new;minvalue=min(minvalue,min(state))
        if step%snapshot_stride==0 or step==steps:trajectory.append((step*dt,state))
    return {'schema_version':1,'model':'linear_diffusion_1d_fixed_dirichlet','method':method,'theta':theta,
            'length':length,'diffusivity':diffusivity,'duration':duration,'steps':steps,'initial':initial,
            'boundary':boundary,'snapshot_stride':snapshot_stride,'positions':tuple(i*dx for i in range(len(initial))),
            'final':state,'trajectory':trajectory,'discrete_equation_residual':residual,'minimum_observed_state':minvalue,
            'dx':dx,'dt':dt,'diffusion_ratio':r,'units':{'position':'m','time':'s','state':'K'},
            'experimental_validation':False,'limitations':'Linear diffusion only; CN can oscillate at large steps; residual is not physical validation.'}
