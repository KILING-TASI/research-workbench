"""Join report equities to original SW records, retaining historical ambiguity."""
import argparse,json,hashlib
from pathlib import Path
from report_screen_bridge import candidate
from sw_classification_archive import parse as parse_stocks
from sw_codebook_archive import parse as parse_names
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant

def run(s):
 if not isinstance(s,dict) or any(not isinstance(s.get(k),dict) for k in ['report','stockArchive','codebook']):raise ValueError('行业记录输入及三个资料对象须完整')
 report=s['report'];c=candidate(report,s['asOf'])
 for key in ['stockArchive','codebook']:
  item=s[key];raw=Path(item['path']).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('行业原表副本摘要不一致')
 stocks=parse_stocks(s['stockArchive']['path'],s['asOf']);names=parse_names(s['codebook']['path']);
 if stocks['sourceSha256']!=s['stockArchive']['sha256'] or names['sourceSha256']!=s['codebook']['sha256']:raise ValueError('行业原表解析时文件摘要变化')
 book={x['code']:x for x in names['entries']};index={}
 for x in stocks['rows']:index.setdefault(x['code'],[]).append(x)
 result=[]
 for x in c['holdings']['value']:
  records=[];later=[]
  if x['market']=='CN-equity':
   for item in index.get(x['code'],[]):
    if item['includedAt']>report['reportDate']:later.append(item);continue
    name=book.get(item['industryCode'])
    records.append(dict(item,nameInSW2021Codebook=name['name'] if name else None,nameLocator=name['locators'] if name else None,nameStatus='代码表新版列匹配；不证明原分类使用该版本' if name else '新版代码表未匹配'))
  result.append(dict(x,classificationRecords=records,recordsAfterReportDate=later,status='不在境内分类覆盖范围，未套用代码匹配' if x['market']!='CN-equity' else '历史分类记录待有效期核验' if records else '本次原表未匹配；不认定无行业暴露',confirmedIndustry=None))
 return dict(type='holding-industry-records',code=c['code'],reportDate=report['reportDate'],asOf=s['asOf'],rows=result,reportSource=c['holdings']['sourceUrl'],reportSha256=c['holdings']['sourceSha256'],stockArchiveSource=stocks['sourceUrl'],codebookSource=names['sourceUrl'],stockArchiveSha256=stocks['sourceSha256'],codebookSha256=names['sourceSha256'],industryWeights=None,limitations=['行业原表更新日不是披露日，当前资料不是事前冻结输入','同股票多行未自动裁决，行业名称只按新版代码表匹配，不证明历史版本','不生成行业权重或主题标签；港美股不使用境内代码映射','基金股票来自已核验披露快照，不代表当前持仓'])

def markdown(r):
 lines=['# 基金股票行业记录核对','',r['code']+'；报告日'+r['reportDate']+'。','本次展示原表匹配线索，尚未核验唯一有效分类，不生成行业权重。','','| 股票 | 市场代码 | 原表记录数 | 状态 |','| --- | --- | ---: | --- |']
 for x in r['rows']:lines.append('| '+x['name'].replace('|','／')+' | '+x['market']+' '+x['code']+' | '+str(len(x['classificationRecords']))+' | '+x['status']+' |')
 for x in r['rows']:
  if not x['classificationRecords']:continue
  lines+=['','## '+x['code']+' '+x['name']]
  for v in x['classificationRecords']:lines.append('- 行业代码'+v['industryCode']+'；新版名称'+(v['nameInSW2021Codebook'] or '未匹配')+'；计入日'+v['includedAt']+'；更新日'+v['updatedAt']+'；原表第'+str(v['locator']['row'])+'行。'+v['nameStatus'])
 lines+=['','## 原始来源','[基金报告]('+r['reportSource']+')；摘要：'+r['reportSha256'],'[股票行业原表]('+r['stockArchiveSource']+')；摘要：'+r['stockArchiveSha256'],'[新版行业代码表]('+r['codebookSource']+')；摘要：'+r['codebookSha256']]
 lines+=['','## 使用边界']+['- '+x for x in r['limitations']]
 return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=run(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant));t=markdown(r);html=render(t);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');a.out.with_suffix('.md').write_text(t,encoding='utf-8');a.out.with_suffix('.html').write_text(html,encoding='utf-8')
