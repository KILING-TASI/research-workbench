import unittest,tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
import batch_collect as b
import portable_collect as p
import market_collect as m
import research_pipeline as r
import collection_quality_brief as q
from research_brief_html import render
from atomic_json import write

class Tests(unittest.TestCase):
 def request(self,**kw):return {'asOf':'2026-09-30','refresh':True,'jobId':'test','requests':[{'kind':'fund','code':'001938'}],**kw}
 def cache(self,root,**kw):
  row={'code':'001938','kind':'fund','historyBasis':'nav-with-distributions','identity':{'code':'001938','name':'测试'},'history':[{'date':'2026-09-01','nav':1}],'retrievedAt':'2026-09-02T00:00:00Z',**kw}
  file=Path(root)/'research-data/fund/001938.json';file.parent.mkdir(parents=True,exist_ok=True);file.write_text(json.dumps(row),encoding='utf-8');return file
 def compare_input(self):return {'asOf':'2026-09-30','rows':[{'code':c,'comparisonGroup':'测试','basis':'nav-with-distributions','frequency':'trading_day','history':[{'date':'2026-09-01','nav':1},{'date':'2026-09-02','nav':1.1}]} for c in ['001938','003095']]}
 def bundle(self):return {'asOf':'2026-09-30','rows':[{'code':'001938','kind':'fund','history':[{'date':'2026-09-01','nav':1}],'source':'https://example.org/a','retrievedAt':'2026-09-02T00:00:00Z'}]}
 def test_r11_windows_reserved_job(self):
  for job in ['CON','nul','COM1','LPT9']:
   with self.assertRaisesRegex(ValueError,'保留'):b.run('.',self.request(jobId=job),None)
 def test_r12_duplicate_inferred_market(self):
  s=self.request();s['requests']=[{'kind':'etf','code':'512800'},{'kind':'etf','code':'512800','market':1}]
  with self.assertRaisesRegex(ValueError,'重复'):b.run('.',s,None)
 def test_r13_missing_checkpoint_not_new_batch(self):
  with tempfile.TemporaryDirectory() as root,patch.object(b,'collect_market') as fetch:
   with self.assertRaisesRegex(ValueError,'断点不存在'):b.run(root,self.request(resume=True),None)
   fetch.assert_not_called();self.assertFalse((Path(root)/'research-data').exists())
 def test_r14_nan_checkpoint_rejected_without_overwrite(self):
  with tempfile.TemporaryDirectory() as root:
   legacy=lambda *a:{'rows':[{'history':[{'date':'2026-09-01','nav':1}]}]}
   first=b.run(root,self.request(),legacy);file=Path(first['checkpoint']);state=json.loads(file.read_text(encoding='utf-8'));state['rows']['0']['history'][0]['nav']=float('nan');file.write_text(json.dumps(state),encoding='utf-8')
   original=file.read_bytes()
   with self.assertRaisesRegex(ValueError,'断点文件不可读'):b.run(root,self.request(resume=True),legacy)
   self.assertEqual(file.read_bytes(),original)
 def test_r15_wrong_returned_identity_is_failure(self):
  with tempfile.TemporaryDirectory() as root:
   out=b.run(root,self.request(),lambda *a:{'rows':[{'code':'999999','history':[1]}]})
   self.assertEqual(out['coverage']['unavailable'],1);self.assertEqual(out['rows'][0]['code'],'001938')
 def test_r16_fund_start_honored(self):
  with tempfile.TemporaryDirectory() as root:
   s=self.request();s['requests'][0]['start']='2026-09-02';out=b.run(root,s,lambda *a:{'rows':[{'history':[{'date':'2026-09-01','nav':1},{'date':'2026-09-02','nav':2}]}]})
   self.assertEqual(out['rows'][0]['history'],[{'date':'2026-09-02','nav':2}])
 def test_r17_wrong_cache_basis_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   self.cache(root,historyBasis='price');row=p.collect(root,'fund',['001938'],'2026-09-30',False)['rows'][0];self.assertIn('口径',row['errors'])
 def test_r18_naive_cache_time_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   self.cache(root,retrievedAt='2026-09-02T00:00:00');self.assertIn('时区',p.collect(root,'fund',['001938'],'2026-09-30',False)['rows'][0]['errors'])
 def test_r19_invalid_quote_cache_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   file=Path(root)/'research-data/stock/600036.json';file.parent.mkdir(parents=True);file.write_text(json.dumps({'code':'600036','kind':'stock','history':[],'retrievedAt':'2026-09-02T00:00:00Z','quote':{'price':-1}}),encoding='utf-8')
   self.assertIn('报价',p.collect(root,'stock',['600036'],'2026-09-30',False)['rows'][0]['errors'])
 def test_r20_boolean_vendor_time_rejected(self):
  with tempfile.TemporaryDirectory() as root,patch.object(p,'get',return_value='var fS_name="测试";var fS_code="001938";var Data_netWorthTrend=[{"x":true,"y":1}];'):
   self.assertIn('时间无效',p.collect(root,'fund',['001938'],'2026-09-30',True)['rows'][0]['errors'])
 def test_r21_failed_atomic_replace_keeps_file(self):
  with tempfile.TemporaryDirectory() as root:
   file=Path(root)/'data.json';write(file,{'value':1});before=file.read_bytes()
   with patch('atomic_json.os.replace',side_effect=PermissionError('占用')):
    with self.assertRaises(PermissionError):write(file,{'value':2})
   self.assertEqual(file.read_bytes(),before);self.assertEqual(list(Path(root).glob('*.tmp')),[])
 def test_r22_invalid_cached_ohlc_rejected(self):
  with tempfile.TemporaryDirectory() as root:
   file=Path(root)/'research-data/etf/512800-1/history-2026-09-01-2026-09-30.json';file.parent.mkdir(parents=True)
   write(file,{'rows':[{'date':'2026-09-01','open':10,'close':10,'high':9,'low':8}],'sources':['https://example.org'],'retrievedAt':'2026-09-02T00:00:00Z'})
   out=m.collect_market(root,'etf','512800','2026-09-30',False,'2026-09-01');self.assertEqual(out['history'],[]);self.assertIn('高低价',out['errors']['history'])
 def test_r23_cash_plus_nav_overflow_rejected(self):
  with self.assertRaisesRegex(ValueError,'合计溢出'):r.series([{'date':'2026-09-01','nav':1e308,'distribution':'分红：每份派现金'+'1'+('0'*308)+'元'}],'2026-09-30','nav-with-distributions')
 def test_r24_currency_mismatch_blocked(self):
  s=self.compare_input();s['rows'][0]['currency']='CNY';s['rows'][1]['currency']='USD'
  with self.assertRaisesRegex(ValueError,'币种'):r.compare(s)
  self.assertIn('missing',r.compare(self.compare_input())['currencyVerification'])
  s=self.compare_input();s['rows'][0]['currency']='人民币'
  with self.assertRaisesRegex(ValueError,'币种'):r.compare(s)
 def test_r25_old_split_outside_requested_window(self):
  s=self.compare_input();s['start']='2026-09-01';s['rows'][0]['history'].insert(0,{'date':'2020-01-01','nav':1,'distribution':'拆分：每份折算2份'})
  self.assertAlmostEqual(r.compare(s)['rows'][0]['totalReturnPct'],10)
 def test_r26_short_volatility_has_reason(self):
  self.assertIn('不足120',r.compare(self.compare_input())['rows'][0]['volatilityUnavailableReason'])
 def test_r27_malformed_and_credentials_link_no_href(self):
  for text in ['[来源](https://[broken)','https://user:password@example.org','[来源](https://user:password@example.org)']:self.assertNotIn('href=',render(text))
 def test_r28_report_future_observation_rejected(self):
  s=self.bundle();s['rows'][0]['history'][0]['date']='2026-10-01'
  with self.assertRaisesRegex(ValueError,'截止日'):q.brief(s)
 def test_r29_report_invalid_number_and_cache_note(self):
  s=self.bundle();s['rows'][0]['history'][0]['nav']=float('nan')
  with self.assertRaisesRegex(ValueError,'无效'):q.brief(s)
  s=self.bundle();s['rows'][0]['collectionStatus']='cached';self.assertIn('未重新刷新',q.brief(s))
 def test_r30_manifest_hashes_and_no_overwrite(self):
  with tempfile.TemporaryDirectory() as root:
   file=Path(root)/'input.json';write(file,self.bundle());out=Path(root)/'report';manifest=q.publish(file,out)
   self.assertEqual(manifest['inputSha256'],hashlib.sha256(file.read_bytes()).hexdigest())
   for name,sha in manifest['files'].items():self.assertEqual(hashlib.sha256((out/name).read_bytes()).hexdigest(),sha)
   with self.assertRaisesRegex(ValueError,'已存在'):q.publish(file,out)

if __name__=='__main__':unittest.main()
