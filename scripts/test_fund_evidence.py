import copy,unittest,tempfile,hashlib
from pathlib import Path
from unittest.mock import MagicMock,patch
from fund_evidence import build,compare

def sample():
    return {'subjectCodes':['a'],'asOf':'2026-10-03','methodology':{'classificationVersion':'v1'},
      'evidence':[{'id':'x','code':'a','field':'NAV','status':'original-disclosed','value':1,
                   'sourceUrl':'https://example.org/a','disclosedAt':'2026-09-30','locator':'p1'}],
      'conclusions':[{'id':'c','text':'原文披露NAV为1','evidenceIds':['x'],'grade':'disclosed-fact','limitations':['只反映披露日']}],
      'notes':[{'text':'待跟踪','conclusionIds':['c']}]}

class Tests(unittest.TestCase):
    def test_observation_cannot_precede_disclosure(self):
        s=sample();s['evidence'][0]['observedAt']='2026-09-29'
        with self.assertRaisesRegex(ValueError,'不能早于披露日'):build(s)
        s['evidence'][0]['observedAt']='2026-09-30';build(s)
    def test_notes_reject_malformed_bindings_before_concatenation(self):
        for value in ['c',None,{},['c','c'],[1]]:
            s=sample();s['notes'][0]['conclusionIds']=value
            with self.assertRaisesRegex(ValueError,'笔记引用'):build(s)
        for value in [1,'  ',None]:
            s=sample();s['notes'][0]['text']=value
            with self.assertRaisesRegex(ValueError,'非空文本'):build(s)
    def test_incomplete_coverage_has_actionable_error(self):
        for coverage in [{'total':100,'basis':'股票市值'},{'known':54,'basis':'股票市值'},{'known':54,'total':100,'basis':True},{'known':54,'total':100,'basis':' '}]:
            s=sample();s['conclusions'][0]['coverage']=coverage
            with self.assertRaisesRegex(ValueError,'覆盖分母或口径无效'):build(s)
    def test_text_contract_matches_report_consumer(self):
        for mutate in [lambda s:s['conclusions'][0].update(text=1),lambda s:s['conclusions'][0].update(limitations='仅片段'),lambda s:s['conclusions'][0].update(evidenceIds=['x','x']),lambda s:s['evidence'][0].update(inputEvidenceIds=['x','x'])]:
            s=sample();mutate(s)
            with self.assertRaises(ValueError):build(s)
    def test_relative_pdf_path_resolves_from_input_directory(self):
        import json
        from fund_evidence import read_input
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.json';s=sample();s['evidence'][0]['pdf']='documents/report.pdf';p.write_text(json.dumps(s),encoding='utf-8')
            self.assertEqual(read_input(p)['evidence'][0]['pdf'],str((Path(d)/'documents/report.pdf').resolve()))
            p.write_text(json.dumps({'before':s,'after':s}),encoding='utf-8');self.assertEqual(read_input(p)['after']['evidence'][0]['pdf'],str((Path(d)/'documents/report.pdf').resolve()))
    def test_empty_observation_date_is_not_silently_ignored(self):
        s=sample();s['evidence'][0]['observedAt']=''
        with self.assertRaises(ValueError):build(s)
    def test_roundtrip_and_note_version(self):
        a=build(sample());self.assertEqual(build(a)['packageVersion'],a['packageVersion'])
        b=copy.deepcopy(a);b['notes'][0]['text']='新笔记';b=build(b)
        r=compare({'before':a,'after':b});self.assertTrue(r['notesChanged']);self.assertEqual(r['evidenceChanges'],[])
    def test_unknown_binding(self):
        s=sample();s['conclusions'][0]['evidenceIds']=['none']
        with self.assertRaises(ValueError):build(s)
    def test_coverage_not_confidence(self):
        s=sample();s['conclusions'][0]['coverage']={'known':54,'total':100,'basis':'股票市值'}
        r=build(s);self.assertEqual(r['conclusions'][0]['coverage']['pct'],54)
        self.assertIn('不是准确率',r['conclusions'][0]['coverage']['meaning'])
    def test_assumption_cannot_hide_behind_derived(self):
        s=sample();s['evidence'].append({'id':'estimate','code':'a','status':'assumption','value':2})
        s['evidence'].append({'id':'derived','code':'a','status':'derived','value':3,'formula':'x+estimate','inputEvidenceIds':['x','estimate'],'parameters':{'units':'CNY'}})
        s['conclusions'][0].update(grade='calculated',evidenceIds=['derived'])
        with self.assertRaises(ValueError):build(s)
        s['conclusions'][0]['grade']='estimate';self.assertEqual(build(s)['conclusions'][0]['grade'],'estimate')
    def test_dependency_cycle(self):
        s=sample();s['evidence'][0].update(status='derived',formula='x',inputEvidenceIds=['x'],parameters={'units':'CNY'})
        with self.assertRaises(ValueError):build(s)
    def test_conflict_retained(self):
        s=sample();s['evidence'][0].update(status='conflict',alternatives=[{'value':1},{'value':2}]);s['conclusions'][0]['grade']='withheld'
        self.assertEqual(len(build(s)['evidence'][0]['alternatives']),2)

    def test_declared_source_not_certified_original(self):
        r=build(sample());self.assertEqual(r['evidence'][0]['originalVerification']['status'],'source-declared-not-original-checked')
    def test_quote_without_bbox_checked_against_page(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'pdf';p.write_bytes(b'pdf');s=sample();s['evidence'][0].update(pdf=str(p),fileSha256=hashlib.sha256(b'pdf').hexdigest(),page=1,quote='原文净值1')
            doc=MagicMock();doc.__enter__.return_value=doc;page=MagicMock();page.extract_text.return_value='原文净值1';doc.pages=[page]
            with patch('pdfplumber.open',return_value=doc):self.assertEqual(build(s)['evidence'][0]['originalVerification']['status'],'quote-found-on-declared-page')
            s['evidence'][0]['quote']='原文净值2'
            with patch('pdfplumber.open',return_value=doc),self.assertRaisesRegex(ValueError,'原文页不符'):build(s)
    def test_bad_structures_and_dependency_ids(self):
        with self.assertRaises(ValueError):build({'subjectCodes':'a'})
        s=sample();s['evidence'][0]['inputEvidenceIds']='x'
        with self.assertRaisesRegex(ValueError,'文本数组'):build(s)
    def test_deep_dependency_chain_without_recursion_and_with_uncertainty(self):
        s=sample();previous='x'
        for i in range(1200):
            current='d'+str(i);s['evidence'].append({'id':current,'code':'a','status':'derived','value':1,'formula':'identity(previous)','inputEvidenceIds':[previous],'parameters':{'unit':'CNY'}});previous=current
        s['conclusions'][0].update(grade='calculated',evidenceIds=[previous]);self.assertEqual(build(s)['conclusions'][0]['grade'],'calculated')
        s['evidence'][0]['status']='assumption'
        with self.assertRaisesRegex(ValueError,'不能标确定结论'):build(s)
        s['conclusions'][0]['grade']='estimate';self.assertEqual(build(s)['conclusions'][0]['grade'],'estimate')
    def test_diamond_uncertainty_propagates(self):
        s=sample();s['evidence'][0]['status']='missing';s['evidence'][0]['value']=None
        for name,deps in [('left',['x']),('right',['x']),('join',['left','right'])]:
            s['evidence'].append({'id':name,'code':'a','status':'derived','value':1,'formula':'demo','inputEvidenceIds':deps,'parameters':{'unit':'CNY'}})
        s['conclusions'][0].update(grade='calculated',evidenceIds=['join'])
        with self.assertRaisesRegex(ValueError,'不能标确定结论'):build(s)
if __name__=='__main__':unittest.main()
