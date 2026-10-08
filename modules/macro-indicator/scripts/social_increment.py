"""Monthly TSF flow, independently stored; no invented publication dates."""
import json,re,math
from resilient_fetch import get_text
URL='https://data.mofcom.gov.cn/datamofcom/front/gnmy/shrzgmQuery'
def fetch(today,metrics=None):
 raw=json.loads(get_text(URL,timeout=10,metrics=metrics,method='POST',data=b''))
 if not isinstance(raw,list):raise ValueError('社融增量接口结构变更')
 points={}
 for row in raw:
  date=str(row.get('date',''));value=row.get('tiosfs')
  if not re.fullmatch(r'\d{4}(0[1-9]|1[0-2])',date):continue
  period=date[:4]+'-'+date[4:]
  if period>=today[:7] or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):continue
  if period in points and points[period]['value']!=value:raise ValueError('社融增量同期间数值冲突，不能静默覆盖')
  points[period]=dict(period=period,value=value,publishedAt=None)
 history=sorted(points.values(),key=lambda r:r['period'])
 if not history:raise ValueError('社融增量接口未返回有效月度观测')
 return history
