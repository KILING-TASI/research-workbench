import json,subprocess,unittest
from pathlib import Path
from decimal import Decimal
from generate_cash_plan import generate
from validation_resources import fixture_path
class BrowserPlan(unittest.TestCase):
 def test_three_capitals_all_events_match_python(self):
  assets=Path(__file__).resolve().parents[1]/'assets';read=lambda name:json.loads(fixture_path(assets,name).read_text(encoding='utf-8'))
  source=read('data.json');overlays=read('calendar-verified-fields.json');calendar=read('bse-trading-calendar-2026.json');end=min('2026-10-03',source['fetchedAt'][:10]);capitals=['500000','10000000','20000000']
  spec={'source':source,'overlays':overlays,'calendar':calendar,'end':end,'capitals':capitals}
  js="const fs=require('fs');require(process.argv[1]);const m=require(process.argv[2]),s=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(s.capitals.map(c=>m.generate(s.source,s.overlays,s.calendar,c,'2026-01-01',s.end))))"
  actual=json.loads(subprocess.check_output(['node','-e',js,str(assets/'cash-ledger.js'),str(assets/'cash-plan.js')],input=json.dumps(spec).encode()))
  for capital,result in zip(capitals,actual):
   expected=generate(source,overlays,calendar,capital,'2026-01-01',end)
   self.assertEqual([x['id'] for x in expected['plan']['issues']],[x['id'] for x in result['plan']['issues']])
   self.assertEqual(len(expected['excluded']),len(result['excluded']))
   self.assertEqual(len(expected['ledger']['steps']),len(result['ledger']['steps']))
   for a,b in zip(expected['ledger']['steps'],result['ledger']['steps']):
    self.assertEqual(a['date'],b['date']);self.assertEqual(a['kind'],b['kind']);self.assertEqual(Decimal(a['balance']),Decimal(b['balance']))
   self.assertEqual(Decimal(expected['ledger']['endCash']),Decimal(result['ledger']['endCash']))
 def test_page_entry_connected(self):
  assets=Path(__file__).resolve().parents[1]/'assets';text=fixture_path(assets,'bjx-panel.html').read_text(encoding='utf-8')
  self.assertEqual(text.count('id="ledgerAuto"'),1)
  self.assertLess(text.index('src="cash-plan.js"'),text.index('src="bjx-workbench.js"'))
if __name__=='__main__':unittest.main()
