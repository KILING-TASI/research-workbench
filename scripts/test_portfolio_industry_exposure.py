import copy
import json
import tempfile
import unittest
from pathlib import Path
from portfolio_industry_exposure import build


class Tests(unittest.TestCase):
    def test_invalid_structure_and_number_raise_value_error(self):
        from portfolio_industry_exposure import number
        for value in [True,None,{},'abc','NaN']:
            with self.subTest(value=value),self.assertRaises(ValueError):number(value,'权重')
        for spec in [None,[],{},dict(reportDate='2026-06-30',assets=[None])]:
            with self.assertRaises(ValueError):build(spec,self.base)
        self.report['sectors'][0]['components']=[dict(locator=['PDF页1'])];self.save()
        with self.assertRaises(ValueError):build(self.spec,self.base)
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.report = dict(code='a', reportDate='2026-06-30', currency='CNY',
            netAssetsCNY=100, equityMarketValueCNY=80, taxonomy='A-S',
            taxonomyVersion='unverified', sourceSha256='fixture',
            sectors=[dict(key='C', name='制造业', marketValueCNY=80,
                components=[dict(locator='PDF页1')])])
        self.spec = dict(reportDate='2026-06-30', assets=[
            dict(code='a', allocation='.5', industryReport='a.json'),
            dict(code='b', allocation='.5', missingReason='未取得行业表')])

    def save(self, report=None):
        (self.base/'a.json').write_text(json.dumps(report or self.report), encoding='utf-8')

    def test_missing_retained_and_amount_recomputed(self):
        self.report['sectors'][0]['navWeight'] = .99  # Reject reliance on precomputed weights.
        self.save(); result = build(self.spec, self.base)
        self.assertEqual(result['knownEquityExposure'], '0.4')
        self.assertEqual(result['unclassifiedResidual'], '0.6')
        self.assertEqual(len(result['missingReports']), 1)

    def test_different_taxonomies_and_versions_separate(self):
        self.save(); other = copy.deepcopy(self.report); other['code'] = 'b'
        for taxonomy, version in [('GICS', 'unverified'), ('A-S', 'v2')]:
            other['taxonomy'] = taxonomy; other['taxonomyVersion'] = version
            (self.base/'b.json').write_text(json.dumps(other), encoding='utf-8')
            self.spec['assets'][1] = dict(code='b', allocation='.5', industryReport='b.json')
            self.assertEqual(len(build(self.spec, self.base)['sectors']), 2)

    def test_snapshot_currency_totals_and_locators_fail_closed(self):
        for key, value in [('code', 'wrong'), ('reportDate', '2025-06-30'),
                           ('currency', 'USD'), ('netAssetsCNY', 'NaN'),
                           ('equityMarketValueCNY', 79)]:
            report = copy.deepcopy(self.report); report[key] = value; self.save(report)
            with self.subTest(key=key), self.assertRaises(ValueError): build(self.spec, self.base)
        self.report['sectors'][0]['components'] = []; self.save()
        with self.assertRaises(ValueError): build(self.spec, self.base)

    def test_weights_and_missing_reason(self):
        self.save()
        self.spec['assets'][1]['allocation'] = '.4'
        with self.assertRaises(ValueError): build(self.spec, self.base)
        self.spec['assets'][1]['allocation'] = '.5'; self.spec['assets'][1].pop('missingReason')
        with self.assertRaises(ValueError): build(self.spec, self.base)


if __name__ == '__main__': unittest.main()
