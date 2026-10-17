"""Finite exact Bayes and conjugate Beta-Binomial inference."""
from fractions import Fraction
from ..core.semantic_ir import rational
from ..math.statistics.bayesian import posterior, predictive


def beta_binomial(successes, trials, *, alpha=1, beta=1):
    if type(successes) is not int or type(trials) is not int or not 0 <= successes <= trials <= 1000000:
        raise ValueError('Require 0 <= successes <= trials <= 1000000')
    alpha, beta = rational(alpha), rational(beta)
    if min(alpha, beta) <= 0:
        raise ValueError('Beta shape parameters must be positive')
    a, b = alpha+successes, beta+trials-successes
    return {'alpha': str(a), 'beta': str(b), 'mean': str(a/(a+b)),
            'variance': str(a*b/((a+b)**2*(a+b+1))), 'predictive_success': str(a/(a+b)),
            'model': 'iid_bernoulli_with_beta_prior', 'arithmetic': 'exact_rational'}


__all__ = ['posterior', 'predictive', 'beta_binomial']


def conjugate_update(kind,data,prior):
    from ._area_utils import vector,scalar
    if kind=='gamma_poisson':
        if set(prior)!={'shape','rate'} or any(type(v) is not int or v<0 for v in data):raise ValueError('Gamma shape/rate prior and Poisson counts required')
        a,b=scalar(prior['shape']),scalar(prior['rate'])
        if min(a,b)<=0:raise ValueError('Positive Gamma parameters required')
        a+=sum(data);b+=len(data)
        return {'shape':str(a),'rate':str(b),'mean':str(a/b),'variance':str(a/b**2)}
    if kind=='dirichlet_multinomial':
        a=vector(prior['alpha'],maximum=256)
        if set(prior)!={'alpha'} or len(data)!=len(a) or any(type(v) is not int or v<0 for v in data) or any(v<=0 for v in a):raise ValueError('Positive Dirichlet prior and counts required')
        a=[v+n for v,n in zip(a,data)];return {'alpha':list(map(str,a)),'mean':[str(v/sum(a)) for v in a]}
    if kind=='normal_known_variance':
        if set(prior)!={'mean','variance','observation_variance'}:raise ValueError('Closed normal prior required')
        values=vector(data);mu,var,obs=(scalar(prior[k]) for k in ('mean','variance','observation_variance'))
        if min(var,obs)<=0:raise ValueError('Positive variances required')
        posterior_variance=1/(1/var+len(values)/obs);mean=posterior_variance*(mu/var+sum(values)/obs)
        return {'mean':str(mean),'variance':str(posterior_variance)}
    raise ValueError('Unsupported conjugate family')


def gaussian_hierarchy(design,response,prior_mean,prior_precision,noise_variance=1.):
    import numpy as np
    from ..math._structured import numeric_array
    x,y,m,p=(numeric_array(v,ndim=n,maximum=65536) for v,n in ((design,2),(response,1),(prior_mean,1),(prior_precision,2)))
    if x.shape!=(len(y),len(m)) or p.shape!=(len(m),len(m)) or not noise_variance>0 or not np.isfinite(noise_variance) or not np.allclose(p,p.T):raise ValueError('Invalid Gaussian hierarchy dimensions')
    np.linalg.cholesky(p);precision=p+x.T@x/noise_variance;covariance=np.linalg.inv(precision);mean=covariance@(p@m+x.T@y/noise_variance)
    # Reverse-KL optimal independent Gaussian for a correlated Gaussian target.
    return {'posterior_mean':mean.tolist(),'posterior_covariance':covariance.tolist(),'mean_field_variances':(1/np.diag(precision)).tolist(),
            'assumptions':'Linear Gaussian likelihood and proper Gaussian prior; group effects are columns of the supplied design.'}


