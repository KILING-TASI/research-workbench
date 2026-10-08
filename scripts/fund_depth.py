"""Public report manager passages, disclosed category movement and attribution inputs."""
import argparse,hashlib,re,copy,math
from pathlib import Path
from research_library import read,dump,day,url,number,brinson,NOTICE

def manager(s):
 import pdfplumber
 if not isinstance(s,dict) or any(not isinstance(s.get(k),str) or not s[k].strip() for k in ['pdf','sha256','identityText','code']):raise ValueError('观点提取须明确文件、摘要与主体身份文本')
 p=Path(s['pdf']);digest=hashlib.sha256(p.read_bytes()).hexdigest()
 if digest!=s['sha256']:raise ValueError('PDF哈希不符')
 url(s['sourceUrl'])
 if day(s['reportDate'])>day(s['publishedAt']) or day(s['publishedAt'])>day(s['asOf']):raise ValueError('报告日期冲突')
 if not s['reportDate'].endswith('-12-31'):raise ValueError('经理观点入口仅解析年报，非年报请保留对应资料范围')
 items=[];active=None;identity=False;excluded=[]
 identity_text=re.sub(r'\s+','',s['identityText'])
 with pdfplumber.open(p) as doc:
  if len(doc.pages)>300:raise ValueError('报告过长，限制300页')
  annual_title=s['reportDate'][:4]+'年年度报告'
  front=''.join(re.sub(r'\s+','',page.extract_text() or '') for page in doc.pages[:5])
  if annual_title not in front:raise ValueError('原文未匹配指定年度报告标题，不能仅凭输入日期认定年报')
  for n,page in enumerate(doc.pages,1):
   text=page.extract_text() or ''
   if n<=5 and re.sub(r'\s+','',s['identityText']) in re.sub(r'\s+','',text):identity=True
   for line in text.splitlines():
    if re.sub(r'\s+','',line)==identity_text:
     excluded.append({'page':n,'text':line,'reason':'exact-report-identity-header'});continue
    # Number must be followed by a manager-report heading; avoid stock prices and contents.
    m=re.match(r'^\s*(\d+\.\d+)\s*(管理人对|基金管理人对)',line)
    if m and not re.search(r'\.{3,}|…{2,}',line):
     if m.group(1) in ['4.4','4.5']:
      active={'section':m.group(1),'kind':'review' if m.group(1)=='4.4' else 'outlook','heading':line,'passages':[]};items.append(active)
     else:active=None
     continue
    if active and re.match(r'^\s*(4\.[6-9]|[5-9]\.\d+)\s',line):active=None
    if active and line.strip() and not re.match(r'^第\s*\d+\s*页',line):
     if active['passages'] and active['passages'][-1]['page']==n:active['passages'][-1]['text']+='\n'+line
     else:active['passages'].append({'page':n,'text':line})
 if not identity:raise ValueError('报告主体未匹配')
 items=[item for item in items if item['passages']]
 return {'type':'manager-public-passages','code':s['code'],'asOf':s['asOf'],'reportDate':s['reportDate'],'publishedAt':s['publishedAt'],'sourceUrl':s['sourceUrl'],'sha256':digest,'sections':items,'excludedLines':excluded,'status':'extracted-needs-context-review' if items else 'not-found','riskNotice':NOTICE,'limitations':['保留管理人原文，区分报告回顾与展望；不把管理人自述当客观已证实事实','仅已提供PDF原文，不覆盖所有采访路演；编号布局不匹配时返回未找到','不从展望推断交易指令或未来收益；跨页页眉可能需人工排除']}

