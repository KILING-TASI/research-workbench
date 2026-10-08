"""On-demand policy HTML archive and paragraph-bound explanations; no legal verdict."""
import argparse,hashlib,html,json,re
from datetime import date,datetime,timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit
from collection_validation import unique_pairs,reject_constant,finite_json_float

def load_json(text):
 return json.loads(text,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def source_url(url):
 if not isinstance(url,str):raise ValueError("需有效HTTPS来源")
 p=urlsplit(url)
 if p.scheme!="https" or not p.hostname or p.username or p.password or any(c.isspace() for c in url):raise ValueError("需有效HTTPS来源")
 try:p.port
 except ValueError:raise ValueError("来源端口无效")
from research_report_reading import check_entry,compact
from research_brief_html import render

class Content(HTMLParser):
 def __init__(self,content_class):
  super().__init__(convert_charrefs=True);self.content_class=content_class;self.depth=0;self.roots=0;self.skip=0;self.buffer=[];self.paragraphs=[];self.unsupported=[]
 def flush(self):
  text=re.sub(r'\s+',' ',''.join(self.buffer)).strip();self.buffer=[]
  if text:self.paragraphs.append(dict(paragraph=len(self.paragraphs)+1,text=text))
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if not self.depth:
   if self.content_class in attrs.get('class','').split():self.depth=1;self.roots+=1
   return
  if tag in ['script','style','noscript']:self.skip+=1
  if tag in ['table','img']:self.unsupported.append(tag)
  if not self.skip and tag in ['p','div','br','li']:self.flush()
  if tag not in ['br','img','hr','meta','link','input','source','wbr']:self.depth+=1
 def handle_endtag(self,tag):
  if not self.depth:return
  if not self.skip and tag in ['p','div','li']:self.flush()
  if tag in ['script','style','noscript'] and self.skip:self.skip-=1
  if tag not in ['br','img','hr','meta','link','input','source','wbr']:self.depth-=1
  if self.depth==0:self.flush()
 def handle_data(self,text):
  if self.depth and not self.skip:self.buffer.append(text)

def parse(raw,encoding,content_class,minimum=100):
 if encoding not in ['utf-8','gb18030']:raise ValueError('需明确支持的网页编码')
 if not isinstance(content_class,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',content_class):raise ValueError('需明确唯一正文容器class')
 p=Content(content_class);p.feed(raw.decode(encoding));p.flush()
 if p.roots!=1 or p.depth!=0:raise ValueError('正文容器缺失、重复或结构不完整，不能自动选择')
 if sum(len(r['text']) for r in p.paragraphs)<minimum:raise ValueError('正文不足；动态网页或图片需另取原文')
 return p.paragraphs,sorted(set(p.unsupported))

def fetch(url):
 source_url(url)
 with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=35) as response:raw=response.read(2*1024*1024+1)
 if len(raw)>2*1024*1024:raise ValueError('政策网页超过2MB限制')
 return raw

def prepare(spec,out):
 date.fromisoformat(spec['asOf']);url=spec['sourceUrl']
 source_url(url)
 raw=Path(spec['htmlPath']).read_bytes() if spec.get('htmlPath') else fetch(url)
 if len(raw)>2*1024*1024:raise ValueError('政策网页超过2MB限制')
 paragraphs,unsupported=parse(raw,spec.get('encoding','utf-8'),spec['contentClass'])
 if not isinstance(spec.get('title'),str) or not spec['title'].strip():raise ValueError('需明确政策标题')
 metadata=[]
 if spec.get('metadataClass'):metadata,_=parse(raw,spec.get('encoding','utf-8'),spec['metadataClass'],minimum=1)
 out=Path(out);out.mkdir(parents=True,exist_ok=False);(out/'original.html').write_bytes(raw)
 result=dict(type='policy-html-archive',asOf=spec['asOf'],sourceUrl=url,title=spec['title'],rawPath=str((out/'original.html').resolve()),sha256=hashlib.sha256(raw).hexdigest(),encoding=spec.get('encoding','utf-8'),contentClass=spec['contentClass'],paragraphs=paragraphs,metadataClass=spec.get('metadataClass'),metadataParagraphs=metadata,unsupportedElements=unsupported,retrievedAt=datetime.now(timezone.utc).isoformat(),metadataStatus='input-declared; current-validity-not-assessed')
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');return result

def verified_archive(path):
 archive=load_json(Path(path).read_text('utf-8-sig'))
 if archive.get('type')!='policy-html-archive':raise ValueError('不是网页政策原文归档')
 raw=Path(archive['rawPath']).read_bytes()
 if hashlib.sha256(raw).hexdigest()!=archive['sha256']:raise ValueError('政策网页原文哈希变化，需重新归档')
 paragraphs,unsupported=parse(raw,archive['encoding'],archive['contentClass'])
 if paragraphs!=archive['paragraphs'] or unsupported!=archive['unsupportedElements']:raise ValueError('保存段落与原文重新解析不一致')
 if archive.get('metadataClass'):
  metadata,_=parse(raw,archive['encoding'],archive['metadataClass'],minimum=1)
  if metadata!=archive.get('metadataParagraphs'):raise ValueError('保存元数据文字与原文不一致')
 return archive,raw

def entry(e,archive):
 if e.get('basis') not in ['policy-statement','research-explanation']:raise ValueError('需区分政策陈述与研究解释')
 refs=e.get('evidence',[]);checked=[]
 if not refs:raise ValueError('政策条目需段落引句')
 for ref in refs:
  location=ref.get('locatorType','body')
  if location not in ['body','metadata'] or type(ref.get('paragraph'))!=int:raise ValueError('需明确正文或元数据段落定位')
  rows=archive['paragraphs'] if location=='body' else archive.get('metadataParagraphs',[])
  item=check_entry(dict(text=e['text'],evidence=[dict(page=ref['paragraph'],quote=ref['quote'])]),dict(sha256=archive['sha256'],pages=[dict(page=r['paragraph'],text=r['text']) for r in rows]))
  checked.extend(dict(paragraph=r['page'],locatorType=location,quote=r['quote'],sha256=r['sha256'],status='quote-located-not-semantic-verification') for r in item['evidence'])
 return dict(text=e['text'],basis=e['basis'],evidence=checked)

def build(spec,out):
 archive,raw=verified_archive(spec['archive']);sections={}
 for key in ['scope','timing','transmission','risks']:
  rows=spec.get(key,[])
  if not isinstance(rows,list):raise ValueError('政策分析各栏需列表')
  sections[key]=[entry(e,archive) for e in rows]
 if not any(sections.values()):raise ValueError('至少需要一项原文依据')
 clocks=[]
 for clock in spec.get('clocks',[]):
  if clock.get('kind') not in ['issue-date','publication-date','project-cutoff','effective-date','implementation-deadline','expiry-date','other']:raise ValueError('政策日期类型无效')
  d=date.fromisoformat(clock['date']);checked=entry(clock,archive)
  quotes=compact(''.join(r['quote'] for r in checked['evidence']))
  literals=[d.isoformat(),d.isoformat().replace('-','/'),f'{d.year}年{d.month}月{d.day}日',f'{d.year}年{d.month:02d}月{d.day:02d}日']
  month=['January','February','March','April','May','June','July','August','September','October','November','December'][d.month-1]
  english_literal=compact(f'{month} {d.day}, {d.year}')
  literals.append(english_literal)
  if not any(v in quotes for v in literals):raise ValueError('声明日期未出现在引句中，需更完整定位')
  chinese_effect=any(re.search(re.escape(v)+r'(?:起)?(?:正式|开始)?(?:施行|实施|生效)',quotes) for v in literals)
  english_effect=bool(re.search(r'(?<![A-Za-z])effective'+re.escape(english_literal),quotes,re.I))
  if clock['kind']=='effective-date' and not (chinese_effect or english_effect):raise ValueError('生效日需对应日期与明确施行措辞，项目分界日不能替代')
  if clock['kind'] in ['issue-date','publication-date'] and d.isoformat()>archive['asOf']:raise ValueError('政策发布时间超出研究截止日')
  clocks.append(dict(checked,date=d.isoformat(),kind=clock['kind'],meaningStatus='input-classified-not-legal-effect-verified'))
 gaps=spec.get('gaps',[])
 if not isinstance(gaps,list) or any(not isinstance(g,str) or not g.strip() for g in gaps):raise ValueError('资料缺口需非空文字列表')
 gaps=list(gaps)+['政策当前有效性、更正及地方实施版本尚未在本流程中核验。']
 for key,label in [('scope','适用范围'),('timing','实施时点'),('transmission','经营传导'),('risks','风险与反证')]:
  if not sections[key]:gaps.append(label+'未提供有据分析。')
 if archive['unsupportedElements']:gaps.append('正文含表格或图片，段落文字不能证明这些内容完整提取。')
 result=dict(type='policy-original-reading',asOf=archive['asOf'],title=archive['title'],sourceUrl=archive['sourceUrl'],sections=sections,clocks=clocks,gaps=gaps,validityStatus='not-assessed',evidenceIntegrity='html-reparsed-paragraphs-matched',originalSha256=archive['sha256'],archivePath=spec['archive'],codeSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),limitations=['仅核对原文引句定位，不证明解释或经营传导成立','日期意义为研究者分类，不构成法律有效性结论','网页段落号不是PDF页码；正文容器及版本变化需重新归档'])
 refs=[ref for entries in sections.values() for e in entries for ref in e['evidence']]+[ref for c in clocks for ref in c['evidence']]
 result['citationScope']=dict(bodyParagraphs=sorted({r['paragraph'] for r in refs if r['locatorType']=='body'}),metadataParagraphs=sorted({r['paragraph'] for r in refs if r['locatorType']=='metadata'}),bodyParagraphCount=len(archive['paragraphs']),status='located-excerpts-not-full-policy-verification')
 result['methodVersions']={name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ['policy_original_reading.py','research_report_reading.py','research_brief_html.py']}
 out=Path(out);out.mkdir(parents=True,exist_ok=False);(out/'source-original.html').write_bytes(raw)
 viewer='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>政策原文段落</title><h1>'+html.escape(archive['title'])+'</h1><p>归档文件哈希：'+archive['sha256']+'</p>'
 viewer+=''.join('<p id="paragraph-'+str(r['paragraph'])+'"><b>段落'+str(r['paragraph'])+'</b> '+html.escape(r['text'])+'</p>' for r in archive['paragraphs'])
 viewer+=''.join('<p id="metadata-'+str(r['paragraph'])+'"><b>网页元数据'+str(r['paragraph'])+'</b> '+html.escape(r['text'])+'</p>' for r in archive.get('metadataParagraphs',[]))
 (out/'原文段落.html').write_text(viewer,'utf-8');lines=['# '+archive['title']+' · 原文研究','', '[查看来源网页]('+archive['sourceUrl']+')。以下区分政策陈述与研究解释，当前有效性尚未判定。']
 for key,label in [('scope','适用对象与范围'),('timing','时点与实施条件'),('transmission','经营传导假设'),('risks','局限与反证')]:
  lines+=['','## '+label]
  for e in sections[key]:
   lines.append(('政策陈述：' if e['basis']=='policy-statement' else '研究解释：')+e['text'])
   for ref in e['evidence']:lines.append('[原文'+('段落' if ref['locatorType']=='body' else '网页元数据')+str(ref['paragraph'])+'](原文段落.html#'+('paragraph-' if ref['locatorType']=='body' else 'metadata-')+str(ref['paragraph'])+')：'+ref['quote'])
  if not sections[key]:lines.append('本次未取得足够依据，保留空缺。')
 lines+=['','## 日期口径','|日期|类型|说明|','|---|---|---|']
 for c in clocks:lines.append('|'+c['date']+'|'+{'issue-date':'发文日','publication-date':'公布日','project-cutoff':'项目分界日','effective-date':'原文明示施行时点','implementation-deadline':'实施期限','expiry-date':'到期日','other':'其他时点'}[c['kind']]+'|'+c['text']+'|')
 lines+=['','## 资料缺口',*gaps];md='\n'.join(lines)
 (out/'政策原文研究.md').write_text(md,'utf-8');(out/'政策原文研究.html').write_text(render(md,title='政策原文研究'),'utf-8');(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8');return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','build']);p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();(prepare if a.mode=='prepare' else build)(load_json(a.input.read_text('utf-8-sig')),a.out_dir)
