"""Repeat-check registered correction evidence against user-supplied original PDFs."""
import argparse, hashlib, json, re
from pathlib import Path
from pypdf import PdfReader

def check(evidence, file):
    if hashlib.sha256(file.read_bytes()).hexdigest() != evidence['sha256']:
        raise ValueError('Original file hash differs')
    pages = [p.extract_text() or '' for p in PdfReader(file).pages]
    compact = lambda s: re.sub(r'\s+', '', s)
    opening = compact(''.join(pages[:2]))
    for key in ['issuerName','documentCode']:
        if not isinstance(evidence.get(key),str) or not compact(evidence[key]):raise ValueError('Issuer identity missing')
    if compact(evidence['issuerName']) not in opening or not re.search(r'(?<![0-9])'+re.escape(compact(evidence['documentCode']))+r'(?![0-9])',opening):
        raise ValueError('Issuer identity missing')
    if not isinstance(evidence.get('excerpts'),list) or not evidence['excerpts']:raise ValueError('No excerpts supplied for correction recheck')
    for excerpt in evidence['excerpts']:
        page = excerpt['page']
        if type(page)!=int or page < 1 or page > len(pages) or not compact(excerpt['text']):
            raise ValueError('Invalid excerpt page')
        if compact(excerpt['text']) not in compact(pages[page-1]):
            raise ValueError('Registered excerpt differs')
    return {'status':'registered-text-rechecked', 'summarySemanticsAutoCertified':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--overlays',type=Path,required=True);p.add_argument('--pdf-dir',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('Use new output')
    hashes={hashlib.sha256(f.read_bytes()).hexdigest():f for f in a.pdf_dir.glob('*.pdf')}
    rows=[]
    for code, r in json.loads(a.overlays.read_text(encoding='utf-8')).get('records',{}).items():
        for e in r.get('announcementCorrectionReviews',[]):
            row={'code':code,'sourceUrl':e['sourceUrl']}
            try:row.update(check(e,hashes[e['sha256']]))
            except Exception as exc:row.update(status='failed',reason=str(exc))
            rows.append(row)
    result={'records':rows,'passed':bool(rows) and all(r['status']=='registered-text-rechecked' for r in rows)}
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':result['passed'],'records':len(rows)}))
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
