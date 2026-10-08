"""Link declared nonoverlapping total-return periods, not performance attribution."""
import argparse,json,datetime as dt,hashlib
from decimal import Decimal,InvalidOperation
from pathlib import Path
from collection_validation import day

def calculate(spec):
 if not isinstance(spec,dict):raise ValueError('收益链接输入须为对象')
 periods=spec.get('periods')
 if not isinstance(periods,list) or not periods:raise ValueError('需要至少一期收益')
 required=('currency','returnBasis','benchmarkId','benchmarkVersion','inputPrecision')
 for key in required:
  if not isinstance(spec.get(key),str) or not spec[key].strip():raise ValueError('缺少口径：'+key)
 if spec['returnBasis']!='total-return':raise ValueError('本入口仅链接声明的总收益；未复权价格不可替代')
 if spec['inputPrecision'] not in ('reported-rounded','unrounded-declared'):raise ValueError('输入精度声明无效')
 fund=benchmark=Decimal(1);previous=None;seen=[]
 bounds=[Decimal(1)]*4;bound_complete=True
 for row in periods:
  if not isinstance(row,dict):raise ValueError('每期收益须为对象')
  for key in required[:-1]:
   if row.get(key)!=spec[key]:raise ValueError('逐期口径不一致：'+key)
  start=day(row.get('start'));end=day(row.get('end'))
  if start>end:raise ValueError('期间起止倒置')
  if previous is not None and start!=previous+dt.timedelta(days=1):raise ValueError('期间重叠、乱序或存在空档；不补造缺期收益')
  for field in ('source','fundReturnPct','benchmarkReturnPct'):
   if field not in row or isinstance(row[field],bool):raise ValueError('缺少收益或来源')
  if not isinstance(row['source'],str) or not row['source'].strip():raise ValueError('来源不能为空')
  try:f=Decimal(str(row['fundReturnPct']));b=Decimal(str(row['benchmarkReturnPct']))
  except InvalidOperation as e:raise ValueError('收益不是有效数值') from e
  if not f.is_finite() or not b.is_finite() or f<-100 or b<=-100:raise ValueError('收益越界；基准财富须大于零')
  precision=row.get('returnPctDecimalPlaces')
  if precision is not None:
   if spec['inputPrecision']!='reported-rounded' or not isinstance(precision,int) or isinstance(precision,bool) or not 0<=precision<=8:raise ValueError('披露百分比精度须为0至8整数，且仅用于舍入输入')
   quantum=Decimal(1).scaleb(-precision)
   if f%quantum or b%quantum:raise ValueError('输入收益含超过声明披露精度的小数')
   half=quantum/2
   lows=[max(Decimal(-100),f-half),max(Decimal(-100),b-half)]
   if lows[1]<=-100:raise ValueError('舍入范围触及基准零财富，不能计算相对范围')
   for i,value in enumerate((lows[0],f+half,lows[1],b+half)):bounds[i]*=1+value/100
  else:bound_complete=False
  fund*=1+f/100;benchmark*=1+b/100;previous=end;seen.append(dict(row))
 envelope=None
 if bound_complete:
  fl,fh,bl,bh=bounds
  envelope={'fundReturnPct':[str((fl-1)*100),str((fh-1)*100)],'benchmarkReturnPct':[str((bl-1)*100),str((bh-1)*100)],'gapPp':[str((fl-bh)*100),str((fh-bl)*100)],'relativeTerminalWealthGapPct':[str((fl/bh-1)*100),str((fh/bl-1)*100)],'assumption':'各期百分比按声明小数位四舍五入；保守闭区间包络，不认证原文舍入规则。','scope':'仅显示舍入误差，不是统计置信区间、数据错误界限或未来收益范围。'}
 return {'start':periods[0]['start'],'end':periods[-1]['end'],'linkedFundReturnPct':str((fund-1)*100),'linkedBenchmarkReturnPct':str((benchmark-1)*100),'linkedGapPp':str((fund-benchmark)*100),'relativeTerminalWealthGapPct':str((fund/benchmark-1)*100),'roundingEnvelope':envelope,'roundingEnvelopeStatus':'calculated-from-declared-precision' if envelope else 'precision-not-declared-for-every-period','periods':seen,'basis':{k:spec[k] for k in required},'formula':'product(1+periodReturnPct/100)-1','verification':'输入口径声明及代数检查；不自动核验原文、有效基准或逐日净值','limitations':['报告显示收益连乘保留舍入误差，不称未舍入精确收益','累计收益差不是各期差值之和、日度跟踪误差或经理贡献','不输出年化损耗、同类排名或未来收益']}

def main():
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--markdown',type=Path);a=p.parse_args()
 if a.out.exists():raise ValueError('输出已存在，不覆盖旧结果或输入')
 if a.markdown and (a.markdown.exists() or a.markdown.resolve()==a.out.resolve()):raise ValueError('简报路径已存在或与结果路径相同')
 for target in [a.out]+([a.markdown] if a.markdown else []):
  if not target.parent.is_dir():raise ValueError('输出目录不存在，先指定有效新目录')
 raw=a.input.read_bytes()
 from collection_validation import unique_pairs,reject_constant
 result=calculate(json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant))
 result['inputSha256']=hashlib.sha256(raw).hexdigest()
 result['methodFiles']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),Path(__file__).with_name('collection_validation.py')]}
 prose=brief(result) if a.markdown else None
 with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 if a.markdown:
  with a.markdown.open('x',encoding='utf-8') as f:f.write(prose)

def brief(result):
 def pct(field):return format(Decimal(result[field]),'.2f')
 gap=Decimal(result['linkedGapPp']);relation='领先' if gap>0 else '落后' if gap<0 else '相同'
 judgment='在声明的连续期间内，基金累计收益'+pct('linkedFundReturnPct')+'%，基准'+pct('linkedBenchmarkReturnPct')+'%，累计'+relation+(format(abs(gap),'.2f')+'个百分点。' if gap else '。')
 lines=['# 连续期间历史表现简报','',judgment,'','这回答的是该窗口相对表现，不是经理个人贡献或未来收益。累计差由分期收益连乘后比较，不是将每期差值简单相加。','','## 期间与比较依据',result['start']+'至'+result['end']+'；币种'+result['basis']['currency']+'。基准：'+result['basis']['benchmarkId']+'；版本声明：'+result['basis']['benchmarkVersion']+'。','口径一致只经过输入声明检查，原文与有效基准仍需另行核验。','','## 披露精度怎样影响结果']
 envelope=result.get('roundingEnvelope')
 if envelope:
  low,high=envelope['fundReturnPct'];lines+=['按声明的四舍五入精度，累计基金收益的舍入包络约为'+format(Decimal(low),'.4f')+'%至'+format(Decimal(high),'.4f')+'%。','这仅是显示舍入影响，不是统计置信区间、原始数据正确性界限或未来收益范围。']
 else:lines+=['各期显示精度未全部声明，不给舍入范围。多位计算结果不代表更高可信精度。']
 lines+=['','## 每期资料来源']
 for row in result['periods']:
  source=row['source'].replace('\r',' ').replace('\n',' ')
  lines+=['- '+row['start']+'至'+row['end']+'：'+source]
 lines+=['','## 本次仍不能判断','未取得日度序列、完整事件及费用时，不能由分期收益计算最大回撤、波动或日度跟踪误差。自身基准差不能直接用于跨产品同类排名、个人能力归因或替换建议。','']
 return '\n'.join(lines)
if __name__=='__main__':main()
