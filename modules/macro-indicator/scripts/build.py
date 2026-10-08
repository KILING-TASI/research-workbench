from pathlib import Path
import json,shutil,sys,os,tempfile
ROOT=Path(__file__).resolve().parents[1]
def publish(outputs):
 staged={};before={};committed=[]
 def stage(path,content):
  fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',suffix='.tmp',dir=path.parent)
  try:
   with os.fdopen(fd,'wb') as handle:handle.write(content);handle.flush();os.fsync(handle.fileno())
  except Exception:
   Path(name).unlink(missing_ok=True);raise
  return Path(name)
 try:
  for path,text in outputs.items():
   before[path]=path.read_bytes() if path.exists() else None
   staged[path]=stage(path,text.encode('utf-8'))
  for path,temp in staged.items():os.replace(temp,path);committed.append(path)
 except Exception as error:
  failures=[]
  for path in reversed(committed):
   recovery=None
   try:
    if before[path] is None:path.unlink()
    else:
     recovery=stage(path,before[path]);os.replace(recovery,path)
   except Exception as restore_error:failures.append(str(path)+': '+str(restore_error))
   finally:
    if recovery is not None:recovery.unlink(missing_ok=True)
  if failures:raise RuntimeError('构建失败且部分文件恢复失败：'+'；'.join(failures)) from error
  raise
 finally:
  for temp in staged.values():temp.unlink(missing_ok=True)

def build():
 a=ROOT/'assets';json.loads((a/'data.json').read_text(encoding='utf-8'))
 outputs={}
 def fill(s):
  for marker,name in [('/*MACRO_STYLE*/','style.css'),('<!--MACRO_PANEL-->','panel.html'),('/*MACRO_ENGINE*/','engine.js'),('/*MACRO_UI*/','ui.js'),('/*MACRO_SNAPSHOT*/','data.json')]:
   text=(a/name).read_text(encoding='utf-8')
   if name=='engine.js':text='const MacroConfig='+(a/'model-config.json').read_text(encoding='utf-8').replace('<','\\u003c')+';\n'+text
   if name=='ui.js':text=text.replace('/*MACRO_KNOWLEDGE*/',(a/'education.json').read_text(encoding='utf-8').replace('<','\\u003c'))
   s=s.replace(marker,text.replace('<','\\u003c') if name.endswith('json') else text)
  return s
 outputs[a/'workbench.html']=fill((a/'standalone.template.html').read_text(encoding='utf-8'))
 platform=ROOT.parent/'bjx-newshare-toolkit'
 if platform.exists():
  for name in ['style.css','panel.html','engine.js','ui.js','data.json']:
   text=(a/name).read_text(encoding='utf-8')
   if name=='engine.js':text='const MacroConfig='+(a/'model-config.json').read_text(encoding='utf-8').replace('<','\\u003c')+';\n'+text
   if name=='ui.js':text=text.replace('/*MACRO_KNOWLEDGE*/',(a/'education.json').read_text(encoding='utf-8').replace('<','\\u003c'))
   outputs[platform/'assets'/('macro-'+name)]=text
  sys.path.insert(0,str(platform/'scripts'));from etf_embed import embed
  assets=platform/'assets';s=(assets/'workbench.template.html').read_text(encoding='utf-8').replace('/*ENGINE*/',(assets/'engine.js').read_text(encoding='utf-8')).replace('/*SNAPSHOT*/',(assets/'data.json').read_text(encoding='utf-8').replace('<','\\u003c'))
  # Read new macro resources from the prepared outputs, not the old disk copies.
  for marker,name in [('/*MACRO_STYLE*/','style.css'),('<!--MACRO_PANEL-->','panel.html'),('/*MACRO_ENGINE*/','engine.js'),('/*MACRO_UI*/','ui.js'),('/*MACRO_SNAPSHOT*/','data.json')]:
   value=outputs[assets/('macro-'+name)]
   s=s.replace(marker,value.replace('<','\\u003c') if name.endswith('.json') else value)
  outputs[assets/'workbench.html']=embed(s,assets)
 # Resource or rendering failures above leave every existing output untouched.
 publish(outputs)
if __name__=='__main__':build();print('Macro workbench built')
