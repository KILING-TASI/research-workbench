"""Unique temporary file prevents simultaneous component writers sharing .tmp."""
import json,os,tempfile
from pathlib import Path

def write(path,value):
 path=Path(path);payload=json.dumps(value,ensure_ascii=False,allow_nan=False)
 path.parent.mkdir(parents=True,exist_ok=True)
 fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
 try:
  with os.fdopen(fd,'w',encoding='utf-8') as handle:
   handle.write(payload);handle.flush();os.fsync(handle.fileno())
  os.replace(tmp,path)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
