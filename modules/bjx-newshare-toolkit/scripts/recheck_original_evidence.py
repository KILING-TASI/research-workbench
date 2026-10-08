"""Recheck registered numeric evidence against provided original PDFs; fail closed."""
import argparse,hashlib,json,re
from decimal import Decimal
from pathlib import Path

def compact(text):return re.sub(r'\s+','',text).replace(',','').replace('，','')
def issuer_code_matches(code,text):
 return bool(re.search(r"(?<![0-9])"+re.escape(str(code))+r"(?![0-9])",text))

def numeric_matches(field,value,text):
 text=re.sub(r'\s+','',text).replace('，',',');expected=Decimal(str(value));found=[]
 token=r'(?<![0-9.,eE+\-−－])((?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?)'
 if field=='price':pattern=r'发行价格(?:为|：|:)?'+token+r'元/股'
 elif field=='ratePct':pattern=r'(?:网上获配比例|网上配售比例)(?:为|：|:)?'+token+r'%'
 elif field=='maxShares':pattern=r'(?:申购上限|最高申购数量)[^。；]{0,70}?'+token+r'(万股|股)'
 else:return False
 for match in re.finditer(pattern,text):
  n=Decimal(match[1].replace(',',''));n*=10000 if field=='maxShares' and match[2]=='万股' else 1
  found.append(n)
 return bool(found) and set(found)=={expected}

def original_span(text,excerpt):
 positions=[i for i,c in enumerate(text) if not c.isspace() and c not in ',，']
 normalized=compact(text);quote=compact(excerpt)
 if not quote or normalized.count(quote)!=1:raise ValueError('Registered excerpt is missing or ambiguous on page')
 start=normalized.index(quote)
 return text[positions[start]:positions[start+len(quote)-1]+1]

def recheck(overlays,pdf_dir):
 from pypdf import PdfReader
 files={};out=[]
 for pdf in pdf_dir.glob('*.pdf'):
  digest=hashlib.sha256(pdf.read_bytes()).hexdigest();files.setdefault(digest,[]).append(pdf)
 for code,r in overlays.get('records',{}).items():
  for field,e in r.get('officialFieldVerification',{}).items():
   if e.get('status')!='original-numeric-matched':continue
   result={'code':code,'field':field,'expected':e.get('value'),'sourceUrl':e.get('sourceUrl'),'page':e.get('page'),'sha256':e.get('sha256'),'status':'not-verified'}
   try:
    candidates=files.get(e.get('sha256'),[])
    if not candidates:raise ValueError('Matching original hash unavailable')
    pdf=candidates[0];reader=PdfReader(pdf);page=e.get('page')
    if type(page)!=int or not 1<=page<=len(reader.pages):raise ValueError('Invalid registered page')
    identity=compact(''.join(p.extract_text() or '' for p in reader.pages[:8]))
    if not issuer_code_matches(code,identity):raise ValueError('Issuer code not confirmed in PDF')
    raw_text=reader.pages[page-1].extract_text() or '';text=compact(raw_text)
    if not text:raise ValueError('No extractable text; OCR/manual review required')
    excerpt=compact(e.get('excerpt',''))
    if not excerpt or excerpt not in text:raise ValueError('Registered excerpt does not match page')
    matched=original_span(raw_text,e.get('excerpt',''))
    if not numeric_matches(field,e['value'],matched):raise ValueError('Numeric value or unit not matched to field context')
    result.update(status='original-rechecked',file=str(pdf),pageTextSha256=hashlib.sha256(text.encode()).hexdigest())
   except Exception as error:result['reason']=str(error)
   out.append(result)
 return {'results':out,'verified':sum(r['status']=='original-rechecked' for r in out),'pending':sum(r['status']!='original-rechecked' for r in out),'boundary':'Registered evidence recheck only; no first-publication certification; scanned text needs OCR/manual review'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--overlays',type=Path,required=True);p.add_argument('--pdf-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise ValueError('Use a new report path')
 report=recheck(json.loads(a.overlays.read_text(encoding='utf-8')),a.pdf_dir);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'verified':report['verified'],'pending':report['pending']}))
if __name__=='__main__':main()
