import unittest
import tempfile,json,hashlib
from pathlib import Path
from unittest.mock import patch
from fund_comparison_question import answer,verify_saved,ANSWER_FILES,PERFORMANCE_FILES

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
    def test_saved_performance_answer_tamper_hides_old_conclusion(self):
        from research_results import publish
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);study=root/'study';study.mkdir();(study/'comparison').mkdir()
            (study/'comparison/input.json').write_text('{}','utf-8')
            for name in PERFORMANCE_FILES:(study/name).write_text(json.dumps({'conclusion':'收益原结论'}) if name.endswith('.json') else '收益原结论','utf-8')
            manifest={'artifactType':'fund-performance-question','primaryReport':'收益追问.html','inputSha256':hashlib.sha256((study/'comparison/input.json').read_bytes()).hexdigest(),'files':{n:hashlib.sha256((study/n).read_bytes()).hexdigest() for n in PERFORMANCE_FILES}}
            (study/'report-manifest.json').write_text(json.dumps(manifest),'utf-8')
            (study/'start-result.json').write_text(json.dumps({'status':'partial','message':'收益回答','headline':'旧摘要'}),'utf-8')
            (study/'打开这里.html').write_text('入口','utf-8')
            self.assertEqual(publish(root,root/'index.md')[0]['headline'],'收益原结论')
            (study/'收益追问.html').write_text('已修改','utf-8')
            row=publish(root,root/'changed.md')[0]
            self.assertEqual(row['status'],'记录需要复查');self.assertIsNone(row['headline'])

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
    def test_return_question_distinguishes_loss_zero_profit_and_ties(self):
        for values in [(-20,-10),(0,-10),(10,10),(10,20)]:
            result=self.calculated()
            for row,value in zip(result['rows'],values):row['totalReturnPct']=value
            with patch('fund_comparison_question.report',return_value=(result,'')):
                data,text=answer(self.document(),'return')
            self.assertEqual(data['highestReturnCodes'],[r['code'] for r in result['rows'] if r['totalReturnPct']==max(values)])
            self.assertIn('不是你的个人持有收益',text)
            if max(values)<0:self.assertIn('亏得较少',data['conclusion'])
            if max(values)==0:self.assertIn('没有盈利',data['conclusion'])
            if values==(10,10):self.assertIn('并列最高',data['conclusion'])

    def test_return_question_shows_requested_and_actual_start(self):
        result=self.calculated();result['requestedStart']='2024-12-31'
        for row in result['rows']:row['totalReturnPct']=5
        with patch('fund_comparison_question.report',return_value=(result,'')):
            data,text=answer(self.document(),'return')
        self.assertIn('原请求起点为2024-12-31',text)
        self.assertIn('实际从2025-01-01开始',text)
        self.assertIn('不据此猜测',text)

    def test_risk_titles_match_question_and_show_actual_scope(self):
        result=self.calculated();result['requestedStart']='2024-12-31'
        for kind,title in [('stability','哪只更稳'),('volatility','哪只日常波动更小'),('drawdown','哪只历史回撤更小')]:
            with patch('fund_comparison_question.report',return_value=(result,'')):
                data,text=answer(self.document(),kind)
            self.assertTrue(text.startswith('# '+title))
            self.assertIn('原请求起点为2024-12-31',text)
            self.assertIn('实际从2025-01-01开始',text)

    def test_return_leader_risk_tradeoff_is_explained_not_hidden_in_table(self):
        result=self.calculated()
        result['rows'][0].update(totalReturnPct=5)
        result['rows'][1].update(totalReturnPct=20,drawdownPct=-30)
        with patch('fund_comparison_question.report',return_value=(result,'')):
            data,text=answer(self.document(),'return')
        self.assertIn('最大回撤幅度为30.00%',data['conclusion'])
        self.assertIn('最小的20.00%更深',data['conclusion'])
        self.assertIn('年化波动为30.00%',data['conclusion'])
        result['rows'][0]['annualizedVolPct']=None
        with patch('fund_comparison_question.report',return_value=(result,'')):
            data,text=answer(self.document(),'return')
        self.assertNotIn('年化波动为',data['conclusion'])

    def test_return_risk_question_keeps_tradeoffs_and_missing_data(self):
        result=self.calculated()
        for row,value in zip(result['rows'],[5,20]):row['totalReturnPct']=value
        with patch('fund_comparison_question.report',return_value=(result,'')):
            data,text=answer(self.document(),'return-risk')
        self.assertEqual(data['jointLeaderCodes'],[])
        self.assertIn('没有一只',data['conclusion'])
        self.assertIn('收益怎么看',text);self.assertIn('风险怎么看',text)
        result['rows'][0]['annualizedVolPct']=None
        with patch('fund_comparison_question.report',return_value=(result,'')):
            data,text=answer(self.document(),'return-risk')
        self.assertIn('波动率缺值',data['conclusion'])

    def test_joint_question_calculates_once_and_keeps_headline_concise(self):
        result=self.calculated()
        for row,value in zip(result['rows'],[5,20]):row['totalReturnPct']=value
        with patch('fund_comparison_question.report',return_value=(result,'')) as calculate:
            data,text=answer(self.document(),'return-risk')
        calculate.assert_called_once_with(self.document())
        self.assertIn('收益较高：起伏基金',data['conclusion'])
        self.assertIn('波动较小：平缓基金',data['conclusion'])
        self.assertNotIn('收益最高不等于风险最低',data['conclusion'])
        self.assertIn('收益最高不等于风险最低',text)

    def test_equal_values_keep_ties(self):
        result=self.calculated();result['rows'][1].update(drawdownPct=-20,annualizedVolPct=10)
        with patch('fund_comparison_question.report',return_value=(result,'')):
            data,text=answer(self.document(),'stability')
        self.assertEqual(data['lowestVolatilityCodes'],['a','b']);self.assertIn('并列',text)

if __name__=='__main__':unittest.main()
