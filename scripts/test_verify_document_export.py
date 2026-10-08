import json,hashlib,tempfile,unittest
from pathlib import Path
from export_financial_docx import export
from verify_document_export import verify,contained
class DocumentIntegrityTests(unittest.TestCase):
 def test_word_text_loss_rejected_even_with_updated_output_hash(self):
  import zipfile
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);source=root/'source.md';source.write_text('# 研究\n核心结论\n\n| 指标 | 值 |\n| --- | --- |\n| 收入 | 100 |',encoding='utf-8');out=root/'out';export(dict(markdownPath=str(source),markdownSha256=hashlib.sha256(source.read_bytes()).hexdigest(),outDir=str(out)))
   manifest=out/'export-result.json';record=json.loads(manifest.read_text(encoding='utf-8'));doc=out/record['outputFile']
   with zipfile.ZipFile(doc) as z:items={name:z.read(name) for name in z.namelist()}
   items['word/document.xml']=items['word/document.xml'].replace('核心结论'.encode(),'已被删改'.encode())
   with zipfile.ZipFile(doc,'w') as z:
    for name,raw in items.items():z.writestr(name,raw)
   record['outputSha256']=hashlib.sha256(doc.read_bytes()).hexdigest();manifest.write_text(json.dumps(record),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'Word可编辑正文'):verify(manifest,source)
 def test_ppt_text_must_match_corresponding_slide(self):
  import zipfile
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);out=root/'report.pptx'
   with zipfile.ZipFile(out,'w') as z:
    z.writestr('[Content_Types].xml','<Types/>')
    for i,text in enumerate(['收入增长','现金下降'],1):z.writestr(f'ppt/slides/slide{i}.xml','<p xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:t>'+text+'</a:t></p>')
   record=dict(format='pptx',outputFile='report.pptx',outputSha256=hashlib.sha256(out.read_bytes()).hexdigest(),slides=2,paragraphs=[['现金下降'],['收入增长']]);p=root/'manifest.json';p.write_text(json.dumps(record))
   with self.assertRaisesRegex(ValueError,'对应页'):verify(p)
   record['paragraphs']=[['收入增长'],['现金下降']];p.write_text(json.dumps(record));self.assertEqual(verify(p)['pages'],2)
   for paragraphs in [[[],[]],[[' '],['现金下降']],[['收入增长'],['']]]:
    record['paragraphs']=paragraphs;p.write_text(json.dumps(record))
    with self.assertRaisesRegex(ValueError,'逐页正文记录无效'):verify(p)
   record['paragraphs']=[['收入增长'],['现金下降']];record['slides']=True;p.write_text(json.dumps(record))
   with self.assertRaisesRegex(ValueError,'正整数'):verify(p)
 def test_changed_body_or_output_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'a.md';source.write_text('# 财务研究\n原值与同比',encoding='utf-8');out=root/'out'
   export(dict(markdownPath=str(source),markdownSha256=hashlib.sha256(source.read_bytes()).hexdigest(),outDir=str(out)))
   verified=verify(out/'export-result.json',source);self.assertEqual(verified['status'],'stored-content-verified');self.assertTrue(verified['markdownSourceHashChecked']);self.assertTrue(verified['bodyChecked']);self.assertFalse(verified['semanticCertification'])
   source.write_text('# 修改后的报告',encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'正文'):verify(out/'export-result.json',source)
   (out/'公司与行业点评.docx').write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'成品'):verify(out/'export-result.json')
 def test_references_cannot_escape_export_directory(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaisesRegex(ValueError,'超出'):contained(Path(d).resolve(),'../source.pdf')
