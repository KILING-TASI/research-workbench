"""Full provider statement fields, dated snapshots and original response retention."""
import argparse,csv,datetime as dt,hashlib,json,re,math
from pathlib import Path
from urllib.parse import urlencode
from market_collect import fetch
from urllib.request import Request,urlopen
import gzip
def native_text(url):
 with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=30) as response:
  raw=response.read()
 if raw[:2]==b"\x1f\x8b":raw=gzip.decompress(raw)
 return raw.decode("utf8")
from collection_validation import unique_pairs,reject_constant,finite_json_float

def native_fetch(url):return json.loads(native_text(url),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def csv_value(value):
 return "'"+value if isinstance(value,str) and value.lstrip().startswith(("=","+","-","@")) else value
from fund_series_tools import day
from research_brief_html import render
TABLES={'balance':'GBALANCE','income':'GINCOME','cashflow':'GCASHFLOW'}
LABELS={'balance':'资产负债表','income':'利润表','cashflow':'现金流量表'}
def validate(code,start,asof):
 if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code):raise ValueError('需六位沪深证券代码')
 day(start);day(asof)
 if start>asof:raise ValueError('区间倒置')
def select(rows,code,start,asof):
 selected=[]
 if not isinstance(rows,list):raise ValueError('报表记录须为数组')
 for x in rows:
  if not isinstance(x,dict):raise ValueError('报表记录须为对象')
  if x.get('SECURITY_CODE')!=code:raise ValueError('证券身份不匹配')
  period=str(x.get('REPORT_DATE',''))[:10];published=str(x.get('NOTICE_DATE',''))[:10];day(period);day(published)
  if period>published:raise ValueError('报告期晚于披露日')
  if start<=period<=asof and published<=asof:selected.append(dict(period=period,publishedAt=published,currency=x.get('CURRENCY'),reportType=x.get('REPORT_TYPE'),raw=x))
 return selected

