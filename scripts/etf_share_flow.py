"""Two-date ETF share-change valuation proxy, never actual settlement cash flow."""
import argparse,json,re
from pathlib import Path
from fund_series_tools import day,num,source
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant

def calculate(s):
 if not isinstance(s,dict) or not isinstance(s.get('code'),str) or not re.fullmatch(r'[0-9]{6}',s['code']):raise ValueError('ETF请求须含六位代码')
 if any(not isinstance(s.get(k),dict) for k in ['startShares','endShares','endNav']):raise ValueError('两期份额与单位净值须为对象')
 code=s['code'];asof=day(s['asOf']);a=s['startShares'];b=s['endShares'];nav=s['endNav']
 for item in [a,b,nav]:
  if item.get('code')!=code:raise ValueError('份额/净值证券代码不一致')
  day(item['observedAt']);source(item['sourceUrl'])
  if item['observedAt']>asof:raise ValueError('数据晚于截止日')
  if not isinstance(item.get('basis'),str) or not item['basis'].strip():raise ValueError('数据缺口径')
  if item.get('publishedAt') and day(item['publishedAt'])>asof:raise ValueError('截止日后披露数据')
  if item.get('publishedAt') and item['publishedAt']<item['observedAt']:raise ValueError('披露日期早于观测日期，不能作为已发生份额或净值')
  if num(item['value'])<0:raise ValueError('份额/净值不可为负')
 if a['observedAt']>=b['observedAt'] or nav['observedAt']!=b['observedAt']:raise ValueError('需递增份额日期及同日单位净值')
 if a.get('unit')!='shares' or b.get('unit')!='shares' or nav.get('unit')!='CNY/share':raise ValueError('需份及人民币每份净值，不用成交价格代替')
 if a['basis']!=b['basis']:raise ValueError('两期份额口径不一致')
 if nav['basis'] not in ('unit-nav','provider-unit-net-worth'):raise ValueError('必须单位净值口径，不用市场价格或累计净值')
 if nav['value']<=0:raise ValueError('单位净值须正数')
 status=s.get('shareEventStatus','unknown')
 if status not in ['verified-no-share-events','assumed-no-share-events','unknown']:raise ValueError('份额事件状态无效')
 if status=='verified-no-share-events':
  evidence=s.get('shareEventEvidence')
  if not isinstance(evidence,dict):raise ValueError('份额事件核验须为证据对象')
  source(evidence.get('sourceUrl'))
  day(evidence['observedAt'])
  if evidence['observedAt']>asof:raise ValueError('份额事件核验依据晚于截止日')
  if not isinstance(evidence.get('quote'),str) or not evidence['quote'].strip():raise ValueError('份额事件核验须原文说明')
  if evidence.get('window')!=a['observedAt']+'/'+b['observedAt']:raise ValueError('份额事件核验区间不一致')
 delta=b['value']-a['value'];value=delta*nav['value'] if status!='unknown' else None
 num(delta)
 if value is not None:num(value)
 field=dict(value=value,unit='CNY',observedAt=b['observedAt'],window=a['observedAt']+'/'+b['observedAt'],sourceUrl=b['sourceUrl'],basis='share-change-times-end-nav:'+status,inputEvidence=[a,b,nav],shareEventEvidence=s.get('shareEventEvidence'))
 return dict(code=code,asOf=asof,shareChange=delta,netFlowCNY=field,shareEventStatus=status,formula='（期末份额－期初份额）×期末单位净值',status='份额变化估值代理，非真实现金流' if value is not None else '拆分/合并等份额事件未核验，不输出资金流估算',limitations=['两点测算按期末净值估值，区间较长时不能还原逐日申赎金额','不包含实物申赎结算、现金替代、费用、时点价差与盘中份额变化','份额拆分/合并可能造成非资金变化；假设无事件时须明确展示假设','不能用成交额、ETF场内价格或规模涨跌代替申赎现金流','仅历史输入区间，不代表未来资金趋势或投资建议'])

def markdown(r):
 value=r['netFlowCNY']['value'];lines=['# ETF份额变化研究','',r['code']+'：'+r['status'],r['formula'],f"份额变化{r['shareChange']:,.2f}份。",'估值代理：'+(f'{value:,.2f}元' if value is not None else '暂不计算')]
 if r['shareEventStatus']=='assumed-no-share-events':lines+=['本次假设区间没有份额拆分、合并等事件，尚未核验；金额仅在该假设下成立。']
 lines+=['']+r['limitations']+['','## 输入来源']
 for e in r['netFlowCNY']['inputEvidence']:lines.append(e['observedAt']+'：'+e['sourceUrl'])
 return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=calculate(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant));text=markdown(r);markup=render(text);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');a.out.with_suffix('.md').write_text(text,encoding='utf-8');a.out.with_suffix('.html').write_text(markup,encoding='utf-8')
