"""Explicit same-date FX translation for price-only research, not total return."""
import argparse,json,hashlib,math
from pathlib import Path
from fund_series_tools import day,num,source,NOTICE
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant

def translate(s):
 if not isinstance(s,dict) or not isinstance(s.get('asset'),dict) or not isinstance(s.get('fx'),dict):raise ValueError('价格与汇率输入须为对象')
 for item in [s['asset'],s['fx']]:
  if not isinstance(item.get('history'),list) or any(not isinstance(x,dict) for x in item['history']):raise ValueError('价格与汇率历史须为对象数组')
 asof=day(s['asOf']);asset=s['asset'];fx=s['fx'];base=asset['currency'];target=fx['targetCurrency']
 if base not in ('USD','HKD') or target!='CNY' or fx['baseCurrency']!=base or fx['unit']!='CNY-per-'+base:raise ValueError('只支持明确USD/HKD到CNY方向及单位；不自动倒数')
 source(asset['sourceUrl']);source(fx['sourceUrl']);day(fx['publishedThrough'])
 if fx['publishedThrough']>asof:raise ValueError('汇率资料披露截止日晚于研究截止日')
 if asset.get('historyBasis')!='provider-day-price-unadjusted-no-total-return-verification':raise ValueError('本入口仅支持已标明未复权的价格日线，不替换总收益口径')
 rates={};components={};last=''
 for x in fx['history']:
  d=day(x['date']);v=num(x['value'],True)
  if d<=last or d>fx['publishedThrough']:raise ValueError('汇率日期重复、乱序或超出披露覆盖')
  if 'cnyPerUSD' in x or 'hkdPerUSD' in x:
   cny=num(x['cnyPerUSD'],True);hkd=num(x['hkdPerUSD'],True)
   if base!='HKD' or not math.isclose(cny/hkd,v,rel_tol=1e-12,abs_tol=1e-12):raise ValueError('交叉汇率与组成观测不一致')
   components[d]=dict(cnyPerUSD=cny,hkdPerUSD=hkd,formula='CNY/USD ÷ HKD/USD')
  rates[d]=v;last=d
 rows=[];missing=[];last=''
 for x in asset['history']:
  d=day(x['date']);v=num(x['close'],True)
  if d<=last or d>asof:raise ValueError('资产日期重复、乱序或超过截止日')
  last=d
  if d not in rates:missing.append(d);continue
  value=v*rates[d];num(value,True)
  rows.append(dict(date=d,localClose=v,fxRate=rates[d],translatedCloseCNY=value,fxComponents=components.get(d)))
 if len(rows)<2:raise ValueError('同日价格和汇率交集不足2项；不前向填充')
 extra_sources=fx.get('sources',[])
 if not isinstance(extra_sources,list):raise ValueError('汇率来源列表无效')
 for url in extra_sources:source(url)
 def digest(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')).hexdigest()
 local=rows[-1]['localClose']/rows[0]['localClose']-1;fx_move=rows[-1]['fxRate']/rows[0]['fxRate']-1
 for value in [local,fx_move,local*100,fx_move*100,local*fx_move*100,((1+local)*(1+fx_move)-1)*100,(rows[-1]['translatedCloseCNY']/rows[0]['translatedCloseCNY']-1)*100]:num(value)
 breakdown=dict(localPricePercentagePoints=local*100,fxPercentagePoints=fx_move*100,interactionPercentagePoints=local*fx_move*100,totalPercentagePoints=((1+local)*(1+fx_move)-1)*100,formula='r_local + r_fx + r_local*r_fx',scope='交集端点价格变动的代数拆分，不是含分红绩效归因或因果贡献')
 provenance=dict(assetInputSha256=digest(asset),fxInputSha256=digest(fx),assetRetrievedAt=asset.get('retrievedAt'),fxRetrievedAt=fx.get('retrievedAt'),fxRawSha256=fx.get('rawSha256'),fxUSDInputSha256=fx.get('usdInputSha256'),historicalPublicationVerified=fx.get('historicalPublicationVerified') is True,currentVintageOnly=fx.get('currentVintageOnly') is True)
 return dict(priceChangeBreakdown=breakdown,inputProvenance=provenance,type='currency-price-translation',market=asset['market'],code=asset['code'],asOf=asof,localCurrency=base,currency='CNY',historyBasis='translated-unadjusted-price-not-total-return',history=rows,missingFXDates=missing,inputPriceObservations=len(asset['history']),matchedObservations=len(rows),localPriceChangePct=(rows[-1]['localClose']/rows[0]['localClose']-1)*100,fxChangePct=(rows[-1]['fxRate']/rows[0]['fxRate']-1)*100,translatedPriceChangePct=(rows[-1]['translatedCloseCNY']/rows[0]['translatedCloseCNY']-1)*100,sources=list(dict.fromkeys([asset['sourceUrl'],fx['sourceUrl']]+fx.get('sources',[]))),fxBasis=fx.get('basis'),formula='本币收盘价 × 同日CNY/本币汇率；累计变动=(1+本币价格变动)*(1+汇率变动)-1',portfolioTotalReturnEligible=False,limitations=['仅换算价格，不补分红拆分，不能送入要求total-return的组合模型','同日匹配不代表报价时刻一致，汇率定盘与证券收盘可能存在时差','汇率来源与方向由输入明确，资料未核验不冒称官方；缺日不填充','原币价、人民币换算价不等于真实账户净收益，未含税费与换汇摩擦','累计价格及汇率变动为本次交集区间，非全部请求日期；不是未来预测'],riskNotice=NOTICE)

def markdown(r):
 lines=['# 跨币种价格换算','',r['market']+' '+r['code']+'；'+r['localCurrency']+'换算为人民币。',f"原始价格{r['inputPriceObservations']}项，同日汇率可匹配{r['matchedObservations']}项。",f"实际交集区间{r['history'][0]['date']}至{r['history'][-1]['date']}；本币价格变动{r['localPriceChangePct']:.2f}%，汇率变动{r['fxChangePct']:.2f}%，人民币换算价格变动{r['translatedPriceChangePct']:.2f}%。",'上述是价格变动，不是含分红的持有收益。',r['formula'],'','## 缺失汇率日期']
 lines+=r['missingFXDates'] or ['本次输入价格日期均有同日汇率；不证明全市场交易日历完整。']
 b=r['priceChangeBreakdown'];lines+=['','## 换算价格变化的拆分',f"本币价格部分{b['localPricePercentagePoints']:.2f}个百分点，汇率部分{b['fxPercentagePoints']:.2f}个百分点，两者交互部分{b['interactionPercentagePoints']:.2f}个百分点；合计{b['totalPercentagePoints']:.2f}个百分点。",b['scope']+'。不能简单相加本币涨幅与汇率涨幅。']
 provenance=r.get('inputProvenance',{})
 lines+=['','## 数据版本','价格取得时间：'+str(provenance.get('assetRetrievedAt') or '未记录')+'；汇率取得时间：'+str(provenance.get('fxRetrievedAt') or '未记录')+'。']
 if provenance.get('currentVintageOnly'):lines.append('使用当前版本历史资料，不是当时逐日冻结数据；研究截止标签不证明历史首次披露时间。')
 lines+=['','## 来源']+r['sources']+['','## 口径限制']+['- '+x for x in r['limitations']]+['',r['riskNotice']]
 return '\n'.join(lines)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=translate(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant));text=markdown(r);markup=render(text);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');a.out.with_suffix('.md').write_text(text,encoding='utf-8');a.out.with_suffix('.html').write_text(markup,encoding='utf-8')
