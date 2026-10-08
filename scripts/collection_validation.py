"""Shared checks for portable observations; not original-source verification."""
import datetime as dt,math,re

def day(value):
 if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError('日期须为YYYY-MM-DD')
 return dt.date.fromisoformat(value)

def timestamp(value):
 if not isinstance(value,str):raise ValueError('抓取时间缺失')
 stamp=dt.datetime.fromisoformat(value)
 if stamp.tzinfo is None or stamp.utcoffset() is None:raise ValueError('时间缺少时区')
 if stamp>dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=5):raise ValueError('抓取时间晚于当前时间')
 return stamp

def positive(value):
 return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0

def quote(record):
 if not isinstance(record,dict) or not positive(record.get('price')):raise ValueError('缓存报价无效')
 observed=day(record.get('asOf'));stamp=timestamp(record.get('quoteAt'))
 if stamp.date()!=observed:raise ValueError('报价时间与所属日冲突')

def market_rows(name,rows):
 if not isinstance(rows,list) or not rows:raise ValueError('缓存资料为空或结构无效')
 if name not in ['history','financials','announcements']:raise ValueError('未知资料组件')
 if name!='history':
  if any(not isinstance(r,dict) for r in rows):raise ValueError('缓存资料行结构无效')
  if name=='announcements':
   ids=[]
   for row in rows:
    day(row.get('date'));ident=row.get('id')
    if not isinstance(ident,str) or not ident.strip():raise ValueError('公告标识缺失')
    ids.append(ident)
   if len(ids)!=len(set(ids)):raise ValueError('公告标识重复')
  if name=='financials':
   seen=set()
   for row in rows:
    period=day(row.get('period'));published=day(row.get('publishedAt'))
    if published<period:raise ValueError('财务披露日早于报告期')
    key=(period,published)
    if key in seen:raise ValueError('同报告期与披露日的财务记录重复')
    seen.add(key)
    if 'raw' in row and not isinstance(row['raw'],dict):raise ValueError('财务原始字段须为对象')
  return
 dates=[]
 for row in rows:
  if not isinstance(row,dict):raise ValueError('缓存行情行结构无效')
  dates.append(day(row.get('date')).isoformat())
  values=[row.get(k) for k in ['open','close','high','low']]
  if not all(positive(v) for v in values):raise ValueError('缓存行情价格无效')
  op,close,high,low=values
  if high<max(op,close,low) or low>min(op,close,high):raise ValueError('缓存行情高低价不一致')
  for field in ['volume','amount']:
   value=row.get(field)
   if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0):raise ValueError('行情成交量或金额无效')
 if dates!=sorted(set(dates)):raise ValueError('缓存行情日期重复或乱序')

def urls(values):
 from urllib.parse import urlsplit
 if not isinstance(values,list) or not values:raise ValueError('资料来源链接缺失')
 for value in values:
  if not isinstance(value,str) or re.search(r'[\s\x00-\x1f\x7f]',value):raise ValueError('资料来源格式无效')
  try:
   u=urlsplit(value);u.port
  except ValueError as exc:raise ValueError('资料来源格式无效') from exc
  if u.scheme!='https' or not u.hostname or u.username is not None or u.password is not None:raise ValueError('资料来源须无凭据HTTPS链接')


