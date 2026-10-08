import hashlib,tempfile,unittest
from pathlib import Path
from export_financial_docx import export,blocks
class Tests(unittest.TestCase):
 def test_title_has_no_inherited_theme_border(self):
  from docx import Document
  from docx.oxml.ns import qn
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'a.md';p.write_text('# 财报核对\n原文与比较期',encoding='utf-8');out=Path(t)/'out'
   export(dict(markdownPath=str(p),markdownSha256=hashlib.sha256(p.read_bytes()).hexdigest(),outDir=str(out)))
   doc=Document(out/'公司与行业点评.docx')
   self.assertEqual(doc.styles['Title'].element.findall('.//'+qn('w:pBdr')),[])
   self.assertEqual(doc.styles['Title'].element.rPr.rFonts.get(qn('w:eastAsia')),'Microsoft YaHei')
 def test_changed_body_rejected_before_output(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'a.md';p.write_text('# 标题\n内容',encoding='utf-8');out=Path(t)/'out'
   with self.assertRaisesRegex(ValueError,'哈希'):export(dict(markdownPath=str(p),markdownSha256='wrong',outDir=str(out)))
   self.assertFalse(out.exists())
 def test_missing_reference_rejected_before_output(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'a.md';p.write_text('# 标题\n[原文](sources/missing.pdf#page=1)',encoding='utf-8');out=Path(t)/'out'
   with self.assertRaisesRegex(ValueError,'缺失'):export(dict(markdownPath=str(p),markdownSha256=hashlib.sha256(p.read_bytes()).hexdigest(),outDir=str(out)))
   self.assertFalse(out.exists())
 def test_table_not_silently_dropped(self):
  with self.assertRaisesRegex(ValueError,'表格'):blocks('# 报告\n|列|数据|')
 def test_table_cells_preserve_empty_and_escaped_pipe(self):
  t=blocks('|指标|值|说明|\n|---|---|---|\n|收益||A\\|C|')[0][2]
  self.assertEqual(t,[['指标','值','说明'],['收益','','A|C']])
 def test_table_width_and_ragged_rows_rejected(self):
  with self.assertRaisesRegex(ValueError,'列数'):blocks('|A|B|\n|---|---|\n|1|')
  with self.assertRaisesRegex(ValueError,'六列'):blocks('|A|B|C|D|E|F|G|\n|---|---|---|---|---|---|---|')
 def test_native_table_and_cell_reference(self):
  import zipfile,xml.etree.ElementTree as E
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'source.pdf').write_bytes(b'fixture-not-real-pdf');p=root/'a.md';p.write_text('# 报告\n|指标|值|来源|\n|---|---|---|\n|收益|-2.5%|[第1页](source.pdf#page=1)|\n|缺失||未披露|',encoding='utf-8');out=root/'out'
   r=export(dict(markdownPath=str(p),markdownSha256=hashlib.sha256(p.read_bytes()).hexdigest(),outDir=str(out)));self.assertEqual(r['tables'],1)
   with zipfile.ZipFile(out/'公司与行业点评.docx') as z:
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};xml=E.fromstring(z.read('word/document.xml'));table=xml.find('.//w:tbl',ns);rows=table.findall('w:tr',ns);self.assertEqual(len(rows),3);self.assertEqual(len(rows[2].findall('w:tc',ns)),3);self.assertIn('source.pdf#page=1',z.read('word/_rels/document.xml.rels').decode())
if __name__=='__main__':unittest.main()
