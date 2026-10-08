"""Parse EIA weekly commercial crude stocks, preserving period and missing values."""
import datetime as dt,re
from html.parser import HTMLParser
from collection_validation import day as observation_day
URL='https://www.eia.gov/dnav/pet/hist/LeafHandler.ashx?f=W&n=PET&s=WCESTUS1'
TITLE='Weekly U.S. Ending Stocks excluding SPR of Crude Oil (Thousand Barrels)'
class History(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.title=[];self.in_title=False;self.rows=[];self.row=None;self.cell=None
 def handle_starttag(self,tag,attrs):
  if tag=='title':self.in_title=True
  if tag=='tr':self.row=[]
  if tag=='td' and self.row is not None:self.cell=[dict(attrs).get('class',''),[]]
 def handle_data(self,data):
  if self.in_title:self.title.append(data)
  if self.cell is not None:self.cell[1].append(data)
 def handle_endtag(self,tag):
  if tag=='title':self.in_title=False
  if tag=='td' and self.cell is not None:
   if self.row is not None:self.row.append((self.cell[0],' '.join(''.join(self.cell[1]).split())))
   self.cell=None
  if tag=='tr' and self.row is not None:
   if any(c=='B6' for c,t in self.row):self.rows.append(self.row)
   self.row=None

def parse(raw,start,end):
 if not isinstance(raw,bytes):raise ValueError('EIA响应须为原始字节')
 if observation_day(start)>observation_day(end):raise ValueError('EIA库存查询起始日晚于截止日')
 parser=History();parser.feed(raw.decode('utf-8-sig'))
 if ' '.join(''.join(parser.title).split())!=TITLE:raise ValueError('EIA库存标题或范围不匹配，不能混入含SPR或石油产品总库存')
 points=[];missing=[];seen=[]
 months={m:i+1 for i,m in enumerate(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])}
 if not parser.rows:raise ValueError('未找到EIA历史库存表，不解析空页面')
 for row in parser.rows:
  if len(row)!=11 or row[0][0]!='B6' or any(row[i][0]!='B5' or row[i+1][0]!='B3' for i in [1,3,5,7,9]):raise ValueError('EIA库存行列结构变化，需复核')
  match=re.fullmatch(r'(\d{4})-([A-Za-z]{3})',row[0][1])
  if not match or match[2] not in months:raise ValueError('库存年月标识无效')
  year=int(match[1]);month=months[match[2]]
  for i in [1,3,5,7,9]:
   date,value=row[i][1],row[i+1][1]
   if not date:
    if value:raise ValueError('库存数值无对应统计期，不能猜日期')
    continue
   day=dt.date.fromisoformat(f'{year:04d}-'+date.replace('/','-')).isoformat()
   if dt.date.fromisoformat(day).month!=month:raise ValueError('统计期与所在年月行冲突')
   seen.append(day)
   if not start<=day<=end:continue
   if value in ['', '.', 'NA','--']:missing.append(day);continue
   if not re.fullmatch(r'\d{1,3}(?:,\d{3})+|\d+',value):raise ValueError('库存数值格式无效')
   n=int(value.replace(',',''))
   if n<=0:raise ValueError('库存须为正，不能将缺失写成零')
   points.append(dict(date=day,value=n,publishedAt=None))
 if seen!=sorted(set(seen)):raise ValueError('EIA库存统计期重复或乱序')
 return points,missing
