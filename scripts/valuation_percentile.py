"""Explicit valuation-series percentile; no fabricated market inputs."""
import argparse,json,math
from pathlib import Path
from fund_series_tools import day,source
from collection_validation import unique_pairs,reject_constant,finite_json_float

def calculate(s):
 asof=day(s['asOf']);start=day(s['start']);source(s['sourceUrl'])
 if start>asof:raise ValueError('起始日晚于截止日')
 for k in ['code','market','subject','metric','method','frequency']:
  if not isinstance(s.get(k),str) or not s[k].strip():raise ValueError('缺少估值身份或口径：'+k)
 minimum=s.get('minimumSamples',60)
 if isinstance(minimum,bool) or not isinstance(minimum,int) or minimum<2:raise ValueError('有效样本下限至少2')
 rows=s['history']
 if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):raise ValueError('估值历史须为对象列表')
 dates=[day(r['date']) for r in rows]
 if dates!=sorted(set(dates)):raise ValueError('日期乱序或重复')
 usable=[];excluded=[]
 for r in rows:
  d=r['date']
  if not start<=d<=asof:continue
  if r.get('publishedAt') is not None and day(r['publishedAt'])>asof:excluded.append(dict(date=d,reason='截止日后披露'));continue
  v=r.get('value')
  if v is None:excluded.append(dict(date=d,reason='缺失'));continue
  if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('估值非有效数值')
  if v<=0:excluded.append(dict(date=d,reason='非正估值，不能解释为低估'));continue
  usable.append(r)
 # Explicit latest date must match current observation, not stale carry-forward.
 current=s['observedAt'];day(current)
 if current>asof or current<start:raise ValueError('当前估值日期不在研究区间')
 valid=len(usable)>=minimum and bool(usable) and usable[-1]['date']==current
 value=None
 if valid:
  v=usable[-1]['value'];less=sum(r['value']<v for r in usable);equal=sum(r['value']==v for r in usable);value=100*(less+equal/2)/len(usable)
 basis='valuation-midrank:'+s['subject']+':'+s['metric']+':'+s['method']+':'+s['frequency']
 field=dict(value=value,observedAt=current,sourceUrl=s['sourceUrl'],basis=basis,window=start+'/'+current,unit='pct')
 return dict(code=s['code'],market=s['market'],subject=s['subject'],metric=s['metric'],method=s['method'],frequency=s['frequency'],usableSamples=len(usable),minimumSamples=minimum,excluded=excluded,valuationPercentile=field,status='可计算' if valid else '样本不足或当前观测缺失，不输出分位',formula='100 × (低于当前值的样本数 + 相等样本数/2) / 有效样本数；包含当前观测',limitations=['分位是历史相对位置，不是收益预测或估值安全判断','仅同口径窗口与频率比较；负PE不视为便宜','指数估值与ETF价格不是同一对象；不将ETF净值当PE','当前修订历史不是事前冻结数据；最低样本门槛不等于统计可靠性'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists() or a.out.with_suffix('.md').exists():raise FileExistsError('输出已存在')
 r=calculate(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float));a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');v=r['valuationPercentile']['value'];a.out.with_suffix('.md').write_text('\n'.join(['# 历史估值分位','',r['code']+'：'+r['status'],f"有效样本{r['usableSamples']}个；最低要求{r['minimumSamples']}个。",'分位：'+(f'{v:.2f}%' if v is not None else '暂不计算'),r['formula'],'',*r['limitations'],'',r['valuationPercentile']['sourceUrl']]),encoding='utf-8')
