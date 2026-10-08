import json,re,subprocess,unittest
from pathlib import Path
from decimal import Decimal
from generate_cash_plan import generate
from validation_resources import fixture_path

class AnnualCashAlignment(unittest.TestCase):
 def setUp(self):
  self.assets=Path(__file__).resolve().parents[1]/'assets'
  self.calendar=json.loads(fixture_path(self.assets,'bse-trading-calendar-2026.json').read_text(encoding='utf-8'))
 def annual(self,rows,capital,end):
  text=(self.assets/'bjx-workbench.js').read_text(encoding='utf-8')
  functions=text[text.index('function decimal('):text.index('function ceil(')]+text[text.index('function nextSaleScenarioDate('):text.index('function stage(')]+text[text.index('function annualReplay('):text.index('function drawChart(')]
  script="const fs=require('fs'),data=JSON.parse(fs.readFileSync(0,'utf8')),$=id=>({value:'0'});"+functions+";console.log(JSON.stringify(annualReplay("+str(capital)+",'2026')));"
  return json.loads(subprocess.check_output(['node','-e',script],input=json.dumps({'fetchedAt':end,'annualRecords':rows,'bseTradingCalendar':self.calendar}).encode()))
 def test_holiday_refund_not_reused_same_day(self):
  first={'code':'a','price':10,'maxShares':100,'minShares':100,'ratePct':50,'gainPct':0,'applyDate':'2026-09-30','refundDate':'2026-10-03','listingDate':'2026-10-09'}
  second={**first,'code':'b','applyDate':'2026-10-08','refundDate':'2026-10-09','ratePct':100,'gainPct':10}
  source={'fetchedAt':'2026-10-30','records':[first,second]}
  ledger=generate(source,{},self.calendar,'1000','2026-01-01','2026-10-30')
  result=self.annual(source['records'],1000,source['fetchedAt'])
  self.assertEqual(result['participated'],1)
  self.assertEqual(result['profit'],0)
  self.assertEqual(len(ledger['plan']['issues']),result['participated'])
 def test_actual_three_capitals_match_exact_cash_ledger(self):
  source=json.loads(fixture_path(self.assets,'data.json').read_text(encoding='utf-8'));overlays=json.loads(fixture_path(self.assets,'calendar-verified-fields.json').read_text(encoding='utf-8'))
  rows=[{**r,**overlays.get('records',{}).get(r['code'],{})} for r in source['records']]
  for capital in [500000,10000000,20000000]:
   result=self.annual(rows,capital,source['fetchedAt']);expected=generate(source,overlays,self.calendar,str(capital),'2026-01-01',source['fetchedAt'][:10])
   self.assertEqual(result['participated'],len(expected['plan']['issues']))
   self.assertAlmostEqual(result['profit'],float(Decimal(expected['ledger']['endCash'])-capital),places=7)
 def test_year_end_cutoff_does_not_require_next_year_calendar(self):
  self.assertEqual(self.annual([],1000,'2026-12-31')['profit'],0)
 def test_just_below_allocation_boundary_not_rounded_up(self):
  row={'code':'a','price':10,'maxShares':10000,'minShares':100,'ratePct':0.9999999999,'gainPct':10,'applyDate':'2026-09-01','refundDate':'2026-09-03','listingDate':'2026-09-04'}
  source={'fetchedAt':'2026-10-03','records':[row]}
  expected=generate(source,{},self.calendar,'100000','2026-01-01','2026-10-03')
  self.assertEqual(expected['plan']['issues'][0]['allocatedWholeLotShares'],'0')
  self.assertEqual(self.annual([row],100000,'2026-10-03')['profit'],0)

if __name__=='__main__':unittest.main()
