"""Read-only DOCX/PPTX integrity checks, distinct from visual/semantic review."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
from collection_validation import unique_pairs,reject_constant,finite_json_float

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def contained(root,name):
 if not isinstance(name,str) or not name:raise ValueError('导出文件路径无效')
 p=(root/name).resolve()
 if not p.is_relative_to(root):raise ValueError('引用超出导出目录')
 return p

def verify(manifest,markdown=None):
 manifest=Path(manifest).resolve();root=manifest.parent;record=json.loads(manifest.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
 if record.get('format') not in ['docx','pptx']:raise ValueError('仅支持DOCX/PPTX')
 output=contained(root,record.get('outputFile'))
 if digest(output)!=record.get('outputSha256'):raise ValueError('成品文件哈希变化')
 if markdown is not None and digest(Path(markdown))!=record.get('markdownSha256'):raise ValueError('正文哈希变化')
 refs=[];declared_paragraphs_checked=False;body_checked=False
 for item in record.get('references',[]):
  p=contained(root,item.get('path'))
  if digest(p)!=item.get('sha256'):raise ValueError('附带原文哈希变化：'+item['path'])
  refs.append(item['path'])
 with zipfile.ZipFile(output) as z:
  if z.testzip() is not None:raise ValueError('Office文件内容损坏')
  names=z.namelist()
  if '[Content_Types].xml' not in names:raise ValueError('缺少Office类型声明')
  if record['format']=='docx':
   doc=ET.fromstring(z.read('word/document.xml'))
   text=''.join(n.text or '' for n in doc.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
   if markdown is not None:
    from export_financial_docx import blocks
    values=[]
    for kind,level,value in blocks(Path(markdown).read_text(encoding='utf-8-sig')):
     values.extend(cell for row in value for cell in row) if kind=='table' else values.append(value)
    display=lambda s:re.sub(r'\s+','',re.sub(r'\[([^\]]+)\]\(([^)]+)\)',r'\1',s).replace('**',''))
    expected=display(''.join(values))
    if not expected or expected not in re.sub(r'\s+','',text):raise ValueError('Word可编辑正文与源Markdown的段落或表格顺序不一致')
    body_checked=True
   page_count=None
  else:
   slides=sorted([n for n in names if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)],key=lambda n:int(re.search(r'(\d+)\.xml$',n)[1]))
   if type(record.get('slides')) is not int or record['slides']<1:raise ValueError('PPT页数须为正整数')
   if len(slides)!=record.get('slides'):raise ValueError('PPT页数与记录不一致')
   texts=[''.join(n.text or '' for n in ET.fromstring(z.read(s)).iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t')) for s in slides];text=''.join(texts)
   page_count=len(slides)
   compact=lambda t:re.sub(r'\s+','',t)
   paragraphs=record.get('paragraphs')
   if paragraphs is not None:
    if not isinstance(paragraphs,list) or len(paragraphs)!=len(slides) or any(not isinstance(row,list) or not row or any(not isinstance(v,str) or not v.strip() for v in row) for row in paragraphs):raise ValueError('PPT逐页正文记录无效')
    for slide,actual in zip(paragraphs,texts):
     for paragraph in slide:
      if compact(paragraph) not in compact(actual):raise ValueError('PPT可编辑正文未在对应页完整保留')
    declared_paragraphs_checked=True
 if not text.strip():raise ValueError('未取得可编辑正文')
 return dict(status='stored-content-verified',format=record['format'],pages=page_count,editableTextCharacters=len(text),referencesChecked=refs,bodyChecked=body_checked,markdownSourceHashChecked=markdown is not None,declaredSlideParagraphsChecked=declared_paragraphs_checked,semanticCertification=False,outputSha256=record['outputSha256'],visualReview='not-performed-by-this-check',limitations=['哈希及可编辑文字检查不代表语义核验或排版合格','提供源Markdown时Word按当前导出器规则对照文字顺序；PPT仅检查清单所声明的逐页正文','DOCX页数须实际渲染，不以XML估计','PPT记录中的正文匹配不代表原始研究结论正确'])

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('--markdown');a=p.parse_args();print(json.dumps(verify(a.manifest,a.markdown),ensure_ascii=False,indent=2))
