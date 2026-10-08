"""Conditional Monte Carlo diagnostics, not uncertainty about future losses."""
import math
import numpy as np


def quantile_precision(values, probability=.95):
    x=np.asarray(values,dtype=float)
    if x.ndim!=1 or len(x)<100 or not np.isfinite(x).all():raise ValueError('分位精度需要至少100个有限模拟值')
    if not 0<probability<1:raise ValueError('分位概率须在0和1之间')
    q=float(np.quantile(x,probability));n=len(x)
    result={'quantile':q,'paths':n,'monteCarloStandardError':None,
            'probability':probability,'valueUnit':'same-as-input',
            'scope':'given sample, weights and bootstrap model; not future-risk confidence',
            'method':'Gaussian kernel density plug-in, asymptotic quantile SE'}
    std=float(np.std(x,ddof=1));bandwidth=1.06*std*n**(-.2)
    # A point mass at the target invalidates the continuous-density formula.
    rank_low,rank_high=np.quantile(x,[max(0,probability-.02),min(1,probability+.02)])
    if n<500 or bandwidth<=0 or len(np.unique(x))<10 or rank_low==rank_high:
        result['status']='not-estimated-small-or-discrete-tail'
        return result
    density=float(np.mean(np.exp(-.5*((q-x)/bandwidth)**2))/(bandwidth*math.sqrt(2*math.pi)))
    if density<=0 or not math.isfinite(density):
        result['status']='not-estimated-density';return result
    result.update(status='estimated-conditional-monte-carlo-error',
                  monteCarloStandardError=math.sqrt(probability*(1-probability)/n)/density,
                  bandwidth=bandwidth)
    return result


def stationary_next(rng, indices, observations, expected_block_length):
    restart=rng.random(len(indices))<1/expected_block_length
    return np.where(restart,rng.integers(0,observations,size=len(indices)),(indices+1)%observations)
