import unittest
from company_financial_report import sample_commentary
class Tests(unittest.TestCase):
 def spec(self,size,valid,missing,value):return dict(period='2026-06-30',groups=[dict(group='指定池',classificationVersion='v1',scope='consolidated',currency='CNY',sampleSize=size,changes={'revenue':{'yoy':dict(validCount=valid,missingCount=missing,median=value)}})])
 def test_single_not_industry(self):
  lines,_=sample_commentary(self.spec(1,1,0,.1));self.assertIn('不能作横向比较','\n'.join(lines))
 def test_missing_not_zero(self):
  lines,groups=sample_commentary(self.spec(3,2,1,.2));self.assertIn('未按零处理','\n'.join(lines));self.assertEqual(groups[0]['entries'][0]['median'],.2)
 def test_all_missing_no_number(self):
  lines,groups=sample_commentary(self.spec(2,0,2,None));self.assertIn('未计算样本中位数','\n'.join(lines));self.assertIsNone(groups[0]['entries'][0]['median'])
 def test_count_mismatch_rejected(self):
  with self.assertRaises(ValueError):sample_commentary(self.spec(3,2,2,.2))
if __name__=='__main__':unittest.main()
