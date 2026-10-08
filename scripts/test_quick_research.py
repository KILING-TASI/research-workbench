import datetime as dt
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from quick_research import snapshot, fund_codes


class QuickResearchTests(unittest.TestCase):
    def test_boundary_failure_response_can_be_revalidated_offline_for_explicit_new_window(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);old=base/'old'
            first=fund_codes(['000001','000002'],'2026-08-01','2026-09-03','池',old,fetch=lambda url:self.raw(url.split('/')[-1][:6]))
            self.assertEqual(first['status'],'blocked')
            self.assertIn('实际记录',json.loads((old/'collection.json').read_text('utf-8'))['000001']['error'])
            def forbidden(url):raise AssertionError('不要重复联网')
            still_failed=fund_codes(['000001','000002'],'2026-08-01','2026-09-03','池',base/'still-failed',reuse_from=old,allow_online=False,fetch=forbidden)
            self.assertEqual(still_failed['status'],'blocked')
            self.assertIn('当前区间实际记录', (base/'still-failed/基金资料未完成.md').read_text('utf-8'))
            second=fund_codes(['000001','000002'],'2026-09-01','2026-09-03','池',base/'new',reuse_from=old,allow_online=False,fetch=forbidden)
            self.assertEqual(second['status'],'partial')
            records=json.loads((base/'new/collection.json').read_text('utf-8'))
            self.assertTrue(all(r['reused'] and r['previousCollectionStatus']=='failed' for r in records.values()))
    def test_share_class_names_are_only_clues_and_stock_names_are_excluded(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'input.csv'
            source.write_text('code,name,market_value,currency,asset_class\n1,测试债券基金A,100,CNY,fund\n2,测试债券基金C,200,CNY,fund\n3,测试科技股票A,50,CNY,stock\n4,测试科技股票C,50,CNY,stock\n','utf-8')
            result=snapshot(source,root/'report','2026-09-30')
            self.assertEqual(len(result['shareClassClues']),1)
            clue=result['shareClassClues'][0]
            self.assertEqual(clue['codes'],['1','2']);self.assertEqual(Decimal(clue['weightPct']),75)
            self.assertEqual(clue['status'],'name-based-share-class-clue-not-verified')
    def test_valid_previous_raw_is_recomputed_without_download(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);old=base/'old'
            fund_codes(['000001','000002'],'2026-09-01','2026-09-03','比较池',old,fetch=lambda url:self.raw(url.split('/')[-1][:6]))
            def forbidden(url):raise AssertionError('network forbidden')
            r=fund_codes(['000001','000002'],'2026-09-01','2026-09-03','新比较池',base/'new',reuse_from=old,allow_online=False,fetch=forbidden)
            self.assertEqual(r['status'],'partial')
            records=json.loads((base/'new'/'collection.json').read_text('utf-8'))
            self.assertTrue(all(row['reused'] for row in records.values()))
            self.assertEqual((old/'raw'/'000001.txt').read_bytes(),(base/'new'/'raw'/'000001.txt').read_bytes())

    def test_resume_only_downloads_failed_fund(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);old=base/'old'
            def first(url):
                if '000002' in url:raise OSError('failed')
                return self.raw('000001')
            fund_codes(['000001','000002'],'2026-09-01','2026-09-03','池',old,fetch=first)
            calls=[]
            def second(url):calls.append(url);return self.raw('000002')
            r=fund_codes(['000001','000002'],'2026-09-01','2026-09-03','池',base/'new',fetch=second,reuse_from=old)
            self.assertEqual(r['status'],'partial');self.assertEqual(len(calls),1);self.assertIn('000002',calls[0])

    def test_changed_raw_hash_does_not_pass_offline(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);old=base/'old'
            fund_codes(['000001','000002'],'2026-09-01','2026-09-03','池',old,fetch=lambda url:self.raw(url.split('/')[-1][:6]))
            with (old/'raw'/'000001.txt').open('a',encoding='utf-8') as f:f.write(' ')
            r=fund_codes(['000001','000002'],'2026-09-01','2026-09-03','池',base/'new',reuse_from=old,allow_online=False)
            self.assertEqual(r['failedCodes'],['000001']);self.assertFalse((base/'new'/'comparison').exists())
    def test_chinese_headers_and_declared_units_preserve_amounts(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);source=base/'中文持仓.csv'
            source.write_text('基金代码,基金名称,当前市值,币种,资产类型,估值日期\n001,基金A,"1,000.00",人民币,基金,2026-09-30\n002,ETF B,1000,cny,ETF,2026-09-30\n','utf-8-sig')
            r=snapshot(source,base/'result','2026-10-08')
            self.assertEqual(Decimal(r['totalMarketValue']),Decimal('2000'))
            self.assertEqual(r['currency'],'CNY')
            self.assertEqual(r['columnMapping']['当前市值'],'market_value')
            self.assertEqual(Decimal(r['holdings'][0]['weightPct']),Decimal('50'))
            self.assertEqual((base/'result/input.csv').read_bytes(),source.read_bytes())

    def test_alias_collision_and_ambiguous_amount_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);source=base/'input.csv'
            source.write_text('code,基金代码,name,market_value,currency,asset_class\n001,002,A,100,CNY,fund\n','utf-8')
            with self.assertRaisesRegex(ValueError,'指向同一字段'):snapshot(source,base/'report','2026-10-08')
            source.write_text('代码,名称,市值,币种,资产类型\n001,A,10万,人民币,基金\n','utf-8')
            with self.assertRaisesRegex(ValueError,'不要填'):snapshot(source,base/'report','2026-10-08')
            self.assertFalse((base/'report').exists())
    def csv(self, base, rows):
        source=base/'holdings.csv'
        source.write_text('code,name,market_value,currency,asset_class,valuation_date\n'+rows,'utf-8-sig')
        return source

    def test_snapshot_exact_amounts_not_health_score(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            source=self.csv(base,'001,基金A,80,CNY,fund,2026-09-30\n002,基金C,20,CNY,fund,\n')
            result=snapshot(source,base/'report','2026-10-08')
            self.assertEqual(result['totalMarketValue'],'100')
            self.assertEqual(Decimal(result['holdings'][0]['weightPct']),Decimal('80'))
            self.assertEqual(result['status'],'partial')
            self.assertNotIn('healthScore',result)
            self.assertTrue(result['gaps'])
            self.assertEqual((base/'report/input.csv').read_bytes(),source.read_bytes())

    def test_mixed_currencies_and_future_values_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            source=self.csv(base,'001,A,80,CNY,fund,\n002,B,20,USD,fund,\n')
            with self.assertRaisesRegex(ValueError,'单一币种'):snapshot(source,base/'report','2026-10-08')
            self.assertFalse((base/'report').exists())
            source=self.csv(base,'001,A,80,CNY,fund,2026-10-09\n')
            with self.assertRaisesRegex(ValueError,'晚于'):snapshot(source,base/'report','2026-10-08')

    def test_duplicate_or_invalid_csv_not_silently_combined(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            source=self.csv(base,'001,A,80,CNY,fund,\n001,A,20,CNY,fund,\n')
            with self.assertRaisesRegex(ValueError,'重复'):snapshot(source,base/'report','2026-10-08')
            source=self.csv(base,'001,A,NaN,CNY,fund,\n')
            with self.assertRaises(ValueError):snapshot(source,base/'report','2026-10-08')

    def raw(self, code):
        points=[]
        for date,value in [('2026-09-01',1),('2026-09-02',1.1),('2026-09-03',1.2)]:
            timestamp=dt.datetime.fromisoformat(date).replace(tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp()*1000
            points.append({'x':timestamp,'y':value,'unitMoney':''})
        return 'var fS_code="'+code+'";var fS_name="测试'+code+'";var Data_netWorthTrend='+json.dumps(points)+';'

    def test_fund_codes_reuse_comparison_and_preserve_raw(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'funds'
            result=fund_codes(['000001','000002'],'2026-09-01','2026-09-03','我的比较池',out,
                              fetch=lambda url:self.raw(url.split('/')[-1][:6]))
            self.assertEqual(result['status'],'partial')
            self.assertTrue((out/'comparison/report-manifest.json').exists())
            self.assertEqual((out/'raw/000001.txt').read_text('utf-8'),self.raw('000001'))
            collection=json.loads((out/'collection.json').read_text('utf-8'))
            self.assertEqual(collection['000001']['observations'],3)

    def test_one_failed_fund_does_not_shrink_comparison_pool(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'funds'
            def fetch(url):
                if '000002' in url:raise OSError('source unavailable')
                return self.raw('000001')
            result=fund_codes(['000001','000002'],'2026-09-01','2026-09-03','比较池',out,fetch=fetch)
            self.assertEqual(result['failedCodes'],['000002'])
            self.assertFalse((out/'comparison').exists())
            self.assertTrue((out/'raw/000001.txt').exists())

    def test_code_identity_mismatch_remains_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)/'funds'
            result=fund_codes(['000001','000002'],'2026-09-01','2026-09-03','比较池',out,fetch=lambda url:self.raw('999999'))
            self.assertEqual(result['status'],'blocked')
            self.assertEqual(result['failedCodes'],['000001','000002'])


if __name__=='__main__':unittest.main()
