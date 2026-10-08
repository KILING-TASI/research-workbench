"""On-demand macro/asset snapshot with explicit periods and price-return boundaries."""
import argparse,csv,datetime as dt,hashlib,io,json,math
from pathlib import Path
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request,urlopen
from cross_market_history import collect as price_collect
from research_brief_html import render
from collection_validation import day as validated_day,unique_pairs,reject_constant,finite_json_float
FX_CONVENTIONS={'DEXUSEU':dict(baseCurrency='EUR',quoteCurrency='USD'),'DEXCHUS':dict(baseCurrency='USD',quoteCurrency='CNY')}
SERIES={
 'DEXUSEU':dict(name='欧元兑美元（每欧元美元数）',unit='USD-per-EUR',frequency='daily-business',role='macro'),
 'DEXCHUS':dict(name='美元兑人民币（每美元人民币数）',unit='CNY-per-USD',frequency='daily-business',role='macro'),
 'INDPRO':dict(name='美国工业生产指数（季调）',unit='index-2017-100',frequency='monthly',role='macro'),
 'UNRATE':dict(name='美国失业率（季调）',unit='percent',frequency='monthly',role='macro'),
 'CPIAUCSL':dict(name='美国CPI（季调指数）',unit='index-1982-84-100',frequency='monthly',role='macro'),
 'DGS10':dict(name='美国10年国债收益率',unit='percent',frequency='daily-business',role='macro'),
 'DFF':dict(name='有效联邦基金利率',unit='percent',frequency='daily-7day',role='macro'),
 'WCESTUS1':dict(name='美国原油期末库存（不含SPR）',unit='thousand-barrels',frequency='weekly',role='macro'),
 'DCOILWTICO':dict(name='WTI库欣原油现货价格（未季调）',unit='USD-per-barrel',frequency='daily-business',role='macro'),
 'PCOPPUSDM':dict(name='全球铜基准价格（月均，未季调）',unit='USD-per-metric-ton',frequency='monthly',role='macro'),
 'CBBTCUSD':dict(name='Coinbase比特币美元价格',unit='USD',frequency='daily-7day',role='asset')}
SEASONALITY={'INDPRO':'seasonally-adjusted','UNRATE':'seasonally-adjusted','CPIAUCSL':'seasonally-adjusted','DCOILWTICO':'not-seasonally-adjusted','PCOPPUSDM':'not-seasonally-adjusted'}
ASSET_SERIES={id:dict(unit='USD',role='asset',frequency='daily-business') for id in ['QQQ','TLT','GLD','IWM']}

def validate_series_contract(series,check_frequency=False):
 contracts=[]
 for s in series:
  known=SERIES.get(s['id']) or ASSET_SERIES.get(s['id'])
  expected_seasonality=SEASONALITY.get(s['id'])
  if expected_seasonality and s.get('seasonality') is not None and s['seasonality']!=expected_seasonality:raise ValueError(s['id']+'季调声明与已支持序列定义冲突')
  if known:
   fields=['unit','role']+(['frequency'] if check_frequency else [])
   for field in fields:
    if s.get(field)!=known[field]:raise ValueError(s['id']+'指标'+field+'与已支持定义不一致；不能猜测或自动换算')
  if s.get('role')=='asset' and (not isinstance(s.get('unit'),str) or not s['unit'].strip()):raise ValueError('资产价格需明确币种')
  contracts.append(dict(id=s['id'],seasonality=expected_seasonality or s.get('seasonality','unspecified'),unit=s.get('unit'),role=s.get('role'),frequency=s.get('frequency'),status='supported-definition-checked' if known else 'input-declared-definition-not-externally-verified'))
 return contracts

def fetch(url):
 with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=25) as r:
  raw=r.read(8*1024*1024+1)
  if len(raw)>8*1024*1024:raise ValueError('响应超过8MB')
  return raw

def parse_csv(raw,id,start,end):
 rows=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
 if rows.fieldnames!=['observation_date',id]:raise ValueError('FRED表头或序列标识不匹配')
 points=[];missing=[];seen=[]
 for row in rows:
  day=validated_day(row['observation_date']).isoformat();seen.append(day)
  if not start<=day<=end:continue
  if row[id] in ['', '.']:missing.append(day);continue
  value=float(row[id])
  if not math.isfinite(value) or (id in ['CPIAUCSL','INDPRO','CBBTCUSD','PCOPPUSDM'] and value<=0):raise ValueError('指标值无效')
  points.append(dict(date=day,value=value,publishedAt=None))
 if seen!=sorted(set(seen)):raise ValueError('日期重复或乱序')
 return points,missing

