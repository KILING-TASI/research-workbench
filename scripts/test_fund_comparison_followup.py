import copy,json,tempfile,unittest
from pathlib import Path
from fund_comparison_brief import publish
from fund_comparison_followup import build

class Tests(unittest.TestCase):
    def spec(self):
        return dict(start='2026-01-01',asOf='2026-01-03',rows=[dict(code=c,name=c,currency='CNY',comparisonGroup='声明池',basis='nav-with-distributions',frequency='trading_day',history=[dict(date=f'2026-01-0{i+1}',nav=v) for i,v in enumerate(values)]) for c,values in [('000001',[1,1.1,1.2]),('000002',[1,.9,1])]])
    def test_shorter_window_recomputed_without_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=self.spec();publish(old,root/'comparison');snapshot=(root/'comparison/input.json').read_bytes()
            new=copy.deepcopy(old);new['start']='2026-01-02';r,text=build(root,new)
            self.assertEqual(r['status'],'same-context-window-review');self.assertAlmostEqual(r['before']['rows'][0]['totalReturnPct'],20)
            self.assertAlmostEqual(r['after']['rows'][0]['totalReturnPct'],(1.2/1.1-1)*100)
            self.assertAlmostEqual(r['intervalExplanations'][0]['returnPct'],10)
            self.assertIn('不是把两个收益率直接相减',text)
            self.assertIn('不能把数字变大或变小理解成基金本身变好了',text);self.assertEqual(snapshot,(root/'comparison/input.json').read_bytes())
    def test_context_or_revised_history_not_attributed_to_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=self.spec();publish(old,root/'comparison')
            for key,value in [('basis','qfq'),('comparisonGroup','另一个池')]:
                new=copy.deepcopy(old)
                if key=='basis':
                    for row in new['rows']:
                        row['basis']=value
                        for h in row['history']:h['close']=h.pop('nav')
                else:
                    for row in new['rows']:row[key]=value
                r,text=build(root,new);self.assertEqual(r['status'],'not-directly-comparable');self.assertNotIn('|产品|',text)
            new=copy.deepcopy(old);new['rows'][0]['history'][1]['nav']=1.11
            self.assertEqual(build(root,new)[0]['status'],'not-directly-comparable')
    def test_no_decomposition_for_changed_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=self.spec();publish(old,root/'comparison')
            new=copy.deepcopy(old);new['asOf']='2026-01-02'
            r,text=build(root,new)
            self.assertEqual(r['intervalExplanations'],[])
            self.assertNotIn('两个起点之间',text)
    def test_missing_overlap_observation_not_explained_as_window_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=self.spec();publish(old,root/'comparison')
            new=copy.deepcopy(old)
            for row in new['rows']:row['history'].pop(1)
            r,text=build(root,new)
            self.assertEqual(r['status'],'not-directly-comparable')
            self.assertEqual(r['intervalExplanations'],[])
            self.assertIn('观察日期不一致',text)
    def test_changed_input_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=self.spec();publish(old,root/'comparison')
            (root/'comparison/input.json').write_text('{}','utf-8')
            with self.assertRaisesRegex(ValueError,'改变'):build(root,old)

if __name__=='__main__':unittest.main()
