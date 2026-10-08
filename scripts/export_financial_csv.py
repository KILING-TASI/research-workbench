"""Portable CSV financial workpapers; no workbook engine or formula recalculation."""
import csv,json,math,tempfile,os,hashlib,argparse
from pathlib import Path
from collection_validation import day,unique_pairs,reject_constant,finite_json_float

def safe(value):
 if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):return "'"+value
 return value

def growth(row,key):
 value=row.get(key)
 if isinstance(value,dict):
  if 'value' not in value:raise ValueError('同比环比对象缺少value')
  return value['value']
 return value

def verify_associated(data):
 hashes=data.get('inputFileHashes')
 if hashes is None:return 0
 if not isinstance(hashes,dict):raise ValueError('关联来源摘要须为对象')
 for path,digest in hashes.items():
  if not isinstance(path,str) or not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('关联来源摘要格式无效')
  if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise ValueError('关联来源已变化，须重新准备底稿')
 return len(hashes)

def export(input_path,out):
 input_path=Path(input_path);out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在，请另存底稿')
 blob=input_path.read_bytes();data=json.loads(blob.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
 if not isinstance(data,dict):raise ValueError('底稿输入须为对象')
 associated=verify_associated(data)
 rows=data.get('rows')
 if not isinstance(rows,list) or not rows:raise ValueError('底稿字段列表为空')
 seen=set()
 for row in rows:
  if not isinstance(row,dict):raise ValueError('底稿字段结构无效')
  key=(row.get('code'),row.get('key'))
  if not all(isinstance(v,str) and v for v in key) or key in seen:raise ValueError('证券字段标识缺失或重复')
  seen.add(key)
  for field,size in [('dates',6),('values',6),('expected',3)]:
   if not isinstance(row.get(field),list) or len(row[field])!=size:raise ValueError('底稿数组长度不匹配：'+field)
  for date in row['dates']:
   if date is not None:day(date)
  for field in ['label','unit']:
   if not isinstance(row.get(field),str) or not row[field].strip():raise ValueError('底稿指标名称及单位须为非空文字')
  for value in row['values']+row['expected']+[growth(row,'yoy'),growth(row,'qoq')]:
   if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):raise ValueError('底稿数值无效')
 if not isinstance(data.get('sources',[]),list) or any(not isinstance(s,dict) for s in data.get('sources',[])):raise ValueError('底稿来源须为对象数组')
 if not isinstance(data.get('limitations',[]),list) or any(not isinstance(v,str) for v in data.get('limitations',[])):raise ValueError('底稿边界须为文字数组')
 out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.csv-workpapers-',dir=out.parent) as directory:
  stage=Path(directory)
  def table(name,headers,values):
   with (stage/name).open('w',encoding='utf-8-sig',newline='') as handle:
    writer=csv.writer(handle);writer.writerow(headers)
    for value in values:writer.writerow([safe(v) for v in value])
  table('原始字段.csv',['代码','公司','指标','单位','本期','差分前期','上年同期','上年差分前期','上季','上季差分前期'],[[r['code'],r.get('name'),r.get('label'),r.get('unit'),*r['values']] for r in rows])
  table('原始期间.csv',['代码','指标','本期','差分前期','上年同期','上年差分前期','上季','上季差分前期'],[[r['code'],r.get('label'),*r['dates']] for r in rows])
  table('季度结果.csv',['代码','公司','指标','单位','本季度或期末','上年同季或期末','上季或期末','同比比例','环比比例'],[[r['code'],r.get('name'),r.get('label'),r.get('unit'),*r['expected'],growth(r,'yoy'),growth(r,'qoq')] for r in rows])
  table('增长口径.csv',['代码','指标','同比缺失或限制说明','环比缺失或限制说明'],[[r['code'],r['label'],r['yoy'].get('reason') if isinstance(r.get('yoy'),dict) else '',r['qoq'].get('reason') if isinstance(r.get('qoq'),dict) else ''] for r in rows])
  fields=['code','metric','field','period','publishedAt','table','url','archiveSha256','reason']
  table('来源.csv',['代码','指标','字段','所属期','披露日期','报表','来源链接','原始资料摘要','缺口'],[[s.get(k) for k in fields] for s in data.get('sources',[])])
  note='# 财务CSV底稿\n\nCSV可用Excel打开；代码列应按文本导入，避免前导零丢失。缺失数值为空，同比环比为小数比例。季度结果沿用输入中的已计算结果，本导出器不重新计算或认证原文；不是含公式的XLSX模型。\n\n'+ '\n'.join(str(v) for v in data.get('limitations',[]))
  (stage/'底稿说明.md').write_text(note,'utf-8')
  manifest={'inputSha256':hashlib.sha256(blob).hexdigest(),'methodSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()},'associatedInputCount':associated,'associatedInputVerification':'hashes-rechecked' if 'inputFileHashes' in data else 'not-declared','formulaRecalculation':'not-performed','originalVerification':'input-status-not-certified','visualReview':'not-performed'}
  (stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
  verify_associated(data)
  if input_path.read_bytes()!=blob:raise ValueError('底稿输入在导出期间变化')
  if out.exists():raise FileExistsError('输出目录已存在')
  os.rename(stage,out)
 return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out-dir',required=True);a=p.parse_args();export(a.input,a.out_dir)
