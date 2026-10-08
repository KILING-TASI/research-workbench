import unittest,copy
from holding_theme_exposure import calculate,markdown,threshold_check
import test_report_screen_bridge as report_fixture
class Tests(unittest.TestCase):
 def test_threshold_unknown_not_zero(self):
  self.assertIsNone(threshold_check([0,50],20)['passed']);self.assertTrue(threshold_check([20,50],20)['passed']);self.assertFalse(threshold_check([0,19],20)['passed']);self.assertIsNone(threshold_check([0,20],20)['passed'])
 def test_threshold_validation(self):
  for value in [-1,101,True,float('nan')]:
   with self.assertRaises((ValueError,TypeError)):threshold_check([0,50],value)
 def spec(self):return dict(asOf='2026-10-03',theme='测试主题',classificationVersion='test-v1',report=report_fixture.Tests().sample(),classifications=[])
 def classification(self):return dict(code='600519',market='CN-equity',sourceUrl='https://example.org/classification',publishedAt='2026-01-01',effectiveFrom='2025-01-01',classificationVersion='test-v1',quote='测试分类依据',locator='p2',themes=['测试主题'])
 def test_missing_is_interval_not_zero(self):
  r=calculate(self.spec());self.assertEqual(r['stockThemeWeightBoundsPctOfNAV'],[0,50]);self.assertEqual(r['classificationCoveragePctOfEquity'],0);self.assertIsNone(r['rows'][0]['belongsToTheme'])
 def test_matching_evidence(self):
  s=self.spec();s['classifications']=[self.classification()];r=calculate(s);self.assertEqual(r['stockThemeWeightBoundsPctOfNAV'],[50,50]);self.assertIn('https://example.org/classification',markdown(r))
 def test_explicit_nonmatch(self):
  s=self.spec();x=self.classification();x['themes']=[];s['classifications']=[x];r=calculate(s);self.assertEqual(r['stockThemeWeightBoundsPctOfNAV'],[0,0]);self.assertEqual(r['classificationCoveragePctOfEquity'],100)
 def test_future_validity_is_unknown(self):
  s=self.spec();x=self.classification();x['effectiveFrom']='2026-01-01';s['classifications']=[x];self.assertEqual(calculate(s)['unclassifiedWeightPctOfNAV'],50)
 def test_expired_classification_retained_not_applied(self):
  s=self.spec();x=self.classification();x['effectiveTo']='2025-06-30';s['classifications']=[x]
  r=calculate(s);row=r['rows'][0]
  self.assertIsNone(row['belongsToTheme']);self.assertIsNone(row['classificationEvidence'])
  self.assertEqual(row['unusedClassificationEvidence'],x)
  self.assertEqual(row['classificationStatus'],'分类在报告日前已失效')
  self.assertIn('2025-06-30',markdown(r));self.assertEqual(r['stockThemeWeightBoundsPctOfNAV'],[0,50])
 def test_missing_vs_not_yet_effective(self):
  s=self.spec();self.assertEqual(calculate(s)['rows'][0]['classificationStatus'],'未提供该证券分类')
  x=self.classification();x['effectiveFrom']='2026-01-01';s['classifications']=[x]
  self.assertEqual(calculate(s)['rows'][0]['classificationStatus'],'分类在报告日尚未生效')
 def test_duplicate_version_or_future_evidence_rejected(self):
  for change in [dict(classificationVersion='other'),dict(publishedAt='2027-01-01'),dict(quote='')]:
   s=self.spec();s['classifications']=[dict(self.classification(),**change)]
   with self.subTest(change=change),self.assertRaises(ValueError):calculate(s)
  s=self.spec();s['classifications']=[self.classification(),self.classification()]
  with self.assertRaises(ValueError):calculate(s)
 def test_bounds_reject_invalid_or_nonfinite(self):
  for bounds in [[],[-1,10],[20,10],[0,float('inf')]]:
   with self.assertRaises(ValueError):threshold_check(bounds,5)
 def test_bad_classification_shape_and_blank_evidence(self):
  for classifications in [{},[None],[dict(self.classification(),quote=' ')],[dict(self.classification(),themes=[' '])]]:
   s=self.spec();s['classifications']=classifications
   with self.assertRaises(ValueError):calculate(s)
if __name__=='__main__':unittest.main()
