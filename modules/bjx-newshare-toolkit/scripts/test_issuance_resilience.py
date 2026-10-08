import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from public_issuance_data import fetch, normalize
from refresh_public_data import refresh, main


def response(pages=1, rows=None):
    return io.BytesIO(json.dumps({'result':{'pages':pages,'data':rows or [{'SECURITY_CODE':'920001','SECURITY_NAME_ABBR':'teaching'}]}}).encode())


class Resilience(unittest.TestCase):
    def test_transient_failure_retries_same_page(self):
        trace=[]
        with patch('public_issuance_data.urllib.request.urlopen',side_effect=[TimeoutError(),response()]) as request,patch('public_issuance_data.time.sleep') as sleep:
            self.assertEqual(len(fetch(trace)),1)
        self.assertEqual(request.call_count,2);self.assertEqual(trace[0]['status'],'transport-error');self.assertEqual(trace[1]['attempt'],2)
        self.assertEqual(request.call_args_list[0].args[0].full_url,request.call_args_list[1].args[0].full_url)
        sleep.assert_called_once_with(1)

    def test_access_limit_does_not_retry(self):
        for code in [403,429]:
            with self.subTest(code=code),patch('public_issuance_data.urllib.request.urlopen',side_effect=urllib.error.HTTPError('test',code,'limit',{},None)) as request,patch('public_issuance_data.time.sleep') as sleep:
                with self.assertRaises(urllib.error.HTTPError):fetch([])
                self.assertEqual(request.call_count,1);sleep.assert_not_called()

    def test_server_error_bounded(self):
        with patch('public_issuance_data.urllib.request.urlopen',side_effect=urllib.error.HTTPError('test',503,'unavailable',{},None)) as request,patch('public_issuance_data.time.sleep'):
            with self.assertRaises(urllib.error.HTTPError):fetch([])
        self.assertEqual(request.call_count,3)

    def test_pagination_change_rejected(self):
        with patch('public_issuance_data.urllib.request.urlopen',side_effect=[response(2),response(3)]),patch('public_issuance_data.time.sleep'):
            with self.assertRaisesRegex(ValueError,'混合批次'):fetch()

    def test_malformed_response_not_retried(self):
        with patch('public_issuance_data.urllib.request.urlopen',return_value=io.BytesIO(b'not-json')) as request:
            with self.assertRaises(json.JSONDecodeError):fetch()
        self.assertEqual(request.call_count,1)

    def test_invalid_page_count_rejected(self):
        for count in [True,0,31,1.5,None]:
            with self.subTest(count=count),patch('public_issuance_data.urllib.request.urlopen',return_value=response(count)):
                with self.assertRaises(ValueError):fetch()

    def test_missing_code_not_string_none(self):
        for code in [None,'','  ']:
            with self.assertRaises(ValueError):normalize([{'SECURITY_CODE':code,'SECURITY_NAME_ABBR':'teaching'}])

    def test_old_announcement_run_not_current_success(self):
        previous={'records':[],'announcementRefresh':{'queried':20,'checkedAt':'old'}}
        with patch('refresh_public_data.fetch',return_value=[]),patch('refresh_public_data.normalize',return_value={'records':[{'code':'1'}]}):result=refresh(previous)
        self.assertTrue(result['announcementRefresh']['notRequested']);self.assertEqual(result['announcementRefresh']['queried'],0)
        self.assertEqual(result['previousAnnouncementRefresh']['checkedAt'],'old')
        self.assertEqual(result['refreshDetails'][0]['originalNumericStatus'],'not-verified')

    def test_failure_saved_no_partial_snapshot_or_old_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);previous=root/'previous.json';before=b'{"fetchedAt":"2026-10-03","records":[]}'
            previous.write_bytes(before);out=root/'new/snapshot.json'
            with patch('sys.argv',['refresh','--previous',str(previous),'--out',str(out)]),patch('refresh_public_data.fetch',side_effect=TimeoutError('test')):
                with self.assertRaises(SystemExit):main()
            self.assertEqual(previous.read_bytes(),before);self.assertFalse(out.exists())
            failure=json.loads(out.with_name('snapshot-failure.json').read_text('utf-8'))
            self.assertTrue(failure['oldSnapshotRetained']);self.assertFalse(failure['partialSnapshotPublished'])
            with patch('sys.argv',['refresh','--previous',str(previous),'--out',str(out)]),patch('refresh_public_data.fetch') as request:
                with self.assertRaises(ValueError):main()
                request.assert_not_called()
