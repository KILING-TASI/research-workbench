"""Readable contribution report; numerical checks do not verify market sources."""
import argparse,json,math,datetime
from pathlib import Path
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant,urls

def number(value):
 if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value):raise ValueError('组合贡献数值无效')
 return value

def freshness_note(review):
 if review['impactStatus']=='stale':return '本报告重现已保存的研究快照；登记输入或计算版本已变化，当前条件下需要重新计算，不能将下列数值作为更新后的结果。'
 return '本报告重现已保存的研究快照；登记的本地输入与计算版本未发现变化。未重新采集远程资料，不能据此确认数据仍为最新。'

def markdown(document):
 if not isinstance(document,dict):raise ValueError('组合贡献结果须为对象')
 freshness=None
 if document.get('type')=='research-template-result':
  from research_workflow import validate_template_result,impact
  validate_template_result(document)
  if document['template']!='portfolio-contribution-review':raise ValueError('不是组合贡献模板')
  freshness=freshness_note(impact(document))
  result=document['result'];gaps=[g['reason'] for g in document['gaps']]
 else:result=document;gaps=result.get('evidenceGaps',[])
 if not isinstance(result,dict) or result.get('type')!='portfolio-return-risk-contributions':raise ValueError('不是组合贡献结果')
 if not isinstance(gaps,list) or any(not isinstance(g,str) or not g.strip() for g in gaps):raise ValueError('资料缺口须为非空文字数组')
 if not isinstance(result.get('limitations'),list) or any(not isinstance(v,str) or not v.strip() for v in result['limitations']):raise ValueError('计算边界须为文字数组')
 if not isinstance(result.get('alignment'),dict) or not isinstance(result.get('worstDrawdown'),dict):raise ValueError('共同区间与峰谷须为对象')
 assets=result.get('assets')
 if not isinstance(assets,list) or any(not isinstance(a,dict) or not isinstance(a.get('code'),str) or not a['code'].strip() for a in assets):raise ValueError('组合资产须为含代码的对象数组')
 for a in assets:urls([a.get('sourceUrl')])
 if not assets or len({a['code'] for a in assets})!=len(assets):raise ValueError('组合资产须唯一且非空')
 volatility=number(result['annualVolatilityPct'])
 if volatility<0 or not 0<=number(result['worstDrawdown']['maximumDrawdownPct'])<=100:raise ValueError('组合波动或最大回撤范围无效')
 if any(number(a['weight'])<0 for a in assets):raise ValueError('本模型不支持负资金权重')
 checks=[('weight',1),('returnContributionPp',number(result['totalReturnPct'])),('worstDrawdownContributionPp',-number(result['worstDrawdown']['maximumDrawdownPct']))]
 if volatility>0:
  checks.extend([('volatilityContributionPp',volatility),('riskSharePct',100)])
  for a in assets:
   if abs(number(a['riskSharePct'])-number(a['volatilityContributionPp'])/volatility*100)>1e-7:raise ValueError('风险占比与波动贡献不一致')
 elif any(a['riskSharePct'] is not None or a['volatilityContributionPp'] is not None for a in assets):raise ValueError('零波动时风险占比与波动贡献须留空')
 for key,total in checks:
  if abs(sum(number(a[key]) for a in assets)-total)>1e-7:raise ValueError('组合贡献合计不一致：'+key)
 def cell(value):return str(value).replace('|','／').replace('\n',' ')
 def fmt(value):return '资料不足' if value is None else f'{number(value):.2f}'
 alignment=result['alignment'];episode=result['worstDrawdown']
 def date(value):
  if not isinstance(value,str) or datetime.date.fromisoformat(value).isoformat()!=value:raise ValueError('组合日期无效')
  return value
 start,end=date(alignment['start']),date(alignment['end']);peak,trough=date(episode['start']),date(episode['end'])
 if not start<=peak<=trough<=end:raise ValueError('组合峰谷须位于共同研究区间且顺序正确')
 if type(alignment.get('observations'))!=int or alignment['observations']<4:raise ValueError('共同观察数须至少四项')
 if episode['maximumDrawdownPct']>0 and peak==trough:raise ValueError('非零回撤不能使用同一个峰谷日期')
 lines=['# 组合收益与风险贡献','本报告为历史模拟，不构成交易指令或未来收益预测。',f"共同区间：{alignment['start']}至{alignment['end']}，共{alignment['observations']}个观察。每观察期无成本恢复目标权重，不是账户真实现金流。",f"累计模拟收益{fmt(result['totalReturnPct'])}%，年化波动{fmt(result['annualVolatilityPct'])}%，最大回撤{fmt(episode['maximumDrawdownPct'])}%。",'|资产代码|资金权重|收益贡献（百分点）|波动风险占比|共同回撤贡献（百分点）|','|---|---:|---:|---:|---:|']
 if freshness:lines.insert(2,freshness)
 if volatility>0:
  leader=max(assets,key=lambda a:a['riskSharePct']);gap=leader['riskSharePct']-leader['weight']*100
  relation='高于' if gap>0 else '低于' if gap<0 else '等于'
  conclusion='本段历史中，'+cell(leader['code'])+'承担最多波动风险；其风险占比'+relation+'资金占比。'
  evidence='论据（历史模拟）：该资产资金占比'+fmt(leader['weight']*100)+'%，波动风险占比'+fmt(leader['riskSharePct'])+'%。风险贡献来自共同区间协方差，可为负或超过100%；不能据此推断未来对冲效果。'
 else:
  conclusion='本段观测未产生组合波动，无法据此识别谁承担更多波动风险。'
  evidence='论据（历史模拟）：风险占比保持空白；零样本波动不代表资产安全，也不代表未来没有回撤。'
 lines[2:2]=['> '+conclusion,evidence]
 for a in assets:lines.append('| '+' | '.join([cell(a['code']),fmt(a['weight']*100)+'%',fmt(a['returnContributionPp']),fmt(a['riskSharePct'])+('%' if a['riskSharePct'] is not None else ''),fmt(a['worstDrawdownContributionPp'])])+' |')
 lines += [f"最大回撤对应同一组合峰谷：{episode['start']}至{episode['end']}。资金等权不代表风险等权；波动风险贡献可以为负，不能把单项资产各自最大回撤加权代替组合回撤。",'## 三项贡献怎样读','收益贡献对应完整共同区间，单位为组合收益的百分点，不能当作单品累计收益率。波动风险占比来自该区间协方差，不是未来亏损概率。共同回撤贡献只对应上述同一组合峰谷，负值表示该段拖累、正值表示该段缓冲，合计为组合回撤的负值。全区间收益贡献和回撤段贡献不互相抵消，也不构成行业或经理的因果归因。','## 资料缺口']
 lines += gaps or ['本结果未登记资料缺口；这不代表原始行情、分红或账户已核验。']
 lines += ['## 来源']+[cell(a['code'])+'：'+a['sourceUrl'] for a in assets]+['## 计算边界',*result['limitations'],'贡献合计核对只检查数值自洽，不证明来源真实性、分红完整性或交易日历完整。']
 return '\n'.join(lines)

def export(document,out):
 text=markdown(document);out=Path(out);out.mkdir(parents=True,exist_ok=False)
 (out/'组合贡献报告.md').write_text(text,encoding='utf8');(out/'组合贡献报告.html').write_text(render(text,title='组合贡献报告'),encoding='utf8')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();export(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.out_dir)