def changes(s):
 reports=s['reports'];cutoff=day(s['asOf'])
 if len(reports)<2:raise ValueError('至少两期分类快照')
 out=[];prepared=[];previous=''
 for r in reports:
  if r['code']!=s['code'] or day(r['publishedAt'])>cutoff or day(r['reportDate'])>day(r['publishedAt']):raise ValueError('主体或日期冲突')
  if r['reportDate']<=previous:raise ValueError('报告期须递增唯一')
  previous=r['reportDate'];url(r['sourceUrl'])
  if r.get('weightBasis')!='equity' or not r.get('taxonomy') or not r.get('taxonomyVersion'):raise ValueError('需股票内部权重及分类版本')
  weights={}
  for x in r['categories']:
   if x['name'] in weights:raise ValueError('类别重复')
   weights[x['name']]=number(x['weight'],'分类权重',0)
  if abs(sum(weights.values())-1)>1e-6:raise ValueError('分类包括未知项须合计1，不归一化删掉未知')
  prepared.append((r,weights))
 for (a,wa),(b,wb) in zip(prepared,prepared[1:]):
  verified=a.get('taxonomyVerified') is True and b.get('taxonomyVerified') is True and a['taxonomy']==b['taxonomy'] and a['taxonomyVersion']==b['taxonomyVersion']
  rows=[{'category':k,'beforePct':wa.get(k,0)*100,'afterPct':wb.get(k,0)*100,'changePp':(wb.get(k,0)-wa.get(k,0))*100 if verified else None} for k in sorted(wa.keys()|wb.keys())]
  unknown=any(k in ['未知','未分类'] and wa.get(k,0)+wb.get(k,0)>1e-12 for k in wa.keys()|wb.keys())
  out.append({'startReport':a['reportDate'],'endReport':b['reportDate'],'rows':rows,'verifiedComparable':verified,'totalVariationPct':sum(abs(x['changePp']) for x in rows)/2 if verified and not unknown else None,'sources':[a['sourceUrl'],b['sourceUrl']],'status':'可比分类分布变化' if verified and not unknown else '仅列原文类别差异，分类版本或未知覆盖未满足'})
 return {'type':'disclosed-category-change','code':s['code'],'asOf':s['asOf'],'pairs':out,'riskNotice':NOTICE,'limitations':['总变差为分类权重绝对变化之和的一半，不是实际换手率或交易量','行业变化不等于价值成长风格变化；仅在输入真正风格分类时解释为风格分布变化','权重变化可能来自价格和申赎，不认定主动调仓；未核验分类或未知项不评分']}

def attribution(s):
 if not isinstance(s,dict) or not isinstance(s.get('base'),dict) or any(not isinstance(s.get(k),list) for k in ['weights','returns']):raise ValueError('归因基础参数、权重及收益列表结构无效')
 base=copy.deepcopy(s['base']);weights=s['weights']
 if any(not isinstance(x,dict) or not isinstance(x.get('industry'),str) or not x['industry'].strip() for x in weights+s['returns']):raise ValueError('行业权重及收益条目须有明确行业名称')
 if len({x['industry'] for x in weights})!=len(weights):raise ValueError('行业权重重复')
 returns={x['industry']:x for x in s['returns']}
 if len(returns)!=len(s['returns']):raise ValueError('行业收益重复')
 extra=set(returns)-{x['industry'] for x in weights}
 if extra:raise ValueError('行业收益包含未匹配权重的行业：'+','.join(sorted(extra)))
 version=base.get('industryVersion')
 if not isinstance(version,str) or not version.strip() or any(not isinstance(x.get('industryVersion'),str) or not x['industryVersion'].strip() for x in weights+s['returns']):
  return {'type':'industry-attribution-gap','code':s['code'],'asOf':base['asOf'],'missingInputs':['行业分类版本（基础参数、权重及行业收益均须提供）'],'missingIndustries':[x['industry'] for x in weights if x['industry'] not in returns],'riskNotice':NOTICE,'limitations':['分类版本未明确，不输出归因；数据缺口不填零']}
 if any(x['industryVersion']!=version for x in weights+s['returns']):raise ValueError('行业分类版本冲突，不能组装归因')
 if len(returns)!=len(s['returns']):raise ValueError('行业收益重复')
 sectors=[];missing=[]
 for w in weights:
  r=returns.get(w['industry'])
  if not r:missing.append(w['industry']);continue
  if r.get('start')!=base['start'] or r.get('end')!=base['end'] or r.get('industrySystem')!=base['industrySystem']:raise ValueError('行业收益区间或分类冲突')
  url(w['sourceUrl']);url(r['sourceUrl'])
  sectors.append({**w,'portfolioReturnPct':r['portfolioReturnPct'],'benchmarkReturnPct':r['benchmarkReturnPct'],'sourceUrl':r['sourceUrl'],'weightSourceUrl':w['sourceUrl']})
 if missing:return {'type':'industry-attribution-gap','code':s['code'],'asOf':base['asOf'],'missingIndustries':missing,'riskNotice':NOTICE,'limitations':['缺少行业收益，不输出归因，不填零']}
 base['sectors']=sectors;r=brinson(base);r.update(code=s['code'],asOf=base['asOf'],industrySystem=base['industrySystem'],industryVersion=version);return r

COMMANDS={'manager':manager,'changes':changes,'attribution':attribution}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=COMMANDS);p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();dump(a.out,COMMANDS[a.command](read(a.input)))
