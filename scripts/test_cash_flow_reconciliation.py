import unittest
import json,subprocess,sys,tempfile
from pathlib import Path
from cash_flow_reconciliation import reconcile

class Tests(unittest.TestCase):
    def test_missing_version_and_duplicate_pages_do_not_pass(self):
        s,o=self.spec();del s['sourceSha256'];del o['fileSha256']
        with self.assertRaisesRegex(ValueError,'哈希缺失'):reconcile(s,o)
        s,o=self.spec();o['pages'].append(dict(o['pages'][0]))
        with self.assertRaisesRegex(ValueError,'物理页重复'):reconcile(s,o)
        s,o=self.spec();s['rows'][0]['page']=True
        with self.assertRaises(ValueError):reconcile(s,o)
    def spec(self):
        row=lambda k,n,c,p:dict(key=k,page=1,quote=n+' '+c+' '+p,current=c,prior=p)
        s=dict(unit='元',currency='CNY',period='2026-06-30',sourceSha256='a',rows=[row('netProfit','净利润','10.00','8.00'),row('inventory','存货','-3.00','-4.00')],cashTotal=row('cfo','经营现金','7.00','4.00'))
        o=dict(fileSha256='a',pages=[dict(page=1,text='\n'.join(r['quote'] for r in s['rows']+[s['cashTotal']]))])
        return s,o
    def test_negative_adjustments_and_prior_reconcile(self):
        s,o=self.spec();r=reconcile(s,o);self.assertEqual(r['status'],'selected-table-reconciled');self.assertEqual(r['rows'][1]['change'],'1.00');self.assertFalse(r['semanticCertification'])
    def test_missing_adjustment_is_not_reconciled(self):
        s,o=self.spec();s['rows'].pop();self.assertEqual(reconcile(s,o)['status'],'reconciliation-mismatch')
    def test_swapped_amounts_or_changed_original_rejected(self):
        s,o=self.spec();s['rows'][0]['current']='8.00';s['rows'][0]['prior']='10.00'
        with self.assertRaises(ValueError):reconcile(s,o)

    def test_thousand_integer_disclosure_keeps_units(self):
        s,o=self.spec();s['reportedUnit']='千元';s['unitEvidence']=dict(page=1,quote='单位：千元 币种：人民币')
        for r in s['rows']+[s['cashTotal']]:
            r['quote']=r['quote'].replace('.00','')
            for k in ['current','prior']:r[k]=str(int(float(r[k]))*1000)
        o['pages'][0]['text']=s['unitEvidence']['quote']+'\n'+'\n'.join(r['quote'] for r in s['rows']+[s['cashTotal']])
        r=reconcile(s,o);self.assertEqual(r['status'],'selected-table-reconciled');self.assertEqual(r['amountScale'],'1000');self.assertEqual(r['rows'][0]['reportedAmounts'],['10','8'])
        s['rows'][0]['current']='10'
        with self.assertRaises(ValueError):reconcile(s,o)

    def test_scale_requires_original_unit_evidence(self):
        s,o=self.spec();s['reportedUnit']='千元'
        with self.assertRaises(ValueError):reconcile(s,o)
        s['unitEvidence']=dict(page=1,quote='单位：万元 币种：人民币')
        with self.assertRaises(ValueError):reconcile(s,o)
        s,o=self.spec();o['fileSha256']='new'
        with self.assertRaises(ValueError):reconcile(s,o)

    def test_original_numeric_substrings_rejected(self):
        for token in ('10.00%','10.00％','10.00e3','10.00.5','−10.00','+10.00','1,0.00'):
            with self.subTest(token=token):
                s,o=self.spec();s['rows'][0]['quote']='净利润 '+token+' 8.00'
                o['pages'][0]['text']='\n'.join(r['quote'] for r in s['rows']+[s['cashTotal']])
                with self.assertRaises(ValueError):reconcile(s,o)

    def test_cli_original_relative_to_input_not_cwd(self):
        s,o=self.spec();s.update(code='test',originalResult='original.json');o['code']='test'
        script=Path(__file__).with_name('cash_flow_reconciliation.py').resolve()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data=root/'data';data.mkdir();cwd=root/'elsewhere';cwd.mkdir()
            (data/'original.json').write_text(json.dumps({'companies':[o]}),encoding='utf-8')
            (data/'input.json').write_text(json.dumps(s),encoding='utf-8');out=root/'result.json'
            result=subprocess.run([sys.executable,str(script),str(data/'input.json'),'--out',str(out)],cwd=cwd,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(out.read_text(encoding='utf-8'))['status'],'selected-table-reconciled')

if __name__=='__main__':unittest.main()