def sample_posterior(log_density,variables,initials,*,samples=1000,burn_in=200,scale=.5,seed=0):
    import numpy as np
    from ..math._structured import expression,sympy,numeric_array
    f,symbols=expression(log_density,variables);points=numeric_array(initials,ndim=2,maximum=256)
    if points.shape[1]!=len(variables) or not 2<=len(points)<=8 or type(samples) is not int or not 4<=samples<=20000 or len(points)*samples*len(variables)>200000 or type(burn_in) is not int or not 0<=burn_in<=20000 or not np.isfinite(scale) or scale<=0:raise ValueError('Posterior sampling budget exceeded')
    def target(point):
        try:value=float(f.subs(dict(zip(symbols,point))))
        except (TypeError,ValueError,OverflowError):return -np.inf
        return value if np.isfinite(value) else -np.inf
    rng=np.random.default_rng(seed);chains=[];accepted=[]
    for point in points:
        current=point.copy();score=target(current)
        if not np.isfinite(score):raise ValueError('Initial point has nonfinite log density')
        chain=[];hits=0
        for iteration in range(samples+burn_in):
            candidate=current+rng.normal(0,scale,len(current));candidate_score=target(candidate)
            if np.log(max(rng.random(),np.finfo(float).tiny))<candidate_score-score:current=candidate;score=candidate_score;hits+=1
            if iteration>=burn_in:chain.append(current.copy())
        chains.append(chain);accepted.append(hits/(samples+burn_in))
    array=np.asarray(chains);within=np.mean(np.var(array,axis=1,ddof=1),axis=0);between=samples*np.var(np.mean(array,axis=1),axis=0,ddof=1);variance=(samples-1)/samples*within+between/samples
    rhat=np.sqrt(np.divide(variance,within,out=np.full_like(within,np.inf),where=within>0))
    return {'chains':array.tolist(),'acceptance_rates':accepted,'rhat':[float(v) if np.isfinite(v) else None for v in rhat],
            'scope':'Seeded random-walk Metropolis; classical R-hat diagnostic is not a convergence certificate.'}


def posterior_diagnostics(chains):
    import numpy as np
    from scipy.stats import rankdata,norm
    from ..math._structured import numeric_array
    a=numeric_array(chains,ndim=3,maximum=200000);m,n,d=a.shape
    if m<2 or n<8 or d<1:raise ValueError('At least two chains, eight draws and one component required')
    half=n//2;split=np.concatenate((a[:,:half],a[:,-half:]),axis=0);m,n,_=split.shape
    def rhat(values):
        w=float(np.mean(np.var(values,axis=1,ddof=1)));b=n*float(np.var(np.mean(values,axis=1),ddof=1));v=(n-1)/n*w+b/n
        return math.sqrt(v/w) if w>0 else None
    import math
    rhats=[];ess=[];mcse=[]
    for j in range(d):
        raw=split[:,:,j];flat=raw.ravel();z=norm.ppf((rankdata(flat)-3/8)/(len(flat)+1/4)).reshape(m,n)
        folded=np.abs(raw-np.median(flat));fz=norm.ppf((rankdata(folded.ravel())-3/8)/(len(flat)+1/4)).reshape(m,n)
        first,second=rhat(z),rhat(fz);rhats.append(max(first,second) if first is not None and second is not None else None)
        w=float(np.mean(np.var(raw,axis=1,ddof=1)));b=n*float(np.var(np.mean(raw,axis=1),ddof=1));variance=(n-1)/n*w+b/n
        if variance<=0:ess.append(None);mcse.append(None);continue
        centered=raw-raw.mean(axis=1,keepdims=True);size=1<<(2*n-1).bit_length();transform=np.fft.rfft(centered,n=size,axis=1);acov=np.fft.irfft(transform*np.conjugate(transform),n=size,axis=1)[:,:n]/n
        rho=1-(w-acov.mean(axis=0))/variance;rho[0]=1;paired=[]
        for t in range(0,n-1,2):
            value=float(rho[t]+rho[t+1])
            if value<0:break
            paired.append(min(value,paired[-1]) if paired else value)
        tau=max(1.,-1+2*sum(paired));effective=min(m*n,m*n/tau);ess.append(effective);mcse.append(math.sqrt(variance/effective))
    return {'rank_normalized_split_rhat':rhats,'effective_sample_size':ess,'monte_carlo_standard_error':mcse,
            'scope':'Rank-normalized/folded split R-hat and initial-positive-sequence ESS estimates; no proof of convergence.'}
