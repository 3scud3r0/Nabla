"""Local stochastic generators, conservative diffusion and information theory.

Symbolic generators are identities under the declared differentiability
hypotheses. Numerical results are floating-point estimates, never automatic
proofs of convergence, positive definiteness or physical adequacy.
"""
import math

from ..math._structured import expression, names, sympy
from ..math.probability.ito import multivariate_ito
from ..math.probability.stochastic import sde_system


def _array(value, ndim=None, maximum=1000000):
    import numpy as np
    result = np.asarray(value, dtype=float)
    if (not result.size or result.size > maximum or not np.isfinite(result).all()
            or (ndim is not None and result.ndim != ndim)):
        raise ValueError('Bounded nonempty finite numeric array required')
    return result


def _positive(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(name+' must be finite and positive')
    return float(value)


def stochastic_generator(variables, drift, diffusion, density, convention='ito', time='t'):
    """Return Ito drift, backward generator on density and Fokker–Planck RHS.

B[i][a] multiplies independent Brownian motion a. For Stratonovich drift,
Ito correction is (1/2) sum_{j,a} B[j,a] partial_j B[i,a]. Density can also
serve as a test function for the backward generator. No boundary is assumed.
"""
    variables = names(variables, 4)
    names(list(variables)+[time], 5)
    n = len(variables)
    if len(drift) != n or len(diffusion) != n or not diffusion[0]:
        raise ValueError('Drift/diffusion dimensions differ')
    m = len(diffusion[0])
    if not 1 <= m <= 4 or any(len(row) != m for row in diffusion):
        raise ValueError('Rectangular diffusion with 1–4 noise dimensions required')
    if convention not in ('ito', 'stratonovich'):
        raise ValueError('Convention is ito or stratonovich')
    sp = sympy()
    allowed = list(variables)+[time]
    x = list(map(sp.Symbol, variables))
    a = [expression(v, allowed)[0] for v in drift]
    b = sp.Matrix([[expression(v, allowed)[0] for v in row] for row in diffusion])
    correction = [sum(b[j,k]*sp.diff(b[i,k], x[j]) for j in range(n) for k in range(m))/2
                  for i in range(n)]
    if convention == 'stratonovich':
        a = [sp.simplify(v+c) for v,c in zip(a, correction)]
    covariance = b*b.T
    p = expression(density, allowed)[0]
    backward = sum(a[i]*sp.diff(p,x[i]) for i in range(n)) + sum(
        covariance[i,j]*sp.diff(p,x[i],x[j])/2 for i in range(n) for j in range(n))
    forward = -sum(sp.diff(a[i]*p,x[i]) for i in range(n)) + sum(
        sp.diff(covariance[i,j]*p,x[i],x[j])/2 for i in range(n) for j in range(n))
    return {'ito_drift': list(map(str, a)), 'stratonovich_correction': list(map(str, correction)),
            'covariance': [[str(v) for v in row] for row in covariance.tolist()],
            'backward': str(sp.simplify(backward)), 'fokker_planck': str(sp.simplify(forward)),
            'hypotheses': 'Smooth coefficients/density; independent Brownian components; local chart'}


def fokker_planck_1d(density, drift, diffusion, spacing, time_step, steps):
    """Cell-centered conservative upwind/centered finite volumes, reflecting ends.

Solves p_t=-∂x(a p)+D ∂xx p for constant a and D>=0. Explicit Euler is
accepted only when the monotonicity CFL condition holds. Density is returned
in the supplied normalization; mass is never silently rescaled or clipped.
"""
    import numpy as np
    from scipy.sparse import diags
    p = _array(density, 1, 100000)
    if len(p) < 2 or (p < 0).any():
        raise ValueError('Nonnegative density on at least two cells required')
    dx = _positive(spacing, 'spacing')
    dt = _positive(time_step, 'time_step')
    if type(steps) is not int or not 0 <= steps <= 100000 or len(p)*steps > 100000000:
        raise ValueError('Evolution budget exceeded')
    if type(drift) not in (int,float) or not math.isfinite(drift):
        raise ValueError('Finite constant drift required')
    if type(diffusion) not in (int,float) or not math.isfinite(diffusion) or diffusion < 0:
        raise ValueError('Nonnegative finite diffusion coefficient required')
    right = max(drift,0)/dx+diffusion/dx**2
    left = max(-drift,0)/dx+diffusion/dx**2
    cfl = dt*(left+right)
    if cfl > 1:
        raise ValueError('Positivity CFL exceeded')
    diagonal = np.full(len(p), -(right+left))
    diagonal[0] = -right
    diagonal[-1] = -left
    generator = diags([np.full(len(p)-1,right),diagonal,np.full(len(p)-1,left)],[-1,0,1],format='csr')
    initial_mass = float(p.sum()*dx)
    if initial_mass <= 0:
        raise ValueError('Positive initial mass required')
    for _ in range(steps):
        p = p+dt*(generator@p)
    if not np.isfinite(p).all() or p.min() < -1e-13:
        raise ArithmeticError('Evolution lost positivity or finiteness')
    return {'density': p.tolist(), 'initial_mass': initial_mass, 'mass': float(p.sum()*dx),
            'minimum': float(p.min()), 'time': dt*steps, 'cfl': cfl,
            'boundary': 'zero flux', 'error': 'Discretization error not certified'}


def gaussian_information(mean, covariance, reference_mean=None, reference_covariance=None):
    """Differential entropy in nats and optional KL(N||reference N)."""
    import numpy as np
    from scipy.linalg import cho_factor, cho_solve
    mu = _array(mean, 1, 256)
    cov = _array(covariance, 2, 65536)
    if cov.shape != (len(mu),len(mu)) or not np.allclose(cov,cov.T,atol=1e-12,rtol=1e-12):
        raise ValueError('Symmetric covariance matching mean required')
    try:
        factor = cho_factor(cov, lower=True)
    except np.linalg.LinAlgError as error:
        raise ValueError('Positive definite covariance required') from error
    logdet = 2*float(np.log(np.diag(factor[0])).sum())
    result = {'entropy_nats': .5*(len(mu)*math.log(2*math.pi*math.e)+logdet)}
    if (reference_mean is None) != (reference_covariance is None):
        raise ValueError('Supply both reference parameters')
    if reference_mean is not None:
        other = _array(reference_mean,1,256)
        ref = _array(reference_covariance,2,65536)
        if other.shape != mu.shape or ref.shape != cov.shape or not np.allclose(ref,ref.T,atol=1e-12,rtol=1e-12):
            raise ValueError('Reference dimensions/symmetry differ')
        try:
            reference = cho_factor(ref,lower=True)
        except np.linalg.LinAlgError as error:
            raise ValueError('Positive definite reference covariance required') from error
        delta = other-mu
        logref = 2*float(np.log(np.diag(reference[0])).sum())
        result['kl_nats'] = .5*(float(np.trace(cho_solve(reference,cov)))
            + float(delta@cho_solve(reference,delta))-len(mu)+logref-logdet)
    return result


def discrete_information(probabilities, reference=None, base=2):
    """Shannon entropy and KL with 0 log 0=0 and unsupported mass => infinity."""
    import numpy as np
    p = _array(probabilities,1,4096)
    if type(base) not in (int,float) or not math.isfinite(base) or base <= 1:
        raise ValueError('Logarithm base greater than one required')
    if (p<0).any() or not np.isclose(p.sum(),1,rtol=0,atol=1e-12):
        raise ValueError('Normalized probability vector required')
    mask = p>0
    result = {'entropy': float(-np.sum(p[mask]*np.log(p[mask]))/math.log(base)), 'base': base}
    if reference is not None:
        q = _array(reference,1,4096)
        if q.shape != p.shape or (q<0).any() or not np.isclose(q.sum(),1,rtol=0,atol=1e-12):
            raise ValueError('Normalized matching reference vector required')
        result['kl'] = None if (q[mask] == 0).any() else float(np.sum(p[mask]*np.log(p[mask]/q[mask]))/math.log(base))
        result['kl_infinite'] = bool((q[mask] == 0).any())
    return result


def channel_capacity(channel, tolerance=1e-10, max_iterations=10000):
    """Blahut–Arimoto for a finite discrete memoryless channel, bounds in bits."""
    import numpy as np
    w = _array(channel,2,65536)
    if not 1 <= w.shape[0] <= 256 or (w<0).any() or not np.allclose(w.sum(axis=1),1,rtol=0,atol=1e-12):
        raise ValueError('Row-stochastic channel matrix required')
    tolerance = _positive(tolerance,'tolerance')
    if type(max_iterations) is not int or not 1 <= max_iterations <= 100000:
        raise ValueError('Iteration budget exceeded')
    p = np.full(w.shape[0],1/w.shape[0])
    for iteration in range(1,max_iterations+1):
        q = p@w
        terms = np.zeros_like(w)
        mask = w>0
        terms[mask] = w[mask]*np.log(w[mask]/np.broadcast_to(q,w.shape)[mask])
        divergence = terms.sum(axis=1)
        lower, upper = float(p@divergence),float(divergence.max())
        if (upper-lower)/math.log(2) <= tolerance or iteration == max_iterations:
            break
        logp = np.log(p)+divergence
        p = np.exp(logp-logp.max())
        p /= p.sum()
    return {'capacity_bits': lower/math.log(2), 'upper_bits': upper/math.log(2),
            'input_distribution': p.tolist(), 'iterations': iteration,
            'converged': (upper-lower)/math.log(2) <= tolerance,
            'bound_scope': 'Floating-point Blahut–Arimoto bounds; no interval certificate'}


def gaussian_process(train_x, train_y, query_x, length_scale=1., variance=1., noise=1e-6):
    """Zero-mean RBF Gaussian process; observation noise is variance, not std."""
    import numpy as np
    from scipy.linalg import cho_factor, cho_solve
    x,y,z = _array(train_x,2,16384),_array(train_y,1,512),_array(query_x,2,16384)
    if len(x) != len(y) or len(x)>512 or len(z)>512 or x.shape[1] != z.shape[1]:
        raise ValueError('GP dimensions differ or 512-point budget exceeded')
    length_scale = _positive(length_scale,'length scale')
    variance = _positive(variance,'variance')
    if type(noise) not in (int,float) or not math.isfinite(noise) or noise < 0:
        raise ValueError('Nonnegative noise variance required')
    def kernel(a,b):
        differences = (a[:,None,:]-b[None,:,:])/length_scale
        return variance*np.exp(-.5*np.sum(differences*differences,axis=2))
    try:
        factor = cho_factor(kernel(x,x)+noise*np.eye(len(x)),lower=True)
    except np.linalg.LinAlgError as error:
        raise ValueError('Singular GP covariance; supply positive observation noise') from error
    cross = kernel(z,x)
    mean = cross@cho_solve(factor,y)
    cov = kernel(z,z)-cross@cho_solve(factor,cross.T)
    cov = (cov+cov.T)/2
    if not np.isfinite(mean).all() or not np.isfinite(cov).all():
        raise ArithmeticError('Nonfinite GP posterior')
    return {'mean':mean.tolist(),'covariance':cov.tolist(),'kernel':'RBF',
            'noise_variance':noise,'scope':'Latent posterior; hyperparameters supplied, not fitted'}


def gaussian_copula(uniforms, correlation):
    """Gaussian copula log density at strictly interior marginal CDF values."""
    import numpy as np
    from scipy.special import ndtri
    from scipy.linalg import cho_factor, cho_solve
    u,r = _array(uniforms,1,64),_array(correlation,2,4096)
    if (u<=0).any() or (u>=1).any() or r.shape != (len(u),len(u)):
        raise ValueError('Interior CDF values and matching correlation required')
    if not np.allclose(r,r.T,atol=1e-12,rtol=0) or not np.allclose(np.diag(r),1,atol=1e-12,rtol=0):
        raise ValueError('Symmetric unit-diagonal correlation required')
    try:
        factor = cho_factor(r,lower=True)
    except np.linalg.LinAlgError as error:
        raise ValueError('Positive definite correlation required') from error
    z = ndtri(u)
    logdet = 2*float(np.log(np.diag(factor[0])).sum())
    return {'log_density': -.5*(logdet+float(z@cho_solve(factor,z)-z@z))}


def clayton_copula(uniforms, theta):
    """Positive-dependence Clayton family; theta=0 is independence."""
    import numpy as np
    u = _array(uniforms,1,64)
    if (u<=0).any() or (u>=1).any() or type(theta) not in (int,float) or not math.isfinite(theta) or not 0 <= theta <= 100:
        raise ValueError('Interior CDF values and 0<=theta<=100 required')
    if theta == 0:
        return {'cdf':float(u.prod()),'log_density':0.}
    logu = np.log(u)
    # sum(exp(-theta log u)) - d + 1, without overflowing at small u.
    logs = -theta*logu
    maximum = float(logs.max())
    logsum = (math.log1p(float(np.expm1(logs).sum())) if maximum < 1
              else maximum+math.log(float(np.exp(logs-maximum).sum())-(len(u)-1)*math.exp(-maximum)))
    log_density = sum(math.log1p(k*theta) for k in range(len(u)))
    log_density -= (1+theta)*float(logu.sum())+(len(u)+1/theta)*logsum
    return {'cdf': math.exp(-logsum/theta), 'log_density':log_density}


def calculate(action, **parameters):
    from .advanced_math import calculate as audited
    return audited('stochastic_info.'+action, **parameters)


__all__ = ['multivariate_ito','sde_system','stochastic_generator','fokker_planck_1d',
           'gaussian_information','discrete_information','channel_capacity',
           'gaussian_process','gaussian_copula','clayton_copula','calculate']

# Continuous information, exact Gaussian dynamics and state-space inference.
def gaussian_channel_capacity(noise_variances, power, gains=None, tolerance=1e-12):
    """Water filling over independent real Gaussian subchannels, bits/use.

    Channel is y_i = gain_i*x_i + noise_i, with independent noise variance N_i.
    The power constraint is sum E[x_i²]<=power. A real channel contributes
    (1/2)log2(1+gain_i²*P_i/N_i); this convention differs from complex channels.
    """
    import numpy as np
    noise=_array(noise_variances,1,4096)
    if (noise<=0).any():raise ValueError('Positive noise variances required')
    if type(power) not in (int,float) or not math.isfinite(power) or power<0:
        raise ValueError('Finite nonnegative total power required')
    gain=np.ones_like(noise) if gains is None else _array(gains,1,4096)
    if gain.shape!=noise.shape:raise ValueError('One gain per subchannel required')
    if not 0<tolerance<1:raise ValueError('Positive subunit tolerance required')
    active=np.flatnonzero(gain!=0)
    allocation=np.zeros_like(noise)
    if power==0 or not len(active):
        return {'capacity_bits':0.,'power':allocation.tolist(),'used_power':0.,'water_level':None}
    equivalent=noise[active]/gain[active]**2
    order=np.argsort(equivalent);sorted_noise=equivalent[order]
    prefix=0.;level=0.
    for count,value in enumerate(sorted_noise,1):
        prefix+=float(value);level=(power+prefix)/count
        if count==len(sorted_noise) or level<=sorted_noise[count]:break
    allocation[active]=np.maximum(level-equivalent,0.)
    used=float(allocation.sum())
    if abs(used-power)>tolerance*max(1,power):raise ArithmeticError('Water-filling power invariant failed')
    capacity=.5*float(np.log2(1+gain*gain*allocation/noise).sum())
    return {'capacity_bits':capacity,'power':allocation.tolist(),'used_power':used,
            'water_level':level,'convention':'Independent real additive Gaussian channels'}


def markov_entropy_rate(transition, stationary=None, tolerance=1e-10):
    """Shannon entropy rate for a finite stationary Markov source, bits/step.

    If no stationary vector is given, uniqueness must be numerically established
    by a one-dimensional nullspace. Reducible chains with several stationary
    laws require the caller to choose one explicitly.
    """
    import numpy as np
    from scipy.linalg import null_space
    matrix=_array(transition,2,65536)
    if matrix.shape[0]!=matrix.shape[1] or len(matrix)>256 or (matrix<0).any() or not np.allclose(matrix.sum(axis=1),1,atol=tolerance,rtol=0):
        raise ValueError('Square row-stochastic matrix required')
    if stationary is None:
        kernel=null_space(matrix.T-np.eye(len(matrix)),rcond=tolerance)
        if kernel.shape[1]!=1:raise ValueError('Stationary law is not unique; provide it explicitly')
        vector=kernel[:,0]
        if vector.sum()<0:vector=-vector
        vector=vector/vector.sum()
        if vector.min() < -tolerance:raise ArithmeticError('Stationary nullspace lost positivity')
        vector=np.maximum(vector,0);vector/=vector.sum()
    else:
        vector=_array(stationary,1,256)
        if vector.shape!=(len(matrix),) or (vector<0).any() or abs(vector.sum()-1)>tolerance or np.max(abs(vector@matrix-vector))>tolerance:
            raise ValueError('Provided law is not stationary and normalized')
    logarithms=np.zeros_like(matrix);mask=matrix>0
    logarithms[mask]=np.log2(matrix[mask])
    conditional=-(matrix*logarithms).sum(axis=1)
    return {'entropy_rate_bits':float(vector@conditional),'stationary':vector.tolist(),
            'conditional_entropies':conditional.tolist(),'stationarity_residual':float(np.max(abs(vector@matrix-vector)))}


def mutual_information(joint, base=2):
    """Exact-discrete-formula mutual information from a normalized joint table."""
    import numpy as np
    table=_array(joint,2,1000000)
    if (table<0).any() or abs(table.sum()-1)>1e-12:
        raise ValueError('Normalized nonnegative joint table required')
    if type(base) not in (int,float) or not math.isfinite(base) or base<=1:
        raise ValueError('Logarithm base greater than one required')
    left,right=table.sum(axis=1),table.sum(axis=0)
    independent=np.outer(left,right);mask=table>0
    value=float(np.sum(table[mask]*np.log(table[mask]/independent[mask]))/math.log(base))
    return {'mutual_information':value,'left_marginal':left.tolist(),'right_marginal':right.tolist(),
            'base':base,'scope':'Discrete law supplied by caller; no estimator bias correction'}


def conditional_mutual_information(joint, base=2):
    """I(X;Y|Z) for an explicit normalized tensor p[x,y,z]."""
    import numpy as np
    table=_array(joint,3,1000000)
    if (table<0).any() or abs(table.sum()-1)>1e-12 or base<=1 or not math.isfinite(base):
        raise ValueError('Normalized joint law and logarithm base >1 required')
    pz=table.sum(axis=(0,1));pxz=table.sum(axis=1);pyz=table.sum(axis=0)
    total=0.
    for z,mass in enumerate(pz):
        if mass==0:continue
        plane=table[:,:,z];mask=plane>0
        ratio=plane*mass/np.maximum(np.outer(pxz[:,z],pyz[:,z]),np.finfo(float).tiny)
        total+=float(np.sum(plane[mask]*np.log(ratio[mask])))
    return {'conditional_mutual_information':total/math.log(base),'conditioning_marginal':pz.tolist(),'base':base}


def renyi_entropy(probabilities, order, base=2):
    """Rényi entropy, with continuous Shannon limit at alpha=1."""
    import numpy as np
    from scipy.special import logsumexp
    p=_array(probabilities,1,65536)
    if (p<0).any() or abs(p.sum()-1)>1e-12 or not math.isfinite(base) or base<=1:
        raise ValueError('Normalized probability vector and base >1 required')
    if type(order) not in (int,float) or math.isnan(order) or order<0:
        raise ValueError('Nonnegative Renyi order required')
    positive=p[p>0]
    if order==0:value=math.log(len(positive))
    elif order==1:value=-float(np.sum(positive*np.log(positive)))
    elif order==math.inf:value=-math.log(float(p.max()))
    else:value=float(logsumexp(order*np.log(positive)))/(1-order)
    return {'entropy':value/math.log(base),'order':None if order==math.inf else order,
            'order_infinite':order==math.inf,'base':base}


def jensen_shannon(probabilities, reference, weight=.5, base=2):
    """Weighted Jensen–Shannon divergence, finite even for disjoint support."""
    import numpy as np
    p=_array(probabilities,1,4096);q=_array(reference,1,4096)
    if p.shape!=q.shape or not 0<weight<1:raise ValueError('Matching laws and interior mixture weight required')
    # Reuse normalization and base validation, but compute the mixed support here.
    discrete_information(p.tolist(),base=base);discrete_information(q.tolist(),base=base)
    mixture=weight*p+(1-weight)*q
    positive_p=p>0;positive_q=q>0
    value=weight*float(np.sum(p[positive_p]*np.log(p[positive_p]/mixture[positive_p])))
    value+=(1-weight)*float(np.sum(q[positive_q]*np.log(q[positive_q]/mixture[positive_q])))
    return {'divergence':value/math.log(base),'weight':weight,'base':base,
            'upper_bound':(-weight*math.log(weight)-(1-weight)*math.log(1-weight))/math.log(base)}


def continuous_information(log_density, variable, lower, upper, *, reference_log_density=None,
                           tolerance=1e-9):
    """Quadrature entropy/KL for a caller-supplied normalized continuous density.

    The domain is a finite interval. Reported errors are QUADPACK estimates;
    integrability, negligible tail mass and smoothness remain caller hypotheses.
    Normalization is checked and never silently repaired.
    """
    import numpy as np
    from scipy.integrate import quad
    sp=sympy();names([variable],1)
    if not all(type(v) in (int,float) and math.isfinite(v) for v in (lower,upper,tolerance)) or lower>=upper or not 0<tolerance<.1:
        raise ValueError('Finite increasing interval and positive tolerance required')
    source,symbols=expression(log_density,[variable])
    logp=sp.lambdify(symbols,source,modules='numpy',cse=True)
    logq=None
    if reference_log_density is not None:
        reference,_=expression(reference_log_density,[variable])
        logq=sp.lambdify(symbols,reference,modules='numpy',cse=True)
    def density(x):
        value=float(logp(x))
        if value==-math.inf:return 0.
        if not math.isfinite(value) or value>700:raise ValueError('Nonfinite or overflowing log density')
        return math.exp(value)
    mass,mass_error=quad(density,lower,upper,epsabs=tolerance,epsrel=tolerance,limit=256)
    if abs(mass-1)>max(10*tolerance,10*mass_error):
        raise ValueError('Density is not normalized on the integration interval')
    def entropy_integrand(x):
        value=density(x)
        return 0. if value==0 else -value*float(logp(x))
    entropy,error=quad(entropy_integrand,lower,upper,epsabs=tolerance,epsrel=tolerance,limit=256)
    result={'entropy_nats':entropy,'entropy_error_estimate':error,'mass':mass,'mass_error_estimate':mass_error}
    if logq is not None:
        def divergence(x):
            value=density(x)
            if value==0:return 0.
            reference=float(logq(x))
            if not math.isfinite(reference):raise ValueError('Reference log density is nonfinite on sampled support')
            return value*(float(logp(x))-reference)
        value,error=quad(divergence,lower,upper,epsabs=tolerance,epsrel=tolerance,limit=256)
        result.update({'kl_nats':value,'kl_error_estimate':error})
    return result


def ornstein_uhlenbeck(initial, mean, rate, volatility, times, *, seed=0, paths=1):
    """Exact OU transitions, including the rate=0 Brownian limit.

    dX=rate*(mean-X)dt+volatility*dW. The generated transition law is exact
    mathematically; its implementation uses floating-point Gaussian samples.
    The supplied seed and time grid determine the reproducible sampled paths.
    """
    import numpy as np
    grid=_array(times,1,10001)
    if len(grid)<2 or grid[0]!=0 or (np.diff(grid)<=0).any():raise ValueError('Increasing time grid starting at zero required')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (initial,mean,rate,volatility)) or rate<0 or volatility<0:
        raise ValueError('Finite OU parameters with nonnegative rate/volatility required')
    if type(paths) is not int or not 1<=paths<=10000 or paths*len(grid)>1000000 or type(seed) is not int or not 0<=seed<2**64:
        raise ValueError('OU sampling budget or seed invalid')
    rng=np.random.default_rng(seed);values=np.empty((paths,len(grid)));values[:,0]=initial
    for i,dt in enumerate(np.diff(grid),1):
        decay=math.exp(-rate*dt)
        variance=volatility**2*dt if rate==0 else -volatility**2*math.expm1(-2*rate*dt)/(2*rate)
        values[:,i]=mean+(values[:,i-1]-mean)*decay+math.sqrt(variance)*rng.standard_normal(paths)
    analytic_mean=mean+(initial-mean)*np.exp(-rate*grid)
    analytic_variance=volatility**2*grid if rate==0 else -volatility**2*np.expm1(-2*rate*grid)/(2*rate)
    return {'times':grid.tolist(),'paths':values.tolist(),'mean':analytic_mean.tolist(),
            'variance':analytic_variance.tolist(),'seed':seed,'transition':'exact Gaussian OU'}


