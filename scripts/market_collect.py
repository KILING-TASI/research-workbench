"""Portable dated market datasets. Third-party observations are never original verification."""
import hashlib
import datetime as dt
import json
import math
import re
from pathlib import Path
from urllib.parse import urlencode
from portable_collect import get
from atomic_json import write as atomic_write
from collection_validation import day as validated_day
from collection_validation import market_rows,timestamp,day,urls as validate_urls,unique_pairs,reject_constant,finite_json_float

KINDS = ['stock','etf','bond','convertible','government-bond','credit-bond']

def cache_hash(record):
    content={key:value for key,value in record.items() if key!='contentSha256'}
    return hashlib.sha256(json.dumps(content,ensure_ascii=False,sort_keys=True,allow_nan=False).encode('utf-8')).hexdigest()

def atomic(path, value):
    atomic_write(path,value)

def fetch(url):
    return json.loads(get(url),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def eastmoney_history(code, market, start, end, identity=None):
    rows=[]; sources=[]; year=int(start[:4]); names=set()
    while year <= int(end[:4]):
        begin=max(start, f'{year}-01-01'); finish=min(end,f'{year}-12-31')
        url='https://push2his.eastmoney.com/api/qt/stock/kline/get?'+urlencode(dict(
            secid=f'{market}.{code}',klt=101,fqt=0,beg=begin.replace('-',''),end=finish.replace('-',''),
            fields1='f1,f2,f3,f4,f5,f6',fields2='f51,f52,f53,f54,f55,f56,f57',lmt=1000))
        payload=fetch(url); data=payload.get('data')
        if not isinstance(data,dict) or data.get('code')!=code:
            raise ValueError('历史行情身份缺失或接口不支持该市场')
        if 'market' in data and (isinstance(data['market'],bool) or not isinstance(data['market'],(int,str)) or str(data['market'])!=str(market)):raise ValueError('历史行情市场标识不一致')
        name=data.get('name')
        if name is not None:
            if not isinstance(name,str) or not name.strip():raise ValueError('历史证券名称无效')
            names.add(name.strip())
            if len(names)>1:raise ValueError('跨窗口证券名称冲突，需确认更名或身份')
        sources.append(url)
        lines=data.get('klines') or []
        if len(lines)>=1000:raise ValueError('历史窗口可能截断')
        for line in lines:
            parts=line.split(','); day=validated_day(parts[0]).isoformat()
            values=[float(v) for v in parts[1:7]]
            if len(values)!=6 or not all(math.isfinite(v) for v in values) or min(values[:4])<=0:
                raise ValueError('历史行情存在非法数值')
            op,close,high,low,volume,amount=values
            if high<max(op,close,low) or low>min(op,close,high) or volume<0 or amount<0:raise ValueError('历史行情高低价或成交量金额不一致')
            if not begin<=day<=finish:raise ValueError('历史行情越界')
            rows.append(dict(zip(['date','open','close','high','low','volume','amount'],[day]+values)))
        year+=1
    if not rows:raise ValueError('指定区间无历史数据；未判定为无交易')
    if [r['date'] for r in rows]!=sorted(set(r['date'] for r in rows)):raise ValueError('历史日期重复或乱序')
    if identity is not None and names:identity.update(code=code,name=next(iter(names)),verification="third-party-code-matched")
    return rows,sources

def history(code,market,start,end,identity=None):
    try:return eastmoney_history(code,market,start,end,identity)
    except Exception as primary:
        primary_error=type(primary).__name__+': '+str(primary)
    symbol=('sh' if market=='1' else 'sz')+code
    rows=[];sources=[];names=set()
    for year in range(int(start[:4]),int(end[:4])+1):
        begin=max(start,f'{year}-01-01');finish=min(end,f'{year}-12-31')
        url='https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?'+urlencode({'param':f'{symbol},day,{begin},{finish},640,'})
        payload=fetch(url);data=(payload.get('data') or {}).get(symbol)
        if payload.get('code')!=0 or not isinstance(data,dict):raise ValueError('备用历史源无有效结果；主源失败：'+primary_error)
        quote=data.get('qt',{}).get(symbol,[])
        if len(quote)<3 or quote[2]!=code or not quote[1]:raise ValueError('备用历史证券身份未确认')
        if not isinstance(quote[1],str) or not quote[1].strip():raise ValueError('备用历史名称无效')
        names.add(quote[1].strip())
        if len(names)>1:raise ValueError('跨窗口证券名称冲突，需确认更名或身份')
        lines=data.get('day')
        if not isinstance(lines,list) or len(lines)>=640:raise ValueError('备用源无未复权历史或窗口截断')
        sources.append(url)
        for parts in lines:
            day=validated_day(parts[0]).isoformat();v=[float(x) for x in parts[1:6]]
            if len(v)!=5 or not all(math.isfinite(x) for x in v) or min(v[:4])<=0:raise ValueError('备用历史非法数值')
            op,close,high,low,volume=v
            if high<max(op,close,low) or low>min(op,close,high) or volume<0:raise ValueError('备用历史高低价或成交量不一致')
            if not begin<=day<=finish:raise ValueError('备用历史日期越界')
            rows.append(dict(zip(['date','open','close','high','low','volume'],[day]+v),amount=None,volumeUnit='provider-unit-unverified'))
    if not rows:raise ValueError('备用历史为空；主源失败：'+primary_error)
    if [r['date'] for r in rows]!=sorted(set(r['date'] for r in rows)):raise ValueError('备用历史日期重复或乱序')
    if identity is not None:identity.update(code=code,name=next(iter(names)),verification="third-party-code-matched")
    return rows,sources

def financials(code,start,end):
    rows=[];sources=[];expected_pages=None
    for page in range(1,101):
        url='https://datacenter.eastmoney.com/api/data/v1/get?'+urlencode(dict(
            reportName='RPT_F10_FINANCE_MAINFINADATA',columns='ALL',
            filter=f'(SECURITY_CODE="{code}")',pageSize=100,pageNumber=page,sortColumns='REPORT_DATE',sortTypes='-1'))
        result=fetch(url).get('result')
        if not isinstance(result,dict) or not isinstance(result.get('data'),list):raise ValueError('财务接口无有效结果')
        pages=result.get('pages')
        if type(pages)!=int or not 1<=pages<=100:raise ValueError('财务分页数量缺失或无效，不能确认完整性')
        if expected_pages is not None and pages!=expected_pages:raise ValueError('财务分页总数变化，需重新取得一致快照')
        expected_pages=pages
        if len(result['data'])>100:raise ValueError('财务分页条目超出请求范围')
        sources.append(url)
        for item in result['data']:
            if item.get('SECURITY_CODE')!=code:raise ValueError('财务证券身份不一致')
            period=str(item.get('REPORT_DATE',''))[:10]; published=str(item.get('NOTICE_DATE',''))[:10]
            period_day=validated_day(period); published_day=validated_day(published)
            if published_day<period_day:raise ValueError('财务披露日期早于报告期末，需核对原文')
            if start<=period<=end and published<=end:
                rows.append({'period':period,'publishedAt':published,'raw':item})
        if page>=expected_pages:break
    else:raise ValueError('财务分页超过上限，拒绝将截断结果标为完整')
    if not rows:raise ValueError('无满足发布时点的财务数据')
    return rows,sources

def announcements(code,start,end):
    rows=[];sources=[];seen=set()
    for page in range(1,101):
        url='https://np-anotice-stock.eastmoney.com/api/security/ann?'+urlencode(dict(
            sr=-1,page_size=100,page_index=page,ann_type='A',stock_list=code,begin_time=start,end_time=end))
        result=fetch(url).get('data')
        if not isinstance(result,dict) or not isinstance(result.get('list'),list):raise ValueError('公告接口无有效结果')
        sources.append(url)
        for item in result['list']:
            if not any(str(c.get('stock_code'))==code for c in item.get('codes',[])):raise ValueError('公告证券身份不一致')
            day=str(item.get('notice_date',''))[:10];dt.date.fromisoformat(day)
            ident=item.get('art_code')
            if not ident or ident in seen:raise ValueError('公告分页重复或缺少标识')
            seen.add(ident)
            if start<=day<=end:rows.append({'id':ident,'date':day,'title':item.get('title'),
                'url':item.get('attach_url') or None,'raw':item,'originalVerified':False})
        if page*100>=int(result.get('total_hits',len(result['list']))):break
    else:raise ValueError('公告分页超过上限，结果未提交')
    if not rows:raise ValueError('公告接口返回空；无法区分无公告与该品种未覆盖，须另查官方来源')
    return rows,sources

def fund_announcements(code,start,end):
    """Fund catalog metadata only; no guessed attachments or effective-version claims."""
    rows=[];sources=[];seen=set();last_page_date=None
    for page in range(1,101):
        url='https://api.fund.eastmoney.com/f10/JJGG?'+urlencode(dict(fundcode=code,pageIndex=page,pageSize=100,type=0))
        payload=fetch(url);items=payload.get('Data')
        if not isinstance(items,list) or len(items)>100:raise ValueError('基金公告目录结构异常')
        sources.append(url)
        dates=[]
        for item in items:
            if not isinstance(item,dict) or str(item.get('FUNDCODE'))!=code:raise ValueError('基金公告目录代码不一致')
            published=str(item.get('PUBLISHDATE',''))[:10];day(published);dates.append(published)
            ident=item.get('ID');title=item.get('TITLE')
            if not isinstance(ident,str) or not ident.strip() or ident in seen:raise ValueError('基金公告标识缺失或分页重复')
            if not isinstance(title,str) or not title.strip():raise ValueError('基金公告标题缺失')
            seen.add(ident)
            if start<=published<=end:rows.append({'id':ident,'date':published,'title':title,'url':None,'raw':item,'originalVerified':False,'provenance':'third-party-fund-catalog'})
        if dates!=sorted(dates,reverse=True) or dates and last_page_date is not None and dates[0]>last_page_date:raise ValueError('基金公告日期顺序异常，不据此提前停止')
        if dates:last_page_date=dates[-1]
        if len(items)<100:break
        if dates and dates[-1]<start:break
    else:raise ValueError('基金公告分页超过上限，拒绝提交截断目录')
    if not rows:raise ValueError('基金公告目录区间内为空，覆盖未确认，不等于没有公告')
    return rows,sources

def collect_market(workspace,kind,code,as_of,refresh,start='2000-01-01',market=None,financial_start=None):
    if kind not in KINDS:raise ValueError('不支持的类型')
    if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code):raise ValueError('代码须为六位字符串')
    if not isinstance(refresh,bool):raise ValueError('refresh须为布尔值')
    if day(start)>day(as_of):raise ValueError('起始日期晚于截止日')
    if financial_start is not None and kind!='stock':raise ValueError('财务起始日仅用于股票')
    if financial_start is not None and day(financial_start)>day(as_of):raise ValueError('财务起始日晚于截止日')
    if isinstance(market,bool):raise ValueError('market不能为布尔值')
    if market is None:
        if kind not in ['stock','etf']:raise ValueError('债券须明确market=0深市或1沪市；银行间代码尚不支持')
        market='1' if code.startswith(('5','6')) else '0'
        if code.startswith(('4','8','92')):raise ValueError('北交所历史市场映射尚未核验')
    market=str(market)
    if market not in ['0','1']:raise ValueError('目前仅支持明确的沪深市场编号')
    row={'code':code,'kind':kind,'historyBasis':'unadjusted-price-not-total-return','components':{},'gaps':[],
         'pointInTime':'按日期和公告发布日过滤；当前修订数据不是历史冻结快照','sourceVerification':'not-verified'}
    announcement_loader=fund_announcements if kind=='etf' else announcements
    for name,loader in [('history',history),('financials',financials),('announcements',announcement_loader)]:
        if name=='financials' and kind!='stock':
            row[name]=[];row['components'][name]={'status':'unsupported','reason':'基金财报或债券发行人映射尚未接入此链路'};continue
        component_start=financial_start if name=='financials' and financial_start is not None else start
        binding={'code':code,'kind':kind,'market':market,'component':name,'start':component_start,'asOf':as_of}
        if name=='announcements':binding['catalogSource']='fund-catalog' if kind=='etf' else 'stock-announcements'
        def validate_values(values):
            market_rows(name,values)
            if name=='history' and any(not component_start<=r['date']<=as_of for r in values):raise ValueError('缓存行情超出请求区间')
            if name=='announcements' and any(not component_start<=r['date']<=as_of for r in values):raise ValueError('公告超出请求区间')
            if name=='financials':
                if any(not component_start<=r['period']<=as_of or r['publishedAt']>as_of for r in values):raise ValueError('财务资料超出研究时点')
                if any(r.get('raw',{}).get('SECURITY_CODE',code)!=code for r in values):raise ValueError('财务证券身份不一致')
        path=Path(workspace)/'research-data'/kind/(code+'-'+market)/f'{name}-{component_start}-{as_of}.json'
        old=None;error=None;cache_error=None;refresh_error=None
        try:
            old=json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float) if path.exists() else None
            if old is not None and (not isinstance(old,dict) or not isinstance(old.get('rows'),list) or not isinstance(old.get('sources'),list) or not isinstance(old.get('retrievedAt'),str)):
                raise ValueError('缓存结构无效，需重新取数')
            if old is not None:
                timestamp(old['retrievedAt']);validate_values(old['rows']);validate_urls(old['sources'])
                if old.get('request',binding)!=binding:raise ValueError('缓存请求身份或窗口不一致')
                if old.get('identity') is not None:
                    ident=old['identity']
                    if not isinstance(ident,dict) or ident.get('code')!=code or not isinstance(ident.get('name'),str) or not ident['name'].strip():raise ValueError('缓存证券名称身份无效')
                if old.get('contentSha256')!=cache_hash(old):raise ValueError('缓存内容摘要缺失或不一致，需重新取数；保留原文件')
        except (ValueError,OSError,TypeError,AttributeError) as exc:
            old=None;cache_error='缓存不可用：'+str(exc);error=cache_error
        record=old
        if refresh:
            try:
                observed_identity={}
                values,source_urls=loader(code,market,component_start,as_of,observed_identity) if name=='history' else loader(code,component_start,as_of)
                validate_values(values);validate_urls(source_urls)
                candidate={'rows':values,'sources':source_urls,'retrievedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'request':binding}
                if observed_identity:candidate['identity']=observed_identity
                candidate['contentSha256']=cache_hash(candidate)
                atomic(path,candidate);record=candidate
                error=None
            except Exception as exc:
                record=old;refresh_error=type(exc).__name__+': '+str(exc)
                error='；重新获取失败：'.join([cache_error,refresh_error]) if cache_error else refresh_error
        row[name]=record['rows'] if record else []
        if name=='history' and record and record.get('identity'):row['identity']=record['identity']
        row['components'][name]={'status':('cached-after-failure' if error else 'cached' if not refresh else 'success') if record else 'failed',
            'error':error or (None if record else '无缓存，请刷新'),'retrievedAt':record.get('retrievedAt') if record else None,
            'cacheError':cache_error,'refreshError':refresh_error,
            'sources':record.get('sources',[]) if record else [],'count':len(row[name]),'request':binding}
    row['errors']={k:v.get('error') for k,v in row['components'].items() if v.get('error')}
    row['gaps']=[k+': '+str(v.get('reason') or v.get('error')) for k,v in row['components'].items() if v['status'] in ['failed','unsupported','cached-after-failure']]
    row['gaps'].append('历史为未复权价格，不含分红票息；区间覆盖不证明上市以来完整，公告元数据不等于原文核验')
    return row
