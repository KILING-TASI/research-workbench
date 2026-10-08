import unittest
from decimal import Decimal
from fund_report_profit import statement_amount,validate_metadata,verify_currency_unit

class Tests(unittest.TestCase):
 def test_dash_requires_explicit_conditional_assumption(self):
  with self.assertRaisesRegex(ValueError,'不能自动填零'):statement_amount('-')
  self.assertEqual(statement_amount('-','assumed-zero-for-explicit-dash'),0)
 def test_comma_groups_and_sign_are_strict(self):
  self.assertEqual(statement_amount('-1,234.56'),Decimal('-1234.56'))
  for token in ['12,34.56','','NaN']:
   with self.assertRaises(ValueError):statement_amount(token)

class Preconditions(unittest.TestCase):
 def test_period_order(self):
  valid={'periodStart':'2025-01-01','periodEnd':'2025-12-31','publishedAt':'2026-03-31'}
  validate_metadata(valid)
  for change in [{'publishedAt':'2025-01-01'},{'periodStart':'2026-01-01'},{'reportDate':'2024-12-31'}]:
   with self.assertRaises(ValueError):validate_metadata({**valid,**change})
 def test_units(self):
  verify_currency_unit('金额单位：人民币元')
  for text in ['单位：人民币千元','无单位','单位：人民币元 单位：人民币万元']:
   with self.assertRaises(ValueError):verify_currency_unit(text)

if __name__=='__main__':unittest.main()
