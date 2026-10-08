import concurrent.futures
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from build_package import build
from package_audit import audit
from public_download import validate_url, PublicRedirect, public_connection,download
from research_tasks import append_note, import_records, read, task_path
from research_topics import ROOT
import company_report_batch as reports
import research_pipeline
from original_layouts import verify_v2
from environment_check import inspect


class RemediationTests(unittest.TestCase):
    def test_download_parameters_rejected_before_dns_or_request(self):
        for kwargs in [dict(limit=-1),dict(limit=True),dict(timeout=0),dict(timeout=float('nan')),dict(timeout=True)]:
            with self.subTest(kwargs=kwargs),patch('public_download.socket.getaddrinfo') as dns,patch('public_download.build_opener') as opener:
                with self.assertRaises(ValueError):download('https://example.org/a',**kwargs)
                dns.assert_not_called();opener.assert_not_called()
        for url in [None,'https://@example.org/a','https://example.org/\nfile','https://example.org/a b']:
            with self.subTest(url=url),patch('public_download.socket.getaddrinfo') as dns:
                with self.assertRaises(ValueError):validate_url(url)
                dns.assert_not_called()
    def test_removed_ocr_rejected_before_pdf_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf=Path(directory)/'scan.pdf';pdf.write_bytes(b'%PDF-example')
            request={'documentPath':str(pdf),'sourceUrl':'https://example.org/scan.pdf',
                     'trustedPublisherHosts':['example.org'],'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
                     'title':'Report','issuer':'Issuer','publishedAt':'2026-01-01','asOf':'2026-10-05',
                     'publicationExcerpt':'2026-01-01','fields':[{'id':'one'}],
                     'ocr':{'enabled':True,'executable':'untrusted'}}
            with patch('original_layouts.pdfplumber.open') as parser:
                with self.assertRaisesRegex(ValueError,'已移除'): verify_v2(request)
                parser.assert_not_called()

    def test_dependency_coverage_and_old_node(self):
        with patch('environment_check.importlib.util.find_spec',return_value=None),patch('environment_check.shutil.which',return_value='node'),patch('environment_check.subprocess.run',return_value=subprocess.CompletedProcess([],0,'v18.0.0','')):
            rows={r['component']:r for r in inspect()['dependencies']}
            for component in ['pypdf','pypdfium2','docx','pandas']: self.assertIn(component,rows)
            self.assertFalse(rows['node']['available'])

    def test_url_boundary(self):
        for url in ['http://example.org/a', 'https://user:secret@example.org/a', 'file:///a']:
            with self.assertRaises(ValueError): validate_url(url)
        for ip in ['127.0.0.1', '10.0.0.1', '169.254.169.254', '::1']:
            with patch('public_download.socket.getaddrinfo', return_value=[(socket.AF_INET, 1, 6, '', (ip,443))]):
                with self.assertRaises(ValueError): validate_url('https://example.org/a')

    def test_redirect_rejected_before_follow(self):
        with self.assertRaises(ValueError):
            PublicRedirect().redirect_request(Request('https://example.org'), None, 302, '', {}, 'http://example.org/a')

    def test_public_url(self):
        with patch('public_download.socket.getaddrinfo', return_value=[(2,1,6,'',('8.8.8.8',443))]):
            self.assertEqual(validate_url('https://example.org/a'), 'https://example.org/a')

    def test_connection_uses_checked_ip(self):
        with patch('public_download.socket.getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))]) as lookup,patch('public_download.socket.socket') as make:
            public_connection(('example.org',443),30)
            lookup.assert_called_once()
            make.return_value.connect.assert_called_once_with(('8.8.8.8',443))
        with patch('public_download.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch('public_download.socket.socket') as make:
            with self.assertRaises(ValueError): public_connection(('example.org',443))
            make.assert_not_called()

    def test_429_not_retried(self):
        with patch.object(reports, 'urlopen', side_effect=HTTPError('https://example.org',429,'limited',{},None)) as fetch:
            with self.assertRaises(HTTPError): reports.request('https://example.org')
            self.assertEqual(fetch.call_count, 1)

    def test_bounded_decompression(self):
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, limit): return gzip.compress(b'test')
        with patch.object(reports, 'urlopen', return_value=Response()):
            self.assertEqual(reports.request('https://example.org'), b'test')
        class Bomb:
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self,limit): return b'x'*(limit)
        with patch.object(reports,'urlopen',return_value=Response()),patch.object(reports.gzip,'GzipFile',return_value=Bomb()):
            with self.assertRaisesRegex(ValueError,'解压'): reports.request('https://example.org')

    def test_concurrent_notes_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)
            import_records(folder, {'type':'research-journal','version':1,'rows':[{'id':'one','title':'example','snapshot':{}}]})
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                list(executor.map(lambda n: append_note(folder,'one',str(n)), range(20)))
            self.assertEqual(len(read(task_path(folder,'one'))['notes']),20)
            self.assertFalse((folder/'.research.lock').exists())

    def test_partial_project_falls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory)/'outputs/fund-market/assets';folder.mkdir(parents=True)
            (folder/'data.json').write_text('{"rows":[]}', 'utf-8')
            with patch('portable_collect.collect', return_value={'fallback':True}) as collect:
                self.assertEqual(research_pipeline.collect(directory,'fund',['000001'],'2026-10-05'),{'fallback':True})
                collect.assert_called_once()

    def test_local_server_mutation_gate(self):
        script=ROOT/'modules/bjx-newshare-toolkit/scripts/toolkit.py'
        sys.path.insert(0,str(script.parent))
        try:
            spec=importlib.util.spec_from_file_location('remediation_toolkit',script)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            server=module.ThreadingHTTPServer(('127.0.0.1',0),module.Handler)
            server.mutation_token='test-token';worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            endpoint='http://127.0.0.1:'+str(server.server_port)+'/api/refresh'
            try:
                with patch.object(module,'fetch',return_value=[]),patch.object(module,'save',return_value={'ok':True}) as save:
                    with self.assertRaises(HTTPError) as exc: urlopen(endpoint)
                    self.assertEqual(exc.exception.code,405);save.assert_not_called()
                    with self.assertRaises(HTTPError) as exc: urlopen(Request(endpoint,data=b'',method='POST'))
                    self.assertEqual(exc.exception.code,403);save.assert_not_called()
                    self.assertEqual(json.loads(urlopen(Request(endpoint,data=b'',method='POST',headers={'X-Research-Token':'test-token'})).read()),{'ok':True})
            finally: server.shutdown();server.server_close();worker.join()
        finally: sys.path.pop(0)

    def test_real_package_runs_topics_and_includes_licenses(self):
        import zipfile
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);archive=folder/'skill.zip'
            result=build(ROOT,archive);self.assertTrue(result['passed'])
            with zipfile.ZipFile(archive) as package:
                names=package.namelist()
                self.assertTrue(any(n.endswith('a-stock-data-LICENSE.txt') for n in names))
                self.assertFalse(any('__pycache__' in n or '/research/tasks/' in n for n in names))
                package.extractall(folder/'installed')
            installed=folder/'installed/research-workbench'
            for topic in ['bjx','macro','etf']:
                process=subprocess.run([sys.executable,str(installed/'scripts/research_topics.py'),topic,'standalone','--','--help'],cwd=directory,capture_output=True,text=True)
                self.assertEqual(process.returncode,0,process.stderr)
            process=subprocess.run([sys.executable,str(installed/'scripts/research_topics.py'),'macro','standalone','--','--data-dir',str(folder/'cache')],cwd=directory,capture_output=True,text=True)
            self.assertEqual(process.returncode,0,process.stderr)
            self.assertEqual(len(json.loads((folder/'cache/data.json').read_text('utf-8'))['indicators']),37)

    def test_omitted_module_detected(self):
        import zipfile
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);(folder/'SKILL.md').write_text('skill');(folder/'modules/topic').mkdir(parents=True)
            archive=folder/'bad.zip'
            with zipfile.ZipFile(archive,'w') as package: package.writestr('research-workbench/SKILL.md','skill')
            self.assertFalse(audit(archive,folder)['passed'])


if __name__ == '__main__': unittest.main()
