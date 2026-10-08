"""Read-only content integrity; not evidence truth or visual acceptance."""
import argparse,json,hashlib,re
from collection_validation import reject_constant
from pathlib import Path
from collection_quality_brief import method_files

def unique_pairs(pairs):
 result={}
 for key,value in pairs:
  if key in result:raise ValueError('清单出现重复字段')
  result[key]=value
 return result

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(manifest_path,input_path=None,original_path=None):
 path=Path(manifest_path);root=path.resolve().parent
 try:
  data=json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
  if not isinstance(data,dict) or type(data.get('schemaVersion'))!=int or data.get('schemaVersion')!=1:raise ValueError('清单版本缺失或不支持')
  artifact=data.get('artifactType','collection-quality')
  if artifact=='archived-holdings':
   from archive_holdings import method_files as methods_fn
   expected_files={'result.json','持仓核对.md','持仓核对.html'}
  elif artifact=='collection-quality':methods_fn=method_files;expected_files={'资料质量说明.md','资料质量说明.html'}
  elif artifact=='fund-comparison':
   from fund_comparison_brief import method_files as methods_fn
   expected_files={'input.json','比较结果.json','基金比较说明.md','基金比较说明.html'}
  else:raise ValueError('未知报告清单类型')
  if not isinstance(data.get('files'),dict) or set(data['files'])!=expected_files:raise ValueError('清单报告文件集合不匹配')
  known={p.name:p for p in methods_fn()}
  if not isinstance(data.get('methodFiles'),dict) or set(data['methodFiles'])!=set(known):raise ValueError('清单方法文件集合不匹配')
  hashes=[data.get('inputSha256'),data.get('methodSha256'),*data['files'].values(),*data['methodFiles'].values()]
  if artifact=='archived-holdings':hashes.append(data.get('sourceSha256'))
  if any(not isinstance(h,str) or not re.fullmatch(r'[0-9a-f]{64}',h) for h in hashes):raise ValueError('清单摘要格式无效')
 except (ValueError,OSError,UnicodeError) as exc:return {'status':'invalid-manifest','problems':[str(exc)],'sourceVerification':'not-verified','visualReview':'not-performed'}
 problems=[]
 for name,expected in data['files'].items():
  candidate=root/name
  try:
   if candidate.resolve().parent!=root:problems.append('报告文件越出目录：'+name);continue
   if not candidate.is_file():problems.append('报告文件缺失：'+name)
   elif digest(candidate)!=expected:problems.append('报告文件内容变化：'+name)
  except OSError:problems.append('报告文件不可读取：'+name)
 input_match=None
 if input_path is not None:
  try:input_match=digest(Path(input_path))==data['inputSha256']
  except OSError:input_match=False
  if not input_match:problems.append('输入快照缺失或内容变化')
 method_changes=[]
 original_match=None
 if original_path is not None:
  try:original_match=artifact=='archived-holdings' and digest(Path(original_path))==data['sourceSha256']
  except (OSError,KeyError):original_match=False
  if not original_match:problems.append('原文文件缺失、内容变化或清单未登记原文')
 for name,p in known.items():
  try:
   if digest(p)!=data['methodFiles'][name]:method_changes.append(name)
  except OSError:method_changes.append(name);problems.append('生成方法文件不可读取：'+name)
 try:
  combined=hashlib.sha256(b''.join(p.read_bytes() for p in methods_fn())).hexdigest()
  if combined!=data['methodSha256'] and not method_changes:problems.append('方法汇总摘要与逐文件摘要不一致')
 except OSError:problems.append('生成方法汇总不可读取')
 return {'status':'content-mismatch' if problems else 'stored-content-verified-method-different' if method_changes else 'stored-content-verified','problems':problems,'inputChecked':input_path is not None,'inputMatches':input_match,'originalChecked':original_path is not None,'originalMatches':original_match,'methodChanges':method_changes,'sourceVerification':'not-verified','visualReview':'not-performed','limitations':['仅检查保存内容；不能证明数据来源真实或最新','未提供输入快照时不核对输入内容','未执行页面视觉验收']}

def main():
 p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('--input');p.add_argument('--original');a=p.parse_args();print(json.dumps(verify(a.manifest,a.input,a.original),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
