import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch
import batch_collect as batch
import market_collect as market

class CollectionTests(unittest.TestCase):
    def test_direct_financial_start_rejects_non_stock_before_fetch(self):
        with patch.object(market,'history') as fetch:
            with self.assertRaisesRegex(ValueError,'仅用于股票'):market.collect_market('.','etf','510300','2025-12-31',True,financial_start='2025-01-01')
            fetch.assert_not_called()
    def test_supplier_json_rejects_duplicates_and_nonfinite(self):
        for payload in ['{"data":1,"data":2}','{"price":NaN}','{"price":Infinity}']:
            with self.subTest(payload=payload),patch.object(market,'get',return_value=payload):
                with self.assertRaises(ValueError):market.fetch('https://example.org')
    def doc(self, **kw):
        return dict(asOf='2025-12-31',refresh=True,jobId='test',requests=[{'kind':'stock','code':'600036','start':'2025-01-01'}],**kw)
    def test_retry_resume_and_changed_input(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(batch,'collect_market',side_effect=[{'errors':'TimeoutError','history':[]},{'errors':{},'history':[{'date':'2025-01-01','open':10,'close':10,'high':10,'low':10}]}]) as f,patch.object(batch.time,'sleep'):
                result=batch.run(root,self.doc(),None)
                self.assertEqual(f.call_count,2)
                self.assertEqual(result['rows'][0]['collectionStatus'],'available')
            with patch.object(batch,'collect_market',side_effect=AssertionError('resume fetched')):
                self.assertTrue(batch.run(root,self.doc(resume=True),None)['rows'][0]['resumed'])
                d=self.doc(resume=True);d['asOf']='2025-12-30'
                with self.assertRaises(ValueError):batch.run(root,d,None)
    def test_no_retry_access_denial(self):
        with tempfile.TemporaryDirectory() as root,patch.object(batch,'collect_market',return_value={'errors':'HTTPError: 403','history':[]}) as f:
            batch.run(root,self.doc(),None);self.assertEqual(f.call_count,1)
    def test_modified_success_checkpoint_refetched(self):
        with tempfile.TemporaryDirectory() as root,patch.object(batch,'collect_market',return_value={'errors':None,'history':[{'date':'2025-01-02','open':10,'close':10,'high':10,'low':10}]}) as f:
            r=batch.run(root,self.doc(),None);p=Path(r['checkpoint']);state=json.loads(p.read_text(encoding='utf-8'));state['rows']['0']['history'][0]['close']=999;p.write_text(json.dumps(state),encoding='utf-8')
            result=batch.run(root,self.doc(resume=True),None)
            self.assertEqual(f.call_count,2);self.assertEqual(result['rows'][0]['history'][0]['close'],10);self.assertIn('resumeValidation',result['rows'][0])
    def test_broken_checkpoint_rejected_before_fetch(self):
        with tempfile.TemporaryDirectory() as root,patch.object(batch,'collect_market') as f:
            p=Path(root)/'research-data/batches/test.json';p.parent.mkdir(parents=True);p.write_text('{broken',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'断点文件不可读'):batch.run(root,self.doc(resume=True),None)
            f.assert_not_called();self.assertEqual(p.read_text(),'{broken')
    def test_denial_with_timeout_text_is_not_retried(self):
        with tempfile.TemporaryDirectory() as root,patch.object(batch,'collect_market',return_value={'errors':'HTTP 403 connection timed out','history':[]}) as f:
            r=batch.run(root,self.doc(),None)
            self.assertEqual(f.call_count,1);self.assertEqual(r['coverage']['unavailable'],1)
    def test_resume_string_rejected_before_fetch(self):
        with tempfile.TemporaryDirectory() as root,patch.object(batch,'collect_market') as f:
            with self.assertRaisesRegex(ValueError,'resume'):batch.run(root,self.doc(resume='false'),None)
            f.assert_not_called();self.assertFalse((Path(root)/'research-data').exists())
    def test_cache_survives_component_failure(self):
        with tempfile.TemporaryDirectory() as root:
            args=(root,'stock','600036','2025-12-31',True,'2025-01-01')
            with patch.object(market,'history',return_value=([{'date':'2025-01-02','open':10,'close':10,'high':10,'low':10}],['https://example.org'])),patch.object(market,'financials',return_value=([{'period':'2025-01-01','publishedAt':'2025-01-02'}],['https://example.org'])),patch.object(market,'announcements',return_value=([{'id':'a','date':'2025-01-02'}],['https://example.org'])):
                first=market.collect_market(*args)
            with patch.object(market,'history',side_effect=TimeoutError()),patch.object(market,'financials',side_effect=TimeoutError()),patch.object(market,'announcements',side_effect=TimeoutError()):
                second=market.collect_market(*args)
            self.assertEqual(first['history'],second['history'])
            self.assertEqual(first['components']['history']['retrievedAt'],second['components']['history']['retrievedAt'])
            self.assertEqual(second['components']['history']['status'],'cached-after-failure')
    def test_empty_announcements_not_verified_absence(self):
        with patch.object(market,'fetch',return_value={'data':{'list':[],'total_hits':0}}):
            with self.assertRaises(ValueError):market.announcements('510300','2025-01-01','2025-12-31')
    def test_corrupt_cache_is_gap_not_batch_crash(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root)/'research-data/etf/512660-1/history-2026-09-01-2026-09-30.json';p.parent.mkdir(parents=True);p.write_text('{"rows":null}',encoding='utf-8')
            r=market.collect_market(root,'etf','512660','2026-09-30',False,'2026-09-01')
            self.assertEqual(r['history'],[]);self.assertIn('缓存不可用',r['errors']['history'])
    def test_bond_requires_market(self):
        with self.assertRaises(ValueError):market.collect_market('.','bond','123456','2025-12-31',True)
    def test_late_invalid_request_rejects_whole_batch_before_fetch(self):
        for request in [{'kind':'etf','code':'512660','start':'2026-01-01'},{'kind':'bond','code':'019766'},{'kind':'etf','code':'512660','market':True}]:
            with self.subTest(request=request),tempfile.TemporaryDirectory() as root,patch.object(batch,'collect_market') as f:
                d=self.doc();d['requests'].append(request)
                with self.assertRaises(ValueError):batch.run(root,d,None)
                f.assert_not_called();self.assertFalse((Path(root)/'research-data').exists())
    def test_more_than_50_and_isolation(self):
        d=self.doc();d['requests']=[{'kind':'stock','code':str(600000+i)} for i in range(51)]
        with tempfile.TemporaryDirectory() as root,patch.object(batch,'collect_market',side_effect=lambda *a: {'errors':'bad' if a[2]=='600001' else None,'history':[] if a[2]=='600001' else [{'date':'2025-01-02','open':10,'close':10,'high':10,'low':10}]}):
            r=batch.run(root,d,None);self.assertEqual(r['coverage']['available'],50);self.assertEqual(r['coverage']['unavailable'],1)

class StrictMarketCacheTests(unittest.TestCase):
    def test_duplicate_fields_cannot_reuse_matching_canonical_hash(self):
        for mode in ['root','nested']:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as root:
                good=[{'date':'2026-09-01','open':10,'close':10,'high':10,'low':10}]
                with patch.object(market,'history',return_value=(good,['https://example.org/history'])),patch.object(market,'fund_announcements',side_effect=ValueError('not available')):
                    market.collect_market(root,'etf','510880','2026-09-30',True,'2026-09-01')
                p=Path(root)/'research-data/etf/510880-1/history-2026-09-01-2026-09-30.json'
                raw=json.dumps(json.loads(p.read_text('utf-8')))
                if mode=='root':raw='{"rows": [],'+raw[1:]
                else:raw=raw.replace('"open": 10','"open": 999, "open": 10',1)
                p.write_text(raw,encoding='utf-8');before=p.read_bytes()
                out=market.collect_market(root,'etf','510880','2026-09-30',False,'2026-09-01')
                self.assertEqual(out['history'],[]);self.assertIn('重复字段',out['errors']['history']);self.assertEqual(p.read_bytes(),before)

if __name__=='__main__':unittest.main()
