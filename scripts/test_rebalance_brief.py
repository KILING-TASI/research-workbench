import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from rebalance_brief import markdown, publish
from rebalance_brief import adjust_input
from rebalance_brief import followup
from rebalance_brief import CalculationError
from rebalance_brief import split_documents
from rebalance_brief import zero_cost_input
from research_results import publish as index


class RebalanceBriefTests(unittest.TestCase):
    def test_split_shares_boundary_but_not_return_intervals(self):
        rows=[{'date':f'2025-01-{i:02d}','value':i} for i in range(1,9)]
        document={'validationSplit':'2025-01-04','assets':[{'history':rows}],'capital':100}
        parts=split_documents(document)
        self.assertEqual(parts[0][1]['assets'][0]['history'][-1],parts[1][1]['assets'][0]['history'][0])
        left=parts[0][1]['assets'][0]['history'];right=parts[1][1]['assets'][0]['history']
        intervals=lambda data:set((a['date'],b['date']) for a,b in zip(data,data[1:]))
        self.assertFalse(intervals(left)&intervals(right))
        self.assertEqual(len(document['assets'][0]['history']),8)
        document['validationSplit']='2025-01-03'
        with self.assertRaises(ValueError):split_documents(document)

    def test_failure_explanation_excludes_stack_paths(self):
        details='Error: 资产日期必须完全一致，不自动填充\n at C:/private/input.js:3'
        error=CalculationError(details)
        self.assertIn('历史日期没有对齐',str(error))
        self.assertNotIn('C:/private',str(error))
        self.assertEqual(error.technical_details,details)

    def test_input_scope_is_visible_before_results(self):
        result=self.sample();result['inputScopeNotes']=['净值代理，不是成交价回测']
        body=markdown(result)
        self.assertLess(body.index('净值代理'),body.index('|方案|'))
        result['inputScopeNotes']=[None]
        with self.assertRaises(ValueError):markdown(result)

    def sample(self):
        return {'type':'rebalance','start':'2025-01-01','end':'2025-12-31','results':[
            {'name':'买入持有基线','totalReturnPct':10,'maximumDrawdownPct':20,'totalCost':0},
            {'name':'再平衡','totalReturnPct':8,'maximumDrawdownPct':12,'totalCost':30,'explanation':'扣费30，不等于期末财富差。','missed':[{'date':'2025-02-01'}]}]}

    def test_tradeoff_and_old_result(self):
        body=markdown(self.sample())
        self.assertIn('以部分收益换来了较低回撤',body)
        self.assertIn('旧结果未保存',body)
        self.assertIn('有1次',body)
        self.assertIn('样本外',body)

    def test_report_found_without_revalidation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            publish(self.sample(),root/'比较')
            index(root,root/'索引.md',query='再平衡')
            self.assertIn('再平衡',(root/'索引.md').read_text('utf-8'))
            with self.assertRaises(FileExistsError):publish(self.sample(),root/'比较')

    def test_reject_invalid_metrics(self):
        data=self.sample();data['results'][1]['totalCost']=True
        with self.assertRaises(ValueError):markdown(data)

    def test_baseline_identity_not_order(self):
        data=self.sample();data['results'].reverse();data['currency']='CNY'
        self.assertIn('以部分收益换来了较低回撤',markdown(data))
        self.assertIn('金额币种：CNY',markdown(data))
        data['results'][1]['name']='未登记'
        with self.assertRaises(ValueError):markdown(data)

    def test_missing_runtime_retains_request(self):
        import json
        from start import execute
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source.json'
            source.write_text(json.dumps({'asOf':'2026-01-01','everyObservations':20}),encoding='utf-8')
            with patch('rebalance_brief.shutil.which',return_value=None):
                result=execute('rebalance',root/'failure',input_path=source,rebalance_options={'everyObservations':10})
            self.assertEqual(result['status'],'blocked')
            self.assertTrue((root/'failure/input.json').is_file())
            self.assertTrue((root/'failure/research-request.json').is_file())
            self.assertEqual(json.loads((root/'failure/input.json').read_text('utf-8'))['everyObservations'],10)

    def test_explicit_adjustments_preserve_other_inputs(self):
        source={'everyObservations':20,'costs':{'commissionPct':.03,'spreadBps':4},'assets':[{'code':'A'}]}
        changed=adjust_input(source,{'everyObservations':10,'commissionPct':0})
        self.assertEqual(source['everyObservations'],20)
        self.assertEqual(changed['costs'],{'commissionPct':0,'spreadBps':4})
        self.assertEqual(changed['assets'],source['assets'])
        for invalid in ({'everyObservations':True},{'everyObservations':1.5},{'commissionPct':-1},{'sellTaxPct':.1}):
            with self.assertRaises(ValueError):adjust_input(source,invalid)

    def test_cost_conflict_not_silently_overridden(self):
        source={'costs':{'commissionPct':.03},'costsByCode':{'A':{'commissionPct':.05}}}
        with self.assertRaises(ValueError):adjust_input(source,{'commissionPct':.01})

    def test_followup_same_history_and_changed_history(self):
        import json,hashlib
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);document={'assets':[{'code':'A'}],'capital':100,'everyObservations':20,'costs':{'commissionPct':.03}}
            raw=json.dumps(document);old=self.sample();old['results'][1]['name']='定期再平衡'
            old['inputSha256']=hashlib.sha256(raw.encode()).hexdigest()
            (root/'input.json').write_text(raw,'utf-8');(root/'result.json').write_text(json.dumps(old),'utf-8')
            new=adjust_input(document,{'everyObservations':10})
            self.assertIn('|频率|每20个观察期',followup(old,new,root))
            new['capital']=200
            self.assertIn('未将收益差解释',followup(old,new,root))
            new['capital']=100
            crlf=raw.replace(', ', ',\r\n ');old['inputSha256']=hashlib.sha256(crlf.encode()).hexdigest()
            (root/'input.json').write_bytes(crlf.encode('utf-8'));(root/'result.json').write_text(json.dumps(old),'utf-8')
            self.assertIn('|频率|每20个观察期',followup(old,new,root))
            (root/'input.json').write_text(raw+' ','utf-8')
            self.assertIn('没有匹配',followup(old,document,root))


    def test_judgment_distinguishes_joint_gain_and_joint_loss(self):
        data=self.sample();data['results'][1]['totalReturnPct']=12
        self.assertIn('同时提高了',markdown(data))
        data['results'][1]['totalReturnPct']=8;data['results'][1]['maximumDrawdownPct']=25
        self.assertIn('收益都更低、回撤也更深',markdown(data))
        data['results'][1]['totalReturnPct']=10;data['results'][1]['maximumDrawdownPct']=20
        self.assertIn('未改变收益和回撤',markdown(data))

    def test_names_and_source_links_are_readable_without_script_urls(self):
        result=self.sample();result['assets']=[{'code':'588000','name':'科创50ETF华夏','sourceUrl':'https://example.org/a(b)'},{'code':'B','sourceUrl':'javascript:alert(1)'}]
        body=markdown(result)
        self.assertIn('[科创50ETF华夏 588000](https://example.org/a%28b%29)',body)
        self.assertNotIn('javascript:',body)

    def test_zero_cost_reference_preserves_strategy_and_original(self):
        original={'periodicRule':'month-change','assets':[{'code':'A','weight':1}],
                  'blockedDates':[{'code':'A','date':'2025-01-01'}],
                  'costs':{'commissionPct':.03},'costsByCode':{'A':{'sellTaxPct':.1}},'costCounterfactual':True}
        zero=zero_cost_input(original)
        self.assertEqual(zero['assets'],original['assets'])
        self.assertEqual(zero['blockedDates'],original['blockedDates'])
        self.assertEqual(zero['periodicRule'],'month-change')
        self.assertTrue(all(value==0 for value in zero['costs'].values()))
        self.assertEqual(zero['costsByCode']['A']['sellTaxPct'],0)
        self.assertEqual(original['costsByCode']['A']['sellTaxPct'],.1)
        self.assertNotIn('costCounterfactual',zero)

if __name__=='__main__':unittest.main()
