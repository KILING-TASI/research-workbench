"""Compare the declared delivery files across source, installed skill and ZIP."""
import argparse,hashlib,json,re,zipfile
from pathlib import Path
from publish_bjx_delivery import FILES,distribution_bytes

def audit(source,installed,archive):
 mismatches=[];hashes={}
 with zipfile.ZipFile(archive) as z:
  roots=[n[:-len('SKILL.md')] for n in z.namelist() if n.endswith('SKILL.md')]
  if len(roots)!=1:raise ValueError('Archive skill root ambiguous')
  prefix=roots[0];zip_error=z.testzip()
  for rel in FILES:
   s=source/rel;i=installed/rel
   if not s.exists() or not i.exists():mismatches.append({'file':rel,'reason':'source or installed missing'});continue
   body=s.read_bytes();hashes[rel]=hashlib.sha256(body).hexdigest()
   if i.read_bytes()!=body:mismatches.append({'file':rel,'reason':'installed differs'})
   try:
    if z.read(prefix+rel)!=distribution_bytes(rel,body):mismatches.append({'file':rel,'reason':'archive differs from distribution projection'})
   except KeyError:mismatches.append({'file':rel,'reason':'archive missing'})
  pdf_entries=[n for n in z.namelist() if n.lower().endswith('.pdf')]
 missing_refs=[]
 for name in ['workbench.html','bjx-panel.html']:
  text=(source/'assets'/name).read_text(encoding='utf-8')
  for ref in re.findall(r'(?:src|href)="([^"]+)"',text):
   if re.match(r'^(?:https?:|#|data:)',ref):continue
   target=source/'assets'/ref.split('#')[0]
   if not target.is_file():missing_refs.append({'page':name,'reference':ref})
 return {'declaredFiles':len(FILES),'fileHashes':hashes,'mismatches':mismatches,'missingPageReferences':missing_refs,'zipIntegrity':zip_error or 'passed','archivePdfEntries':pdf_entries,'scope':'Declared delivery files and static relative references; legacy project files and browser rendering not certified','visualVerified':False,'passed':not mismatches and not missing_refs and not zip_error}
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--installed',type=Path,required=True);p.add_argument('--zip',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise ValueError('Use new audit output')
 r=audit(a.source,a.installed,a.zip);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'passed':r['passed'],'declaredFiles':r['declaredFiles'],'mismatches':len(r['mismatches']),'missingReferences':len(r['missingPageReferences']),'archivePdfEntries':len(r['archivePdfEntries'])}));
 if not r['passed']:raise SystemExit(1)
if __name__=='__main__':main()
