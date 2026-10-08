import json,tempfile,unittest
from pathlib import Path
from bjx_annual_followup import repeat,comparison

class Followup(unittest.TestCase):
    def test_less_than_in_transit_rejected_without_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);prior=root/'prior';prior.mkdir()
            spec=json.loads((Path(__file__).resolve().parents[1]/'modules/bjx-newshare-toolkit/assets/example-annual-yield.json').read_text('utf-8'));spec['s_in_transit']='5000000'
            (prior/'input.json').write_text(json.dumps(spec),'utf-8')
            with self.assertRaises(ValueError):repeat(prior,root/'new','4000000')
            self.assertFalse((root/'new').exists())
    def test_comparison_explains_income_and_idle_capital(self):
        def value(capital,net,rate,amount):return {'capital':capital,'availableCapital':capital,'scenarios':{'neutral':{'annualNet':net,'annualCumulativeRate':rate,'atAvailableCap':{'subscriptionAmount':amount,'expectedHands':2,'fundCost':3}}}}
        body=comparison(value(100,10,.1,100),value(200,15,.075,150))
        self.assertIn('+5.00元',body);self.assertIn('-2.50个百分点',body);self.assertIn('50.00元',body);self.assertIn('未加入闲置资金',body)
    def test_repeat_preserves_assumptions_and_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);prior=root/'prior';prior.mkdir()
            spec=json.loads((Path(__file__).resolve().parents[1]/'modules/bjx-newshare-toolkit/assets/example-annual-yield.json').read_text('utf-8'))
            source=prior/'input.json';source.write_text(json.dumps(spec),'utf-8');before=source.read_bytes()
            result=repeat(prior,root/'new','12500000')
            saved=json.loads((root/'new/input.json').read_text('utf-8'))
            self.assertEqual(source.read_bytes(),before);self.assertEqual(saved['scenarios'],spec['scenarios']);self.assertEqual(result['capital'],12500000)
            self.assertEqual(saved['eligibility'],spec['eligibility'])
            self.assertIn('资金调整说明.md',json.loads((root/'new/report-manifest.json').read_text('utf-8'))['files'])
            with self.assertRaises(FileExistsError):repeat(prior,root/'new','100')
    def test_invalid_capital_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'input.json').write_text(json.dumps({'s_capital':1,'scenarios':{}}),'utf-8')
            for value in (True,'NaN','-1','0','1.001'):
                with self.assertRaises(ValueError):repeat(root,root/'new',value)
