import unittest,tempfile,json
from pathlib import Path
from appraisal_contract import coverage,validate_details,ROLES
from observation_calendar import assess
from financial_research_pipeline import appraisal_summary
from source_health import run

class Tests(unittest.TestCase):
 def test_whitespace_or_untyped_judgments_do_not_cover_report(self):
  entries=[dict(basis='research-explanation',role=role,conclusion='判断',alternatives=['另一解释'],invalidationSignal='反证') for role in ROLES]
  for key,value in [('conclusion',' '),('conclusion',True),('alternatives',[' ']),('alternatives','guess'),('invalidationSignal',' ')]:
   changed=[dict(e) for e in entries]
   target='business' if key=='alternatives' else 'falsification'
   next(e for e in changed if e['role']==target)[key]=value
   with self.subTest(key=key,value=value):self.assertEqual(coverage(changed)['status'],'partial')
  with self.assertRaises(ValueError):coverage([None])
 def calendar(self):return dict(start='2026-09-28',end='2026-10-06',dates=['2026-09-28','2026-09-29','2026-09-30'],market='SSE',sourceUrl='https://www.sse.com.cn/calendar',applicabilityConfirmed=True)
 def test_no_commentary_is_data_only(self):
  self.assertEqual(coverage([])['status'],'data-only')
  self.assertEqual(appraisal_summary(None,['601138'])['companies'][0]['status'],'data-only')
 def test_quotes_and_labels_do_not_prove_appraisal_complete(self):
  r=coverage([dict(basis='company-statement',role=r,conclusion='数值') for r in ROLES]);self.assertEqual(r['status'],'partial');self.assertEqual(r['missingRoles'],list(ROLES))
 def test_causal_alternative_and_invalidation_required(self):
  entries=[dict(basis='research-explanation',role=r,conclusion='判断') for r in ROLES]
  self.assertEqual(coverage(entries)['status'],'partial')
  for e in entries:
   e['alternatives']=['另一解释待核实'];e['invalidationSignal']='现金兑现转弱'
  self.assertEqual(coverage(entries)['status'],'covered-awaiting-semantic-review')
 def test_invalid_details_rejected(self):
  for entry in [dict(role='unknown'),dict(alternatives='guess'),dict(alternatives=['']),dict(invalidationSignal='')]:
   with self.assertRaises(ValueError):validate_details(entry)
 def test_holiday_not_missing_and_calendar_scope(self):
  cal=self.calendar();r=assess(cal['dates'],cal['start'],cal['end'],cal,'SSE');self.assertEqual(r['coveragePct'],100);self.assertEqual(r['lastExpectedDate'],'2026-09-30')
  with self.assertRaises(ValueError):assess(cal['dates'],'2026-09-01',cal['end'],cal,'SSE')
  with self.assertRaises(ValueError):assess(cal['dates'],cal['start'],cal['end'],cal,'HK')
 def test_missing_dates_not_filled(self):
  cal=self.calendar();r=assess(['2026-09-28','2026-09-30'],cal['start'],cal['end'],cal,'SSE');self.assertEqual(r['missingDates'],['2026-09-29']);self.assertEqual(r['status'],'date-gaps')
 def test_unconfirmed_and_empty_calendar_not_100(self):
  cal=self.calendar();cal['applicabilityConfirmed']=False
  self.assertIsNone(assess(cal['dates'],cal['start'],cal['end'],cal,'SSE')['coveragePct'])
  cal['applicabilityConfirmed']=True;cal['dates']=[]
  self.assertEqual(assess([],'2026-10-01',cal['end'],cal,'SSE')['status'],'no-observation-days')
 def test_health_rejects_gap_for_alternative_but_holiday_is_fresh(self):
  cal=self.calendar();spec={'asOf':cal['end'],'requests':[{'profile':'cn-history-eastmoney','code':'512800','market':'1','start':cal['start'],'maxLagDays':0,'calendar':cal}]}
  def raw(days):return json.dumps({'data':{'code':'512800','name':'银行ETF','klines':[d+',1,1,1,1,100,100' for d in days]}}).encode()
  with tempfile.TemporaryDirectory() as d:
   r=run(spec,Path(d)/'full',lambda *a,**k:raw(cal['dates']));self.assertEqual(r['rows'][0]['freshness']['status'],'within-threshold');self.assertTrue(r['alternatives'])
   r=run(spec,Path(d)/'gap',lambda *a,**k:raw(['2026-09-28','2026-09-30']));self.assertEqual(r['status'],'partial');self.assertEqual(r['alternatives'],[])
class DownstreamCalendarTests(unittest.TestCase):
 def test_shared_missing_day_still_blocks_annualization(self):
  from research_pipeline import compare
  dates=['2026-09-28','2026-09-30']
  calendar=Tests().calendar()
  document=dict(asOf=calendar['end'],start=calendar['start'],rows=[dict(code=c,comparisonGroup='指定池',basis='nav-with-distributions',frequency='trading_day',calendar=calendar,calendarMarket='SSE',history=[dict(date=d,nav=1+i*.01) for i,d in enumerate(dates)]) for c in ['a','b']])
  result=compare(document)
  self.assertEqual(result['alignment'][0]['excludedObservations'],0)
  self.assertEqual(result['alignment'][0]['calendarCheck']['missingDates'],['2026-09-29'])
  self.assertIsNone(result['rows'][0]['annualizedVolPct'])
  self.assertIn('日历',result['rows'][0]['volatilityUnavailableReason'])
 def test_calendar_cannot_be_used_for_another_market(self):
  from research_pipeline import compare
  cal=Tests().calendar()
  document=dict(asOf=cal['end'],start=cal['start'],rows=[dict(code=c,comparisonGroup='指定池',basis='nav-with-distributions',calendar=cal,calendarMarket='HK',history=[dict(date=d,nav=1) for d in cal['dates']]) for c in ['a','b']])
  with self.assertRaises(ValueError):compare(document)
if __name__=='__main__':unittest.main()

