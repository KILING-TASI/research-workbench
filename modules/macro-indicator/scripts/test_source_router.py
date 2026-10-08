import unittest,json
from unittest.mock import patch
from source_router import compatible
from social_increment import fetch

class SourceComparison(unittest.TestCase):
 def row(self,value=1):return dict(definition='同口径',unit='%',currency='不适用',algorithm_version='v1',data_period='2026-10-01',value=value)
 def test_nonfinite_or_boolean_does_not_get_consistent_label(self):
  for value in [float('inf'),float('nan'),True]:
   with self.subTest(value=value):
    ok,reason=compatible(self.row(value),self.row(value));self.assertFalse(ok);self.assertNotEqual(reason,'一致')
 def test_missing_definition_is_not_comparable(self):
  a=self.row();a.pop('definition');b=dict(a);self.assertFalse(compatible(a,b)[0])
 def test_time_difference_uses_full_duration(self):
  a=self.row();b=self.row();a['data_period']='2026-10-01T00:00:00';b['data_period']='2026-10-02T23:00:00';self.assertFalse(compatible(a,b)[0])
  b['data_period']='2026-10-02T00:00:00';self.assertTrue(compatible(a,b)[0])
 def test_same_period_conflict_is_not_overwritten(self):
  with patch('social_increment.get_text',return_value=json.dumps([dict(date='202608',tiosfs=1),dict(date='202608',tiosfs=2)])):
   with self.assertRaisesRegex(ValueError,'冲突'):fetch('2026-10-08')
 def test_exact_duplicate_and_nonfinite_rows(self):
  rows=[dict(date='202608',tiosfs=1),dict(date='202608',tiosfs=1),dict(date='202609',tiosfs=float('inf'))]
  with patch('social_increment.get_text',return_value=json.dumps(rows)):
   result=fetch('2026-10-08');self.assertEqual(len(result),1);self.assertIsNone(result[0]['publishedAt'])
if __name__=='__main__':unittest.main()
