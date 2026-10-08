"""Per-claim checks; numeric agreement and original quotations are not causal proof."""
import argparse,json,hashlib,math,re
from pathlib import Path
from fund_series_tools import day,source
from research_brief_html import render,safe_url
from collection_validation import unique_pairs,reject_constant

def finite(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def pointer(obj,path):
 if not isinstance(path,str) or not path.startswith('/'):raise ValueError('需JSON Pointer')
 for segment in path[1:].split('/'):
  if re.search(r'~(?![01])',segment):raise ValueError('JSON Pointer转义无效')
  key=segment.replace('~1','/').replace('~0','~')
  if isinstance(obj,list):
   if not re.fullmatch(r'0|[1-9][0-9]*',key) or int(key)>=len(obj):raise ValueError('JSON Pointer数组索引无效')
   obj=obj[int(key)]
  elif isinstance(obj,dict):obj=obj[key]
  else:raise ValueError('JSON Pointer不能继续定位标量')
 return obj

def verify(spec):
 if not isinstance(spec,dict):raise ValueError('事实核验输入须为对象')
 day(spec.get('asOf'));claims=spec.get('claims')
 if not isinstance(claims,list) or not 1<=len(claims)<=200:raise ValueError('需1至200条主张')
 ids=set();rows=[]
 for c in claims:
  if not isinstance(c,dict) or not isinstance(c.get('id'),str) or not c['id'].strip() or c['id'] in ids or not isinstance(c.get('text'),str) or not c['text'].strip() or c.get('kind') not in ('numeric','quotation','ranking','causal'):raise ValueError('主张编号、类型或正文无效')
  if not isinstance(c.get('evidence',[]),list) or any(not isinstance(e,dict) for e in c.get('evidence',[])):raise ValueError('证据须为对象数组')
  ids.add(c['id']);row=dict(id=c['id'],text=c['text'],kind=c['kind'],status='insufficient',reason='尚未取得可用于该主张的证据',evidence=[])
  for e in c.get('evidence',[]):
   record=dict(e)
   try:
    day(e['publishedAt']);source(e['sourceUrl'])
    if e['publishedAt']>spec['asOf']:raise ValueError('证据披露晚于截止日')
    raw=Path(e['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=e['sha256']:raise ValueError('证据文件摘要不一致')
    if c['kind']=='numeric':
     if c.get('scope')!=e.get('scope') or not c.get('scope'):raise ValueError('对象、指标、期间及单位口径须一致且明确')
     required=('entity','metric','period','unit')
     if any(not c['scope'].get(k) for k in required):raise ValueError('口径字段缺失')
     value=pointer(json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant),e['pointer']);digits=c.get('decimalPlaces',2)
     if type(digits)!=int or not 0<=digits<=8 or not finite(value) or not finite(c.get('value')):raise ValueError('数值或精度无效')
     record['observedValue']=value;record['comparisonMatches']=round(value,digits)==round(c['value'],digits)
    elif c['kind']=='quotation':
     if not c.get('quote'):raise ValueError('需明确待核对原文引句')
     page=e.get('page')
     if Path(e['path']).suffix.lower()=='.pdf':
      if type(page)!=int or page<1:raise ValueError('需PDF页码')
      import pdfplumber
      with pdfplumber.open(e['path']) as doc:text=doc.pages[page-1].extract_text() or ''
     else:text=raw.decode('utf-8-sig')
     compact=lambda s:''.join(s.split())
     record['quoteLocated']=compact(c['quote']) in compact(text)
    record['fileChecked']=True
   except Exception as exc:record.update(fileChecked=False,error=str(exc))
   row['evidence'].append(record)
  valid=[e for e in row['evidence'] if e.get('fileChecked')]
  if c['kind']=='numeric' and valid:
   matches={e['comparisonMatches'] for e in valid}
   row.update(status='conflict' if len(matches)>1 else 'supported' if True in matches else 'inconsistent',reason='同口径证据数值存在分歧' if len(matches)>1 else '按指定小数位数复算一致' if True in matches else '按指定小数位数与证据不一致')
  elif c['kind']=='quotation' and valid:
   located={e['quoteLocated'] for e in valid}
   row.update(status='supported' if True in located else 'insufficient',reason='原文引句已定位；不自动验证主张的语义扩展或因果关系' if True in located else '指定证据位置未找到引句，不能据此判定引句为假')
  elif c['kind']=='ranking':row['reason']='完整样本池、分类、去重及共同区间尚未独立复核；报道存在不等于排名已核验'
  elif c['kind']=='causal':row['reason']='原文陈述或相关性不能证明因果贡献；需识别方法、对照及交易归因证据'
  rows.append(row)
 return dict(asOf=spec['asOf'],claims=rows,limitations=['AI先拆解用户自然语言为主张并准备证据，不要求用户写JSON','文件摘要与数值相符不证明资料来源真实或无历史修订','quotation仅核对明确引句，不能扩展为整段语义真伪','缺证据不等于主张错误；不生成准确率或投资结论'])
def markdown(r):
 labels={'supported':'有证据支持','inconsistent':'与证据不一致','conflict':'证据存在分歧','insufficient':'证据不足'}
 lines=['# 逐条事实核验','', '资料截止日'+r['asOf']+'。数字、引句、排名与因果判断分别核对。']
 for c in r['claims']:
  lines+=['','## '+c['id']+'：'+labels[c['status']],c['text'],c['reason']]
  for e in c['evidence']:
   url=e.get('sourceUrl');link='[证据来源]('+url+')' if isinstance(url,str) and safe_url(url) and not any(c in url for c in '()\r\n') else '证据来源：'+str(url or '未提供')
   lines.append(link+'；披露日'+str(e.get('publishedAt','未提供'))+'；定位'+str(e.get('pointer') or e.get('page') or '未指定')+'；文件摘要'+str(e.get('sha256','未提供')))
   if e.get('error'):lines.append('核对失败：'+e['error'])
   if 'observedValue' in e:lines.append('证据数值：'+str(e['observedValue']))
 lines+=['','## 核验边界',*r['limitations']];return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=verify(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant));text=markdown(r);a.out.parent.mkdir(parents=True,exist_ok=True)
 a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8');a.out.with_suffix('.md').write_text(text,encoding='utf8');a.out.with_suffix('.html').write_text(render(text,title='逐条事实核验'),encoding='utf8')
