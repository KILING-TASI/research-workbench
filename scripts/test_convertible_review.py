import unittest
from convertible_review import calculate, present_value, yield_rate, rolling_clause

class Tests(unittest.TestCase):
    def test_direct_cli_human_notice_keeps_stdout_and_result_compatible(self):
        import json,subprocess,sys,tempfile,hashlib
        from pathlib import Path
        root=Path(__file__).resolve().parents[1];example=root/'references/examples/convertible-review-example.json'
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'report';command=[sys.executable,str(root/'scripts/convertible_review.py'),str(example),'--out-dir',str(out)]
            first=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(first.returncode,0,first.stderr);self.assertEqual(first.stdout,'')
            self.assertIn('教学假设',first.stderr);self.assertIn('可转债基础诊断.html',first.stderr)
            self.assertEqual(json.loads((out/'result.json').read_text('utf-8')),calculate(json.loads(example.read_text('utf-8'))))
            before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
            second=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(second.returncode,1);self.assertIn('换一个新名字',second.stderr)
            self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()})
    def test_cli_failure_does_not_echo_private_input_path(self):
        import subprocess,sys,tempfile
        from pathlib import Path
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            command=[sys.executable,str(root/'scripts/convertible_review.py'),str(Path(tmp)/'PRIVATE_TOKEN_INPUT.json'),'--out-dir',str(Path(tmp)/'report')]
            result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,1);self.assertIn('核对',result.stderr)
            self.assertNotIn('PRIVATE_TOKEN',result.stderr);self.assertEqual(result.stdout,'')
    def test_invalid_direct_yield_inputs_do_not_enter_root_search(self):
        for price in [0,-100,True,float('nan'),10**10000]:
            with self.assertRaises(ValueError):yield_rate([(1,100)],price)
        for cf in [[],[(1,0)],[(2,100),(1,100)],[(float('inf'),100)],[(1,100,2)]]:
            with self.assertRaises(ValueError):yield_rate(cf,100)
    def test_discount_boundary_and_clause_shape_are_explicit(self):
        with self.assertRaises(ValueError):present_value([(1,100)],-1)
        for rows in ({'date':'2026-01-01'},[None]):
            with self.assertRaises(ValueError):rolling_clause(rows,30,15,1.3,'above')
        with self.assertRaises(ValueError):
            rolling_clause([dict(date='2026-01-01',stockPrice=10,conversionPrice=1e308)],30,15,1e308,'above')
    def test_extreme_sensitivity_returns_readable_error(self):
        spec=self.spec();spec.update(discountYield=1e200,cashFlows=[dict(year=1,amount=1e308)])
        with self.assertRaisesRegex(ValueError,'敏感度'):calculate(spec)
    def spec(self):
        return dict(currency='CNY',source='教学现金流，非真实转债',fullPrice=118.5,faceValue=100,
                    stockPrice=10.52,conversionPrice=10,discountYield=.045,
                    cashFlows=[{'year':t,'amount':a} for t,a in [(1,.3),(2,.5),(3,1),(4,111.5)]])
    def test_yield_reprices_cashflows(self):
        cf=[(1,.3),(2,.5),(3,1),(4,111.5)]
        for price in (20,100,118.5,200):
            y=yield_rate(cf,price)
            self.assertAlmostEqual(present_value(cf,y),price,places=9)
        self.assertLess(yield_rate(cf,118.5),0)
    def test_duration_and_convexity_against_derivatives(self):
        spec=self.spec();r=calculate(spec);cf=[(x['year'],x['amount']) for x in spec['cashFlows']]
        h=1e-5;y=spec['discountYield'];p=present_value(cf,y)
        self.assertAlmostEqual((present_value(cf,y-h)-present_value(cf,y+h))/(2*h*p),r['modifiedDuration'],places=6)
        self.assertAlmostEqual((present_value(cf,y-h)+present_value(cf,y+h)-2*p)/(h*h*p),r['convexity'],places=4)
    def test_parity_face_scaling_and_premium(self):
        r=calculate(self.spec());self.assertAlmostEqual(r['conversionValue'],105.2)
        self.assertAlmostEqual(r['conversionPremiumPct'],(118.5/105.2-1)*100)
    def test_no_unconfirmed_exit(self):
        spec=self.spec();spec['exitScenarios']=[{'eligibility':'unknown'}]
        with self.assertRaises(ValueError):calculate(spec)
    def test_rolling_drops_only_expired_observation_and_adjusts_conversion(self):
        rows=[{'date':f'2026-01-{d:02}','stockPrice':13,'conversionPrice':10 if d<4 else 11} for d in range(1,6)]
        out=rolling_clause(rows,3,2,1.3,'above')
        self.assertEqual([r['hits'] for r in out],[1,2,3,2,1])
        self.assertEqual(out[0]['status'],'insufficient-window')
        self.assertEqual(out[3]['status'],'condition-met')
        self.assertEqual(out[4]['status'],'condition-not-met')
    def test_invalid_inputs(self):
        for key,value in [('fullPrice',True),('discountYield',-1),('stockPrice',float('nan')),('conversionPrice',0)]:
            spec=self.spec();spec[key]=value
            with self.assertRaises(ValueError):calculate(spec)
    def test_publish_and_refuse_overwrite(self):
        import tempfile
        from pathlib import Path
        from convertible_review import publish
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'report';publish(self.spec(),out)
            self.assertIn('不是保本线',(out/'可转债基础诊断.md').read_text('utf-8'))
            with self.assertRaises(FileExistsError):publish(self.spec(),out)
    def test_zero_yield_not_called_positive(self):
        import tempfile
        from pathlib import Path
        from convertible_review import publish
        spec=self.spec();spec['fullPrice']=113.3
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'report';publish(spec,out)
            self.assertIn('大致持平',(out/'可转债基础诊断.md').read_text('utf-8'))
    def test_currency_and_scenario_shape(self):
        for patch in ({'currency':None},{'exitScenarios':{}},{'exitScenarios':[{'label':'bad\nline'}]}):
            spec=self.spec();spec.update(patch)
            with self.assertRaises(ValueError):calculate(spec)
    def test_manifest_is_discoverable(self):
        import tempfile
        from pathlib import Path
        from convertible_review import publish
        from research_results import publish as find
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);publish(self.spec(),root/'review')
            found=find(root,root/'index.md')
            self.assertEqual(len(found),1)
            self.assertEqual(found[0]['entry'].name,'可转债基础诊断.html')
    def test_unified_entry_and_continuation(self):
        import tempfile,json
        from pathlib import Path
        from start import execute
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'input.json';p.write_text(json.dumps(self.spec()),'utf-8')
            execute('convertible',root/'first',input_path=p)
            self.assertTrue((root/'first'/'打开这里.html').is_file())
            execute('convertible',root/'second',continue_from=root/'first')
            self.assertTrue((root/'second'/'可转债基础诊断.html').is_file())

if __name__=='__main__':unittest.main()
