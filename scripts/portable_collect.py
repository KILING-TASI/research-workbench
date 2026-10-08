"""Small stdlib collector for a fresh installation; no project universe required."""
import datetime as dt
import json
import re
import math
import hashlib
import urllib.request
from pathlib import Path
from collection_validation import day,timestamp,quote,unique_pairs,reject_constant,finite_json_float
from atomic_json import write as atomic_write

MAX_RESPONSE_BYTES=16*1024*1024

def cache_hash(record):
    content={k:v for k,v in record.items() if k!='contentSha256'}
    return hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()

def get(url, encoding='utf-8'):
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Referer':'https://fund.eastmoney.com/'})
    with urllib.request.urlopen(req, timeout=25) as response:
        payload=response.read(MAX_RESPONSE_BYTES+1)
        if len(payload)>MAX_RESPONSE_BYTES:raise ValueError('取数响应超过16MiB限制，未解析或替换缓存')
        return payload.decode(encoding)

def named(text, name):
    match = re.search(r'var\s+'+re.escape(name)+r'\s*=\s*',text)
    return json.JSONDecoder(object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float).raw_decode(text[match.end():])[0] if match else None

def collect(workspace, kind, codes, as_of, refresh):
    if kind not in ['fund','stock','etf'] or not isinstance(refresh,bool):raise ValueError('无效类型或刷新参数')
    if not isinstance(as_of,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',as_of):raise ValueError('截止日期须为YYYY-MM-DD')
    cutoff=dt.date.fromisoformat(as_of)
    if not isinstance(codes,(list,tuple)) or not codes or any(not isinstance(c,str) or not re.fullmatch(r'\d{6}',c) for c in codes) or len(codes)!=len(set(codes)):raise ValueError('代码须为不重复六位字符串列表')
    cache = Path(workspace)/'research-data'/kind
    cache.mkdir(parents=True,exist_ok=True)
    rows=[]
    for code in codes:
        path=cache/(code+'.json')
        error=None;cache_error=None;refresh_error=None
        try:
            old=json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float) if path.exists() else None
            if old is not None:
                if not isinstance(old,dict) or old.get('code')!=code or old.get('kind')!=kind or not isinstance(old.get('history'),list) or not isinstance(old.get('retrievedAt'),str):raise ValueError('缓存结构或证券身份不一致')
                timestamp(old['retrievedAt'])
                if not isinstance(old.get('identity',{}),dict) or old.get('identity',{}).get('code',code)!=code:raise ValueError('缓存名称身份不一致')
                if kind=='fund' and old.get('historyBasis','nav-with-distributions')!='nav-with-distributions':raise ValueError('缓存净值口径不一致')
                if kind=='fund' and not old['history']:raise ValueError('缓存净值为空')
                if kind!='fund':quote(old.get('quote'))
                days=[]
                for h in old['history']:
                    observed_day=h['date'];day(observed_day);days.append(observed_day)
                    if kind=='fund' and (isinstance(h.get('nav'),bool) or not isinstance(h.get('nav'),(int,float)) or not math.isfinite(h['nav']) or h['nav']<=0):raise ValueError('缓存净值无效')
                if days!=sorted(set(days)):raise ValueError('缓存日期重复或乱序')
                if old.get('contentSha256')!=cache_hash(old):raise ValueError('缓存内容摘要缺失或不一致，需重新取数；保留原文件')
        except (ValueError,OSError,KeyError,TypeError) as exc:
            old=None;cache_error='缓存不可用：'+str(exc);error=cache_error
        record=old
        if refresh:
            try:
                now=dt.datetime.now(dt.timezone.utc).isoformat()
                if kind=='fund':
                    url='https://fund.eastmoney.com/pingzhongdata/'+code+'.js'
                    text=get(url)
                    name=named(text,'fS_name'); identity=named(text,'fS_code')
                    if str(identity)!=code or not isinstance(name,str) or not name:
                        raise ValueError('基金返回代码与名称无法核实')
                    history=[]
                    for h in named(text,'Data_netWorthTrend') or []:
                        if not isinstance(h,dict) or isinstance(h.get('y'),bool) or not isinstance(h.get('y'),(int,float)) or not math.isfinite(h['y']) or h['y']<=0:raise ValueError('接口存在无效净值，不能静默删去该观测')
                        raw_time=h.get('x')
                        if isinstance(raw_time,bool) or not isinstance(raw_time,(int,float)) or not math.isfinite(raw_time) or raw_time<0:raise ValueError('净值观测时间无效')
                        observed_day=dt.datetime.fromtimestamp(raw_time/1000,dt.timezone(dt.timedelta(hours=8))).date().isoformat()
                        if day(observed_day)>dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date():raise ValueError('净值观测日期晚于当前日期')
                        history.append({'date':observed_day,'nav':h['y'],'distribution':h.get('unitMoney','')})
                    record={'code':code,'kind':kind,'identity':{'code':code,'name':name},'history':history,'historyBasis':'nav-with-distributions','source':url,'retrievedAt':now}
                else:
                    prefix='sh' if code.startswith(('5','6')) else 'bj' if code.startswith(('4','8','92')) else 'sz'
                    symbol=prefix+code;url='https://qt.gtimg.cn/q='+symbol
                    text=get(url,'gb18030');match=re.search(r'v_'+symbol+r'="([^"]*)"',text)
                    fields=match[1].split('~') if match else []
                    if len(fields)<38 or fields[2]!=code or not fields[1] or not re.fullmatch(r'\d{14}',fields[30]):
                        raise ValueError('行情返回身份或交易日期无法核实')
                    stamp=dt.datetime.strptime(fields[30],'%Y%m%d%H%M%S').replace(tzinfo=dt.timezone(dt.timedelta(hours=8)))
                    price=float(fields[3])
                    if not math.isfinite(price) or price<=0:raise ValueError('无有效行情价格')
                    record={'code':code,'kind':kind,'identity':{'code':code,'name':fields[1],'exchangePrefix':prefix},'history':[],
                            'quote':{'asOf':stamp.date().isoformat(),'quoteAt':stamp.isoformat(),'price':price},'source':url,'retrievedAt':now,
                            'classificationVerified':False}
                    quote(record['quote'])
                    # A quote validates the code/name, not whether it is an ETF or stock.
                if kind=='fund' and not record['history']:raise ValueError('净值历史为空')
                if kind=='fund':
                    days=[h['date'] for h in record['history']]
                    if days!=sorted(set(days)):raise ValueError('净值历史日期重复或乱序，保留旧缓存')
                record['contentSha256']=cache_hash(record)
                atomic_write(path,record)
                error=None
            except Exception as exc:
                record=old;refresh_error=type(exc).__name__+': '+str(exc)
                error='；重新获取失败：'.join([cache_error,refresh_error]) if cache_error else refresh_error
        if record is None:
            rows.append({'code':code,'kind':kind,'history':[],'errors':error or '无缓存，请使用 --refresh','cacheError':cache_error,'refreshError':refresh_error,'gaps':['尚无已获取数据']})
            continue
        row={**record,'history':[h for h in record.get('history',[]) if h['date']<=as_of],
             'errors':error,'cacheError':cache_error,'refreshError':refresh_error,'cacheRetained':bool(error and old),'pointInTime':'按所属日过滤，当前修订历史不等于当时冻结数据',
             'gaps':['未接入公告财务核验与完整基准'] if kind=='fund' else ['产品类别尚未经官方名录核验','行情历史、公告与财务尚未接入独立模式']}
        if row.get('quote') and row['quote']['asOf']>as_of:
            row['quote']=None;row['gaps'].append('当前报价晚于研究截止日，已排除，不能充当历史报价')
        rows.append(row)
    return {'type':'research-bundle','version':1,'asOf':as_of,'mode':'standalone','refreshAttempted':refresh,'rows':rows,
            'conclusion':'第三方数据研究档案；缺失不填补，不直接产生买卖结论'}
