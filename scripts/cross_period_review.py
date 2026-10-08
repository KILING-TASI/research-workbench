"""Compare declared snapshots only after method and file integrity checks."""
import hashlib,json,datetime as dt
from decimal import Decimal,InvalidOperation
from pathlib import Path
from io import BytesIO
from collection_validation import unique_pairs,reject_constant,finite_json_float

def load_json(text):
 return json.loads(text,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def date_value(value):
 if not isinstance(value,str):raise ValueError("日期须为标准YYYY-MM-DD")
 result=dt.date.fromisoformat(value)
 if result.isoformat()!=value:raise ValueError("日期须为标准YYYY-MM-DD")
 return result

BASE=['entityId','field','periodBasis','statementScope','basis','unit','currency']
METHOD_KEYS=['definitionVersion','industryClassificationVersion','benchmarkId','distributionPolicy','adjustmentVersion','consolidationScope']
LABELS={'definitionVersion':'指标定义版本','industryClassificationVersion':'行业分类版本','benchmarkId':'比较基准','distributionPolicy':'分红处理','adjustmentVersion':'复权版本','consolidationScope':'合并范围','entityId':'标的','field':'指标','periodBasis':'期间口径','statementScope':'报表范围','basis':'金额口径','unit':'单位','currency':'币种'}
VERIFICATION={'manual-selected-label-and-amount-matched':'已对所选字段名称与金额人工核对','not-verified':'尚未核对字段与金额'}
def number(v):
 if isinstance(v,bool) or v is None:raise ValueError('数值不得为空或布尔值')
 try:n=Decimal(str(v))
 except InvalidOperation:raise ValueError('数值格式无效')
 if not n.is_finite():raise ValueError('数值必须有限')
 return n
def check_source(row,asof):
 for k in BASE+['period','publishedAt']:
  if not isinstance(row.get(k),str) or not row[k].strip():raise ValueError('缺少口径:'+k)
 period=date_value(row['period']);published=date_value(row['publishedAt'])
 if period>published or published>asof:raise ValueError('报告期、披露日或截止日越界')
 if row.get('comparabilityWarning') is not None and (not isinstance(row['comparabilityWarning'],str) or not row['comparabilityWarning'].strip()):raise ValueError('可比性警告须为非空文字')
 source=row.get('source',{})
 if not isinstance(source,dict) or not isinstance(source.get('path'),str):raise ValueError('须提供原文来源对象和路径')
 p=Path(source['path'])
 if not p.is_file() or p.suffix.lower()!='.pdf':raise ValueError('必须提供本地PDF原文')
 raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest()
 if not raw.startswith(b'%PDF-') or source.get('sha256')!=digest:raise ValueError('原文PDF哈希不符')
 page=source.get('page')
 if isinstance(page,bool) or not isinstance(page,int) or page<1:raise ValueError('须提供PDF物理页码')
 import pdfplumber
 with pdfplumber.open(BytesIO(raw)) as doc:
  if page>len(doc.pages):raise ValueError('原文页码越界')
 methods=row.get('methods',{})
 if not isinstance(methods,dict):raise ValueError('methods须为对象')
 if any(k not in METHOD_KEYS for k in methods):raise ValueError('未知方法口径字段')
 if any(v is not None and (not isinstance(v,str) or (v!='' and not v.strip())) for v in methods.values()):raise ValueError('方法口径须为非空文字或明确缺失')
 return {'path':str(p.resolve()),'sha256':digest,'page':page,'sourceUrl':source.get('sourceUrl'),
         'verification':'file-integrity-and-page-range-only','fieldVerification':source.get('fieldVerification','not-verified'),
         'limitation':'字段核验状态由输入声明；哈希和页码检查不证明数值或标签已与原文匹配'}
def review(spec):
 if not isinstance(spec,dict):raise ValueError('跨期输入须为对象')
 asof=date_value(spec['asOf']);required=spec.get('requiredMethodKeys',[])
 if not isinstance(required,list) or not required or any(k not in METHOD_KEYS for k in required) or len(set(required))!=len(required):raise ValueError('须明确不重复的必需方法口径字段')
 pairs=spec.get('pairs',[])
 if not isinstance(pairs,list) or not 1<=len(pairs)<=200:raise ValueError('比较对数须为1至200')
 result=[]
 for pair in pairs:
  if not isinstance(pair,dict) or any(not isinstance(pair.get(k),dict) for k in ['before','after']):raise ValueError('比较对须为前后期对象')
  for key in ['label','meaning','followUp','comparabilityWarning']:
   if key in pair and (not isinstance(pair[key],str) or not pair[key].strip()):raise ValueError('比较说明须为非空文字')
  a,b=pair['before'],pair['after'];ea=check_source(a,asof);eb=check_source(b,asof)
  va,vb=number(a['value']),number(b['value'])
  if b['period']<a['period']:raise ValueError('后期不得早于前期')
  if b['publishedAt']<a['publishedAt']:raise ValueError('后版本披露日不得早于前版本')
  differences=[{'field':k,'before':a[k],'after':b[k]} for k in BASE if a[k]!=b[k]]
  keys=set(required)|set(a.get('methods',{}))|set(b.get('methods',{}))
  missing=[k for k in sorted(keys) if a.get('methods',{}).get(k) in [None,''] or b.get('methods',{}).get(k) in [None,'']]
  differences += [{'field':k,'before':a['methods'].get(k),'after':b['methods'].get(k)} for k in sorted(keys) if k not in missing and a['methods'].get(k)!=b['methods'].get(k)]
  warnings=[r.get('comparabilityWarning') for r in [a,b] if r.get('comparabilityWarning')]
  blocked=bool(differences or missing or warnings)
  delta=None if blocked else str(vb-va)
  growth=None if blocked or va<=0 else str((vb-va)/va*100)
  status='blocked-method-difference' if differences else 'blocked-method-missing' if missing else 'blocked-comparability-warning' if warnings else 'same-period-revision' if a['period']==b['period'] else 'comparable-declared-basis'
  label=pair.get('label',b['field'])
  finding=(label+'：口径或可比性条件未通过，本次不计算跨期变化。' if blocked else label+'：在已声明口径下，'+a['period']+'至'+b['period']+'变化为'+format(number(delta),',.2f')+' '+b['unit']+'。'+('两份记录属于同一报告期，应解释为版本差异。' if status=='same-period-revision' else ''))
  result.append({'label':label,'identity':{k:b[k] for k in BASE},'methods':{'before':a.get('methods',{}),'after':b.get('methods',{})},'status':status,'beforePeriod':a['period'],'afterPeriod':b['period'],'beforeValue':str(va),'afterValue':str(vb),'delta':delta,'changePct':growth,'differences':differences,'missingMethods':missing,'comparabilityWarnings':warnings,'evidence':[ea,eb],'finding':finding,'meaning':pair.get('meaning','尚未提供经营意义，不能由数字变化自动推断原因。'),'followUp':pair.get('followUp','结合原文附注与经营资料进一步解释。'),'percentageBasis':'未计算：前期非正数' if not blocked and va<=0 else '已声明口径；不等同于报告披露可比同比'})
 return {'type':'cross-period-evidence-review','asOf':spec['asOf'],'rows':result,'requiredMethodKeys':required,'inputSha256':hashlib.sha256(json.dumps(spec,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),'methodSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'limitations':['原文哈希与页码检查只证明文件及定位完整性；不自动认证字段核验声明','相同口径名称不证明会计政策或合并范围实际一致，仍需原文核对','仅对指定比较对计算，不生成价格预测或投资指令']}
def markdown(r):
 lines=['# 跨期研究：先核对口径，再解释变化','', '资料截止日：'+r['asOf']+'。原文文件与页码范围已检查；字段原文核验状态另列。','']
 for i,row in enumerate(r['rows'],1):
  lines+=['## '+row['label'],row['finding'],'研究意义：'+row['meaning'],'后续核对：'+row['followUp']]
  lines+=['','|报告期|数值（'+row['identity']['unit']+'）|原文位置|','|---|---|---|']
  for key,e in zip(['before','after'],row['evidence']):
   location='[PDF第'+str(e['page'])+'页]('+e['exportedPath']+'#page='+str(e['page'])+')' if e.get('exportedPath') else 'PDF第'+str(e['page'])+'页'
   lines.append('|'+row[key+'Period']+'|'+format(number(row[key+'Value']),',.2f')+'|'+location+'|')
  lines.append('')
  if row['delta'] is not None:lines.append('变化金额／数值：'+format(number(row['delta']),',.2f')+'；相对变化：'+(format(number(row['changePct']),'.2f')+'%' if row['changePct'] is not None else '前期为零或负数，不输出百分比')+'。相对变化按所给金额计算，尚需核对报告披露的可比同比口径。')
  for d in row['differences']:lines.append('口径差异：'+LABELS.get(d['field'],d['field'])+'，'+str(d['before'])+' → '+str(d['after'])+'。')
  if row['missingMethods']:lines.append('缺少口径：'+'、'.join(LABELS.get(k,k) for k in row['missingMethods'])+'。')
  lines+=row['comparabilityWarnings']
  for label,e in zip(['前期','后期'],row['evidence']):
   location='[查看原文]('+e['exportedPath']+'#page='+str(e['page'])+')' if e.get('exportedPath') else e['path']
   lines.append(label+'原文：'+location+'，PDF第'+str(e['page'])+'页；哈希 '+e['sha256']+'；字段核验声明：'+VERIFICATION.get(e['fieldVerification'],'其他核验声明（需核对记录）')+'。')
 lines+=['','## 研究范围',*r['limitations']]
 return '\n'.join(lines)
def export(spec,out):
 r=review(spec);out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在，使用新目录')
 # Copy and link only the files explicitly supplied; copies confer no distribution rights.
 import shutil
 from research_brief_html import render
 out.mkdir(parents=True);(out/'sources').mkdir()
 for row in r['rows']:
  for e in row['evidence']:
   target=out/'sources'/(e['sha256']+'.pdf')
   if not target.exists():shutil.copy2(e['path'],target)
   if hashlib.sha256(target.read_bytes()).hexdigest()!=e['sha256']:raise ValueError('原文副本哈希变化')
   e['exportedPath']='sources/'+target.name
 md=markdown(r);html=render(md,title='跨期口径与证据研究')
 frozen=load_json(json.dumps(spec,allow_nan=False))
 for pair in frozen['pairs']:
  for key in ['before','after']:
   source=pair[key]['source'];source['path']='sources/'+source['sha256']+'.pdf'
 (out/'input.json').write_text(json.dumps(frozen,ensure_ascii=False,indent=2),'utf-8')
 (out/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),'utf-8')
 (out/'跨期研究.md').write_text(md,'utf-8');(out/'跨期研究.html').write_text(html,'utf-8')
 files=[p for p in out.rglob('*') if p.is_file()]
 manifest={'type':'cross-period-replay-manifest','files':{p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'methodSha256':r['methodSha256'],'rendererSha256':hashlib.sha256(Path(__file__).with_name('research_brief_html.py').read_bytes()).hexdigest(),'resultProjectionSha256':projection_hash(r),'limitation':'本地哈希清单非签名，不能防止恶意同时修改文件与清单；原文副本不授予再分发权'}
 (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
 return r
def projection_hash(r):
 rows=[]
 for row in r['rows']:
  rows.append({**{k:v for k,v in row.items() if k!='evidence'},'evidence':[{'sha256':e['sha256'],'page':e['page'],'fieldVerification':e['fieldVerification']} for e in row['evidence']]})
 return hashlib.sha256(json.dumps({'asOf':r['asOf'],'rows':rows,'requiredMethodKeys':r['requiredMethodKeys']},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def replay(folder):
 folder=Path(folder).resolve();manifest=load_json((folder/'manifest.json').read_text('utf-8'))
 if manifest['methodSha256']!=hashlib.sha256(Path(__file__).read_bytes()).hexdigest() or manifest['rendererSha256']!=hashlib.sha256(Path(__file__).with_name('research_brief_html.py').read_bytes()).hexdigest():raise ValueError('方法或报告版式版本已变化，需重新核验')
 for rel,expected in manifest['files'].items():
  p=(folder/rel).resolve()
  if not p.is_relative_to(folder):raise ValueError('快照引用越出目录')
  if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('快照文件缺失或变化:'+rel)
 spec=load_json((folder/'input.json').read_text('utf-8'))
 for pair in spec['pairs']:
  for key in ['before','after']:
   p=(folder/pair[key]['source']['path']).resolve()
   if not p.is_relative_to(folder):raise ValueError('来源引用越出目录')
   pair[key]['source']['path']=str(p)
 r=review(spec)
 if projection_hash(r)!=manifest['resultProjectionSha256']:raise ValueError('冻结输入重算结果不同')
 return {'status':'replayed-identical-declared-results','pairs':len(r['rows']),'limitations':r['limitations']}
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path);p.add_argument('--replay',action='store_true');a=p.parse_args()
 if a.replay:print(json.dumps(replay(a.input),ensure_ascii=False))
 elif a.out_dir:export(load_json(a.input.read_text('utf-8-sig')),a.out_dir)
 else:p.error('生成报告需要--out-dir；重放目录使用--replay')
