"""Screen verified feeder stock paths; absence stays unknown."""
import argparse,json,re,datetime as dt,math
from fund_series_tools import NOTICE
from decimal import Decimal
from pathlib import Path
from feeder_equity_exposure import build
from multidimensional_screen import screen,markdown
from research_brief_html import render
from collection_validation import day,unique_pairs,reject_constant

def run(dossier,conditions):
 exposure=build(dossier);parent=dossier['report'];child=dossier['targetReport']
 h=dict(basis='verified-feeder-equity-lookthrough',sourceUrl=parent['metadata']['sourceUrl'],observedAt=exposure['reportDate'],publishedAt=max(parent['metadata']['publishedAt'],child['metadata']['publishedAt']),complete=False,scope='partialFeederEquity',coveredSecurityNamespaces=list(sorted({x['namespace'] for x in exposure['rows']})),value=[dict(code=x['code'],market=x['namespace'],weightPct=float(Decimal(x['weight'])*100)) for x in exposure['rows']])
 candidate=dict(code=exposure['code'],name='联接基金已核验股票路径',kind='fund',market='CN',holdings=h)
 spec=dict(asOf=exposure['asOf'],candidates=[candidate],conditions=conditions)
 result=screen(spec);result['screeningInput']=spec;result['lookthroughEvidence']=exposure
 result['limitations']=['仅已核验一层股票暴露，未出现或不足阈值不能证明全组合不持有','来源为父子同期报告副本，不代表当前持仓；非股票与衍生品未展开']
 return result

def run_many(dossiers,conditions,asof):
 day(asof)
 if not isinstance(conditions,list) or not conditions:raise ValueError('研究条件不能为空')
 for c in conditions:
  if not isinstance(c,dict):raise ValueError('证券筛选条件须为对象')
  v=c.get('minimumWeightPct',0)
  if c.get('kind')!='holding' or not c.get('code') or not c.get('market') or isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:raise ValueError('仅支持非负有限权重的证券持仓条件')
 if not isinstance(dossiers,list) or not 1<=len(dossiers)<=500:raise ValueError('指定基金池须1至500项')
 if any(not isinstance(x,dict) or ('report' in x and x['report'] is not None and not isinstance(x['report'],dict)) for x in dossiers):raise ValueError('基金池档案及报告须为对象')
 codes=[x.get('code') or (x.get('report') or {}).get('code') for x in dossiers]
 if any(not isinstance(x,str) or not re.fullmatch(r'\d{6}',x) for x in codes) or len(set(codes))!=len(codes):raise ValueError('基金池代码非法或重复')
 result=dict(type='feeder-pool-holdings-screen',asOf=asof,scope='指定联接基金研究池',candidateCount=len(dossiers),conditions=conditions,selected=[],excluded=[],unknown=[],coverage=[],rankingGroups=[],rankingGaps=[],riskNotice=NOTICE,limitations=['指定输入基金池，不代表全市场','未完成穿透的对象保留资料不足，未展开资产不当作零持仓'],screeningInput=dict(asOf=asof,candidates=[],conditions=conditions),lookthroughEvidence={})
 for code,dossier in zip(codes,dossiers):
  try:
   if (dossier.get('report') or {}).get('code')!=code:raise ValueError('请求代码与父报告代码不一致')
   if dossier.get('asOf')!=asof:raise ValueError('档案截止日与本次基金池截止日不同')
   one=run(dossier,conditions)
   if one['screeningInput']['asOf']!=asof:raise ValueError('父子报告实际截止日与基金池不同')
   for key in ['selected','excluded','unknown']:result[key]+=one[key]
   result['screeningInput']['candidates']+=one['screeningInput']['candidates']
   result['lookthroughEvidence'][code]=one['lookthroughEvidence']
  except (ValueError,KeyError,OSError,TypeError,ArithmeticError) as exc:
   result['unknown'].append(dict(code=code,kind='fund',market='CN',name=code,checks=[dict(condition=c,passed=None,reason='穿透资料未完成：'+str(exc)) for c in conditions]))
 for i,c in enumerate(conditions):result['coverage'].append(dict(condition=c,usable=sum(x['checks'][i]['passed'] is not None for key in ['selected','excluded','unknown'] for x in result[key]),total=len(dossiers)))
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out)
 if any(x.exists() for x in [out,out.with_suffix('.md'),out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 s=json.loads(Path(a.input).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant);r=run_many(s['dossiers'],s['conditions'],s['asOf']) if 'dossiers' in s else run(s['dossier'],s['conditions']);text=markdown(r,r['screeningInput'])+'\n\n'+'\n'.join('- '+x for x in r['limitations']);markup=render(text);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');out.with_suffix('.md').write_text(text,encoding='utf-8');out.with_suffix('.html').write_text(markup,encoding='utf-8')
