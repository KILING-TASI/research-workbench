"""Constrained returns-based style fit; estimates behavior, not holdings or compliance."""
import argparse,itertools,json,hashlib
from pathlib import Path
import numpy as np
from portfolio_models import prepare
from research_pipeline import read
from research_brief_html import render

def fit(y,x):
    y=np.asarray(y,dtype=float);x=np.asarray(x,dtype=float)
    if y.ndim!=1 or x.ndim!=2 or len(y)!=len(x) or not 2<=x.shape[1]<=5 or not np.isfinite(y).all() or not np.isfinite(x).all():raise ValueError('拟合收益维度或数值无效')
    scale=float(np.std(y,ddof=1))
    if not np.isfinite(scale) or scale<=1e-12:raise ValueError('基金收益波动无效或近似不变，不能定义解释度')
    yc=(y-y.mean())/scale;xc=(x-x.mean(axis=0))/scale
    best=None
    for count in range(1,x.shape[1]+1):
        for free in itertools.combinations(range(x.shape[1]),count):
            a=xc[:,free];q=a.T@a;b=a.T@yc
            matrix=np.block([[q,np.ones((count,1))],[np.ones((1,count)),np.zeros((1,1))]])
            rhs=np.r_[b,1.0];solution=np.linalg.lstsq(matrix,rhs,rcond=None)[0]
            if np.max(np.abs(matrix@solution-rhs))>1e-7 or np.min(solution[:-1])< -1e-8:continue
            w=np.zeros(x.shape[1]);w[list(free)]=np.maximum(solution[:-1],0);w/=w.sum()
            variance=float(np.var(y-x@w,ddof=1))
            if best is None or variance<best[0]:best=(variance,w)
    if best is None:raise ValueError('未取得稳定可行的风格权重')
    variance,w=best;residual=y-x@w
    constrained_rank=int(np.linalg.matrix_rank(np.vstack([xc,np.ones((1,x.shape[1]))])))
    return {'weights':w.tolist(),'rSquaredVariance':1-variance/float(np.var(y,ddof=1)),
            'residualVariance':variance,'meanResidual':float(residual.mean()),'centeredFactorRank':int(np.linalg.matrix_rank(xc)),
            'constrainedDesignRank':constrained_rank,'weightIdentificationWarning':bool(constrained_rank<x.shape[1])}

