"""Dated event timeline; title candidates never become verified fundamentals."""
import calendar
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from market_collect import announcements, atomic
from collection_validation import unique_pairs,reject_constant,finite_json_float

def iso_day(value):
    if not isinstance(value,str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",value):raise ValueError("日期须为YYYY-MM-DD")
    return dt.date.fromisoformat(value)

RULES={
 '业绩':r'业绩|年度报告|季度报告|半年度报告|盈利|亏损',
 '减持':r'减持','回购':r'回购','诉讼仲裁':r'诉讼|仲裁',
 '监管':r'问询|监管|处罚|立案|警示|纪律处分',
 '订单合同':r'订单|中标|重大合同|采购合同',
 '融资定增':r'定增|向特定对象|发行股票|融资|借款|债券发行',
 '分红':r'分红|权益分派|利润分配','并购重组':r'重组|收购|合并|出售资产',
 '担保债务':r'担保|逾期|违约|偿债|兑付','退市风险':r'退市|风险警示',
 '治理人事':r'辞职|聘任|董事|高管|实际控制人'}
PATHS={'业绩':'收入、盈利与现金流假设','减持':'股东行为、供给与治理；不能直接推导股价',
 '回购':'资金用途、实施进度与资本分配','诉讼仲裁':'或有负债、经营连续性与回款',
 '监管':'合规成本、整改与披露可靠性','订单合同':'收入确认、履约、毛利与客户集中度',
 '融资定增':'融资成本、资金用途与股本稀释','分红':'现金分配与除息；不凭空增加资产',
 '并购重组':'交易条件、整合、商誉与审批','担保债务':'流动性、偿债及或有负债',
 '退市风险':'持续经营与交易制度','治理人事':'治理结构与管理连续性'}

def start_date(end,months):
    n=end.year*12+end.month-1-months;y,m=divmod(n,12);m+=1
    return dt.date(y,m,min(end.day,calendar.monthrange(y,m)[1]))

def identity(spec):
    market=spec.get('market','CN');code=spec.get('code')
    patterns={'CN':r'[0-9]{6}','HK':r'[0-9]{5}','US':r'[A-Z][A-Z0-9.\-]{0,14}'}
    if market not in patterns or not isinstance(code,str) or not re.fullmatch(patterns[market],code):raise ValueError('须明确CN六位、HK五位或US大写代码')
    end=iso_day(spec['asOf']);months=spec.get('months',1)
    if type(months)!=int or months not in [1,3]:raise ValueError('months仅支持1或3个日历月')
    if type(spec.get('refresh',False)) is not bool:raise ValueError('refresh须为布尔值')
    return market,code,start_date(end,months).isoformat(),end.isoformat()

def analyze(item,market,code):
    if not isinstance(item,dict):raise ValueError('事件须为对象')
    if ('code' in item and item['code']!=code) or ('market' in item and item['market']!=market):raise ValueError('事件声明的标的身份与研究对象不一致')
    title=item.get('title');text=item.get('text','')
    if not isinstance(title,str) or not title.strip() or not isinstance(text,str):raise ValueError('事件须提供标题；正文须为字符串')
    day=item.get('publishedAt') or item.get('date');iso_day(day)
    combined=title+'\n'+text;types=[k for k,v in RULES.items() if re.search(v,combined)] or ['其他']
    modification=bool(re.search(r'更正|修订|补充|更新',title))
    stage='待核查'
    if re.search(r'完成|实施完毕|已支付',title):stage='标题称已完成，待原文核对'
    elif re.search(r'预案|计划|拟|意向',title):stage='拟议或计划'
    elif re.search(r'进展|回复',title):stage='进展或回复'
    priority='需核查' if any(t in types for t in ['监管','退市风险','担保债务','诉讼仲裁','并购重组','业绩']) else '持续跟踪'
    # Extract mentions, never assign an ambiguous amount to financial impact.
    amounts=[{'text':m.group(0),'context':combined[max(0,m.start()-30):m.end()+30],'role':'金额提及，归属与净影响待核对'} for m in re.finditer(r'(?<![\d.])\d+(?:\.\d+)?\s*(?:亿|万)?\s*(?:元|美元|港元)',text)]
    dates=list(dict.fromkeys(re.findall(r'\d{4}年\d{1,2}月\d{1,2}日|\d{4}-\d{2}-\d{2}',text)))
    if item.get('eventDate') is not None:iso_day(item['eventDate'])
    subjects=item.get('relatedSubjects',[])
    if not isinstance(subjects,list) or any(not isinstance(x,str) for x in subjects):raise ValueError('relatedSubjects须为字符串列表')
    return {'id':str(item.get('id') or hashlib.sha256((market+code+day+combined).encode()).hexdigest()),
        'market':market,'code':code,'publishedAt':day,'title':title,'eventTypes':types,
        'eventDate':item.get('eventDate'),'eventDateVerification':'输入声明，待原文核验', 'dateMentions':dates,'amountMentions':amounts,
        'impactAmount':None,'validity':item.get('validity'), 'relatedSubjects':subjects,
        'subjectVerification':'输入声明，未证明子公司或同一控制关系',
        'relationshipMentions':[{'text':m.group(0),'verification':'正文提及，主体身份与控制关系待核对'} for m in re.finditer(r'(?:全资子公司|控股子公司|关联方|实际控制人)[^，。；\n]{0,50}',text)],
        'stage':stage,'isRevision':modification,'priority':priority,
        'fundamentalImpact':'待核查','priceDirection':None,
        'impactPaths':[PATHS[t] for t in types if t in PATHS],
        'sourceUrl':item.get('url') or item.get('sourceUrl'),
        'sourceType':item.get('sourceType','announcement-metadata'),
        'originalVerification':'not-verified','textAvailable':bool(text),
        'explicitRelatedIds':item.get('relatedIds',[]),
        'gaps':['标题分类不是原文核验；金额提及不等于损益','利好/利空须指定基本面指标与证据，不自动等同价格方向']}

def run(spec,workspace,loader=announcements):
    market,code,start,end=identity(spec);cache=Path(workspace)/'research-data'/'events'/market/code/f'{start}-{end}.json'
    old=json.loads(cache.read_text(encoding='utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float) if cache.exists() else None
    record=old;failure=None;provided=spec.get('items')
    if provided is not None:
        if not isinstance(provided,list) or len(provided)>10000:raise ValueError('items须为列表且最多10000条')
        record={'rows':provided,'sources':[],'retrievedAt':None};status='user-supplied'
    elif spec.get('refresh',False) and market=='CN':
        try:
            rows,urls=loader(code,start,end)
            if not rows:raise ValueError('空响应无法证明无事件')
            # Validate before committing cache.
            for row in rows:analyze(row,market,code)
            record={'rows':rows,'sources':urls,'retrievedAt':dt.datetime.now(dt.timezone.utc).isoformat()}
            atomic(cache,record);status='fetched'
        except Exception as exc:
            failure=type(exc).__name__+': '+str(exc);status='cached-after-failure' if old else 'unavailable'
    else:status='cached' if old else 'unsupported' if market!='CN' else 'unavailable'
    timeline=[];excluded=[];seen={}
    for raw in record['rows'] if record else []:
        row=analyze(raw,market,code)
        if not start<=row['publishedAt']<=end:
            excluded.append({'id':row['id'],'reason':'发布日期超出研究窗口'});continue
        key=row['id'];signature=hashlib.sha256(json.dumps(row,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        if key in seen:
            if seen[key]!=signature:raise ValueError('同一事件ID内容冲突，不能静默去重')
            continue
        seen[key]=signature;timeline.append(row)
    timeline.sort(key=lambda r:(r['publishedAt'],r['id']))
    ids={r['id'] for r in timeline};links=[]
    for row in timeline:
        refs=row['explicitRelatedIds']
        if not isinstance(refs,list) or any(not isinstance(x,str) for x in refs):raise ValueError('relatedIds须为字符串列表')
        for ref in refs:links.append({'from':row['id'],'to':ref,'status':'input-declared' if ref in ids else 'target-missing'})
    today=[r for r in timeline if r['publishedAt']==end]
    return {'type':'research-event-timeline','market':market,'code':code,'start':start,'asOf':end,
        'riskNotice':'仅为事件事实与研究线索，不构成投资建议；事件标签不代表价格方向',
        'collectionStatus':status,'error':failure,'retrievedAt':record.get('retrievedAt') if record else None,
        'sources':record.get('sources',[]) if record else [],'timeline':timeline,'excluded':excluded,'links':links,
        'brief':{'date':end,'count':len(today),'events':[{'id':r['id'],'title':r['title'],'priority':r['priority'],'impactPaths':r['impactPaths']} for r in today],
                 'coverage':'仅本次取得且当天发布的事件；不是全市场今日新闻'},
        'limitations':['仅A股公告元数据自动采集；港美股及新闻须提供items','事件发生日与有效期缺失保留null','未进行原文、主体关系或历史冲击核验','无常驻调度与消息提醒；不输出交易指令或涨跌预测']}

def monitor(spec):
    result=spec['result'];rules=spec.get('rules',{});previous=spec.get('seen',{})
    if result.get('type')!='research-event-timeline' or not isinstance(previous,dict):raise ValueError('监控输入无效')
    keywords=rules.get('keywords',[]);types=rules.get('eventTypes',[])
    if any(not isinstance(x,str) or not x for x in keywords+types):raise ValueError('筛选词须为非空字符串')
    if any(x not in RULES and x!='其他' for x in types):raise ValueError('事件类型无效')
    alerts=[];current=dict(previous)
    for row in result['timeline']:
        key=f"{row['market']}:{row['code']}:{row['id']}"
        digest=hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        matched=(not keywords or any(x in row['title'] for x in keywords)) and (not types or any(x in row['eventTypes'] for x in types))
        if matched and previous.get(key)!=digest:alerts.append({'id':row['id'],'reason':'new' if key not in previous else 'changed','event':row})
        current[key]=digest
    return {'type':'research-event-monitor-evaluation','alerts':alerts,'seen':current,
        'collectionStatus':result['collectionStatus'],'error':result.get('error'),
        'limitations':'本地差异与关键词筛选，不创建调度、不发送消息；行业关联需另有已核验映射'}
