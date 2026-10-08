import unittest,tempfile,json
from pathlib import Path
from sec_facts_batch import run,markdown
class Tests(unittest.TestCase):
 def test_ambiguous_archive_is_gap_not_silent_overwrite(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'facts.json';p.write_text('{"cik":320193,"entityName":"A","entityName":"B","facts":{}}')
   r=run(dict(asOf='2026-10-03',archives=[dict(cik='0000320193',path=str(p))]));self.assertEqual(len(r['gaps']),1);self.assertFalse(r['results']);self.assertIn('重复字段',r['gaps'][0]['reason'])
 def test_relative_archive_paths_use_input_directory(self):
  from sec_facts_batch import read_input
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'facts.json').write_text(json.dumps(dict(cik=320193,entityName='Apple',facts={})));p=root/'input.json';p.write_text(json.dumps(dict(asOf='2026-10-03',archives=[dict(cik='0000320193',path='facts.json')])));self.assertEqual(len(run(read_input(p))['results']),1)
 def test_missing_company_retained(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'data.json';p.write_text(json.dumps(dict(cik=320193,entityName='Apple',facts={})))
   r=run(dict(asOf='2026-10-03',archives=[dict(cik='0000320193',path=str(p)),dict(cik='0000789019',path=str(Path(t)/'missing.json'))]));self.assertEqual(r['candidateCount'],2);self.assertEqual(len(r['results']),1);self.assertEqual(len(r['gaps']),1);self.assertEqual(len(r['results'][0]['gaps']),8)
 def test_report_discloses_field_gaps_and_provenance(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'data.json';p.write_text(json.dumps(dict(cik=320193,entityName='Apple',facts={})))
   r=run(dict(asOf='2026-10-03',periodStart='2025-04-01',periodEnd='2025-06-30',archives=[dict(cik='0000320193',path=str(p))]))
   text=markdown(r)
   self.assertIn(r['results'][0]['inputSha256'],text)
   self.assertIn('来源获取过程未自动验证',text)
   self.assertIn('StockholdersEquity',text)
   self.assertIn('2025-04-01至2025-06-30',text)
   self.assertIn('跨边界累计值未转换成单季',text)
 def test_duplicate_rejected(self):
  row=dict(cik='0000320193',path='missing')
  with self.assertRaises(ValueError):run(dict(asOf='2026-10-03',archives=[row,row]))
if __name__=='__main__':unittest.main()
