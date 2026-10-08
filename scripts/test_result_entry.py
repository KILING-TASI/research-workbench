import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote
from result_entry import write_entry


class ResultEntryTests(unittest.TestCase):
    def test_bjx_dates_are_declared_scenario_not_today(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'research-request.json').write_text(json.dumps({'command':'bjx','scenarioDates':{'applyDate':'2026-10-12','refundDate':'2026-10-14','saleSettlementDate':'2026-10-20'}}),'utf-8')
            write_entry(root,{'status':'partial','message':'情景已生成','nextSteps':[]})
            body=(root/'打开这里.md').read_text('utf-8');self.assertIn('申购2026-10-12',body);self.assertIn('不表示今天可申购',body)
    def test_previous_report_reference_not_remote_or_executable_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            summary={'status':'blocked','message':'续算尚未完成','nextSteps':[],'previousStudy':{'entry':'javascript:alert(1)/打开这里.html'}}
            write_entry(root,summary);text=(root/'打开这里.md').read_text('utf-8')
            self.assertNotIn('javascript:',text);self.assertNotIn('返回上次报告',text)
    def test_recorded_period_visible_without_inventing_data_freshness(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'research-request.json').write_text(json.dumps({'start':'2025-01-02','asOf':'2025-12-31'}),'utf-8')
            write_entry(root,{'status':'partial','message':'沿用资料','nextSteps':[]})
            body=(root/'打开这里.md').read_text('utf-8');self.assertIn('2025-01-02至2025-12-31',body);self.assertIn('不等于数据更新日期',body)
            (root/'research-request.json').write_text(json.dumps({'start':'<bad>','asOf':'2025-12-31'}),'utf-8')
            write_entry(root,{'status':'partial','message':'沿用资料','nextSteps':[]});self.assertNotIn('<bad>',(root/'打开这里.md').read_text('utf-8'))
    def test_primary_report_is_first_and_does_not_trigger_no_report_message(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'z-main.html').write_text('报告','utf-8')
            (root/'report-manifest.json').write_text(json.dumps({'files':{'z-main.html':None},'primaryReport':'z-main.html'}),'utf-8')
            write_entry(root,{'status':'partial','message':'配置比较完成','nextSteps':['核对限制']})
            body=(root/'打开这里.md').read_text('utf-8');self.assertIn('打开主报告',body);self.assertNotIn('暂未生成',body)
            (root/'a-attachment.html').write_text('说明','utf-8')
            write_entry(root,{'status':'partial','message':'配置比较完成','nextSteps':[]})
            body=(root/'打开这里.md').read_text('utf-8');self.assertLess(body.index('打开主报告'),body.index('a-attachment'))
    def test_links_point_to_published_reports_and_keep_partial_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);report=root/'comparison'/'基金 比较.html';report.parent.mkdir();report.write_text('report','utf-8')
            write_entry(root,{'status':'partial','message':'历史比较完成','nextSteps':['基准尚未取得']})
            text=(root/'打开这里.md').read_text('utf-8')
            self.assertIn('已完成部分研究',text)
            self.assertIn('comparison/%E5%9F%BA%E9%87%91%20%E6%AF%94%E8%BE%83.html',text)
            self.assertTrue((root/unquote('comparison/%E5%9F%BA%E9%87%91%20%E6%AF%94%E8%BE%83.html')).exists())

    def test_failure_does_not_invent_successful_report_link(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'下一步.md').write_text('原因','utf-8')
            write_entry(root,{'status':'blocked','message':'输入缺失','nextSteps':['补充持仓表']})
            text=(root/'打开这里.md').read_text('utf-8')
            self.assertIn('尚未完成',text);self.assertIn('失败原因与处理办法',text)
            self.assertNotIn('基金比较说明',text)

    def test_teaching_mode_is_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            write_entry(root,{'status':'passed','mode':'teaching-demo','message':'教学结果','nextSteps':['换成真实资料']})
            self.assertIn('不是你的真实持仓',(root/'打开这里.html').read_text('utf-8'))


if __name__=='__main__':unittest.main()