def native_collect(kind,code,start,asof,folder,sources,hashes,loader,text_loader):
 symbol=('SH' if code.startswith('6') else 'SZ')+code
 base='https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/'
 url=base+'Index?'+urlencode(dict(type='web',code=symbol.lower()))
 html=text_loader(url);(folder/'company-type.html').write_text(html,encoding='utf8');sources.append(url);hashes.append(hashlib.sha256(html.encode('utf8')).hexdigest())
 match=re.search(r'<input[^>]*id="hidctype"[^>]*value="(\d+)"',html)
 if not match:raise ValueError('公司类型未取得，不猜类型')
 stem={'balance':'zcfzb','income':'lrb','cashflow':'xjllb'}[kind]
 def request(endpoint,params,name):
  url=base+endpoint+'?'+urlencode(params);payload=loader(url);raw=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf8');(folder/name).write_bytes(raw);sources.append(url);hashes.append(hashlib.sha256(raw).hexdigest())
  if not isinstance(payload.get('data'),list):raise ValueError('行业专用接口结构不匹配')
  return payload['data']
 params=dict(companyType=match[1],reportDateType='0',code=symbol)
 dates=[]
 for r in request(stem+'DateAjaxNew',params,'report-dates.json'):
  date=str(r.get('REPORT_DATE',''))[:10];day(date)
  if start<=date<=asof:dates.append(date)
 dates=sorted(set(dates),reverse=True)
 if len(dates)>500:raise ValueError('报告期数量超过上限')
 rows=[]
 for i in range(0,len(dates),5):
  batch=request(stem+'AjaxNew',dict(params,reportType='1',dates=','.join(dates[i:i+5])),'native-'+str(i//5+1)+'.json')
  rows.extend(select(batch,code,start,asof))
 if not rows:raise ValueError('行业专用接口无截止日前报表')
 return rows

def collect(code,start,asof,out,loader=fetch,text_loader=native_text):
 validate(code,start,asof);out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在')
 out.mkdir(parents=True);tables={};gaps=[]
 for kind,suffix in TABLES.items():
  folder=out/kind;folder.mkdir();rows=[];sources=[];failure=None;hashes=[]
  try:
   for page in range(1,101):
    url='https://datacenter.eastmoney.com/api/data/v1/get?'+urlencode(dict(reportName='RPT_F10_FINANCE_'+suffix,columns='ALL',filter='(SECURITY_CODE="'+code+'")',pageSize=100,pageNumber=page,sortColumns='REPORT_DATE',sortTypes='-1'))
    payload=loader(url);raw=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf8');(folder/('page-'+str(page)+'.json')).write_bytes(raw);sources.append(url);hashes.append(hashlib.sha256(raw).hexdigest())
    result=payload.get('result')
    if not isinstance(result,dict) or not isinstance(result.get('data'),list):raise ValueError('接口结构不匹配')
    pages=result.get('pages')
    if type(pages)!=int or not 1<=pages<=100:raise ValueError('分页总量未知或超过上限')
    rows.extend(select(result['data'],code,start,asof))
    if page>=pages:break
   if not rows:raise ValueError('截止日前未取得该表数据')
  except Exception as exc:
   failure=str(exc)
   if not rows:
    try:rows=native_collect(kind,code,start,asof,folder,sources,hashes,native_fetch if loader is fetch else loader,text_loader);failure=None
    except Exception as fallback:failure+='；行业接口：'+str(fallback)
   if failure:gaps.append(LABELS[kind]+'：'+failure)
  tables[kind]=dict(status='partial' if failure and rows else 'unavailable' if failure else 'available',rows=rows,sources=sources,responseSha256=hashes,error=failure)
  with (folder/'全部字段.csv').open('w',encoding='utf-8-sig',newline='') as f:
   writer=csv.writer(f);writer.writerow(['reportPeriod','publishedAt','currency','field','value'])
   for r in rows:
    for k,v in r['raw'].items():writer.writerow([csv_value(a) for a in [r['period'],r['publishedAt'],r['currency'],k,'' if v is None else v]])
 common=sorted(set.intersection(*[{r['period'] for r in t['rows']} for t in tables.values()]))
 checks=[]
 for r in tables['balance']['rows']:
  x=r['raw'];v=[x.get(k) for k in ['TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_EQUITY']]
  if all(isinstance(a,(int,float)) and not isinstance(a,bool) and math.isfinite(a) for a in v):
   diff=v[0]-v[1]-v[2];checks.append(dict(period=r['period'],publishedAt=r['publishedAt'],difference=diff,status='within-rounding' if abs(diff)<=.02 else 'difference',basis='资产减负债减所有者权益；渠道原单位'))
 result=dict(code=code,start=start,asOf=asof,retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat(),tables=tables,commonPeriods=common,balanceChecks=checks,gaps=gaps,status='available' if all(t['status']=='available' for t in tables.values()) else 'partial',limitations=['完整仅指接口返回三表全部字段，不证明与公告每一行、附注完全一致','G系列报表按接口披露口径保留，合并/母公司及原文单位仍需正式报告核验','币种和数值按供应商原值保留，空值不填零，金额不自动换算','期间现金流与利润为报告累计口径，不推算单季或跨表因果','当前修订接口不是历史冻结数据，版本及披露时间保留'])
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8');text=markdown(result);(out/'三表说明.md').write_text(text,encoding='utf8');(out/'三表说明.html').write_text(render(text,title='上市公司三张报表'),encoding='utf8');return result

def markdown(r):
 lines=['# '+r['code']+' · 三张报表资料','', '报告期查询'+r['start']+'至'+r['asOf']+'，按披露日截止筛选。','保留各表全部渠道字段；中文说明为覆盖概览，完整明细见各表CSV和JSON。']
 for key,t in r['tables'].items():
  fields=set().union(*(set(x['raw']) for x in t['rows'])) if t['rows'] else set()
  lines+=['','## '+LABELS[key], '状态'+t['status']+'；记录'+str(len(t['rows']))+'条；不同字段'+str(len(fields))+'个。']
  for x in t['rows']:lines.append(x['period']+'，披露'+x['publishedAt']+'，币种'+str(x['currency'])+'，报告类型'+str(x['reportType'])+'。')
  if t['error']:lines.append('资料缺口：'+t['error'])
  lines+=['[数据接口]('+url+')' for url in t['sources']]
 lines+=['','## 三表共同报告期','、'.join(r['commonPeriods']) or '未取得共同报告期','','## 资产负债恒等式核对']
 for c in r['balanceChecks']:lines.append(c['period']+'：差额'+format(c['difference'],'.6f')+'，'+c['status']+'；仅会计恒等式检查，不证明报表真实性。')
 lines+=['','## 资料边界',*r['limitations']];return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--code',required=True);p.add_argument('--start',required=True);p.add_argument('--as-of',required=True);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();collect(a.code,a.start,a.as_of,a.out_dir)
