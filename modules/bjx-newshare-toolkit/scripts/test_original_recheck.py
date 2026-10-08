import unittest
from recheck_original_evidence import numeric_matches, issuer_code_matches,original_span
class Original(unittest.TestCase):
 def test_raw_grouping_preserved_and_negative_not_reinterpreted(self):
  self.assertFalse(numeric_matches('price',123,'发行价格为1,23元/股'))
  self.assertTrue(numeric_matches('price',1230,'发行价格为1,230元/股'))
  self.assertFalse(numeric_matches('maxShares',100,'申购上限为-100股'))
  raw=original_span('申购上限为1,23股。','申购上限为123股')
  self.assertIn('1,23',raw);self.assertFalse(numeric_matches('maxShares',123,raw))
  with self.assertRaises(ValueError):original_span('发行价格为10元/股；发行价格为10元/股','发行价格为10元/股')
 def test_exact_units_and_context(self):
  self.assertTrue(numeric_matches('maxShares',1231400,'申购上限不超过网上发行数量的5%，即123.1400万股。'))
  self.assertFalse(numeric_matches('maxShares',1231400,'申购上限123.1400股。'))
  self.assertTrue(numeric_matches('ratePct',.0294520509,'网上获配比例为0.0294520509%。'))
  self.assertFalse(numeric_matches('ratePct',.02945205,'网上获配比例为0.0294520509%。'))
 def test_unrelated_number_not_evidence(self):
  self.assertFalse(numeric_matches('price',14.21,'发行费用14.21元/股'))
  self.assertFalse(numeric_matches('ratePct',1,'营业利润率为1%'))
 def test_conflicting_values_fail_even_when_one_matches(self):
  self.assertFalse(numeric_matches('price',4.33,'发行价格为4.33元/股；发行价格为4.34元/股。'))
  self.assertFalse(numeric_matches('ratePct',.11,'网上获配比例为0.11%；网上配售比例为0.12%。'))
  self.assertTrue(numeric_matches('price',4.33,'发行价格为4.33元/股；发行价格为4.330元/股。'))
 def test_code_inside_another_number_is_not_identity(self):
  self.assertFalse(issuer_code_matches('920019','联系电话19200190'))
  self.assertTrue(issuer_code_matches('920019','证券代码：920019证券简称：铜冠矿建'))
if __name__=='__main__':unittest.main()
