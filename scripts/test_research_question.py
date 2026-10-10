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
    def test_unrecognized_name_gives_example_without_collection(self):
        r=self.execute({"question":"招商银行近三个月有哪些需要核对原文的公告？"})
        self.assertNotIn("eventResult",r)
        self.assertIn("查询招商银行",r["answer"])
        self.assertEqual(r["failureKind"],"request-needs-clarification")
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
    def test_missing_catalog_has_recovery_and_no_collection(self):
        def search(*a):return {'rows':[],'coverage':[{'kind':'stock','status':'missing-local-catalog'}]}
        r=self.execute({'question':'分析招商银行最近三个月公告'},search)
        self.assertEqual(r['failureKind'],'missing-local-catalog')
        self.assertTrue(r['nextSteps']);self.assertNotIn('eventResult',r)
    def test_online_identity_does_not_require_author_catalog(self):
        calls=[]
        def search(*a):
            calls.append(a)
            return {'rows':[{'kind':'stock','code':'600036','name':'招商银行','identityVerification':'third-party-candidate'}],'truncated':False}
        r=self.execute({'question':'分析招商银行最近三个月公告','onlineSearch':True,'items':[{'date':'2026-09-01','title':'行长任职资格核准公告'}]},search)
        self.assertTrue(calls[0][3]);self.assertEqual(r['resolvedSecurity']['code'],'600036')
        self.assertEqual(r['categoryCounts']['治理人事'],1)
        self.assertEqual(r['status'],'partial');self.assertEqual(r['facts'][0]['verification'],'metadata-not-original-verified')
if __name__=='__main__':unittest.main()
