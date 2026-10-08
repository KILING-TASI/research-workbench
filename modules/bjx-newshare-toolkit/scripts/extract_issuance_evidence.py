"""Extract contextual numeric candidates from issuer originals, preserving ambiguity."""
import argparse,hashlib,json,re
from decimal import Decimal
from pathlib import Path
from recheck_original_evidence import compact, issuer_code_matches

PATTERNS={
 'price':r'发行价格(?:为|：|:)?(\d+(?:\.\d+)?)元/股',
 'maxShares':r'(?:申购上限|最高申购数量)[^。；]{0,70}?(\d+(?:\.\d+)?)(万股|股)',
 'ratePct':r'(?:网上获配比例|网上配售比例)(?:为|：|:)?(\d+(?:\.\d+)?)%'}

def candidates(pages,fields):
 result={field:[] for field in fields}
 for page,text in enumerate(pages,1):
  text=compact(text)
  for field in fields:
   for m in re.finditer(PATTERNS[field],text):
    value=Decimal(m[1])
    if field=='maxShares' and m[2]=='万股':value*=10000
    result[field].append({'value':str(value),'page':page,'excerpt':text[max(0,m.start()-50):m.end()+60],'unit':{'price':'元/股','ratePct':'%','maxShares':'股'}[field]})
 return {field:{'status':'unique-candidate' if len({x['value'] for x in entries})==1 else 'conflicting-candidates' if entries else 'missing-or-layout-unsupported','candidates':entries} for field,entries in result.items()}

def supplement_ocr(pages,sidecar,source_hash):
 """Accept hash-bound, page-numbered external OCR only as review candidates."""
 if sidecar.get('sourceSha256')!=source_hash:raise ValueError('OCR source hash mismatch')
 if not isinstance(sidecar.get('engine'),str) or not sidecar['engine'].strip():raise ValueError('OCR engine/source required')
 result=list(pages);used=[];seen=set()
 for entry in sidecar.get('pages',[]):
  page=entry.get('page');text=entry.get('text')
  if type(page)!=int or not 1<=page<=len(pages) or page in seen:raise ValueError('OCR page missing, duplicate or outside PDF')
  seen.add(page)
  if not isinstance(text,str) or not text.strip() or len(text)>200000:raise ValueError('OCR text missing or oversized')
  if not compact(pages[page-1]):result[page-1]=text;used.append(page)
 return result,used

def extract(manifest):
 from pypdf import PdfReader
 results=[]
 for item in manifest['documents']:
  row={k:item.get(k) for k in ['code','name','sourceUrl','metadataDate','kind']}
  try:
   path=Path(item['file']);source_hash=hashlib.sha256(path.read_bytes()).hexdigest()
   if item.get('sha256') and item['sha256']!=source_hash:raise ValueError('Downloaded manifest hash mismatch; original changed before extraction')
   reader=PdfReader(path)
   if len(reader.pages)>300:raise ValueError('PDF exceeds extraction page limit')
   pages=[p.extract_text() or '' for p in reader.pages]
   ocr_pages=[]
   if item.get('ocrSidecar'):
    sidecar_path=Path(item['ocrSidecar'])
    if sidecar_path.stat().st_size>10000000:raise ValueError('OCR sidecar exceeds size limit')
    pages,ocr_pages=supplement_ocr(pages,json.loads(sidecar_path.read_text(encoding='utf-8')),source_hash)
   row['textCoverage']={'ocrPages':ocr_pages,'emptyPages':[i+1 for i,t in enumerate(pages) if not compact(t)],'ocrAutoVerified':False}
   identity=compact(''.join(pages[:8]))
   if not issuer_code_matches(item['code'],identity) or compact(item['name']) not in identity:raise ValueError('Issuer code and name not both matched in opening pages')
   fields=['ratePct'] if item['kind']=='result' else ['price','maxShares'] if item['kind']=='issue' else []
   if not fields:raise ValueError('Document kind must be issue/result')
   row.update(status='extracted-for-review',sha256=hashlib.sha256(path.read_bytes()).hexdigest(),fields=candidates(pages,fields),file=str(path),ocrReviewRequired=bool(ocr_pages))
   for field in row['fields'].values():
    for candidate in field['candidates']:candidate['textOrigin']='external-ocr-unverified' if candidate['page'] in ocr_pages else 'embedded-pdf-text'
  except Exception as error:row.update(status='failed',reason=str(error))
  results.append(row)
 return {'documents':results,'boundary':'Context extraction creates candidates only; no automatic verification badge, OCR guarantee or first-publication certification','modelOptimizationRun':False}

def main():
 p=argparse.ArgumentParser();p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise ValueError('Use a new report filename')
 spec=json.loads(a.manifest.read_text(encoding='utf-8'))
 if len(spec['documents'])>50:raise ValueError('Maximum 50 documents per batch')
 report=extract(spec);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'documents':len(report['documents']),'failed':sum(x['status']=='failed' for x in report['documents'])}))
if __name__=='__main__':main()
