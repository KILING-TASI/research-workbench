import unittest
from contract_maturity_review import calculate,token_value
class Tests(unittest.TestCase):
 def test_dash_is_not_unconditional_zero(self):
  for token in ['—','-']:
   with self.assertRaisesRegex(ValueError,'不能自动填零'):token_value(token)
   self.assertEqual(token_value(token,'assumed-zero-for-explicit-dash'),0)
  with self.assertRaises(ValueError):token_value('')
 def test_totals(self):
  self.assertEqual(calculate([dict(label="应付",amounts=["2","3","0","5"])],dict(amounts=["2","3","0","5"]))["columnTotals"],["2","3","0","5"])
 def test_row_wrong(self):
  with self.assertRaisesRegex(ValueError,"行内"):calculate([dict(label="应付",amounts=[2,3,0,6])],dict(amounts=[2,3,0,5]))
 def test_column_wrong(self):
  with self.assertRaisesRegex(ValueError,"列合计"):calculate([dict(label="应付",amounts=[2,3,0,5])],dict(amounts=[3,2,0,5]))
 def test_missing_not_zero(self):
  with self.assertRaises(ValueError):calculate([dict(label="应付",amounts=[None,3,0,3])],dict(amounts=[0,3,0,3]))
 def test_negative_or_infinite(self):
  for value in ["-1","NaN","Infinity",True]:
   with self.assertRaises(ValueError):calculate([dict(label="应付",amounts=[value,3,0,3])],dict(amounts=[0,3,0,3]))
 def test_duplicate(self):
  with self.assertRaisesRegex(ValueError,"重复"):calculate([dict(label="应付",amounts=[0,0,0,0])]*2,dict(amounts=[0,0,0,0]))

 def test_five_columns_and_zero_label_total(self):
  r=calculate([dict(label="租赁",amounts=[1,2,3,4,10])],dict(label="",amounts=[1,2,3,4,10]),5)
  self.assertEqual(r["columnTotals"],["1","2","3","4","10"])
 def test_column_number_not_inferred(self):
  with self.assertRaisesRegex(ValueError,"列金额"):calculate([dict(label="租赁",amounts=[1,2,3,4,10])],dict(amounts=[1,2,3,4,10]))
