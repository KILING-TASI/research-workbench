import json
import tempfile
import unittest
from pathlib import Path
from research_results import publish


class Results(unittest.TestCase):
    def test_changed_registered_input_hides_old_headline_but_remains_findable(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=root/'old';old.mkdir();raw=b'old csv'
            (old/'input.csv').write_bytes(raw)
            (old/'research-request.json').write_text(json.dumps({'command':'snapshot','names':['声明项目'],'savedInputSha256':hashlib.sha256(raw).hexdigest()}),'utf-8')
            (old/'start-result.json').write_text(json.dumps({'status':'partial','message':'结构快照','headline':'旧金额10元'}),'utf-8')
            (old/'打开这里.html').write_text('入口','utf-8')
            self.assertEqual(publish(root,root/'original.md','声明项目')[0]['headline'],'旧金额10元')
            (old/'input.csv').write_bytes(b'new csv')
            row=publish(root,root/'changed.md','声明项目')[0]
            self.assertEqual(row['status'],'记录需要复查');self.assertIsNone(row['headline']);self.assertIsNotNone(row['entry'])
    def test_bjx_declared_dates_search_not_investment_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=root/'scenario';old.mkdir()
            (old/'research-request.json').write_text(json.dumps({'command':'bjx','codes':['920022'],'scenarioDates':{'applyDate':'2026-10-12','refundDate':'2026-10-14','saleSettlementDate':'2026-10-20'}}),'utf-8')
            (old/'start-result.json').write_text(json.dumps({'status':'partial','message':'教学情景'}),'utf-8')
            (old/'打开这里.html').write_text('入口','utf-8')
            rows=publish(root,root/'found.md','920022 2026-10-12')
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['periodKind'],'scenario-dates')
            text=(root/'found.md').read_text('utf-8');self.assertIn('原情景资金日期',text);self.assertNotIn('研究区间：',text)
            self.assertIn('不表示今天可申购',text)
            request=json.loads((old/'research-request.json').read_text('utf-8'));request['scenarioDates']['applyDate']='bad-date'
            (old/'research-request.json').write_text(json.dumps(request),'utf-8')
            rows=publish(root,root/'bad-date.md','920022');self.assertEqual(len(rows),1);self.assertIsNone(rows[0]['period'])
    def test_legacy_snapshot_names_require_matching_saved_csv(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);old=root/'old';old.mkdir()
            raw=b'code,name\n1,fund\n';(old/'input.csv').write_bytes(raw)
            (old/'result.json').write_text(json.dumps({'inputSha256':hashlib.sha256(raw).hexdigest(),'holdings':[{'code':'user-1','name':'基金项目乙'}]}),'utf-8')
            (old/'research-request.json').write_text(json.dumps({'command':'snapshot','asOf':'2026-09-30'}),'utf-8')
            (old/'start-result.json').write_text(json.dumps({'status':'partial','message':'快照已生成'}),'utf-8')
            (old/'打开这里.html').write_text('入口','utf-8')
            rows=publish(root,root/'found.md','基金项目乙')
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['subjectIdentity'],'user-declared-not-verified')
            self.assertIn('未核验身份',(root/'found.md').read_text('utf-8'))
            (old/'input.csv').write_bytes(raw+b'changed')
            self.assertEqual(publish(root,root/'changed.md','基金项目乙'),[])
    def test_old_code_comparison_can_be_found_by_second_fund_name(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);report=root/'old';(report/'comparison').mkdir(parents=True)
            (report/'start-result.json').write_text(json.dumps({'status':'partial','message':'共同区间比较','headline':'第一只基金收益较少'}),'utf-8')
            (report/'打开这里.html').write_text('入口','utf-8')
            (report/'research-request.json').write_text(json.dumps({'command':'funds','codes':['510050','510500'],'names':None}),'utf-8')
            (report/'comparison/input.json').write_text(json.dumps({'rows':[{'code':'510500','name':'中证500ETF南方'},{'code':'other','name':'无关基金'}]}),'utf-8')
            rows=publish(root,root/'found.md','中证500ETF南方');self.assertEqual(len(rows),1)
            self.assertEqual(publish(root,root/'unrelated.md','无关基金'),[])
            (report/'research-request.json').write_text(json.dumps({'command':'funds','codes':None,'names':['中证500基金']}),'utf-8')
            self.assertEqual(len(publish(root,root/'old-name.md','中证500ETF南方')),1)
    def test_opening_prose_is_excerpt_not_invented_judgement(self):
        from research_results import report_summary
        self.assertEqual(report_summary('# 财报\n\n现金收入与利润不同。')[0],'现金收入与利润不同。')
        self.assertEqual(report_summary('# 表\n\n|金额|\n|---|\n|100|'),(None,None))
        self.assertEqual(report_summary('# 示例\n\n```text\n> 这是代码不是结论\n\n100\n```\n\n实际报告说明。')[0],'实际报告说明。')
    def test_independent_hint_does_not_leak_to_next_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('a-independent','b-ordinary'):
                p=root/name;p.mkdir();(p/'正文.html').write_text('报告','utf-8');(p/'正文.md').write_text('# 报告\n\n原文开头。','utf-8')
                (p/'report-manifest.json').write_text(json.dumps({'files':{'正文.html':None,'正文.md':None},'savedAt':'2026-10-08T20:00:00+00:00'}),'utf-8')
            (root/'a-independent/research-request.json').write_text(json.dumps({'command':'independent','engine':'financial'}),'utf-8')
            rows=publish(root,root/'found.md');mapped={r['name']:r for r in rows}
            self.assertEqual(mapped['a-independent']['independentEngine'],'financial');self.assertIsNone(mapped['b-ordinary']['independentEngine'])
            text=(root/'found.md').read_text('utf-8');self.assertIn('正文开头摘录：原文开头。',text);self.assertIn('2026-10-09 04:00:00 北京时间',text)
    def test_explicit_primary_report_overrides_alphabetical_attachment(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);report=root/'reports';report.mkdir()
            for name,text in [('a-note.html','附件'),('z-main.html','正文'),('z-main.md','> 主报告判断')]:
                (report/name).write_text(text,'utf-8')
            record=report/'report-manifest.json'
            record.write_text(json.dumps({'files':{name:None for name in ('a-note.html','z-main.html','z-main.md')},'primaryReport':'z-main.html'}),'utf-8')
            rows=publish(root,root/'found.md');self.assertEqual(rows[0]['entry'],(report/'z-main.html').resolve());self.assertEqual(rows[0]['headline'],'主报告判断')
            record.write_text(json.dumps({'files':{'z-main.html':None},'primaryReport':'../secret.html'}),'utf-8')
            rows=publish(root,root/'invalid.md');self.assertIsNone(rows[0]['entry']);self.assertEqual(rows[0]['status'],'记录不可读取')
    def test_manifest_headline_matches_primary_html_not_adjustment_note(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);report=root/'anonymous';report.mkdir()
            for name,body in [('年度情景.html','报告'),('年度情景.md','# 年度情景\n\n> 中性情景收益需要复核'),('资金调整说明.md','# 资金调整\n仅改本金')]:
                (report/name).write_text(body,'utf-8')
            (report/'report-manifest.json').write_text(json.dumps({'files':{name:None for name in ('年度情景.html','资金调整说明.md','年度情景.md')},'savedAt':'2025-02-01T00:00:00+00:00','followup':'bjx-annual'}),'utf-8')
            rows=publish(root,root/'found.md','中性情景')
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['headline'],'中性情景收益需要复核')
            self.assertIsNotNone(rows[0]['savedAt']);self.assertIn('沿用这份年度情景',(root/'found.md').read_text('utf-8'))
    def test_recent_sort_uses_saved_time_not_name_or_modified_time(self):
        import os
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name,stamp in [('a-old','2025-01-01T00:00:00+00:00'),('z-recent','2025-02-01T00:00:00+00:00'),('0-undated',None)]:
                directory=root/name;directory.mkdir()
                record=directory/'start-result.json'
                record.write_text(json.dumps({'status':'partial','message':'基金比较','savedAt':stamp}),'utf-8')
                os.utime(record,(1800000000,1800000000))
            rows=publish(root,root/'recent.md','基金',limit=1)
            self.assertEqual([r['name'] for r in rows],['z-recent'])
            text=(root/'recent.md').read_text('utf-8')
            self.assertIn('找到3条',text);self.assertIn('留存时间不代表数据已更新',text)
            with self.assertRaises(ValueError):publish(root,root/'bad-limit.md',limit=0)

    def test_saved_names_are_searchable_without_headline(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'anonymous';old.mkdir()
            (old/'start-result.json').write_text(json.dumps({'status':'partial','message':'结果已生成'}),'utf-8')
            (old/'research-request.json').write_text(json.dumps({'command':'funds','names':['测试基金A','测试基金C']}),'utf-8')
            rows=publish(root,root/'by-name.md','测试基金C')
            self.assertEqual(len(rows),1)
            text=(root/'by-name.md').read_text('utf-8')
            self.assertIn('已完成部分研究',text);self.assertIn('测试基金A、测试基金C',text)
    def test_manifest_reports_are_found_but_external_paths_are_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);report=root/'legacy';report.mkdir()
            (report/'report.md').write_text('# 研究\n\n> 现金兑现尚需观察\n','utf-8')
            (report/'report.html').write_text('report','utf-8')
            (report/'report-manifest.json').write_text(json.dumps({'files':{'report.md':'x','report.html':'x','../secret.html':'x'}}),'utf-8')
            rows=publish(root,root/'found.md','现金兑现')
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['entry'],(report/'report.html').resolve())
            self.assertIn('未重新验收',rows[0]['status'])
    def test_find_by_conclusion_and_display_saved_period(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);old=root/'opaque';old.mkdir()
            (old/'start-result.json').write_text(json.dumps({'status':'partial','message':'比较完成','headline':'消费基金历史回撤仍需关注'}),'utf-8')
            (old/'research-request.json').write_text(json.dumps({'start':'2025-01-02','asOf':'2026-09-30'}),'utf-8')
            rows=publish(root,root/'find.md','消费基金')
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['period'],'2025-01-02至2026-09-30')
            self.assertEqual(publish(root,root/'none.md','黄金'),[])
    def test_results_and_invalid_records_are_visible_without_modifying_them(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);good=root/'基金比较';good.mkdir()
            record=good/'start-result.json';raw=json.dumps({'status':'partial','message':'历史比较已完成'})
            record.write_text(raw,'utf-8');(good/'打开这里.html').write_text('report','utf-8')
            bad=root/'失败';bad.mkdir();(bad/'start-result.json').write_text('{','utf-8')
            rows=publish(root,root/'索引.md')
            self.assertEqual(len(rows),2);self.assertEqual(record.read_text('utf-8'),raw)
            text=(root/'索引.md').read_text('utf-8')
            self.assertIn('打开报告与下一步',text);self.assertIn('记录不可读取',text)
            with self.assertRaises(ValueError):publish(root,root/'索引.md')

    def test_no_recursive_discovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);nested=root/'private'/'nested';nested.mkdir(parents=True)
            (nested/'start-result.json').write_text('{}','utf-8')
            self.assertEqual(publish(root,root/'index.md'),[])
