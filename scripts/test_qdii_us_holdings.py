import unittest
from qdii_us_holdings import parse_row,reported_groups
from decimal import Decimal
class Tests(unittest.TestCase):
 def row(self):return ["3","Alphabet Inc","Alphabet股份有限公司","GOOGL US","纳斯达克","美国","10","20.00","1.00"]
 def test_dual_class_not_deduplicated(self):
  first,last,_=parse_row(self.row(),None);raw=[None,None,None,"GOOG US","纳斯达克","美国","5","10.00","0.50"];second,_,_=parse_row(raw,last);self.assertEqual(first["rank"],second["rank"]);self.assertNotEqual(first["securityCode"],second["securityCode"])
 def test_split_code_preserves_original(self):
  raw=self.row();raw[3]="A VGO US";row,_,_=parse_row(raw,None);self.assertEqual(row["securityCode"],"US:AVGO");self.assertEqual(row["rawSecurityCell"],"A VGO US")
 def test_orphan_subrow_rejected(self):
  raw=self.row();raw[:3]=[None]*3
  with self.assertRaisesRegex(ValueError,"歧义"):parse_row(raw,None)
 def test_other_market_not_coerced(self):
  raw=self.row();raw[3]="0700 HK"
  with self.assertRaisesRegex(ValueError,"市场"):parse_row(raw,None)
 def test_fragment_kept_as_fragment(self):
  row,last,kind=parse_row(["","Holdings Inc","","","克","","","",""],None);self.assertEqual(kind,"fragment");self.assertIsNone(row)
 def test_negative_and_fractional_quantity_rejected(self):
  raw=self.row();raw[7]="-20.00"
  with self.assertRaises(ValueError):parse_row(raw,None)
  raw=self.row();raw[6]="1.5"
  with self.assertRaisesRegex(ValueError,"整数"):parse_row(raw,None)

 def test_report_group_aggregates_class_values(self):
  a,last,_=parse_row(self.row(),None);b,_,_=parse_row([None,None,None,"GOOG US","纳斯达克","美国","5","10.00","0.50"],last);groups=reported_groups([a,b],Decimal("100"));self.assertEqual(groups[0]["value"],"30.00");self.assertEqual(groups[0]["navPct"],"30.00");self.assertEqual(groups[0]["securityCodes"],["US:GOOGL","US:GOOG"])
 def test_report_group_name_conflict_rejected(self):
  a,_,_=parse_row(self.row(),None);b=dict(a,securityCode="US:GOOG",reportedChinese="不同公司")
  with self.assertRaisesRegex(ValueError,"名称冲突"):reported_groups([a,b],Decimal("100"))

 def test_group_invalid_denominator_rejected(self):
  row,_,_=parse_row(self.row(),None)
  for nav in [Decimal('0'),Decimal('-1'),Decimal('NaN'),Decimal('Infinity'),True]:
   with self.assertRaises(ValueError):reported_groups([row],nav)
 def test_cli_json_duplicate_and_nonfinite_rejected(self):
  from qdii_us_holdings import load_json
  for text in ['{"nav":1,"nav":2}','{"nav":NaN}','{"nav":1e999}']:
   with self.assertRaises(ValueError):load_json(text)