def parse_chart(raw,id,start,end):
 from zoneinfo import ZoneInfo
 payload=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float);chart=payload.get('chart',{})
 if chart.get('error') or not isinstance(chart.get('result'),list) or len(chart['result'])!=1 or not isinstance(chart['result'][0],dict):raise ValueError('备用价格来源须返回唯一证券结果')
 node=chart['result'][0];meta=node.get('meta',{})
 if meta.get('symbol')!=id or meta.get('currency')!='USD' or meta.get('instrumentType')!='ETF':raise ValueError('备用来源证券身份不匹配')
 timezone=meta.get('exchangeTimezoneName')
 if not timezone:raise ValueError('备用来源交易所时区缺失')
 stamps=node.get('timestamp',[]);closes=node.get('indicators',{}).get('quote',[{}])[0].get('close',[])
 if len(stamps)!=len(closes):raise ValueError('备用价格日期和值数量不一致')
 points=[];missing=[];seen=[]
 for stamp,value in zip(stamps,closes):
  if isinstance(stamp,bool) or not isinstance(stamp,(int,float)) or not math.isfinite(stamp):raise ValueError('备用价格时间戳无效')
  day=dt.datetime.fromtimestamp(stamp,ZoneInfo(timezone)).date().isoformat();seen.append(day)
  if not start<=day<=end:continue
  if value is None:missing.append(day);continue
  if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:raise ValueError('备用价格值无效')
  points.append(dict(date=day,value=value,publishedAt=None))
 if seen!=sorted(set(seen)):raise ValueError('备用价格日期重复或乱序')
 return points,missing,timezone

def collect(spec,out,fetch_fn=fetch,asset_fn=price_collect):
 start=validated_day(spec['start']);end=validated_day(spec['asOf'])
 if start>=end:raise ValueError('请求窗口无效')
 selected=spec.get('seriesIds',['CPIAUCSL','DGS10','DFF','CBBTCUSD'])
 if not isinstance(selected,list) or not selected or len(selected)!=len(set(selected)) or any(i not in SERIES for i in selected):raise ValueError('指标列表为空、重复或不在支持范围')
 asset_ids=spec.get('assetIds',['QQQ','TLT'])
 if not isinstance(asset_ids,list) or len(asset_ids)!=len(set(asset_ids)) or any(i not in ASSET_SERIES for i in asset_ids):raise ValueError('资产列表重复或不在支持范围')
 out=Path(out);out.mkdir(parents=True,exist_ok=False);series=[]
 for id in selected:
  meta=SERIES[id]
  url='https://fred.stlouisfed.org/graph/fredgraph.csv?'+urlencode(dict(id=id,cosd=start.isoformat(),coed=end.isoformat()))
  if id=='WCESTUS1':
   from eia_inventory_source import URL
   url=URL
  s=dict(id=id,**meta,sourceUrl=url if id=='WCESTUS1' else 'https://fred.stlouisfed.org/series/'+id,downloadUrl=url,points=[],status='failed',retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat(),publicationDatesVerified=False,vintage='current-revised-history',clock='source notes: 17:00 PST; not synchronous with ETF close' if meta['role']=='asset' else 'observation-period')
  try:
   raw=fetch_fn(url);s['rawFile']=id+('.html' if id=='WCESTUS1' else '.csv');(out/s['rawFile']).write_bytes(raw);s['sha256']=hashlib.sha256(raw).hexdigest()
   if id=='WCESTUS1':
    from eia_inventory_source import parse
    s['points'],s['missingDates']=parse(raw,start.isoformat(),end.isoformat())
   else:s['points'],s['missingDates']=parse_csv(raw,id,start.isoformat(),end.isoformat())
   s['status']='available' if s['points'] else 'empty'
  except Exception as exc:s['error']=str(exc)
  series.append(s)
 for id in asset_ids:
  s=dict(id=id,name=id,role='asset',unit='USD',frequency='daily-business',clock='provider-day; exact-close-time-unverified',points=[],publicationDatesVerified=False,vintage='current-provider-history',status='failed')
  try:
   r,attempts=asset_fn('US',id,start.isoformat(),end.isoformat());(out/(id+'-raw.json')).write_text(json.dumps(attempts,ensure_ascii=False,indent=2),encoding='utf8');s.update(sourceUrl=r['sourceUrl'],retrievedAt=r['retrievedAt'],sha256=r.get('sha256'),points=[dict(date=p['date'],value=p['close'],publishedAt=None) for p in r['history']],status='available' if r['history'] else 'empty',error=r.get('reason'),priceBasis=r.get('historyBasis'),calendarVerified=False)
   matches=[a for a in attempts if a.get('sha256')==s.get('sha256') and a.get('rawText')]
   if matches:
    primary_raw=matches[-1]['rawText'].encode('utf-8')
    if hashlib.sha256(primary_raw).hexdigest()!=s['sha256']:raise ValueError('主要行情原始响应编码与哈希不一致')
    s['rawFile']=id+'-source.json';(out/s['rawFile']).write_bytes(primary_raw)
  except Exception as exc:s['error']=str(exc)
  if len(s['points'])<2:
   url='https://query1.finance.yahoo.com/v8/finance/chart/'+id+'?'+urlencode(dict(period1=int(dt.datetime.combine(start,dt.time(),dt.timezone.utc).timestamp()),period2=int(dt.datetime.combine(end+dt.timedelta(days=1),dt.time(),dt.timezone.utc).timestamp()),interval='1d'))
   s['initialSource']=dict(sourceUrl=s.get('sourceUrl'),sha256=s.get('sha256'),observations=len(s['points']),error=s.get('error'))
   try:
    raw=fetch_fn(url);(out/(id+'-fallback.json')).write_bytes(raw);points,missing,timezone=parse_chart(raw,id,start.isoformat(),end.isoformat())
    if len(points)>len(s['points']):s.update(points=points,missingDates=missing,status='available',rawFile=id+'-fallback.json',sourceUrl=url,sha256=hashlib.sha256(raw).hexdigest(),clock=timezone+' provider daily close; exact-close-confirmation-unverified',priceBasis='unadjusted-close-price; dividends-and-splits-not-verified',error=None,retrievedAt=dt.datetime.now(dt.timezone.utc).isoformat())
   except Exception as exc:s['fallbackError']=str(exc)
  series.append(s)
 result=dict(start=start.isoformat(),asOf=end.isoformat(),series=series,limitations=['当前修订历史不证明研究截止日当时已可取得；不用于事前事件回测','观测所属期与发布日期不同，CSV不含逐点发布日期，未核验则保留空白','所选ETF为未复权价格，初始来源短历史时尝试备用日线并留存两次来源；BTC与ETF每日定价时刻不同，日历日期对齐不等于同步行情','CPI为季调指数；DFF为有效成交利率，不是联邦基金目标区间或政策声明','库存为美国期末原油、不含SPR，单位千桶；统计期末不是发布日期，当前网页历史不证明当时可知','原油为WTI库欣现货美元每桶，铜为美元每公吨月均基准价；不是期货、ETF净值或可交易总收益，缺少库存供需证据时不判断商品周期'])
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result

