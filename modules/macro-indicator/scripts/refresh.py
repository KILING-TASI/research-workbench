"""Refresh verified official cycle observations; never invent publication dates."""
import json,datetime as dt,math,re,copy,os,tempfile
from urllib.parse import urlparse
from pathlib import Path
from official_cycles import fetch_all
ROOT=Path(__file__).resolve().parents[1]
def validate_observations(items,frequency,today):
 if not isinstance(items,list) or not items:raise ValueError('本次观测列表为空')
 seen=set();result=[]
 for item in items:
  if not isinstance(item,dict):raise ValueError('观测须为对象')
  period=item.get('period');value=item.get('value')
  patterns={'月':r'\d{4}-(?:0[1-9]|1[0-2])','季':r'\d{4}-Q[1-4]','年':r'\d{4}'}
  if not isinstance(period,str) or not re.fullmatch(patterns.get(frequency,r'\d{4}(?:-(?:0[1-9]|1[0-2])|-Q[1-4])?'),period) or period in seen:raise ValueError('所属期无效、频率不符或重复')
  seen.add(period)
  period_start=dt.date(int(period[:4]),(int(period[-1])*3-2) if '-Q' in period else int(period[5:7]) if len(period)==7 else 1,1)
  if period_start>today:raise ValueError('观测所属期晚于当前日期')
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('观测数值无效')
  yoy=item.get('yoy')
  if yoy is not None and (isinstance(yoy,bool) or not isinstance(yoy,(int,float)) or not math.isfinite(yoy)):raise ValueError('同比数值无效')
  source=urlparse(item.get('sourceUrl') or '')
  if source.scheme!='https' or source.hostname!='www.stats.gov.cn' or source.username or source.password:raise ValueError('官方来源链接不匹配')
  for field in ['official_release_date','observed_release_date']:
   if item.get(field) is not None:
    released=dt.date.fromisoformat(item[field])
    if released>today or released<period_start:raise ValueError('公告日期与观测所属期或当前日期冲突')
  result.append(copy.deepcopy(item))
 return result

def save_json(path,value):
 path=Path(path);text=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)
 fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
 try:
  with os.fdopen(fd,'w',encoding='utf-8') as handle:handle.write(text);handle.flush();os.fsync(handle.fileno())
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)

def refresh(dest=None):
 target=Path(dest) if dest is not None else ROOT/'assets'
 d=json.loads((target/'data.json').read_text(encoding='utf-8'))
 now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(timespec='seconds')
 try: observations,errors,urls=fetch_all()
 except Exception as e:observations,errors,urls={}, {'discovery':str(e)},{}
 accepted=set();latest_fresh=set()
 for row in d['indicators']:
  id=row['id'];row['refreshStatus']='not-updated';row['modelEligible']=False
  if id not in observations:continue
  try:
   incoming=validate_observations(observations[id],row.get('frequency'),dt.datetime.fromisoformat(now).date())
   merged={h['period']:copy.deepcopy(h) for h in row.get('history',[])}
   for h in incoming:
    h['fetched_at']=now;old=merged.get(h['period'],{})
    if h.get('official_release_date') is None and old.get('official_release_date') and h['value']==old.get('value') and h.get('yoy')==old.get('yoy'):
     h['official_release_date']=old['official_release_date'];h['releaseDateBasis']='retained-prior-unchanged-value';h['priorReleaseSourceUrl']=old.get('sourceUrl')
    merged[h['period']]=h
   history=sorted(merged.values(),key=lambda h:h['period']);last=history[-1]
   latest_received=last['period'] in {h['period'] for h in incoming}
   latest_time=last.get('fetched_at') or row.get('fetched_at')
   row.update(history=history,value=last['value'],previous=history[-2]['value'] if len(history)>1 else None,data_period=last['period'],official_release_date=last.get('official_release_date'),fetched_at=latest_time,sourceUrl=last['sourceUrl'],missing=None,source_status='官方公告观测已取得，数值与口径仍需核对',last_successful_fetch_at=now,fetch_error=None,yoy=last.get('yoy'),modelEligible=False,refreshStatus='updated' if latest_received else 'history-only-updated')
   if latest_received:latest_fresh.add(id)
   row['history_status']='已取'+str(len(history))+'期，长期历史覆盖仍需补全';accepted.add(id)
  except Exception as exc:
   row['fetch_error']='观测校验未通过：'+str(exc);row['refreshStatus']='retained-after-failure';errors['indicator:'+id]=row['fetch_error']
 # Failures retain existing observations and are visible in the affected rows.
 affected={'pmi':['pmi_new_orders','pmi_raw_inventory','pmi_finished_inventory','pmi_purchase_quantity','pmi_backlog_orders'],'profit':['industrial_revenue','industrial_profit','industrial_profit_margin','inventory_days','finished_inventory'],'industrial':['industrial_output'],'investment':['equipment_investment','manufacturing_investment','infrastructure_investment'],'housing':['real_estate_investment','housing_starts','housing_completions','housing_sales_area','housing_for_sale'],'ppi':['producer_prices'],'capacity':['capacity_utilization'],'annual':['urbanization','labor_productivity','research_intensity','hightech_value_share']}
 for kind,error in errors.items():
  for row in d['indicators']:
   if kind=='discovery' or row['id'] in affected.get(kind,[]):row['fetch_error']=error;row['refreshStatus']='retained-after-failure'
 d.update(fetchedAt=now,errors=errors,sourceDiscovery=urls)
 rows=d['indicators'];d['fetchHealth']=dict(total=len(rows),available=sum(r['value'] is not None for r in rows),fresh=len(latest_fresh),historyOnly=len(accepted-latest_fresh),accepted=len(accepted),missing=sum(bool(r.get('missing')) for r in rows),failed=sum(bool(r.get('fetch_error')) for r in rows))
 d['status']='部分官方公告观测已取得；缺项与长期历史不足，周期阶段未确认'
 d['maintenanceWarnings']=[]
 reg=target/'source-registry.json'
 if reg.exists():
  try:
   records=json.loads(reg.read_text(encoding='utf-8'))
   if not isinstance(records,list) or any(not isinstance(record,dict) or not isinstance(record.get('id'),str) for record in records):raise ValueError('来源登记格式无效')
   if len({record['id'] for record in records})!=len(records):raise ValueError('来源登记标识重复')
   for record in records:
    if record['id'] in accepted:record.update(verifiedAdapter=True,lastCheckedAt=now)
   save_json(reg,records)
  except Exception as exc:d['maintenanceWarnings'].append('来源登记未更新，观测结果单独保存：'+str(exc))
 save_json(target/'data.json',d)
 return d
if __name__=='__main__':
 d=refresh();print(json.dumps(d['fetchHealth'],ensure_ascii=False));print(json.dumps(d['errors'],ensure_ascii=False))
