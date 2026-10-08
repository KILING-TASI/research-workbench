import copy,unittest
from portfolio_cashflow_review import calculate

class Tests(unittest.TestCase):
    def test_growing_balance_can_still_be_loss_and_million_display_preserves_money(self):
        import tempfile
        from pathlib import Path
        from portfolio_cashflow_review import publish
        spec=self.spec();spec['observations'][-1].update(beforeFlowValue=135,afterFlowValue=135)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);result=publish(spec,root/'base')
            self.assertIn('增加35.00',result['headline']);self.assertIn('净转入100.00',result['headline']);self.assertIn('亏损65.00',result['headline'])
            spec['amountUnit']='million'
            for row in spec['observations']:
                for key in ('beforeFlowValue','afterFlowValue','externalFlow'):row[key]/=1000000
            scaled=publish(spec,root/'million');text=(root/'million/组合出入金与收益观察.md').read_text('utf-8')
            self.assertIn('亏损65.00',scaled['headline']);self.assertIn('+100.00',text);self.assertIn('原输入为百万单位',text)
    def test_named_account_can_be_found_and_invalid_label_rejected(self):
        import tempfile
        from pathlib import Path
        from portfolio_cashflow_review import publish
        from research_results import publish as find
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);spec=self.spec();spec['accountLabel']='长期账户';publish(spec,root/'opaque')
            rows=find(root,root/'found.md','长期账户');self.assertEqual(len(rows),1)
            self.assertEqual(len(find(root,root/'combined.md','长期账户 2023')),1)
            self.assertEqual(find(root,root/'not-this-year.md','长期账户 2030'),[])
        spec=self.spec();spec['accountLabel']=' '
        with self.assertRaises(ValueError):calculate(spec)
    def test_million_unit_does_not_allow_ten_thousand_reconciliation_error(self):
        spec=self.spec();spec['amountUnit']='million'
        spec['observations'][1]['afterFlowValue']+=.005
        with self.assertRaises(ValueError):calculate(spec)
    def test_unit_scaling_preserves_returns_and_scales_profit(self):
        spec=self.spec();base=calculate(spec);spec['amountUnit']='million'
        for row in spec['observations']:
            for key in ('beforeFlowValue','afterFlowValue','externalFlow'):row[key]/=1000000
        scaled=calculate(spec)
        self.assertAlmostEqual(scaled['twrPct'],base['twrPct']);self.assertAlmostEqual(scaled['profit']*1000000,base['profit'])
    def test_human_ledger_and_report_discovery(self):
        import tempfile,json
        from pathlib import Path
        from portfolio_cashflow_review import publish
        from research_results import publish as find
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);out=root/'review';publish(self.spec(),out)
            text=(out/'组合出入金与收益观察.md').read_text('utf-8')
            self.assertIn('逐期出入金明细',text);self.assertIn('CNY',text);self.assertIn('+100.00',text)
            self.assertEqual(len(find(root,root/'found.md','组合出入金')),1)
            from start import execute
            result=execute('cashflow',root/'continued',continue_from=out)
            self.assertEqual(result['status'],'partial');self.assertIn('时间加权',result['headline'])
            self.assertEqual(json.loads((root/'continued/input.json').read_text('utf-8')),self.spec())
    def spec(self):return {'cashFlowCoverage':'declared-complete','basis':'教学估值','currency':'CNY','amountUnit':'base','observations':[{'date':'2023-01-01','beforeFlowValue':100,'externalFlow':0,'afterFlowValue':100},{'date':'2023-07-01','beforeFlowValue':110,'externalFlow':100,'afterFlowValue':210},{'date':'2024-01-01','beforeFlowValue':231,'externalFlow':0,'afterFlowValue':231}]}
    def test_added_money_not_mistaken_for_returns(self):
        result=calculate(self.spec());self.assertAlmostEqual(result['twrPct'],21);self.assertEqual(result['profit'],31);self.assertIsNotNone(result['xirrPct'])
    def test_withdrawal_reconciles_profit(self):
        spec=self.spec();spec['observations'][1].update(externalFlow=-50,afterFlowValue=60);spec['observations'][2].update(beforeFlowValue=66,afterFlowValue=66)
        result=calculate(spec);self.assertAlmostEqual(result['twrPct'],21);self.assertEqual(result['profit'],16)
    def test_missing_coverage_and_wrong_values_rejected(self):
        for change in ({'cashFlowCoverage':'unknown'},{'basis':''}):
            spec=self.spec();spec.update(change)
            with self.assertRaises(ValueError):calculate(spec)
        spec=self.spec();spec['observations'][1]['afterFlowValue']=200
        with self.assertRaises(ValueError):calculate(spec)
    def test_nonconventional_flows_do_not_choose_an_irr_root(self):
        spec=self.spec();spec['observations'][1].update(beforeFlowValue=200,externalFlow=-150,afterFlowValue=50);spec['observations'][2].update(beforeFlowValue=55,externalFlow=100,afterFlowValue=155)
        spec['observations'].append({'date':'2024-07-01','beforeFlowValue':170,'externalFlow':0,'afterFlowValue':170})
        self.assertIsNone(calculate(spec)['xirrPct'])
