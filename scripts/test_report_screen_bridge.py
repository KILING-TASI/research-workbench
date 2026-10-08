import unittest,copy,json,tempfile
from pathlib import Path
from report_screen_bridge import candidate,instrument_identity,report_text,build
class Tests(unittest.TestCase):
 def test_relative_paths_resolve_from_manifest_and_duplicates_rejected(self):
  from report_screen_bridge import read_input
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'report.json').write_text(json.dumps(self.sample()));p=root/'input.json';spec=dict(asOf='2026-10-03',reports=['report.json'],conditions=[dict(kind='holding',code='600519',market='CN-equity')]);p.write_text(json.dumps(spec))
   self.assertEqual(build(read_input(p))['usableReportCount'],1)
   spec['reports']=['report.json','report.json']
   with self.assertRaisesRegex(ValueError,'不重复'):build(spec)
 def test_human_report_explains_scope_and_reason(self):
  from multidimensional_screen import screen
  spec=dict(asOf='2026-10-03',candidates=[candidate(self.sample(),'2026-10-03')],conditions=[dict(kind='holding',code='019740',market='CN-bond')])
  text=report_text(dict(screenInput=spec,result=screen(spec),reportGaps=[]))
  self.assertIn('查询证券不在本次披露资产范围内',text);self.assertIn('https://example.org/r',text);self.assertIn('报告核对与范围',text)
 def test_us_equity_report_reverse_lookup(self):
  from multidimensional_screen import screen
  r=self.sample();r['holdings']['holdings'][0].update(code='NVDA',securityNamespace='US-equity');c=candidate(r,'2026-10-03')
  s=dict(asOf='2026-10-03',candidates=[c],conditions=[dict(kind='holding',code='NVDA',market='US-equity')]);self.assertEqual(len(screen(s)['selected']),1)
  s['conditions'][0]['code']='ABSENT';self.assertEqual(len(screen(s)['excluded']),1)
  s['conditions'][0]['market']='US-bond';self.assertEqual(len(screen(s)['unknown']),1)
 def sample(self):
  return dict(code='000001',reportDate='2025-12-31',metadata=dict(title='报告',publishedAt='2026-03-31',sourceUrl='https://example.org/r'),sha256='hash',status='副本身份及股票持仓勾稽完成',holdings=dict(id='000001',reportDate='2025-12-31',publishedAt='2026-03-31',sourceUrl='https://example.org/r',sourceSha256='hash',disclosureScope='completeEquity',netAssetsCNY=100,equityWeight=.5,holdings=[dict(code='600519',name='股票',securityNamespace='CN-equity',weight=.5,locator='p5')]))
 def test_failed_report_keeps_requested_denominator(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'report.json';p.write_text(json.dumps(self.sample()),encoding='utf-8')
   r=build(dict(asOf='2026-10-03',reports=[str(p),str(Path(t)/'missing.json')],conditions=[dict(kind='holding',code='600519',market='CN-equity')]))
   self.assertEqual(r['requestedReportCount'],2);self.assertEqual(r['usableReportCount'],1);self.assertEqual(r['failedReportCount'],1)
   self.assertEqual(r['result']['candidateCount'],1)
   self.assertIn('失败对象未被认定为不满足条件',report_text(r))
 def test_all_failed_is_unavailable_not_no_matches(self):
  r=build(dict(asOf='2026-10-03',reports=['missing-a.json','missing-b.json'],conditions=[dict(kind='holding',code='600519',market='CN-equity')]))
  self.assertEqual(r['status'],'unavailable');self.assertIsNone(r['result']);self.assertEqual(r['failedReportCount'],2)
  self.assertIn('未执行条件筛选',report_text(r));self.assertIn('不能据此判断没有匹配基金',report_text(r))
 def test_invalid_rule_not_masked_by_missing_reports(self):
  for rule in [dict(kind='unknown'),dict(kind='metric',field='invented',op='gt',value=1),dict(kind='holding',code='600519',market='CN-equity',minimumWeightPct=-1),None]:
   with self.subTest(rule=rule),self.assertRaises(ValueError):build(dict(asOf='2026-10-03',reports=['missing.json'],conditions=[rule]))
 def test_empty_report_request_rejected(self):
  with self.assertRaises(ValueError):build(dict(asOf='2026-10-03',reports=[],conditions=[{}]))
 def test_namespace(self):self.assertEqual(candidate(self.sample(),'2026-10-03')['holdings']['value'][0]['market'],'CN-equity')
 def identity(self):return dict(code='000001',observedAt='2026-09-30',sourceUrl='https://example.org/identity',quote='交易型开放式指数基金，上海证券交易所上市',instrumentType='exchange-traded-etf',exchange='SSE')
 def test_etf_identity_requires_evidence(self):
  r=candidate(self.sample(),'2026-10-03',self.identity());self.assertEqual(r['kind'],'etf');self.assertEqual(r['market'],'SSE')
  self.assertEqual(candidate(self.sample(),'2026-10-03')['instrumentType'],'fund-unclassified')
 def test_link_not_exchange_etf(self):
  i=self.identity();i['instrumentType']='etf-link';r=candidate(self.sample(),'2026-10-03',i);self.assertEqual(r['kind'],'fund')
 def test_identity_invalid(self):
  for change in [dict(code='999999'),dict(observedAt='2027-01-01'),dict(quote=''),dict(exchange=None)]:
   with self.subTest(change=change),self.assertRaises(ValueError):instrument_identity(dict(self.identity(),**change),'000001','2026-10-03')
 def test_hash(self):
  s=self.sample();s['sha256']='changed'
  with self.assertRaises(ValueError):candidate(s,'2026-10-03')
 def test_partial(self):
  s=self.sample();s['holdings']['disclosureScope']='top10'
  with self.assertRaises(ValueError):candidate(s,'2026-10-03')
 def test_total(self):
  s=self.sample();s['holdings']['equityWeight']=.6
  with self.assertRaises(ValueError):candidate(s,'2026-10-03')
if __name__=='__main__':unittest.main()
