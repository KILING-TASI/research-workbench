"""Convert reconciled equity report archives into evidence-bound candidates."""
import argparse,json,math
from pathlib import Path
from fund_series_tools import day,source
from multidimensional_screen import screen,markdown,validate_rules
from research_brief_html import render as render_html
from collection_validation import unique_pairs,reject_constant,finite_json_float

def read_json(path):
 return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def read_input(path):
 path=Path(path).resolve();spec=read_json(path)
 if isinstance(spec,dict) and isinstance(spec.get('reports'),list):
  spec['reports']=[str((path.parent/Path(p)).resolve()) if isinstance(p,str) and p.strip() else p for p in spec['reports']]
 return spec

def instrument_identity(identity,code,asof):
 if identity is None:return dict(kind='fund',market='CN-fund',instrumentType='fund-unclassified',identityEvidence=None)
 if identity.get('code')!=code:raise ValueError('证券身份代码不一致')
 day(identity['observedAt']);source(identity['sourceUrl'])
 if identity['observedAt']>asof:raise ValueError('证券身份资料晚于截止日')
 category=identity.get('instrumentType')
 if category not in ('exchange-traded-etf','etf-link','fund'):raise ValueError('证券身份类型不支持')
 if not isinstance(identity.get('quote'),str) or not identity['quote'].strip():raise ValueError('证券身份缺少原文依据')
 exchange=identity.get('exchange')
 if category=='exchange-traded-etf' and exchange not in ('SSE','SZSE'):raise ValueError('场内ETF缺少明确交易所')
 return dict(kind='etf' if category=='exchange-traded-etf' else 'fund',market=exchange if category=='exchange-traded-etf' else 'CN-fund',instrumentType=category,identityEvidence=identity)

def candidate(r,asof,identity=None):
 day(asof);day(r['reportDate']);day(r['metadata']['publishedAt']);source(r['metadata']['sourceUrl'])
 if not r['reportDate']<=r['metadata']['publishedAt']<=asof:raise ValueError('报告披露日期越界')
 h=r.get('holdings')
 if not h or r['status']!='副本身份及股票持仓勾稽完成':raise ValueError('完整股票持仓未核验')
 if h['id']!=r['code'] or h['reportDate']!=r['reportDate'] or h['publishedAt']!=r['metadata']['publishedAt']:raise ValueError('报告身份/日期不一致')
 if h['sourceSha256']!=r['sha256'] or h['sourceUrl']!=r['metadata']['sourceUrl']:raise ValueError('报告哈希/来源不一致')
 if h.get('disclosureScope')!='completeEquity':raise ValueError('非完整股票披露')
 values=[];seen=set()
 for x in h['holdings']:
  namespace=x['securityNamespace'];key=(namespace,x['code'])
  if namespace not in ('CN-equity','HK-equity','US-equity') or key in seen:raise ValueError('股票命名空间不支持或重复')
  seen.add(key);weight=x['weight']
  if isinstance(weight,bool) or not isinstance(weight,(int,float)) or not math.isfinite(weight) or weight<0:raise ValueError('股票权重无效')
  values.append(dict(code=x['code'],market=namespace,weightPct=weight*100,name=x['name'],locator=x['locator']))
 if abs(sum(x['weightPct'] for x in values)/100-h['equityWeight'])>1e-8:raise ValueError('持仓合计与权益比例不一致')
 ev=dict(observedAt=r['reportDate'],publishedAt=r['metadata']['publishedAt'],sourceUrl=r['metadata']['sourceUrl'],sourceSha256=r['sha256'])
 return dict(code=r['code'],**instrument_identity(identity,r['code'],asof),name=r['metadata']['title'],fields=dict(aumCNY=dict(ev,value=h['netAssetsCNY'],basis='fund-all-share-classes-net-assets',unit='CNY')),holdings=dict(ev,value=values,complete=True,basis='actual-fund-holdings',scope='completeEquity',coveredSecurityNamespaces=['CN-equity','HK-equity','US-equity'],marketIdentity='命名空间为境内/香港/美国股票，不代表具体交易所'),limitations=['完整性仅指股票表，不含债券与衍生品','报告期末快照不代表当前持仓','不同份额共用全基金净资产，不能重复累计规模','原始PDF副本身份与勾稽不等于官方发布网页核验'])
def build(s):
 day(s['asOf'])
 if not isinstance(s.get('reports'),list) or not 1<=len(s['reports'])<=5000:raise ValueError('需1至5000份报告输入')
 if any(not isinstance(p,str) or not p.strip() for p in s['reports']) or len(s['reports'])!=len(set(s['reports'])):raise ValueError('报告路径须非空且不重复')
 validate_rules(s.get('conditions'))
 result=[];gaps=[];identities={}
 for identity in s.get('identities',[]):
  code=identity['code']
  if code in identities:raise ValueError('同代码证券身份重复，需先解释冲突')
  identities[code]=identity
 for path in s['reports']:
  try:
   report=read_json(path)
   result.append(candidate(report,s['asOf'],identities.get(report['code'])))
  except Exception as exc:gaps.append(dict(path=path,reason=str(exc)))
 spec=dict(asOf=s['asOf'],scope='指定已取得报告池；股票命名空间反查',candidates=result,conditions=s['conditions'])
 if s.get('rank'):spec['rank']=s['rank']
 return dict(status='available' if result else 'unavailable',screenInput=spec,result=screen(spec) if result else None,reportGaps=gaps,requestedReportCount=len(s['reports']),usableReportCount=len(result),failedReportCount=len(gaps),requestedReports=list(s['reports']))
def report_text(r):
 text=markdown(r['result'],r['screenInput']) if r['result'] is not None else '# 报告持仓条件研究\n\n本次没有可用的已核验报告，未执行条件筛选。不能据此判断没有匹配基金；请先补齐下列报告资料。'
 if 'requestedReportCount' in r:
  text+='\n\n## 本次资料覆盖\n请求'+str(r['requestedReportCount'])+'份报告，可用于筛选'+str(r['usableReportCount'])+'份，失败'+str(r['failedReportCount'])+'份。筛选统计仅覆盖可用报告；失败对象未被认定为不满足条件。\n'
 text+='\n\n## 报告核对与范围\n完整性仅指报告期末股票表，不覆盖债券、衍生品，也不代表当前持仓。规模为全基金各份额合计净资产，不能按份额重复累计。\n'
 text+='\n## 未进入筛选的报告\n'
 if not r['reportGaps']:text+='本次输入报告均通过筛选输入核对。\n'
 for gap in r['reportGaps']:text+='- '+str(gap['path']).replace('|','／')+'：'+gap['reason']+'\n'
 return text

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=build(read_input(a.input));a.out.parent.mkdir(parents=True,exist_ok=True)
 a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 text=report_text(r);a.out.with_suffix('.md').write_text(text,encoding='utf-8');a.out.with_suffix('.html').write_text(render_html(text,title='报告持仓条件研究'),encoding='utf-8')
