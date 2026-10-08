"""Bounded retries and atomic, request-bound restart checkpoints."""
import datetime as dt
import hashlib
import json
import math
import re
import time
from pathlib import Path
from market_collect import KINDS, atomic, collect_market
from collection_validation import day as validated_day, unique_pairs, reject_constant, finite_json_float, market_rows

def valid_nav(value):
    try:return not isinstance(value,bool) and isinstance(value,(int,float)) and math.isfinite(value) and value>0
    except OverflowError:return False

def validate_market_components(row,request,as_of):
    start=request.get('start','2000-01-01')
    for name in ['financials','announcements']:
        values=row.get(name,[])
        if not isinstance(values,list):raise ValueError('资料组件须为列表：'+name)
        if not values:continue
        market_rows(name,values)
        if name=='financials':
            begin=request.get('financialStart',start)
            if any(not begin<=v['period']<=as_of or v['publishedAt']>as_of for v in values):raise ValueError('财务资料超出研究时点')
            if any(v.get('raw',{}).get('SECURITY_CODE',request['code'])!=request['code'] for v in values):raise ValueError('财务证券身份不一致')
        elif any(not start<=v['date']<=as_of for v in values):raise ValueError('公告资料超出研究时点')

def row_hash(row):
    return hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()

def method_hashes():
    return {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ['batch_collect.py','market_collect.py','portable_collect.py','collection_validation.py','atomic_json.py']}

