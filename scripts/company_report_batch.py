"""On-demand CNInfo report coverage, archival and page-level public evidence."""
import argparse,datetime as dt,gzip,hashlib,json,re,io,time,math
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,urlparse
from research_brief_html import render
from fund_series_tools import day
from collection_validation import unique_pairs,reject_constant

def request(url,data=None):
 req=Request(url,data=urlencode(data).encode() if data else None,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'})
 for attempt in range(3):
  try:
   with urlopen(req,timeout=35) as response:raw=response.read(64*1024*1024+1)
   break
  except HTTPError as exc:
   if exc.code not in (408,500,502,503,504) or attempt==2:raise
   time.sleep(2 ** attempt)
  except (URLError,TimeoutError):
   if attempt==2:raise
   time.sleep(2 ** attempt)
 if len(raw)>64*1024*1024:raise ValueError('响应超过64MB限制')
 if raw[:2]==b'\x1f\x8b':
  with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:raw=compressed.read(64*1024*1024+1)
  if len(raw)>64*1024*1024:raise ValueError('解压响应超过64MB限制')
 return raw

def report_title(period):
 year=period[:4];tail=period[5:]
 if tail=='06-30':return year+'年半年度报告','category_bndbg_szsh'
 if tail=='12-31':return year+'年年度报告','category_ndbg_szsh'
 if tail=='03-31':return year+'年第一季度报告','category_yjdbg_szsh'
 if tail=='09-30':return year+'年第三季度报告','category_sjdbg_szsh'
 raise ValueError('报告期需自然年季度末')

def report_title_variants(period):
 target,_=report_title(period);titles=[target,target.replace(period[:4]+'年',period[:4],1)]
 if period.endswith('03-31'):titles.extend([period[:4]+'年一季度报告',period[:4]+'一季度报告'])
 if period.endswith('09-30'):titles.extend([period[:4]+'年三季度报告',period[:4]+'三季度报告'])
 return list(dict.fromkeys(titles))

def candidates(items,code,period,asof):
 day(period);day(asof)
 if not isinstance(items,list) or any(not isinstance(item,dict) for item in items):raise ValueError('公告候选须为对象列表')
 results=[];titles=report_title_variants(period);seen={}
 for item in items:
  if item.get('secCode')!=code:continue
  title=re.sub('<[^>]+>','',item.get('announcementTitle',''));normalized=re.sub(r'\s+','',title)
  if not any(title in normalized for title in titles) or re.search('摘要|英文|取消|作废',normalized):continue
  stamp=item.get('announcementTime')
  if isinstance(stamp,bool) or not isinstance(stamp,(int,float)) or not math.isfinite(stamp):raise ValueError('公告时间戳无效')
  published=dt.datetime.fromtimestamp(stamp/1000,dt.timezone(dt.timedelta(hours=8))).date().isoformat()
  if not period<=published<=asof:continue
  path=item.get('adjunctUrl','')
  if not re.fullmatch(r'finalpage/\d{4}-\d{2}-\d{2}/[\w.-]+\.[pP][dD][fF]',path):raise ValueError('附件路径不符合公开PDF格式')
  candidate=dict(code=code,name=re.sub('<[^>]+>','',item.get('secName','')),id=item['announcementId'],title=title,publishedAt=published,url='https://static.cninfo.com.cn/'+path)
  token=str(candidate['id'])
  if token in seen:
   if seen[token]!=candidate:raise ValueError('同公告编号元数据冲突，不能任取版本')
   continue
  seen[token]=candidate;results.append(candidate)
 return results

def report_identity_confirmed(report,code):
 text='\n'.join(p['text'] for p in report['pages'][:12])
 front=re.sub(r'\s+','',text)
 return any(title in front for title in report_title_variants(report['period'])) and bool(re.search(r'(?<!\d)'+re.escape(code)+r'(?!\d)',text))

KEYWORDS={'需求订单':'订单|需求|客户','价格盈利':'价格|毛利率|盈利','库存回款':'存货|库存|应收账款','产能供给':'产能|资本开支|募投|供应链','风险':'风险|不确定性'}
def parse_pdf(path,code,period):
 import pdfplumber
 pages=[]
 with pdfplumber.open(path) as doc:
  if len(doc.pages)>800:raise ValueError('PDF超过800页上限')
  for number,p in enumerate(doc.pages,1):pages.append(dict(page=number,text=p.extract_text() or ''))
 if not report_identity_confirmed(dict(pages=pages,period=period),code):raise ValueError('报告前12页未确认证券代码与所属期标题')
 if sum(len(p['text']) for p in pages)<100:raise ValueError('扫描件或文本提取不足，需人工复核')
 evidence={}
 for label,pattern in KEYWORDS.items():
  matches=[]
  for p in pages:
   for line in p['text'].splitlines():
    line=re.sub(r'\s+',' ',line).strip()
    if re.search(pattern,line) and len(line)>=12 and not re.search(r'\.{4}|…{3}',line):
     matches.append(dict(page=p['page'],quote=line[:180],status='原文关键词线索，未确认因果'))
     if len(matches)>=3:break
   if len(matches)>=3:break
  evidence[label]=matches
 scope=[]
 for p in pages:
  if re.search('合并利润表|合并资产负债表|合并现金流量表',re.sub(r'\s+','',p['text'])):scope.append(dict(page=p['page'],kind='合并报表标题'))
  if '单位：元' in p['text'] or '单位:元' in p['text']:scope.append(dict(page=p['page'],kind='金额单位元文字线索'))
 return dict(parser='pdfplumber',pages=pages,evidence=evidence,scopeEvidence=scope,identityStatus='证券代码与报告期标题匹配，数值尚未逐行核验')

def collect_one(code,period,asof,out,fetch=request,selected_id=None,uploaded=None,source_document=None):
 out=Path(out);out.mkdir(parents=True,exist_ok=False);result=dict(code=code,period=period,asOf=asof,catalogStatus='not-attempted',disclosureStatus='unknown',downloadStatus='not-attempted',parseStatus='not-attempted',numericVerification='not-attempted',sources=[],candidates=[],error=None)
 try:
  if sum(bool(x) for x in [uploaded,source_document,selected_id])>1:raise ValueError('上传、明确原文与目录版本选择不能同时给出')
  if uploaded:
   path=Path(uploaded)
   if path.stat().st_size>64*1024*1024:raise ValueError('上传PDF超过64MB限制')
   raw=path.read_bytes();result['sourceType']='user-upload';result['disclosureStatus']='user-provided-unverified';result['sources'].append(dict(fileName=path.name))
  elif source_document:
   meta=dict(source_document);date=meta['publishedAt'];dt.date.fromisoformat(date)
   if not period<=date<=asof:raise ValueError('明确原文披露日期不在研究范围')
   if meta.get('code')!=code or not re.fullmatch(r'\d+',str(meta.get('id',''))):raise ValueError('明确原文代码或公告ID无效')
   expected='https://static.cninfo.com.cn/finalpage/'+date+'/'+str(meta['id'])+'.PDF'
   if meta.get('url')!=expected or not meta.get('title'):raise ValueError('明确原文需匹配巨潮日期、ID与完整PDF网址')
   result['metadata']=meta;result['disclosureStatus']='explicit-source-unverified';result['sourceType']='cninfo-explicit-url';result['sources'].append(dict(url=expected,metadataVerification='input-declared'));raw=fetch(expected)
  else:
   _,category=report_title(period);items=[]
   for page in range(1,21):
    params=dict(pageNum=page,pageSize=30,column='sse' if code.startswith('6') else 'szse',tabName='fulltext',searchkey=code,seDate=period+'~'+asof,category=category,sortName='time',sortType='desc',isHLtitle='false')
    url='https://www.cninfo.com.cn/new/hisAnnouncement/query';raw=fetch(url,params);(out/f'catalog-{page}.json').write_bytes(raw);result['sources'].append(dict(url=url,request=params,sha256=hashlib.sha256(raw).hexdigest()));payload=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant)
    if not isinstance(payload.get('announcements'),list):raise ValueError('目录结构或内容无效')
    items.extend(payload['announcements'])
    if payload.get('hasMore') is False:break
   else:raise ValueError('目录超过600条，不能认定覆盖完整')
   result['catalogStatus']='retrieved';matched=candidates(items,code,period,asof)
   # Some catalog responses return only the latest year's report for wide ranges.
   # Requery the historical publication year without treating misses as nonpublication.
   narrow_end=min(asof,str(int(period[:4])+1)+('-06-30' if period.endswith('12-31') else '-03-31'))
   if not matched and narrow_end<asof:
    for page in range(1,21):
     params=dict(pageNum=page,pageSize=30,column='sse' if code.startswith('6') else 'szse',tabName='fulltext',searchkey=code,seDate=period+'~'+narrow_end,category=category,sortName='time',sortType='desc',isHLtitle='false')
     raw=fetch(url,params);(out/f'catalog-historical-{page}.json').write_bytes(raw);result['sources'].append(dict(url=url,request=params,sha256=hashlib.sha256(raw).hexdigest(),purpose='historical-window-recheck'));payload=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant)
     if not isinstance(payload.get('announcements'),list):raise ValueError('历史窗口目录结构或内容无效')
     items.extend(payload['announcements'])
     if payload.get('hasMore') is False:break
    else:raise ValueError('历史窗口目录超过600条，不能认定覆盖完整')
    matched=candidates(items,code,period,asof)
   result['candidates']=matched
   if not matched:
    result['disclosureStatus']='not-found';return result
   result['disclosureStatus']='published';chosen=[x for x in matched if x['id']==selected_id] if selected_id else matched
   if len(chosen)!=1:result['downloadStatus']='conflict';result['error']='多个版本或选定ID不匹配，需明确版本';return result
   meta=chosen[0];result['metadata']=meta;raw=fetch(meta['url']);result['sources'].append(dict(url=meta['url']));result['sourceType']='cninfo-public'
  if len(raw)>64*1024*1024:raise ValueError('报告PDF超过64MB限制')
  if not raw.startswith(b'%PDF'):
   result['rejectedResponse']=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),reason='PDF文件头缺失；不保存为报告PDF，不进入原文解析成功状态')
   raise ValueError('下载或上传内容不是PDF')
  path=out/'report.pdf';path.write_bytes(raw);result['fileSha256']=hashlib.sha256(raw).hexdigest();result['downloadStatus']='downloaded'
  parsed=parse_pdf(path,code,period);result.update(parsed);result['parseStatus']='parsed'
 except Exception as exc:
  result['error']=str(exc)
  if result['downloadStatus']=='downloaded':result['parseStatus']='failed'
  elif result['catalogStatus']=='not-attempted' and not uploaded and not source_document:result['catalogStatus']='failed'
  else:result['downloadStatus']='failed'
 finally:
  (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 return result

def reusable_report(prior,prior_root,code,period,asof):
 if prior.get('code')!=code or prior.get('period')!=period or prior.get('asOf')!=asof:raise ValueError('缓存报告身份或截止日不一致')
 if prior.get('parseStatus')!='parsed' or prior.get('downloadStatus')!='downloaded':return None
 path=Path(prior_root)/code/'report.pdf'
 if not path.is_file():raise ValueError('缓存PDF缺失')
 if hashlib.sha256(path.read_bytes()).hexdigest()!=prior.get('fileSha256'):raise ValueError('缓存PDF哈希变化')
 parsed=parse_pdf(path,code,period)
 if any(prior.get(k)!=v for k,v in parsed.items()):raise ValueError('缓存解析内容或方法变化')
 return dict(prior,reuseStatus='local-pdf-and-pages-reverified; remote-revisions-not-checked')

def acquisition_summary(rows):
 reused=[r['code'] for r in rows if r.get('reuseStatus','').startswith('local-pdf-and-pages-reverified;')]
 return dict(reusedCodes=reused,acquisitionAttemptedCodes=[r['code'] for r in rows if r['code'] not in reused],remoteRevisionCheckPendingCodes=reused)

def acquisition_lines(summary):
 lines=[]
 if summary.get('reusedCodes'):lines.append('复用已保存原文：'+ '、'.join(summary['reusedCodes'])+'。文件哈希、报告身份及解析文字已重新核对。')
 if summary.get('acquisitionAttemptedCodes'):lines.append('本次尝试重新获取原文：'+'、'.join(summary['acquisitionAttemptedCodes'])+'。获取是否成功以覆盖清单为准。')
 if summary.get('remoteRevisionCheckPendingCodes'):lines.append('未重新检查远程更正公告：'+'、'.join(summary['remoteRevisionCheckPendingCodes'])+'。本地复用不代表公告版本已更新。')
 return lines

def run(spec,out,fetch=request):
 if not isinstance(spec,dict) or not isinstance(spec.get('companies'),list) or any(not isinstance(c,dict) or not isinstance(c.get('code'),str) for c in spec['companies']):raise ValueError('公司批量输入须为对象及代码列表')
 period=spec['period'];asof=spec['asOf'];day(period);day(asof);report_title(period)
 if period>asof:raise ValueError('报告期超过截止日')
 codes=[x['code'] for x in spec['companies']]
 if not 1<=len(codes)<=30 or len(set(codes))!=len(codes) or any(not re.fullmatch(r'\d{6}',x) for x in codes):raise ValueError('需1至30个不重复六位代码')
 prior_rows={};prior_root=None
 if spec.get('resumeFrom'):
  prior_path=Path(spec['resumeFrom']);prior_data=json.loads(prior_path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant);prior_root=prior_path.parent
  if prior_data.get('period')!=period or prior_data.get('asOf')!=asof:raise ValueError('续采报告期或截止日不一致，需新建研究批次')
  prior_codes=[r['code'] for r in prior_data['companies']]
  if len(prior_codes)!=len(set(prior_codes)) or set(prior_codes)!=set(codes):raise ValueError('续采公司集合不一致，不能遗漏或增加样本')
  prior_rows={r['code']:r for r in prior_data['companies']}
 out=Path(out);out.mkdir(parents=True,exist_ok=False);rows=[]
 for c in spec['companies']:
  reused=None;cache_error=None
  if prior_root and not any(c.get(k) for k in ['selectedId','uploadedPdf','sourceDocument']):
   try:reused=reusable_report(prior_rows[c['code']],prior_root,c['code'],period,asof)
   except Exception as exc:cache_error=str(exc)
  if reused:
   import shutil
   shutil.copytree(prior_root/c['code'],out/c['code']);(out/c['code']/'result.json').write_text(json.dumps(reused,ensure_ascii=False,indent=2),encoding='utf8');rows.append(reused)
  else:
   row=collect_one(c['code'],period,asof,out/c['code'],fetch,c.get('selectedId'),c.get('uploadedPdf'),c.get('sourceDocument'))
   if prior_root:row['reuseStatus']='not-reused; acquisition-attempted';row['cacheReviewError']=cache_error
   (out/c['code']/'result.json').write_text(json.dumps(row,ensure_ascii=False,indent=2),encoding='utf8');rows.append(row)
 result=dict(period=period,asOf=asof,companies=rows,coverage=dict(requested=len(rows),published=sum(r['disclosureStatus']=='published' for r in rows),downloaded=sum(r['downloadStatus']=='downloaded' for r in rows),parsed=sum(r['parseStatus']=='parsed' for r in rows)),limitations=['目录未命中不证明未披露；下载和解析失败分别说明','页码为PDF物理页，不等于印刷页；关键词线索不证明经营原因','多个版本不自动取最新，扫描件需人工复核，不提供内置OCR','指定池与截止日覆盖，不代表全行业完整资料'])
 result['acquisitionSummary']=acquisition_summary(rows)
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
 lines=['# 财报覆盖清单','',period+'，披露截止日'+asof+'。','','| 公司 | 披露线索 | 下载 | 文本解析 | 数值核验 |','|---|---|---|---|---|']
 labels={'published':'找到披露','not-found':'目录未命中','unknown':'未知','downloaded':'已下载','not-attempted':'未执行','parsed':'已解析','failed':'失败','conflict':'版本冲突','user-provided-unverified':'用户提供，披露待核验'}
 labels['explicit-source-unverified']='明确原文链接，元数据待核验'
 for r in rows:
  lines.append('| '+r['code']+' | '+' | '.join(labels.get(r[k],r[k]) for k in ['disclosureStatus','downloadStatus','parseStatus','numericVerification'])+' |')
  if r['error']:lines.extend(['',r['code']+'：'+r['error']])
  if r.get('reuseStatus','').startswith('local-pdf'):lines.extend(['',r['code']+'：复用已保存原文，文件哈希及解析文字重新核对一致；未重新检查远程更正。'])
  if r['downloadStatus']=='conflict' and r['candidates']:
   lines.extend(['','### '+r['code']+' 可选择的报告版本','','同一报告期检索到以下版本。未自动认定最新版本优先，也未进行数值核验。','','| 报告标题 | 披露日期 | 公告编号 | 原文 |','|---|---|---|---|'])
   for candidate in r['candidates']:
    title=candidate['title'].replace('|','／').replace('\n',' ')
    lines.append('| '+title+' | '+candidate['publishedAt']+' | '+str(candidate['id'])+' | [查看原文]('+candidate['url']+') |')
 lines+=['','## 本次原文资料',*acquisition_lines(result['acquisitionSummary']),'','## 范围说明',*result['limitations']];text='\n'.join(lines);(out/'财报覆盖.md').write_text(text,encoding='utf8');(out/'财报覆盖.html').write_text(render(text,title='财报覆盖'),encoding='utf8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();run(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.out_dir)
