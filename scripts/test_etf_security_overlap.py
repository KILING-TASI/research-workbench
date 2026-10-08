import unittest
from etf_evaluation import evaluate_layers
class SecurityTests(unittest.TestCase):
 def result(self,left,right,metric=False):
  def fact(rows):return dict(value=rows,observedAt='2026-06-30',availableAt='2026-08-01',sourceUrl='https://example.org/report',locator='table',verification='official-reviewed',basis='fund-holdings')
  d=dict(asOf='2026-10-06',positionCurrency='CNY',positionValue=100,holdingYears=1,current=dict(code='A',constituents=fact(left)),candidate=dict(code='B',constituents=fact(left)),portfolio=[dict(code='held',constituents=fact(right))])
  r=evaluate_layers(d)
  m=next(m for layer in r['products'][0]['layers'] for m in layer['metrics'] if m['id']=='overlap')
  return m if metric else m['value'][0]
 def row(self,market='SSE',code='123456',share='ordinary',weight=1):return dict(market=market,code=code,shareClass=share,weight=weight)
 def test_same_code_different_market(self):self.assertEqual(self.result([self.row()],[self.row('HKEX')])['overlapPct'],0)
 def test_missing_identity_is_gap(self):self.assertIsNone(self.result([dict(code='123456',weight=1)],[dict(code='123456',weight=1)])['overlapPct'])
 def test_share_class_separate(self):self.assertEqual(self.result([self.row()],[self.row(share='preferred')])['overlapPct'],0)
 def test_explicit_namespace_same_security(self):
  left=self.row();right=self.row('CN-exchange-unresolved');left['securityNamespace']=right['securityNamespace']='CN-equity';self.assertEqual(self.result([left],[right])['overlapPct'],100)
 def test_unresolved_identity_not_displayed_as_calculated(self):
  m=self.result([dict(code='123456',weight=1)],[dict(code='123456',weight=1)],metric=True)
  self.assertEqual(m['status'],'待补证据');self.assertIn('证券市场',m['gap'])
 def test_zero_overlap_is_a_valid_calculation(self):
  m=self.result([self.row()],[self.row('HKEX')],metric=True)
  self.assertEqual(m['status'],'已计算');self.assertEqual(m['gap'],'')
if __name__=='__main__':unittest.main()

