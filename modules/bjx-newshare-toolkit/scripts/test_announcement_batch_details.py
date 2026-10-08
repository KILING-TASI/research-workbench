import datetime as dt
import unittest
from unittest.mock import patch
from announcements import enrich,query


class BatchDetails(unittest.TestCase):
    def rows(self):
        return [{'code':str(i),'name':'teaching','applyDate':dt.date.today().isoformat()} for i in range(3)]
    def test_bounded_batch_lists_unattempted(self):
        snapshot={'fetchedAt':'test','records':self.rows()}
        with patch('announcements.query',return_value=[]),patch('announcements.time.sleep'):enrich(snapshot,{'records':[]},1)
        self.assertEqual(snapshot['announcementRefresh']['pending'],2)
        self.assertEqual([x['status'] for x in snapshot['announcementRefreshDetails']],['no-match-this-run','not-attempted','not-attempted'])
    def test_empty_search_with_old_links_not_new_match(self):
        rows=self.rows();old={'records':[{**rows[0],'announcements':[{'url':'https://www.bse.cn/old','title':'发行公告','date':'2026-01-01','source':'old'}]}]}
        snapshot={'fetchedAt':'test','records':rows}
        with patch('announcements.query',return_value=[]),patch('announcements.time.sleep'):enrich(snapshot,old,3)
        self.assertEqual(snapshot['announcementRefresh']['matchedThisRun'],0);self.assertEqual(snapshot['announcementRefresh']['covered'],1)
        self.assertEqual(snapshot['records'][0]['announcementStatus'],'matched')
        self.assertEqual(next(x for x in snapshot['announcementRefreshDetails'] if x['code']=='0')['status'],'no-match-this-run')
    def test_access_stop_lists_rest_and_preserves_links(self):
        rows=self.rows();old={'records':[{**r,'announcements':[]} for r in rows]};snapshot={'fetchedAt':'test','records':rows}
        with patch('announcements.query',side_effect=RuntimeError('HTTP 429')) as request,patch('announcements.time.sleep'):enrich(snapshot,old,3)
        self.assertEqual(request.call_count,1);self.assertTrue(snapshot['announcementRefresh']['accessLimitStopped'])
        self.assertEqual(snapshot['announcementRefreshDetails'][1]['reason'],'access-limit-stop')
        self.assertEqual(snapshot['announcementRefreshDetails'][0]['status'],'failed-cache-retained')
    def test_invalid_limit_rejected_before_request(self):
        with patch('announcements.query') as request:
            for limit in [-1,51,True]:
                with self.assertRaises(ValueError):enrich({'records':[]},{'records':[]},limit)
            request.assert_not_called()
    def test_malformed_empty_response_preserves_cache_as_failure(self):
        stock={'code':'920022','name':'teaching','applyDate':dt.date.today().isoformat()}
        cached={'url':'https://www.bse.cn/old','title':'发行公告','date':'2026-01-01','source':'old'}
        for response in [{'announcements':''},{'announcements':{}},{'announcements':[None]}, {'announcements':[],'hasMore':'false'}]:
            with self.subTest(response=response):
                snapshot={'fetchedAt':'test','records':[dict(stock)]}
                prior={'records':[{**stock,'announcements':[dict(cached)]}]}
                with patch('announcements.issuer',return_value={'code':'920022','orgId':'test'}),patch('announcements.request_json',return_value=response),patch('announcements.time.sleep'):
                    enrich(snapshot,prior,1)
                self.assertEqual(snapshot['records'][0]['announcementStatus'],'failed')
                self.assertEqual(snapshot['records'][0]['announcements'],[cached])
                self.assertEqual(snapshot['announcementRefresh']['noMatchThisRun'],0)
    def test_valid_empty_and_null_list_stay_distinct_from_failure(self):
        stock={'code':'920022','name':'teaching','applyDate':dt.date.today().isoformat()}
        for items in [[],None]:
            with self.subTest(items=items),patch('announcements.request_json',return_value={'announcements':items,'hasMore':False}):
                self.assertEqual(query(stock,_resolved={'code':'920022','orgId':'test'}),[])
