import unittest
from fund_report_industries import international_taxonomy
class Tests(unittest.TestCase):
 def test_explicit_gics(self):self.assertEqual(international_taxonomy('采用GICS标准'),'GICS')
 def test_generic_international_not_gics_claim(self):self.assertEqual(international_taxonomy('采用彭博提供的国际通用行业分类标准'),'report-native-international')
 def test_ambiguous_not_inferred(self):self.assertIsNone(international_taxonomy('行业分布'))
if __name__=='__main__':unittest.main()
