import datetime as dt, tempfile, unittest
from pathlib import Path
from research_evidence import export, conflicts, package, verify, validate

class Tests(unittest.TestCase):
    def test_deep_dependency_chain_and_malformed_lists(self):
        nodes=[self.node()];previous='a'
        for i in range(1200):
            current='d'+str(i);nodes.append({**self.node(),'id':current,'kind':'derived','formula':'identity(previous)','dependsOn':[previous]});previous=current
        self.assertEqual(len(validate(nodes)),1201)
        for dependencies in ['a',None,{},['a','a']]:
            with self.assertRaisesRegex(ValueError,'文本列表'):validate([self.node(),{**self.node(),'id':'b','kind':'derived','formula':'x','dependsOn':dependencies}])
    def node(self,**kw):return dict(id='a',subject='920022',metric='price',kind='assumption',value='10',unit='CNY',basis='example',verification='user-declared',**kw)
    def test_cycle_missing_dependency(self):
        a=self.node();a.update(kind='derived',formula='x',dependsOn=['a'])
        with self.assertRaises(ValueError):validate([a])
        a['dependsOn']=['missing']
        with self.assertRaises(ValueError):validate([a])
    def test_original_cannot_without_proof(self):
        a=self.node();a['kind']='original'
        with self.assertRaises(ValueError):validate([a])
    def test_conflict_not_latest_wins(self):
        a=self.node();b={**a,'id':'b','value':'11','publishedAt':'2026-10-03'}
        r=conflicts({'nodes':[a,b]})['groups'][0]
        self.assertEqual(r['status'],'unresolved');self.assertIsNone(r['resolvedValue'])
    def test_units_and_declared_supersession(self):
        a=self.node();a['version']='v1';b={**a,'id':'b','version':'v2','unit':'shares'}
        self.assertIn('unit-difference',conflicts({'nodes':[a,b]})['groups'][0]['reasons'])
        b.update(unit='CNY',supersedes='v1',value='12')
        self.assertEqual(conflicts({'nodes':[a,b]})['groups'][0]['resolvedValue'],'12')
    def spec(self,p):
        f=p/'input.json';f.write_text('{}')
        return {'evidence':{'nodes':[self.node()]},'dependencies':[{'path':str(f),'role':r} for r in ['research-input','rule','calculation-result']]}
    def test_portable_and_tamper(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);s=self.spec(p);r=package(s,p);folder=Path(r['packagePath'])
            (p/'input.json').unlink();self.assertTrue(verify(folder)['verified'])
            next((folder/'files').iterdir()).write_text('tamper')
            with self.assertRaises(ValueError):verify(folder)
    def test_past_and_incomplete_blocked(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);s=self.spec(p);s.update(mode='predecision',decisionCutoff='2020-01-01T00:00:00+00:00')
            with self.assertRaises(ValueError):package(s,p)
            s['mode']='research';s['dependencies']=s['dependencies'][:1]
            with self.assertRaises(ValueError):package(s,p)
    def test_live_requires_available_time(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);s=self.spec(p);s.update(mode='predecision',decisionCutoff=(dt.datetime.now(dt.timezone.utc)+dt.timedelta(days=1)).isoformat())
            with self.assertRaises(ValueError):package(s,p)
            for d in s['dependencies']:d['availableAt']=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=1)).isoformat()
            self.assertEqual(package(s,p)['mode'],'predecision')
if __name__=='__main__':unittest.main()
