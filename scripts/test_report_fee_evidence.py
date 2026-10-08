import unittest,tempfile
from pathlib import Path
from report_fee_evidence import statements,sales_service_statements,extract_archive
class Tests(unittest.TestCase):
 def test_relative_source_changed_hash_rejected_before_parsing(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'original.pdf';p.write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'哈希'):
    extract_archive(dict(status='副本身份已匹配',documentPath='original.pdf',sha256='0'*64),d)
 def test_share_sales_rate_and_explicit_zero(self):
  r=sales_service_statements([(30,'本基金A类基金份额不收取销售服务费，C类基金份额的销售服务费按前一日C类基金份额的基金资产净值的0.50%的年费率计提。')])
  self.assertEqual(r['A']['value'],0);self.assertEqual(r['C']['value'],.5)
 def test_annual_class_rate(self):
  r=sales_service_statements([(29,'本基金C类基金份额的年销售服务费费率为0.80%')]);self.assertEqual(r['C']['value'],.8);self.assertIsNone(r['A']['value'])
 def test_prospectus_annual_rate_word_order(self):
  r=sales_service_statements([(72,'本基金A类基金份额不收取销售服务费，C类基金份额的销售服务费年费率为0.80%')]);self.assertEqual(r['C']['value'],.8);self.assertEqual(r['A']['value'],0)
 def test_nonannual_rate_remains_unmatched(self):
  self.assertIsNone(sales_service_statements([(1,'C类基金份额的销售服务费费率为0.8%')])['C']['value'])
 def test_related_party_amounts_are_not_rates(self):
  r=sales_service_statements([(29,'销售服务费合计455,205.43，C类基金份额持有比例0.80%')]);self.assertIsNone(r['C']['value'])
 def test_sales_conflict_retained(self):
  r=sales_service_statements([(1,'C类基金份额的年销售服务费费率为0.8%'),(2,'C类基金份额的年销售服务费费率为0.5%')]);self.assertIsNone(r['C']['value']);self.assertEqual(len(r['C']['evidence']),2)
 def test_single(self):
  r=statements([(47,'基金管理费按前一日基金资产净值的 1.20%年费率计提。')]);self.assertEqual(r['管理费']['value'],1.2);self.assertFalse(r['管理费']['currentEffectiveVerified'])
 def test_etf_explicit_wordings(self):
  r=statements([(27,'本基金的管理费按前一日基金资产净值的0.15%年费率计提。本基金的托管费按前一日基金资产净值的0.05%的年费率计提。')])
  self.assertEqual(r['管理费']['value'],.15);self.assertEqual(r['托管费']['value'],.05)
  r=statements([(32,'基金管理人报酬按前一日基金资产净值0.15%的年费率计提。基金托管费按前一日基金资产净值0.05%的年费率计提。')])
  self.assertEqual(r['管理费']['value'],.15);self.assertEqual(r['托管费']['value'],.05)
 def test_invesco_wordings(self):
  r=statements([(42,'支付基金管理人的管理人报酬按前一日基金资产净值1.00%的年费率计提'),(43,'支付基金托管人的托管费按前一日基金资产净值0.20%的年费率计提')]);self.assertEqual(r['管理费']['value'],1.0);self.assertEqual(r['托管费']['value'],.2)
 def test_conflict(self):
  r=statements([(1,'基金管理费按前一日基金资产净值的1.20%年费率计提'),(2,'基金管理费按前一日基金资产净值的0.60%年费率计提')]);self.assertIsNone(r['管理费']['value']);self.assertIn('冲突',r['管理费']['status'])
 def test_no_reverse(self):self.assertIsNone(statements([(1,'管理费总额1.20元')])['管理费']['value'])
 def test_efund_wording(self):
  r=statements([(37,'在通常情况下，基金管理费按前一日基金资产净值的年费率计提。本基金年管理费率为1.2%')]);self.assertEqual(r['管理费']['value'],1.2);self.assertIn('通常情况下',r['管理费']['evidence'][0]['context'])
 def test_other_rate_not_fee(self):self.assertIsNone(statements([(1,'本基金年收益率为1.2%，托管机构持股0.2%')])['管理费']['value'])
if __name__=='__main__':unittest.main()
