"""First prediction capture, separated historical replay, and matched-sample review."""
import argparse,datetime as dt,hashlib,json,math,re,statistics,uuid
from decimal import Decimal
from pathlib import Path
from allocation_cash import calculate,LABELS

def now():return dt.datetime.now(dt.timezone.utc)
def stamp(value):
    d=dt.datetime.fromisoformat(value)
    if d.tzinfo is None:raise ValueError('时间戳须带时区')
    return d

def hashvalue(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def read(path):
    r=json.loads(Path(path).read_text(encoding='utf-8'));h=r.pop('recordHash')
    if hashvalue(r)!=h:raise ValueError('档案被修改')
    r['recordHash']=h;return r

def store(path,r):
    r['recordHash']=hashvalue(r);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2,allow_nan=False)
    return r

def capture(spec,workspace,replay=False):
    model=spec['modelVersion']
    if not isinstance(model,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',model) or model in ['.','..']:raise ValueError('modelVersion格式无效')
    recorded=now();cutoff=stamp(spec['decisionCutoff'])
    if not replay and recorded>=cutoff:raise ValueError('决策截止时点已过去，只能历史回放，不能补造冻结预测')
    inputs=spec.get('inputs')
    if not isinstance(inputs,list) or not 1<=len(inputs)<=50:raise ValueError('需1至50项输入可得时间和文件')
    plan=calculate(spec['allocation']);code=plan['code']
    if cutoff.date().isoformat()!=spec['allocation']['applyDate']:raise ValueError('截止日须对应申购日，按时间戳所给时区解释')
    origin=Path(workspace)/'research-data'/'bjx-predictions'/('replays' if replay else 'frozen')/model/code
    path=origin/('replay-'+uuid.uuid4().hex+'.json' if replay else 'first.json')
    signature=hashvalue(spec)
    if path.exists():
        old=read(path)
        if old['inputSpecHash']!=signature:raise ValueError('首次预测已存在，不允许更新；使用新模型版本或独立历史回放')
        return {**old,'duplicate':True}
    checked=[];blobs=[]
    for item in inputs:
        available=stamp(item['availableAt']);observed=stamp(item['retrievedAt'])
        if available>observed or available>cutoff or (not replay and (available>recorded or observed>recorded)):raise ValueError('输入含未来可得时间')
        blob=Path(item['path']).read_bytes()
        if len(blob)>100*1024*1024:raise ValueError('单文件超过100MiB')
        h=hashlib.sha256(blob).hexdigest()
        if item.get('sha256') and item['sha256']!=h:raise ValueError('输入文件哈希不符')
        checked.append({'sourceUrl':item.get('sourceUrl'),'availableAt':item['availableAt'],'retrievedAt':item['retrievedAt'],'sha256':h,'archiveName':h+'.bin','availabilityProof':'caller-declared-not-independently-attested','retrospectiveCopy':observed>cutoff})
        blobs.append((h,blob))
    origin.mkdir(parents=True,exist_ok=True);lock=origin/'write.lock'
    with lock.open('x') as f:f.write('locked')
    try:
        if path.exists():raise ValueError('首次预测并发写入，已保留原记录')
        archives=origin/'inputs';archives.mkdir(exist_ok=True)
        for h,blob in blobs:
            target=archives/(h+'.bin')
            if not target.exists():target.write_bytes(blob)
        r={'type':'bjx-prediction-record','mode':'historical-replay' if replay else 'first-live-capture',
           'code':code,'modelVersion':model,'recordedAt':recorded.isoformat(),'decisionCutoff':spec['decisionCutoff'],
           'inputSpecHash':signature,'allocationSpec':spec['allocation'],'prediction':plan,'inputs':checked,
           'codeHashes':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ['prediction_review.py','allocation_cash.py']},
           'limitations':['本地时钟与输入发布时间为待外部核验依据，不是可信时间戳认证','历史回放永不升级为已冻结事前预测','首次文件不可由本工具更新，仍需备份防文件系统人为改写']}
        return store(path,r)
    finally:lock.unlink()

