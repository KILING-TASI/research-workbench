import unittest,tempfile,json
from pathlib import Path
from macro_asset_observation import parse_csv,parse_chart,changes,build,collect
class Tests(unittest.TestCase):
 def test_exact_month_over_month(self):
  s=dict(id='INDPRO',unit='index-2017-100',frequency='monthly',status='available',points=[dict(date='2026-06-01',value=100),dict(date='2026-08-01',value=105)])
  self.assertIsNone(changes(s)['monthOverMonth'])
  s['points'][0]['date']='2026-07-01';self.assertAlmostEqual(changes(s)['monthOverMonth']['value'],.05)
 def test_monthly_rate_change_points(self):
  s=dict(id='UNRATE',unit='percent',frequency='monthly',status='available',points=[dict(date='2026-07-01',value=4),dict(date='2026-08-01',value=4.2)])
  m=changes(s)['monthOverMonth'];self.assertEqual(m['unit'],'percentage-point');self.assertAlmostEqual(m['value'],.2)
 def test_seasonality_conflict(self):
  s=dict(id='CPIAUCSL',unit='index-1982-84-100',role='macro',seasonality='not-seasonally-adjusted',frequency='monthly',status='available',points=[])
  from macro_asset_observation import validate_series_contract
  with self.assertRaises(ValueError):validate_series_contract([s])
  with self.assertRaises(ValueError):changes(s)
 def test_monthly_duplicates_rejected(self):
  s=dict(id='INDPRO',unit='index-2017-100',frequency='monthly',status='available',points=[dict(date='2026-08-01',value=100),dict(date='2026-08-02',value=105)])
  with self.assertRaises(ValueError):changes(s)
 def test_summary_no_claim_without_month_basis(self):
  from macro_asset_observation import report_summary
  self.assertIn('缺少可用',report_summary([],{'month':None})[0])
 def test_summary_direction_and_boundaries(self):
  from macro_asset_observation import report_summary
  s={'name':'失业率','monthOverMonth':{'end':'2026-09-01','value':.1,'unit':'percentage-point'}}
  text=''.join(report_summary([s],{'month':'2026-08'}));self.assertIn('上升0.10个百分点',text);self.assertIn('不能拼成',text)
 def test_irrelevant_limitations_excluded(self):
  from macro_asset_observation import applicable_limitations
  r=applicable_limitations(['所选ETF未复权','CPI为季调指数；DFF为利率','库存为美国期末原油','当前修订历史'],[dict(id='INDPRO',role='macro')])
  self.assertEqual(r,['当前修订历史'])
 def test_selected_cpi_caveat_retained(self):
  from macro_asset_observation import applicable_limitations
  r=applicable_limitations(['CPI为季调指数；DFF为利率'],[dict(id='CPIAUCSL',role='macro')]);self.assertEqual(len(r),1);self.assertIn('未季调同比',r[0])
 def test_fred_identity(self):
  with self.assertRaises(ValueError):parse_csv(b'observation_date,DFF\n2026-01-01,4\n','DGS10','2026-01-01','2026-10-05')
 def test_missing_not_zero(self):
  points,gaps=parse_csv(b'observation_date,DGS10\n2026-01-01,\n2026-01-02,4.2\n','DGS10','2026-01-01','2026-10-05');self.assertEqual(len(points),1);self.assertEqual(gaps,['2026-01-01'])
 def test_rates_in_bp(self):
  s=dict(id='DGS10',unit='percent',frequency='daily',status='available',points=[dict(date='2026-01-01',value=4),dict(date='2026-01-02',value=4.1)]);self.assertAlmostEqual(changes(s)['change']['value'],10)
 def test_cpi_exact_prior_year(self):
  s=dict(id='CPIAUCSL',unit='index',frequency='monthly',status='available',points=[dict(date='2025-08-01',value=100),dict(date='2026-08-01',value=105)]);self.assertAlmostEqual(changes(s)['cpiYoY']['value'],.05);s['points'][0]['date']='2025-07-01';self.assertIsNone(changes(s)['cpiYoY'])
 def test_chart_identity(self):
  with self.assertRaises(ValueError):parse_chart(json.dumps({'chart':{'result':[{'meta':{'symbol':'BAD','currency':'USD','instrumentType':'ETF'}}]}}).encode(),'QQQ','2026-01-01','2026-10-05')
 def chart_payload(self):
  from datetime import datetime,timezone
  stamp=int(datetime(2026,1,2,20,tzinfo=timezone.utc).timestamp())
  return {'chart':{'result':[{'meta':{'symbol':'QQQ','currency':'USD','instrumentType':'ETF','exchangeTimezoneName':'America/New_York'},'timestamp':[stamp],'indicators':{'quote':[{'close':[100]}]}}]}}
 def test_chart_boolean_price_rejected(self):
  p=self.chart_payload();p['chart']['result'][0]['indicators']['quote'][0]['close']=[True]
  with self.assertRaisesRegex(ValueError,'价格值无效'):parse_chart(json.dumps(p).encode(),'QQQ','2026-01-01','2026-10-05')
 def test_chart_boolean_timestamp_rejected_even_outside_window(self):
  p=self.chart_payload();p['chart']['result'][0]['timestamp']=[True]
  with self.assertRaisesRegex(ValueError,'时间戳无效'):parse_chart(json.dumps(p).encode(),'QQQ','2026-01-01','2026-10-05')
 def test_chart_ambiguous_results_rejected(self):
  p=self.chart_payload();p['chart']['result']*=2
  with self.assertRaisesRegex(ValueError,'唯一证券'):parse_chart(json.dumps(p).encode(),'QQQ','2026-01-01','2026-10-05')
 def archive(self,p,series):
  a=p/'a.json';a.write_text(json.dumps(dict(start='2026-01-01',asOf='2026-10-05',series=series,limitations=[])),encoding='utf8');return dict(archive=str(a))
 def asset(self,id,points):return dict(id=id,role='asset',unit='USD',frequency='daily-business',status='available',clock='date-only',points=points)
 def test_common_dates_no_fill(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);ss=[self.asset('QQQ',[dict(date='2026-08-01',value=100),dict(date='2026-10-01',value=110)]),self.asset('BTC',[dict(date='2026-08-02',value=200),dict(date='2026-10-01',value=210)])];r=build(self.archive(p,ss),p/'out');self.assertEqual(r['assetWindows'][0]['status'],'insufficient')
 def test_future_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with self.assertRaises(ValueError):build(self.archive(p,[self.asset('QQQ',[dict(date='2026-10-06',value=100)])]),p/'out')
 def test_valid_price_return(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=build(self.archive(p,[self.asset('QQQ',[dict(date='2026-09-01',value=100),dict(date='2026-10-01',value=110)])]),p/'out');self.assertAlmostEqual(r['assetWindows'][0]['returns'][0]['value'],.1)
 def test_collect_failure_keeps_each_source(self):
  def failed(url):raise OSError('offline')
  def failed_asset(*a):raise OSError('offline')
  with tempfile.TemporaryDirectory() as d:
   r=collect(dict(start='2026-01-01',asOf='2026-10-05'),Path(d)/'out',fetch_fn=failed,asset_fn=failed_asset);self.assertEqual(len(r['series']),6);self.assertTrue(all(not s['points'] for s in r['series']))
 def test_raw_source_mutation_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'QQQ-fallback.json').write_bytes(b'changed');s=self.asset('QQQ',[dict(date='2026-10-01',value=110)]);s['rawFile']='QQQ-fallback.json';s['sha256']='wrong'
   with self.assertRaises(ValueError):build(self.archive(p,[s]),p/'out')
 def test_missing_binding_explicit(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);r=build(self.archive(p,[self.asset('QQQ',[dict(date='2026-10-01',value=110)])]),p/'out');self.assertEqual(r['sourceBindings'][0]['status'],'raw-source-not-bound')
 def test_archive_value_changed_raw_unchanged_rejected(self):
  import hashlib
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);raw=b'observation_date,DGS10\n2026-10-01,4.2\n';(p/'DGS10.csv').write_bytes(raw);s=dict(id='DGS10',role='macro',unit='percent',frequency='daily-business',status='available',rawFile='DGS10.csv',sha256=hashlib.sha256(raw).hexdigest(),points=[dict(date='2026-10-01',value=99)])
   with self.assertRaises(ValueError):build(self.archive(p,[s]),p/'out')
 def test_archive_matches_raw_observations(self):
  import hashlib
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);raw=b'observation_date,DGS10\n2026-10-01,4.2\n';(p/'DGS10.csv').write_bytes(raw);s=dict(id='DGS10',role='macro',unit='percent',frequency='daily-business',status='available',rawFile='DGS10.csv',sha256=hashlib.sha256(raw).hexdigest(),points=[dict(date='2026-10-01',value=4.2)])
   r=build(self.archive(p,[s]),p/'out');self.assertEqual(r['sourceBindings'][0]['status'],'raw-file-and-observations-matched')
 def test_transmission_requires_observed_factors_and_counterevidence(self):
  from macro_asset_observation import transmission_hypotheses
  series=[dict(id='DGS10',role='macro',points=[dict(date='2026-01-01',value=4)])]
  row=dict(factorIds=['DGS10'],mechanism='利率可能影响折现率',conditions=['需区分实际利率与风险溢价'],counterEvidence=['盈利变化是否抵消？'])
  result=transmission_hypotheses([row],series);self.assertEqual(result[0]['status'],'research-hypothesis-not-causal-verification');self.assertEqual(result[0]['observations'][0]['sourceBindingStatus'],'raw-source-not-bound');self.assertFalse(result[0]['observations'][0]['publicationDatesVerified'])
  for changed in [dict(row,factorIds=['UNKNOWN']),dict(row,counterEvidence=[]),dict(row,conditions='条件')]:
   with self.assertRaises(ValueError):transmission_hypotheses([changed],series)
 def test_unknown_selected_series_rejected_before_output(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'out'
   with self.assertRaises(ValueError):collect(dict(start='2025-01-01',asOf='2026-10-05',seriesIds=['UNKNOWN']),p)
   self.assertFalse(p.exists())
 def test_macro_only_does_not_request_assets(self):
  with tempfile.TemporaryDirectory() as d:
   def fetcher(url):return b'observation_date,INDPRO\n2025-01-01,100\n2026-01-01,102\n'
   def forbidden(*args):raise AssertionError('不应请求资产')
   r=collect(dict(start='2025-01-01',asOf='2026-10-05',seriesIds=['INDPRO'],assetIds=[]),Path(d)/'out',fetch_fn=fetcher,asset_fn=forbidden)
   self.assertEqual(len(r['series']),1);self.assertAlmostEqual(changes(r['series'][0])['activityYoY']['value'],.02)
 def test_unemployment_change_is_percentage_points(self):
  r=changes(dict(id='UNRATE',unit='percent',frequency='monthly',status='available',points=[dict(date='2026-07-01',value=4),dict(date='2026-08-01',value=4.2)]))
  self.assertAlmostEqual(r['change']['value'],.2);self.assertEqual(r['change']['unit'],'percentage-point')
 def test_activity_missing_prior_same_month_stays_empty(self):
  r=changes(dict(id='INDPRO',unit='index-2017-100',frequency='monthly',status='available',points=[dict(date='2025-07-01',value=100),dict(date='2026-08-01',value=102)]))
  self.assertIsNone(r['activityYoY'])
 def test_monthly_alignment_uses_common_period_without_fill(self):
  from macro_asset_observation import monthly_alignment
  a=dict(id='INDPRO',role='macro',frequency='monthly',unit='index',points=[dict(date='2026-07-01',value=100),dict(date='2026-08-01',value=102)])
  b=dict(id='CPIAUCSL',role='macro',frequency='monthly',unit='index',points=[dict(date='2026-07-01',value=300)])
  r=monthly_alignment([a,b]);self.assertEqual(r['month'],'2026-07');self.assertEqual(r['observations'][0]['point']['value'],100);self.assertEqual([h['month'] for h in r['history']],['2026-07'])
  b['points']=[];self.assertEqual(monthly_alignment([a,b])['status'],'no-common-month')
 def test_monthly_gaps_include_unobserved_months_and_series(self):
  from macro_asset_observation import monthly_alignment
  a=dict(id='INDPRO',role='macro',frequency='monthly',unit='index',points=[dict(date='2026-01-01',value=100),dict(date='2026-03-01',value=102)])
  b=dict(id='UNRATE',role='macro',frequency='monthly',unit='percent',points=[dict(date='2026-01-01',value=4)])
  r=monthly_alignment([a,b]);self.assertFalse(r['isContinuous']);self.assertEqual(r['monthGaps'],[dict(month='2026-02',missingSeries=['INDPRO','UNRATE']),dict(month='2026-03',missingSeries=['UNRATE'])]);self.assertEqual(r['month'],'2026-01')
 def test_no_common_month_still_lists_missing_inputs(self):
  from macro_asset_observation import monthly_alignment
  a=dict(id='INDPRO',role='macro',frequency='monthly',points=[dict(date='2026-01-01',value=100)])
  b=dict(id='UNRATE',role='macro',frequency='monthly',points=[dict(date='2026-02-01',value=4)])
  r=monthly_alignment([a,b]);self.assertIsNone(r['month']);self.assertEqual(r['monthGaps'],[dict(month='2026-01',missingSeries=['UNRATE']),dict(month='2026-02',missingSeries=['INDPRO'])])
  a['points']=[];b['points']=[];r=monthly_alignment([a,b]);self.assertIsNone(r['observedRange']);self.assertEqual(r['missingSeries'],['INDPRO','UNRATE']);self.assertEqual(r['monthGaps'],[])
 def test_invalid_index_and_before_window_rejected_without_output(self):
  for point in [dict(date='2026-02-01',value=0),dict(date='2025-12-01',value=100),dict(date='2026-02-01',value=True)]:
   with tempfile.TemporaryDirectory() as d:
    p=Path(d);s=dict(id='INDPRO',role='macro',unit='index',frequency='monthly',status='available',points=[point])
    with self.assertRaises(ValueError):build(self.archive(p,[s]),p/'out')
    self.assertFalse((p/'out').exists())
  with self.assertRaises(ValueError):parse_csv(b'observation_date,INDPRO\n2026-01-01,0\n','INDPRO','2026-01-01','2026-10-05')
 def test_malformed_transmission_factor_list(self):
  from macro_asset_observation import transmission_hypotheses
  series=[dict(id='DGS10',role='macro',points=[dict(date='2026-01-01',value=4)])]
  for row in [None,dict(factorIds='DGS10'),dict(factorIds=[{}])]:
   with self.assertRaises(ValueError):transmission_hypotheses([row],series)
 def test_macro_only_has_no_failed_asset_windows(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);s=dict(id='UNRATE',role='macro',unit='percent',frequency='monthly',status='available',points=[dict(date='2026-02-01',value=4)])
   r=build(self.archive(p,[s]),p/'out');self.assertEqual(r['assetWindows'],[])
   report=(p/'out'/'宏观与跨资产观察.md').read_text(encoding='utf-8');self.assertIn('未请求资产行情',report);self.assertNotIn('共同历史不足',report)
 def test_observation_window_counts_actual_intervals(self):
  from macro_asset_observation import observation_windows
  s=dict(id='DGS10',unit='percent',points=[dict(date='2026-01-01',value=4),dict(date='2026-01-15',value=4.1)])
  r=observation_windows(s);self.assertAlmostEqual(r[0]['value'],10);self.assertEqual(r[0]['calendarDays'],14);self.assertEqual(r[1]['status'],'insufficient-observations')
 def test_joint_rate_asset_windows_use_intersection(self):
  from macro_asset_observation import daily_rate_asset_alignment
  rates=dict(id='DGS10',role='macro',unit='percent',points=[dict(date='2026-01-01',value=4),dict(date='2026-01-03',value=4.1),dict(date='2026-01-04',value=5)])
  asset=dict(id='TLT',role='asset',unit='USD',points=[dict(date='2026-01-01',value=100),dict(date='2026-01-02',value=99),dict(date='2026-01-03',value=98)])
  r=daily_rate_asset_alignment([rates,asset]);self.assertEqual(r[0]['end'],'2026-01-03');self.assertEqual(r[0]['calendarDays'],2)
  self.assertAlmostEqual(r[0]['changes'][0]['value'],10);self.assertAlmostEqual(r[0]['changes'][1]['value'],-.02);self.assertEqual(r[1]['status'],'insufficient-common-observations')
  self.assertEqual(daily_rate_asset_alignment([rates]),[])
 def test_known_series_metadata_tamper_blocks_before_output(self):
  for field,value in [('unit','bp'),('unit','decimal'),('role','asset'),('frequency','monthly')]:
   with tempfile.TemporaryDirectory() as d:
    p=Path(d);s=dict(id='DGS10',role='macro',unit='percent',frequency='daily-business',status='available',points=[dict(date='2026-01-01',value=4),dict(date='2026-01-02',value=4.1)])
    s[field]=value
    with self.assertRaisesRegex(ValueError,'定义不一致'):build(self.archive(p,[s]),p/'out')
    self.assertFalse((p/'out').exists())
 def test_joint_rate_units_not_inferred(self):
  from macro_asset_observation import daily_rate_asset_alignment
  rate=dict(id='DGS10',role='macro',unit='bp',points=[dict(date='2026-01-01',value=400),dict(date='2026-01-02',value=410)])
  asset=self.asset('TLT',[dict(date='2026-01-01',value=100),dict(date='2026-01-02',value=99)])
  with self.assertRaisesRegex(ValueError,'定义不一致'):daily_rate_asset_alignment([rate,asset])
 def test_known_dollar_asset_cannot_be_relabelled(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);s=self.asset('QQQ',[dict(date='2026-01-01',value=100),dict(date='2026-01-02',value=101)]);s['unit']='CNY'
   with self.assertRaisesRegex(ValueError,'定义不一致'):build(self.archive(p,[s]),p/'out')
   self.assertFalse((p/'out').exists())
 def test_transmission_assets_bind_observations_without_substitution(self):
  from macro_asset_observation import transmission_hypotheses
  rate=dict(id='DGS10',role='macro',points=[dict(date='2026-01-01',value=4)])
  asset=self.asset('TLT',[dict(date='2026-01-02',value=100)])
  row=dict(factorIds=['DGS10'],assetIds=['TLT'],mechanism='利率变化可能影响债券价格',conditions=['需久期与票息数据'],counterEvidence=['收益率曲线是否非平行变动？'])
  r=transmission_hypotheses([row],[rate,asset])[0]
  self.assertEqual(r['assetObservations'][0]['latest']['date'],'2026-01-02');self.assertEqual(r['observations'][0]['latest']['date'],'2026-01-01');self.assertEqual(r['assetObservations'][0]['sourceBindingStatus'],'raw-source-not-bound')
  for ids in [['QQQ'],['TLT','TLT'],'TLT']:
   with self.assertRaisesRegex(ValueError,'资产'):transmission_hypotheses([dict(row,assetIds=ids)],[rate,asset])
class AssetScopeTests(unittest.TestCase):
 def test_new_assets_have_declared_usd_daily_scope(self):
  from macro_asset_observation import ASSET_SERIES
  for code in ['GLD','IWM']:
   self.assertEqual(ASSET_SERIES[code]['unit'],'USD');self.assertEqual(ASSET_SERIES[code]['role'],'asset');self.assertEqual(ASSET_SERIES[code]['frequency'],'daily-business')
 def test_unrecognized_asset_rejected_before_output(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'archive'
   with self.assertRaisesRegex(ValueError,'支持范围'):collect(dict(start='2026-01-01',asOf='2026-10-05',seriesIds=['DGS10'],assetIds=['UNSUPPORTED']),p)
   self.assertFalse(p.exists())

class IndividualAssetWindowTests(unittest.TestCase):
 def test_partial_asset_does_not_block_individual_history(self):
  import datetime as dt
  from macro_asset_observation import individual_asset_windows
  asset=dict(id='GLD',points=[dict(date='2026-01-01',value=100),dict(date='2026-06-01',value=110),dict(date='2026-07-01',value=120)])
  result=individual_asset_windows(asset,dt.date(2026,7,1));self.assertAlmostEqual(result['windows'][0]['value'],120/110-1);self.assertEqual(result['windows'][1]['status'],'insufficient')
  self.assertTrue(all(w['value'] is None for w in individual_asset_windows(dict(id='IWM',points=[]),dt.date(2026,7,1))['windows']))

class JointSpacingTests(unittest.TestCase):
 def test_sparse_common_dates_keep_endpoint_change_with_warning(self):
  from macro_asset_observation import daily_rate_asset_alignment
  rows=[dict(id='DGS10',role='macro',unit='percent',points=[dict(date='2026-01-01',value=4),dict(date='2026-02-01',value=4.1)]),dict(id='TLT',role='asset',unit='USD',points=[dict(date='2026-01-01',value=100),dict(date='2026-02-01',value=99)])]
  r=daily_rate_asset_alignment(rows)[0];self.assertEqual(r['maximumCalendarGapDays'],31);self.assertEqual(r['continuityStatus'],'sparse-observations-not-daily-window');self.assertAlmostEqual(r['changes'][0]['value'],10);self.assertAlmostEqual(r['changes'][1]['value'],-.01)
 def test_weekend_spacing_does_not_prove_verified_calendar(self):
  from macro_asset_observation import daily_rate_asset_alignment
  rows=[dict(id='DFF',role='macro',unit='percent',points=[dict(date='2026-01-02',value=4),dict(date='2026-01-05',value=4)]),dict(id='QQQ',role='asset',unit='USD',points=[dict(date='2026-01-02',value=100),dict(date='2026-01-05',value=101)])]
  r=daily_rate_asset_alignment(rows)[0];self.assertEqual(r['continuityStatus'],'observed-spacing-within-rule-not-calendar-verified');self.assertEqual(r['maximumCalendarGapDays'],3)

class DailySummaryTests(unittest.TestCase):
 def test_daily_bp_observation_is_not_monthly_failure(self):
  from macro_asset_observation import report_summary
  x=dict(name='长端利率',frequency='daily-business',monthOverMonth=None,change=dict(value=-5,unit='bp',start='2026-09-30',end='2026-10-01'))
  t=''.join(report_summary([x],{}));self.assertIn('下降5.00bp',t);self.assertNotIn('缺少可用的严格月度对比',t);self.assertIn('不是政策目标',t)
 def test_daily_unchanged_is_explicit(self):
  from macro_asset_observation import report_summary
  x=dict(name='有效利率',frequency='daily-7day',change=dict(value=0,unit='bp',start='2026-09-30',end='2026-10-01'))
  self.assertIn('持平',report_summary([x],{})[0])

class PrimarySourceBindingTests(unittest.TestCase):
 def archive(self,p):
  from cross_market_history import collect as primary_collect
  payload={'code':0,'data':{'usQQQ':{'qt':{'usQQQ':['','QQQ','QQQ']},'day':[['2026-01-01','100','101','102','99'],['2026-01-02','101','103','104','100']]}}}
  raw=json.dumps(payload,ensure_ascii=False).encode('utf-8')
  def asset_fn(market,code,start,end):return primary_collect(market,code,start,end,fetch_fn=lambda url:raw)
  collect(dict(start='2026-01-01',asOf='2026-10-05',seriesIds=['DGS10'],assetIds=['QQQ']),p/'archive',fetch_fn=lambda url:b'observation_date,DGS10\n2026-01-01,4\n2026-01-02,4.1\n',asset_fn=asset_fn)
  return p/'archive/result.json'
 def test_primary_bytes_and_all_closes_reparsed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);archive=self.archive(p);r=build(dict(archive=str(archive)),p/'report')
   self.assertEqual(r['sourceBindings'][1]['rawFile'],'QQQ-source.json');self.assertEqual(r['sourceBindings'][1]['status'],'raw-file-and-observations-matched')
 def test_archived_close_edit_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);archive=self.archive(p);data=json.loads(archive.read_text(encoding='utf-8'));data['series'][1]['points'][0]['value']=999;archive.write_text(json.dumps(data),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'原始响应不一致'):build(dict(archive=str(archive)),p/'report')
 def test_source_window_edit_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);archive=self.archive(p);data=json.loads(archive.read_text(encoding='utf-8'));data['series'][1]['sourceUrl']=data['series'][1]['sourceUrl'].replace('2026-01-01','2025-01-01');archive.write_text(json.dumps(data),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'请求窗口不一致'):build(dict(archive=str(archive)),p/'report')

