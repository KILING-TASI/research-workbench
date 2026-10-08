"""Transparent covariance and normalized variance-contribution diagnostics."""
import math
import numpy as np


def covariance_diagnostics(sample, estimated, observations, shrinkage=None):
    sample=np.asarray(sample,dtype=float);estimated=np.asarray(estimated,dtype=float)
    if sample.ndim!=2 or sample.shape[0]!=sample.shape[1] or not 2<=sample.shape[0]<=6 or estimated.shape!=sample.shape:
        raise ValueError('诊断需要同维度的2至6资产方阵')
    if not np.isfinite(sample).all() or not np.isfinite(estimated).all():raise ValueError('协方差必须有限')
    if isinstance(observations,bool) or not isinstance(observations,int) or observations<1:raise ValueError('收益观察数须为正整数')
    if shrinkage is not None:
        if not isinstance(shrinkage,dict):raise ValueError('收缩信息须为对象')
        intensity=shrinkage.get('intensity')
        if isinstance(intensity,bool) or not isinstance(intensity,(int,float)) or not math.isfinite(intensity) or not 0<=intensity<=1:
            raise ValueError('收缩强度须在0至1之间')
    def condition(value):
        c=float(np.linalg.cond(value))
        return c if math.isfinite(c) else None
    before,after=condition(sample),condition(estimated)
    warnings=[]
    if before is None or before>1e8:
        warnings.append('样本协方差接近奇异，可能有高度重复的资产；不自动删除标的。')
    if shrinkage and shrinkage.get('intensity',0)>.5:
        warnings.append('收缩强度超过50%，结果对目标矩阵依赖较大；不等于可靠性概率。')
    return {'sampleConditionNumber':before,'estimatedConditionNumber':after,
            'assetsPerObservation':sample.shape[0]/observations,
            'conditionNumberConvention':'2-norm; null means infinite or undefined',
            'warnings':warnings}


def risk_concentration(shares):
    if shares is None:return {'status':'undefined-zero-variance','effectiveRiskContributors':None}
    s=np.asarray(shares,dtype=float)
    if s.ndim!=1 or len(s)<1 or not np.isfinite(s).all() or abs(float(s.sum())-1)>1e-7:
        raise ValueError('风险贡献占比须有限且合计为1')
    if (s < -1e-10).any():
        return {'status':'signed-contributions-not-concentration','effectiveRiskContributors':None,
                'note':'有负贡献的对冲项，不能将占比平方倒数解释成独立风险数量'}
    value=1/float(s@s)
    return {'status':'nonnegative-contributions','effectiveRiskContributors':value,
            'note':'基于归一化方差贡献的集中度等效数，不是独立风险来源数'}
