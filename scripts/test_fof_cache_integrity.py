import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from fof_reports import run,load_json
class Tests(unittest.TestCase):
 def parent(self):return dict(reportDate='2025-12-31',holdings=[dict(code='000001',weight=.5)])
 def test_parent_invalid_rejected_before_workspace_write(self):
  for rows in [[dict(code='000001'),dict(code='000001')],[dict(code='000001',weight=float('nan'))]]:
   with tempfile.TemporaryDirectory() as d:
    out=Path(d)/'new'
    with self.assertRaises(ValueError):run(dict(reportDate='2025-12-31',holdings=rows),out,'2026-10-05')
    self.assertFalse(out.exists())
 def test_cache_traversal_is_pending_not_read(self):
  with tempfile.TemporaryDirectory() as d:
   folder=Path(d)/'fof-report-library/000001/2025-12-31';folder.mkdir(parents=True)
   (folder/'source.json').write_text(json.dumps(dict(filename='../../outside.pdf')),encoding='utf-8')
   with patch('fof_reports.inspect_and_parse') as parser:
    r=run(self.parent(),d,'2026-10-05')
    parser.assert_not_called()
   self.assertEqual(r['counts']['pending'],1);self.assertIn('文件名无效',r['pendingReports'][0]['reason']);self.assertEqual(r['nodes'],{})
 def test_noncanonical_parent_dates_rejected_before_write(self):
  for field in ['reportDate','asOf']:
   for value in ['20251231','2025-W52-3','2026-02-30',True]:
    with self.subTest(field=field,value=value),tempfile.TemporaryDirectory() as d:
     parent=self.parent();asof='2026-10-05'
     if field=='reportDate':parent['reportDate']=value
     else:asof=value
     workspace=Path(d)/'new'
     with self.assertRaises(ValueError):run(parent,workspace,asof)
     self.assertFalse(workspace.exists())
 def test_json_duplicate_rejected(self):
  with self.assertRaises(ValueError):load_json('{"code":"000001","code":"000002"}')
 def test_invalid_published_day_never_archived_or_parsed(self):
  for published in ['2026-02-30','2026-2-01','20260331',True]:
   with self.subTest(published=published),tempfile.TemporaryDirectory() as d:
    pdf=Path(d)/'upload.pdf';pdf.write_bytes(b'%PDF-test')
    upload={'code':'000001','reportDate':'2025-12-31','path':str(pdf),'title':'annual report','publishedAt':published,'sourceUrl':'https://example.com/report.pdf'}
    with patch('fof_reports.inspect_and_parse') as parser:
     result=run(self.parent(),d,'2026-10-05',uploads=[upload]);parser.assert_not_called()
    self.assertEqual(result['nodes'],{});self.assertEqual(result['counts']['pending'],1)
    self.assertIn('日期',result['pendingReports'][0]['reason'])
    self.assertFalse((Path(d)/'fof-report-library/000001/2025-12-31/source.json').exists())
 def test_unresolved_balance_keeps_review_artifact_without_accepting_node(self):
  with tempfile.TemporaryDirectory() as d:
   pdf=Path(d)/'upload.pdf';pdf.write_bytes(b'%PDF-test')
   parsed={'holdings':[{'code':'600000','weight':.4}], 'accountingReconciliation':{'status':'unresolved','differenceCNY':'12.34'}}
   upload={'code':'000001','reportDate':'2025-12-31','path':str(pdf),'title':'annual report','publishedAt':'2026-03-31','sourceUrl':'https://example.com/report.pdf'}
   with patch('fof_reports.inspect_and_parse',return_value=parsed),patch('pdf_structure_review.review',return_value={'reviewRequired':False}):
    result=run(self.parent(),d,'2026-10-05',uploads=[upload])
   self.assertEqual(result['nodes'],{});self.assertEqual(result['counts']['pending'],1)
   row=result['pendingReports'][0]
   self.assertEqual(row['scopeStatus'],'accounting-reconciliation-required')
   self.assertEqual(row['accountingReconciliation']['differenceCNY'],'12.34')
   self.assertEqual(row['holdingsCount'],1)
   self.assertEqual(json.loads(Path(row['parsedPath']).read_text(encoding='utf-8'))['accountingReconciliation'],row['accountingReconciliation'])