class StrictArchiveTests(unittest.TestCase):
 def test_ambiguous_json_archive_rejected_without_output(self):
  for raw in ['{"asOf":"2026-10-01","asOf":"2026-10-05","start":"2026-01-01","series":[]}', '{"asOf":"2026-10-05","start":"2026-01-01","series":[],"value":1e999}', '{"asOf":"2026-10-05","start":"2026-01-01","series":[],"value":NaN}']:
   with tempfile.TemporaryDirectory() as d:
    p=Path(d);a=p/'archive.json';a.write_text(raw,encoding='utf-8');out=p/'out'
    with self.assertRaises(ValueError):build(dict(archive=str(a)),out)
    self.assertFalse(out.exists());self.assertEqual(a.read_text('utf-8'),raw)
 def test_noncanonical_collect_date_rejected_before_network(self):
  for bad in ['20260101','2026-W01-1','2026-02-30']:
   with tempfile.TemporaryDirectory() as d:
    out=Path(d)/'out'
    def forbidden(*args):raise AssertionError('invalid request must not reach network')
    with self.assertRaises(ValueError):collect(dict(start=bad,asOf='2026-10-05'),out,fetch_fn=forbidden,asset_fn=forbidden)
    self.assertFalse(out.exists())
 def test_noncanonical_csv_observation_rejected(self):
  from macro_asset_observation import parse_csv
  for date in ['20260101','2026-W01-1','2026-02-30']:
   with self.assertRaises(ValueError):parse_csv(('observation_date,DGS10\n'+date+',4\n').encode(),'DGS10','2026-01-01','2026-10-05')

if __name__=='__main__':unittest.main()
