import unittest,tempfile,json,copy,hashlib
from pathlib import Path
from unittest.mock import patch
import market_collect as m
import portable_collect as p
import fund_series_tools as f
import collection_quality_brief as q
from collection_validation import market_rows,urls
from verify_collection_report import verify

class Tests(unittest.TestCase):
 def price(self,value=10):return {'date':'2026-09-01','open':value,'close':value,'high':value,'low':value,'volume':1,'amount':10}
 def seed(self,root):
  with patch.object(m,'history',return_value=([self.price()],['https://example.org'])),patch.object(m,'fund_announcements',return_value=([{'id':'a','date':'2026-09-01'}],['https://example.org'])):return m.collect_market(root,'etf','512800','2026-09-30',True,'2026-09-01')
 def dist(self):return {'code':'test','asOf':'2026-09-02','sourceUrl':'https://example.org','eventCoverage':'verified-complete-for-window','events':[],'history':[{'date':'2026-09-01','nav':1},{'date':'2026-09-02','nav':1}]}
 def bundle(self):return {'asOf':'2026-09-30','rows':[{'kind':'fund','code':'001938','history':[{'date':'2026-09-01','nav':1}],'source':'https://example.org','retrievedAt':'2026-09-02T00:00:00Z'}]}
 def report(self,root):
  file=Path(root)/'input.json';file.write_text(json.dumps(self.bundle()),encoding='utf-8');out=Path(root)/'report';q.publish(file,out);return file,out/'report-manifest.json'
 def test_r31_fresh_invalid_price_keeps_old(self):
  with tempfile.TemporaryDirectory() as root:
   old=self.seed(root)
   with patch.object(m,'history',return_value=([self.price(-1)],['https://example.org'])),patch.object(m,'fund_announcements',side_effect=TimeoutError()):out=m.collect_market(root,'etf','512800','2026-09-30',True,'2026-09-01')
   self.assertEqual(out['history'],old['history']);self.assertEqual(out['components']['history']['status'],'cached-after-failure')
 def test_r32_failed_write_keeps_old_return_and_file(self):
  with tempfile.TemporaryDirectory() as root:
   old=self.seed(root)
   with patch.object(m,'history',return_value=([self.price(20)],['https://example.org'])),patch.object(m,'fund_announcements',side_effect=TimeoutError()),patch.object(m,'atomic',side_effect=PermissionError()):out=m.collect_market(root,'etf','512800','2026-09-30',True,'2026-09-01')
   self.assertEqual(out['history'],old['history']);self.assertEqual(m.collect_market(root,'etf','512800','2026-09-30',False,'2026-09-01')['history'],old['history'])
 def test_r33_direct_invalid_code_preflight(self):
  with patch.object(m,'history') as get:
   with self.assertRaises(ValueError):m.collect_market('.','stock','../abc','2026-09-30',True)
   get.assert_not_called()
 def test_r34_direct_dates_boolean_refresh(self):
  for cutoff,refresh in [('20260930',True),('2026-09-30','true')]:
   with self.assertRaises(ValueError):m.collect_market('.','stock','600036',cutoff,refresh)
 def test_r35_invalid_source_links_rejected(self):
  for value in [[],['http://example.org'],['https://user:pass@example.org'],[None]]:
   with self.assertRaises(ValueError):urls(value)
 def test_r36_invalid_volume_and_amount(self):
  for field,value in [('volume',-1),('amount',float('nan')),('volume',True)]:
   row=self.price();row[field]=value
   with self.assertRaises(ValueError):market_rows('history',[row])
 def test_r37_announcement_metadata_duplicates(self):
  with self.assertRaises(ValueError):market_rows('announcements',[{'id':'a','date':'2026-09-01'}]*2)
 def test_r38_financial_window_independent(self):
  with tempfile.TemporaryDirectory() as root,patch.object(m,'history',return_value=([self.price()],['https://example.org'])),patch.object(m,'fund_announcements',return_value=([{'id':'a','date':'2026-09-01'}],['https://example.org'])),patch.object(m,'financials',return_value=([{'period':'2026-06-30','publishedAt':'2026-08-30'}],['https://example.org'])) as get:
   out=m.collect_market(root,'stock','600036','2026-09-30',True,'2026-09-01',financial_start='2026-01-01');get.assert_called_once_with('600036','2026-01-01','2026-09-30');self.assertEqual(len(out['financials']),1)
 def test_r39_cache_request_binding_mismatch(self):
  with tempfile.TemporaryDirectory() as root:
   self.seed(root);file=Path(root)/'research-data/etf/512800-1/history-2026-09-01-2026-09-30.json';data=json.loads(file.read_text(encoding='utf-8'));data['request']['code']='999999';file.write_text(json.dumps(data),encoding='utf-8')
   self.assertEqual(m.collect_market(root,'etf','512800','2026-09-30',False,'2026-09-01')['history'],[])
 def test_r40_empty_fund_cache_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   file=Path(root)/'research-data/fund/001938.json';file.parent.mkdir(parents=True);file.write_text(json.dumps({'code':'001938','kind':'fund','history':[],'retrievedAt':'2026-09-02T00:00:00Z'}),encoding='utf-8');self.assertIn('为空',p.collect(root,'fund',['001938'],'2026-09-30',False)['rows'][0]['errors'])
 def test_r41_future_vendor_nav_rejected(self):
  text='var fS_name="测试";var fS_code="001938";var Data_netWorthTrend=[{"x":4102444800000,"y":1}];'
  with tempfile.TemporaryDirectory() as root,patch.object(p,'get',return_value=text):self.assertIn('晚于',p.collect(root,'fund',['001938'],'2026-09-30',True)['rows'][0]['errors'])
 def test_r42_invalid_code_list_type(self):
  with self.assertRaises(ValueError):p.collect('.','fund',[[]],'2026-09-30',False)
 def test_r43_future_vendor_quote_rejected(self):
  fields=['']*40;fields[1]='测试';fields[2]='600036';fields[3]='10';fields[30]='20300101120000'
  with tempfile.TemporaryDirectory() as root,patch.object(p,'get',return_value='v_sh600036="'+'~'.join(fields)+'";'):self.assertIn('晚于',p.collect(root,'stock',['600036'],'2026-09-30',True)['rows'][0]['errors'])
 def test_r44_event_entry_shape(self):
  s=self.dist();s['events']=[None]
  with self.assertRaises(ValueError):f.distributions(s)
 def test_r45_event_derived_overflow_rejected(self):
  s=self.dist();s['history'][0]['nav']=1e-300;s['history'][1]['nav']=1e300
  with self.assertRaises(ValueError):f.distributions(s)
 def test_r46_annual_overflow_is_gap(self):
  s=self.dist();s['history'][1]['nav']=1000;out=f.distributions(s);self.assertIsNone(out['reinvest']['annualizedReturnPct']);self.assertIsNotNone(out['reinvest']['annualizationGap'])
 def test_r47_quality_jump_overflow(self):
  s=self.dist();s['history'][0]['nav']=1e-300;s['history'][1]['nav']=1e300;s['eventCoverage']='unknown'
  with self.assertRaises(ValueError):f.quality(s)
 def test_r48_benchmark_alignment_loss_blocks_annual_metrics(self):
  def asset(code,missing=False):return {'code':code,'sourceUrl':'https://example.org','basis':'total-return','currency':'CNY','weight':1,'history':[{'date':f'2026-09-0{i}','value':1+i/100} for i in range(1,6) if not (missing and i==3)]}
  out=f.benchmarks({'asOf':'2026-09-05','frequency':'daily','currency':'CNY','fund':asset('a'),'benchmarks':[{'name':'test','rebalance':'buy-and-hold','components':[asset('b',True)]}]})
  self.assertIsNone(out['benchmarks'][0]['annualTrackingErrorPct']);self.assertIsNone(out['benchmarks'][0]['jensenAlphaAnnualizedPp'])
 def test_r49_snapshot_difference_overflow(self):
  meta={'returnBasis':'total-return','frequency':'daily','window':'fixed','classificationVersion':'v1'};a={'subjectCodes':['a'],'asOf':'2026-09-01','metrics':{'x':-1e308},'methodology':meta};b={**a,'asOf':'2026-09-02','metrics':{'x':1e308}}
  self.assertIsNone(f.snapshot_diff({'before':a,'after':b})['metrics'][0]['difference'])
 def test_r50_calendar_applicability_type(self):
  s=self.dist();s['calendar']={'applicabilityConfirmed':'true'}
  with self.assertRaises(ValueError):f.quality(s)
 def test_r51_report_null_name_blank(self):
  s=self.bundle();s['rows'][0]['identity']={'name':None};self.assertNotIn('None',q.brief(s))
 def test_r52_report_component_failure_without_error_summary(self):
  s=self.bundle();s['rows'][0]['components']={'history':{'status':'cached-after-failure','error':'TimeoutError'}};out=q.brief(s);self.assertIn('资料缺口',out);self.assertIn('取数超时',out)
 def test_r53_quote_only_report(self):
  s=self.bundle();s['rows'][0].update(kind='stock',history=[],quote={'price':10,'asOf':'2026-09-01','quoteAt':'2026-09-01T10:00:00+08:00'});self.assertIn('单点报价不能替代历史行情',q.brief(s))
 def test_r54_financial_and_announcement_counts_visible(self):
  s=self.bundle();s['rows'][0].update(financials=[{'period':'2026-06-30','publishedAt':'2026-08-30'}],announcements=[{'id':'a','date':'2026-09-01'},{'id':'b','date':'2026-09-02'}]);out=q.brief(s);self.assertIn('1条财务摘要',out);self.assertIn('2条公告元数据',out)
 def test_r55_publish_failure_leaves_no_output(self):
  with tempfile.TemporaryDirectory() as root:
   file=Path(root)/'input.json';file.write_text(json.dumps(self.bundle()),encoding='utf-8');out=Path(root)/'report'
   with patch.object(q,'atomic_write',side_effect=PermissionError()):
    with self.assertRaises(PermissionError):q.publish(file,out)
   self.assertFalse(out.exists());self.assertEqual(list(Path(root).glob('.report-*')),[])
 def test_r56_report_change_detected(self):
  with tempfile.TemporaryDirectory() as root:
   file,manifest=self.report(root);self.assertEqual(verify(manifest,file)['status'],'stored-content-verified');(manifest.parent/'资料质量说明.html').write_text('changed',encoding='utf-8');self.assertEqual(verify(manifest,file)['status'],'content-mismatch')
 def test_r57_manifest_traversal_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   file,manifest=self.report(root);data=json.loads(manifest.read_text(encoding='utf-8'));data['files']['../outside']='0'*64;manifest.write_text(json.dumps(data),encoding='utf-8');self.assertEqual(verify(manifest,file)['status'],'invalid-manifest')
 def test_r58_input_drift_detected(self):
  with tempfile.TemporaryDirectory() as root:
   file,manifest=self.report(root);file.write_text('{}',encoding='utf-8');self.assertFalse(verify(manifest,file)['inputMatches'])
 def test_r59_method_change_separate(self):
  with tempfile.TemporaryDirectory() as root:
   file,manifest=self.report(root);data=json.loads(manifest.read_text(encoding='utf-8'));data['methodFiles']['fund_series_tools.py']='0'*64;manifest.write_text(json.dumps(data),encoding='utf-8');out=verify(manifest,file);self.assertEqual(out['status'],'stored-content-verified-method-different')
 def test_r60_duplicate_manifest_fields_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   file=Path(root)/'manifest.json';file.write_text('{"schemaVersion":1,"schemaVersion":1}',encoding='utf-8');self.assertEqual(verify(file)['status'],'invalid-manifest')

if __name__=='__main__':unittest.main()
