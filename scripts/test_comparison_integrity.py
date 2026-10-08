import unittest,tempfile,json
from pathlib import Path
from fund_comparison_brief import publish
from verify_collection_report import verify
class ComparisonIntegrity(unittest.TestCase):
 def test_price_proxy_boundary_only_for_price_inputs(self):
  from research_pipeline import compare
  spec=self.spec()
  self.assertNotIn('价格变动代理',compare(spec)['basis'])
  spec['rows'][0]['basis']='qfq'
  for point in spec['rows'][0]['history']:point['close']=point.pop('nav')
  self.assertIn('价格变动代理',compare(spec)['basis'])
 def spec(self):return {'asOf':'2026-09-30','rows':[{'code':c,'basis':'nav-with-distributions','comparisonGroup':'指定研究组','history':[{'date':'2026-09-01','nav':1},{'date':'2026-09-02','nav':v}]} for c,v in [('006113',1.1),('009342',.9)]]}
 def test_complete_input_and_outputs_verified(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'report';publish(self.spec(),p);v=verify(p/'report-manifest.json',p/'input.json');self.assertEqual(v['status'],'stored-content-verified');self.assertTrue(v['inputMatches']);self.assertEqual(v['sourceVerification'],'not-verified')
 def test_changed_result_or_input_detected(self):
  for name in ['比较结果.json','input.json']:
   with self.subTest(name=name),tempfile.TemporaryDirectory() as root:
    p=Path(root)/'report';publish(self.spec(),p);(p/name).write_text('{}','utf-8');self.assertEqual(verify(p/'report-manifest.json',p/'input.json')['status'],'content-mismatch')
 def test_existing_report_preserved(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'report';publish(self.spec(),p);before=(p/'report-manifest.json').read_bytes()
   with self.assertRaises(FileExistsError):publish(self.spec(),p)
   self.assertEqual(before,(p/'report-manifest.json').read_bytes())
