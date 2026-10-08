import unittest
from macro_asset_observation import changes,validate_series_contract,SERIES
class FxTests(unittest.TestCase):
 def series(self,id):return dict(id=id,**SERIES[id],status='available',points=[dict(date='2026-09-24',value=7.0),dict(date='2026-09-25',value=7.2)])
 def test_inverse_return_not_sign_flip(self):
  fx=changes(self.series('DEXCHUS'))['exchangeRateBasis'];self.assertEqual(fx['baseCurrency'],'USD');self.assertEqual(fx['quoteCurrency'],'CNY');self.assertAlmostEqual(fx['directChange'],7.2/7-1);self.assertAlmostEqual(fx['inverseChange'],7/7.2-1);self.assertNotAlmostEqual(fx['inverseChange'],-fx['directChange'])
 def test_euro_direction_and_mislabeled_unit_rejected(self):
  s=self.series('DEXUSEU');self.assertEqual(changes(s)['exchangeRateBasis']['baseCurrency'],'EUR');s['unit']='EUR-per-USD'
  with self.assertRaises(ValueError):validate_series_contract([s],True)
 def test_zero_fx_and_missing_prior(self):
  s=self.series('DEXCHUS');s['points'][0]['value']=0
  with self.assertRaises(ValueError):changes(s)
  s['points']=s['points'][1:];self.assertIsNone(changes(s)['exchangeRateBasis']['directChange'])
