from validation_resources import fixture_path
import json,subprocess,unittest
from pathlib import Path
class CoverageWarning(unittest.TestCase):
 def test_warning_changes_with_year_before_calculation(self):
  assets=Path(__file__).resolve().parents[1]/'assets';s=(assets/'bjx-workbench.js').read_text(encoding='utf-8');fn=s[s.index('function annualCalculate()'):s.index("$('annualRun').onclick")]
  js="const data={bseTradingCalendar:{year:2026}},nodes={};function $(id){return nodes[id]||(nodes[id]={value:'invalid',replaceChildren(){}})};"+fn+";const out=[];for(const y of ['2025','2026']){$('annualYear').value=y;annualCalculate();out.push($('calendarCoverage').textContent)}console.log(JSON.stringify(out))"
  result=json.loads(subprocess.check_output(['node','-e',js]));self.assertIn('自然日假设',result[0]);self.assertIn('本页载入的北交所交易日历',result[1]);self.assertIn('不代表券商实际到账',result[1]);self.assertNotIn('已核验',result[1])
  self.assertEqual(fixture_path(assets,'bjx-panel.html').read_text(encoding='utf-8').count('id="calendarCoverage"'),1)
if __name__=='__main__':unittest.main()
