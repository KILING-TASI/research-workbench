from validation_resources import fixture_path
import json,subprocess,unittest
from decimal import Decimal
from pathlib import Path
from generate_repo_scenario import schedule
class BrowserRepo(unittest.TestCase):
 def test_optional_empty_event_lists_and_invalid_shape(self):
  assets=Path(__file__).resolve().parents[1]/'assets'
  js="require(process.argv[1]);const m=require(process.argv[2]);const p={capital:'100000',start:'2026-10-08',end:'2026-10-12'},c={year:2026,closedRanges:[]};const r=m.schedule(p,c,'3.65');if(!r.plan.repos.length||p.repos!==undefined)throw Error('缺省或原输入变更');for(const bad of [{...p,issues:null},{...p,repos:{}}]){let rejected=false;try{m.schedule(bad,c,'3.65')}catch(e){rejected=/记录须为数组/.test(e.message)}if(!rejected)throw Error('错误记录未拒绝')}console.log('ok')"
  self.assertEqual(subprocess.check_output(['node','-e',js,str(assets/'cash-ledger.js'),str(assets/'cash-repo-plan.js')]).strip(),b'ok')
 def test_weekend_and_fee_cross_engine(self):
  assets=Path(__file__).resolve().parents[1]/'assets';plan={'capital':'100000','start':'2026-10-08','end':'2026-10-12','issues':[],'repos':[]};calendar={'year':2026,'closedRanges':[]}
  js="require(process.argv[1]);const m=require(process.argv[2]);console.log(JSON.stringify(m.schedule("+json.dumps(plan)+','+json.dumps(calendar)+",'3.65','100','1')))"
  actual=json.loads(subprocess.check_output(['node','-e',js,str(assets/'cash-ledger.js'),str(assets/'cash-repo-plan.js')]))
  expected=schedule(plan,calendar,'3.65',100,1)
  self.assertEqual(Decimal(actual['incrementalEndCash']),Decimal(expected['incrementalEndCash']))
  self.assertEqual(actual['plan']['repos'][0]['availableDate'],'2026-10-12');self.assertEqual(len(actual['plan']['repos']),1)
 def test_markup_connected(self):
  assets=Path(__file__).resolve().parents[1]/'assets';s=fixture_path(assets,'bjx-panel.html').read_text(encoding='utf-8')
  self.assertEqual(s.count('id="ledgerRepo"'),1);self.assertLess(s.index('src="cash-repo-plan.js"'),s.index('src="bjx-workbench.js"'))
if __name__=='__main__':unittest.main()
