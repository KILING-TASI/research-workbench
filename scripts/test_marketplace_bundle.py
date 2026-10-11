import importlib.util,json,tempfile,unittest
from pathlib import Path

ROOT=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('marketplace_bundle',ROOT/'tools/build_marketplace_bundle.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class Tests(unittest.TestCase):
    def test_twelve_wrappers_registry_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'bundle';self.assertEqual(module.build(ROOT/'distribution/marketplace-catalog.json',out),12)
            rows=json.loads((out/'.codebuddy-skill/marketplace.json').read_text('utf-8'))['skills']
            self.assertEqual(len(rows),12)
            for row in rows:self.assertTrue((out/'skills'/row['source']/'SKILL.md').is_file())
            self.assertFalse(json.loads((out/'receipt.json').read_text('utf-8'))['platformImportVerified'])
            self.assertTrue((out/'LICENSE').is_file())
            with self.assertRaises(ValueError):module.build(ROOT/'distribution/marketplace-catalog.json',out)
    def test_prerelease_and_path_escape_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for key,value in [('version','0.1.0-beta.20'),('source','../other')]:
                data=json.loads((ROOT/'distribution/marketplace-catalog.json').read_text('utf-8'));data['skills'][0][key]=value
                path=Path(tmp)/'bad.json';path.write_text(json.dumps(data),'utf-8');out=Path(tmp)/'bad'
                with self.assertRaises(ValueError):module.build(path,out)
                self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
