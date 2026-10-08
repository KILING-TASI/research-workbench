import unittest,copy,tempfile
from pathlib import Path
from research_workflow import impact,digest,file_digest,compare_results,impact_markdown
class Tests(unittest.TestCase):
 def sample(self):
  r={'type':'policy-original-reading','sourceUrl':'https://example.org/policy','value':1};p={'asOf':'2026-10-05'};h=digest(p)
  x=dict(type='research-template-result',status='calculated-with-gaps',gaps=['unverified'],template='report-reading-review',contextHash=h,contextSnapshot=dict(parameters=p,contextHash=h),result=r,lineage=dict(files=[],calculations=[dict(outputSha256=digest(r),code=[dict(module='research_workflow.py',sha256=file_digest(Path(__file__).with_name('research_workflow.py')))])]))
  x['envelopeSha256']=digest(x);return x
 def test_whole_record_mutations_rejected(self):
  for field,value in [('status','verified'),('gaps',[]),('result',{'value':2})]:
   x=self.sample();x[field]=value
   with self.assertRaisesRegex(ValueError,'封装摘要'):impact(x)
 def test_fresh_and_legacy_scopes(self):
  x=self.sample();self.assertEqual(impact(x)['impactStatus'],'unchanged-for-registered-dependencies')
  del x['envelopeSha256'];self.assertIn('历史记录',impact_markdown(impact(x)))
  x['result']['value']=3
  with self.assertRaisesRegex(ValueError,'计算摘要'):impact(x)
 def test_unknown_replacement_rejected(self):
  with self.assertRaisesRegex(ValueError,'未登记'):impact(self.sample(),replacements={'unknown':'other'})
 def test_registered_file_change(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'source';p.write_text('before');x=self.sample();x['lineage']['files']=[dict(role='original',path=str(p),sha256=file_digest(p))];del x['envelopeSha256'];x['envelopeSha256']=digest(x)
   p.write_text('after');self.assertEqual(impact(x)['reasons'][0]['type'],'file-changed')
 def test_policy_url_identifies_comparison(self):
  x=self.sample();self.assertTrue(compare_results(x,x)['directlyComparable']);y=copy.deepcopy(x);y['result']['sourceUrl']='https://example.org/other';del y['envelopeSha256'];y['lineage']['calculations'][0]['outputSha256']=digest(y['result']);y['envelopeSha256']=digest(y)
  self.assertIn('研究对象不同',compare_results(x,y)['comparisonBlockers'])
if __name__=='__main__':unittest.main()