def observation_windows(s):
 points=s['points'];windows=[]
 for intervals in [1,5,20]:
  row=dict(observationIntervals=intervals,status='insufficient-observations',start=None,end=None,value=None,unit=None)
  if len(points)>intervals:
   first,last=points[-intervals-1],points[-1];row.update(start=first['date'],end=last['date'],calendarDays=(dt.date.fromisoformat(last['date'])-dt.date.fromisoformat(first['date'])).days,inputs=[first['value'],last['value']],status='observed-interval-change')
   if s['unit']=='percent':
    rate=s['id']!='UNRATE';row.update(value=(last['value']-first['value'])*(100 if rate else 1),unit='bp' if rate else 'percentage-point',formula='(endPercent-startPercent)*100' if rate else 'endPercent-startPercent')
   elif first['value']>0:row.update(value=last['value']/first['value']-1,unit='relative-change',formula='endValue/startValue-1')
   else:row.update(status='nonpositive-base',value=None,unit=None)
  windows.append(row)
 return windows

def changes(s):
 if s['id'] in SEASONALITY and s.get('seasonality') is not None and s['seasonality']!=SEASONALITY[s['id']]:raise ValueError('季调声明与序列定义冲突')
 ps=s['points'];result=dict(monthOverMonth=None,seasonality=SEASONALITY.get(s['id'],s.get('seasonality','unspecified')),recentObservationWindows=observation_windows(s),id=s['id'],name=s.get('name',s['id']),unit=s['unit'],frequency=s['frequency'],status=s['status'],latest=None,previous=None,change=None,cpiYoY=None,activityYoY=None)
 if not ps:return result
 result['latest']=ps[-1];result['previous']=ps[-2] if len(ps)>1 else None
 if s['frequency']=='monthly':
  months=[p['date'][:7] for p in ps]
  if len(months)!=len(set(months)):raise ValueError('月度同月重复观测，不能选择环比基数')
  latest=dt.date.fromisoformat(ps[-1]['date']);prior=(latest.replace(day=1)-dt.timedelta(days=1)).strftime('%Y-%m')
  matches=[p for p in ps if p['date'][:7]==prior]
  if matches:
   a,b=matches[0],ps[-1];rate=s['unit']=='percent'
   if not rate and a['value']<=0:raise ValueError('环比基数必须为正')
   result['monthOverMonth']=dict(start=a['date'],end=b['date'],value=b['value']-a['value'] if rate else b['value']/a['value']-1,unit='percentage-point' if rate else 'relative-change',formula='endPercent-priorMonthPercent' if rate else 'endValue/priorMonthValue-1',inputs=[a['value'],b['value']],basis='exact-prior-calendar-month',seasonality=result['seasonality'])
 if s['unit']=='percent' and len(ps)>1:
  scale=1 if s['id']=='UNRATE' else 100
  result['change']=dict(value=(ps[-1]['value']-ps[-2]['value'])*scale,unit='percentage-point' if s['id']=='UNRATE' else 'bp',start=ps[-2]['date'],end=ps[-1]['date'],inputs=[ps[-2]['value'],ps[-1]['value']],formula='endPercent-startPercent' if s['id']=='UNRATE' else '(endPercent-startPercent)*100')
 if s['unit']=='thousand-barrels' and len(ps)>1:result['change']=dict(value=ps[-1]['value']-ps[-2]['value'],unit='thousand-barrels',start=ps[-2]['date'],end=ps[-1]['date'],inputs=[ps[-2]['value'],ps[-1]['value']],formula='endStock-startStock')
 if s['id'] in FX_CONVENTIONS:
  convention=FX_CONVENTIONS[s['id']]
  result['exchangeRateBasis']=dict(convention,quotation='quote-currency-units-per-one-base-currency',directChange=None,inverseChange=None,limitation='纽约中午买入价观测，不是即时可成交汇率；不含点差、费用或跨币种资产总收益')
  if len(ps)>1:
   first,last=ps[-2],ps[-1]
   if first['value']<=0 or last['value']<=0:raise ValueError('汇率观测必须为正')
   result['exchangeRateBasis'].update(directChange=last['value']/first['value']-1,inverseChange=first['value']/last['value']-1,start=first['date'],end=last['date'],inputs=[first['value'],last['value']],directFormula='endRate/startRate-1',inverseFormula='startRate/endRate-1')
 if s['id'] in ['CPIAUCSL','INDPRO']:
  latest=dt.date.fromisoformat(ps[-1]['date']);prior=f'{latest.year-1:04d}-{latest.month:02d}'
  matches=[p for p in ps if p['date'][:7]==prior]
  if len(matches)==1:result['cpiYoY' if s['id']=='CPIAUCSL' else 'activityYoY']=dict(value=ps[-1]['value']/matches[0]['value']-1,start=matches[0]['date'],end=ps[-1]['date'],basis='seasonally-adjusted-index-derived-yoy',inputs=[matches[0]['value'],ps[-1]['value']],formula='endIndex/priorYearSameMonthIndex-1')
 return result

