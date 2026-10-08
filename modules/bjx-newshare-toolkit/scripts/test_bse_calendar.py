import json,subprocess,unittest
from pathlib import Path
from trading_calendar import next_open
from validation_resources import fixture_path
class BseCalendar(unittest.TestCase):
 def test_frontend_and_backend_holiday_dates(self):
  assets=Path(__file__).resolve().parents[1]/'assets';c=json.loads(fixture_path(assets,'bse-trading-calendar-2026.json').read_text(encoding='utf-8'))
  self.assertEqual(c['market'],'BSE');self.assertEqual(c['verificationStatus'],'original-calendar-rechecked')
  dates=['2026-09-30','2026-10-09','2026-02-13'];expected=['2026-10-08','2026-10-12','2026-02-24']
  self.assertEqual([next_open(x,c) for x in dates],expected)
  source=(assets/'bjx-workbench.js').read_text(encoding='utf-8');helper=source[source.index('function nextSaleScenarioDate'):source.index('function stage(r,t)')]
  js='const data='+json.dumps({'bseTradingCalendar':c})+';'+helper+';console.log(JSON.stringify('+json.dumps(dates)+'.map(nextSaleScenarioDate)))'
  actual=json.loads(subprocess.check_output(['node','-e',js]));self.assertEqual(actual,expected)
if __name__=='__main__':unittest.main()