def brownian_bridge(start, end, duration, times, *, seed=0, paths=1):
    """Sample a Brownian bridge using W_t−(t/T)W_T on an arbitrary time grid."""
    import numpy as np
    duration=_positive(duration,'duration');grid=_array(times,1,10001)
    if len(grid)<2 or grid[0]!=0 or grid[-1]!=duration or (np.diff(grid)<=0).any():
        raise ValueError('Increasing bridge grid must include 0 and duration exactly')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (start,end)):
        raise ValueError('Finite bridge endpoints required')
    if type(paths) is not int or not 1<=paths<=10000 or paths*len(grid)>1000000 or type(seed) is not int or not 0<=seed<2**64:
        raise ValueError('Bridge sampling budget or seed invalid')
    rng=np.random.default_rng(seed)
    increments=rng.standard_normal((paths,len(grid)-1))*np.sqrt(np.diff(grid))
    brownian=np.column_stack((np.zeros(paths),np.cumsum(increments,axis=1)))
    fraction=grid/duration
    values=start+(end-start)*fraction+brownian-brownian[:,-1,None]*fraction
    values[:,0]=start;values[:,-1]=end
    return {'times':grid.tolist(),'paths':values.tolist(),'mean':(start+(end-start)*fraction).tolist(),
            'variance':(grid*(1-fraction)).tolist(),'seed':seed}


def linear_sde_transition(drift_matrix, diffusion_matrix, duration, offset=None):
    """Van Loan matrix-exponential transition for dX=(A X+b)dt+B dW.

    The block exponential evaluates Q=integral exp(A s) B Bᵀ exp(Aᵀ s) ds
    without numerical time stepping. Matrix exponential errors remain floating
    point; covariance symmetry and PSD are checked to numerical tolerance.
    """
    import numpy as np
    from scipy.linalg import expm
    a=_array(drift_matrix,2,1024);b=_array(diffusion_matrix,2,1024)
    n=len(a)
    if a.shape!=(n,n) or n>32 or b.shape[0]!=n:raise ValueError('Matching bounded linear SDE matrices required')
    duration=_positive(duration,'duration')
    shift=np.zeros(n) if offset is None else _array(offset,1,32)
    if shift.shape!=(n,):raise ValueError('Drift offset dimension mismatch')
    block=np.zeros((2*n,2*n));block[:n,:n]=a;block[:n,n:]=b@b.T;block[n:,n:]=-a.T
    exponential=expm(block*duration)
    transition=exponential[:n,:n]
    covariance=exponential[:n,n:]@transition.T
    covariance=(covariance+covariance.T)/2
    augmented=np.zeros((n+1,n+1));augmented[:n,:n]=a;augmented[:n,n]=shift
    displacement=expm(augmented*duration)[:n,n]
    if not np.isfinite(exponential).all() or np.linalg.eigvalsh(covariance).min() < -1e-9*max(1,float(np.linalg.norm(covariance))):
        raise ArithmeticError('Linear SDE transition overflowed or covariance lost PSD')
    return {'transition':transition.tolist(),'offset':displacement.tolist(),'covariance':covariance.tolist(),
            'duration':duration,'method':'Van Loan block exponential'}


def _covariance(value, dimension, name, *, positive_definite=False):
    import numpy as np
    matrix=_array(value,2,65536)
    if matrix.shape!=(dimension,dimension) or not np.allclose(matrix,matrix.T,atol=1e-12,rtol=1e-12):
        raise ValueError(name+' must be a symmetric matching matrix')
    eigenvalues=np.linalg.eigvalsh(matrix)
    threshold=1e-12*max(1,float(np.linalg.norm(matrix)))
    if eigenvalues.min() < -threshold or (positive_definite and eigenvalues.min()<=0):
        raise ValueError(name+' must be '+('positive definite' if positive_definite else 'positive semidefinite'))
    return matrix


def kalman_filter(observations, transition, observation_matrix, process_covariance,
                  observation_covariance, initial_mean, initial_covariance):
    """Linear Gaussian filter with Joseph covariance updates and missing rows.

    Each observation row may be null to represent an entirely missing time
    sample. The first row updates the initial prior directly; transition is
    applied before subsequent rows. Log likelihood uses observed rows only.
    """
    import numpy as np
    from scipy.linalg import cho_factor,cho_solve
    mean=_array(initial_mean,1,64);n=len(mean)
    covariance=_covariance(initial_covariance,n,'Initial covariance')
    a=_array(transition,2,4096);h=_array(observation_matrix,2,4096);m=len(h)
    if a.shape!=(n,n) or h.shape[1]!=n or not 1<=m<=64:
        raise ValueError('State/observation dimensions differ')
    q=_covariance(process_covariance,n,'Process covariance')
    r=_covariance(observation_covariance,m,'Observation covariance',positive_definite=True)
    if not isinstance(observations,(list,tuple)) or not 1<=len(observations)<=10000 or len(observations)*n*n>1000000:
        raise ValueError('Kalman history budget exceeded')
    filtered=[];predicted=[];innovations=[];log_likelihood=0.
    identity=np.eye(n)
    for index,row in enumerate(observations):
        if index:
            mean=a@mean;covariance=a@covariance@a.T+q
            covariance=(covariance+covariance.T)/2
        predicted.append({'mean':mean.tolist(),'covariance':covariance.tolist()})
        if row is None:
            innovations.append(None)
        else:
            observation=_array(row,1,64)
            if observation.shape!=(m,):raise ValueError('Observation row dimension mismatch')
            innovation=observation-h@mean
            residual_covariance=h@covariance@h.T+r
            try:factor=cho_factor(residual_covariance,lower=True)
            except np.linalg.LinAlgError as error:raise ArithmeticError('Innovation covariance is not positive definite') from error
            gain=cho_solve(factor,h@covariance).T
            mean=mean+gain@innovation
            residual=identity-gain@h
            covariance=residual@covariance@residual.T+gain@r@gain.T
            covariance=(covariance+covariance.T)/2
            logdet=2*float(np.log(np.diag(factor[0])).sum())
            log_likelihood-=.5*(m*math.log(2*math.pi)+logdet+float(innovation@cho_solve(factor,innovation)))
            innovations.append({'residual':innovation.tolist(),'covariance':residual_covariance.tolist(),'gain':gain.tolist()})
        if not np.isfinite(mean).all() or not np.isfinite(covariance).all():raise ArithmeticError('Kalman state became nonfinite')
        filtered.append({'mean':mean.tolist(),'covariance':covariance.tolist()})
    return {'filtered':filtered,'predicted':predicted,'innovations':innovations,
            'log_likelihood':log_likelihood,'convention':'First sample observes initial prior'}


