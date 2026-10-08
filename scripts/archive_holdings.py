"""Explicit archived report to equity evidence; unknown accounting differences remain open."""
import argparse,hashlib,json,shutil,tempfile,os
from pathlib import Path
from fund_document_archive import read_pages,identity,report_period
from fof_reports import inspect_and_parse
from research_brief_html import render
from atomic_json import write
from collection_validation import day,urls,unique_pairs,reject_constant

def method_files():
 return [Path(__file__).with_name(name) for name in ['archive_holdings.py','fund_document_archive.py','fof_reports.py','fund_report_holdings.py','verify_original.py','research_brief_html.py','atomic_json.py','collection_validation.py']]

def run(archive_path,directory,parse_fn=inspect_and_parse):
 archive_path=Path(archive_path);raw=archive_path.read_bytes();archive=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
 if not isinstance(archive,dict) or any(not isinstance(archive.get(k),dict) for k in ['identity','catalogItem','reportPeriod','metadata']):raise ValueError('归档须含身份、报告期、目录及来源对象')
 out=Path(directory)
 if out.exists():raise FileExistsError('输出目录已存在，保留旧研究')
 path=Path(archive['documentPath']);digest=hashlib.sha256(path.read_bytes()).hexdigest()
 if digest!=archive.get('sha256'):raise ValueError('原文文件摘要不一致，停止持仓解析')
 code=archive['code'];item=archive['catalogItem'];period=archive.get('reportPeriod')
 if archive['identity'].get('matched') is not True or not period or period.get('status')!='matched':raise ValueError('原文身份及明确报告期须先核对')
 if day(period.get('expectedStart'))>day(period.get('expectedEnd')):raise ValueError('报告期起止顺序无效')
 day(item.get('publishedAt'));day(archive.get('asOf'));urls([archive['metadata'].get('sourceUrl')])
 pages=read_pages(path)
 if not identity(pages,code,item['title'])['matched']:raise ValueError('重新读取原文身份未匹配')
 if report_period(pages,period['expectedStart'],period['expectedEnd'])['status']!='matched':raise ValueError('重新读取原文明示报告期未匹配')
 if period['expectedEnd']>item['publishedAt'] or item['publishedAt']>archive['asOf']:raise ValueError('报告期、披露日期与截止日不一致')
 meta={'title':item['title'],'publishedAt':item['publishedAt'],'sourceUrl':archive['metadata']['sourceUrl']}
 result={'code':code,'reportDate':period['expectedEnd'],'sourceSha256':digest,'archiveSha256':hashlib.sha256(raw).hexdigest(),'sourceUrl':meta['sourceUrl'],'status':'unparsed','holdings':None,'gaps':[]}
 try:
  parsed=parse_fn(path,code,period['expectedEnd'],meta)
  if not isinstance(parsed,dict) or not isinstance(parsed.get('holdings'),list) or any(not isinstance(h,dict) for h in parsed['holdings']):raise ValueError('持仓解析输出结构无效')
  if parsed.get('sourceSha256')!=digest or parsed.get('id')!=code or parsed.get('reportDate')!=period['expectedEnd']:raise ValueError('解析输出与原文身份不一致')
  result['holdings']=parsed;result['status']='parsed-with-accounting-gap' if parsed.get('accountingReconciliation',{}).get('status')=='unresolved' else 'parsed'
 except Exception as exc:result['gaps'].append('持仓尚未解析完成：'+str(exc))
 lines=['# 公开股票持仓核对','',item['title'],'报告期末：'+period['expectedEnd']+'。这里只研究披露时点，不代表当前仓位或真实交易。','']
 parsed=result['holdings']
 if parsed:
  lines.append('取得'+str(len(parsed['holdings']))+'只股票，明细行的金额、权重与股票表合计按现有布局核对。非股票资产及当前持仓不在本次核对范围。')
  accounting=parsed.get('accountingReconciliation',{})
  if accounting.get('status')=='unresolved':
   result['gaps'].append('会计股票余额与明细合计差额未解释，暂不进入严格FOF自动穿透')
   lines+=['','会计股票余额减去明细合计的差额为'+accounting['differenceCNY']+'元。明细与行业表一致，但会计勾稽仍有缺口；口径注释不是独立调整金额，不能据此核销差额。']
   for note in accounting.get('scopeNotes',[]):lines.append('PDF第'+str(note['page'])+'页：'+note['quote'])
  else:lines.append('本次解析未登记未解释会计差额；这不证明全部资产或官方发布来源已核验。')
  lines+=['','## 前十只已披露股票','占比以基金全部份额合计净资产为分母。','| 股票 | 占基金净资产 | 原文物理页 |','|---|---|---|']
  for h in parsed['holdings'][:10]:lines.append('| '+h['name'].replace('|','\\|')+'（'+h['code']+'） | '+f"{h['weight']*100:.2f}%"+' | '+h['locator']+' |')
 result['gaps']+=['未核验官方发布网页与完整非股票资产','持仓快照不还原调仓、收益归因或实时风险']
 lines+=['','## 本次局限']+['- '+gap for gap in result['gaps']]+['','[原文副本]('+result['sourceUrl']+')','文件摘要（SHA-256）：'+digest,'','不构成投资建议。']
 text='\n'.join(lines);out.parent.mkdir(parents=True,exist_ok=True);temporary=Path(tempfile.mkdtemp(prefix='.'+out.name+'-',dir=out.parent))
 try:
  write(temporary/'result.json',result);(temporary/'持仓核对.md').write_text(text,'utf-8');(temporary/'持仓核对.html').write_text(render(text),'utf-8')
  methods=method_files()
  manifest={'schemaVersion':1,'artifactType':'archived-holdings','inputSha256':result['archiveSha256'],'sourceSha256':digest,'methodSha256':hashlib.sha256(b''.join(p.read_bytes() for p in methods)).hexdigest(),'methodFiles':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in methods},'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in temporary.iterdir() if p.is_file()},'visualReview':'not-performed','sourceVerification':'not-verified'}
  write(temporary/'report-manifest.json',manifest)
  if out.exists():raise FileExistsError('输出目录已存在，保留旧研究')
  os.rename(temporary,out)
 finally:
  if temporary.exists():shutil.rmtree(temporary)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('archive');p.add_argument('--out-dir',required=True);a=p.parse_args();run(a.archive,a.out_dir)