def transmission_hypotheses(rows,series,bindings=None):
 if not isinstance(rows,list):raise ValueError('传导假设须为列表')
 available={s['id']:s for s in series if s['role']=='macro' and s['points']}
 available_assets={s['id']:s for s in series if s['role']=='asset' and s['points']}
 result=[]
 binding_by_id={b['id']:b['status'] for b in (bindings or [])}
 for row in rows:
  if not isinstance(row,dict):raise ValueError('传导假设每项须为对象')
  ids=row.get('factorIds',[])
  if not isinstance(ids,list) or any(not isinstance(i,str) for i in ids) or not ids or len(ids)!=len(set(ids)) or any(i not in available for i in ids):raise ValueError('传导假设必须引用已取得的宏观序列')
  asset_ids=row.get('assetIds',[])
  if not isinstance(asset_ids,list) or any(not isinstance(i,str) for i in asset_ids) or len(asset_ids)!=len(set(asset_ids)) or any(i not in available_assets for i in asset_ids):raise ValueError('传导假设资产必须引用本次已取得的资产序列，不替代缺项')
  asset_observations=[dict(id=i,latest=available_assets[i]['points'][-1],unit=available_assets[i]['unit'],clock=available_assets[i].get('clock','unconfirmed'),priceBasis=available_assets[i].get('priceBasis','provider-price-not-total-return-verified'),sourceSha256=available_assets[i].get('sha256'),sourceBindingStatus=binding_by_id.get(i,'raw-source-not-bound'),publicationDatesVerified=available_assets[i].get('publicationDatesVerified',False)) for i in asset_ids]
  mechanism=row.get('mechanism')
  if not isinstance(mechanism,str) or not mechanism.strip():raise ValueError('传导机制须明确说明')
  for key in ['conditions','counterEvidence']:
   if not isinstance(row.get(key),list) or not row[key] or any(not isinstance(x,str) or not x.strip() for x in row[key]):raise ValueError('传导假设须列验证条件和反证问题')
  result.append(dict(mechanism=mechanism,factorIds=ids,assetIds=asset_ids,assetObservations=asset_observations,observations=[dict(id=i,latest=available[i]['points'][-1],sourceSha256=available[i].get('sha256'),sourceBindingStatus=binding_by_id.get(i,'raw-source-not-bound'),publicationDatesVerified=available[i].get('publicationDatesVerified',False),vintage=available[i].get('vintage','unconfirmed')) for i in ids],conditions=row['conditions'],counterEvidence=row['counterEvidence'],status='research-hypothesis-not-causal-verification'))
 return result

def monthly_alignment(series):
 monthly=[s for s in series if s['role']=='macro' and s['frequency']=='monthly']
 if len(monthly)<2:return dict(status='not-applicable',month=None,observations=[],history=[])
 maps=[]
 for s in monthly:
  keys=[p['date'][:7] for p in s['points']]
  if len(keys)!=len(set(keys)):raise ValueError('月度序列同月存在多个观测，需核对频率')
  maps.append({p['date'][:7]:p for p in s['points']})
 common=set.intersection(*[set(m) for m in maps])
 union=set.union(*[set(m) for m in maps])
 if not union:return dict(status='no-common-month',month=None,observations=[],history=[],monthGaps=[],observedRange=None,isContinuous=False,missingSeries=[s['id'] for s in monthly])
 first=min(union);last=max(union)
 first_n=int(first[:4])*12+int(first[5:])-1;last_n=int(last[:4])*12+int(last[5:])-1
 expected=[f'{n//12:04d}-{n%12+1:02d}' for n in range(first_n,last_n+1)]
 gaps=[dict(month=period,missingSeries=[s['id'] for s,m in zip(monthly,maps) if period not in m]) for period in expected if period not in common]
 if not common:return dict(status='no-common-month',month=None,observations=[],history=[],monthGaps=gaps,observedRange=dict(start=first,end=last),isContinuous=False,missingSeries=[s['id'] for s in monthly if not s['points']])
 month=max(common)
 return dict(monthGaps=gaps,observedRange=dict(start=first,end=last),isContinuous=not gaps,status='common-observation-month-not-publication-aligned',month=month,observations=[dict(id=s['id'],point=m[month],latestMonth=s['points'][-1]['date'][:7],unit=s['unit'],sourceSha256=s.get('sha256')) for s,m in zip(monthly,maps)],history=[dict(month=period,observations=[dict(id=s['id'],point=m[period],unit=s['unit'],sourceSha256=s.get('sha256')) for s,m in zip(monthly,maps)]) for period in sorted(common)[-12:]])