def analyze(document):
    benchmarks=document.get('benchmarks')
    if not isinstance(benchmarks,list) or not 2<=len(benchmarks)<=5:raise ValueError('需要2至5个明确基准；避免堆叠高度重叠基准')
    for item in [document.get('fund')]+benchmarks:
        if not isinstance(item,dict) or ('name' in item and (not isinstance(item['name'],str) or not item['name'].strip())):raise ValueError('标的名称提供时须为非空文字')
    benchmark_role=document.get('benchmarkRole','user-selected-not-verified')
    if benchmark_role not in ('product-proxies','user-selected-not-verified','declared-style-indices'):raise ValueError('benchmarkRole仅支持产品代理、用户指定或声明风格指数')
    spec={key:document[key] for key in ('asOf','currency','frequency')}
    spec['assets']=[document['fund']]+benchmarks
    returns,_,_,dates=prepare(spec)
    minimum=120 if spec['frequency']=='daily' else 24
    if len(returns)<minimum:raise ValueError('收益观察不足；日度至少120组，月度至少24组，这是运行门槛而非统计可靠性保证')
    window=document.get('window',minimum);step=document.get('step',max(1,window//4) if isinstance(window,int) else 1)
    if isinstance(window,bool) or not isinstance(window,int) or not minimum<=window<=len(returns) or isinstance(step,bool) or not isinstance(step,int) or step<1:raise ValueError('滚动窗口或步长无效')
    full=fit(returns[:,0],returns[:,1:]);rolling=[]
    ends=list(range(window,len(returns)+1,step))
    if ends[-1]!=len(returns):ends.append(len(returns))
    for end in ends:
        rolling.append({'start':dates[end-window],'end':dates[end],**fit(returns[end-window:end,0],returns[end-window:end,1:])})
    matrix=np.array([row['weights'] for row in rolling])
    return {'type':'returns-based-style-observation','fundCode':document['fund']['code'],'benchmarkCodes':[row['code'] for row in benchmarks],
            'fundName':document['fund'].get('name'),'benchmarkNames':[row.get('name') for row in benchmarks],'benchmarkRole':benchmark_role,
            'start':dates[0],'end':dates[-1],'observations':len(returns),'fullSample':full,'rolling':rolling,
            'rollingWeightStd':np.std(matrix,axis=0,ddof=1).tolist() if len(matrix)>1 else None,
            'limitations':['权重拟合的是选定基准的收益暴露，不是披露仓位、真实交易或违规证据','R²下降可能由基准遗漏、估值滞后、汇率或关系变化引起，不能单独判断换赛道','币种、总收益及日期对齐来自输入；QDII净值所属日须事先核查，不固定套用T-1','滚动窗口重叠，权重标准差不是独立样本显著性检验；共线性可使权重不唯一','不能替代债券久期信用、发行人或FOF实际持仓穿透']}

def publish(document,out):
    out=Path(out)
    if out.exists():raise ValueError('输出目录已存在，请另存新结果')
    result=analyze(document);full=result['fullSample']
    body='# 收益行为是否符合选定风格基准？\n\n这次分析检查历史净值与基准收益的关系，不能据此认定实际持仓或合规状态。\n\n'
    if document.get('exampleType')=='teaching-only':body='**教学样本：收益与风格变化为合成数据，不是真实基金评价。**\n\n'+body
    body+='实际区间：'+result['start']+'至'+result['end']+'，收益观察'+str(result['observations'])+'组。\n\n'
    if result['fundName']:body+='研究对象：'+result['fundName'].replace('\n',' ')+'（'+result['fundCode']+'）。\n\n'
    role={'product-proxies':'本次基准是产品收益代理，不是官方风格因子；权重不能解释为实际资产配置。','user-selected-not-verified':'本次基准由输入者选择，适用性尚未认证。','declared-style-indices':'本次输入声明使用风格指数，指数版本与适用性仍须核查；此声明不构成官方认证。'}
    body+=role[result['benchmarkRole']]+'\n\n'
    if isinstance(document.get('sourceScope'),str):body+='本次输入范围：'+document['sourceScope']+'\n\n'
    body+='选定基准组合对本区间收益波动的解释度为'+format(full['rSquaredVariance']*100,'.2f')+'%。低解释度也可能意味着基准池不适配，不能直接归因于经理漂移。\n\n'
    if full['weightIdentificationWarning']:body+='**基准存在共线性，风格权重可能不唯一，不宜解读为确定配置。**\n\n'
    body+='|基准|样本内拟合权重|\n|---|---:|\n'
    labels=[(name+'（'+code+'）' if name else code).replace('|','／').replace('\n',' ') for name,code in zip(result['benchmarkNames'],result['benchmarkCodes'])]
    for label,weight in zip(labels,full['weights']):body+='|'+label+'|'+format(weight*100,'.2f')+'%|\n'
    body+='\n## 拟合关系有没有变化？\n\n共'+str(len(result['rolling']))+'个滚动窗口。'
    if result['rollingWeightStd'] is None:body+='只有一个窗口，不能计算跨窗口权重波动。\n\n'
    else:
        scores=[row['rSquaredVariance'] for row in result['rolling']]
        body+='窗口解释度介于'+format(min(scores)*100,'.2f')+'%与'+format(max(scores)*100,'.2f')+'%之间。下降不是漂移或违规的自动证明。\n\n'
        for label,value in zip(labels,result['rollingWeightStd']):body+=label+'的滚动权重标准差为'+format(value*100,'.2f')+'个百分点。\n\n'
    body+='\n## 下一步怎么看\n\n核查基准是否覆盖基金允许的资产、币种与估值时差，再对照滚动结果和样本外表现。权重变动仅作为需要进一步核查的线索，不直接转成调仓或违规判断。\n\n## 资料边界\n\n'+'\n\n'.join(result['limitations'])
    out.mkdir(parents=True)
    result['inputSha256']=hashlib.sha256(json.dumps(document,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    (out/'input.json').write_text(json.dumps(document,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
    (out/'收益风格说明.md').write_text(body,'utf-8');(out/'收益风格说明.html').write_text(render(body,'收益风格观察'),'utf-8')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='收益风格拟合，不推断持仓或违规')
    parser.add_argument('input');parser.add_argument('--out-dir',required=True)
    args=parser.parse_args();publish(read(args.input),args.out_dir)
