"""Build a code/docs-only portable package with exact source audit, no runtime libraries."""
import argparse,os,tempfile,zipfile
from pathlib import Path
from package_audit import ROOT,allowed,audit,source_file

def build(source,out):
 source=Path(source).resolve();out=Path(out)
 if out.exists():raise FileExistsError('交付包已存在，请另存版本')
 if not (source/'SKILL.md').is_file():raise ValueError('缺少SKILL.md')
 out.parent.mkdir(parents=True,exist_ok=True);fd,name=tempfile.mkstemp(suffix='.zip',prefix='.package-',dir=out.parent);os.close(fd);temporary=Path(name)
 try:
  with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as z:
   for path in sorted(source.rglob('*')):
    if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
    rel=path.relative_to(source).as_posix()
    if allowed(rel):z.write(source_file(source,path),ROOT+rel)
  result=audit(temporary,source)
  if not result['passed']:raise ValueError('交付范围检查失败：'+str(result['issues']))
  os.rename(temporary,out)
  return result
 finally:
  if temporary.exists():temporary.unlink()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--out',required=True);a=p.parse_args();build(a.source,a.out)
