import unittest
from cash_flow_reconciliation import direct_cash_bridge
class DirectCashTests(unittest.TestCase):
 def spec(self):
  return ([{'key':'sales','direction':'inflow','current':'100.00','prior':'90.00'},{'key':'purchases','direction':'outflow','current':'80.00','prior':'60.00'}],{'current':{'inflow':'100.00','outflow':'80.00','net':'20.00'},'prior':{'inflow':'90.00','outflow':'60.00','net':'30.00'}})
 def test_outflow_contribution(self):
  rows,totals=self.spec();r=direct_cash_bridge(rows,totals);self.assertEqual(r['netChange'],'-10.00');self.assertEqual(r['rows'][1]['netChangeContribution'],'-20.00');self.assertFalse(r['originalVerified'])
 def test_missing_not_zero(self):
  rows,totals=self.spec();rows[0]['prior']=None;r=direct_cash_bridge(rows,totals);self.assertEqual(r['status'],'missing-data');self.assertIsNone(r['netChange'])
 def test_net_agreement_does_not_hide_wrong_subtotals(self):
  rows,totals=self.spec();totals['current'].update(inflow='110.00',outflow='90.00');self.assertEqual(direct_cash_bridge(rows,totals)['status'],'reconciliation-mismatch')
 def test_duplicate_and_unknown_direction(self):
  rows,totals=self.spec()
  with self.assertRaises(ValueError):direct_cash_bridge(rows+[rows[0]],totals)
  rows[0]['direction']='net'
  with self.assertRaises(ValueError):direct_cash_bridge(rows,totals)
 def test_explicit_negative_retained(self):
  rows,totals=self.spec();rows[1]['current']='-5.00';totals['current'].update(outflow='-5.00',net='105.00');self.assertEqual(direct_cash_bridge(rows,totals)['netChange'],'75.00')
 def test_malformed_money_rejected(self):
  for value in ('1,00.00','1e3','10%','NaN','Infinity','','—',' 10.00','−10.00',True,10):
   with self.subTest(value=value):
    rows,totals=self.spec();rows[0]['current']=value
    with self.assertRaises(ValueError):direct_cash_bridge(rows,totals)
 def test_valid_grouped_decimal(self):
  rows,totals=self.spec();rows[0]['current']='1,100.00';totals['current'].update(inflow='1100.00',net='1020.00');self.assertEqual(direct_cash_bridge(rows,totals)['netChange'],'990.00')
if __name__=='__main__':unittest.main()