def daily_rate_asset_alignment(series):
 validate_series_contract(series)
 rates=[s for s in series if s['role']=='macro' and s['id'] in ['DGS10','DFF']]
 assets=[s for s in series if s['role']=='asset']
 if not rates or not assets:return []
 selected=rates+assets
 common=sorted(set.intersection(*[{p['date'] for p in s['points']} for s in selected]))
 rows=[]
 for count in [1,5,20]:
  row=dict(observationIntervals=count,status='insufficient-common-observations',start=None,end=None,changes=[],includedSeries=[s['id'] for s in selected])
  if len(common)>count:
   start,end=common[-count-1],common[-1];row.update(status='same-date-observations-not-causal',start=start,end=end,calendarDays=(dt.date.fromisoformat(end)-dt.date.fromisoformat(start)).days)
   window_dates=common[-count-1:];maximum_gap=max((dt.date.fromisoformat(b)-dt.date.fromisoformat(a)).days for a,b in zip(window_dates,window_dates[1:]))
   row.update(maximumCalendarGapDays=maximum_gap,continuityStatus='sparse-observations-not-daily-window' if maximum_gap>7 else 'observed-spacing-within-rule-not-calendar-verified',spacingRuleDays=7)
   for item in selected:
    points={p['date']:p['value'] for p in item['points']};a,b=points[start],points[end]
    rate=item in rates
    row['changes'].append(dict(id=item['id'],value=(b-a)*100 if rate else b/a-1,unit='bp' if rate else 'price-return',inputStart=a,inputEnd=b,formula='(end-start)*100' if rate else 'endPrice/startPrice-1',sourceSha256=item.get('sha256')))
  rows.append(row)
 return rows

def individual_asset_windows(asset,asof):
 points={p['date']:p['value'] for p in asset['points']};dates=sorted(points);rows=[]
 for days in [30,90,180]:
  row=dict(windowDays=days,status='insufficient',start=None,end=None,value=None)
  if dates:
   end=dt.date.fromisoformat(dates[-1]);target=end-dt.timedelta(days=days);candidates=[d for d in dates if dt.date.fromisoformat(d)<=target]
   if candidates and (target-dt.date.fromisoformat(candidates[-1])).days<=7:
    start=candidates[-1];row.update(status='individual-price-only-not-common-window',start=start,end=dates[-1],actualDays=(end-dt.date.fromisoformat(start)).days,endLagDays=(asof-end).days,value=points[dates[-1]]/points[start]-1,inputStart=points[start],inputEnd=points[dates[-1]],formula='endPrice/startPrice-1')
  rows.append(row)
 return dict(id=asset['id'],windows=rows,scope='单项有效日期，不与其他资产自动组成同期比较')

def report_summary(snapshots,alignment):
 lines=[]
 for s in snapshots:
  m=s.get('monthOverMonth')
  if not m:
   delta=s.get('change')
   if s.get('frequency') in ('daily','daily-business','daily-7day') and delta and delta.get('unit')=='bp':
    value=delta['value'];direction='上升' if value>0 else '下降' if value<0 else '持平'
    amount=f"{abs(value):.2f}bp" if value else ''
    lines.append(s['name']+'在'+delta['end']+'较上一有效观测（'+delta['start']+'）'+direction+amount+'；这是观测变化，不是政策目标或未来走势判断。')
   continue
  change=m['value'];direction='上升' if change>0 else '下降' if change<0 else '持平'
  amount=f"{abs(change):.2f}个百分点" if m['unit']=='percentage-point' else f"{abs(change):.2%}"
  lines.append(s['name']+'在'+m['end'][:7]+'较上月'+direction+(amount if change else '')+'。')
 if not lines:lines.append('本次缺少可用的严格月度对比，不能据此给出月度改善或恶化结论。')
 if alignment.get('month'):lines.append('共同所属月为'+alignment['month']+'；各项最新值月份可能不同，应分别阅读，不能拼成同一月份的经济状态。')
 lines.append('这些是所选指标的历史观察，不足以单独判定经济周期、政策转向或资产未来表现；逐点发布日期未核验。')
 return lines

