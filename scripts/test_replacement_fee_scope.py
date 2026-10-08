import unittest
from unittest.mock import patch
from replacement_research import evaluate
class Tests(unittest.TestCase):
 @patch('replacement_research.evaluate_layers',return_value={})
 def test_invalid_evidence_source_or_time_cannot_support_savings(self,_):
  for change in [{'sourceUrl':'https://user:secret@example.com/fee'},{'sourceUrl':'https://example.com/ fee'},{'observedAt':'2026-10-02','availableAt':'2026-10-01'}]:
   d=self.data()
   for key in ['current','candidate']:d[key]['annualFeePct']['components']=['management','custody']
   d['candidate']['annualFeePct'].update(change)
   r=evaluate(d);self.assertIsNone(r['annualFeeSaving']);self.assertFalse(any(e['code']=='510310' and e['field']=='annualFeePct' for e in r['evidence']))
 def data(self):
  def product(code,fee):return {'code':code,'currency':'CNY','annualFeePct':{'value':fee,'observedAt':'2026-10-01','availableAt':'2026-10-01','sourceUrl':'https://example.com/fee','locator':'费用表','verification':'official-reviewed'}}
  return {'asOf':'2026-10-08','current':product('510300',.6),'candidate':product('510310',.2),'positionCurrency':'CNY','positionValue':100000,'holdingYears':3}
 @patch('replacement_research.evaluate_layers',return_value={})
 def test_missing_components_withhold_savings(self,_):
  r=evaluate(self.data());self.assertIsNone(r['annualFeeSaving']);self.assertIsNone(r['feeOnlyBreakevenYears']);self.assertTrue(any('覆盖项缺失' in g for g in r['evidenceGaps']))
 @patch('replacement_research.evaluate_layers',return_value={})
 def test_identical_explicit_components_allow_cost_only_calculation(self,_):
  d=self.data()
  for key in ['current','candidate']:d[key]['annualFeePct']['components']=['management','custody']
  r=evaluate(d);self.assertAlmostEqual(r['annualFeeSaving'],400);self.assertIn('暂缓判断',r['decision'])
 @patch('replacement_research.evaluate_layers',return_value={})
 def test_different_components_withhold_savings(self,_):
  d=self.data();d['current']['annualFeePct']['components']=['management','custody'];d['candidate']['annualFeePct']['components']=['management']
  self.assertIsNone(evaluate(d)['annualFeeSaving'])

 @patch('replacement_research.evaluate_layers',return_value={})
 def test_bad_research_date_rejected(self,_):
  for date in ['20261008','2026-W41-4']:
   d=self.data();d['asOf']=date
   with self.assertRaises(ValueError):evaluate(d)
 @patch('replacement_research.evaluate_layers',return_value={})
 def test_tracking_count_not_numeric_integer_is_gap(self,_):
  for count in ['130',True,130.5]:
   d=self.data()
   for key in ['current','candidate']:
    d[key]['tracking']={'value':{'basis':'nav-total-return-minus-index-total-return','start':'2025-01-01','end':'2026-09-30','count':count,'indexId':'000300'},'observedAt':'2026-10-01','availableAt':'2026-10-01','sourceUrl':'https://example.com/tracking','locator':'跟踪结果','verification':'third-party-observed'}
   r=evaluate(d);self.assertFalse(r['trackingComparable']);self.assertTrue(any('跟踪质量' in g for g in r['evidenceGaps']))