def rts_smoother(filter_result, transition):
    """Rauch–Tung–Striebel backward smoothing of a recorded Kalman history."""
    import numpy as np
    from scipy.linalg import cho_factor,cho_solve
    if not isinstance(filter_result,dict) or not {'filtered','predicted'} <= set(filter_result):
        raise ValueError('Kalman filtering result required')
    filtered=filter_result['filtered'];predicted=filter_result['predicted']
    if not filtered or len(filtered)!=len(predicted) or len(filtered)>10000:
        raise ValueError('Matching nonempty filtering histories required')
    n=len(filtered[0]['mean']);a=_array(transition,2,4096)
    if a.shape!=(n,n):raise ValueError('Smoothing transition dimension mismatch')
    means=[_array(row['mean'],1,64) for row in filtered]
    covariances=[_covariance(row['covariance'],n,'Filtered covariance') for row in filtered]
    if any(value.shape!=(n,) for value in means):raise ValueError('Filtering means have inconsistent dimensions')
    gains=[None]*max(0,len(filtered)-1)
    for k in range(len(filtered)-2,-1,-1):
        prior=_covariance(predicted[k+1]['covariance'],n,'Prediction covariance',positive_definite=True)
        prior_mean=_array(predicted[k+1]['mean'],1,64)
        factor=cho_factor(prior,lower=True)
        gain=cho_solve(factor,a@covariances[k]).T
        means[k]=means[k]+gain@(means[k+1]-prior_mean)
        covariances[k]=covariances[k]+gain@(covariances[k+1]-prior)@gain.T
        covariances[k]=(covariances[k]+covariances[k].T)/2
        gains[k]=gain.tolist()
    return {'smoothed':[{'mean':m.tolist(),'covariance':c.tolist()} for m,c in zip(means,covariances)],
            'gains':gains,'scope':'Linear Gaussian fixed-interval smoothing'}


__all__ += ['gaussian_channel_capacity','markov_entropy_rate','mutual_information',
            'conditional_mutual_information','renyi_entropy','jensen_shannon',
            'continuous_information','ornstein_uhlenbeck','brownian_bridge',
            'linear_sde_transition','kalman_filter','rts_smoother']


class ItoCalculus:
    """Closed-expression multivariate Ito calculus for independent Wiener drivers."""
    def __init__(self, variables, drift, diffusion, time='t', convention='ito'):
        self.variables=names(variables,4);self.time=time
        names(list(self.variables)+[time],5)
        n=len(self.variables)
        if len(drift)!=n or len(diffusion)!=n or not diffusion[0]:raise ValueError('SDE coefficient dimensions differ')
        m=len(diffusion[0])
        if not 1<=m<=4 or any(len(row)!=m for row in diffusion):raise ValueError('Rectangular diffusion with 1–4 noises required')
        if convention not in ('ito','stratonovich'):raise ValueError('Convention must be ito or stratonovich')
        self.symbols=tuple(map(sympy().Symbol,self.variables));self.time_symbol=sympy().Symbol(time)
        allowed=list(self.variables)+[time]
        self.diffusion=sympy().Matrix([[expression(v,allowed)[0] for v in row] for row in diffusion])
        declared=[expression(v,allowed)[0] for v in drift]
        correction=self.correction()
        self.drift=tuple(sympy().simplify(v+c) if convention=='stratonovich' else v for v,c in zip(declared,correction))
        self.convention=convention

    def correction(self):
        n=len(self.variables);m=self.diffusion.cols;sp=sympy()
        return tuple(sp.simplify(sum(self.diffusion[j,k]*sp.diff(self.diffusion[i,k],self.symbols[j])
                                     for j in range(n) for k in range(m))/2) for i in range(n))

    def ito_to_stratonovich(self):
        return [str(sympy().simplify(v-c)) for v,c in zip(self.drift,self.correction())]

    def lemma(self, function):
        sp=sympy();allowed=list(self.variables)+[self.time]
        value=expression(function,allowed)[0]
        gradient=sp.Matrix([sp.diff(value,x) for x in self.symbols])
        hessian=sp.hessian(value,self.symbols);covariance=self.diffusion*self.diffusion.T
        drift=sp.diff(value,self.time_symbol)+sum(a*b for a,b in zip(self.drift,gradient))
        drift+=sum(covariance[i,j]*hessian[i,j]/2 for i in range(len(self.variables)) for j in range(len(self.variables)))
        noise=gradient.T*self.diffusion
        return {'drift':str(sp.simplify(drift)),'diffusion':[str(sp.simplify(v)) for v in noise],
                'ito_drift':list(map(str,self.drift)),'stratonovich_drift':self.ito_to_stratonovich(),
                'hypotheses':'C1 in time, C2 in space; local semimartingale Ito formula'}

    def lie_noise_derivatives(self):
        """L_j B_i,k for the Milstein correction and commutativity check."""
        n=len(self.variables);m=self.diffusion.cols;sp=sympy()
        return tuple(tuple(tuple(sp.simplify(sum(self.diffusion[l,j]*sp.diff(self.diffusion[i,k],self.symbols[l])
                                                for l in range(n))) for k in range(m)) for j in range(m)) for i in range(n))

    def commuting_noise(self):
        derivative=self.lie_noise_derivatives();m=self.diffusion.cols
        residual=[]
        for j in range(m):
            for k in range(j+1,m):
                residual.append([str(sympy().simplify(derivative[i][j][k]-derivative[i][k][j])) for i in range(len(self.variables))])
        return {'commuting':all(v=='0' for row in residual for v in row),'bracket_residuals':residual}


class SDESolver:
    """Euler–Maruyama and commutative-noise Milstein with recorded increments.

    Strong orders 1/2 and 1 are theoretical under the usual smoothness, growth
    and Lipschitz hypotheses, not promises for arbitrary coefficient strings.
    Noncommuting multidimensional noise requires Levy-area simulation and is
    explicitly refused by Milstein rather than silently approximated as zero.
    """
    def __init__(self, variables, drift, diffusion, *, time='t', convention='ito'):
        self.calculus=ItoCalculus(variables,drift,diffusion,time,convention)
        self.variables=self.calculus.variables
        self.drift=drift;self.diffusion=diffusion;self.time=time;self.convention=convention

    def solve(self, initial, duration=1., steps=1000, *, seed=0, method='euler_maruyama',
              paths=1, increments=None, store_increments=False):
        import numpy as np
        n=len(self.variables);m=self.calculus.diffusion.cols
        state=_array(initial,1,4)
        if state.shape!=(n,):raise ValueError('Initial state dimension differs')
        duration=_positive(duration,'duration')
        if type(steps) is not int or not 1<=steps<=100000 or type(paths) is not int or not 1<=paths<=10000:
            raise ValueError('Invalid SDE trajectory dimensions')
        if steps*paths*max(n,m)>2000000:raise ValueError('SDE history budget exceeded')
        if type(seed) is not int or not 0<=seed<2**64:raise ValueError('Seed must be an unsigned 64-bit integer')
        if method not in ('euler_maruyama','milstein'):raise ValueError('Unknown SDE integration scheme')
        if type(store_increments) is not bool:raise ValueError('store_increments must be boolean')
        if method=='milstein' and not self.calculus.commuting_noise()['commuting']:
            raise ValueError('Milstein requires commuting noise; Levy areas are not supplied')
        dt=duration/steps;rng=np.random.Generator(np.random.PCG64(seed))
        if increments is None:
            brownian=rng.standard_normal((steps,paths,m))*math.sqrt(dt)
        else:
            brownian=_array(increments,maximum=2000000)
            if brownian.shape==(steps,m) and paths==1:brownian=brownian[:,None,:]
            if brownian.shape!=(steps,paths,m):raise ValueError('Increment tensor must have shape (steps,paths,noises)')
        arguments=[self.calculus.time_symbol]+list(self.calculus.symbols)
        drift=[sympy().lambdify(arguments,v,modules='numpy',cse=True) for v in self.calculus.drift]
        diffusion=[[sympy().lambdify(arguments,self.calculus.diffusion[i,j],modules='numpy',cse=True) for j in range(m)] for i in range(n)]
        derivatives=None
        if method=='milstein':
            derivatives=[[[sympy().lambdify(arguments,v,modules='numpy',cse=True) for v in row] for row in layer]
                         for layer in self.calculus.lie_noise_derivatives()]
        history=np.empty((steps+1,paths,n));history[0]=state
        state=np.broadcast_to(state,(paths,n)).copy()
        identity=np.eye(m)
        def vector(function,args):
            value=np.asarray(function(*args),dtype=float)
            return np.broadcast_to(value,(paths,))
        for step in range(steps):
            args=[step*dt]+[state[:,i] for i in range(n)]
            a=np.column_stack([vector(f,args) for f in drift])
            b=np.stack([np.column_stack([vector(f,args) for f in row]) for row in diffusion],axis=1)
            update=a*dt+np.einsum('pij,pj->pi',b,brownian[step])
            if derivatives is not None:
                double=np.einsum('pj,pk->pjk',brownian[step],brownian[step])-dt*identity
                for i in range(n):
                    for j in range(m):
                        for k in range(m):update[:,i]+=.5*vector(derivatives[i][j][k],args)*double[:,j,k]
            state=state+update
            if not np.isfinite(state).all():raise ArithmeticError('SDE became nonfinite at step '+str(step+1))
            history[step+1]=state
        from ..core.semantic_ir import fingerprint
        increment_id=fingerprint(brownian.tolist())
        result={'times':np.linspace(0,duration,steps+1).tolist(),'states':history.tolist(),
                'seed':seed,'generator':'numpy.PCG64','method':method,'time_step':dt,
                'increments_sha256':increment_id,'increments_source':'generated' if increments is None else 'provided',
                'strong_order_under_regular_hypotheses':.5 if method=='euler_maruyama' else 1.,
                'hypotheses':'Regularity/growth conditions required; no certified pathwise error bound'}
        if store_increments:result['increments']=brownian.tolist()
        return result

    def coupled_refinement(self, initial, duration=1., coarse_steps=100, *, seed=0,
                           paths=1, method='milstein'):
        """Couple two levels by summing pairs of the SAME fine Brownian increments."""
        import numpy as np
        if type(coarse_steps) is not int or not 1<=coarse_steps<=50000:raise ValueError('Refinement step budget exceeded')
        fine=self.solve(initial,duration,coarse_steps*2,seed=seed,paths=paths,method=method,store_increments=True)
        increments=np.asarray(fine['increments'])
        coarse_increments=increments.reshape(coarse_steps,2,paths,self.calculus.diffusion.cols).sum(axis=1)
        coarse=self.solve(initial,duration,coarse_steps,seed=seed,paths=paths,method=method,increments=coarse_increments)
        difference=np.asarray(fine['states'])[-1]-np.asarray(coarse['states'])[-1]
        return {'coarse':coarse,'fine':{k:v for k,v in fine.items() if k!='increments'},
                'terminal_rms_difference':float(np.sqrt(np.mean(difference*difference))),
                'scope':'Coupled level difference; not a proof of strong convergence or error estimate against the exact path'}


class FokkerPlanckPDE:
    """Conservative finite-volume generator with variable drift and diffusion.

    On uniform cell centers, the Ito flux is a*p - d(D*p)/dx, D=σ²/2.
    At each face, rates right=max(a,0)/dx+D_left/dx² and
    left=max(-a,0)/dx+D_right/dx² form a continuous-time Markov generator.
    Reflecting endpoints remove outward rates. This preserves total mass and
    positivity under exact matrix exponentiation, or explicit Euler with CFL.
    """
    def __init__(self, centers, drift, diffusion):
        import numpy as np
        self.centers=_array(centers,1,10000)
        if len(self.centers)<2:raise ValueError('At least two cell centers required')
        differences=np.diff(self.centers)
        if (differences<=0).any() or not np.allclose(differences,differences[0],atol=1e-12,rtol=1e-10):
            raise ValueError('Uniform increasing finite-volume cell centers required')
        self.spacing=float(differences[0]);self.drift=_array(drift,1,10000);self.diffusion=_array(diffusion,1,10000)
        if self.drift.shape!=self.centers.shape or self.diffusion.shape!=self.centers.shape or (self.diffusion<0).any():
            raise ValueError('One finite drift and nonnegative D=σ²/2 per cell required')

    def generator(self):
        import numpy as np
        from scipy.sparse import diags
        dx=self.spacing;face=(self.drift[:-1]+self.drift[1:])/2
        right=np.maximum(face,0)/dx+self.diffusion[:-1]/dx**2
        left=np.maximum(-face,0)/dx+self.diffusion[1:]/dx**2
        diagonal=np.zeros(len(self.centers));diagonal[:-1]-=right;diagonal[1:]-=left
        return diags([right,diagonal,left],[-1,0,1],format='csc')

    def stationary(self):
        """Stationary law of an irreducible birth-death generator via log ratios."""
        import numpy as np
        from scipy.special import logsumexp
        generator=self.generator()
        right=generator.diagonal(-1);left=generator.diagonal(1)
        if (right<=0).any() or (left<=0).any():
            raise ValueError('Unique positive stationary law requires positive rates across every face')
        logarithms=np.concatenate(([0.],np.cumsum(np.log(right)-np.log(left))))
        probability=np.exp(logarithms-logsumexp(logarithms))
        return {'density':(probability/self.spacing).tolist(),'mass':1.,
                'generator_residual':float(np.max(abs(generator@probability)))}

    def solve(self, density, duration=1., steps=100, method='exponential'):
        import numpy as np
        from scipy.sparse.linalg import expm_multiply
        initial=_array(density,1,10000)
        if initial.shape!=self.centers.shape or (initial<0).any() or initial.sum()<=0:
            raise ValueError('Nonnegative density matching the grid with positive mass required')
        duration=_positive(duration,'duration')
        if type(steps) is not int or not 1<=steps<=10000 or steps*len(initial)>1000000:
            raise ValueError('Fokker–Planck evolution budget exceeded')
        if method not in ('exponential','explicit'):raise ValueError('Method is exponential or explicit')
        generator=self.generator();dt=duration/steps
        cfl=float(-generator.diagonal().min()*dt)
        if method=='explicit' and cfl>1:raise ValueError('Finite-volume positivity CFL exceeded')
        if method=='exponential':history=expm_multiply(generator,initial,start=0,stop=duration,num=steps+1,endpoint=True)
        else:
            history=np.empty((steps+1,len(initial)));history[0]=initial
            for i in range(steps):history[i+1]=history[i]+dt*(generator@history[i])
        masses=history.sum(axis=1)*self.spacing
        if not np.isfinite(history).all() or history.min() < -1e-12*max(1,float(initial.max())):
            raise ArithmeticError('Fokker–Planck evolution lost positivity or finiteness')
        return {'centers':self.centers.tolist(),'times':np.linspace(0,duration,steps+1).tolist(),
                'density':history.tolist(),'masses':masses.tolist(),
                'maximum_mass_drift':float(np.max(abs(masses-masses[0]))),'cfl':cfl,
                'method':method,'boundary':'reflecting zero flux',
                'scope':'Variable-coefficient spatial discretization; time-independent coefficients; spatial error not certified'}


