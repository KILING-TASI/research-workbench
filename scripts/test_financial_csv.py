import unittest,tempfile,json,csv
from pathlib import Path
from export_financial_csv import export
class PortableFinancialCsv(unittest.TestCase):
 def test_bad_units_dates_and_sources_fail_before_output(self):
  import copy
  with tempfile.TemporaryDirectory() as root:
   for index,change in enumerate(['unit','date','sources']):
    data=copy.deepcopy(self.spec())
    if change=='unit':data['rows'][0]['unit']=' '
    elif change=='date':data['rows'][0]['dates'][0]='2026-02-30'
    else:data['sources']=[None]
    p=Path(root)/'input.json';p.write_text(json.dumps(data),'utf-8');out=Path(root)/str(index)
    with self.assertRaises(ValueError):export(p,out)
    self.assertFalse(out.exists())
 def spec(self):return {'rows':[{'code':'000001','key':'revenue','name':'=HYPERLINK("x")','label':'收入','unit':'元','dates':['2026-06-30']*6,'values':[1,None,2,3,4,5],'expected':[1,None,2],'yoy':None,'qoq':.1}],'sources':[]}
 def test_missing_and_formula_text_preserved_safely(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'input.json';p.write_text(json.dumps(self.spec()),'utf-8');out=Path(root)/'csv';export(p,out)
   with (out/'季度结果.csv').open(encoding='utf-8-sig',newline='') as f:row=list(csv.reader(f))[1]
   self.assertEqual(row[0],'000001');self.assertTrue(row[1].startswith("'="));self.assertEqual(row[5],'');self.assertEqual(row[8],'0.1')
 def test_invalid_value_creates_no_output(self):
  with tempfile.TemporaryDirectory() as root:
   d=self.spec();d['rows'][0]['expected'][0]=True;p=Path(root)/'input.json';p.write_text(json.dumps(d),'utf-8');out=Path(root)/'csv'
   with self.assertRaises(ValueError):export(p,out)
   self.assertFalse(out.exists())
 def test_existing_output_not_overwritten(self):
  with tempfile.TemporaryDirectory() as root:
   p=Path(root)/'input.json';p.write_text(json.dumps(self.spec()),'utf-8');out=Path(root)/'csv';export(p,out);before=(out/'manifest.json').read_bytes()
   with self.assertRaises(FileExistsError):export(p,out)
   self.assertEqual(before,(out/'manifest.json').read_bytes())

 def test_real_prepared_growth_objects_and_missing_reason(self):
  with tempfile.TemporaryDirectory() as root:
   d=self.spec();d['rows'][0]['yoy']={'value':None,'reason':'基数缺失'};d['rows'][0]['qoq']={'value':.1,'reason':None}
   p=Path(root)/'input.json';p.write_text(json.dumps(d),'utf-8');out=Path(root)/'csv';export(p,out)
   with (out/'季度结果.csv').open(encoding='utf-8-sig',newline='') as f:row=list(csv.reader(f))[1]
   self.assertEqual(row[7],'');self.assertEqual(row[8],'0.1')
   self.assertIn('基数缺失',(out/'增长口径.csv').read_text(encoding='utf-8-sig'))

 def test_stale_associated_evidence_rejected_without_output(self):
  import hashlib
  with tempfile.TemporaryDirectory() as root:
   source=Path(root)/'source.json';source.write_text('{}','utf-8')
   d=self.spec();d['inputFileHashes']={str(source):hashlib.sha256(source.read_bytes()).hexdigest()}
   p=Path(root)/'input.json';p.write_text(json.dumps(d),'utf-8');source.write_text('{"changed":true}','utf-8');out=Path(root)/'csv'
   with self.assertRaisesRegex(ValueError,'来源已变化'):export(p,out)
   self.assertFalse(out.exists())
 def test_evidence_changed_during_export_does_not_publish(self):
  import hashlib
  from unittest.mock import patch
  from export_financial_csv import verify_associated
  with tempfile.TemporaryDirectory() as root:
   source=Path(root)/'source.json';source.write_text('{}','utf-8')
   d=self.spec();d['inputFileHashes']={str(source):hashlib.sha256(source.read_bytes()).hexdigest()}
   p=Path(root)/'input.json';p.write_text(json.dumps(d),'utf-8');out=Path(root)/'csv'
   calls=[]
   def check(data):
    calls.append(1)
    if len(calls)==2:source.write_text('{"changed":true}','utf-8')
    return verify_associated(data)
   with patch('export_financial_csv.verify_associated',side_effect=check):
    with self.assertRaisesRegex(ValueError,'来源已变化'):export(p,out)
   self.assertFalse(out.exists())
