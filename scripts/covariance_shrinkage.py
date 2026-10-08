"""Python adaptation of Ledoit/Wolf covCor (2021), constant-correlation target.
Source: https://github.com/oledoit/covShrinkage/blob/main/covCor.m

Copyright (c) 2014-2021, Olivier Ledoit and Michael Wolf
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
"""
import numpy as np

def estimate(returns):
    data=np.asarray(returns,dtype=float)
    if data.ndim!=2 or data.shape[0]<24 or not 2<=data.shape[1]<=6 or not np.isfinite(data).all():raise ValueError('自动收缩需要至少24个对齐收益观察和2至6资产')
    observations,assets=data.shape;degrees=observations-1
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        try:
            centered=data-data.mean(axis=0);sample=centered.T@centered/degrees
            variances=np.diag(sample);std=np.sqrt(variances)
            if np.any(std<=0):raise ValueError('零方差资产不能估计常相关目标')
            average=float((np.sum(sample/np.outer(std,std))-assets)/(assets*(assets-1)))
            target=average*np.outer(std,std);np.fill_diagonal(target,variances)
            fourth=(centered**2).T@(centered**2)/degrees-sample**2
            distance=float(np.sum((sample-target)**2))
            cross=(centered**3).T@centered/degrees-variances[:,None]*sample
            np.fill_diagonal(cross,0)
            rho=float(np.trace(fourth)+average*np.sum(np.outer(1/std,std)*cross))
            intensity=0. if distance<=np.finfo(float).eps*float(np.sum(sample**2)) else float(np.clip((fourth.sum()-rho)/(degrees*distance),0,1))
            covariance=intensity*target+(1-intensity)*sample
        except FloatingPointError as error:raise ValueError('自动收缩数值溢出或除零') from error
    if not np.isfinite(covariance).all():raise ValueError('自动收缩结果非有限')
    return covariance,{'method':'ledoit-wolf-constant-correlation','intensity':intensity,'averageCorrelation':average,'observations':observations,'covarianceDivisor':degrees,'sourceUrl':'https://github.com/oledoit/covShrinkage/blob/main/covCor.m','status':'sample-equals-target' if intensity==0 and distance<=np.finfo(float).eps*float(np.sum(sample**2)) else 'estimated','limitations':['原估计假设独立同分布，不保证金融序列满足','强度估计不证明样本外风险改善']}
