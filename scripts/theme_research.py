"""Freeze name candidates then collect specified-window fund metrics."""
import argparse,datetime as dt,hashlib,json,urllib.request
from pathlib import Path
from theme_candidates import URL,parse,discover
from fund_batch_screen import run as batch
from multidimensional_screen import screen
from fund_series_tools import day
from research_brief_html import render as render_html

def run(spec,directory,resume=False,catalog_fetch=None,batch_runner=batch):
 day(spec['start']);day(spec['end']);day(spec['asOf'])
 if spec['start']>=spec['end'] or spec['end']>spec['asOf']:raise ValueError('日期范围无效')
 pre=dict(asOf=spec['asOf'],candidates=[dict(code='validation',kind='fund',market='CN',fields={})],conditions=spec['conditions'])
 if spec.get('rank'):pre['rank']=spec['rank']
 screen(pre)
 cap=spec.get('maxCandidates',30)
 if isinstance(cap,bool) or not isinstance(cap,int) or not 1<=cap<=500:raise ValueError('maxCandidates须1至500')
 if not spec.get('terms'):raise ValueError('需提供名称关键词')
 path=Path(directory);freeze=path/'candidates.json'
 if path.exists() and not resume:raise ValueError('目录存在；续采须resume')
 if resume:
  if not freeze.exists():raise ValueError('无候选冻结记录')
  saved=json.loads(freeze.read_text(encoding='utf-8'))
  if saved['request']!=spec:raise ValueError('参数变化，请用新目录')
  raw=(path/'catalog.js').read_text(encoding='utf-8')
  if hashlib.sha256(raw.encode()).hexdigest()!=saved['sha256']:raise ValueError('目录缓存改变，不能续采')
 else:
  if catalog_fetch:raw=catalog_fetch()
  else:
   with urllib.request.urlopen(urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as response:raw=response.read().decode('utf-8-sig')
  rows=parse(raw);found=discover(rows,spec['terms'],spec.get('exclude'),spec.get('fundType'),spec.get('mode','any'),5000)
  # No alphabetical silent cap: narrower query or explicit candidate codes required.
  if found['matchedCount']>cap:raise ValueError(f"名称匹配{found['matchedCount']}项，超过本次上限{cap}；请缩小条件或使用指定池，不按代码截断筛选")
  saved=dict(request=spec,sourceUrl=URL,retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat(),sha256=hashlib.sha256(raw.encode()).hexdigest(),**found)
  path.mkdir(parents=True,exist_ok=True);(path/'catalog.js').write_text(raw,encoding='utf-8');freeze.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
 if not saved['codes']:
  (path/'研究摘要.md').write_text('名称条件没有匹配候选。不能据此认定市场不存在该主题基金。',encoding='utf-8');return dict(candidates=saved,result=None)
 b={k:spec[k] for k in ['start','end','asOf','conditions']}
 b['codes']=saved['codes']
 for key in ['annualRiskFreePct','rank']:
  if key in spec:b[key]=spec[key]
 dest=path/'metrics';result=batch_runner(b,dest,resume=resume and dest.exists())
 summary=['# 名称候选研究','',f"名称匹配{len(saved['codes'])}个代码；满足指标条件{len(result['selected'])}项，不满足{len(result['excluded'])}项，数据不足{len(result['unknown'])}项。",'', '名称匹配仅用于构建本次候选，未核实主题投资暴露。不同份额未合并；当前目录不用于事前历史策略检验。','', '指标取数与共同区间、各标的失败原因见 metrics/筛选简报.md；原始目录和候选清单保留供复查。','', '本结果为公开资料与历史样本研究，不构成投资建议。']
 text='\n'.join(summary)
 if (dest/'筛选简报.md').exists():text+='\n\n'+(dest/'筛选简报.md').read_text(encoding='utf-8')
 (path/'研究摘要.md').write_text(text,encoding='utf-8');(path/'研究摘要.html').write_text(render_html(text),encoding='utf-8');return dict(candidates=saved,result=result)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',required=True);p.add_argument('--resume',action='store_true');a=p.parse_args();run(json.loads(a.input.read_text(encoding='utf-8-sig')),a.out_dir,a.resume)
