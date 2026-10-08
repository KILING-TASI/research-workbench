import unittest
from company_one_page import build
class Tests(unittest.TestCase):
 def base(self):return dict(asOf='2026-10-03',identity=dict(name='测试公司',code='600001',market='CN'))
 def test_missing_not_filled(self):
  r=build(self.base());self.assertEqual(len(r['gaps']),5);self.assertEqual(r['sections']['financial'],[])
 def test_future_disclosure_rejected(self):
  s=self.base();s['business']=[dict(text='业务',observedAt='2026-09-30',publishedAt='2026-10-04',sourceUrl='https://example.org',basis='source-statement',locator='页1')]
  with self.assertRaises(ValueError):build(s)
 def test_numeric_without_unit_rejected(self):
  s=self.base();s['financial']=[dict(text='收入',value=100,observedAt='2026-09-30',publishedAt='2026-10-01',sourceUrl='https://example.org',basis='source-statement',locator='页1')]
  with self.assertRaises(ValueError):build(s)

 def test_judgment_requires_scope_and_counterevidence(self):
  s=self.base();s['judgment']=[dict(text='利润兑现仍待核',observedAt='2026-09-30',publishedAt='2026-10-01',sourceUrl='https://example.org',basis='research-explanation',locator='页1')]
  with self.assertRaises(ValueError):build(s)
  s['judgment'][0].update(scope='有限经营专题',coreContradiction='收入与现金不同步',alternatives='账期或需求变化尚待区分',counterEvidence='同口径现金改善后修正判断')
  from company_one_page import markdown
  r=build(s);text=markdown(r);self.assertLess(text.index('研究结论与核心矛盾'),text.index('业务与竞争结构'));self.assertIn('竞争解释',text)
  s['judgment'][0]['text']='输入后来修改';self.assertEqual(r['sections']['judgment'][0]['text'],'利润兑现仍待核')
 def test_result_identity_snapshot_not_mutable_input(self):
  s=self.base();r=build(s);s['identity']['name']='后来修改';self.assertEqual(r['identity']['name'],'测试公司')

if __name__=='__main__':unittest.main()