def applicable_limitations(limitations,series):
 ids={s['id'] for s in series};has_assets=any(s['role']=='asset' for s in series)
 result=[]
 for text in limitations:
  if ('所选ETF' in text or '资产对照仅用共同日期' in text) and not has_assets:continue
  if 'CPI为季调指数；DFF' in text:
   if 'CPIAUCSL' in ids:result.append('CPI为季调指数，推算同比不等于通常公布的未季调同比。')
   if 'DFF' in ids:result.append('DFF为有效成交利率，不是联邦基金目标区间或政策声明。')
   continue
  if '库存为美国期末原油' in text and 'WCESTUS1' not in ids:continue
  if '原油为WTI' in text and not ids.intersection({'DCOILWTICO','PCOPPUSDM'}):continue
  result.append(text)
 return result

def build(spec,out):
 archive=Path(spec['archive']);raw=archive.read_bytes();data=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float);asof=validated_day(data['asOf']);validated_day(data['start']);assets=[s for s in data['series'] if s['role']=='asset'];ids=[s['id'] for s in data['series']]
 if len(ids)!=len(set(ids)):raise ValueError('序列ID重复')
 contracts=validate_series_contract(data['series'],check_frequency=True)
 bindings=[]
 for s in data['series']:
  candidate=s.get('rawFile')
  if not candidate:
   for name in [s['id']+'.csv',s['id']+'-fallback.json']:
    if (archive.parent/name).is_file():candidate=name;break
  status='raw-source-not-bound'
  if candidate:
   path=(archive.parent/candidate).resolve()
   if path.parent!=archive.parent.resolve():raise ValueError('原始来源文件必须在观测归档目录')
   if not path.is_file() or not s.get('sha256') or hashlib.sha256(path.read_bytes()).hexdigest()!=s['sha256']:raise ValueError('原始观测来源文件缺失或哈希变化：'+s['id'])
   source_raw=path.read_bytes()
   if candidate.endswith('.csv'):
    parsed,_=parse_csv(source_raw,s['id'],data['start'],data['asOf'])
   elif candidate.endswith('.html') and s['id']=='WCESTUS1':
    from eia_inventory_source import parse
    parsed,_=parse(source_raw,data['start'],data['asOf'])
   elif candidate.endswith('-fallback.json'):
    parsed,_,_=parse_chart(source_raw,s['id'],data['start'],data['asOf'])
   elif candidate.endswith('-source.json'):
    from cross_market_history import parse as parse_primary
    url=urlsplit(s['sourceUrl']);params=parse_qs(url.query).get('param',[])
    if url.hostname!='web.ifzq.gtimg.cn' or url.path!='/appstock/app/fqkline/get' or len(params)!=1:raise ValueError('主要行情请求来源或参数未确认')
    fields=params[0].split(',')
    if len(fields)<4 or fields[1]!='day' or fields[2:4]!=[data['start'],data['asOf']]:raise ValueError('主要行情请求窗口不一致')
    primary=parse_primary(json.loads(source_raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float),'US',s['id'],data['start'],data['asOf'],fields[0])
    parsed=[dict(date=p['date'],value=p['close']) for p in primary['history']]
   else:parsed=None
   if parsed is not None and [(p['date'],p['value']) for p in parsed]!=[(p['date'],p['value']) for p in s['points']]:raise ValueError('观测档案数值与原始响应不一致：'+s['id'])
   status='raw-file-and-observations-matched' if parsed is not None else 'raw-file-hash-matched'
  bindings.append(dict(id=s['id'],rawFile=candidate,status=status))

 for s in data['series']:
  dates=[p['date'] for p in s['points']]
  if dates!=sorted(set(dates)):raise ValueError('序列日期乱序或重复')
  if any(not dt.date.fromisoformat(data['start'])<=validated_day(p['date'])<=asof or not isinstance(p['value'],(int,float)) or isinstance(p['value'],bool) or not math.isfinite(p['value']) for p in s['points']):raise ValueError('序列日期或值无效')
  if (s['role']=='asset' or s['id'] in ['CPIAUCSL','INDPRO','PCOPPUSDM',*FX_CONVENTIONS]) and any(p['value']<=0 for p in s['points']):raise ValueError('价格或指数必须为正')
 if len({s['unit'] for s in assets if s['points']})>1:raise ValueError('资产价格币种不一致，需另行汇兑')
 snapshots=[changes(s) for s in data['series'] if s['role']=='macro'];common=set.intersection(*[set(p['date'] for p in s['points']) for s in assets]) if assets else set();dates=sorted(common);windows=[]
 for days in ([30,90,180] if assets else []):
  row=dict(windowDays=days,status='insufficient',start=None,end=None,returns=[],missingAssets=[s['id'] for s in assets if not s['points']])
  if dates:
   end=dt.date.fromisoformat(dates[-1]);target=end-dt.timedelta(days=days);candidates=[d for d in dates if dt.date.fromisoformat(d)<=target]
   if candidates and (target-dt.date.fromisoformat(candidates[-1])).days<=7:
    start=candidates[-1];row.update(status='date-aligned-price-only',start=start,end=dates[-1],actualDays=(end-dt.date.fromisoformat(start)).days,endLagDays=(asof-end).days)
    for s in assets:
     ps={p['date']:p['value'] for p in s['points']};row['returns'].append(dict(id=s['id'],value=ps[dates[-1]]/ps[start]-1,inputStart=ps[start],inputEnd=ps[dates[-1]],formula='endPrice/startPrice-1',sourceSha256=s.get('sha256'),sourceUrl=s.get('sourceUrl'),basis=s.get('priceBasis') or 'provider-price; no-total-return-verification',clock=s['clock']))
  windows.append(row)
 result=dict(asOf=data['asOf'],archiveSha256=hashlib.sha256(raw).hexdigest(),codeSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),macro=snapshots,seriesContracts=contracts,sourceBindings=bindings,assetWindows=windows,missingSeries=[s['id'] for s in data['series'] if not s['points']],sources=[{k:s.get(k) for k in ['id','sourceUrl','sha256','retrievedAt','vintage','publicationDatesVerified','error']} for s in data['series']],limitations=applicable_limitations(data['limitations'],data['series'])+[*(['资产对照仅用共同日期，不填充节假日或BTC周末值；窗口起点相对目标日偏差超过7自然日则留空，此为研究规则而非交易日历验证'] if any(s['role']=='asset' for s in data['series']) else []),'本报告不把宏观最新观测与过去资产变化拼成因果，不生成涨跌预测、政策立场评分或配置权重'])
 result['individualAssetWindows']=[individual_asset_windows(asset,asof) for asset in assets]
 result['dailyRateAssetAlignment']=daily_rate_asset_alignment(data['series'])
 result['monthlyAlignment']=monthly_alignment(data['series'])
 result['transmissionHypotheses']=transmission_hypotheses(spec.get('transmissionHypotheses',[]),data['series'],bindings)
 out=Path(out);out.mkdir(parents=True,exist_ok=False);lines=['# 宏观与跨资产观察','',f"研究截止日：{data['asOf']}。这里并列展示宏观观测和历史价格变化，不判断这些变量导致了资产涨跌。",'','## 主要观察']+report_summary(snapshots,result['monthlyAlignment'])+['','## 观测依据']
 for s in snapshots:
  if not s['latest']:lines.append(s['name']+'：本次未取得数据。');continue
  line=s['name']+'：'+str(s['latest']['value'])+'（'+{'percent':'%','index-2017-100':'指数，2017=100','index-1982-84-100':'指数，1982–1984=100','USD-per-barrel':'美元/桶','USD-per-metric-ton':'美元/公吨','thousand-barrels':'千桶'}.get(s['unit'],s['unit'])+'），所属期'+s['latest']['date']+'。逐点发布日期未核验。'
  if s['change']:line+=' 较上一个有效观测变化'+f"{s['change']['value']:.2f}"+{'percentage-point':'个百分点。','bp':'bp。','thousand-barrels':'千桶。'}[s['change']['unit']]
  if s['monthOverMonth']:
   m=s['monthOverMonth'];line+=' 同上月变化'+(f"{m['value']:.2f}个百分点" if m['unit']=='percentage-point' else f"{m['value']:.2%}")+'（严格匹配上一个日历月）。'
  if s['cpiYoY']:line+=' 季调指数计算的同比变化'+f"{s['cpiYoY']['value']:.2%}，不冒充通常公布的未季调同比。"
  if s['activityYoY']:line+=' 工业生产指数同月同比变化'+f"{s['activityYoY']['value']:.2%}"+'，不是GDP增长率。'
  lines.append(line)
  if s.get('exchangeRateBasis'):
   fx=s['exchangeRateBasis'];lines.append('报价方向：1 '+fx['baseCurrency']+'对应'+fx['quoteCurrency']+'数量。'+fx['limitation']+'。')
   if fx['directChange'] is not None:lines.append('相邻观测区间 '+fx['start']+'至'+fx['end']+'：'+fx['baseCurrency']+'相对'+fx['quoteCurrency']+'变化'+format(fx['directChange'],'.2%')+'；反向报价变化'+format(fx['inverseChange'],'.2%')+'。反向变化不是直接改符号。')
  for w in s['recentObservationWindows']:
   if w['status']=='observed-interval-change':lines.append('跨'+str(w['observationIntervals'])+'个实际观测间隔：'+w['start']+'至'+w['end']+'（'+str(w['calendarDays'])+'自然日），变化'+(format(w['value'],'.2%') if w['unit']=='relative-change' else format(w['value'],'.2f')+('bp' if w['unit']=='bp' else '个百分点'))+'。不等于连续交易日或固定自然日窗口。')
 alignment=result['monthlyAlignment']
 if alignment['status']!='not-applicable':
  lines+=['','## 月度指标同口径观察']
  if not alignment['month']:
   lines.append('月度指标没有共同月份，不补值，也不合成同步周期判断。')
   lines += [g['month']+'：缺少'+ '、'.join(g['missingSeries'])+'，该月不补值。' for g in alignment['monthGaps']]
   if alignment.get('missingSeries'):lines.append('完全未取得观测的月度序列：'+ '、'.join(alignment['missingSeries'])+'。')
  else:
   lines.append('共同所属月为'+alignment['month']+'，不是共同发布日期；各指标仍可能是修订历史。')
   lines += [o['id']+'：'+str(o['point']['value'])+'（'+o['unit']+'），该序列最新月份为'+o['latestMonth']+'。' for o in alignment['observations']]
   if alignment['monthGaps']:
    lines.append('共同月份存在断档，不能把下表视作连续月度趋势。')
    lines += [g['month']+'：缺少'+ '、'.join(g['missingSeries'])+'，该月不补值。' for g in alignment['monthGaps']]
   ids=[o['id'] for o in alignment['observations']]
   lines+=['','最近共同月份明细（只列实际共同观测，不补缺期）：','','| 所属月 | '+' | '.join(ids)+' |','|---|'+ '|'.join(['---']*len(ids))+'|']
   lines += ['| '+h['month']+' | '+' | '.join(str(o['point']['value']) for o in h['observations'])+' |' for h in alignment['history']]
 lines+=['','## 资产历史价格对照']
 if not assets:lines.append('本次未请求资产行情，不属于取数失败。')
 for w in windows:
  if w['status']=='insufficient':lines.append(str(w['windowDays'])+'日窗口：共同历史不足，未计算；不以指数或其他资产代替缺项。');continue
  lines.append(f"约{w['windowDays']}日窗口，实际{w['start']}至{w['end']}，{w['actualDays']}自然日，结束日距截止日{w['endLagDays']}日。")
  lines += [('比特币（Coinbase美元报价）' if r['id']=='CBBTCUSD' else r['id'])+'：'+f"{r['value']:.2%}"+'（价格变化，非含分红总收益）' for r in w['returns']]
 if any(w['status']=='insufficient' for w in windows) and assets:
  lines+=['','## 单项资产可用历史','共同窗口不足时，仍展示单项已取得的价格历史。各项起止日期可能不同，不能用这张表直接排名或比较同步表现。','|资产|名义窗口|实际区间|价格变化|','|---|---:|---|---:|']
  for asset in result['individualAssetWindows']:
   for w in asset['windows']:
    period=w['start']+'至'+w['end'] if w['value'] is not None else '历史不足'
    value=format(w['value'],'.2%') if w['value'] is not None else '未计算'
    lines.append('|'+asset['id']+'|'+str(w['windowDays'])+'日|'+period+'|'+value+'|')
 if result['dailyRateAssetAlignment']:
  lines+=['','## 利率与资产同窗口对照','仅使用所有所选日度利率与资产共同存在的日期；同一日期不代表同一时刻，也不证明因果。月度CPI不混入此表，缺值不补齐。']
  for row in result['dailyRateAssetAlignment']:
   if row['status']=='insufficient-common-observations':lines.append(str(row['observationIntervals'])+'个共同观测间隔：历史不足，不计算。');continue
   lines.append(row['start']+'至'+row['end']+'，跨'+str(row['observationIntervals'])+'个共同观测间隔（'+str(row['calendarDays'])+'自然日）。')
   if row['continuityStatus']=='sparse-observations-not-daily-window':lines.append('共同观测较稀疏，最长相邻间隔为'+str(row['maximumCalendarGapDays'])+'自然日；这里只比较已有端点，不代表连续日度行情。')
   lines+=['| 指标或资产 | 同窗口变化 |','|---|---:|']
   lines+=['| '+c['id']+' | '+(format(c['value'],'.2f')+'bp' if c['unit']=='bp' else format(c['value'],'.2%'))+' |' for c in row['changes']]
 if result['transmissionHypotheses']:
  lines+=['','## 传导假设与验证问题','以下为待验证的研究解释，不是因果结论或资产预测。']
  for row in result['transmissionHypotheses']:
   if row['assetObservations']:lines.append('所引用资产观测：'+'；'.join(o['id']+'，日期'+o['latest']['date']+'，价格单位'+o['unit'] for o in row['assetObservations'])+'。这些日期不保证与宏观观测同步，价格口径不等于含分红总收益。')
   lines += [row['mechanism'],'对应观测：'+ '、'.join(row['factorIds']), '观测核验：'+ '；'.join(o['id']+('已与原始响应一致' if o['sourceBindingStatus']=='raw-file-and-observations-matched' else '原始观测尚未完整核对')+('，逐点发布日期未核验' if not o['publicationDatesVerified'] else '，发布日期已登记核验状态') for o in row['observations']),'成立条件：'+ '；'.join(row['conditions']),'反证与待补资料：'+ '；'.join(row['counterEvidence'])]
 lines+=['','## 本次资料缺口',('未取得序列：'+','.join(result['missingSeries'])) if result['missingSeries'] else '各序列已取得观测，但发布日期、复权和同步时刻仍未核验。','','## 口径与局限',*result['limitations'],'','## 数据来源',*[s.get('sourceUrl') or (s['id']+'：来源链接未登记') for s in result['sources']]];md='\n'.join(lines)
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');(out/'宏观与跨资产观察.md').write_text(md,encoding='utf8');(out/'宏观与跨资产观察.html').write_text(render(md,title='宏观与跨资产观察'),encoding='utf8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['collect','build']);p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();globals()[a.command](json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float),a.out_dir)