class InformationMetrics:
    """Consistent information metrics with explicit support and logarithm base."""
    shannon=staticmethod(discrete_information)
    differential=staticmethod(continuous_information)
    mutual=staticmethod(mutual_information)
    conditional_mutual=staticmethod(conditional_mutual_information)
    gaussian=staticmethod(gaussian_information)
    renyi=staticmethod(renyi_entropy)
    jensen_shannon=staticmethod(jensen_shannon)

    @staticmethod
    def cross_entropy(probabilities, reference, base=2):
        result=discrete_information(probabilities,reference,base)
        return {'cross_entropy':None if result['kl_infinite'] else result['entropy']+result['kl'],
                'infinite':result['kl_infinite'],'base':base}

    @staticmethod
    def kl(probabilities, reference, base=2):
        result=discrete_information(probabilities,reference,base)
        return {'divergence':result['kl'],'infinite':result['kl_infinite'],'base':base}


def gumbel_copula(uniforms, theta):
    """Gumbel–Hougaard copula CDF and bivariate log density, theta>=1.

    Higher-dimensional CDFs are supported; density above dimension two is
    deliberately absent rather than returning a bivariate formula unchanged.
    """
    import numpy as np
    from scipy.special import logsumexp
    u=_array(uniforms,1,64)
    if (u<=0).any() or (u>=1).any() or type(theta) not in (int,float) or not math.isfinite(theta) or not 1<=theta<=100:
        raise ValueError('Interior CDF values and 1<=theta<=100 required')
    t=-np.log(u);logs=theta*np.log(t);logsum=float(logsumexp(logs));root=math.exp(logsum/theta)
    result={'cdf':math.exp(-root),'theta':theta}
    if len(u)==2:
        log_density=-root-float(np.log(u).sum())+(theta-1)*float(np.log(t).sum())
        log_density+=(2/theta-2)*logsum+math.log1p((theta-1)/root)
        result['log_density']=log_density
    else:result['density_status']='Only bivariate density implemented'
    return result


class CopulaEngine:
    """Dependence models, reproducible Gaussian sampling and rank diagnostics."""
    gaussian=staticmethod(gaussian_copula)
    clayton=staticmethod(clayton_copula)
    gumbel=staticmethod(gumbel_copula)

    @staticmethod
    def sample_gaussian(correlation, samples=1000, seed=0):
        import numpy as np
        from scipy.special import ndtr
        matrix=_array(correlation,2,4096);n=len(matrix)
        matrix=_covariance(matrix,n,'Correlation',positive_definite=True)
        if not np.allclose(np.diag(matrix),1,atol=1e-12,rtol=0):raise ValueError('Correlation diagonal must be one')
        if type(samples) is not int or not 1<=samples<=100000 or n*samples>1000000 or type(seed) is not int or not 0<=seed<2**64:
            raise ValueError('Copula sampling budget or seed invalid')
        rng=np.random.Generator(np.random.PCG64(seed))
        normal=rng.standard_normal((samples,n))@np.linalg.cholesky(matrix).T
        uniforms=ndtr(normal)
        return {'uniforms':uniforms.tolist(),'seed':seed,'generator':'numpy.PCG64','correlation':matrix.tolist(),
                'scope':'Gaussian copula samples; marginal inverse CDFs are supplied by the caller'}

    @staticmethod
    def empirical_dependence(samples):
        import numpy as np
        from scipy.stats import kendalltau,spearmanr
        values=_array(samples,2,1000000);n=values.shape[1]
        if not 2<=len(values)<=100000 or not 1<=n<=64:raise ValueError('Dependence sample budget exceeded')
        if np.any(np.std(values,axis=0)==0):raise ValueError('Rank dependence is undefined for constant marginals')
        kendall=np.eye(n);spearman=np.eye(n)
        for i in range(n):
            for j in range(i):
                kendall[i,j]=kendall[j,i]=float(kendalltau(values[:,i],values[:,j]).statistic)
                spearman[i,j]=spearman[j,i]=float(spearmanr(values[:,i],values[:,j]).statistic)
        return {'kendall_tau':kendall.tolist(),'spearman_rho':spearman.tolist(),'samples':len(values),
                'scope':'Empirical rank dependence; no causal or convergence claim'}


def sde_euler_maruyama(variables, drift, diffusion, initial, duration=1., steps=1000,
                       seed=0, paths=1, convention='ito'):
    return SDESolver(variables,drift,diffusion,convention=convention).solve(initial,duration,steps,seed=seed,paths=paths)


def sde_milstein(variables, drift, diffusion, initial, duration=1., steps=1000,
                 seed=0, paths=1, convention='ito'):
    return SDESolver(variables,drift,diffusion,convention=convention).solve(initial,duration,steps,seed=seed,paths=paths,method='milstein')


def fokker_planck_solve(centers, drift, diffusion, density, duration=1., steps=100,
                       method='exponential'):
    return FokkerPlanckPDE(centers,drift,diffusion).solve(density,duration,steps,method)


def information_divergence_kl(probabilities, reference, base=2):
    return InformationMetrics.kl(probabilities,reference,base)


__all__ += ['ItoCalculus','SDESolver','FokkerPlanckPDE','InformationMetrics','CopulaEngine',
            'gumbel_copula','sde_euler_maruyama','sde_milstein','fokker_planck_solve',
            'information_divergence_kl']


class GaussianProcessRegressor:
    """Gaussian-process inference with optimized hyperparameters and gradients.

    Kernels are stationary RBF, Matérn-3/2 and Matérn-5/2 with isotropic length
    scale. Hyperparameters are fitted in log coordinates by marginal likelihood.
    Reported posterior variances condition on the fitted parameters: parameter
    uncertainty and model misspecification are not integrated out.
    """
    def __init__(self, train_x, train_y, *, kernel='rbf', length_scale=1.,
                 variance=1., noise=1e-6):
        import numpy as np
        self.x=_array(train_x,2,32768);self.y=_array(train_y,1,512)
        if len(self.x)!=len(self.y) or len(self.x)>512 or self.x.shape[1]>64:
            raise ValueError('GP requires matching observations within the dense 512-point budget')
        if kernel not in ('rbf','matern32','matern52'):raise ValueError('Kernel is rbf, matern32 or matern52')
        self.kernel=kernel;self.length_scale=_positive(length_scale,'length scale');self.variance=_positive(variance,'variance')
        self.noise=_positive(noise,'noise variance');self._factor=None;self._alpha=None

    def covariance(self, left, right, *, parameters=None):
        import numpy as np
        a=_array(left,2,32768);b=_array(right,2,32768)
        if a.shape[1]!=self.x.shape[1] or b.shape[1]!=a.shape[1]:raise ValueError('GP feature dimensions differ')
        length,variance,_=(self.length_scale,self.variance,self.noise) if parameters is None else parameters
        length=_positive(length,'length scale');variance=_positive(variance,'variance')
        squared=np.sum(((a[:,None,:]-b[None,:,:])/length)**2,axis=2)
        if self.kernel=='rbf':return variance*np.exp(-squared/2)
        radius=np.sqrt(np.maximum(squared,0))
        if self.kernel=='matern32':
            scaled=math.sqrt(3)*radius
            return variance*(1+scaled)*np.exp(-scaled)
        scaled=math.sqrt(5)*radius
        return variance*(1+scaled+scaled*scaled/3)*np.exp(-scaled)

    def _prepare(self):
        import numpy as np
        from scipy.linalg import cho_factor,cho_solve
        try:self._factor=cho_factor(self.covariance(self.x,self.x)+self.noise*np.eye(len(self.x)),lower=True)
        except np.linalg.LinAlgError as error:raise ValueError('GP covariance is numerically singular') from error
        self._alpha=cho_solve(self._factor,self.y)

    def log_marginal_likelihood(self, parameters=None):
        import numpy as np
        from scipy.linalg import cho_factor,cho_solve
        parameters=(self.length_scale,self.variance,self.noise) if parameters is None else tuple(parameters)
        if len(parameters)!=3 or any(not math.isfinite(v) or v<=0 for v in parameters):
            raise ValueError('Three positive GP hyperparameters required')
        matrix=self.covariance(self.x,self.x,parameters=parameters)+parameters[2]*np.eye(len(self.x))
        try:factor=cho_factor(matrix,lower=True)
        except np.linalg.LinAlgError as error:raise ValueError('GP covariance is not positive definite') from error
        quadratic=float(self.y@cho_solve(factor,self.y));logdet=2*float(np.log(np.diag(factor[0])).sum())
        return -.5*(quadratic+logdet+len(self.x)*math.log(2*math.pi))

    def fit(self, *, bounds=((1e-3,1e3),(1e-6,1e6),(1e-10,1e2)), max_iterations=100):
        import numpy as np
        from scipy.optimize import minimize
        box=np.asarray(bounds,dtype=float)
        if box.shape!=(3,2) or not np.isfinite(box).all() or (box[:,0]<=0).any() or np.any(box[:,1]<=box[:,0]):
            raise ValueError('Three positive increasing hyperparameter intervals required')
        if type(max_iterations) is not int or not 1<=max_iterations<=1000:raise ValueError('GP optimization budget invalid')
        guess=np.log([self.length_scale,self.variance,self.noise]);guess=np.clip(guess,np.log(box[:,0]),np.log(box[:,1]))
        def objective(log_parameters):
            try:return -self.log_marginal_likelihood(np.exp(log_parameters))
            except (ValueError,ArithmeticError):return 1e100
        result=minimize(objective,guess,method='L-BFGS-B',bounds=np.log(box),options={'maxiter':max_iterations})
        parameters=np.exp(result.x)
        self.length_scale,self.variance,self.noise=map(float,parameters);self._prepare()
        return {'converged':bool(result.success),'message':str(result.message),'iterations':result.nit,
                'length_scale':self.length_scale,'variance':self.variance,'noise_variance':self.noise,
                'log_marginal_likelihood':self.log_marginal_likelihood(),
                'scope':'Local hyperparameter optimum; no global optimization or calibration claim'}

    def predict(self, query_x, *, observation_noise=False):
        import numpy as np
        from scipy.linalg import cho_solve
        query=_array(query_x,2,32768)
        if len(query)>512 or query.shape[1]!=self.x.shape[1]:raise ValueError('GP query budget/dimension mismatch')
        if type(observation_noise) is not bool:raise ValueError('observation_noise must be boolean')
        self._prepare();cross=self.covariance(query,self.x)
        mean=cross@self._alpha
        covariance=self.covariance(query,query)-cross@cho_solve(self._factor,cross.T)
        covariance=(covariance+covariance.T)/2
        if observation_noise:covariance+=self.noise*np.eye(len(query))
        diagonal=np.diag(covariance)
        if diagonal.min() < -1e-10*max(1,self.variance):raise ArithmeticError('GP posterior variance became negative beyond rounding tolerance')
        deviation=np.sqrt(np.maximum(diagonal,0))
        return {'mean':mean.tolist(),'covariance':covariance.tolist(),'standard_deviation':deviation.tolist(),
                'gaussian_95_percent_interval':np.column_stack((mean-1.959963984540054*deviation,mean+1.959963984540054*deviation)).tolist(),
                'interval_scope':'Conditional Gaussian posterior, hyperparameters treated as fixed'}

    def mean_gradient(self, query_x):
        """Analytic gradient of the posterior mean for all three kernels."""
        import numpy as np
        query=_array(query_x,2,32768)
        if len(query)>512 or query.shape[1]!=self.x.shape[1]:raise ValueError('GP gradient query dimensions differ')
        self._prepare();difference=query[:,None,:]-self.x[None,:,:]
        radius=np.linalg.norm(difference,axis=2)/self.length_scale
        if self.kernel=='rbf':factor=-self.covariance(query,self.x)/self.length_scale**2
        elif self.kernel=='matern32':factor=-3*self.variance*np.exp(-math.sqrt(3)*radius)/self.length_scale**2
        else:factor=-(5/3)*self.variance*(1+math.sqrt(5)*radius)*np.exp(-math.sqrt(5)*radius)/self.length_scale**2
        gradient=np.einsum('qnd,qn,n->qd',difference,factor,self._alpha)
        return {'gradient':gradient.tolist(),'kernel':self.kernel,'scope':'Derivative of conditional posterior mean'}


class StatisticalInformationGeometry:
    """Fisher metrics and coordinate KL curvature for basic statistical families."""
    @staticmethod
    def bernoulli(probability):
        if type(probability) not in (int,float) or not math.isfinite(probability) or not 0<probability<1:
            raise ValueError('Interior Bernoulli probability required')
        return {'fisher':[[1/(probability*(1-probability))]],'coordinate':'probability',
                'natural_coordinate':math.log(probability/(1-probability))}

    @staticmethod
    def normal(mean, standard_deviation):
        if type(mean) not in (int,float) or not math.isfinite(mean):raise ValueError('Finite normal mean required')
        sigma=_positive(standard_deviation,'standard deviation')
        return {'fisher':[[1/sigma**2,0.],[0.,2/sigma**2]],'coordinates':['mean','standard_deviation'],
                'gaussian_curvature':-.5}

    @staticmethod
    def categorical(probabilities):
        import numpy as np
        p=_array(probabilities,1,256)
        if len(p)<2 or (p<=0).any() or abs(p.sum()-1)>1e-12:raise ValueError('Interior normalized categorical law required')
        # Last category is 1-sum(first n-1), so its derivative contributes to
        # every matrix element instead of pretending all n coordinates are free.
        fisher=np.diag(1/p[:-1])+np.ones((len(p)-1,len(p)-1))/p[-1]
        return {'fisher':fisher.tolist(),'coordinates':'First n-1 probabilities; last probability is constrained'}

    @staticmethod
    def exponential_family(log_partition, parameters, point):
        sp=sympy();parameters=names(parameters,8)
        if len(point)!=len(parameters):raise ValueError('One natural-parameter value per dimension required')
        value,symbols=expression(log_partition,parameters)
        substitution={symbol:expression(coordinate,parameters)[0] for symbol,coordinate in zip(symbols,point)}
        if any(v.free_symbols or v.is_real is not True or v.is_finite is not True for v in substitution.values()):
            raise ValueError('Finite real natural-parameter point required')
        mean=sp.Matrix([sp.diff(value,x) for x in symbols]).subs(substitution)
        fisher=sp.hessian(value,symbols).subs(substitution)
        if any(v.has(sp.nan,sp.zoo,sp.oo,-sp.oo) for v in fisher):raise ValueError('Singular log-partition Hessian at this point')
        return {'mean_sufficient_statistics':list(map(str,mean)),
                'fisher':[[str(sp.simplify(v)) for v in row] for row in fisher.tolist()],
                'hypotheses':'Declared function is a valid differentiable log-partition on the family natural-parameter domain'}

    @staticmethod
    def natural_gradient(gradient, fisher, damping=0.):
        import numpy as np
        g=_array(gradient,1,256);matrix=_covariance(fisher,len(g),'Fisher metric')
        if type(damping) not in (int,float) or not math.isfinite(damping) or damping<0:raise ValueError('Nonnegative finite damping required')
        regularized=matrix+damping*np.eye(len(g))
        try:result=np.linalg.solve(regularized,g)
        except np.linalg.LinAlgError as error:raise ValueError('Fisher metric is singular; use an explicit positive damping') from error
        return {'natural_gradient':result.tolist(),'damping':damping,
                'linear_residual':float(np.linalg.norm(regularized@result-g))}


