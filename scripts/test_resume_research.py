import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from resume_research import plan,run,run_from_search

class Tests(unittest.TestCase):
    def test_monthly_rebalance_changes_only_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=self.previous(Path(tmp),command='rebalance')
            p=plan(old,'改成按月再平衡')
            self.assertEqual(p['changes'],{'rebalance_options':{'periodicRule':'month-change'}})
            self.assertFalse(p['online'])
            self.assertEqual(plan(old,'按月再平衡并把佣金设为零')['status'],'needs-clarification')
            (old/'input.json').write_text(json.dumps({'periodicRule':'month-change'}),'utf-8')
            with patch('resume_research.execute',return_value={'status':'partial','message':'完成','nextSteps':[]}):
                result=run(old,'按月再平衡',Path(tmp)/'new')
                self.assertIn('已经采用',result['followupInterpretation'])
    def test_cashflow_question_does_not_guess_missing_deposit(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=self.previous(Path(tmp),command='cashflow')
            self.assertEqual(plan(old,'我到底赚了多少？')['questionType'],'cashflow-profit')
            self.assertEqual(plan(old,'我到底赚了多少并补上昨天的转入')['status'],'needs-clarification')
    def test_portfolio_question_does_not_swallow_rebalance(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=self.previous(Path(tmp),command='portfolio')
            self.assertEqual(plan(old,'谁在拖累组合？')['questionType'],'portfolio-drag')
            self.assertEqual(plan(old,'谁在拖累组合并把它卖掉')['status'],'needs-clarification')
    def test_bjx_money_units_and_full_phrase(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=self.previous(Path(tmp),command='bjx')
            for phrase,expected in [('沿用上一份，把资金改为1,250万元','12500000'),('预算改成1000000元','1000000'),('把本金调整为12.345万元','123450.000')]:
                self.assertEqual(plan(old,phrase)['changes']['budget'],expected)
            for phrase in ['把资金改为1,00万元','把资金改为100美元','把资金改为100万元并更新预测','把资金改为-1元']:
                self.assertEqual(plan(old,phrase)['status'],'needs-clarification')
            with self.assertRaises(ValueError):plan(old,'把资金改为1.001元')
    def test_snapshot_question_preserves_amounts_and_rejects_extra_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=self.previous(Path(tmp),command='snapshot')
            self.assertEqual(plan(old,'我的钱主要集中在哪？')['questionType'],'money-concentration')
            self.assertEqual(plan(old,'我的钱主要集中在哪并把仓位减半')['status'],'needs-clarification')
    def test_risk_question_retains_parameters_and_does_not_swallow_extra_instruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=self.previous(Path(tmp))
            p=plan(old,'哪只更稳？');self.assertEqual(p['questionType'],'stability');self.assertEqual(p['changes'],{})
            self.assertEqual(plan(old,'哪只更稳并换成000003')['status'],'needs-clarification')
    def previous(self,root,end='2024-02-29',command='funds'):
        old=root/'old';old.mkdir()
        (old/'research-request.json').write_text(json.dumps({'command':command,'asOf':end,'online':True}),'utf-8')
        return old
    def test_calendar_anchor_and_no_online_inheritance(self):
        with tempfile.TemporaryDirectory() as tmp:
            old=self.previous(Path(tmp));before=(old/'research-request.json').read_bytes()
            p=plan(old,'沿用上一份，只看近一年')
            self.assertEqual(p['changes'],{'start':'2023-02-28'})
            self.assertFalse(p['online']);self.assertIn('不是今天',p['message'])
            self.assertEqual(before,(old/'research-request.json').read_bytes())
    def test_extra_changes_require_clarification_without_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=self.previous(root)
            with patch('resume_research.execute') as execute:
                for text in ['只看近一年并把预算改成十万','换成000001','近一年并联网更新']:
                    self.assertEqual(run(old,text,root/'new')['status'],'needs-clarification')
                execute.assert_not_called();self.assertFalse((root/'new').exists())
    def test_explicit_dates_and_unsupported_other_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=self.previous(root)
            self.assertEqual(plan(old,'看2023-01-01至2023-12-31')['changes'],{'start':'2023-01-01','as_of':'2023-12-31'})
            with self.assertRaises(ValueError):plan(old,'近0个月')
            (old/'research-request.json').write_text(json.dumps({'command':'portfolio'}),'utf-8')
            self.assertEqual(plan(old,'只看近一年')['status'],'needs-clarification')
            self.assertEqual(plan(old,'重算')['status'],'ready')
    def test_existing_output_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=self.previous(root);out=root/'new';out.mkdir()
            sentinel=out/'start-result.json';sentinel.write_text('original','utf-8')
            with patch('resume_research.execute',return_value={'status':'blocked','failureKind':'output-exists','message':'已存在'}):
                run(old,'重算',out)
            self.assertEqual(sentinel.read_text('utf-8'),'original');self.assertFalse((out/'追问解释.json').exists())
    def test_search_ambiguity_does_not_execute_or_create_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ['one','two']:
                d=root/name;d.mkdir()
                (d/'start-result.json').write_text(json.dumps({'status':'partial','message':'基金测试'}),'utf-8')
                (d/'打开这里.html').write_text('报告','utf-8')
            with patch('resume_research.run') as execute:
                result=run_from_search(root,'基金','重算',root/'new')
                self.assertEqual(len(result['matches']),2);execute.assert_not_called()
                self.assertFalse((root/'new').exists())
    def test_search_unique_selects_declared_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=self.previous(root)
            (old/'start-result.json').write_text(json.dumps({'status':'partial','message':'目标基金'}),'utf-8')
            (old/'打开这里.html').write_text('报告','utf-8')
            with patch('resume_research.run',return_value={'status':'partial'}) as execute:
                self.assertEqual(run_from_search(root,'目标基金','重算',root/'new')['status'],'partial')
                execute.assert_called_once_with(old,'重算',root/'new')

if __name__=='__main__':unittest.main()
