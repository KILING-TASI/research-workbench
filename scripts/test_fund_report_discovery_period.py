import unittest
from fof_reports import period_title_matches


class ReportPeriodTests(unittest.TestCase):
    def test_supported_year_forms(self):
        for title in ['某基金2026年中期报告','某基金二〇二六年中期报告','某基金２０２６ 年 中期报告']:
            self.assertTrue(period_title_matches(title,'2026','中期报告'))

    def test_substring_year_and_wrong_type_are_not_selected(self):
        for title in ['某基金20260年中期报告','某基金12026年中期报告','2026年提示：某基金2025年中期报告','某基金2026年年度报告']:
            self.assertFalse(period_title_matches(title,'2026','中期报告'))


if __name__=='__main__':
    unittest.main()
