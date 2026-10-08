import unittest,copy
from currency_price_bridge import translate
class Tests(unittest.TestCase):
 def test_finite_translated_prices_can_still_have_overflow_return(self):
  s=self.spec();s['asset']['history']=[dict(date='2026-01-01',close=1e-300),dict(date='2026-01-03',close=1e300)]
  with self.assertRaises(ValueError):translate(s)
 def test_invalid_shapes_rejected(self):
  for s in [None,[],{},dict(asset={},fx={})]:
   with self.assertRaises(ValueError):translate(s)
 def test_input_digest_changes_with_input_and_preserves_vintage(self):
  s=self.spec();s['fx']['currentVintageOnly']=True;s['fx']['historicalPublicationVerified']=False;r=translate(s);s['asset']['history'][0]['close']=101;r2=translate(s);self.assertNotEqual(r['inputProvenance']['assetInputSha256'],r2['inputProvenance']['assetInputSha256']);self.assertTrue(r['inputProvenance']['currentVintageOnly']);self.assertFalse(r['inputProvenance']['historicalPublicationVerified'])
 def test_cross_rate_components_checked_and_kept(self):
  s=self.spec();s['asset']['currency']='HKD';s['fx'].update(baseCurrency='HKD',unit='CNY-per-HKD')
  for x in s['fx']['history']:x.update(cnyPerUSD=x['value']*7.8,hkdPerUSD=7.8)
  r=translate(s);self.assertEqual(r['history'][0]['fxComponents']['hkdPerUSD'],7.8)
  s['fx']['history'][0]['cnyPerUSD']=1
  with self.assertRaises(ValueError):translate(s)
 def test_extra_source_must_be_url(self):
  s=self.spec();s['fx']['sources']=['not-a-source']
  with self.assertRaises(ValueError):translate(s)
 def spec(self):return dict(asOf='2026-01-03',asset=dict(market='US',code='TEST',currency='USD',sourceUrl='https://example.org/prices',historyBasis='provider-day-price-unadjusted-no-total-return-verification',history=[dict(date='2026-01-01',close=100),dict(date='2026-01-02',close=110),dict(date='2026-01-03',close=120)]),fx=dict(baseCurrency='USD',targetCurrency='CNY',unit='CNY-per-USD',publishedThrough='2026-01-03',sourceUrl='https://example.org/fx',basis='测试假设',history=[dict(date='2026-01-01',value=7),dict(date='2026-01-03',value=6.5)]))
 def test_same_day_and_multiplicative_change(self):
  r=translate(self.spec());self.assertEqual(r['missingFXDates'],['2026-01-02']);self.assertAlmostEqual(r['translatedPriceChangePct'],(780/700-1)*100);self.assertFalse(r['portfolioTotalReturnEligible'])
 def test_interaction_decomposition_reconciles_and_keeps_sign(self):
  r=translate(self.spec());b=r['priceChangeBreakdown']
  self.assertGreater(b['localPricePercentagePoints'],0);self.assertLess(b['fxPercentagePoints'],0);self.assertLess(b['interactionPercentagePoints'],0)
  self.assertAlmostEqual(sum(b[k] for k in ['localPricePercentagePoints','fxPercentagePoints','interactionPercentagePoints']),r['translatedPriceChangePct'])
 def test_reverse_unit_rejected(self):
  s=self.spec();s['fx']['unit']='USD-per-CNY'
  with self.assertRaises(ValueError):translate(s)
 def test_insufficient_no_fill(self):
  s=self.spec();s['fx']['history']=s['fx']['history'][:1]
  with self.assertRaises(ValueError):translate(s)
 def test_future_evidence_or_duplicate_rejected(self):
  s=self.spec();s['fx']['publishedThrough']='2027-01-01'
  with self.assertRaises(ValueError):translate(s)
  s=self.spec();s['fx']['history']*=2
  with self.assertRaises(ValueError):translate(s)
 def test_no_currency_or_total_return_relabel(self):
  s=self.spec();s['asset']['historyBasis']='total-return'
  with self.assertRaises(ValueError):translate(s)
if __name__=='__main__':unittest.main()
