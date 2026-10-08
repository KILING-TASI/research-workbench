import json,tempfile,unittest
from pathlib import Path
from bjx_scenario_gateway import adjust
from start import execute,ROOT


class Gateway(unittest.TestCase):
    def test_adjust_only_budget(self):
        spec={'allocation':{'budget':'6000000','price':'25'},'scenarios':[{'id':'same'}]}
        changed=adjust(spec,'1000000')
        self.assertEqual(spec['allocation']['budget'],'6000000')
        self.assertEqual(changed['allocation']['price'],'25')
        self.assertEqual(changed['scenarios'],spec['scenarios'])
        for value in (True,'NaN','1.001','-1'):
            with self.assertRaises(ValueError):adjust(spec,value)

    def test_gateway_continuation_reuses_and_preserves_old_input(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=ROOT/'modules/bjx-newshare-toolkit/assets/example-joint-scenarios.json'
            first=execute('bjx',root/'old',input_path=source)
            old=(root/'old/input.json').read_bytes()
            second=execute('bjx',root/'new',continue_from=root/'old',budget='1000000')
            self.assertEqual(first['status'],'partial');self.assertEqual(second['status'],'partial')
            self.assertEqual(old,(root/'old/input.json').read_bytes())
            self.assertEqual(json.loads((root/'new/input.json').read_text('utf-8'))['allocation']['budget'],'1000000')
            self.assertIn('余股',second['headline'])
            self.assertEqual(json.loads((root/'new/research-request.json').read_text('utf-8'))['command'],'bjx')

if __name__=='__main__':unittest.main()
