import copy,unittest,tempfile
from pathlib import Path
from portfolio_contribution_report import markdown,export

class Tests(unittest.TestCase):
 def test_malformed_structures_and_sources_fail_clearly(self):
  for key,value in [('assets',None),('assets',[None]),('alignment',[]),('worstDrawdown',None),('evidenceGaps','缺分红'),('limitations','历史模拟')]:
   data=self.fixture();data[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):markdown(data)
  for document in [None,[]]:
   with self.assertRaises(ValueError):markdown(document)
  data=self.fixture();data['assets'][0]['sourceUrl']='https://user:password@example.org'
  with self.assertRaises(ValueError):markdown(data)
 def test_episode_dates_must_belong_to_same_research_window(self):
  for change in [('start','2024-12-31'),('end','2025-02-02'),('start','2025-02-01')]:
   data=self.fixture();data['worstDrawdown'][change[0]]=change[1]
   with self.subTest(change=change),self.assertRaises(ValueError):markdown(data)
 def test_contribution_units_and_distinct_windows_explained(self):
  text=markdown(self.fixture());self.assertIn('不是未来亏损概率',text);self.assertIn('负值表示该段拖累',text);self.assertIn('不互相抵消',text)
 def fixture(self):return dict(type='portfolio-return-risk-contributions',alignment=dict(start='2025-01-01',end='2025-02-01',observations=4),totalReturnPct=0,annualVolatilityPct=0,worstDrawdown=dict(start='2025-01-01',end='2025-01-01',maximumDrawdownPct=0),assets=[dict(code='a',weight=1,returnContributionPp=0,volatilityContributionPp=None,riskSharePct=None,worstDrawdownContributionPp=0,sourceUrl='https://example.org')],evidenceGaps=['分红资料未核验'],limitations=['历史模拟'])
 def test_export_contains_real_table(self):
  from research_brief_html import render
  html=render(markdown(self.fixture()))
  self.assertEqual(html.count('<table>'),1)
  self.assertIn('<td class="align-right">100.00%</td>',html)
  self.assertNotIn('<p>|',html)
 def test_zero_volatility_has_no_invented_share(self):
  text=markdown(self.fixture());self.assertIn('资料不足',text);self.assertIn('分红资料未核验',text);self.assertNotIn('nan',text)
 def test_inconsistent_contribution_blocks_export_before_files(self):
  with tempfile.TemporaryDirectory() as d:
   for key in ['weight','returnContributionPp','worstDrawdownContributionPp']:
    data=self.fixture();data['assets'][0][key]=2;out=Path(d)/key
    with self.assertRaises(ValueError):export(data,out)
    self.assertFalse(out.exists())
 def test_boolean_and_duplicate_asset_rejected(self):
  data=self.fixture();data['assets'][0]['returnContributionPp']=True
  with self.assertRaises(ValueError):markdown(data)
 def test_negative_risk_contribution_allowed_but_share_must_reconcile(self):
  data=self.fixture();data['annualVolatilityPct']=10
  data['assets'][0].update(weight=.5,volatilityContributionPp=-2,riskSharePct=-20)
  second=copy.deepcopy(data['assets'][0]);second.update(code='b',volatilityContributionPp=12,riskSharePct=120);data['assets'].append(second)
  self.assertIn('-20.00%',markdown(data))
  self.assertIn('b承担最多波动风险',markdown(data));self.assertIn('高于资金占比',markdown(data))
  data['assets'][1]['riskSharePct']=100
  with self.assertRaises(ValueError):markdown(data)
 def test_zero_volatility_does_not_accept_fabricated_share(self):
  data=self.fixture();data['assets'][0]['riskSharePct']=100
  with self.assertRaises(ValueError):markdown(data)
  data=self.fixture();data['assets'].append(copy.deepcopy(data['assets'][0]))
  with self.assertRaises(ValueError):markdown(data)

class FreshnessTests(unittest.TestCase):
 def test_snapshot_changed_not_labeled_current(self):
  from portfolio_contribution_report import freshness_note
  self.assertIn('需要重新计算',freshness_note(dict(impactStatus='stale')))
  self.assertIn('未重新采集远程资料',freshness_note(dict(impactStatus='unchanged-for-registered-dependencies')))
