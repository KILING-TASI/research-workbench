"""Explicit, portable component configuration; no installation or path guessing."""
import os
import hashlib,json,zipfile
from pathlib import Path

def component_environment(directory=None):
 env=os.environ.copy()
 selected=directory if directory is not None else env.get('ARTIFACT_NODE_MODULES')
 if selected is not None:
  if not isinstance(selected,str) or not selected.strip():raise ValueError('导出组件目录需非空路径')
  path=Path(selected).expanduser().resolve()
  if not path.is_dir():raise ValueError('导出组件目录不存在：'+str(path))
  env['ARTIFACT_NODE_MODULES']=str(path)
 return env

def verify_workbook(path,input_path):
 path=Path(path)
 if not path.is_file() or not zipfile.is_zipfile(path):raise OSError('导出器未生成有效XLSX文件')
 with zipfile.ZipFile(path) as archive:
  if not {'[Content_Types].xml','_rels/.rels','xl/workbook.xml'}.issubset(archive.namelist()):raise OSError('导出文件缺少XLSX结构')
 try:qa=json.loads(Path(str(path)+'.qa.json').read_text(encoding='utf-8'))
 except (OSError,ValueError) as exc:raise OSError('缺少可读的Excel公式核对记录') from exc
 if not isinstance(qa,dict):raise OSError('Excel核对记录必须为对象')
 if qa.get('formulaDifferences')!=[]:raise OSError('Excel公式核对存在差异或记录缺失')
 for name,p in [('inputSha256',Path(input_path)),('workbookSha256',path)]:
  if qa.get(name)!=hashlib.sha256(p.read_bytes()).hexdigest():raise OSError('Excel核对记录与文件不匹配：'+name)
 try:
  inputs=json.loads(Path(input_path).read_text(encoding='utf-8'))
  collections={key:inputs[key] for key in ['rows','companies','groups']}
  if any(not isinstance(value,list) or not value for value in collections.values()):raise ValueError('输入集合为空或类型错误')
 except (OSError,ValueError,KeyError,TypeError) as exc:raise OSError('Excel检查输入结构未确认') from exc
 expected={'quarterValueChecks':len(collections['rows'])*3,'growthChecks':len(collections['rows'])*2,'summaryChecks':len(collections['companies'])*4,'groupChecks':len(collections['groups'])*4}
 for key,count in expected.items():
  if type(qa.get(key)) is not int or qa[key]!=count:raise OSError('Excel公式检查数量缺失或与输入不符：'+key)
 try:
  scan=qa['errorScan']
  if not isinstance(scan,str):raise ValueError('扫描格式错误')
  entries=[json.loads(line) for line in scan.splitlines() if line.strip()]
  if len(entries)!=1 or entries[0].get('kind')!='notice' or entries[0].get('message')!='Cell search matched 0 entries.':raise ValueError('未明确确认零错误')
 except (KeyError,ValueError,AttributeError) as exc:raise OSError('Excel错误单元格扫描未通过或记录缺失') from exc
 return qa