def review(spec,workspace):
    path=Path(spec['predictionPath']);prediction=read(path)
    for source in prediction['inputs']:
        if hashlib.sha256((path.parent/'inputs'/source['archiveName']).read_bytes()).hexdigest()!=source['sha256']:raise ValueError('预测输入档案被修改')
    actual=spec['actual'];published=stamp(actual['publishedAt'])
    if actual['code']!=prediction['code']:raise ValueError('实际结果代码不一致')
    if published>now():raise ValueError('实际公布时间尚未到，不能核验未来结果')
    if published<=stamp(prediction['decisionCutoff']):raise ValueError('实际公布不晚于决策截止日，不能用于本轮样本外验证')
    actual_path=Path(actual['sourcePath']);blob=actual_path.read_bytes()
    rate=Decimal(str(actual['ratePct']))
    if not rate.is_finite() or not 0<rate<=100:raise ValueError('实际配售率须(0,100]')
    allocation=dict(prediction['allocationSpec'])
    evidence=prediction['prediction'].get('factEvidence',{})
    if allocation.get('factsStore'):
        for key in ['price','maxShares','refundDate']:allocation[key]=evidence[key]['value']
        allocation.pop('factsStore')
    allocation={**allocation,'ratesPct':{k:str(rate) for k in LABELS},'rateBasis':'actual-rate-for-review-only'}
    actual_grade='caller-supplied-actual-not-automatically-original-verified'
    if actual.get('factsStore'):
        from issuance_facts import view
        facts=view({'code':actual['code'],'asOf':published.date().isoformat()},Path(actual['factsStore']))
        evidence=facts['facts']['ratePct']
        if not evidence or Decimal(evidence['value'])!=rate or evidence['documentSha256']!=hashlib.sha256(blob).hexdigest():raise ValueError('实际率、原文事实与来源PDF不一致')
        actual_grade='original-rate-text-matched-publication-time-declared'
    truth=calculate(allocation);reference=truth['scenarios']['P50'];actualfund=Decimal(reference['thresholdFunds']);metrics={}
    for label in LABELS:
        p=prediction['prediction']['scenarios'][label];fund=Decimal(p['thresholdFunds']) if p['thresholdFunds'] is not None else None
        metrics[label]={'predictedThresholdFunds':str(fund) if fund is not None else None,'actualConditionalThresholdFunds':str(actualfund),
            'absoluteErrorFunds':str(abs(fund-actualfund)) if fund is not None else None,'absoluteErrorPct':str(abs(fund/actualfund-1)*100) if fund is not None else None,
            'underestimated':fund<actualfund if fund is not None else None,'predictedRatePct':p['ratePct'],'actualRatePct':str(rate),
            'rateErrorPctPoints':str(Decimal(p['ratePct'])-rate),'wholeLotSharesError':p['wholeLotShares']-reference['wholeLotShares'],
            'actualConditionalReachable':reference['thresholdReachable']}
    realized=None
    if actual.get('allocatedShares') is not None:
        a=Decimal(str(actual['allocatedShares']))
        if not a.is_finite() or a<0 or a%100 or a>Decimal(prediction['prediction']['subscriptionShares']):raise ValueError('实际获配股数无效')
        realized={'allocatedShares':str(a),'actualVsWholeLotScenario':[{'scenario':k,'sharesDifference':str(a-Decimal(prediction['prediction']['scenarios'][k]['wholeLotShares']))} for k in LABELS]}
    if 'cashflowsComplete' in actual and type(actual['cashflowsComplete']) is not bool:raise ValueError('cashflowsComplete须布尔值')
    cashflows=actual.get('cashflows');cash_review=None
    if cashflows is not None:
        if not isinstance(cashflows,list) or not cashflows:raise ValueError('cashflows须非空流水')
        flows=[]
        for row in cashflows:
            day=dt.date.fromisoformat(row['date'])
            if day>now().date() or row['kind'] not in ['subscription','refund','settlement','fees','financing']:raise ValueError('流水日期或类型无效')
            amount=Decimal(str(row['amount']))
            if not amount.is_finite():raise ValueError('流水金额无效')
            flows.append({'date':row['date'],'amount':str(amount),'kind':row['kind']})
        cash_review={'flows':flows,'netCashFlow':str(sum(Decimal(r['amount']) for r in flows)),
            'scenarioNetProfitErrors':[{'scenario':k,'difference':str(Decimal(prediction['prediction']['scenarios'][k]['netProfit'])-sum(Decimal(r['amount']) for r in flows))} for k in LABELS] if actual.get('cashflowsComplete') is True else None,
            'complete':actual.get('cashflowsComplete') is True,'limitations':'用户提供流水，未核券商账单；不完整流水不解释为最终收益'}
    r={'type':'bjx-prediction-review','mode':prediction['mode'],'code':prediction['code'],'modelVersion':prediction['modelVersion'],
       'predictionHash':prediction['recordHash'],'decisionCutoff':prediction['decisionCutoff'],'recordedAt':now().isoformat(),
       'actual':actual,'actualSourceSha256':hashlib.sha256(blob).hexdigest(),'actualOutcomeKey':hashvalue({'code':actual['code'],'ratePct':str(rate.normalize()),'price':str(Decimal(str(allocation['price'])).normalize())}),
       'metrics':metrics,'realizedAllocation':realized,'cashflowReview':cash_review,
       'eligibleForFrozenComparison':prediction['mode']=='first-live-capture' and stamp(prediction['recordedAt'])<published,
       'evidenceGrade':actual_grade,
       'limitations':['金额目标为实际配售率条件下的整手门槛，不等于真实零股最低获配资金','实际结果只核验，不进入输入或调参','时间顺序检查不证明输入来源独立或历史数据完整']}
    target=Path(workspace)/'research-data'/'bjx-reviews'/(uuid.uuid4().hex+'.json');return store(target,r)