def unique_pairs(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('JSON出现重复字段：'+key)
  result[key]=value
 return result

def reject_constant(value):raise ValueError('JSON包含非有限数值：'+value)

def finite_json_float(token):
 value=float(token)
 if not math.isfinite(value):raise ValueError('JSON浮点数超出有限范围：'+token)
 return value


def report_contract(bundle):
 if not isinstance(bundle,dict):raise ValueError('取数结果须为对象')
 cutoff=bundle.get('asOf')
 if cutoff is not None:day(cutoff)
 rows=bundle.get('rows')
 if not isinstance(rows,list) or not rows:raise ValueError('无可整理的取数结果')
 kinds={'fund','stock','etf','bond','convertible','government-bond','credit-bond'}
 statuses={'available','partial','unavailable','cached','cached-after-failure'}
 component_statuses={'success','cached','cached-after-failure','failed','unsupported'}
 for row in rows:
  if not isinstance(row,dict):raise ValueError('资料条目须为对象')
  if not isinstance(row.get('kind'),str) or row.get('kind') not in kinds:raise ValueError('资料类型缺失或不支持')
  if row.get('collectionStatus') is not None and (not isinstance(row['collectionStatus'],str) or row['collectionStatus'] not in statuses):raise ValueError('取数状态无效')
  ident=row.get('identity')
  if ident is not None and not isinstance(ident,dict):raise ValueError('身份须为对象')
  if ident and 'name' in ident and ident['name'] is not None and not isinstance(ident['name'],str):raise ValueError('名称须为文字')
  errors=row.get('errors')
  if errors is not None and not isinstance(errors,(str,dict)):raise ValueError('错误说明须为文字或对象')
  if isinstance(errors,dict) and any(not isinstance(k,str) or (v is not None and not isinstance(v,str)) for k,v in errors.items()):raise ValueError('错误字段须为文字')
  gaps=row.get('gaps',[])
  if not isinstance(gaps,list) or any(not isinstance(g,str) for g in gaps):raise ValueError('缺口清单须为文字数组')
  for flag in ['cacheRetained','resumed']:
   if flag in row and not isinstance(row[flag],bool):raise ValueError(flag+'须为布尔值')
  scope=row.get('requestScope')
  if scope is not None:
   if not isinstance(scope,dict):raise ValueError('请求区间须为对象')
   requested_end=day(scope.get('asOf'))
   if cutoff and scope['asOf']!=cutoff:raise ValueError('请求区间与报告截止日不一致')
   for key in ['start','financialStart']:
    if scope.get(key) is not None and day(scope[key])>requested_end:raise ValueError('请求起始日晚于截止日')
  if row.get('source') is not None:urls([row['source']])
  if row.get('retrievedAt') is not None:timestamp(row['retrievedAt'])
  for name in ['history','financials','announcements']:
   if not isinstance(row.get(name,[]),list):raise ValueError(name+'须为数组')
  components=row.get('components',{})
  if not isinstance(components,dict):raise ValueError('组件须为对象')
  for name,c in components.items():
   if name not in ['history','financials','announcements']:raise ValueError('未知报告组件')
   if not isinstance(c,dict):raise ValueError('组件须为对象')
   if not isinstance(c.get('status'),str) or c.get('status') not in component_statuses:raise ValueError('组件状态无效')
   sources=c.get('sources',[])
   if not isinstance(sources,list):raise ValueError('组件来源须为数组')
   if sources:urls(sources)
   if c.get('retrievedAt') is not None:timestamp(c['retrievedAt'])
   if c.get('error') is not None and not isinstance(c['error'],str):raise ValueError('组件错误须为文字')
   if c.get('reason') is not None and not isinstance(c['reason'],str):raise ValueError('组件原因须为文字')
   if 'count' in c and (type(c['count'])!=int or c['count']<0 or c['count']!=len(row.get(name,[]))):raise ValueError('组件记录数与资料不一致')
   if c['status'] in ['failed','unsupported'] and row.get(name):raise ValueError('失败或不支持的组件不能声明已有资料')
  for name in ['financials','announcements']:
   values=row.get(name,[])
   if not isinstance(values,list):raise ValueError(name+'须为数组')
   if values:
    market_rows(name,values)
    for v in values:
     if name=='financials' and isinstance(scope,dict) and scope.get('financialStart') is not None and v['period']<scope['financialStart']:raise ValueError('财务报告期早于请求起始日')
     if cutoff and (v.get('date',v.get('period'))>cutoff or (name=='financials' and v['publishedAt']>cutoff)):raise ValueError('资料晚于研究截止日')
     raw=v.get('raw',{})
     if name=='financials' and raw.get('SECURITY_CODE',row.get('code'))!=row.get('code'):raise ValueError('财务身份冲突')
     if name=='announcements' and v.get('title') is not None and not isinstance(v['title'],str):raise ValueError('公告标题须为文字')
  if row.get('collectionStatus')=='unavailable' and any(row.get(k) for k in ['history','quote','financials','announcements','marketObservation']):raise ValueError('不可用状态与已有资料冲突')
