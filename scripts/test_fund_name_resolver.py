import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from fund_name_resolver import resolve


class Names(unittest.TestCase):
    def catalog(self):
        return 'var r='+json.dumps([['000001','A','测试成长基金A','混合型'],['000002','C','测试成长基金C','混合型'],['000003','B','测试价值基金A','混合型'],['510300','ETF','测试指数ETF','指数型']],ensure_ascii=False)+';'

    def test_full_names_resolve_without_dropping_share_class(self):
        with tempfile.TemporaryDirectory() as folder:
            r=resolve(['测试成长基金A','测试价值基金A'],Path(folder)/'result',online=True,fetch=lambda url:self.catalog())
            self.assertEqual(r['codes'],['000001','000003'])

    def test_provider_utf8_bom_is_accepted_without_executing_script(self):
        with tempfile.TemporaryDirectory() as folder:
            r=resolve(['测试成长基金A','测试价值基金A'],Path(folder)/'result',online=True,fetch=lambda url:'\ufeff'+self.catalog())
            self.assertEqual(r['status'],'resolved')

    def test_partial_name_and_etf_do_not_download_as_fund(self):
        with tempfile.TemporaryDirectory() as folder:
            r=resolve(['测试成长基金','测试指数ETF'],Path(folder)/'result',online=True,fetch=lambda url:self.catalog())
            self.assertEqual(r['status'],'needs-clarification');self.assertEqual(r['codes'],[])
            self.assertEqual(r['matches'][0]['candidateCount'],2)

    def test_previous_catalog_can_be_reused_without_network(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);resolve(['测试成长基金A','测试价值基金A'],root/'old'/'identity',online=True,fetch=lambda url:self.catalog())
            fetch=Mock(side_effect=AssertionError('network forbidden'))
            r=resolve(['测试成长基金A','测试价值基金A'],root/'new',reuse_from=root/'old',fetch=fetch)
            self.assertEqual(r['status'],'resolved');self.assertTrue(r['catalog']['reused']);fetch.assert_not_called()

    def test_tampered_catalog_is_not_reused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);resolve(['测试成长基金A','测试价值基金A'],root/'old'/'identity',online=True,fetch=lambda url:self.catalog())
            (root/'old'/'identity'/'catalog.txt').write_text(self.catalog()+' ','utf-8')
            with self.assertRaisesRegex(ValueError,'未取得可复用'):resolve(['测试成长基金A','测试价值基金A'],root/'new',reuse_from=root/'old')

    def test_invalid_or_future_catalog_time_is_not_reused(self):
        for timestamp in ['not-a-date','2026-01-01T00:00:00','2999-01-01T00:00:00+00:00']:
            with self.subTest(timestamp=timestamp), tempfile.TemporaryDirectory() as folder:
                root=Path(folder)
                resolve(['测试成长基金A','测试价值基金A'],root/'old'/'identity',online=True,fetch=lambda url:self.catalog())
                path=root/'old'/'identity'/'result.json'
                record=json.loads(path.read_text('utf-8'));record['catalog']['retrievedAt']=timestamp
                path.write_text(json.dumps(record),'utf-8')
                fetch=Mock(side_effect=AssertionError('network forbidden'))
                with self.assertRaisesRegex(ValueError,'未取得可复用'):
                    resolve(['测试成长基金A','测试价值基金A'],root/'new',reuse_from=root/'old',fetch=fetch)
                fetch.assert_not_called()


if __name__=='__main__':unittest.main()
