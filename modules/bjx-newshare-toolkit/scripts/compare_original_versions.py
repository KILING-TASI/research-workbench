"""Page-located full extracted-text differences; no automatic semantic certification."""
import argparse, difflib, hashlib, json, re
from pathlib import Path
from pypdf import PdfReader

def extract(file, name, code):
    reader=PdfReader(file)
    if len(reader.pages)>1000:raise ValueError('Page limit exceeded')
    pages=[p.extract_text() or '' for p in reader.pages]
    compact=lambda x:re.sub(r'\s+','',x)
    opening=compact(''.join(pages[:8]))
    if name not in opening or not re.search(r'(?<!\d)'+re.escape(code)+r'(?!\d)', '\n'.join(pages[:8])):raise ValueError('Issuer identity not found')
    if any(not compact(p) for p in pages):raise ValueError('Empty/scanned page: full text comparison unavailable')
    lines=[]
    for page,text in enumerate(pages,1):
        for line in text.splitlines():
            normalized=compact(line)
            if normalized:lines.append({'page':page,'text':line,'normalized':normalized})
    return {'sha256':hashlib.sha256(file.read_bytes()).hexdigest(),'pageCount':len(pages),'lines':lines}

def difference_hint(change):
    # Ignore only an exact prospectus page marker for this optional hint.
    # Never discard the original difference or a business number.
    def body(lines):
        return ''.join(x['normalized'] for x in lines if not re.fullmatch(r'1-1-\d+',x['normalized']))
    before,after=body(change['before']),body(change['after'])
    if before==after:
        return 'page-marker-or-line-wrap-only-in-extracted-text'
    return 'content-difference-needs-review'

def compare(before,after):
    matcher=difflib.SequenceMatcher(None,[x['normalized'] for x in before['lines']],[x['normalized'] for x in after['lines']],autojunk=False)
    changes=[]
    for tag,a,b,c,d in matcher.get_opcodes():
        if tag!='equal':
            change={'type':tag,'before':before['lines'][a:b],'after':after['lines'][c:d]}
            change['reviewHint']=difference_hint(change);changes.append(change)
    hints={key:sum(x['reviewHint']==key for x in changes) for key in ['page-marker-or-line-wrap-only-in-extracted-text','content-difference-needs-review']}
    return {'beforeHash':before['sha256'],'afterHash':after['sha256'],'beforePages':before['pageCount'],'afterPages':after['pageCount'],'changes':changes,'reviewHintCounts':hints,'semanticReviewComplete':False,'boundary':'All extracted lines compared, including layout/page-number differences; hints retain every original difference and do not certify table meaning. PDF extraction may omit images. No automatic fact replacement.'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--name',required=True);p.add_argument('--document-code',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():raise ValueError('Use new output')
    r=compare(extract(a.before,a.name,a.document_code),extract(a.after,a.name,a.document_code));a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'changes':len(r['changes']),'beforePages':r['beforePages'],'afterPages':r['afterPages'],'semanticReviewComplete':False}))

if __name__=='__main__':main()
