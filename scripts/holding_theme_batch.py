"""Apply one explicit classification version to a supplied fund dossier pool."""
import argparse,json,re
from pathlib import Path
from holding_theme_exposure import calculate,threshold_check
from fund_series_tools import day,NOTICE
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant

def run(s):
 if not isinstance(s,dict):raise ValueError('主题批量输入须为对象')
 asof=day(s['asOf']);rows=s['dossiers']
 if not isinstance(rows,list) or not 1<=len(rows)<=500:raise ValueError('需要1至500份基金档案')
 threshold_check([0,100],s['minimumWeightPctOfNAV'])
 if not s.get('theme') or not s.get('classificationVersion'):raise ValueError('主题和分类版本必须明确')
 results=[];gaps=[];seen=set()
 for row in rows:
  if not isinstance(row,dict):raise ValueError('基金档案条目须为对象')
  code=row.get('code')
  if not isinstance(code,str) or not re.fullmatch(r'\d{6}',code) or code in seen:raise ValueError('代码非法或重复')
  seen.add(code)
  try:
   report=row['report']
   if row['asOf']!=asof or report['asOf']!=asof or report['code']!=code:raise ValueError('档案代码或截止日不一致')
   results.append(calculate(dict(asOf=asof,theme=s['theme'],classificationVersion=s['classificationVersion'],classifications=s.get('classifications',[]),minimumWeightPctOfNAV=s['minimumWeightPctOfNAV'],report=report)))
  except (ValueError,KeyError,TypeError,OSError) as exc:gaps.append(dict(code=code,reason=str(exc)))
 return dict(type='holding-theme-batch',asOf=asof,theme=s['theme'],classificationVersion=s['classificationVersion'],candidateCount=len(rows),requestedCodes=[x['code'] for x in rows],results=results,gaps=gaps,riskNotice=NOTICE)

def markdown(r):
 lines=['# 指定基金池股票主题研究','',r['theme']+'；分类版本：'+r['classificationVersion']+'；截止日'+r['asOf']+'。','仅已披露股票部分；未知分类不按零处理，上下界不是置信区间。','','| 基金 | 报告日 | 主题权重范围（净资产） | 阈值核对 |','| --- | --- | --- | --- |']
 for x in r['results']:
  lo,hi=x['stockThemeWeightBoundsPctOfNAV'];v=x['thresholdCheck']['passed'];lines.append(f"| {x['code']} | {x['reportDate']} | {lo:.2f}%至{hi:.2f}% | "+('满足' if v is True else '不满足' if v is False else '资料不足')+' |')
 lines+=['','## 待补资料']+['- '+x['code']+'：'+x['reason'] for x in r['gaps']]
 lines+=['','本次分类由输入资料提供，不按基金名称猜测；不同报告日不作同期排名。逐股证据和来源保留在结果文件中。',r['riskNotice']]
 return '\n'.join(lines)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=run(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant));t=markdown(r);html=render(t);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');a.out.with_suffix('.md').write_text(t,encoding='utf-8');a.out.with_suffix('.html').write_text(html,encoding='utf-8')
