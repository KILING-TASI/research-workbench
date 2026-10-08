import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from source_health import prepare, run


def encoded(value):
    return json.dumps(value).encode()


def domestic(code='510500', date='2026-09-30'):
    return encoded({'data': {'code': code, 'name': '教学名称',
                             'klines': [date + ',10,11,12,9,100,1000']}})


class SourceHealthTests(unittest.TestCase):
    def test_fund_embedded_json_does_not_accept_duplicate_nav(self):
        spec=self.spec([dict(profile='fund-nav',code='000001')])
        raw=b'var fS_code="000001";var fS_name="Teaching";var Data_netWorthTrend=[{"x":1759190400000,"y":1,"y":2}];'
        result=self.execute(spec,lambda *a,**k:raw)
        self.assertEqual(result['rows'][0]['status'],'invalid-sample')
        self.assertFalse(result['rows'][0]['sampleValid'])
    def test_profile_shape_is_rejected_before_run(self):
        spec=self.spec();spec['requests'][0]['profile']=[]
        with self.assertRaises(ValueError):prepare(spec)
    def spec(self, requests=None):
        return {'asOf': '2026-10-05', 'requests': requests or [
            {'profile': 'cn-history-eastmoney', 'code': '510500', 'market': '1'}]}

    def execute(self, spec, fetch):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'check'
            result = run(spec, out, fetch)
            self.assertTrue((out / 'result.json').exists())
            self.assertTrue((out / '数据源体检.html').exists())
            for row in result['rows']:
                for entry in row['attempts']:
                    if entry.get('responsePath'):
                        self.assertTrue((out / entry['responsePath']).exists())
            return result

    def test_success_has_dates_but_no_full_coverage_or_original_claim(self):
        result = self.execute(self.spec(), lambda *a, **k: domestic())
        row = result['rows'][0]
        self.assertTrue(row['sampleValid'])
        self.assertFalse(row['coverageVerified'])
        self.assertFalse(row['originalVerified'])
        self.assertEqual(row['freshness']['lagCalendarDays'], 5)
        self.assertFalse(row['freshness']['calendarVerified'])

    def test_stale_does_not_erase_valid_observations(self):
        spec = self.spec(); spec['requests'][0]['maxLagDays'] = 2
        result = self.execute(spec, lambda *a, **k: domestic())
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(result['rows'][0]['sampleValid'])
        self.assertEqual(result['rows'][0]['freshness']['status'], 'stale')

    def test_wrong_identity_not_usable(self):
        result = self.execute(self.spec(), lambda *a, **k: domestic('000001'))
        self.assertEqual(result['rows'][0]['status'], 'invalid-sample')
        self.assertFalse(result['rows'][0]['sampleValid'])

    def test_empty_data_is_not_no_trading(self):
        result = self.execute(self.spec(), lambda *a, **k: encoded({'data': {'code': '510500', 'name': '教学', 'klines': []}}))
        self.assertEqual(result['rows'][0]['status'], 'empty-sample')
        self.assertEqual(result['rows'][0]['freshness']['status'], 'unknown')

    def test_duplicate_json_and_nonfinite_values_are_rejected(self):
        for raw in [b'{"data":{},"data":null}', b'{"data":NaN}']:
            self.assertEqual(self.execute(self.spec(), lambda *a, **k: raw)['rows'][0]['status'], 'invalid-sample')

    def test_invalid_ohlc_and_out_of_window_are_rejected(self):
        for raw in [domestic(date='2026-01-01'), domestic().replace(b'10,11,12,9', b'10,11,8,9')]:
            self.assertEqual(self.execute(self.spec(), lambda *a, **k: raw)['rows'][0]['status'], 'invalid-sample')

    def test_blocked_source_is_not_retried_for_other_codes(self):
        requests = [{'profile': 'cn-history-eastmoney', 'code': c, 'market': '1'} for c in ['510500', '510300']]
        calls = []
        def blocked(url, **kw):
            calls.append(url)
            raise HTTPError(url, 429, 'limited', {}, None)
        result = self.execute(self.spec(requests), blocked)
        self.assertEqual(len(calls), 1)
        self.assertEqual([r['status'] for r in result['rows']], ['blocked', 'skipped-source-blocked'])
        self.assertTrue(result['rows'][0]['endpointResponded'])

    def test_timeout_partial_failure_preserves_another_success(self):
        requests = [{'profile': 'cn-history-eastmoney', 'code': c, 'market': '1'} for c in ['510500', '510300']]
        def fetch(url, **kw):
            if '510500' in url: raise TimeoutError('teaching timeout')
            return domestic('510300')
        result = self.execute(self.spec(requests), fetch)
        self.assertEqual([r['status'] for r in result['rows']], ['network-error', 'observed'])

    def test_us_mapping_is_followed_once_and_identity_checked(self):
        calls = []
        def fetch(url, **kw):
            calls.append(url)
            sym = 'usMSFT' if len(calls) == 1 else 'usMSFT.OQ'
            return encoded({'code': 0, 'data': {sym: {'qt': {sym: ['', 'Microsoft', 'MSFT.OQ']},
                            'day': [] if len(calls) == 1 else [['2026-09-30', '10', '11', '12', '9']]}}})
        result = self.execute(self.spec([{'profile': 'hk-us-history', 'code': 'MSFT', 'market': 'US'}]), fetch)
        self.assertEqual(len(calls), 2)
        self.assertTrue(result['rows'][0]['sampleValid'])
        self.assertEqual(len(result['rows'][0]['attempts']), 2)

    def test_quote_only_not_confused_with_history(self):
        raw = encoded({'code': 0, 'data': {'hk00700': {'qt': {'hk00700': ['', 'Tencent', '00700']}}}})
        result = self.execute(self.spec([{'profile': 'hk-us-history', 'code': '00700', 'market': 'HK'}]), lambda *a, **k: raw)
        self.assertFalse(result['rows'][0]['sampleValid'])

    def test_one_observation_is_accessible_but_not_enough_for_returns(self):
        result = self.execute(self.spec(), lambda *a, **k: domestic())
        self.assertTrue(result['rows'][0]['sampleValid'])
        self.assertFalse(result['rows'][0]['minimumReturnObservationsMet'])
        self.assertEqual(result['status'], 'partial')

    def test_nav_window_and_positive_values_checked(self):
        stamp = int(dt.datetime(2026, 9, 30, tzinfo=dt.timezone(dt.timedelta(hours=8))).timestamp() * 1000)
        raw = ('var fS_code="161005";var fS_name="教学基金";var Data_netWorthTrend=' + json.dumps([{'x': stamp, 'y': 1.2}]) + ';').encode()
        spec = self.spec([{'profile': 'fund-nav', 'code': '161005'}])
        self.assertTrue(self.execute(spec, lambda *a, **k: raw)['rows'][0]['sampleValid'])
        bad = raw.replace(b'1.2', b'-1.2')
        self.assertFalse(self.execute(spec, lambda *a, **k: bad)['rows'][0]['sampleValid'])

    def test_financial_dates_differ_from_price_dates(self):
        raw = encoded({'result': {'data': [{'SECURITY_CODE': '601012', 'REPORT_DATE': '2026-06-30', 'NOTICE_DATE': '2026-08-30'}]}})
        result = self.execute(self.spec([{'profile': 'stock-financial-summary', 'code': '601012'}]), lambda *a, **k: raw)
        row = result['rows'][0]
        self.assertEqual(row['dateBasis'], '报告期末')
        self.assertEqual(row['latestPublishedAt'], '2026-08-30')
        self.assertEqual(row['freshness']['maxLagDays'], 210)

    def test_future_financial_disclosure_excluded(self):
        raw = encoded({'result': {'data': [{'SECURITY_CODE': '601012', 'REPORT_DATE': '2026-06-30', 'NOTICE_DATE': '2026-10-10'}]}})
        result = self.execute(self.spec([{'profile': 'stock-financial-summary', 'code': '601012'}]), lambda *a, **k: raw)
        self.assertEqual(result['rows'][0]['status'], 'empty-sample')

    def test_announcements_empty_and_duplicate_distinguished(self):
        spec = self.spec([{'profile': 'stock-announcements', 'code': '601012'}])
        self.assertEqual(self.execute(spec, lambda *a, **k: encoded({'data': {'list': []}}))['rows'][0]['status'], 'empty-sample')
        item = {'codes': [{'stock_code': '601012'}], 'notice_date': '2026-09-30', 'art_code': 'x', 'title': '教学'}
        self.assertEqual(self.execute(spec, lambda *a, **k: encoded({'data': {'list': [item, item]}}))['rows'][0]['status'], 'invalid-sample')

    def test_mixed_sources_available_alternative(self):
        spec = self.spec([{'profile': p, 'code': '510500', 'market': '1'} for p in ['cn-history-eastmoney', 'cn-history-tencent']])
        def fetch(url, **kw):
            if 'eastmoney' in url: raise TimeoutError()
            return encoded({'code': 0, 'data': {'sh510500': {'qt': {'sh510500': ['', '教学', '510500']},
                                   'day': [['2026-09-29', '10', '11', '12', '9', '100'],['2026-09-30', '10', '11', '12', '9', '100']]}}})
        result = self.execute(spec, fetch)
        self.assertEqual(result['alternatives'][0]['sampleUsableProfiles'], ['cn-history-tencent'])

    def test_all_inputs_validated_before_network_or_output(self):
        for request in [{'profile': 'fund-nav', 'code': '161005', 'url': 'https://localhost/'},
                        {'profile': 'cn-history-eastmoney', 'code': '510500'},
                        {'profile': 'fund-nav', 'code': '161005', 'maxLagDays': True}]:
            with tempfile.TemporaryDirectory() as folder:
                out = Path(folder) / 'output'
                with self.assertRaises(ValueError):
                    run(self.spec([request]), out, lambda *a, **k: self.fail('network attempted'))
                self.assertFalse(out.exists())
        with self.assertRaises(ValueError): prepare({**self.spec(), 'apiKey': 'do-not-store'})

    def test_output_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            sentinel = Path(folder) / 'original.txt'; sentinel.write_text('keep')
            with self.assertRaises(FileExistsError): run(self.spec(), folder, lambda *a, **k: self.fail('network'))
            self.assertEqual(sentinel.read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
