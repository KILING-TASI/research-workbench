import unittest,copy
from multidimensional_screen import screen,markdown
class Tests(unittest.TestCase):
 def test_price_and_nav_drawdown_not_interchangeable(self):
  s=self.sample();s['candidates'][0]['fields']['maximumDrawdownPct']=dict(value=18,unit='pct',basis='unadjusted-close-price',window='2025-01-02/2026-09-30',observedAt='2026-09-30',sourceUrl='https://example.org')
  s['conditions']=[dict(kind='metric',field='maximumDrawdownPct',op='lt',value=20)]
  self.assertTrue(screen(s)['unknown'])
  s['conditions'][0].update(basis='reinvested-nav',window='2025-01-02/2026-09-30');self.assertTrue(screen(s)['unknown'])
  s['conditions'][0]['basis']='unadjusted-close-price';self.assertTrue(screen(s)['selected'])
 def test_equity_scope_cannot_exclude_bond(self):
  s=self.sample();h=s['candidates'][0]['holdings'];h.update(complete=True,scope='completeEquity');s['conditions'][0].update(code='019740',market='CN-bond');self.assertEqual(len(screen(s)['unknown']),1)
 def test_explicit_namespace_blocks_other_market(self):
  s=self.sample();h=s['candidates'][0]['holdings'];h.update(complete=True,coveredSecurityNamespaces=['CN-equity']);self.assertEqual(len(screen(s)['unknown']),1)
 def test_complete_equity_absent_stock(self):
  s=self.sample();h=s['candidates'][0]['holdings'];h.update(complete=True,scope='completeEquity',coveredSecurityNamespaces=['CN-equity','HK-equity']);s['conditions'][0].update(code='600000',market='CN-equity');self.assertEqual(len(screen(s)['excluded']),1)
 def sample(self):return {'asOf':'2026-10-03','candidates':[{'kind':'etf','market':'SSE','code':'588000','fields':{'aumCNY':{'value':100,'observedAt':'2025-06-30','basis':'NAV-assets','unit':'CNY','sourceUrl':'https://example.org'}},'holdings':{'value':[{'code':'688981','market':'SSE','weightPct':10}],'complete':False,'observedAt':'2025-06-30','basis':'actual-fund-holdings','sourceUrl':'https://example.org'}}],'conditions':[{'kind':'holding','code':'688981','market':'SSE'}]}
 def test_reverse(self):self.assertEqual(len(screen(self.sample())['selected']),1)
 def test_missing_partial(self):
  s=self.sample();s['conditions'][0]['code']='600000';self.assertEqual(len(screen(s)['unknown']),1)
 def test_complete_absence(self):
  s=self.sample();s['candidates'][0]['holdings']['complete']=True;s['conditions'][0]['code']='600000';self.assertEqual(len(screen(s)['excluded']),1)
 def test_proxy_rejected(self):
  s=self.sample();s['candidates'][0]['holdings']['basis']='index-constituents';self.assertEqual(len(screen(s)['unknown']),1)
 def test_sort_isolation(self):
  s=self.sample();b=copy.deepcopy(s['candidates'][0]);b['code']='510300';b['fields']['aumCNY']['observedAt']='2025-12-31';s['candidates'].append(b);s['rank']={'field':'aumCNY','direction':'desc'};self.assertEqual(len(screen(s)['rankingGroups']),2)
 def test_performance_rank_requires_window(self):
  s=self.sample();s['rank']=dict(field='returnPct',direction='desc')
  s['candidates'][0]['fields']['returnPct']=dict(value=10,unit='pct',basis='reinvested-nav',observedAt='2025-06-30',sourceUrl='https://example.org')
  r=screen(s);self.assertFalse(r['rankingGroups']);self.assertIn('统计区间',r['rankingGaps'][0]['reason'])
  s['candidates'][0]['fields']['returnPct']['window']='2025-01-01/2025-06-30';self.assertTrue(screen(s)['rankingGroups'])
 def test_blank_or_boolean_basis_not_evidence(self):
  for basis in [' ',True]:
   s=self.sample();s['candidates'][0]['holdings']['basis']=basis
   self.assertTrue(screen(s)['unknown'])
 def test_wrong_units_unknown_not_pass(self):
  s=self.sample();s['conditions']=[dict(kind='metric',field='maximumDrawdownPct',op='lt',value=20)]
  s['candidates'][0]['fields']['maximumDrawdownPct']=dict(value=.3,unit='ratio',observedAt='2025-06-30',basis='history',sourceUrl='https://example.org')
  r=screen(s);self.assertEqual(len(r['unknown']),1);self.assertIn('单位',r['unknown'][0]['checks'][0]['reason'])
 def test_wrong_currency_unknown(self):
  s=self.sample();s['conditions']=[dict(kind='metric',field='aumCNY',op='gt',value=10)];s['candidates'][0]['fields']['aumCNY']['unit']='USD';self.assertEqual(len(screen(s)['unknown']),1)
 def test_invalid_threshold_rejected_even_missing(self):
  for threshold in [True,float('nan'),'20']:
   s=self.sample();s['conditions']=[dict(kind='metric',field='maximumDrawdownPct',op='lt',value=threshold)]
   with self.assertRaises((ValueError,TypeError)):screen(s)
 def test_rule_unit_requires_explicit_conversion(self):
  s=self.sample();s['conditions']=[dict(kind='metric',field='aumCNY',op='gt',value=10,unit='USD')]
  with self.assertRaises(ValueError):screen(s)
 def test_wrong_unit_not_ranked(self):
  s=self.sample();s['rank']=dict(field='aumCNY',direction='desc');s['candidates'][0]['fields']['aumCNY']['unit']='USD';r=screen(s)
  self.assertFalse(r['rankingGroups']);self.assertTrue(r['rankingGaps'])
 def test_flow_requires_window_and_basis(self):
  s=self.sample();s['candidates'][0]['fields']['netFlowCNY']=dict(value=100,unit='CNY',basis='proxy',window='2025-06-29/2025-06-30',observedAt='2025-06-30',sourceUrl='https://example.org')
  s['conditions']=[dict(kind='metric',field='netFlowCNY',op='gt',value=0)]
  self.assertTrue(screen(s)['unknown'])
  s['conditions'][0].update(basis='proxy',window='2025-06-29/2025-06-30');self.assertTrue(screen(s)['selected'])
  s['conditions'][0]['basis']='actual-settlement';self.assertTrue(screen(s)['unknown'])
 def test_report_preserves_unknown_and_scope(self):
  s=self.sample();s['conditions'][0]['code']='600000';text=markdown(screen(s),s)
  self.assertIn('资料不足1项',text);self.assertIn('局部披露未出现',text);self.assertIn('不代表七个维度全部齐备',text)
 def test_report_table_escape(self):
  s=self.sample();s['candidates'][0]['name']='名称|测试';self.assertIn('名称／测试',markdown(screen(s),s))
 def test_report_actual_values_and_invalid_values_not_displayed(self):
  s=self.sample();s['conditions']=[dict(kind='metric',field='aumCNY',op='gt',value=110)]
  text=markdown(screen(s),s);self.assertIn('100 元 | 不满足',text);self.assertIn('大于110 元',text)
  s['candidates'][0]['fields']['aumCNY']['value']=999999;s['candidates'][0]['fields']['aumCNY']['observedAt']='2027-01-01'
  text=markdown(screen(s),s);self.assertNotIn('999999',text);self.assertIn('资料不足 | 不可判定',text)
 def test_same_index_unknown_not_grouped(self):
  s=self.sample();s['rank']=dict(field='aumCNY',direction='desc',sameIndexOnly=True);r=screen(s)
  self.assertFalse(r['rankingGroups']);self.assertIn('跟踪指数',r['rankingGaps'][0]['reason'])
 def test_future(self):
  s=self.sample();s['candidates'][0]['holdings']['observedAt']='2027-01-01'
  r=screen(s);self.assertTrue(r['unknown']);self.assertIn('证据不可核验',r['unknown'][0]['checks'][0]['reason'])
if __name__=='__main__':unittest.main()
