"""Stateful source switching; adapters must supply verified, comparable observations."""
from datetime import datetime,timedelta
import math

def compatible(a,b,rate=False):
 for key in ('definition','unit','currency','algorithm_version'):
  if any(not isinstance(row.get(key),str) or not row[key].strip() for row in (a,b)):return False,'口径字段未明确：'+key
  if a.get(key)!=b.get(key):return False,'口径不一致：'+key
 try:
  da=datetime.fromisoformat(a['data_period']);db=datetime.fromisoformat(b['data_period'])
  if abs((da-db).total_seconds())>86400:return False,'统计期超出T+1'
  if isinstance(a['value'],bool) or isinstance(b['value'],bool):return False,'数值无效'
  x,y=float(a['value']),float(b['value'])
 except (KeyError,ValueError,TypeError):return False,'字段不完整'
 if not math.isfinite(x) or not math.isfinite(y):return False,'数值无效'
 tolerance=.005 if rate else abs(x)*.005
 return abs(x-y)<=tolerance,'数值偏差超阈值' if abs(x-y)>tolerance else '一致'

def transition(prior,primary_ok,backup_ok,dual=True,comparable=True):
 s=dict(prior or {});s.setdefault('mode','primary');s.setdefault('failures',0);s.setdefault('successes',0)
 s['successes']=s['successes']+1 if primary_ok else 0
 s['failures']=0 if primary_ok else s['failures']+1
 if s['mode']=='backup':
  if primary_ok and s['successes']>=2:s['mode']='primary'
  elif not backup_ok or not comparable:s['mode']='failed'
 elif primary_ok:s['mode']='primary'
 elif dual and s['failures']>=2 and backup_ok and comparable:s['mode']='backup'
 else:s['mode']='failed'
 s['availability']={'primary':1,'backup':.85,'failed':0}[s['mode']]
 s['pool_cap']=.7 if s['mode']=='backup' else 1
 return s

def deviation(prior,consistent):
 n=0 if consistent else int((prior or {}).get('deviations',0))+1
 return dict(deviations=n,reviewRequired=n>=3)
