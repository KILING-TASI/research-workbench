"""Audit distributable code/docs only; never import author research records."""
import argparse,hashlib,json,zipfile
from pathlib import Path
ROOT='research-workbench/'
ALLOWED=('SKILL.md','README.md','BEGINNER.md','try_demo.py','Start-Demo.cmd','Start-Demo.sh','pyproject.toml','setup.py','_build_skill.py','MANIFEST.in','research_workbench/','DISCLAIMER.md','THIRD_PARTY_NOTICES.md','LICENSE','agents/','references/','scripts/','modules/')
RESOURCE_SUFFIXES={'.py','.js','.cjs','.mjs','.md','.json','.txt','.csv','.html','.css','.yaml','.yml'}

def allowed(rel):
 return (rel in {'LICENSE','Start-Demo.cmd','Start-Demo.sh','pyproject.toml','MANIFEST.in','references/examples/readme-preview-desktop.jpg'} or Path(rel).suffix.lower() in RESOURCE_SUFFIXES) and any(rel.startswith(x) if x.endswith('/') else rel==x for x in ALLOWED)

def source_file(source,path):
 source=Path(source).resolve();path=Path(path)
 if not path.resolve().is_relative_to(source):raise ValueError('交付文件指向源码目录外：'+str(path))
 return path
def audit(package,source):
 source=Path(source).resolve();issues=[];count=0
 with zipfile.ZipFile(package) as z:
  names=z.namelist()
  if (source/'modules').is_dir():
   for module in (source/'modules').iterdir():
    if module.is_dir():
     for required in ['TOPIC.md','scripts/standalone.py']:
      if ROOT+'modules/'+module.name+'/'+required not in names:issues.append('专题必要文件缺失：'+module.name+'/'+required)
  if len(names)!=len(set(names)):issues.append('ZIP含重复文件名')
  for name in names:
   if name.endswith('/'):continue
   if not name.startswith(ROOT):issues.append('包根目录不符合约定：'+name);continue
   rel=name[len(ROOT):];parts=Path(rel).parts
   if '\\' in rel or ':' in rel or '..' in parts or rel.startswith('/') or '__pycache__' in parts or rel.endswith('.pyc') or not allowed(rel):issues.append('非交付内容：'+name);continue
   p=source/rel
   try:source_file(source,p)
   except ValueError as error:issues.append(str(error));continue
   if not p.is_file() or p.read_bytes()!=z.read(name):issues.append('源码与包不一致：'+rel)
   count+=1
  for p in source.rglob('*'):
   if not p.is_file():continue
   rel=p.relative_to(source).as_posix()
   if '__pycache__' in p.parts or p.suffix=='.pyc':continue
   if allowed(rel):
    try:source_file(source,p)
    except ValueError as error:issues.append(str(error));continue
   if allowed(rel) and ROOT+rel not in names:issues.append('交付文件缺失：'+rel)
 return dict(passed=not issues,checkedFiles=count,issues=issues,packageSha256=hashlib.sha256(Path(package).read_bytes()).hexdigest(),scope='脚本、安装说明、依赖提示、教学示例与agent配置；项目研究记录不纳入交付')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('package');p.add_argument('--source',required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if a.out.exists():raise FileExistsError('输出已存在')
 r=audit(a.package,a.source);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
 if not r['passed']:raise SystemExit(1)
