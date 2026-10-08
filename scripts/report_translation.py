"""Publish AI-authored Chinese translations with complete source-text coverage checks."""
import argparse,hashlib,json,re,shutil
from pathlib import Path
from collections import Counter
from research_report_reading import compact,verify_pdf_pages
from research_brief_html import render
from collection_validation import day,unique_pairs,reject_constant

def numeric_tokens(text):
 text=re.sub(r'\bpercent\b','%',text,flags=re.I).replace('百分比','%')
 text=text.replace('−','-').replace('–','-').replace('—','-')
 pattern=r'[+-]?\s*\d+(?:[,.]\d+)*(?:\s*(?:%|billion|million|trillion|亿|万))?'
 return Counter(re.sub(r'\s+','',m.group()).lower() for m in re.finditer(pattern,text,flags=re.I))

def translated_page(entry,original):
 if not isinstance(entry,dict) or type(entry.get('page'))!=int or entry['page']<1:raise ValueError('译页须为对象及正整数页码')
 if set(entry)-{'page','blocks'}:raise ValueError('译页只接受page和blocks，不接受自声明核验状态')
 blocks=entry.get('blocks')
 if not isinstance(blocks,list) or not blocks:raise ValueError('译页需非空段落列表')
 for block in blocks:
  if not isinstance(block,dict) or set(block)!={'sourceText','translation'}:raise ValueError('译段需sourceText和translation')
  if not all(isinstance(block[k],str) and block[k].strip() for k in block):raise ValueError('原文及译文需非空文字')
  if not re.search(r'[\u4e00-\u9fff]',block['translation']):raise ValueError('中文译文需包含中文文字')
 if compact(''.join(b['sourceText'] for b in blocks))!=compact(original):raise ValueError('译段原文未按顺序完整覆盖该页文字')
 warnings=[]
 for index,b in enumerate(blocks,1):
  if numeric_tokens(b['sourceText'])!=numeric_tokens(b['translation']):warnings.append('第'+str(index)+'段数字、正负号、百分号或数量级写法不同，需人工核对；可能包含合法的日期或单位换写。')
 return dict(page=entry['page'],blocks=blocks,sourceTextCoverage='complete-for-extracted-text',numericWarnings=warnings,semanticVerification='not-independently-verified')

def build(spec,out):
 if not isinstance(spec,dict):raise ValueError('译文请求须为对象')
 raw=Path(spec['archive']).read_bytes();archive=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant);day(archive.get('asOf'))
 candidates=[r for r in archive['reports'] if r['id']==spec['reportId']]
 if len(candidates)!=1 or candidates[0]['status']!='readable':raise ValueError('需唯一已解析原文')
 report=candidates[0];integrity=verify_pdf_pages(report);original={p['page']:p['text'] for p in report['pages']}
 entries=spec['pages']
 if not isinstance(entries,list) or any(not isinstance(p,dict) for p in entries):raise ValueError('译页须为对象列表')
 ids=[p.get('page') for p in entries]
 if not entries or any(type(n)!=int or n not in original for n in ids) or ids!=sorted(set(ids)):raise ValueError('译页需有效、唯一且按页码排序')
 pages=[translated_page(p,original[p['page']]) for p in entries]
 missing=sorted(set(original)-set(ids));low=[n for n,text in original.items() if len(text.strip())<40]
 coverage='all-extracted-pages-covered' if not missing and not low else 'partial-or-low-text'
 result=dict(reportId=report['id'],asOf=archive['asOf'],title=report.get('title'),sourceUrl=report.get('sourceUrl'),originalSha256=report['sha256'],archiveSha256=hashlib.sha256(raw).hexdigest(),methodSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),evidenceIntegrity=integrity,pages=pages,missingPages=missing,lowTextPages=low,coverage=coverage,semanticVerification='not-independently-verified',sourceFile='sources/original.pdf',limitations=['译文由AI按原文组织；原文覆盖及数字检查不证明翻译语义正确。','只覆盖可提取文字，不还原图片、公式及复杂表格版式；原PDF仍需复核。','历史文件不代表最新政策或研究观点，原文元数据沿用输入声明。'])
 snapshot=Path(report['pdfPath']).read_bytes()
 if hashlib.sha256(snapshot).hexdigest()!=report['sha256']:raise ValueError('交付前原PDF变化，需重新解析')
 out=Path(out);out.mkdir(parents=True,exist_ok=False);(out/'sources').mkdir();(out/'sources/original.pdf').write_bytes(snapshot)
 lines=['# '+(report.get('title') or report['id'])+'：中文译文','','本次按原文物理页提供中文译文。文字覆盖检查不等于语义核验，数字提示需结合原件复查。']
 if missing:lines.append('尚未翻译的物理页：'+','.join(map(str,missing))+'。')
 if low:lines.append('文字不足的物理页：'+','.join(map(str,low))+'，不能据此声称全文翻译完整。')
 for page in pages:
  lines+=['','## [原文第'+str(page['page'])+'页](sources/original.pdf#page='+str(page['page'])+')','']
  for b in page['blocks']:lines += [b['translation'],'']
  lines+=page['numericWarnings']
 lines+=['','## 翻译范围与局限',*result['limitations']]
 md='\n'.join(lines);html=render(md,title='中文译文');payload=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
 (out/'中文译文.md').write_text(md,encoding='utf8');(out/'中文译文.html').write_text(html,encoding='utf8');(out/'result.json').write_text(payload,encoding='utf8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();build(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.out_dir)
