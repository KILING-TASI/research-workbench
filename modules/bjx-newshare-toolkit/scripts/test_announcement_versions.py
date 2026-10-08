import unittest
from announcement_versions import version_review
from build_bjx_workbench import payload

class VersionTests(unittest.TestCase):
    def test_correction_not_automatic_supersession(self):
        r = version_review([{'title':'发行公告', 'date':'2026-09-01','url':'a'},
                            {'title':'发行公告（更正后）','date':'2026-09-02','url':'b'}])
        self.assertEqual(r['status'], 'needs-body-review')
        self.assertFalse(r['groups'][0]['supersessionConfirmed'])
        self.assertEqual(len(r['groups'][0]['documents']), 2)

    def test_unknown_family_retained(self):
        self.assertEqual(version_review([{'title':'关于更正信息的公告'}])['groups'][0]['family'], '未明确关联文件')
        self.assertEqual(version_review([])['status'], 'no-change-title-detected')

    def test_builder_recomputes_from_current_links(self):
        s={'source':'test','fetchedAt':'2026-10-03','records':[{'code':'920001','name':'测试','announcements':[{'title':'发行结果更正公告','url':'a'}]}]}
        r=payload(s,{}, {})['records'][0]
        self.assertEqual(r['announcementVersionReview']['status'],'needs-body-review')

if __name__ == '__main__': unittest.main()