def run(workspace, document, legacy):
    if not isinstance(document,dict):raise ValueError('批量请求须为对象')
    as_of=document.get('asOf')
    if not isinstance(as_of,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',as_of):raise ValueError('截止日期须为YYYY-MM-DD')
    dt.date.fromisoformat(as_of)
    requests=document.get('requests'); refresh=document.get('refresh',False)
    if not isinstance(refresh,bool):raise ValueError('refresh须为布尔值')
    if not isinstance(document.get('resume',False),bool):raise ValueError('resume须为布尔值')
    if not isinstance(requests,list) or not 1<=len(requests)<=1000:raise ValueError('requests须为1至1000项')
    retries=document.get('retries',2)
    if type(retries)!=int or not 0<=retries<=3:raise ValueError('retries须为0至3')
    job=document.get('jobId')
    if job is not None and (not isinstance(job,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',job)):raise ValueError('jobId格式无效')
    if job and re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])',job):raise ValueError('jobId不能使用Windows保留名称')
    if document.get('resume') and not job:raise ValueError('resume需要jobId')
    seen=set()
    for r in requests:
        if not isinstance(r,dict) or r.get('kind') not in ['fund']+KINDS or not isinstance(r.get('code'),str) or not re.fullmatch(r'\d{6}',r['code']):raise ValueError('须明确类型和六位字符串代码')
        inferred='1' if r['code'].startswith(('5','6')) else '0'
        key=(r['kind'],r['code'],str(r.get('market',inferred if r['kind'] in ['stock','etf'] else '')))
        if key in seen:raise ValueError('重复对象')
        seen.add(key)
        if r.get('financialStart') is not None:
            from collection_validation import day
            if r['kind']!='stock' or day(r['financialStart'])>day(as_of):raise ValueError('financialStart仅用于股票，且不晚于截止日')
        if r['kind']!='fund' or 'start' in r:
            start=r.get('start','2000-01-01')
            if not isinstance(start,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',start):raise ValueError('起始日期须为YYYY-MM-DD')
            try:start_date=dt.date.fromisoformat(start)
            except (ValueError,TypeError) as exc:raise ValueError('起始日期须为YYYY-MM-DD') from exc
            if start_date>dt.date.fromisoformat(as_of):raise ValueError('起始日期晚于截止日')
            market=r.get('market')
            if market is not None and (isinstance(market,bool) or str(market) not in ['0','1']):raise ValueError('market须为0深市或1沪市')
            if r['kind'] not in ['stock','etf','fund'] and market is None:raise ValueError('债券须明确market=0或1')
            if r['kind']!='fund' and market is None and r['code'].startswith(('4','8','92')):raise ValueError('北交所历史市场映射尚未核验')
    signature=hashlib.sha256(json.dumps({'asOf':as_of,'requests':requests,'refresh':refresh},sort_keys=True).encode()).hexdigest()
    path=Path(workspace)/'research-data'/'batches'/(job+'.json') if job else None
    methods=method_hashes()
    state={'signature':signature,'rows':{},'rowHashes':{},'methodFiles':methods}
    if document.get('resume') and not path.exists():raise ValueError('续采断点不存在；请检查jobId或明确开始新批次')
    if path and path.exists():
        if not document.get('resume'):raise ValueError('jobId已存在；使用resume或新jobId')
        try:
            state=json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=unique_pairs, parse_constant=reject_constant, parse_float=finite_json_float)
            if not isinstance(state,dict) or not isinstance(state.get('rows'),dict) or not isinstance(state.get('rowHashes',{}),dict):raise ValueError('结构无效')
        except (ValueError,OSError) as exc:raise ValueError('断点文件不可读；请保留原文件并使用新jobId：'+str(exc)) from exc
        if state.get('signature')!=signature:raise ValueError('断点参数与原批次不一致')
        if state.get('methodFiles')!=methods:raise ValueError('采集或校验方法已变更，或旧断点未登记方法；保留原断点，使用新jobId重新执行，不能直接复用成功状态')
        state.setdefault('rowHashes',{})
    rows=[]
    for index,request in enumerate(requests):
        key=str(index);previous=state['rows'].get(key)
        expected_scope={'start':request.get('start',None if request['kind']=='fund' else '2000-01-01'),'asOf':as_of,'financialStart':request.get('financialStart')}
        try:
            intact=isinstance(previous,dict) and state['rowHashes'].get(key)==row_hash(previous)
            if intact:
                intact=previous.get('code')==request['code'] and previous.get('kind')==request['kind'] and previous.get('requestScope')==expected_scope
                if intact:
                    if not isinstance(previous.get('history',[]),list):raise ValueError('断点历史结构无效')
                    if request['kind']=='fund' and not previous.get('history'):raise ValueError('断点基金净值为空')
                    if request['kind']=='fund' and any(not isinstance(h,dict) or not valid_nav(h.get('nav')) for h in previous.get('history',[])):raise ValueError('断点基金净值无效')
                    if request['kind']!='fund':validate_market_components(previous,request,as_of)
                    if request['kind']!='fund' and previous.get('history'):market_rows('history',previous['history'])
                    dates=[h['date'] for h in previous.get('history',[])]
                    intact=dates==sorted(set(dates)) and all(dt.date.fromisoformat(day)<=dt.date.fromisoformat(as_of) and (expected_scope['start'] is None or day>=expected_scope['start']) for day in dates)
        except (ValueError,TypeError,KeyError,OverflowError):intact=False
        if intact and previous.get('collectionStatus') in ['available','cached']:
            rows.append({**previous,'resumed':True});continue
        attempts=[]
        for attempt in range(retries+1):
            try:
                if request['kind']=='fund':row=legacy(workspace,'fund',[request['code']],as_of,refresh)['rows'][0]
                else:
                    options={'financial_start':request['financialStart']} if request.get('financialStart') is not None else {}
                    row=collect_market(workspace,request['kind'],request['code'],as_of,refresh,request.get('start','2000-01-01'),request.get('market'),**options)
                if not isinstance(row,dict):raise ValueError('采集返回结构无效')
                if row.get('code',request['code'])!=request['code'] or row.get('kind',request['kind'])!=request['kind']:raise ValueError('采集返回证券身份不一致')
                if not isinstance(row.get('history',[]),list):raise ValueError('采集返回历史结构无效')
                history=row.get('history',[])
                if request['kind']=='fund' and any(not isinstance(h,dict) or not valid_nav(h.get('nav')) for h in history):raise ValueError('采集返回基金净值无效')
                if request['kind']!='fund':validate_market_components(row,request,as_of)
                if request['kind']!='fund' and history:market_rows('history',history)
                dates=[validated_day(h['date']).isoformat() for h in history]
                if dates!=sorted(set(dates)):raise ValueError('采集返回历史日期重复或乱序')
                components=row.get('components',{})
                if not isinstance(components,dict) or any(not isinstance(c,dict) for c in components.values()):raise ValueError('采集返回组件状态结构无效')
                row={**row,'code':request['code'],'kind':request['kind']}
                if request['kind']=='fund':row['history']=[h for h in history if h['date']<=as_of and ('start' not in request or request['start']<=h['date'])]
                elif any(day>as_of or day<request.get('start','2000-01-01') for day in dates):raise ValueError('采集返回历史超出请求区间')
                row_hash(row)
            except Exception as exc:row={**request,'errors':type(exc).__name__+': '+str(exc),'history':[]}
            error=row.get('errors');attempts.append({'attempt':attempt+1,'error':error,'at':dt.datetime.now(dt.timezone.utc).isoformat()})
            # Do not retry access denials, invalid requests, or vendor schema errors.
            message=str(error)
            transient=any(s in message.lower() for s in ['timeout','timed out','connection','remote end','502','503','504'])
            denied=bool(re.search(r'\b(?:400|401|403|404|422|429)\b',message)) or any(s in message.lower() for s in ['access denied','permission denied','forbidden','unauthorized'])
            if denied:transient=False
            if not refresh or not error or not transient or attempt==retries:break
            time.sleep(min(2**attempt,4))
        available=any(row.get(k) for k in ['history','quote','marketObservation','financials','announcements'])
        cached=any(c.get('status')=='cached-after-failure' for c in row.get('components',{}).values()) or row.get('cacheRetained')
        row['collectionStatus']=('cached-after-failure' if cached else 'partial' if available else 'unavailable') if row.get('errors') else ('available' if refresh else 'cached') if available else 'unavailable'
        row.update(attempts=attempts,resumed=False,sourceVerification='not-verified',requestScope=expected_scope)
        if previous and not intact:row['resumeValidation']='断点条目摘要、证券身份或请求区间未通过校验，已重新采集；摘要仅核对保存内容，不证明来源真实'
        rows.append(row);state['rows'][key]=row
        state['rowHashes'][key]=row_hash(row)
        if path:atomic(path,state)
    return {'type':'unified-research-bundle','version':2,'asOf':as_of,'refreshAttempted':refresh,'rows':rows,
        'checkpoint':str(path) if path else None,'collectionMethodFiles':methods,'coverage':{'requested':len(rows),**{s:sum(r['collectionStatus']==s for r in rows) for s in ['available','cached','partial','cached-after-failure','unavailable']}},
        'limitations':['原始价格不等于总收益','财务为第三方摘要，公告仅元数据，未核验原文','resume跳过已成功对象；部分成功对象会重新采集，旧成功组件保留']}
