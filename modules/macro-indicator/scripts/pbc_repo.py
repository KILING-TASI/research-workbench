"""Read only seven-day pledged reverse-repo rates from PBC notices."""
import re,html,datetime,concurrent.futures,urllib.parse
from resilient_fetch import get_text
INDEX='https://www.pbc.gov.cn/zhengcehuobisi/125207/125213/125431/125475/index.html'
def plain(s):return re.sub(r'\s+','',html.unescape(re.sub(r'<[^>]+>','',s)))
def parse_notice(text,url,today):
 release=re.search(r'id=[\"\x27]shijian[\"\x27][^>]*>\s*(\d{4}-\d{2}-\d{2})',text)
 if not release:raise ValueError('公告缺发布日期')
 pub=datetime.date.fromisoformat(release.group(1)).isoformat()
 if pub>today:return None
 zoom=text.find('id="zoom"')
 if zoom<0:raise ValueError('公告正文结构变更')
 body=text[zoom:];flat=plain(body)
 if '买断式逆回购' in flat:return None
 operation=re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日[^。]{0,140}逆回购',flat)
 if not operation:
  if not re.search(r'7天(?:期)?',flat):return None
  raise ValueError('公告缺可核实的操作日')
 date=datetime.date(*(int(x) for x in operation.groups())).isoformat()
 if date>today:return None
 ratecol=None
 for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>',body,re.S|re.I):
  cells=[plain(x) for x in re.findall(r'<t[dh]\b[^>]*>(.*?)</t[dh]>',row,re.S|re.I)]
  if '期限' in cells:
   columns=[i for i,x in enumerate(cells) if x in ['操作利率','中标利率']]
   ratecol=columns[0] if len(columns)==1 else None
  if cells and cells[0] in ['7天','7天期']:
   if ratecol is None and len(cells)>1 and all(re.fullmatch(r'0(?:\.0+)?亿元',x) for x in cells[1:]):return None
   if ratecol is None or ratecol>=len(cells):raise ValueError('7天利率表头无法核实')
   match=re.fullmatch(r'(\d+(?:\.\d+)?)%',cells[ratecol])
   if not match:raise ValueError('7天利率字段不是百分数')
   value=float(match.group(1))
   if not 0<=value<=20:raise ValueError('7天利率超出合理范围')
   return dict(period=date,value=value,publishedAt=pub,sourceUrl=url,tenor='7天',operationType='质押式逆回购')
 return None
def fetch(today,metrics=None):
 metrics=metrics if metrics is not None else {};metrics['attempts']=0
 count={};text=get_text(INDEX,timeout=10,metrics=count);metrics['attempts']+=count.get('attempts',0)
 links=[]
 for url,title in re.findall(r'<a[^>]*href=[\"\x27]([^\"\x27]+)[\"\x27][^>]*>(.*?)</a>',text,re.S):
  url=urllib.parse.urljoin(INDEX,url)
  if '公开市场业务交易公告' in plain(title) and '/125475/' in url and url!=INDEX and urllib.parse.urlparse(url).hostname=='www.pbc.gov.cn':links.append(url)
 links=list(dict.fromkeys(links))[:20]
 if not links:raise ValueError('官方公告目录未返回有效链接')
 def job(url):
  count={}
  try:return parse_notice(get_text(url,timeout=10,metrics=count),url,today),None,count.get('attempts',0)
  except Exception as e:return None,url+': '+str(e),count.get('attempts',0)
 history=[];errors=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for point,error,attempts in pool.map(job,links):
   metrics['attempts']+=attempts
   if point:history.append(point)
   if error:errors.append(error)
 if not history:raise ValueError('官方公告未返回可核实的7天逆回购利率')
 metrics.update(notices=len(links),parsed=len(history),partial_errors=errors)
 grouped={}
 for point in history:grouped.setdefault(point['period'],[]).append(point)
 conflicts=[dict(period=period,candidates=points) for period,points in grouped.items() if len({p['value'] for p in points})>1]
 if conflicts:
  metrics['conflicts']=conflicts
  raise ValueError('同一操作日7天利率冲突，保留候选，不能静默合并')
 result=[]
 for points in grouped.values():
  point=dict(points[0])
  if len(points)>1:point['matchingSources']=[dict(sourceUrl=p['sourceUrl'],publishedAt=p['publishedAt']) for p in points]
  result.append(point)
 return sorted(result,key=lambda p:p['period'])
