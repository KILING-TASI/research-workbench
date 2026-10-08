import json,tempfile,unittest,hashlib
from pathlib import Path
from unittest.mock import patch
from collect_index_evidence import collect

class Tests(unittest.TestCase):
 def test_bad_subresponses_do_not_discard_collection(self):
  def response(url,**kwargs):return json.dumps(dict(code=200,data= 'wrong' if 'get-derivative' in url else {'编制方案':[None,{}]} if 'index-details-data' in url else [])).encode()
  with tempfile.TemporaryDirectory() as root,patch('collect_index_evidence.download',side_effect=response):
   result=collect(root,'000300','2026-01-01','2026-09-30')
   self.assertTrue(Path(result['output']).exists());self.assertIn('derivatives',result['errors']);self.assertIn('编制方案:1',result['errors']);self.assertIn('编制方案:2',result['errors'])
 def test_multiple_same_suffix_documents_keep_each_version(self):
  def response(url,**kwargs):
   if 'oss-ch' in url:return url.encode()
   data={'编制方案':[dict(filePath='https://oss-ch.csindex.com.cn/a.pdf'),dict(filePath='https://oss-ch.csindex.com.cn/b.pdf')]} if 'index-details-data' in url else []
   return json.dumps(dict(code=200,data=data)).encode()
  with tempfile.TemporaryDirectory() as root,patch('collect_index_evidence.download',side_effect=response):
   result=collect(root,'000905','2026-01-01','2026-09-30');data=json.loads(Path(result['output']).read_text('utf-8'))
   self.assertEqual(len({r['path'] for r in data['files']}),2)
   for row in data['files']:self.assertEqual(hashlib.sha256(Path(row['path']).read_bytes()).hexdigest(),row['sha256'])

if __name__=='__main__':unittest.main()
