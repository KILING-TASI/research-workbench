import unittest
from appraisal_contract import validate_details
class JudgmentTests(unittest.TestCase):
 def test_fields_preserved(self):
  d=dict(coreTension='增长与现金兑现之间的矛盾',positioning='适用于跟踪增长质量',judgmentBoundary='仅限财报观察')
  self.assertEqual(validate_details(d),d)
 def test_invalid_fields(self):
  for key in ['coreTension','positioning','judgmentBoundary']:
   for v in ['',True,[], 'a'*361,'<script>','a\nb']:
    with self.assertRaises(ValueError):validate_details({key:v})
 def test_no_invented_defaults(self):self.assertEqual(validate_details({}),{})
if __name__=='__main__':unittest.main()
