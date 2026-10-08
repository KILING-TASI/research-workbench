import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import batch_collect as batch
from collection_quality_brief import brief


class CollectionMethodWindow(unittest.TestCase):
    def document(self):
        return {'asOf':'2026-09-30','refresh':True,'jobId':'scope','requests':[{'kind':'fund','code':'008903','start':'2026-09-01'}]}
    def test_changed_method_refuses_success_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory,patch('batch_collect.method_hashes',return_value={'collector':'old'}):
            legacy=lambda *args:{'rows':[{'code':'008903','kind':'fund','history':[{'date':'2026-09-02','nav':1}],'errors':None}]}
            result=batch.run(directory,self.document(),legacy);path=Path(result['checkpoint']);before=path.read_bytes()
            document={**self.document(),'resume':True}
            with patch('batch_collect.method_hashes',return_value={'collector':'new'}),patch('batch_collect.collect_market') as fetch:
                with self.assertRaisesRegex(ValueError,'方法已变更'):batch.run(directory,document,legacy)
                fetch.assert_not_called()
            self.assertEqual(path.read_bytes(),before)
    def test_missing_method_checkpoint_not_silently_resumed(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy=lambda *args:{'rows':[{'history':[{'date':'2026-09-02','nav':1}]}]}
            result=batch.run(directory,self.document(),legacy);path=Path(result['checkpoint']);state=json.loads(path.read_text('utf-8'));state.pop('methodFiles');path.write_text(json.dumps(state),'utf-8')
            with self.assertRaisesRegex(ValueError,'旧断点未登记方法'):batch.run(directory,{**self.document(),'resume':True},legacy)
    def row(self,code,dates):
        return {'code':code,'kind':'fund','history':[{'date':day,'nav':1} for day in dates],'requestScope':{'start':'2026-09-01','asOf':'2026-09-30'},'gaps':[]}
    def test_common_dates_and_excluded_quote_only(self):
        a=self.row('008903',['2026-09-02','2026-09-03','2026-09-04']);b=self.row('009548',['2026-09-03','2026-09-04','2026-09-05']);c=self.row('159869',[])
        text=brief({'asOf':'2026-09-30','rows':[a,b,c]})
        self.assertIn('2026-09-03至2026-09-04，共2个日期',text);self.assertIn('未纳入日期对齐：159869',text)
        self.assertIn('不能标成完整请求期间的表现',text)
    def test_no_overlap_is_not_filled_or_comparable(self):
        text=brief({'asOf':'2026-09-30','rows':[self.row('008903',['2026-09-02','2026-09-03']),self.row('009548',['2026-09-04','2026-09-05'])]})
        self.assertIn('共同观测日期不足2个',text)
    def test_scope_conflict_rejected(self):
        row=self.row('008903',['2026-09-02']);row['requestScope']['asOf']='2026-09-29'
        with self.assertRaisesRegex(ValueError,'截止日不一致'):brief({'asOf':'2026-09-30','rows':[row]})
    def test_history_before_requested_start_rejected(self):
        row=self.row('008903',['2026-08-31'])
        with self.assertRaisesRegex(ValueError,'早于请求起始日'):brief({'asOf':'2026-09-30','rows':[row]})
    def test_scope_survives_fund_date_filter_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            legacy=lambda *args:{'rows':[{'history':[{'date':'2026-08-31','nav':1},{'date':'2026-09-02','nav':1}]}]}
            result=batch.run(directory,self.document(),legacy);row=result['rows'][0]
            self.assertEqual([r['date'] for r in row['history']],['2026-09-02'])
            self.assertEqual(row['requestScope']['start'],'2026-09-01')
            resumed=batch.run(directory,{**self.document(),'resume':True},lambda *a:(_ for _ in ()).throw(AssertionError('unexpected fetch')))
            self.assertTrue(resumed['rows'][0]['resumed']);self.assertEqual(resumed['rows'][0]['requestScope'],row['requestScope'])