def copula_sample(family, dimension, samples=1000, *, parameter=1., correlation=None,
                  seed=0):
    """Marshall–Olkin frailty sampling for Clayton/Gumbel plus Gaussian sampling."""
    import numpy as np
    if type(dimension) is not int or not 2<=dimension<=64 or type(samples) is not int or not 1<=samples<=100000 or samples*dimension>1000000:
        raise ValueError('Copula sample budget exceeded')
    if type(seed) is not int or not 0<=seed<2**64:raise ValueError('Unsigned 64-bit seed required')
    if family=='gaussian':
        matrix=np.eye(dimension) if correlation is None else correlation
        result=CopulaEngine.sample_gaussian(matrix,samples,seed)
        if len(result['correlation'])!=dimension:raise ValueError('Correlation dimension differs from copula dimension')
        return result
    rng=np.random.Generator(np.random.PCG64(seed))
    if type(parameter) not in (int,float) or not math.isfinite(parameter):raise ValueError('Finite copula parameter required')
    exponential=rng.exponential(size=(samples,dimension))
    if family=='clayton':
        if not 0<=parameter<=100:raise ValueError('Clayton theta must be between zero and 100')
        if parameter==0:uniforms=np.exp(-exponential)
        else:
            frailty=rng.gamma(1/parameter,size=samples)
            if np.any(frailty==0):raise ArithmeticError('Clayton gamma frailty underflowed at the requested parameter')
            uniforms=np.exp(-np.log1p(exponential/frailty[:,None])/parameter)
    elif family=='gumbel':
        if not 1<=parameter<=100:raise ValueError('Gumbel theta must be between one and 100')
        alpha=1/parameter
        if parameter==1:uniforms=np.exp(-exponential)
        else:
            angle=rng.uniform(np.nextafter(0.,1.),np.nextafter(math.pi,0.),size=samples)
            mixing=rng.exponential(size=samples)
            log_frailty=(np.log(np.sin(alpha*angle))-np.log(np.sin(angle))/alpha
                          +(1-alpha)/alpha*(np.log(np.sin((1-alpha)*angle))-np.log(mixing)))
            with np.errstate(over='ignore',under='ignore'):
                uniforms=np.exp(-np.exp(alpha*(np.log(exponential)-log_frailty[:,None])))
    else:raise ValueError('Copula family is gaussian, clayton or gumbel')
    uniforms=np.clip(uniforms,np.nextafter(0.,1.),np.nextafter(1.,0.))
    if not np.isfinite(uniforms).all():raise ArithmeticError('Copula sampler generated nonfinite samples')
    return {'uniforms':uniforms.tolist(),'family':family,'parameter':parameter,
            'seed':seed,'generator':'numpy.PCG64','boundary_policy':'Machine-exact 0/1 rounded inward'}


def wasserstein_discrete_1d(left_points, left_weights, right_points, right_weights, order=2):
    """Exact discrete quantile coupling formula, evaluated in floating point."""
    import numpy as np
    x=_array(left_points,1,100000);a=_array(left_weights,1,100000)
    y=_array(right_points,1,100000);b=_array(right_weights,1,100000)
    if x.shape!=a.shape or y.shape!=b.shape or (a<0).any() or (b<0).any() or abs(a.sum()-1)>1e-12 or abs(b.sum()-1)>1e-12:
        raise ValueError('Normalized nonnegative weighted point measures required')
    if type(order) not in (int,float) or not math.isfinite(order) or not 1<=order<=16:raise ValueError('Wasserstein order must lie in [1,16]')
    ix=np.argsort(x);iy=np.argsort(y);x=x[ix];a=a[ix].copy();y=y[iy];b=b[iy].copy()
    i=j=0;cost=0.;coupling=[]
    while i<len(x) and j<len(y):
        mass=min(a[i],b[j])
        if mass>0:
            cost+=mass*abs(x[i]-y[j])**order
            coupling.append([int(ix[i]),int(iy[j]),float(mass)])
        a[i]-=mass;b[j]-=mass
        if a[i]<=1e-15:i+=1
        if b[j]<=1e-15:j+=1
    if not math.isfinite(cost):raise ArithmeticError('Transport cost overflow')
    return {'distance':cost**(1/order),'power_cost':cost,'order':order,'coupling':coupling,
            'scope':'Optimal 1D coupling of the supplied discrete measures; floating-point mass arithmetic'}


def sinkhorn_transport(cost, left_weights, right_weights, regularization=.1,
                       tolerance=1e-9, max_iterations=10000):
    """Log-domain balanced entropic optimal transport with marginal residuals.

    Objective is <C,π>+ε KL(π||a⊗b). The regularized objective is not the
    unregularized Wasserstein distance. Zero-weight support is removed and
    reconstructed explicitly; strict positivity is not imposed on user masses.
    """
    import numpy as np
    from scipy.special import logsumexp
    matrix=_array(cost,2,262144);a=_array(left_weights,1,512);b=_array(right_weights,1,512)
    if matrix.shape!=(len(a),len(b)) or (matrix<0).any() or (a<0).any() or (b<0).any() or abs(a.sum()-1)>1e-12 or abs(b.sum()-1)>1e-12:
        raise ValueError('Nonnegative cost and normalized compatible measures required')
    epsilon=_positive(regularization,'regularization');tolerance=_positive(tolerance,'tolerance')
    if type(max_iterations) is not int or not 1<=max_iterations<=100000:raise ValueError('Sinkhorn iteration budget exceeded')
    ia=np.flatnonzero(a>0);ib=np.flatnonzero(b>0);aa=a[ia];bb=b[ib];c=matrix[np.ix_(ia,ib)]
    loga=np.log(aa);logb=np.log(bb);kernel=-c/epsilon;logv=np.zeros(len(bb));residual=math.inf
    for iteration in range(1,max_iterations+1):
        logu=loga-logsumexp(kernel+logv[None,:],axis=1)
        logv=logb-logsumexp(kernel+logu[:,None],axis=0)
        if iteration%10==0 or iteration==1 or iteration==max_iterations:
            logplan=logu[:,None]+kernel+logv[None,:];plan=np.exp(logplan)
            residual=max(float(np.max(abs(plan.sum(axis=1)-aa))),float(np.max(abs(plan.sum(axis=0)-bb))))
            if residual<=tolerance:break
    full=np.zeros_like(matrix);full[np.ix_(ia,ib)]=plan
    positive=plan>0
    kl=float(np.sum(plan[positive]*(logplan-loga[:,None]-logb[None,:])[positive])-plan.sum()+1)
    transport=float(np.sum(plan*c));objective=transport+epsilon*kl
    dual_f=epsilon*(logu-loga);dual_g=epsilon*(logv-logb)
    dual=float(aa@dual_f+bb@dual_g-epsilon*(plan.sum()-1))
    return {'plan':full.tolist(),'transport_cost':transport,'regularized_objective':objective,
            'dual_objective':dual,'observed_primal_dual_gap':objective-dual,
            'maximum_marginal_residual':residual,'converged':residual<=tolerance,
            'iterations':iteration,'regularization':epsilon,
            'scope':'Floating-point entropic transport; residual/gap are not interval certificates'}


__all__ += ['GaussianProcessRegressor','StatisticalInformationGeometry','copula_sample',
            'wasserstein_discrete_1d','sinkhorn_transport']


def geometric_brownian_motion(initial, drift, volatility, times, *, paths=1, seed=0):
    """Exact GBM transitions with analytic first/second moments on the same grid."""
    import numpy as np
    grid=_array(times,1,10001)
    if len(grid)<2 or grid[0]!=0 or np.any(np.diff(grid)<=0):raise ValueError('Increasing time grid starting at zero required')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (initial,drift,volatility)) or initial<=0 or volatility<0:
        raise ValueError('Positive initial GBM value and nonnegative volatility required')
    if type(paths) is not int or not 1<=paths<=100000 or len(grid)*paths>2000000 or type(seed) is not int or not 0<=seed<2**64:
        raise ValueError('GBM sampling budget or seed invalid')
    rng=np.random.Generator(np.random.PCG64(seed))
    increments=rng.standard_normal((paths,len(grid)-1))*np.sqrt(np.diff(grid))
    brownian=np.column_stack((np.zeros(paths),np.cumsum(increments,axis=1)))
    with np.errstate(over='raise',under='ignore'):
        try:values=initial*np.exp((drift-volatility**2/2)*grid+volatility*brownian)
        except FloatingPointError as error:raise ArithmeticError('GBM exponential overflow') from error
    if not np.isfinite(values).all():raise ArithmeticError('GBM paths became nonfinite')
    mean=initial*np.exp(drift*grid)
    variance=initial**2*np.exp(2*drift*grid)*np.expm1(volatility**2*grid)
    return {'times':grid.tolist(),'paths':values.tolist(),'mean':mean.tolist(),'variance':variance.tolist(),
            'seed':seed,'generator':'numpy.PCG64','transition':'Exact lognormal GBM; machine underflow may round tiny positive values to zero'}


def cir_process(initial, long_run_mean, rate, volatility, times, *, paths=1, seed=0):
    """Exact CIR transition sampling, including accessible/absorbing zero cases.

    dX=κ(θ−X)dt+σ sqrt(X)dW. The noncentral chi-square transition handles the
    Feller boundary correctly, including θ=0 through its Poisson/Gamma mixture.
    The Feller inequality diagnoses unattainability of zero, not existence of
    nonnegative solutions when the inequality fails.
    """
    import numpy as np
    grid=_array(times,1,10001)
    if len(grid)<2 or grid[0]!=0 or np.any(np.diff(grid)<=0):raise ValueError('Increasing CIR grid from zero required')
    parameters=(initial,long_run_mean,rate,volatility)
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in parameters):
        raise ValueError('Finite nonnegative CIR parameters required')
    if type(paths) is not int or not 1<=paths<=100000 or paths*len(grid)>2000000 or type(seed) is not int or not 0<=seed<2**64:
        raise ValueError('CIR sampling budget or seed invalid')
    rng=np.random.Generator(np.random.PCG64(seed));history=np.empty((paths,len(grid)));history[:,0]=initial
    for i,dt in enumerate(np.diff(grid),1):
        decay=math.exp(-rate*dt)
        if volatility==0:
            history[:,i]=long_run_mean+(history[:,i-1]-long_run_mean)*decay;continue
        scale=volatility**2*dt/4 if rate==0 else -volatility**2*math.expm1(-rate*dt)/(4*rate)
        degrees=4*rate*long_run_mean/volatility**2
        noncentral=history[:,i-1]*decay/scale
        if degrees>0:history[:,i]=scale*rng.noncentral_chisquare(degrees,noncentral)
        else:
            counts=rng.poisson(noncentral/2);draws=np.zeros(paths);positive=counts>0
            draws[positive]=rng.gamma(counts[positive],2.)
            history[:,i]=scale*draws
    decay=np.exp(-rate*grid);mean=long_run_mean+(initial-long_run_mean)*decay
    if rate==0:variance=initial*volatility**2*grid
    else:variance=initial*volatility**2*decay*(1-decay)/rate+long_run_mean*volatility**2*(1-decay)**2/(2*rate)
    if not np.isfinite(history).all() or history.min()<0:raise ArithmeticError('CIR transition lost nonnegativity/finiteness')
    return {'times':grid.tolist(),'paths':history.tolist(),'mean':mean.tolist(),'variance':variance.tolist(),
            'feller_zero_unattainable':bool(2*rate*long_run_mean>=volatility**2 and initial>0),
            'seed':seed,'generator':'numpy.PCG64','transition':'Exact noncentral-chi-square CIR'}


def compound_poisson_process(initial, rate, times, *, jump_family='normal',
                             jump_parameters=None, drift=0., compensated=False,
                             paths=1, seed=0):
    """Compound Poisson paths with exact conditional jump-sum distributions."""
    import numpy as np
    grid=_array(times,1,10001)
    if len(grid)<2 or grid[0]!=0 or np.any(np.diff(grid)<=0):raise ValueError('Increasing jump-process grid from zero required')
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in (initial,rate,drift)) or rate<0:
        raise ValueError('Finite jump parameters and nonnegative event rate required')
    if type(paths) is not int or not 1<=paths<=100000 or paths*len(grid)>2000000 or type(seed) is not int or not 0<=seed<2**64 or type(compensated) is not bool:
        raise ValueError('Jump-process sampling budget/seed/policy invalid')
    parameters={} if jump_parameters is None else dict(jump_parameters)
    if jump_family=='normal':
        if set(parameters)-{'mean','standard_deviation'}:raise ValueError('Unknown normal jump parameters')
        mean=float(parameters.get('mean',0));sigma=float(parameters.get('standard_deviation',1))
        if not math.isfinite(mean) or not math.isfinite(sigma) or sigma<0:raise ValueError('Invalid normal jump law')
        second=sigma*sigma+mean*mean
    elif jump_family=='exponential':
        if set(parameters)-{'scale'}:raise ValueError('Unknown exponential jump parameters')
        mean=_positive(parameters.get('scale',1.),'jump scale');second=2*mean*mean
    elif jump_family=='constant':
        if set(parameters)-{'value'}:raise ValueError('Unknown constant jump parameters')
        mean=float(parameters.get('value',1.))
        if not math.isfinite(mean):raise ValueError('Finite constant jump size required')
        second=mean*mean
    else:raise ValueError('Jump law is normal, exponential or constant')
    rng=np.random.Generator(np.random.PCG64(seed));history=np.empty((paths,len(grid)));history[:,0]=initial
    counts_history=np.zeros((paths,len(grid)-1),dtype=np.int64)
    compensation=rate*mean if compensated else 0.
    for i,dt in enumerate(np.diff(grid),1):
        if rate*dt>1e12:raise ValueError('Expected jump count exceeds sampling budget')
        counts=rng.poisson(rate*dt,size=paths);counts_history[:,i-1]=counts
        if jump_family=='normal':jumps=counts*mean+sigma*np.sqrt(counts)*rng.standard_normal(paths)
        elif jump_family=='constant':jumps=counts*mean
        else:
            jumps=np.zeros(paths);nonzero=counts>0;jumps[nonzero]=rng.gamma(counts[nonzero],mean)
        history[:,i]=history[:,i-1]+(drift-compensation)*dt+jumps
    if not np.isfinite(history).all():raise ArithmeticError('Jump process became nonfinite')
    return {'times':grid.tolist(),'paths':history.tolist(),'jump_counts':counts_history.tolist(),
            'mean':(initial+(drift+rate*mean-compensation)*grid).tolist(),
            'variance':(rate*second*grid).tolist(),'seed':seed,'generator':'numpy.PCG64',
            'compensated':compensated,'jump_family':jump_family}


