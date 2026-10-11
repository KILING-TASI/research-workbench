import unittest
from copy import deepcopy
from claim_evidence_review import review


def sample():
    row = dict(id='announcement', status='available', reason='教学原文', source='https://example.org/notice', locator='第1页', sourceVersion='1',
               publishedDate='2026-10-01', acquiredAt='2026-10-02T12:00:00+08:00', rawSourceSha256='a'*64, dataDate='2026-10-01',
               valueType='disclosed', subjectId='demo', referencePeriod='2026-Q3', excerpt='教学声明，仅完成部分项目。')
    return dict(inputSchema='claim-evidence/1', evidence=dict(inputSchema='evidence-status/1', sampleType='teaching', question='项目是否全部完成？',
                asOfDate='2026-10-11', asOf='2026-10-11T23:59:59+08:00', maxAgeDays=30, records=[row]),
                claims=[dict(id='completion', text='项目已全部完成', subjectId='demo', referencePeriod='2026-Q3',
                             links=[dict(evidenceId='announcement', relation='partial', rationale='摘录仅表示部分完成')])])


class Tests(unittest.TestCase):
    def test_partial_not_full_support(self):
        result=review(sample()); self.assertEqual(result['records'][0]['status'], 'partial-only'); self.assertFalse(result['records'][0]['originalVerified'])
    def test_conflicting_same_file_not_vote(self):
        spec=sample(); spec['claims'][0]['links'][0]['relation']='supports'
        spec['evidence']['records'].append(dict(spec['evidence']['records'][0], id='repost'))
        spec['claims'][0]['links'].append(dict(evidenceId='repost', relation='contradicts', rationale='人工声明存在反例'))
        row=review(spec)['records'][0]; self.assertEqual(row['status'], 'conflicting'); self.assertEqual(len(row['sourceArtifactGroups']), 1)
    def test_subject_period_proxy_and_future_excluded(self):
        for field,value in [('subjectId','other'),('referencePeriod','2025'),('valueType','proxy'),('acquiredAt','2026-10-12T12:00:00+08:00')]:
            with self.subTest(field=field):
                spec=sample(); spec['claims'][0]['links'][0]['relation']='supports'; spec['evidence']['records'][0][field]=value
                row=review(spec)['records'][0]; self.assertEqual(row['status'], 'insufficient'); self.assertEqual(len(row['excluded']),1)
    def test_failed_is_unknown_not_counterevidence(self):
        spec=sample(); spec['evidence']['records'][0]['status']='failed'; self.assertEqual(review(spec)['records'][0]['status'],'insufficient')
    def test_unknown_and_duplicate_references_fail(self):
        spec=sample(); spec['claims'][0]['links'][0]['evidenceId']='absent'
        with self.assertRaises(ValueError): review(spec)
        spec=sample(); spec['claims'][0]['links']*=2
        with self.assertRaises(ValueError): review(spec)
    def test_empty_and_wrong_record_shape(self):
        spec=sample(); spec['evidence']['records']=[None]
        with self.assertRaises(ValueError): review(spec)
        spec=sample(); spec['evidence']['records'][0]['id']=' '
        with self.assertRaises(ValueError): review(spec)


if __name__=='__main__': unittest.main()