def compare(spec):
    groups=[];excluded=[]
    for name in ['before','after']:
        rows={}
        for filename in spec[name]:
            r=read(filename)
            if r['type']!='bjx-prediction-review' or not r['eligibleForFrozenComparison'] or r['mode']!='first-live-capture':excluded.append({'path':filename,'reason':'非首次冻结验证'});continue
            key=(r['code'],r['decisionCutoff'])
            if key in rows:raise ValueError('同一模型组存在重复样本')
            rows[key]=r
        if len({r['modelVersion'] for r in rows.values()})>1:raise ValueError('组内模型版本不统一')
        groups.append(rows)
    common=set(groups[0])&set(groups[1]);same=[]
    for key in sorted(common):
        a,b=[g[key] for g in groups]
        if a['actualOutcomeKey']!=b['actualOutcomeKey']:excluded.append({'sample':key,'reason':'实际目标或发行价不一致'});continue
        if any(r['metrics'][k]['absoluteErrorFunds'] is None for r in [a,b] for k in LABELS):excluded.append({'sample':key,'reason':'三档预测缺失'});continue
        same.append(key)
    summary={}
    for index,name in enumerate(['before','after']):
        summary[name]={}
        for label in LABELS:
            rows=[groups[index][key]['metrics'][label] for key in same];errors=sorted(Decimal(r['absoluteErrorFunds']) for r in rows);pct=sorted(Decimal(r['absoluteErrorPct']) for r in rows)
            summary[name][label]={'count':len(rows),'MAE':str(sum(errors)/len(errors)) if errors else None,
                'meanAbsoluteErrorPct':str(sum(pct)/len(pct)) if pct else None,'P90AbsoluteError':str(errors[math.ceil(.9*len(errors))-1]) if errors else None,
                'maxAbsoluteError':str(max(errors)) if errors else None,'P90AbsoluteErrorPct':str(pct[math.ceil(.9*len(pct))-1]) if pct else None,'maxAbsoluteErrorPct':str(max(pct)) if pct else None,'underestimationPct':str(Decimal(sum(r['underestimated'] for r in rows))/len(rows)*100) if rows else None}
    return {'type':'bjx-matched-model-comparison','commonCount':len(same),'commonSamples':same,'summary':summary,'excluded':excluded,
        'unmatchedCounts':{'before':len(set(groups[0])-common),'after':len(set(groups[1])-common)},'automaticReplacement':False,
        'limitations':['本地首次捕获与调用者实际结果，未自动证明已完成原文核验或外部时间戳认证','不含历史回放，不用不同覆盖样本宣称改善','小样本与尾部误差需单独评估，均值改善不自动通过替换']}

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','replay','review','compare']);p.add_argument('input',type=Path);p.add_argument('--workspace',type=Path,default=Path.cwd());p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('输出已存在')
    spec=json.loads(a.input.read_text(encoding='utf-8-sig'))
    result=capture(spec,a.workspace,a.command=='replay') if a.command in ['freeze','replay'] else review(spec,a.workspace) if a.command=='review' else compare(spec)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
if __name__=='__main__':main()
