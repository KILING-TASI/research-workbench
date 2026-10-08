"""Small convex minimum-variance solver with explicit group exposure bounds."""
import itertools,math
import numpy as np
from portfolio_models import number

def solve(cov,classes,bounds,lower=0,upper=1,mean=None,target=None):
    matrix=np.asarray(cov,dtype=float);n=len(classes);lower=number(lower);upper=number(upper)
    if not 2<=n<=6 or matrix.shape!=(n,n) or not np.isfinite(matrix).all() or not np.allclose(matrix,matrix.T,atol=1e-12,rtol=0) or np.linalg.eigvalsh(matrix).min()<-1e-12:raise ValueError('需要2至6资产、对称半正定有限协方差')
    if not 0<=lower<=upper<=1 or n*lower>1+1e-12 or n*upper<1-1e-12:raise ValueError('统一上下限不可行')
    scale=float(np.max(np.abs(matrix)))
    normalized=matrix/scale if scale else matrix.copy()
    if np.linalg.eigvalsh(normalized).min()<-1e-10:raise ValueError('协方差尺度归一后非半正定')
    if any(not isinstance(label,str) or not label.strip() for label in classes) or not isinstance(bounds,dict) or not 1<=len(bounds)<=3:raise ValueError('需要明确资产类别及1至3类约束')
    inequalities=[];limits=[]
    for i in range(n):
        row=np.zeros(n);row[i]=1;inequalities.extend((row,-row));limits.extend((lower,-upper))
    for label,limit in bounds.items():
        if label not in classes or not isinstance(limit,dict) or set(limit)!={'min','max'}:raise ValueError('类别须存在，且明确给出min/max')
        lo=number(limit['min']);hi=number(limit['max'])
        if not 0<=lo<=hi<=1:raise ValueError('类别上下限无效')
        row=np.array([float(value==label) for value in classes]);inequalities.extend((row,-row));limits.extend((lo,-hi))
    if mean is not None:
        mean=np.asarray(mean,dtype=float)
        if mean.shape!=(n,) or not np.isfinite(mean).all():raise ValueError('历史均值维度或数值无效')
    if target is not None:
        number(target)
        if mean is None:raise ValueError('目标需明确历史均值')
        if np.max(np.abs(mean-mean[0]))<1e-12:
            if abs(target-mean[0])>1e-10:raise ValueError('共同历史均值下目标不可行')
            target=None
    G=np.array(inequalities);h=np.array(limits);best=None;highest=None
    # Enumerate active inequality faces of a small-dimensional convex polytope.
    for count in range(n):
        for selected in itertools.combinations(range(len(h)),count):
            A=np.vstack([np.ones(n),G[list(selected)]]);b=np.concatenate([[1.],h[list(selected)]])
            if target is not None:A=np.vstack([A,mean]);b=np.concatenate([b,[target]])
            if np.linalg.matrix_rank(A)<len(A):continue
            K=np.block([[2*normalized,A.T],[A,np.zeros((len(A),len(A)))]])
            rhs=np.concatenate([np.zeros(n),b]);solution=np.linalg.lstsq(K,rhs,rcond=None)[0];w=solution[:n]
            if np.max(np.abs(K@solution-rhs))>1e-8 or np.min(G@w-h)<-1e-8:continue
            variance=float(w@matrix@w)
            if mean is not None:
                score=float(w@mean)
                if highest is None or score>highest:highest=score
            if best is None or variance<best[0]:best=(variance,w)
    if best is None:raise ValueError('类别与资产约束无可行稳定解；没有放宽条件')
    w=best[1]
    return {'weights':w.tolist(),'variance':best[0],'highestHistoricalMean':highest,'classWeights':{label:float(sum(w[i] for i,value in enumerate(classes) if value==label)) for label in set(classes)},'maxConstraintViolation':float(max(0,-np.min(G@w-h))),'status':'calculated-constrained-minimum-variance','limitations':['历史均值不代表预期收益，不是交易方案','仅给定协方差和约束下最小方差，不证明未来回撤预算']}
