"""Theme exposure from reconciled report stocks and explicit sourced classifications."""
import argparse,json
from pathlib import Path
from report_screen_bridge import candidate
from fund_series_tools import day,source,num,NOTICE
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant

def threshold_check(bounds,threshold):
 threshold=num(threshold)
 if not 0<=threshold<=100:raise ValueError('主题阈值须为0至100的净资产百分比')
 if not isinstance(bounds,(list,tuple)) or len(bounds)!=2:raise ValueError('主题上下界须为两个数值')
 low,high=map(num,bounds)
 if low<0 or high<low:raise ValueError('主题上下界顺序无效')
 return dict(minimumWeightPctOfNAV=threshold,passed=True if low>=threshold else False if high<threshold else None,reason='已确认股票主题下界满足阈值' if low>=threshold else '股票主题上界仍低于阈值' if high<threshold else '未分类股票可能改变结果，无法判定')

def calculate(s):
 if not isinstance(s,dict) or not isinstance(s.get('report'),dict) or not isinstance(s.get('classifications',[]),list):raise ValueError('主题输入、报告及分类列表结构无效')
 asof=day(s['asOf']);theme=s['theme'];version=s['classificationVersion']
 if not isinstance(theme,str) or not theme.strip() or not isinstance(version,str) or not version.strip():raise ValueError('主题及分类版本须明确')
 report=s['report'];c=candidate(report,asof);h=c['holdings'];mapping={}
 for item in s.get('classifications',[]):
  if not isinstance(item,dict):raise ValueError('证券分类须为对象')
  if any(not isinstance(item.get(k),str) or not item[k].strip() for k in ['market','code','quote']):raise ValueError('分类证券身份及原文引用须为非空文本')
  locator=item.get('locator')
  if not ((isinstance(locator,str) and locator.strip()) or (isinstance(locator,dict) and locator)):raise ValueError('分类原文位置须为文本或结构化对象')
  key=(item['market'],item['code'])
  if key in mapping:raise ValueError('同证券分类重复，需解释冲突')
  source(item['sourceUrl']);day(item['publishedAt']);day(item['effectiveFrom'])
  if item['publishedAt']>asof:raise ValueError('分类资料晚于研究截止日')
  if item.get('effectiveTo'):day(item['effectiveTo'])
  if item.get('effectiveTo') and item['effectiveTo']<item['effectiveFrom']:raise ValueError('分类有效期倒置')
  if item.get('classificationVersion')!=version or not item.get('quote') or not item.get('locator'):raise ValueError('分类版本或原文依据缺失')
  if not isinstance(item.get('themes'),list) or any(not isinstance(t,str) or not t.strip() for t in item['themes']):raise ValueError('主题标签须明确列表；空列表表示此版本明确未归入主题')
  mapping[key]=item
 rows=[];matched=known=unknown=0
 for stock in h['value']:
  item=mapping.get((stock['market'],stock['code']));valid=item and item['effectiveFrom']<=report['reportDate'] and (not item.get('effectiveTo') or report['reportDate']<=item['effectiveTo'])
  status='未提供该证券分类';belongs=None
  if item and not valid:status='分类在报告日尚未生效' if item['effectiveFrom']>report['reportDate'] else '分类在报告日前已失效'
  if valid:
   belongs=theme in item['themes'];known+=stock['weightPct'];status='归入本次主题' if belongs else '本分类版本未归入主题'
   if belongs:matched+=stock['weightPct']
  else:unknown+=stock['weightPct']
  rows.append(dict(stock,belongsToTheme=belongs,classificationStatus=status,classificationEvidence=item if valid else None,unusedClassificationEvidence=item if item and not valid else None))
 equity=sum(x['weightPct'] for x in h['value'])
 return dict(thresholdCheck=threshold_check([matched,matched+unknown],s['minimumWeightPctOfNAV']) if 'minimumWeightPctOfNAV' in s else None,type='holding-theme-exposure',code=c['code'],name=c['name'],asOf=asof,reportDate=report['reportDate'],theme=theme,classificationVersion=version,matchedWeightPctOfNAV=matched,classifiedWeightPctOfNAV=known,unclassifiedWeightPctOfNAV=unknown,equityWeightPctOfNAV=equity,classificationCoveragePctOfEquity=known/equity*100 if equity else None,stockThemeWeightBoundsPctOfNAV=[matched,matched+unknown],rows=rows,reportSource=h['sourceUrl'],reportSha256=h['sourceSha256'],limitations=['仅报告期末完整股票表；不含债券、衍生品及未穿透资产','区间是未知股票可能归属的确定性上下界，不是统计置信区间','分类覆盖率不是结论置信度；主题分类需要原文复核，输入来源不等于自动核验','主题可能重叠，多个主题占比不能直接相加；没有主题暴露不代表没有相关经济风险','截止日取得的分类可能是事后资料，本结果不证明事前可得性'],riskNotice=NOTICE)

def markdown(r):
 def cell(v):return str(v).replace('|','／').replace('\n',' ')
 lo,hi=r['stockThemeWeightBoundsPctOfNAV'];coverage=r['classificationCoveragePctOfEquity']
 lines=['# 持仓主题暴露研究','',r['code']+'；报告日'+r['reportDate']+'；主题：'+r['theme']+'。',f"已确认归入该主题的股票占基金净资产{lo:.2f}%；未分类股票占{r['unclassifiedWeightPctOfNAV']:.2f}%。",f'仅对股票部分，主题占净资产的可能范围为{lo:.2f}%至{hi:.2f}%；这不是置信区间或未来预测。','分类覆盖已披露股票的比例：'+('不适用' if coverage is None else f'{coverage:.2f}%')+'。覆盖率不是置信度。','分类版本：'+cell(r['classificationVersion']),'','| 股票 | 市场与代码 | 占净资产 | 分类结果 |','| --- | --- | ---: | --- |']
 for x in r['rows']:lines.append('| '+cell(x['name'])+' | '+cell(x['market']+' '+x['code'])+' | '+f"{x['weightPct']:.4f}%"+' | '+x['classificationStatus']+' |')
 if r.get('thresholdCheck'):
  check=r['thresholdCheck'];lines+=['','## 股票主题阈值核对',str(check['minimumWeightPctOfNAV'])+'%净资产阈值：'+('满足' if check['passed'] is True else '不满足' if check['passed'] is False else '资料不足')+'。'+check['reason']+'。仅针对已披露股票，不代表基金全部资产的经济暴露。']
 lines+=['','## 来源','[股票报告]('+r['reportSource']+')']
 for x in r['rows']:
  ev=x['classificationEvidence'] or x.get('unusedClassificationEvidence')
  if ev:lines.append('- '+x['code']+'：[分类来源]('+ev['sourceUrl']+')；披露日期'+ev['publishedAt']+'；有效期'+ev['effectiveFrom']+'至'+(ev.get('effectiveTo') or '未提供截止日')+'；'+x['classificationStatus']+'；'+cell(ev['locator'])+'；依据：'+cell(ev['quote']))
 lines+=['','## 研究边界']+['- '+v for v in r['limitations']]+['',r['riskNotice']]
 return '\n'.join(lines)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=calculate(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant));text=markdown(r);html=render(text);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');a.out.with_suffix('.md').write_text(text,encoding='utf-8');a.out.with_suffix('.html').write_text(html,encoding='utf-8')
