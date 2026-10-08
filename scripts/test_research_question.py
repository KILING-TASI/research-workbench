import tempfile,unittest,json
from pathlib import Path
from research_question import run
class Router(unittest.TestCase):
    def search(self,*args):return {'rows':[{'kind':'stock','code':'600036','name':'招商银行','identityVerification':'test-candidate'}],'truncated':False}
    def execute(self,spec,search=None):
        with tempfile.TemporaryDirectory() as folder:
            result=run({'asOf':'2026-10-03',**spec},folder,search or self.search)
            self.assertTrue(Path(result['archivePath']).exists())
            return result
    def test_name_window(self):
        r=self.execute({'question':'分析招商银行最近三个月公告','items':[{'date':'2026-09-01','title':'拟回购公告'}]})
        self.assertEqual(r['eventResult']['start'],'2026-07-03');self.assertEqual(r['status'],'partial');self.assertIn('待补',r['answer'])
    def test_ambiguous(self):
        def search(*a):return {'rows':[{'kind':'stock','code':'600036','name':'招商银行'},{'kind':'stock','code':'000001','name':'招商银行'}]}
        self.assertEqual(self.execute({'question':'分析招商银行公告'},search)['status'],'needs-clarification')
    def test_window_conflict(self):
        r=self.execute({'question':'分析600036近三个月公告','months':1});self.assertNotIn('eventResult',r)
    def test_unsupported_not_routed(self):
        r=self.execute({'question':'比较两只基金的历史收益'});self.assertEqual(r['status'],'unsupported')
    def test_trade_not_answered(self):
        r=self.execute({'question':'分析600036公告，可以买入吗','items':[]});self.assertEqual(r['status'],'data-unavailable');self.assertEqual(r['facts'],[])
    def test_code_conflict(self):
        r=self.execute({'question':'分析600036公告','code':'000001'});self.assertNotIn('eventResult',r)
    def test_unsupported_days(self):
        r=self.execute({'question':'分析600036最近90天公告'});self.assertNotIn('eventResult',r)
if __name__=='__main__':unittest.main()
