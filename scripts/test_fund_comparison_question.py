import unittest
import tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
from fund_comparison_question import answer,verify_saved,ANSWER_FILES

class Tests(unittest.TestCase):
    def test_saved_answer_changes_are_detected_when_finding_reports(self):
        from research_results import publish
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);study=root/'study';study.mkdir();(study/'comparison').mkdir()
            (study/'comparison/input.json').write_text('{}','utf-8')
            for name in ANSWER_FILES:(study/name).write_text(json.dumps({'conclusion':'原回答'}) if name.endswith('.json') else '原回答','utf-8')
            m={'artifactType':'fund-risk-question','primaryReport':'风险追问.html','inputSha256':hashlib.sha256((study/'comparison/input.json').read_bytes()).hexdigest(),'files':{n:hashlib.sha256((study/n).read_bytes()).hexdigest() for n in ANSWER_FILES}}
            (study/'report-manifest.json').write_text(json.dumps(m),'utf-8')
            (study/'start-result.json').write_text(json.dumps({'status':'partial','message':'风险回答','headline':'另一个旧摘要'}),'utf-8')
            (study/'打开这里.html').write_text('入口','utf-8')
            self.assertEqual(verify_saved(study,m),[])
            self.assertEqual(publish(root,root/'index.md')[0]['headline'],'原回答')
            (study/'风险追问.md').write_text('变更后的内容','utf-8')
            rows=publish(root,root/'changed-index.md')
            self.assertEqual(rows[0]['status'],'记录需要复查');self.assertIsNone(rows[0]['headline'])
            self.assertIn('保存后内容发生变化',rows[0]['message'])
    def document(self):return {'rows':[{'code':'a','name':'平缓基金'},{'code':'b','name':'起伏基金'}]}
    def calculated(self):return {'start':'2025-01-01','end':'2025-12-31','rows':[{'code':'a','drawdownPct':-20,'annualizedVolPct':10},{'code':'b','drawdownPct':-10,'annualizedVolPct':30}]}
    def test_conflicting_risk_dimensions_are_not_forced_into_one_winner(self):
        with patch('fund_comparison_question.report',return_value=(self.calculated(),'')):
            data,text=answer(self.document(),'stability')
        self.assertEqual(data['lowestVolatilityCodes'],['a']);self.assertEqual(data['smallestDrawdownCodes'],['b'])
        self.assertIn('不能给出统一',data['conclusion']);self.assertIn('10.00%',text);self.assertIn('30.00%',text)
    def test_missing_volatility_does_not_silently_shrink_pool(self):
        result=self.calculated();result['rows'][0]['annualizedVolPct']=None
        with patch('fund_comparison_question.report',return_value=(result,'')):
            data,text=answer(self.document(),'volatility')
        self.assertEqual(data['lowestVolatilityCodes'],[]);self.assertEqual(data['missingVolatilityCodes'],['a'])
        self.assertIn('不排除',data['conclusion']);self.assertIn('未计算',text)
    def test_drawdown_question_does_not_claim_future_safety(self):
        with patch('fund_comparison_question.report',return_value=(self.calculated(),'')):
            data,text=answer(self.document(),'drawdown')
        self.assertIn('起伏基金',data['conclusion']);self.assertIn('不等于未来更安全',data['conclusion'])
    def test_equal_values_keep_ties(self):
        result=self.calculated();result['rows'][1].update(drawdownPct=-20,annualizedVolPct=10)
        with patch('fund_comparison_question.report',return_value=(result,'')):
            data,text=answer(self.document(),'stability')
        self.assertEqual(data['lowestVolatilityCodes'],['a','b']);self.assertIn('并列',text)

if __name__=='__main__':unittest.main()
