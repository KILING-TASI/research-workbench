import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from company_financial_report import load_quarter_reviews

class QuarterLink(unittest.TestCase):
 def financial(self):return dict(period='2026-06-30',companies=[dict(code='600406',metadata={'unit':'元'})])
 def test_supplied_review_is_reverified_against_this_archive(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'review.json';p.write_text(json.dumps({'code':'600406'}),encoding='utf-8');archive={'600406':{'code':'600406'}}
   with patch('quarter_original_review.verified_saved_result',return_value={'code':'600406','fields':[]}) as verify:
    r=load_quarter_reviews([str(p)],self.financial(),archive)
   verify.assert_called_once_with(str(p),archive['600406'],{'unit':'元'},'2026-06-30');self.assertIn('600406',r)
 def test_unknown_duplicate_and_stale_reviews_are_not_ignored(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'review.json';p.write_text(json.dumps({'code':'000001'}),encoding='utf-8')
   with self.assertRaises(ValueError):load_quarter_reviews([str(p)],self.financial(),{})
   with self.assertRaises(ValueError):load_quarter_reviews([str(p),str(p)],self.financial(),{})
   p.write_text(json.dumps({'code':'600406'}),encoding='utf-8')
   with patch('quarter_original_review.verified_saved_result',side_effect=ValueError('方法已变更')):
    with self.assertRaisesRegex(ValueError,'方法已变更'):load_quarter_reviews([str(p)],self.financial(),{'600406':{}})
 def test_no_quarter_review_is_an_explicit_empty_scope(self):self.assertEqual(load_quarter_reviews([],self.financial(),{}),{})
if __name__=='__main__':unittest.main()
