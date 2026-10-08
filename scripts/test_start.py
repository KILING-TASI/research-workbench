import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from start import execute


class FirstUseTests(unittest.TestCase):
    def test_offline_demo_has_judgment_and_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'demo'
            result = execute('demo', out)
            self.assertEqual(result['mode'], 'teaching-demo')
            self.assertEqual(result['sourceVerification'], 'not-verified')
            calculation = json.loads((out / '比较结果.json').read_text('utf-8'))
            self.assertAlmostEqual(calculation['rows'][0]['totalReturnPct'], 10)
            self.assertAlmostEqual(calculation['rows'][1]['totalReturnPct'], -10)
            self.assertIn('不能证明经理能力', (out / '基金比较说明.md').read_text('utf-8'))
            self.assertIn('虚构样本', (out / '基金比较说明.html').read_text('utf-8'))
            self.assertTrue((out / 'report-manifest.json').exists())

    def test_missing_input_provides_recovery_without_fake_report(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'failure'
            result = execute('compare', out, Path(directory) / 'absent.json')
            self.assertEqual(result['failureKind'], 'missing-input')
            self.assertTrue(result['nextSteps'])
            self.assertTrue((out / '下一步.md').exists())
            self.assertFalse((out / '基金比较说明.html').exists())

    def test_existing_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            marker = out / 'mine.txt'
            marker.write_text('keep', 'utf-8')
            self.assertEqual(execute('demo', out)['failureKind'], 'output-exists')
            self.assertEqual(marker.read_text('utf-8'), 'keep')
            self.assertEqual(list(out.iterdir()), [marker])

    def test_invalid_json_is_not_published_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'input.json'
            source.write_text('{"rows": [], "rows": []}', 'utf-8')
            out = Path(directory) / 'failure'
            self.assertEqual(execute('compare', out, source)['status'], 'blocked')
            self.assertFalse((out / 'input.json').exists())

    def test_question_missing_catalog_gives_readable_report(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / 'ask'
            result = execute('ask', out, question='分析招商银行最近三个月公告', as_of='2026-10-08')
            self.assertEqual(result['status'], 'needs-clarification')
            research = json.loads((out / '研究结果.json').read_text('utf-8'))
            self.assertEqual(research['failureKind'], 'missing-local-catalog')
            self.assertTrue(Path(research['archivePath']).exists())
            self.assertIn('--online', (out / '研究结果.md').read_text('utf-8'))

    def test_ask_rebases_archive_after_atomic_publication(self):
        from research_question import run
        def offline(spec, workspace):
            spec = dict(spec, items=[{'date':'2026-09-01','title':'半年度报告'}])
            def identity(*args):
                return {'rows':[{'kind':'stock','code':'600036','name':'招商银行','identityVerification':'test'}]}
            return run(spec, workspace, searcher=identity)
        with tempfile.TemporaryDirectory() as directory, patch('research_question.run', side_effect=offline):
            out = Path(directory) / 'ask'
            self.assertEqual(execute('ask', out, question='分析招商银行近三个月公告', as_of='2026-10-08')['status'], 'partial')
            research = json.loads((out / '研究结果.json').read_text('utf-8'))
            archive = Path(research['archivePath'])
            self.assertTrue(archive.exists())
            self.assertEqual(json.loads(archive.read_text('utf-8'))['archivePath'],str(archive))

    def test_funds_without_online_does_not_fetch(self):
        with tempfile.TemporaryDirectory() as directory, patch('portable_collect.get') as fetch:
            result=execute('funds',Path(directory)/'funds',codes=['000001','000002'],start='2026-09-01',as_of='2026-09-30',group='比较池')
            self.assertEqual(result['status'],'blocked')
            fetch.assert_not_called()

    def test_snapshot_gateway_has_preserved_input_and_partial_status(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory);source=base/'mine.csv'
            source.write_text('code,name,market_value,currency,asset_class\nfund-A,A,100,CNY,fund\n','utf-8')
            out=base/'snapshot'
            result=execute('snapshot',out,input_path=source,as_of='2026-10-08')
            self.assertEqual(result['status'],'partial')
            self.assertEqual((out/'input.csv').read_bytes(),source.read_bytes())
            self.assertTrue((out/'持仓结构.html').exists())

    def test_broken_csv_or_uncomputable_amount_returns_recovery(self):
        for row in ['A,"unfinished,100,CNY,fund\n','A,A,1e999999999,CNY,fund\n']:
            with tempfile.TemporaryDirectory() as directory:
                base=Path(directory);source=base/'input.csv'
                source.write_text('code,name,market_value,currency,asset_class\n'+row,'utf-8')
                out=base/'result'
                result=execute('snapshot',out,input_path=source,as_of='2026-10-08')
                self.assertEqual(result['status'],'blocked')
                self.assertTrue((out/'下一步.md').exists())
                self.assertFalse((out/'持仓结构.html').exists())


if __name__ == '__main__':
    unittest.main()
