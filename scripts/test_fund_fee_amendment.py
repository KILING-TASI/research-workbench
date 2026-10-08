import unittest
from fund_fee_amendment import fee_row,markdown
class Tests(unittest.TestCase):
 def test_invalid_fee_range(self):
  for value in ['100.01%','9'*400+'%']:
   rows=self.rows();rows[2][2]=value
   with self.subTest(value=value),self.assertRaises(ValueError):fee_row(rows,'某基金')
 def test_report_distinguishes_dates(self):
  r=dict(fundFullName='某基金',publishedAt='2023-07-08',effectiveFrom='2023-07-10',asOf='2026-10-03',feeEvidence=dict(beforeManagementPct=1.5,afterManagementPct=1.2,beforeCustodyPct=.25,afterCustodyPct=.2,page=2),effectiveDateEvidence=[dict(page=1,quote='自2023年7月10日起')],sourceUrl='https://example.org',limitations=['不认定当前有效费率'],riskNotice='历史不代表未来')
  t=markdown(r);self.assertIn('公告披露日2023-07-08；生效日2023-07-10',t);self.assertIn('不认定当前有效费率',t);self.assertIn('PDF第2页',t)
 def rows(self):return [['序号','基金名称','调整前',None,'调整后',None],[None,None,'管理费率','托管费率','管理费率','托管费率'],['1','某基金','1.50%','0.25%','1.20%','0.20%']]
 def test_exact_name_not_substring(self):self.assertEqual(len(fee_row(self.rows(),'某基金')),1);self.assertFalse(fee_row(self.rows(),'某'))
 def test_wrong_column_not_guess(self):
  r=self.rows();r[1][2]='申购费'
  with self.assertRaises(ValueError):fee_row(r,'某基金')
if __name__=='__main__':unittest.main()
