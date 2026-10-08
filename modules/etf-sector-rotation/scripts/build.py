"""Build standalone ETF page and, if present, update the multi-scene workbench."""
from pathlib import Path
import json,re,sys,os,tempfile
ROOT=Path(__file__).resolve().parents[1]

def publish(outputs):
 staged={};before={};committed=[]
 def stage(path,content):
  fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',suffix='.tmp',dir=path.parent)
  try:
   with os.fdopen(fd,'wb') as handle:handle.write(content);handle.flush();os.fsync(handle.fileno())
  except Exception:Path(name).unlink(missing_ok=True);raise
  return Path(name)
 try:
  for path,text in outputs.items():
   before[path]=path.read_bytes() if path.exists() else None;staged[path]=stage(path,text.encode('utf-8'))
  for path,temp in staged.items():os.replace(temp,path);committed.append(path)
 except Exception as error:
  failures=[]
  for path in reversed(committed):
   recovery=None
   try:
    if before[path] is None:path.unlink()
    else:recovery=stage(path,before[path]);os.replace(recovery,path)
   except Exception as restore_error:failures.append(str(path)+': '+str(restore_error))
   finally:
    if recovery is not None:recovery.unlink(missing_ok=True)
  if failures:raise RuntimeError('构建失败且部分文件恢复失败：'+'；'.join(failures)) from error
  raise
 finally:
  for temp in staged.values():temp.unlink(missing_ok=True)
def build():
 from build_market_tracking import build as build_tracking
 tracking=build_tracking(write=False)
 assets=ROOT/'assets'
 outputs={}
 if tracking is not None:outputs[assets/'market-data.json']=json.dumps(tracking,ensure_ascii=False,indent=2,allow_nan=False)
 ui=(assets/'ui.js').read_text(encoding='utf-8')
 for variable,name in [('ETFMarketSnapshot','market-data.json'),('ETFOfficialSnapshot','market-official.json')]:
  path=assets/name
  if path in outputs or path.exists():
   value=outputs[path] if path in outputs else path.read_text(encoding='utf-8')
   replacement='const '+variable+'='+json.dumps(json.loads(value),ensure_ascii=False,allow_nan=False).replace('<',r'\u003c')+';'
   ui=re.sub(r'const '+variable+r'=.*?;(?=\s*(?:window|const|$))',lambda _:replacement,ui,flags=re.S)
 outputs[assets/'ui.js']=ui
 json.loads((assets/'data.json').read_text(encoding='utf-8'))
 text=(assets/'standalone.template.html').read_text(encoding='utf-8')
 for marker,name in [('/*ETF_STYLE*/','style.css'),('<!--ETF_PANEL-->','panel.html'),('/*ETF_ENGINE*/','engine.js'),('/*ETF_UI*/','ui.js')]:
  text=text.replace(marker,ui if name=='ui.js' else (assets/name).read_text(encoding='utf-8'))
 text=text.replace('/*ETF_SNAPSHOT*/',(assets/'data.json').read_text(encoding='utf-8').replace('<','\\u003c'))
 outputs[assets/'workbench.html']=text
 platform=ROOT.parent/'bjx-newshare-toolkit/assets'
 if platform.exists():
  shared=ROOT.parent/'shared-market/taxonomy.js'
  if shared.exists():outputs[platform/'market-taxonomy.js']=shared.read_text(encoding='utf-8')
  for source,name in [('style.css','etf-style.css'),('panel.html','etf-panel.html'),('engine.js','etf-engine.js'),('ui.js','etf-ui.js'),('data.json','etf-data.json')]:outputs[platform/name]=ui if source=='ui.js' else (assets/source).read_text(encoding='utf-8')
  template=(platform/'workbench.template.html').read_text(encoding='utf-8')
  selection=assets/'selection-data.json'
  if selection.exists():
   replacement='const ETFSelectionSnapshot='+json.dumps(json.loads(selection.read_text(encoding='utf8')),ensure_ascii=False).replace('<',r'\u003c')+';'
   template=re.sub(r'const ETFSelectionSnapshot=.*?;(?=\nconst ETFSelectionModel)',lambda _:replacement,template,flags=re.S)
  sys.path.insert(0,str(platform.parent/'scripts'))
  from etf_embed import embed
  template=template.replace('/*ENGINE*/',(platform/'engine.js').read_text(encoding='utf-8')).replace('/*SNAPSHOT*/',(platform/'data.json').read_text(encoding='utf-8').replace('<',r'\u003c'))
  for marker,name in [('/*ETF_STYLE*/','etf-style.css'),('<!--ETF_PANEL-->','etf-panel.html'),('/*ETF_ENGINE*/','etf-engine.js'),('/*ETF_UI*/','etf-ui.js'),('/*ETF_SNAPSHOT*/','etf-data.json')]:
   value=outputs[platform/name];template=template.replace(marker,value.replace('<',r'\u003c') if name.endswith('.json') else value)
  outputs[platform/'workbench.html']=embed(template,platform)
 publish(outputs)
 return text
if __name__=='__main__':build();print('ETF工作台及平台已生成')
