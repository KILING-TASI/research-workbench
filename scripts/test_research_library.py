import copy,json,tempfile,unittest
from pathlib import Path
from research_library import brinson,pool,score,reverse,archive,url,read,dump

class Tests(unittest.TestCase):
 def test_archive_group_identity_and_preflight(self):
  with tempfile.TemporaryDirectory() as directory:
   store=Path(directory);good=store/'good.json';bad=store/'bad.json'
   good.write_text(json.dumps({'type':'research','subjectCodes':['000001','000002']}));bad.write_text(json.dumps({'type':'research','subjectCodes':['000003']}))
   with self.assertRaisesRegex(ValueError,'主体不一致'):archive({'code':'000001','resultFiles':[str(good),str(bad)]},store)
   self.assertFalse((store/'fund-archives').exists())
   result=archive({'code':'000001','resultFiles':[str(good)]},store);self.assertEqual(len(result['results']),1)
   with self.assertRaisesRegex(ValueError,'路径列表'):archive({'code':'000001','resultFiles':str(good)},store)
 def test_overflow_rejected_before_archiving_any_results(self):
  with tempfile.TemporaryDirectory() as directory:
   store=Path(directory);good=store/'good.json';bad=store/'overflow.json'
   good.write_text('{"code":"000001","value":1}')
   bad.write_text('{"code":"000001","value":1e999}')
   with self.assertRaises(ValueError):read(bad)
   with self.assertRaises(ValueError):archive({'code':'000001','resultFiles':[str(good),str(bad)]},store)
   self.assertFalse((store/'fund-archives').exists())
 def test_weight_publication_clock(self):
  s=self.spec();self.assertEqual(brinson(s)['informationTiming']['status'],'publication-date-missing')
  for date,status in [('2025-12-31','declared-before-period-not-externally-verified'),('2026-01-01','same-day-timing-unconfirmed'),('2026-01-20','retrospective-only')]:
   s['weightPublishedAt']=date;self.assertEqual(brinson(s)['informationTiming']['status'],status)
  for date in ['2025-12-30','2026-05-01']:
   s['weightPublishedAt']=date
   with self.assertRaises(ValueError):brinson(s)
 def spec(self):
  return {'start':'2026-01-01','end':'2026-03-31','asOf':'2026-04-30','weightDate':'2025-12-31','basis':'disclosed-snapshot-estimate','industrySystem':'test','industryVersion':'test-v1','returnBasis':'total-return','sectors':[{'industry':'A','portfolioWeight':.6,'benchmarkWeight':.4,'portfolioReturnPct':12,'benchmarkReturnPct':10,'sourceUrl':'https://example.org/A'},{'industry':'B','portfolioWeight':.4,'benchmarkWeight':.6,'portfolioReturnPct':0,'benchmarkReturnPct':-5,'sourceUrl':'https://example.org/B'}]}
 def test_brinson_reconcile(self):
  r=brinson(self.spec());self.assertAlmostEqual(r['activeSnapshotReturnPp'],6.2);self.assertAlmostEqual(r['totals']['totalEffectPp'],6.2);self.assertAlmostEqual(r['arithmeticResidualPp'],0)
 def test_future_weight_and_incomplete(self):
  s=self.spec();s['weightDate']='2026-03-31'
  with self.assertRaises(ValueError):brinson(s)
  s=self.spec();s['sectors'][0]['portfolioWeight']=.5
  with self.assertRaises(ValueError):brinson(s)
 def test_pool_versions_and_score(self):
  with tempfile.TemporaryDirectory() as store:
   store=Path(store);model=[{'metric':'maximumDrawdownPct','direction':'lower','weight':.4},{'metric':'Sharpe','direction':'higher','weight':.6}]
   p=pool({'name':'成长备选池','add':['000001','000002','000003'],'scoreModel':model},store);q=pool({'name':'成长备选池','remove':['000003']},store);self.assertEqual(p['revision'],1);self.assertEqual(q['revision'],2);self.assertEqual(len(p['codes']),3)
   rows=[{'code':'000001','comparisonScope':'3y','comparisonGroup':'growth','sourceUrl':'https://example.org/a','metrics':{'maximumDrawdownPct':10,'Sharpe':2}},{'code':'000002','comparisonScope':'3y','comparisonGroup':'growth','sourceUrl':'https://example.org/b','metrics':{'maximumDrawdownPct':20,'Sharpe':1}}]
   r=score({'pool':p,'rows':rows,'comparisonScope':'3y','comparisonGroup':'growth'});self.assertEqual(r['ranked'][0]['score'],100);self.assertEqual(r['ranked'][1]['score'],0);self.assertEqual(r['excluded'][0]['code'],'000003')
 def test_reverse_scope_market_and_unknown(self):
  f={'id':'000001','publishedAt':'2026-04-20','reportDate':'2026-03-31','sourceUrl':'https://example.org/a','weightBasis':'fund-nav','disclosureScope':'top10','holdings':[{'market':'HKEX','code':'00001','weight':.1}]}
  r=reverse({'asOf':'2026-04-30','reportDate':'2026-03-31','target':{'kind':'security','market':'SZSE','code':'000001'},'funds':[f]});self.assertEqual(r['matches'],[]);self.assertIn('不能证明',r['excluded'][0]['reason'])
 def test_archive_is_append_only(self):
  with tempfile.TemporaryDirectory() as store:
   store=Path(store);p=store/'result.json';p.write_text(json.dumps({'type':'test','code':'000001','value':1}));a=archive({'code':'000001','tags':['待跟踪'],'userNote':'观察','resultFiles':[str(p)]},store);b=archive({'code':'000001','tags':['备选']},store);self.assertNotEqual(a['id'],b['id']);self.assertEqual(len(list((store/'fund-archives/000001/entries').glob('*.json'))),2);self.assertEqual(a['userNote'],'观察')
 def test_bad_sources(self):
  for value in ['https://user:secret@example.org/x','https://example.org/white space','https:///nohost']:
   with self.assertRaises(ValueError):url(value)
 def test_json_rejected_without_partial_output(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'input.json';p.write_text('{"code":"000001","code":"000002"}')
   with self.assertRaises(ValueError):read(p)
   out=Path(t)/'out.json'
   with self.assertRaises(ValueError):dump(out,{'score':float('nan')})
   self.assertFalse(out.exists())
 def test_extreme_finite_score_remains_bounded(self):
  s={'pool':{'name':'test','codes':['000001','000002'],'scoreModel':[{'metric':'x','weight':1,'direction':'higher'}]},'comparisonScope':'same','comparisonGroup':'same','rows':[{'code':c,'comparisonScope':'same','comparisonGroup':'same','sourceUrl':'https://example.org/'+c,'metrics':{'x':v}} for c,v in [('000001',-1e308),('000002',1e308)]]}
  r=score(s);self.assertEqual([x['score'] for x in r['ranked']],[100,0])
 def test_direct_attribution_requires_version(self):
  s=self.spec();s.pop('industryVersion')
  with self.assertRaisesRegex(ValueError,'版本未明确'):brinson(s)
  s=self.spec();s['sectors'][0]['industryVersion']='other'
  with self.assertRaisesRegex(ValueError,'版本冲突'):brinson(s)
 def test_reverse_industry_version_not_silently_mixed(self):
  f={'id':'000001','publishedAt':'2026-04-20','reportDate':'2026-03-31','sourceUrl':'https://example.org/a','weightBasis':'fund-nav','disclosureScope':'complete','industrySystem':'SW','industryVersion':'SW2014','holdings':[{'market':'SSE','code':'600519','weight':.1,'industry':'白酒'}]}
  s={'asOf':'2026-04-30','reportDate':'2026-03-31','target':{'kind':'industry','name':'白酒'},'industrySystem':'SW','industryVersion':'SW2021','funds':[f]}
  r=reverse(s);self.assertEqual(r['matches'],[]);self.assertIn('版本',r['excluded'][0]['reason'])
  f['industryVersion']='SW2021';self.assertEqual(len(reverse(s)['matches']),1)
if __name__=='__main__':unittest.main()
