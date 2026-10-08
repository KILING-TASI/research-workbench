import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch
from refresh import refresh
from observation_brief import brief
class HistoryFreshness(unittest.TestCase):
 def run_case(self,period):
  with tempfile.TemporaryDirectory() as root:
   old={'period':'2026-08','value':5,'sourceUrl':'https://www.stats.gov.cn/old','fetched_at':'2026-09-15T00:00:00+08:00'}
   row={'id':'x','name':'测试','frequency':'月','value':5,'history':[old],'fetched_at':old['fetched_at'],'missing':None}
   p=Path(root);(p/'data.json').write_text(json.dumps({'indicators':[row]}),'utf-8')
   incoming={'period':period,'value':3,'sourceUrl':'https://www.stats.gov.cn/new'}
   with patch('refresh.fetch_all',return_value=({'x':[incoming]},{},{})):return refresh(p)
 def test_older_only_does_not_retimestamp_latest(self):
  d=self.run_case('2026-07');r=d['indicators'][0]
  self.assertEqual(r['value'],5);self.assertEqual(r['fetched_at'],'2026-09-15T00:00:00+08:00');self.assertEqual(r['previous'],3);self.assertEqual(d['fetchHealth']['fresh'],0);self.assertEqual(d['fetchHealth']['historyOnly'],1);self.assertIn('仅补充历史期间',brief(d))
 def test_current_period_refresh_is_fresh(self):
  d=self.run_case('2026-08');self.assertEqual(d['fetchHealth']['fresh'],1);self.assertEqual(d['fetchHealth']['historyOnly'],0);self.assertEqual(d['indicators'][0]['value'],3)
 def test_newer_period_refresh_is_fresh(self):
  d=self.run_case('2026-09');self.assertEqual(d['indicators'][0]['data_period'],'2026-09');self.assertEqual(d['fetchHealth']['fresh'],1)