class AbsorbingFokkerPlanck:
    """First-passage finite volumes with explicit absorbing probability states.

    The augmented generator is conservative in the sum of surviving cell mass
    and two absorbing reservoirs. Survival probability decreases while total
    probability remains one. Boundary discretization is first-order/upwind in
    advection and finite-volume Dirichlet diffusion across a half-cell distance.
    """
    def __init__(self, centers, drift, diffusion, *, left=True, right=True):
        if type(left) is not bool or type(right) is not bool or not (left or right):
            raise ValueError('At least one absorbing endpoint required')
        self.base=FokkerPlanckPDE(centers,drift,diffusion);self.left=left;self.right=right

    def generator(self):
        import numpy as np
        from scipy.sparse import lil_matrix
        n=len(self.base.centers);dx=self.base.spacing
        augmented=lil_matrix((n+2,n+2));augmented[:n,:n]=self.base.generator()
        left_rate=(max(-self.base.drift[0],0)/dx+2*self.base.diffusion[0]/dx**2) if self.left else 0.
        right_rate=(max(self.base.drift[-1],0)/dx+2*self.base.diffusion[-1]/dx**2) if self.right else 0.
        augmented[0,0]-=left_rate;augmented[n,0]=left_rate
        augmented[n-1,n-1]-=right_rate;augmented[n+1,n-1]=right_rate
        return augmented.tocsc()

    def solve(self, density, duration=1., steps=100):
        import numpy as np
        from scipy.sparse.linalg import expm_multiply
        initial=_array(density,1,10000);n=len(self.base.centers)
        if initial.shape!=(n,) or (initial<0).any() or abs(initial.sum()*self.base.spacing-1)>1e-10:
            raise ValueError('Normalized nonnegative initial density on the supplied grid required')
        duration=_positive(duration,'duration')
        if type(steps) is not int or not 1<=steps<=10000 or steps*(n+2)>2000000:
            raise ValueError('First-passage history budget exceeded')
        augmented=np.concatenate((initial*self.base.spacing,[0.,0.]))
        history=expm_multiply(self.generator(),augmented,start=0,stop=duration,num=steps+1,endpoint=True)
        survival=history[:,:n].sum(axis=1);left=history[:,n];right=history[:,n+1]
        total=survival+left+right
        if history.min() < -1e-12 or np.max(abs(total-1))>1e-8:raise ArithmeticError('Absorbing finite-volume probability invariant failed')
        return {'times':np.linspace(0,duration,steps+1).tolist(),'density':(history[:,:n]/self.base.spacing).tolist(),
                'survival':survival.tolist(),'left_absorbed':left.tolist(),'right_absorbed':right.tolist(),
                'first_passage_cdf':(left+right).tolist(),'maximum_total_probability_error':float(np.max(abs(total-1))),
                'scope':'First passage of the finite-volume Markov discretization; no continuum boundary-error certificate'}


class BootstrapParticleFilter:
    """Nonlinear Gaussian state-space SMC with systematic resampling.

    Model is X_k=f(X_{k-1},t_k)+N(0,Q), Y_k=h(X_k,t_k)+N(0,R).
    f and h are closed AST expressions; Q can be positive semidefinite and R
    must be positive definite. The first observation updates the initial prior.
    The likelihood estimate is stochastic; log of that estimate is biased.
    """
    def __init__(self, variables, transition, observation, process_covariance,
                 observation_covariance, *, time='t'):
        self.variables=names(variables,4);names(list(self.variables)+[time],5)
        if len(transition)!=len(self.variables) or not 1<=len(observation)<=4:
            raise ValueError('Transition/observation expression dimensions differ')
        self.time=time;self.transition=tuple(transition);self.observation=tuple(observation)
        self.q=_covariance(process_covariance,len(self.variables),'Process covariance')
        self.r=_covariance(observation_covariance,len(observation),'Observation covariance',positive_definite=True)
        self.symbols=tuple(map(sympy().Symbol,[time]+list(self.variables)))
        self.f=[sympy().lambdify(self.symbols,expression(v,list(self.variables)+[time])[0],modules='numpy',cse=True) for v in transition]
        self.h=[sympy().lambdify(self.symbols,expression(v,list(self.variables)+[time])[0],modules='numpy',cse=True) for v in observation]

    @staticmethod
    def systematic_resample(weights, generator):
        import numpy as np
        probabilities=_array(weights,1,100000)
        if (probabilities<0).any() or abs(probabilities.sum()-1)>1e-10:raise ValueError('Normalized particle weights required')
        count=len(probabilities);positions=(generator.random()+np.arange(count))/count
        cumulative=np.cumsum(probabilities);cumulative[-1]=1.
        indices=np.searchsorted(cumulative,positions,side='right')
        if indices.max()>=count:raise ArithmeticError('Systematic resampling index overflow')
        return indices

    def filter(self, observations, initial_mean, initial_covariance, *, times=None,
               particles=1000, seed=0, resample_fraction=.5, retain_particles=False):
        import numpy as np
        from scipy.linalg import cho_factor,cho_solve
        from scipy.special import logsumexp
        n=len(self.variables);m=len(self.observation)
        if not isinstance(observations,(list,tuple)) or not 1<=len(observations)<=10000:
            raise ValueError('Nonempty observation sequence required')
        if type(particles) is not int or not 2<=particles<=100000 or len(observations)*particles*n>10000000:
            raise ValueError('Particle filter work budget exceeded')
        if retain_particles and len(observations)*particles*n>1000000:raise ValueError('Retained particle history budget exceeded')
        if type(seed) is not int or not 0<=seed<2**64 or not 0<resample_fraction<=1 or type(retain_particles) is not bool:
            raise ValueError('Invalid particle-filter seed or resampling policy')
        mean=_array(initial_mean,1,4)
        if mean.shape!=(n,):raise ValueError('Initial state dimension mismatch')
        covariance=_covariance(initial_covariance,n,'Initial covariance')
        clock=np.arange(len(observations),dtype=float) if times is None else _array(times,1,10000)
        if clock.shape!=(len(observations),) or np.any(np.diff(clock)<=0):raise ValueError('One increasing time per observation required')
        rng=np.random.Generator(np.random.PCG64(seed))
        def square_root(matrix):
            values,vectors=np.linalg.eigh(matrix)
            return vectors@np.diag(np.sqrt(np.maximum(values,0)))
        state=mean+rng.standard_normal((particles,n))@square_root(covariance).T
        process_root=square_root(self.q);factor=cho_factor(self.r,lower=True)
        logdet=2*float(np.log(np.diag(factor[0])).sum());logweights=np.full(particles,-math.log(particles))
        results=[];retained=[];log_likelihood=0.
        def evaluate(functions,time,points):
            args=[time]+[points[:,i] for i in range(n)]
            values=np.column_stack([np.broadcast_to(np.asarray(f(*args),dtype=float),(particles,)) for f in functions])
            if not np.isfinite(values).all():raise ArithmeticError('Particle-model expression became nonfinite')
            return values
        for index,(time,row) in enumerate(zip(clock,observations)):
            if index:state=evaluate(self.f,time,state)+rng.standard_normal((particles,n))@process_root.T
            if row is not None:
                data=_array(row,1,4)
                if data.shape!=(m,):raise ValueError('Particle observation dimension mismatch')
                residual=data-evaluate(self.h,time,state)
                quadratic=np.einsum('pi,ip->p',residual,cho_solve(factor,residual.T))
                updated=logweights-.5*(m*math.log(2*math.pi)+logdet+quadratic)
                normalizer=float(logsumexp(updated))
                if not math.isfinite(normalizer):raise ArithmeticError('All particle likelihood weights vanished')
                log_likelihood+=normalizer;logweights=updated-normalizer
            weights=np.exp(logweights);weights/=weights.sum()
            filtered_mean=weights@state;centered=state-filtered_mean
            filtered_covariance=(centered.T*weights)@centered
            ess=1/float(np.sum(weights*weights));resampled=ess<resample_fraction*particles
            results.append({'time':float(time),'mean':filtered_mean.tolist(),'covariance':filtered_covariance.tolist(),
                            'effective_sample_size':ess,'resampled':resampled})
            if retain_particles:retained.append({'states':state.tolist(),'weights':weights.tolist()})
            if resampled:
                indices=self.systematic_resample(weights,rng);state=state[indices];logweights=np.full(particles,-math.log(particles))
        result={'filtered':results,'log_likelihood_estimate':log_likelihood,'particles':particles,
                'seed':seed,'generator':'numpy.PCG64','scope':'Monte Carlo filtering; no convergence or likelihood-error certificate'}
        if retain_particles:result['particle_history']=retained
        return result


__all__ += ['geometric_brownian_motion','cir_process','compound_poisson_process',
            'AbsorbingFokkerPlanck','BootstrapParticleFilter']


class ContinuousTimeMarkovChain:
    """Finite row-generator CTMC with exact hitting statistics and seeded jumps."""
    def __init__(self, generator):
        from ..math._structured import rational_matrix
        sp=sympy();matrix=rational_matrix(generator,maximum=64)
        if matrix.rows!=matrix.cols:raise ValueError('Square continuous-time generator required')
        if any(matrix[i,j]<0 for i in range(matrix.rows) for j in range(matrix.cols) if i!=j):
            raise ValueError('CTMC off-diagonal rates must be nonnegative')
        if any(sum(matrix.row(i))!=0 for i in range(matrix.rows)):raise ValueError('Row-generator rates must sum exactly to zero')
        self.generator=sp.ImmutableMatrix(matrix);self.states=matrix.rows

    def transition(self, duration):
        import numpy as np
        from scipy.linalg import expm
        duration=_positive(duration,'duration')
        matrix=expm(np.asarray(self.generator,dtype=float)*duration)
        if not np.isfinite(matrix).all() or matrix.min() < -1e-12 or np.max(abs(matrix.sum(axis=1)-1))>1e-9:
            raise ArithmeticError('CTMC exponential lost stochastic matrix invariants')
        return {'transition':matrix.tolist(),'duration':duration,
                'row_sum_error':float(np.max(abs(matrix.sum(axis=1)-1))),
                'scope':'Floating-point matrix exponential, not a certified interval transition'}

    def stationary(self):
        """Stationary family as an exact nullspace, with uniqueness explicit."""
        sp=sympy();kernel=self.generator.T.nullspace()
        if len(kernel)!=1:
            return {'unique':False,'kernel_basis':[list(map(str,v)) for v in kernel],
                    'scope':'Choose a nonnegative normalized combination to specify a stationary law'}
        vector=kernel[0];total=sum(vector)
        if total==0:raise ArithmeticError('Unique stationary nullspace cannot be normalized')
        vector=vector/total
        if any(v<0 for v in vector):raise ArithmeticError('Stationary law failed nonnegativity')
        if self.generator.T*vector!=sp.zeros(self.states,1):raise ArithmeticError('Stationarity residual nonzero')
        return {'unique':True,'probabilities':list(map(str,vector)),'residual_zero':True}

    def hitting(self, targets):
        """Exact eventual hitting probability and conditional first two moments."""
        sp=sympy();n=self.states
        if not isinstance(targets,(list,tuple)) or not targets or any(type(v) is not int or not 0<=v<n for v in targets):
            raise ValueError('Nonempty valid target state indices required')
        target=set(targets);reachable=set(target)
        while True:
            previous=set(reachable)
            reachable.update(i for i in range(n) if any(self.generator[i,j]>0 for j in reachable if i!=j))
            if previous==reachable:break
        transient=sorted(reachable-target);h=sp.zeros(n,1)
        for i in target:h[i]=1
        if transient:
            a=self.generator.extract(transient,transient)
            rhs=sp.Matrix([-sum(self.generator[i,j] for j in target) for i in transient])
            values=a.inv()*rhs
            for i,value in zip(transient,values):h[i]=sp.simplify(value)
        positive=[i for i in transient if h[i]>0];mean={i:sp.Integer(0) for i in target};second=dict(mean)
        if positive:
            conditioned=sp.Matrix(len(positive),len(positive),lambda i,j:self.generator[positive[i],positive[j]]*h[positive[j]]/h[positive[i]])
            first=-conditioned.inv()*sp.ones(len(positive),1);moments=-2*conditioned.inv()*first
            mean.update({i:sp.simplify(v) for i,v in zip(positive,first)})
            second.update({i:sp.simplify(v) for i,v in zip(positive,moments)})
        return {'states':[{'state':i,'hitting_probability':str(h[i]),
                           'conditional_mean':str(mean[i]) if i in mean else None,
                           'conditional_variance':str(sp.simplify(second[i]-mean[i]**2)) if i in mean else None,
                           'unconditional_mean_infinite':h[i]!=1} for i in range(n)],
                'arithmetic':'Exact rational generator/Doob transform; holding times are continuous'}

    def simulate(self, initial, duration, *, seed=0, max_events=100000):
        import numpy as np
        if type(initial) is not int or not 0<=initial<self.states:raise ValueError('Valid initial CTMC state required')
        duration=_positive(duration,'duration')
        if type(seed) is not int or not 0<=seed<2**64 or type(max_events) is not int or not 1<=max_events<=1000000:
            raise ValueError('CTMC seed/event budget invalid')
        rng=np.random.Generator(np.random.PCG64(seed));state=initial;clock=0.;events=[{'time':0.,'state':initial}]
        matrix=np.asarray(self.generator,dtype=float)
        while clock<duration:
            rate=-matrix[state,state]
            if rate==0:break
            jump=clock+float(rng.exponential(1/rate))
            if jump>duration:break
            if len(events)-1>=max_events:raise ArithmeticError('CTMC event budget exhausted before the requested duration')
            probabilities=matrix[state].copy();probabilities[state]=0;probabilities/=rate
            state=int(rng.choice(self.states,p=probabilities));clock=jump
            events.append({'time':clock,'state':state})
        return {'events':events,'duration':duration,'final_state':state,'seed':seed,
                'generator':'numpy.PCG64','scheme':'Exact exponential holding times and categorical jumps'}


def feynman_kac_expectation(variables, drift, diffusion, initial, payoff, *, killing='0',
                           duration=1., steps=1000, paths=1000, seed=0,
                           method='euler_maruyama'):
    """Monte Carlo terminal Feynman–Kac functional with trapezoidal killing.

    Computes E[exp(-integral V(X_s,s)ds) g(X_T,T)]. Sampling standard error
    estimates Monte Carlo uncertainty only; time discretization, rare-event
    bias and model validity are separate. Negative killing is rejected at every
    sampled point to keep discounting bounded above by one on the sample paths.
    """
    import numpy as np
    solver=SDESolver(variables,drift,diffusion)
    result=solver.solve(initial,duration,steps,seed=seed,paths=paths,method=method)
    allowed=list(solver.variables)+['t'];symbols=tuple(map(sympy().Symbol,allowed))
    terminal=expression(payoff,allowed)[0];potential=expression(killing,allowed)[0]
    reward=sympy().lambdify(symbols,terminal,modules='numpy',cse=True)
    kill=sympy().lambdify(symbols,potential,modules='numpy',cse=True)
    state=np.asarray(result['states']);clock=np.asarray(result['times'])
    args=[state[:,:,i] for i in range(len(variables))]+[clock[:,None]]
    rates=np.broadcast_to(np.asarray(kill(*args),dtype=float),state.shape[:2])
    if not np.isfinite(rates).all() or rates.min()<0:raise ValueError('Killing rate must be finite and nonnegative on every sampled state')
    integral=np.sum((rates[:-1]+rates[1:])*.5*np.diff(clock)[:,None],axis=0)
    terminal_args=[state[-1,:,i] for i in range(len(variables))]+[duration]
    rewards=np.broadcast_to(np.asarray(reward(*terminal_args),dtype=float),(paths,))
    values=np.exp(-integral)*rewards
    if not np.isfinite(values).all():raise ArithmeticError('Feynman–Kac payoff became nonfinite')
    mean=float(values.mean());error=float(values.std(ddof=1)/math.sqrt(paths)) if paths>1 else None
    return {'expectation':mean,'monte_carlo_standard_error':error,'paths':paths,'seed':seed,
            'increments_sha256':result['increments_sha256'],
            'normal_95_percent_interval':None if error is None else [mean-1.959963984540054*error,mean+1.959963984540054*error],
            'scope':'Conditional Feynman–Kac interpretation under regularity; estimated sampling interval excludes discretization error'}


