import unittest
from public_issuance_data import normalize
class Provider(unittest.TestCase):
 def base(self):return {'SECURITY_CODE':'920001','SECURITY_NAME_ABBR':'example','ISSUE_PRICE':10,'APPLY_NUM_UPPER':10000,'APPLY_AMT_UPPER':100000}
 def test_unlisted_performance_not_fabricated(self):
  r=self.base();r['LD_CLOSE_CHANGE']=20;r['CAPTURE_PROFIT']=5
  result=normalize([r])['records'][0];self.assertIsNone(result['gainPct']);self.assertIsNone(result['approxAnnualPct'])
 def test_duplicates_and_nonfinite_rejected(self):
  with self.assertRaises(ValueError):normalize([self.base(),self.base()])
  r=self.base();r['ISSUE_PRICE']='NaN'
  with self.assertRaises(ValueError):normalize([r])
 def test_declared_total_mismatch_rejected(self):
  from public_issuance_data import fetch
  from unittest.mock import patch
  with patch('public_issuance_data._page',return_value={'result':{'data':[self.base()],'pages':1,'count':2}}):
   with self.assertRaisesRegex(ValueError,'实际记录数'):fetch()
  with patch('public_issuance_data._page',side_effect=[{'result':{'data':[self.base()],'pages':2,'count':2}},{'result':{'data':[self.base()],'pages':2,'count':3}}]):
   with self.assertRaisesRegex(ValueError,'记录总数变化'):fetch()
 def test_fund_units_checked(self):
  r=self.base();r['APPLY_AMT_UPPER']=100
  with self.assertRaises(ValueError):normalize([r])
if __name__=='__main__':unittest.main()
