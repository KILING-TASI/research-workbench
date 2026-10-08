import unittest
from source_registry import plan,collect
class SourceTests(unittest.TestCase):
    def test_same_code_different_market_preserves_request_position(self):
        spec={'asOf':'2026-10-03','requests':[{'kind':'bond','code':'123456','market':'0'},{'kind':'bond','code':'123456','market':'1'}]}
        fake=lambda *a:{'rows':[dict(kind='bond',code='123456',history=[{'date':'2026-09-01'}],collectionStatus='available'),dict(kind='bond',code='123456',history=[],errors='missing')]}
        result=collect(spec,None,fake)
        self.assertEqual([r['status'] for r in result['rows']],['observed','missing'])
        self.assertEqual([r['requestIndex'] for r in result['rows']],[0,1])
    def test_bad_response_identity_is_not_observed(self):
        result=collect(self.spec(),None,lambda *a:{'rows':[dict(kind='etf',code='wrong',history=[1])]})
        self.assertEqual(result['rows'][0]['status'],'missing')
    def spec(self,kind='etf',domains=None):
        return {'asOf':'2026-10-03','requests':[{'kind':kind,'code':'510300','domains':domains or ['history']}]}
    def test_missing_market(self):
        self.assertEqual(plan(self.spec('bond'))['rows'][0]['status'],'unsupported')
    def test_no_network_for_unconnected(self):
        def fail(*args):raise AssertionError('must not dispatch')
        r=collect(self.spec(domains=['realtime-iopv','original-pdf']),None,fail)
        self.assertIsNone(r['bundle']);self.assertEqual([x['status'] for x in r['rows']],['unsupported','requires-input'])
    def test_partial_not_available(self):
        def fake(*args):return {'rows':[{'kind':'etf','code':'510300','history':[{'date':'2026-10-01'}],'announcements':[],'collectionStatus':'partial','errors':'announcement timeout'}]}
        r=collect(self.spec(domains=['history','announcement-metadata']),None,fake)
        self.assertEqual([x['status'] for x in r['rows']],['observed','missing'])
        self.assertEqual(r['rows'][0]['sourceVerification'],'not-verified')
    def test_invalid_domain(self):
        with self.assertRaises(ValueError):plan(self.spec(domains=['invented']))
    def test_future_start(self):
        s=self.spec();s['requests'][0]['start']='2027-01-01'
        with self.assertRaises(ValueError):plan(s)
if __name__=='__main__':unittest.main()
