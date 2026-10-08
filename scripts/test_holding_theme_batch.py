import unittest
from holding_theme_batch import run
import test_report_screen_bridge as fixture
class Tests(unittest.TestCase):
 def spec(self):
  r=fixture.Tests().sample();r['asOf']='2026-10-03';return dict(asOf='2026-10-03',theme='测试',classificationVersion='test-v1',minimumWeightPctOfNAV=20,dossiers=[dict(code=r['code'],asOf='2026-10-03',report=r),dict(code='000002',asOf='2026-10-03')])
 def test_partial_keeps_denominator(self):
  r=run(self.spec());self.assertEqual(r['candidateCount'],2);self.assertEqual(len(r['results']),1);self.assertEqual(len(r['gaps']),1);self.assertIsNone(r['results'][0]['thresholdCheck']['passed'])
 def test_duplicate_rejected(self):
  s=self.spec();s['dossiers'].append(s['dossiers'][0]);
  with self.assertRaises(ValueError):run(s)
 def test_nonobject_dossier_rejected(self):
  s=self.spec();s['dossiers']=[None]
  with self.assertRaisesRegex(ValueError,'条目'):run(s)
if __name__=='__main__':unittest.main()
