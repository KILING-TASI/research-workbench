import copy,unittest
from attribution_link import link,render_summary
import test_research_library as fixtures
class LinkTests(unittest.TestCase):
 def test_invalid_shapes_fail_clearly(self):
  for spec in [None,[],{},dict(periods='wrong'),dict(periods=[None])]:
   with self.assertRaises(ValueError):link(spec)
 def test_overflow_cannot_pass_nan_residual_check(self):
  from unittest.mock import patch
  from research_library import brinson
  s=fixtures.Tests().spec();t=copy.deepcopy(s);t.update(start=s['end'],end='2026-06-30',asOf='2026-07-31',weightDate='2026-03-31');s['asOf']='2026-07-31'
  a=brinson(s);b=brinson(t)
  for r in [a,b]:r['portfolioSnapshotReturnPct']=1e308;r['benchmarkReturnPct']=1e308
  with patch('attribution_link.brinson',side_effect=[a,b]),self.assertRaisesRegex(ValueError,'溢出'):link(dict(asOf='2026-07-31',periods=[s,t]))
 def test_readable_report_does_not_hide_missing_declarations(self):
  s=fixtures.Tests().spec();r=link(dict(asOf=s['asOf'],periods=[s]));text=render_summary(r)
  self.assertIn('不能据此得出完整跨期归因结论',text);self.assertIn('行业分类版本',text);self.assertNotIn('industryVersion',text);self.assertIn(s['sectors'][0]['sourceUrl'],text);self.assertIn('不是基金经理纯 Alpha',text)
 def test_link_report_renders_contribution_columns(self):
  from research_brief_html import render
  s=fixtures.Tests().spec();r=link(dict(asOf=s['asOf'],periods=[s]))
  html=render(render_summary(r))
  self.assertEqual(html.count('<table>'),1)
  self.assertRegex(html,r'<th scope="col"(?: class="align-right")?>行业配置贡献</th>')
  self.assertNotIn('<p>|',html)
 def test_reconciliation_and_gap(self):
  s=fixtures.Tests().spec();t=copy.deepcopy(s);t.update(start=s['end'],end='2026-06-30',asOf='2026-07-31',weightDate='2026-03-31');s['asOf']='2026-07-31';r=link({'asOf':'2026-07-31','periods':[s,t]});self.assertAlmostEqual(sum(r['effectsPp'].values()),r['activeReturnPp']);self.assertNotAlmostEqual(r['activeReturnPp'],12.4);t['start']='2026-04-01'
  with self.assertRaises(ValueError):link({'asOf':'2026-07-31','periods':[s,t]})
 def test_changed_benchmark_or_scope_blocks_link(self):
  for key in ['benchmarkId','portfolioId','weightScope','currency','industryVersion']:
   s=fixtures.Tests().spec();t=copy.deepcopy(s);s[key]='first';t[key]='second'
   with self.assertRaisesRegex(ValueError,key):link(dict(asOf=s['asOf'],periods=[s,t]))
 def test_unknown_comparability_is_explicit(self):
  s=fixtures.Tests().spec();r=link(dict(asOf=s['asOf'],periods=[s]));self.assertEqual(len(r['gaps']),4);self.assertEqual(r['comparabilityStatus'],'incomplete-declarations')
  s.update(benchmarkId='declared-index',portfolioId='fund',weightScope='equity-subportfolio',currency='CNY',industryVersion='declared-v1')
  r=link(dict(asOf=s['asOf'],periods=[s]));self.assertEqual(r['gaps'],[]);self.assertEqual(r['comparabilityStatus'],'declared-consistent-not-externally-verified')

class InterpretationTests(unittest.TestCase):
 def test_missing_scope_blocks_contribution_judgment(self):
  from attribution_link import interpret_link
  self.assertIn('暂不评价',interpret_link(dict(gaps=['unknown'])))
 def test_offsetting_contributions_not_capability_score(self):
  from attribution_link import interpret_link
  text=interpret_link(dict(gaps=[],activeReturnPp=0,effectsPp=dict(allocationPp=10,selectionPp=-10,interactionPp=0)))
  self.assertIn('相互抵消',text);self.assertIn('不把贡献除以',text)
 def test_largest_effect_sign_kept_and_personal_alpha_not_inferred(self):
  from attribution_link import interpret_link
  text=interpret_link(dict(gaps=[],activeReturnPp=-2,effectsPp=dict(allocationPp=1,selectionPp=-3,interactionPp=0)))
  self.assertIn('行业内选择',text);self.assertIn('负向',text);self.assertIn('不是基金真实交易',text)

if __name__=='__main__':unittest.main()