def steady_state_kalman(transition, observation_matrix, process_covariance,
                        observation_covariance, *, continuous=False):
    """Algebraic Riccati steady-state filtering with a stability diagnostic."""
    import numpy as np
    from scipy.linalg import solve_continuous_are,solve_discrete_are
    a=_array(transition,2,4096);h=_array(observation_matrix,2,4096);n=len(a);m=len(h)
    if a.shape!=(n,n) or h.shape[1]!=n or type(continuous) is not bool:raise ValueError('Compatible bounded state-space matrices required')
    q=_covariance(process_covariance,n,'Process covariance');r=_covariance(observation_covariance,m,'Observation covariance',positive_definite=True)
    try:
        if continuous:
            covariance=solve_continuous_are(a.T,h.T,q,r)
            gain=np.linalg.solve(r,h@covariance).T
            residual=a@covariance+covariance@a.T+q-covariance@h.T@np.linalg.solve(r,h@covariance)
            eigenvalues=np.linalg.eigvals(a-gain@h);stable=bool(np.max(eigenvalues.real)<0)
        else:
            covariance=solve_discrete_are(a.T,h.T,q,r)
            innovation=h@covariance@h.T+r
            gain=np.linalg.solve(innovation,h@covariance).T
            residual=a@covariance@a.T+q-a@covariance@h.T@np.linalg.solve(innovation,h@covariance@a.T)-covariance
            eigenvalues=np.linalg.eigvals(a@(np.eye(n)-gain@h));stable=bool(np.max(abs(eigenvalues))<1)
    except np.linalg.LinAlgError as error:raise ArithmeticError('Riccati solver could not find a stabilizing covariance') from error
    return {'covariance':covariance.tolist(),'gain':gain.tolist(),'riccati_residual_norm':float(np.linalg.norm(residual)),
            'error_dynamics_eigenvalues':[[float(v.real),float(v.imag)] for v in eigenvalues],
            'numerically_stable':stable,'continuous':continuous,
            'scope':'Numerical Riccati solution; detectability/stabilizability and rounding remain explicit considerations'}


def bernoulli_confidence_sequence(observations, alpha=.05):
    """Time-uniform Hoeffding union-bound intervals for bounded Bernoulli data.

    At time t the two-sided error allocation is alpha/[t(t+1)]. Summing these
    allocations over all positive integers gives alpha. Coverage requires the
    independent/common-mean (or corresponding conditional-mean martingale)
    assumptions; it does not follow for an arbitrary correlated time series.
    """
    import numpy as np
    if not isinstance(observations,(list,tuple)) or not 1<=len(observations)<=1000000 or any(type(v) is not int or v not in (0,1) for v in observations):
        raise ValueError('Nonempty bounded binary observation sequence required')
    if type(alpha) not in (int,float) or not 0<alpha<1:raise ValueError('Confidence error level must be in (0,1)')
    time=np.arange(1,len(observations)+1,dtype=float);mean=np.cumsum(observations)/time
    radius=np.sqrt(np.log(2*time*(time+1)/alpha)/(2*time))
    return {'means':mean.tolist(),'lower':np.maximum(0,mean-radius).tolist(),'upper':np.minimum(1,mean+radius).tolist(),
            'alpha':alpha,'coverage_scope':'Time-uniform under stated common-mean bounded martingale assumptions',
            'rounding':'Floating-point evaluation of analytic Hoeffding/union bounds'}


def bernoulli_e_process(observations, null_probability, prior_alpha=1., prior_beta=1.):
    """Beta-mixture likelihood-ratio e-process against a fixed Bernoulli null."""
    import numpy as np
    from scipy.special import betaln
    if not isinstance(observations,(list,tuple)) or not 1<=len(observations)<=1000000 or any(type(v) is not int or v not in (0,1) for v in observations):
        raise ValueError('Nonempty bounded binary observation sequence required')
    if not 0<null_probability<1 or not math.isfinite(null_probability):raise ValueError('Interior Bernoulli null probability required')
    aa=_positive(prior_alpha,'prior alpha');bb=_positive(prior_beta,'prior beta')
    successes=np.cumsum(observations);time=np.arange(1,len(observations)+1);failures=time-successes
    log_e=betaln(aa+successes,bb+failures)-betaln(aa,bb)-successes*math.log(null_probability)-failures*math.log1p(-null_probability)
    return {'log_e_values':log_e.tolist(),'maximum_log_e':float(log_e.max()),
            'null_probability':null_probability,'prior_alpha':aa,'prior_beta':bb,
            'scope':'Test martingale under the fixed iid Bernoulli null; no automatic rejection threshold chosen'}


__all__ += ['ContinuousTimeMarkovChain','feynman_kac_expectation','steady_state_kalman',
            'bernoulli_confidence_sequence','bernoulli_e_process']


class GaussianMixture:
    """Finite Gaussian mixtures with log-domain likelihood and EM fitting.

    Full covariances are positive definite. A declared diagonal regularizer is
    applied during fitting and recorded; it is not silently added during ordinary
    density evaluation. EM is a local optimization procedure, not a guarantee of
    the globally best number of components or calibrated scientific prediction.
    """
    def __init__(self, weights, means, covariances):
        import numpy as np
        self.weights=_array(weights,1,32);self.means=_array(means,2,2048)
        if len(self.weights)!=len(self.means) or (self.weights<=0).any() or abs(self.weights.sum()-1)>1e-12:
            raise ValueError('Positive normalized mixture weights and matching means required')
        if self.means.shape[1]>64 or len(covariances)!=len(self.weights):raise ValueError('Mixture dimensions exceed budget')
        self.covariances=np.asarray([_covariance(c,self.means.shape[1],'Mixture covariance',positive_definite=True) for c in covariances])

    def component_log_density(self, points):
        import numpy as np
        from scipy.linalg import cho_factor,cho_solve
        samples=_array(points,2,2000000)
        if samples.shape[1]!=self.means.shape[1] or len(samples)*len(self.weights)>2000000:
            raise ValueError('Mixture sample dimension/work budget mismatch')
        values=np.empty((len(samples),len(self.weights)));dimension=samples.shape[1]
        for i,(mean,covariance) in enumerate(zip(self.means,self.covariances)):
            factor=cho_factor(covariance,lower=True);difference=samples-mean
            quadratic=np.einsum('ni,in->n',difference,cho_solve(factor,difference.T))
            logdet=2*float(np.log(np.diag(factor[0])).sum())
            values[:,i]=-.5*(dimension*math.log(2*math.pi)+logdet+quadratic)
        return values

    def log_density(self, points):
        import numpy as np
        from scipy.special import logsumexp
        return logsumexp(self.component_log_density(points)+np.log(self.weights),axis=1).tolist()

    def responsibilities(self, points):
        import numpy as np
        from scipy.special import logsumexp
        joint=self.component_log_density(points)+np.log(self.weights)
        return np.exp(joint-logsumexp(joint,axis=1)[:,None]).tolist()

    def moments(self):
        import numpy as np
        mean=self.weights@self.means;covariance=np.zeros_like(self.covariances[0])
        for weight,component,within in zip(self.weights,self.means,self.covariances):
            difference=component-mean;covariance+=weight*(within+np.outer(difference,difference))
        return {'mean':mean.tolist(),'covariance':covariance.tolist()}

    def sample(self, samples=1000, seed=0):
        import numpy as np
        if type(samples) is not int or not 1<=samples<=1000000 or samples*self.means.shape[1]>2000000 or type(seed) is not int or not 0<=seed<2**64:
            raise ValueError('Mixture sample budget or seed invalid')
        rng=np.random.Generator(np.random.PCG64(seed));labels=rng.choice(len(self.weights),size=samples,p=self.weights)
        points=np.empty((samples,self.means.shape[1]))
        for i,(mean,covariance) in enumerate(zip(self.means,self.covariances)):
            selected=np.flatnonzero(labels==i)
            if len(selected):points[selected]=mean+rng.standard_normal((len(selected),self.means.shape[1]))@np.linalg.cholesky(covariance).T
        return {'points':points.tolist(),'components':labels.tolist(),'seed':seed,'generator':'numpy.PCG64'}

    def fit(self, samples, *, max_iterations=100, tolerance=1e-6, covariance_regularization=1e-6):
        import numpy as np
        data=_array(samples,2,2000000);n,dimension=data.shape;k=len(self.weights)
        if dimension!=self.means.shape[1] or n<k or n*k>2000000:raise ValueError('Mixture training dimensions/budget mismatch')
        if type(max_iterations) is not int or not 1<=max_iterations<=1000 or not 0<tolerance<1:
            raise ValueError('EM convergence budget invalid')
        regularization=_positive(covariance_regularization,'covariance regularization')
        likelihood=[];converged=False
        for iteration in range(max_iterations):
            value=float(np.sum(self.log_density(data)))
            likelihood.append(value)
            responsibilities=np.asarray(self.responsibilities(data));mass=responsibilities.sum(axis=0)
            if np.min(mass)<1e-10:raise ArithmeticError('EM component collapsed to negligible effective sample count')
            means=responsibilities.T@data/mass[:,None];covariances=[]
            for i in range(k):
                difference=data-means[i]
                covariance=(difference.T*responsibilities[:,i])@difference/mass[i]+regularization*np.eye(dimension)
                covariances.append(covariance)
            self.weights=mass/n;self.means=means;self.covariances=np.asarray(covariances)
            updated=float(np.sum(self.log_density(data)))
            if abs(updated-value)<=tolerance*max(1,abs(value)):
                likelihood.append(updated);converged=True;break
        return {'converged':converged,'iterations':iteration+1,'log_likelihood_history':likelihood,
                'weights':self.weights.tolist(),'means':self.means.tolist(),'covariances':self.covariances.tolist(),
                'covariance_regularization':regularization,
                'scope':'Regularized local EM fit; monotonic unregularized likelihood is not assumed under covariance flooring'}

    def entropy_estimate(self, samples=10000, seed=0):
        import numpy as np
        generated=self.sample(samples,seed);information=-np.asarray(self.log_density(generated['points']))
        return {'entropy_nats':float(information.mean()),
                'standard_error':float(information.std(ddof=1)/math.sqrt(samples)) if samples>1 else None,
                'samples':samples,'seed':seed,'scope':'Monte Carlo differential entropy estimate, not exact mixture entropy'}


def conditional_gaussian(mean, covariance, observed_indices, observed_values):
    """Schur-complement conditioning with an explicit ordered variable partition."""
    import numpy as np
    from scipy.linalg import cho_factor,cho_solve
    mu=_array(mean,1,256);matrix=_covariance(covariance,len(mu),'Joint covariance',positive_definite=True)
    if not isinstance(observed_indices,(list,tuple)) or not observed_indices or len(set(observed_indices))!=len(observed_indices) or any(type(i) is not int or not 0<=i<len(mu) for i in observed_indices):
        raise ValueError('Distinct observed variable indices required')
    values=_array(observed_values,1,256)
    if len(values)!=len(observed_indices):raise ValueError('Observation index/value dimensions differ')
    remaining=[i for i in range(len(mu)) if i not in observed_indices]
    if not remaining:raise ValueError('At least one unobserved Gaussian variable required')
    a=np.asarray(remaining);b=np.asarray(observed_indices)
    block=matrix[np.ix_(b,b)];cross=matrix[np.ix_(a,b)];factor=cho_factor(block,lower=True)
    conditional_mean=mu[a]+cross@cho_solve(factor,values-mu[b])
    conditional_covariance=matrix[np.ix_(a,a)]-cross@cho_solve(factor,cross.T)
    conditional_covariance=(conditional_covariance+conditional_covariance.T)/2
    return {'remaining_indices':remaining,'mean':conditional_mean.tolist(),'covariance':conditional_covariance.tolist(),
            'observation_indices':list(observed_indices),'scope':'Conditioning of the supplied nonsingular joint Gaussian law'}


def gaussian_wasserstein(mean, covariance, reference_mean, reference_covariance):
    """Squared 2-Wasserstein/Bures distance between Gaussian probability laws."""
    import numpy as np
    from scipy.linalg import eigh
    mu=_array(mean,1,128);other=_array(reference_mean,1,128)
    if mu.shape!=other.shape:raise ValueError('Gaussian mean dimensions differ')
    a=_covariance(covariance,len(mu),'Covariance');b=_covariance(reference_covariance,len(mu),'Reference covariance')
    def square_root(matrix):
        values,vectors=eigh((matrix+matrix.T)/2)
        if values.min()<-1e-10:raise ArithmeticError('Matrix square root lost positive semidefiniteness')
        return (vectors*np.sqrt(np.maximum(values,0)))@vectors.T
    root=square_root(a);middle=square_root(root@b@root)
    squared=float((mu-other)@(mu-other)+np.trace(a+b-2*middle))
    if squared < -1e-8*max(1,float(np.trace(a+b))):raise ArithmeticError('Gaussian transport distance became negative beyond rounding tolerance')
    return {'squared_distance':max(0,squared),'distance':math.sqrt(max(0,squared)),
            'scope':'Floating-point Gaussian Wasserstein distance, including singular covariances'}


def girsanov_log_weight(variables, original_drift, target_drift, diffusion, states, increments,
                        duration):
    """Discrete path likelihood-ratio diagnostic for invertible square diffusion.

    For dX=b dt+σ dW, θ=σ^-1(target_b-b) and log Z≈Σ θ·ΔW−|θ|²dt/2.
    This finite-grid functional is not a proof that Novikov's condition holds,
    nor an exact continuous-time Radon–Nikodym derivative at finite step size.
    """
    import numpy as np
    variables=names(variables,4);n=len(variables);clock=_positive(duration,'duration')
    if len(original_drift)!=n or len(target_drift)!=n or len(diffusion)!=n or any(len(row)!=n for row in diffusion):
        raise ValueError('Square invertible-diffusion drift-change model required')
    trajectory=_array(states,2,1000000);brownian=_array(increments,2,1000000)
    if trajectory.shape!=(len(brownian)+1,n) or brownian.shape[1]!=n:raise ValueError('One left-point state per Brownian increment plus terminal state required')
    allowed=list(variables)+['t'];symbols=tuple(map(sympy().Symbol,allowed))
    change=sympy().Matrix([expression(a,allowed)[0]-expression(b,allowed)[0] for a,b in zip(target_drift,original_drift)])
    sigma=sympy().Matrix([[expression(v,allowed)[0] for v in row] for row in diffusion])
    if sympy().simplify(sigma.det())==0:raise ValueError('Diffusion is identically singular')
    theta=(sigma.inv()*change).applyfunc(sympy().simplify)
    kernel=sympy().lambdify(symbols,theta,modules='numpy',cse=True)
    dt=clock/len(brownian);terms=[]
    for i,(state,increment) in enumerate(zip(trajectory[:-1],brownian)):
        value=np.asarray(kernel(*state,i*dt),dtype=float).reshape(n)
        if not np.isfinite(value).all():raise ArithmeticError('Girsanov drift change reached a singular diffusion')
        terms.append(float(value@increment-.5*dt*(value@value)))
    return {'log_weight':float(sum(terms)),'increments':terms,'time_step':dt,
            'hypotheses':'Equivalent laws require integrability such as Novikov and valid drift/diffusion domains',
            'scope':'Left-point discretized stochastic exponential; not a continuous-path equivalence certificate'}


