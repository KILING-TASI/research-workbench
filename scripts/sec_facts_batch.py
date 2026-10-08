"""Batch supplied SEC fact archives; preserve missing-company denominator."""
import argparse,json,re,hashlib
from pathlib import Path
from sec_company_facts import parse,select_period
from fund_series_tools import day
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant,finite_json_float

def read_json(path):
 return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def read_input(path):
 path=Path(path).resolve();s=read_json(path)
 if isinstance(s,dict) and isinstance(s.get('archives'),list):
  for item in s['archives']:
   if isinstance(item,dict) and isinstance(item.get('path'),str) and item['path'].strip():item['path']=str((path.parent/Path(item['path'])).resolve())
 return s

def run(s):
 asof=day(s['asOf']);items=s['archives']
 if not isinstance(items,list) or not 1<=len(items)<=100:raise ValueError('需1至100个归档输入')
 if any(not isinstance(item,dict) or not isinstance(item.get('path'),str) or not item['path'].strip() for item in items):raise ValueError('归档条目须含有效路径')
 if bool(s.get('periodStart'))!=bool(s.get('periodEnd')):raise ValueError('财务期间起止同时提供')
 if s.get('periodStart'):select_period(dict(asOf=asof,metrics={}),s['periodStart'],s['periodEnd'])
 results=[];gaps=[];seen=set()
 for item in items:
  cik=item['cik']
  if not isinstance(cik,str) or not re.fullmatch(r'\d{10}',cik) or cik in seen:raise ValueError('CIK非法或重复')
  seen.add(cik)
  try:
   path=Path(item['path']);raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
   if item.get('sha256') and item['sha256']!=digest:raise ValueError('归档文件摘要不一致')
   r=parse(json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float),cik,asof);r.update(inputPath=str(path.resolve()),inputSha256=digest,inputProvenance='用户指定归档；来源获取过程未自动验证')
   if s.get('periodStart'):r['periodSelection']=select_period(r,s['periodStart'],s['periodEnd'])
   results.append(r)
  except (ValueError,KeyError,TypeError,OSError) as exc:gaps.append(dict(cik=cik,reason=str(exc)))
 return dict(type='sec-facts-batch',asOf=asof,candidateCount=len(items),requestedCIKs=[x['cik'] for x in items],results=results,gaps=gaps,limitations=['指定归档池，不是全市场采集','共同查询期间不保证各公司财季或会计准则相同；未生成财务优劣排名','缺公司与缺标签分别保留，不补零或按其他公司回填'])

def cell(value):
 return str(value).replace('|','／').replace('\n',' ').replace('\r',' ')

def markdown(r):
 lines=['# 多公司申报财务资料核对','',f"截止日{r['asOf']}；输入{r['candidateCount']}个主体，可解析{len(r['results'])}个，失败{len(r['gaps'])}个。",'这里只展示数据覆盖，不是公司财务评级。','','| 申报主体 | CIK | 已取得标签数 | 标签缺口数 |','| --- | --- | ---: | ---: |']
 for x in r['results']:lines.append('| '+x['entityName'].replace('|','／')+' | '+x['cik']+' | '+str(sum(bool(m['observations']) for m in x['metrics'].values()))+' | '+str(len(x['gaps']))+' |')
 for x in r['results']:
  lines+=['','## '+cell(x['entityName'])+'的资料范围',
   '归档文件：'+cell(x['inputPath']),
   '文件摘要（SHA-256）：'+x['inputSha256'],
   '来源状态：'+x['inputProvenance']+'。文件摘要只能核对副本一致性，不能证明数据由SEC取得。']
  if x['gaps']:
   lines+=['','未取得字段：']+['- '+cell(g['metric'])+'：'+cell(g['reason']) for g in x['gaps']]
  else:lines+=['','指定标签均有观测；这不代表报表、附注或历史期间完整。']
  if x.get('periodSelection'):
   q=x['periodSelection'];lines+=['','查询期间：'+q['start']+'至'+q['end']+'。',
    '| 财务标签 | 完整落入期间数 | 跨边界累计期间数 |','| --- | ---: | ---: |']
   for key in x['metrics']:
    lines.append('| '+cell(key)+' | '+str(len(q['selectedPeriods'][key]))+' | '+str(len(q['crossBoundaryPeriods'][key]))+' |')
   lines+=['跨边界累计值未转换成单季；该区间没有合格观测时，不用区间外数据补齐。']
 lines+=['','## 未完成主体']+['- '+x['cik']+'：'+x['reason'] for x in r['gaps']]+['','## 使用边界']+['- '+x for x in r['limitations']]
 return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=run(read_input(a.input));a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');t=markdown(r);a.out.with_suffix('.md').write_text(t,encoding='utf-8');a.out.with_suffix('.html').write_text(render(t),encoding='utf-8')
