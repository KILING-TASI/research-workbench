import datetime as dt
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from quick_research import snapshot, fund_codes


class QuickResearchTests(unittest.TestCase):
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
