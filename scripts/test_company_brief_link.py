import unittest,tempfile,json
from pathlib import Path
from company_one_page import financial_review,valuation_review
class Tests(unittest.TestCase):
 def files(self,p,asof='2026-10-05'):
  (p/'fin.json').write_text(json.dumps(dict(period='2026-06-30',companies=[dict(code='600031')])))
  (p/'original.json').write_text(json.dumps(dict(asOf=asof,companies=[])))
  return dict(financialResult=str(p/'fin.json'),originalResult=str(p/'original.json'),archives=[])
 def test_wrong_target_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with self.assertRaisesRegex(ValueError,'目标证券'):financial_review(self.files(p),dict(code='000425',market='CN'),'2026-10-05')
 def test_future_original_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with self.assertRaisesRegex(ValueError,'晚于'):financial_review(self.files(p,'2026-10-06'),dict(code='600031',market='CN'),'2026-10-05')
 def test_non_cn_not_coerced(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)
   with self.assertRaisesRegex(ValueError,'A股'):financial_review(self.files(p),dict(code='AAPL',market='US'),'2026-10-05')
 def test_future_valuation_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'value.json';p.write_text(json.dumps(dict(currency='CNY',asOf='2026-10-06')))
   with self.assertRaisesRegex(ValueError,'晚于'):valuation_review(p,dict(code='600031',market='CN'),'2026-10-05')
if __name__=='__main__':unittest.main()