def bernstein_concentration(bound, variance, samples, error_probability=.05):
    """Bernstein deviation radius for independent centered bounded observations.

    Assumptions: |X_i−E X_i|<=bound, and average variance<=variance. The
    returned two-sided radius solves the standard exponential upper bound;
    inputs are declared bounds, not estimates promoted into known constants.
    """
    if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in (bound,variance)):
        raise ValueError('Finite nonnegative known bound/variance required')
    if type(samples) is not int or not 1<=samples<=10**12 or not 0<error_probability<1:
        raise ValueError('Positive sample count and interior error probability required')
    log=math.log(2/error_probability)
    radius=bound*log/(3*samples)+math.sqrt(2*variance*log/samples+(bound*log/(3*samples))**2)
    return {'radius':radius,'samples':samples,'error_probability':error_probability,
            'hypotheses':'Independent common-mean samples with the DECLARED known centered bound and variance bound',
            'rounding':'Floating-point evaluation of an analytic concentration inequality'}


__all__ += ['GaussianMixture','conditional_gaussian','gaussian_wasserstein',
            'girsanov_log_weight','bernstein_concentration']


class SurvivalAnalysis:
    """Right-censored survival estimates with explicit tied-event risk sets."""
    @staticmethod
    def _data(times, events, entry=None):
        import numpy as np
        clock=_array(times,1,100000)
        if (clock<0).any() or not isinstance(events,(list,tuple)) or len(events)!=len(clock) or any(type(v) is not int or v not in (0,1) for v in events):
            raise ValueError('Nonnegative event/censor times and binary event flags required')
        start=np.zeros(len(clock)) if entry is None else _array(entry,1,100000)
        if start.shape!=clock.shape or (start<0).any() or (start>clock).any():raise ValueError('Entry times must precede their event/censor times')
        return clock,np.asarray(events,dtype=int),start

    @classmethod
    def kaplan_meier(cls, times, events, *, entry=None, confidence=.95):
        import numpy as np
        from scipy.special import ndtri
        clock,event,start=cls._data(times,events,entry)
        if type(confidence) not in (int,float) or not 0<confidence<1:raise ValueError('Interior confidence level required')
        unique=np.unique(clock)
        if len(unique)*len(clock)>10000000:raise ValueError('Survival risk-set evaluation budget exceeded')
        survival=1.;greenwood=0.;hazard=0.;hazard_variance=0.;rows=[];z=float(ndtri((1+confidence)/2))
        for time in unique:
            risk=int(np.sum((start<=time)&(clock>=time)));deaths=int(np.sum((clock==time)&(event==1)));censored=int(np.sum((clock==time)&(event==0)))
            if risk<=0 or deaths>risk:raise ArithmeticError('Survival risk set became inconsistent')
            if deaths:
                hazard+=deaths/risk;hazard_variance+=deaths/risk**2;survival*=1-deaths/risk
                if risk>deaths:greenwood+=deaths/(risk*(risk-deaths))
            if survival in (0.,1.):lower=upper=survival
            else:
                loglog=math.log(-math.log(survival));se=math.sqrt(greenwood)/abs(math.log(survival))
                upper=math.exp(-math.exp(max(-700,min(700,loglog-z*se))))
                lower=math.exp(-math.exp(max(-700,min(700,loglog+z*se))))
            rows.append({'time':float(time),'at_risk':risk,'events':deaths,'censored':censored,
                         'survival':survival,'lower':lower,'upper':upper,
                         'greenwood_variance':survival**2*greenwood if survival>0 else 0.,
                         'nelson_aalen_hazard':hazard,'hazard_variance':hazard_variance})
        return {'table':rows,'confidence':confidence,'observations':len(clock),'events':int(event.sum()),
                'scope':'Kaplan-Meier with independent/noninformative censoring and appropriate delayed-entry assumptions; pointwise log-log intervals'}

    @classmethod
    def restricted_mean(cls, times, events, horizon):
        horizon=_positive(horizon,'restricted mean horizon')
        result=cls.kaplan_meier(times,events);previous=0.;survival=1.;area=0.
        for row in result['table']:
            time=min(row['time'],horizon)
            area+=(time-previous)*survival;previous=time
            if time>=horizon:break
            survival=row['survival']
        if previous<horizon:area+=(horizon-previous)*survival
        return {'restricted_mean':area,'horizon':horizon,
                'extrapolates_beyond_last_observation':horizon>max(times),
                'scope':'Step-function KM integral; tail beyond observation support is not empirically identified'}

    @classmethod
    def logrank(cls, times, events, groups):
        import numpy as np
        from scipy.stats import chi2
        clock,event,start=cls._data(times,events)
        if not isinstance(groups,(list,tuple)) or len(groups)!=len(clock) or any(type(v) is not int or v not in (0,1) for v in groups) or set(groups)!={0,1}:
            raise ValueError('Two nonempty groups labeled zero/one required')
        group=np.asarray(groups);unique=np.unique(clock[event==1])
        if len(unique)*len(clock)>10000000:raise ValueError('Log-rank risk-set budget exceeded')
        observed=expected=variance=0.
        for time in unique:
            risk=clock>=time;n=int(risk.sum());n1=int(np.sum(risk&(group==1)))
            deaths=(clock==time)&(event==1);d=int(deaths.sum());d1=int(np.sum(deaths&(group==1)))
            observed+=d1;expected+=d*n1/n
            if n>1:variance+=n1*(n-n1)*d*(n-d)/(n*n*(n-1))
        if variance==0:return {'statistic':None,'p_value':None,'reason':'No informative event variance','observed':observed,'expected':expected}
        statistic=(observed-expected)**2/variance
        return {'statistic':statistic,'p_value':float(chi2.sf(statistic,1)),
                'observed':observed,'expected':expected,'variance':variance,
                'scope':'Asymptotic two-group log-rank test; independent/noninformative censoring assumptions required'}

    @classmethod
    def cox_partial_likelihood(cls, times, events, predictors, coefficients):
        import numpy as np
        from scipy.special import logsumexp
        clock,event,start=cls._data(times,events)
        x=_array(predictors,2,160000);beta=_array(coefficients,1,16)
        if len(x)!=len(clock) or x.shape[1]!=len(beta):raise ValueError('Cox predictor/coefficient dimensions differ')
        unique=np.unique(clock[event==1])
        if len(unique)*len(clock)*len(beta)>2000000:raise ValueError('Cox risk-set work budget exceeded')
        eta=x@beta;likelihood=0.;score=np.zeros(len(beta));information=np.zeros((len(beta),len(beta)))
        for time in unique:
            risk=clock>=time;deaths=(clock==time)&(event==1);count=int(deaths.sum())
            logsum=float(logsumexp(eta[risk]));weights=np.exp(eta[risk]-logsum);risk_x=x[risk]
            mean=weights@risk_x;centered=risk_x-mean
            likelihood+=float(eta[deaths].sum())-count*logsum
            score+=x[deaths].sum(axis=0)-count*mean
            information+=count*(centered.T*weights)@centered
        return {'log_partial_likelihood':likelihood,'score':score.tolist(),'observed_information':information.tolist(),
                'ties':'Breslow','scope':'Fixed-coefficient Cox partial likelihood, not a fitted causal or proportional-hazards validation'}


__all__ += ['SurvivalAnalysis']


def bootstrap_interval(values, *, statistic='mean', replicates=2000, confidence=.95,
                       method='bca', seed=0):
    """Percentile/basic/BCa bootstrap intervals with recorded seed and assumptions.

    Resampling assumes iid observations from the target sampling law. BCa uses
    leave-one-out acceleration and a finite-replicate continuity correction for
    the bias quantile. These are approximate frequentist intervals, not finite-
    sample confidence certificates for arbitrary heavy tails or time series.
    """
    import numpy as np
    from scipy.special import ndtr,ndtri
    data=_array(values,1,100000);n=len(data)
    if statistic not in ('mean','median','variance') or method not in ('percentile','basic','bca'):
        raise ValueError('Unknown bootstrap statistic or interval method')
    if statistic=='variance' and n<2:raise ValueError('Sample variance needs at least two observations')
    if type(replicates) is not int or not 100<=replicates<=100000 or n*replicates>2000000:
        raise ValueError('Bootstrap work budget exceeded')
    if not 0<confidence<1 or type(seed) is not int or not 0<=seed<2**64:
        raise ValueError('Invalid confidence level or bootstrap seed')
    if method=='bca' and (n<3 or n>2000):raise ValueError('BCa jackknife requires 3–2000 observations')
    def estimate(array,axis=None):
        if statistic=='mean':return np.mean(array,axis=axis)
        if statistic=='median':return np.median(array,axis=axis)
        return np.var(array,axis=axis,ddof=1)
    rng=np.random.Generator(np.random.PCG64(seed));indices=rng.integers(0,n,size=(replicates,n))
    estimates=np.asarray(estimate(data[indices],axis=1));point=float(estimate(data))
    alpha=(1-confidence)/2;quantiles=[alpha,1-alpha];correction=acceleration=None
    if method=='bca':
        fraction=(np.sum(estimates<point)+.5*np.sum(estimates==point))/replicates
        fraction=float(np.clip(fraction,.5/replicates,1-.5/replicates));correction=float(ndtri(fraction))
        jackknife=np.asarray([estimate(np.delete(data,i)) for i in range(n)])
        deviations=jackknife.mean()-jackknife;squared=float(np.sum(deviations**2))
        acceleration=float(np.sum(deviations**3)/(6*squared**1.5)) if squared>0 else 0.
        adjusted=[]
        for quantile in quantiles:
            z=float(ndtri(quantile));denominator=1-acceleration*(correction+z)
            if denominator<=0:raise ArithmeticError('BCa correction has a singular/nonmonotone endpoint transform')
            adjusted.append(float(ndtr(correction+(correction+z)/denominator)))
        quantiles=adjusted
    lower,upper=map(float,np.quantile(estimates,quantiles))
    if method=='basic':lower,upper=2*point-upper,2*point-lower
    if lower>upper or not all(math.isfinite(v) for v in (point,lower,upper)):
        raise ArithmeticError('Bootstrap interval became nonfinite or reversed')
    return {'estimate':point,'lower':lower,'upper':upper,'confidence':confidence,
            'method':method,'statistic':statistic,'replicates':replicates,'seed':seed,
            'bias_z0':correction,'acceleration':acceleration,
            'scope':'Approximate iid bootstrap interval; no distribution-free finite-sample coverage claim'}


def permutation_mean_test(left, right, *, alternative='two_sided', method='monte_carlo',
                          permutations=10000, seed=0):
    """Exchangeability permutation test with exact or +1 Monte Carlo p-values."""
    import numpy as np
    from itertools import combinations
    x=_array(left,1,10000);y=_array(right,1,10000);data=np.concatenate((x,y));n=len(data);k=len(x)
    if alternative not in ('two_sided','greater','less') or method not in ('exact','monte_carlo'):
        raise ValueError('Invalid permutation alternative or method')
    if type(seed) is not int or not 0<=seed<2**64:raise ValueError('Unsigned 64-bit permutation seed required')
    observed=float(x.mean()-y.mean());total=float(data.sum())
    def statistic(indices):
        first=float(data[indices].sum())
        return first/k-(total-first)/(n-k)
    def extreme(value):
        if alternative=='two_sided':return abs(value)>=abs(observed)-1e-14
        if alternative=='greater':return value>=observed-1e-14
        return value<=observed+1e-14
    exceed=0
    if method=='exact':
        count=math.comb(n,k)
        if count>100000 or count*k>2000000:raise ValueError('Exact permutation enumeration budget exceeded')
        for indices in combinations(range(n),k):exceed+=int(extreme(statistic(list(indices))))
        p_value=exceed/count
    else:
        if type(permutations) is not int or not 1<=permutations<=100000 or permutations*n>2000000:
            raise ValueError('Monte Carlo permutation budget exceeded')
        rng=np.random.Generator(np.random.PCG64(seed));count=permutations
        for _ in range(count):exceed+=int(extreme(statistic(rng.permutation(n)[:k])))
        p_value=(exceed+1)/(count+1)
    return {'observed_mean_difference':observed,'p_value':p_value,'extreme_permutations':exceed,
            'permutations':count,'method':method,'alternative':alternative,'seed':seed,
            'hypotheses':'Group labels are exchangeable under the null; equality of means alone is insufficient under arbitrary heteroskedastic laws'}


__all__ += ['bootstrap_interval','permutation_mean_test']


def empirical_characteristic_function(samples, frequencies, *, weights=None):
    """Vectorized empirical Fourier transform with iid standard-error estimates.

    Weighted estimates require deterministic normalized weights. The reported
    component variances use independent samples and do not account for MCMC
    autocorrelation or uncertainty in estimated weights.
    """
    import numpy as np
    values = _array(samples, 1, 100000)
    points = _array(frequencies, 1, 10000)
    if len(values)*len(points) > 2000000:
        raise ValueError('Characteristic-function work budget exceeded')
    probabilities = np.full(len(values), 1/len(values)) if weights is None else _array(weights, 1)
    if probabilities.shape != values.shape or np.any(probabilities < 0):
        raise ValueError('Nonnegative weights matching the samples required')
    if not np.isclose(probabilities.sum(), 1, rtol=1e-12, atol=1e-14):
        raise ValueError('Weights must already sum to one')
    phase = points[:, None]*values[None, :]
    real = np.cos(phase)
    imaginary = np.sin(phase)
    mean_real = real@probabilities
    mean_imaginary = imaginary@probabilities
    squared_weights = probabilities**2
    denominator = 1-float(squared_weights.sum())
    if denominator <= 0:
        variance_real = variance_imaginary = None
    else:
        variance_real = ((real-mean_real[:, None])**2@probabilities*float(squared_weights.sum())/denominator).tolist()
        variance_imaginary = ((imaginary-mean_imaginary[:, None])**2@probabilities*float(squared_weights.sum())/denominator).tolist()
    return {'frequencies': points.tolist(), 'real': mean_real.tolist(),
            'imaginary': mean_imaginary.tolist(),
            'real_mean_variance': variance_real, 'imaginary_mean_variance': variance_imaginary,
            'effective_sample_size': float(1/squared_weights.sum()),
            'scope': 'Empirical characteristic function; independent-observation variance estimate'}


def entropy_power(covariance):
    """Gaussian entropy power det(Sigma)^(1/d), using a stable log determinant."""
    import numpy as np
    matrix = _array(covariance, 2)
    if matrix.shape[0] != matrix.shape[1] or len(matrix) > 128:
        raise ValueError('Square covariance of dimension at most 128 required')
    matrix = _covariance(matrix, len(matrix), 'covariance', positive_definite=True)
    _, logdet = np.linalg.slogdet(matrix)
    power = float(np.exp(logdet/len(matrix)))
    entropy = float((len(matrix)*math.log(2*math.pi*math.e)+logdet)/2)
    return {'entropy_nats': entropy, 'entropy_power': power,
            'dimension': len(matrix), 'distribution': 'Gaussian'}


__all__ += ['empirical_characteristic_function', 'entropy_power']
