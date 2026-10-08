import unittest,copy
from fund_dca import calculate,schedule,xirr
class DcaTests(unittest.TestCase):
 def test_missing_fees_are_disclosed_and_incomplete_event_rejected(self):
  from fund_dca import markdown
  s=self.sample();self.assertIn('按零申购费假设',markdown(calculate(s)))
  s['plans'][0]['subscriptionFeePct']=0;self.assertNotIn('申购费率未声明',markdown(calculate(s)))
  s=self.sample();del s['events'][0]['cashPerOldUnit'];del s['events'][0]['newUnitsPerOldUnit']
  with self.assertRaisesRegex(ValueError,'未披露'):calculate(s)
 def sample(self):
  return dict(code='000001',asOf='2025-03-31',start='2025-01-31',end='2025-03-31',sourceUrl='https://example.org/nav',eventCoverage='verified-complete',eventEvidence='fixture',history=[{'date':d,'nav':n} for d,n in [('2025-01-31',1),('2025-02-28',1),('2025-03-01',.5),('2025-03-31',.5)]],events=[dict(date='2025-03-01',cashPerOldUnit=0,newUnitsPerOldUnit=2,sourceUrl='https://example.org/split')],plans=[dict(name='monthly',frequency='monthly',mode='amount',value=100,distribution='reinvest')])
 def test_month_anchor(self):self.assertEqual(schedule('2025-01-31','2025-03-31','monthly'),['2025-01-31','2025-02-28','2025-03-31'])
 def test_split_preserves_assets(self):
  r=calculate(self.sample())['plans'][0];self.assertAlmostEqual(r['endingTotalAssets'],300);self.assertEqual(r['periods'],3);self.assertAlmostEqual(r['xirrPct'],0,places=5)
 def test_fixed_units_fee(self):
  s=self.sample();s['plans'][0].update(mode='units',value=100,subscriptionFeePct=1)
  r=calculate(s)['plans'][0];self.assertAlmostEqual(r['totalContribution'],252.5);self.assertAlmostEqual(r['endingTotalAssets'],250)
 def test_cash_vs_reinvest(self):
  s=self.sample();s['events'][0].update(cashPerOldUnit=.5,newUnitsPerOldUnit=1);s['history'][-1]['nav']=1
  s['plans']=[dict(name=d,frequency='monthly',mode='amount',value=100,distribution=d) for d in ['cash','reinvest']]
  a,b=calculate(s)['plans'];self.assertAlmostEqual(a['endingTotalAssets'],400);self.assertAlmostEqual(b['endingTotalAssets'],500)
 def test_unknown_event_coverage(self):
  s=self.sample();s['eventCoverage']='unknown'
  with self.assertRaises(ValueError):calculate(s)
 def test_xirr_known(self):self.assertAlmostEqual(xirr([('2023-01-01',-100),('2024-01-01',110)]),(1.1**(365.25/365)-1)*100,places=6)
 def test_no_backward_fill(self):
  s=self.sample();s['history']=s['history'][1:]
  with self.assertRaises(ValueError):calculate(s)
 def test_schedule_gap_disclosed_and_guarded(self):
  s=self.sample();s['plans'][0]['frequency']='weekly'
  r=calculate(s);self.assertGreater(max(x['calendarDays'] for x in r['plans'][0]['scheduleDelays']),7)
  s['maxScheduleDelayDays']=7
  with self.assertRaises(ValueError):calculate(s)
 def test_stale_valuation_guard(self):
  s=self.sample();s['end']='2025-03-20';r=calculate(s);self.assertEqual(r['valuationAgeDays'],19)
  s['maxValuationAgeDays']=7
  with self.assertRaises(ValueError):calculate(s)
 def test_limit_validation(self):
  for v in [True,-1,1.5,'7']:
   s=self.sample();s['maxScheduleDelayDays']=v
   with self.assertRaises(ValueError):calculate(s)
 def test_zero_delay_allowed(self):
  s=self.sample();s.update(maxScheduleDelayDays=0,maxValuationAgeDays=0)
  r=calculate(s);self.assertEqual(r['plans'][0]['scheduleDelays'],[])
 def test_events_must_be_explicit(self):
  for value in [None,{},'none']:
   s=self.sample();s['events']=value
   with self.assertRaises(ValueError):calculate(s)
  s=self.sample();del s['events']
  with self.assertRaises(ValueError):calculate(s)
 def test_evidence_must_be_text(self):
  for value in [True,{},'  ']:
   s=self.sample();s['eventEvidence']=value
   with self.assertRaises(ValueError):calculate(s)
 def test_declaration_not_certification(self):
  from fund_dca import markdown
  s=self.sample();r=calculate(s)
  self.assertEqual(r['eventVerificationStatus'],'input-declared-not-independently-verified')
  self.assertIn('程序未独立核验',markdown(r))
  s['eventCoverage']='assumed-complete';r=calculate(s)
  self.assertEqual(r['eventVerificationStatus'],'explicit-completeness-assumption')
  self.assertIn('完整性假设',markdown(r))
 def test_delayed_reinvestment(self):
  s=self.sample();s['events'][0].update(cashPerOldUnit=.5,newUnitsPerOldUnit=1,reinvestDate='2025-03-31');s['history'][-1]['nav']=1
  r=calculate(s)['plans'][0];self.assertAlmostEqual(r['endingTotalAssets'],400)
  event=next(x for x in r['ledger'] if x['kind']=='distribution-or-split');self.assertEqual(event['eligibleOldUnits'],200)
  settle=next(x for x in r['ledger'] if x['kind']=='dividend-reinvestment');self.assertEqual(settle['date'],'2025-03-31');self.assertEqual(settle['purchasedUnits'],100)
 def test_pending_reinvestment_retained(self):
  s=self.sample();s['events'][0].update(cashPerOldUnit=.5,newUnitsPerOldUnit=1,reinvestDate='2025-04-01')
  r=calculate(s)['plans'][0];self.assertEqual(r['endingCashEntitlement'],100);self.assertEqual(r['pendingReinvestment'][0]['cashEntitlement'],100)
 def test_invalid_reinvestment_date(self):
  for d in ['2025-02-28','2025-03-02']:
   s=self.sample();s['events'][0]['reinvestDate']=d
   with self.assertRaises(ValueError):calculate(s)
 def test_cash_only_blocks_reinvest(self):
  s=self.sample();s['events'][0].update(cashPerOldUnit=.5,distributionPolicy='cash-only',policyEvidence='fixture cash-only clause')
  with self.assertRaises(ValueError):calculate(s)
  s['plans'][0]['distribution']='cash';self.assertEqual(calculate(s)['distributionPolicyStatus'],'all-input-declared')
 def test_policy_evidence_required(self):
  s=self.sample();s['events'][0]['distributionPolicy']='cash-only'
  with self.assertRaises(ValueError):calculate(s)
 def test_unknown_policy_disclosed(self):
  from fund_dca import markdown
  self.assertIn('分红方式未完整登记',markdown(calculate(self.sample())))
 def test_cash_only_split_without_cash_allowed(self):
  s=self.sample();s['events'][0].update(distributionPolicy='cash-only',policyEvidence='fixture');calculate(s)
if __name__=='__main__':unittest.main()
