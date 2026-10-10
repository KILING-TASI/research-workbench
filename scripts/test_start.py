import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from start import execute


class FirstUseTests(unittest.TestCase):
    def test_cashflow_missing_specialist_has_specific_guidance_and_retains_input(self):
        import os
        from start import ROOT
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch.dict(os.environ,{'RESEARCH_WORKBENCH_PORTFOLIO_DIR':str(root/'not-installed')}):
                result=execute('cashflow',root/'blocked',input_path=ROOT/'references/examples/example-cashflow-review.json')
            self.assertEqual(result['failureKind'],'missing-dependency')
            self.assertIn('portfolio-decision-engine',' '.join(result['nextSteps']))
            self.assertIn('其他研究可以继续',result['message'])
            self.assertEqual(result['dependencyCheck']['dataStatus'],'not-checked')
            self.assertTrue((root/'blocked/input.json').is_file())
    def test_data_gap_is_not_reported_as_missing_software(self):
        from start import ROOT
        with tempfile.TemporaryDirectory() as tmp:
            with patch('specialist_loader.require',return_value={'available':True}),patch('portfolio_cashflow_review.publish',side_effect=ValueError('资料来源尚未取得')):
                result=execute('cashflow',Path(tmp)/'blocked',input_path=ROOT/'references/examples/example-cashflow-review.json')
            self.assertEqual(result['failureKind'],'invalid-input-or-runtime')
            self.assertIn('资料来源尚未取得',result['message'])
            self.assertNotIn('安装',' '.join(result['nextSteps']))
    def test_unused_specialists_do_not_block_demo_or_report_continuation(self):
        from start import ROOT
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch('specialist_loader.check',side_effect=AssertionError('unused specialist must not be checked')):
                demo=execute('demo',root/'demo')
                first=execute('news',root/'old',input_path=ROOT/'references/examples/news-example.json')
                old=(root/'old/input.json').read_bytes()
                second=execute('news',root/'new',continue_from=root/'old')
            self.assertEqual(demo['status'],'passed');self.assertEqual(demo['sourceVerification'],'not-verified')
            self.assertEqual(first['status'],'partial');self.assertEqual(second['status'],'partial')
            self.assertEqual((root/'old/input.json').read_bytes(),old)
    def test_cashflow_gap_has_relevant_next_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'input.json';source.write_text(json.dumps({'cashFlowCoverage':'unknown'}),'utf-8')
            result=execute('cashflow',root/'blocked',input_path=source)
            self.assertEqual(result['status'],'blocked');self.assertIn('全部外部转入',result['nextSteps'][0])
            self.assertNotIn('净值',' '.join(result['nextSteps']));self.assertIn('不能仅修改完整性声明',' '.join(result['nextSteps']))
    def test_help_renders_percent_without_formatting_error(self):
        import subprocess,sys,os
        from start import ROOT
        env=os.environ.copy();env['PYTHONIOENCODING']='ascii'
        p=subprocess.run([sys.executable,str(ROOT/'scripts/start.py'),'--help'],env=env,capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(p.returncode,0,p.stderr);self.assertIn('0.03表示0.03%',p.stdout)
    def test_changed_saved_snapshot_requires_explicit_new_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);csv=root/'holding.csv'
            header='code,name,market_value,currency,asset_class\n'
            csv.write_text(header+'a,现金,10,CNY,cash\n','utf-8')
            execute('snapshot',root/'old',input_path=csv,as_of='2026-10-09')
            changed=root/'old/input.csv';changed.write_text(header+'a,现金,20,CNY,cash\n','utf-8')
            blocked=execute('snapshot',root/'blocked',continue_from=root/'old')
            self.assertEqual(blocked['status'],'blocked');self.assertIn('已保存输入发生变化',blocked['message'])
            updated=execute('snapshot',root/'updated',continue_from=root/'old',input_path=changed)
            self.assertEqual(updated['status'],'partial');self.assertEqual(updated['inputReuseVerification'],'explicit-new-input')
            self.assertEqual(json.loads((root/'updated/result.json').read_text('utf-8'))['totalMarketValue'],'20')
    def test_news_can_continue_but_is_not_complete_event_evaluation(self):
        from start import ROOT
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            first=execute('news',root/'old',input_path=ROOT/'references/examples/news-example.json')
            second=execute('news',root/'new',continue_from=root/'old')
            self.assertEqual(first['status'],'partial');self.assertEqual(second['status'],'partial')
            self.assertEqual((root/'old'/'input.json').read_bytes(),(root/'new'/'input.json').read_bytes())
            self.assertIn('不是预计损失',second['headline'])
    def test_snapshot_continuation_preserves_amounts_and_date(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'mine.csv'
            source.write_text('code,name,market_value,currency,asset_class\nA,资产A,100,CNY,fund\n','utf-8')
            execute('snapshot',root/'old',input_path=source,as_of='2026-09-30')
            result=execute('snapshot',root/'new',continue_from=root/'old')
            self.assertEqual(result['status'],'partial')
            self.assertEqual((root/'new'/'input.csv').read_bytes(),source.read_bytes())
            self.assertEqual(json.loads((root/'new'/'result.json').read_text('utf-8'))['asOf'],'2026-09-30')
            self.assertEqual(execute('funds',root/'wrong',continue_from=root/'old')['status'],'blocked')
    def test_continue_fund_request_reuses_parameters_but_not_online_permission(self):
        def collect(codes,start,as_of,group,out,**kwargs):
            self.assertEqual(codes,['000001','000002'])
            self.assertEqual(start,'2025-01-01');self.assertEqual(as_of,'2026-09-30')
            self.assertFalse(kwargs['allow_online']);out.mkdir()
            return {'status':'partial','message':'历史比较','nextSteps':[]}
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);previous=root/'old';previous.mkdir()
            (previous/'research-request.json').write_text(json.dumps({'command':'funds','codes':['000001','000002'],'start':'2025-01-01','asOf':'2026-09-30'}),'utf-8')
            with patch('quick_research.fund_codes',side_effect=collect):
                result=execute('funds',root/'new',continue_from=previous)
            self.assertEqual(result['status'],'partial')
            self.assertTrue((root/'new'/'research-request.json').exists())
    def test_continuation_links_to_selected_source_without_changing_it(self):
        from urllib.parse import unquote
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'mine.csv';source.write_text('code,name,market_value,currency,asset_class\nA,资产A,100,CNY,fund\n','utf-8')
            execute('snapshot',root/'old',input_path=source,as_of='2026-09-30')
            original=(root/'old/打开这里.html').read_bytes()
            result=execute('snapshot',root/'nested/new',continue_from=root/'old')
            relative=result['previousStudy']['entry']
            self.assertEqual((root/'nested/new'/relative).resolve(),(root/'old/打开这里.html').resolve())
            self.assertIn('返回上次报告',(root/'nested/new/打开这里.md').read_text('utf-8'))
            self.assertEqual(original,(root/'old/打开这里.html').read_bytes())

    def test_fund_group_can_be_omitted_without_claiming_same_category(self):
        def collect(codes,start,as_of,group,out,**kwargs):
            self.assertEqual(group,'用户指定比较池（未核验同类）')
            out.mkdir()
            return {'status':'partial','message':'历史比较','nextSteps':[]}
        with tempfile.TemporaryDirectory() as folder, patch('quick_research.fund_codes',side_effect=collect):
            result=execute('funds',Path(folder)/'result',online=True,codes=['000001','000002'],start='2025-01-01',as_of='2026-09-30')
            self.assertEqual(result['status'],'partial')

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
