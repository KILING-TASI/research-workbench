"""Evidence-bound company brief; supplied facts and optional SEC original archive."""
import argparse,json,hashlib,math,statistics,copy
from pathlib import Path
from fund_series_tools import day,source,NOTICE
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant,urls
SECTIONS={'business':'业务与竞争结构','financial':'财务概况','valuation':'估值口径','events':'关键事件','risks':'风险与待验证事项'}

EXTENDED_SECTIONS={'businessSegments':'业务拆分','supplyChain':'产销链与供应链','researchDevelopment':'研发与技术能力','brokerViews':'已取得券商研究观点','catalysts':'催化条件与反证','forecast':'盈利预测假设','tracking':'近况与跟踪清单'}

def financial_review(link,identity,asof):
 from financial_source_binding import bound_archives,bound_originals,comparability_warnings,verify_financial_snapshot,income_basis_warnings,report_metadata_warnings
 from company_financial_report import original_checks,sample_commentary
 financial_path=Path(link['financialResult']);original_path=Path(link['originalResult'])
 fin=json.loads(financial_path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant);original=json.loads(original_path.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
 if identity['market']!='CN':raise ValueError('当前财报简报联动只接受A股档案')
 if fin['period']>asof or original['asOf']>asof:raise ValueError('财报联动资料晚于简报截止日')
 matches=[c for c in fin['companies'] if c['code']==identity['code']]
 if len(matches)!=1:raise ValueError('财报计算不含唯一的目标证券')
 company=matches[0]
 if company['metadata']['scope']!='consolidated' or company['metadata']['currency']!='CNY':raise ValueError('财报联动须为合并人民币口径')
 archives,archive_hashes=bound_archives(fin,link['archives']);bindings=bound_originals(original,original_path)
 if any(a['asOf']>asof for a in archives.values()):raise ValueError('三表档案截止日晚于简报截止日')
 verify_financial_snapshot(fin,archives)
 reports=[r for r in original['companies'] if r['code']==identity['code']]
 if len(reports)>1:raise ValueError('原文目标证券重复')
 report=reports[0] if reports else None
 checks=original_checks(archives[identity['code']],report,fin['period']) if report else []
 unverified=[x['label']+'未通过同期原文核验' for x in checks if x['status']!='matched']
 unverified+=report_metadata_warnings(report)
 if not checks:unverified.append('同期原文未完成支持字段核验')
 unverified += [w['warning'] for w in income_basis_warnings(archives[identity['code']],fin['period'])]
 unverified += [w['warning']+'（PDF第'+str(w['page'])+'页）' for w in comparability_warnings(report)]
 selected_groups=[g for g in fin['groups'] if all(g[k]==company['metadata'][k] for k in ['group','classificationVersion','scope','currency','unit','sectorType'])]
 comparison_lines,_=sample_commentary(dict(period=fin['period'],groups=selected_groups))
 return dict(code=identity['code'],period=fin['period'],unit=company['metadata']['unit'],metrics=company['metrics'],ratios=company['ratios'],signals=company['signals'],sampleComparison=comparison_lines,gaps=company['gaps']+unverified,checks=checks,reportSource=report.get('metadata') if report else None,archiveHashes=archive_hashes,originalBindings=bindings,inputHashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in [financial_path,original_path]},limits=['单季差分与累计原文核验分开；只核当前支持字段','这是指定公司历史财务，不补业务、估值或行业展望'])

def valuation_review(path,identity,asof):
 from company_scenarios import relative
 raw=Path(path).read_bytes();spec=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
 if identity['market']!='CN' or spec['currency']!='CNY':raise ValueError('当前估值联动只接受人民币A股指定池')
 if spec['asOf']>asof:raise ValueError('估值资料晚于简报截止日')
 result=relative(spec);rows=[r for r in result['rows'] if r['code']==identity['code']]
 if len(rows)!=1:raise ValueError('估值池不含唯一的目标证券')
 company=next(c for c in spec['companies'] if c['code']==identity['code'])
 return dict(row=rows[0],valuationDate=result['valuationDate'],financialPeriod=result['financialPeriod'],definition=result['definition'],marketCapEvidence=company.get('marketCap'),sourceFiles=spec.get('sourceFiles',[]),inputSha256=hashlib.sha256(raw).hexdigest(),limits=result['limitations'])
def build(spec):
 if not isinstance(spec,dict):raise ValueError('研究输入须为对象')
 spec=copy.deepcopy(spec)
 day(spec.get('asOf'));identity=spec.get('identity')
 if not isinstance(identity,dict):raise ValueError('公司身份须为对象')
 if any(not isinstance(identity.get(k),str) or not identity[k].strip() for k in ['name','code','market']):raise ValueError('公司身份字段须为非空文字')
 if identity.get('market') not in ('CN','HK','US') or not identity.get('code') or not identity.get('name'):raise ValueError('需明确公司名称、市场和代码')
 if type(spec.get('deepResearch',False)) is not bool:raise ValueError('deepResearch须为布尔值')
 titles={**({'judgment':'研究结论与核心矛盾'} if 'judgment' in spec else {}),**SECTIONS,**{k:v for k,v in EXTENDED_SECTIONS.items() if spec.get('deepResearch') or k in spec}}
 sections={};gaps=[]
 for key in titles:
  items=spec.get(key,[])
  if not isinstance(items,list):raise ValueError('章节必须为列表')
  checked=[]
  for item in items:
   if not isinstance(item,dict) or not isinstance(item.get('text'),str) or not item['text'].strip():raise ValueError('条目缺少说明')
   day(item['observedAt']);day(item['publishedAt']);urls([item['sourceUrl']])
   if not item['observedAt']<=item['publishedAt']<=spec['asOf']:raise ValueError('条目日期越界')
   if item.get('basis') not in ('source-statement','calculation','assumption','research-explanation'):raise ValueError('需区分来源陈述、计算或假设')
   if not isinstance(item.get('locator'),str) or not item['locator'].strip():raise ValueError('条目缺少原文或计算定位')
   if 'value' in item and item['value'] is not None:
    if isinstance(item['value'],bool) or not isinstance(item['value'],(int,float)) or not math.isfinite(item['value']) or (not isinstance(item.get('unit'),str) or not item['unit'].strip()):raise ValueError('数值需有限且有单位')
   if key=='judgment':
    if item['basis']!='research-explanation':raise ValueError('研究结论须标研究解释，不认证为原文事实')
    for field in ['scope','coreContradiction','alternatives','counterEvidence']:
     if not isinstance(item.get(field),str) or not item[field].strip():raise ValueError('研究结论须说明'+field)
   if key=='forecast':
    if item['basis'] not in ('assumption','calculation') or not isinstance(item.get('assumptions'),list) or not item['assumptions'] or any(not isinstance(v,str) or not v.strip() for v in item['assumptions']):raise ValueError('预测须明确假设，不标为已发生事实')
    if not item.get('targetPeriod'):raise ValueError('预测须明确目标期')
    day(item['targetPeriod'])
    if item['targetPeriod']<=spec['asOf']:raise ValueError('预测目标期须晚于截止日')
   if key=='catalysts' and (not isinstance(item.get('trigger'),str) or not item['trigger'].strip() or not isinstance(item.get('counterEvidence'),str) or not item['counterEvidence'].strip()):raise ValueError('催化研究须明确触发条件与反证')
   checked.append(item)
  sections[key]=checked
  if not checked:gaps.append(titles[key]+'未取得带来源资料')
 sec=None
 if spec.get('secArchive'):
  if identity['market']!='US':raise ValueError('SEC入口仅用于美国申报主体')
  binding=spec['secArchive'];path=Path(binding['path']);raw=path.read_bytes()
  if hashlib.sha256(raw).hexdigest()!=binding['sha256']:raise ValueError('SEC原始文件摘要不一致')
  from sec_company_facts import parse
  sec=parse(json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant),binding['cik'],spec['asOf'])
  if sec['entityName']!=identity['name']:raise ValueError('SEC主体名称与输入不一致')
  sec['originalSha256']=binding['sha256'];sec['sourceUrl']='https://data.sec.gov/api/xbrl/companyfacts/CIK'+binding['cik']+'.json'
 review=financial_review(spec['financialReview'],identity,spec['asOf']) if spec.get('financialReview') else None
 if review:gaps=[g for g in gaps if g!=SECTIONS['financial']+'未取得带来源资料']+review['gaps']
 valuation=valuation_review(spec['valuationInputPath'],identity,spec['asOf']) if spec.get('valuationInputPath') else None
 if valuation:
  gaps=[g for g in gaps if g!=SECTIONS['valuation']+'未取得带来源资料']
  names={'marketCap':'市值','netProfit':'净利润','equity':'净资产','revenue':'收入','netDebt':'净债务','EBITDA':'息税折旧摊销前利润'}
  gaps+=['估值所需'+names.get(k,k)+'资料缺失' for k in valuation['row']['gaps']]
 return dict(identity=identity,asOf=spec['asOf'],sections=sections,secFacts=sec,financialReview=review,valuationReview=valuation,gaps=gaps,limitations=['输入证券代码与申报主体的映射须另核；不按名称猜证券身份','用户提供的来源陈述不自动标为已核验原文','财务事实不是完整三表，缺附注或估值数据时不补造','估值及情景假设不代表目标价格或交易结论'],riskNotice=NOTICE)
def markdown(r):
 i=r['identity'];lines=['# '+i['name']+' · 公司研究简报','',i['market']+' / '+i['code']+'；资料截止日'+r['asOf']+'。','只展示本次取得资料；完整度不足时保留缺口，内容较多时不强行压缩为一张纸。']
 labels={'source-statement':'来源陈述（未自动核验）','calculation':'计算','assumption':'假设','research-explanation':'研究解释（未证明因果）'}
 for key,items in r['sections'].items():
  title={**SECTIONS,**EXTENDED_SECTIONS,'judgment':'研究结论与核心矛盾'}[key]
  lines+=['','## '+title]
  if not r['sections'][key] and not (key=='financial' and r.get('financialReview')) and not (key=='valuation' and r.get('valuationReview')):lines.append('尚未取得带来源的资料。')
  for x in r['sections'][key]:
   lines.append(x['text']+' 【'+labels[x['basis']]+'】')
   if key=='judgment':lines+=['核心矛盾：'+x['coreContradiction'],'判断范围：'+x['scope'],'竞争解释：'+x['alternatives'],'改变判断的证据：'+x['counterEvidence']]
   if key=='forecast':lines+=['目标期：'+x['targetPeriod']+'；这是假设下的预测，不代表未来实际结果。','假设：'+'；'.join(x['assumptions'])]
   if key=='catalysts':lines+=['触发条件：'+x['trigger'],'反证条件：'+x['counterEvidence']+'；尚未确认触发。']
   if x.get('value') is not None:lines.append('数值：'+str(x['value'])+' '+x['unit'])
   lines.append('所属日'+x['observedAt']+'；披露日'+x['publishedAt']+'；定位：'+str(x['locator'])+'。[来源]('+x['sourceUrl']+')')
  if key=='financial' and r.get('financialReview'):
   f=r['financialReview'];lines+=['报告期'+f['period']+'，以下单季数值按累计报表差分；金额单位：'+f['unit']+'。累计原文核验见下方，不将本期核验外推到其他报告期。','|指标|本季度|同比|环比|','|---|---:|---:|---:|']
   for metric in ['revenue','parentProfit','operatingCash']:
    m=f['metrics'][metric];v=m['current']['value'];pct=lambda obj:format(obj['value']*100,'.2f')+'%' if obj['value'] is not None else '未计算：'+obj['reason']
    lines.append('|'+m['label']+'|'+(format(v,',.2f') if v is not None else '缺失')+'|'+pct(m['yoy'])+'|'+pct(m['qoq'])+'|')
   lines+=f['signals']
   matched=sum(x['status']=='matched' for x in f['checks']);lines.append('同期原文支持字段'+str(len(f['checks']))+'项，其中'+str(matched)+'项在披露精度内匹配；这不证明其他期差分或所有附注均已核验。')
   for check in f['checks']:
    url=(f.get('reportSource') or {}).get('url');pages='、'.join(('[PDF第'+str(v['page'])+'页]('+url.split('#')[0]+'#page='+str(v['page'])+')') if url else 'PDF物理第'+str(v['page'])+'页' for v in check['original']);lines.append(check['label']+'：'+('已匹配' if check['status']=='matched' else '尚未匹配，需复核')+('，'+pages if pages else '')+'。')
   if (f.get('reportSource') or {}).get('url'):lines.append('[同期报告原文]('+f['reportSource']['url']+')')
   lines+=['','### 指定样本对照',*f['sampleComparison']]
  if key=='valuation' and r.get('valuationReview'):
   v=r['valuationReview'];lines.append('估值比较日'+v['valuationDate']+'，财务期间'+v['financialPeriod']+'。口径：'+v['definition']+'；不自动视为滚动十二个月估值。')
   for name,value in v['row']['multiples'].items():lines.append(name+'：'+(format(value,'.2f') if value is not None else '未计算'))
   cap=v['marketCapEvidence']
   if cap:
    lines.append('市值依据（'+labels[cap['basis']]+'）：'+cap['note']+'。')
    if cap.get('sourceUrl'):lines.append('[市值来源]('+cap['sourceUrl']+')')
   lines+=v['limits']
 sec=r['secFacts']
 if sec:
  lines+=['','## SEC原始财务事实覆盖','重新解析保留的原始响应，按申报日过滤；不静默选择同期间冲突版本。','|标签|有效观测|最近期末|最近期末期间与数值|','|---|---:|---|---|']
  for key,m in sec['metrics'].items():
   groups=m['periodGroups'];latest=max((g['end'] for g in groups),default=None);parts=[]
   for g in groups:
    if g['end']==latest:parts.append((g['start'] or '时点')+'至'+g['end']+'：'+str(g['distinctValues'])+' USD'+('（版本数值冲突）' if g['valueConflict'] else ''))
   lines.append('|'+key+'|'+str(len(m['observations']))+'|'+(latest or '缺失')+'|'+'；'.join(parts)+'|')
  lines+=['','[SEC数据接口]('+sec['sourceUrl']+')','原始文件摘要：'+sec['originalSha256'],'期间指标按实际起止展示，不拼成自然季度；CIK与证券代码映射尚未独立核验。']
 lines+=['','## 资料缺口']+['- '+x for x in r['gaps']]+['','## 使用范围']+r['limitations']+['',r['riskNotice']]
 return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 if any(x.exists() for x in [a.out,a.out.with_suffix('.md'),a.out.with_suffix('.html')]):raise FileExistsError('输出已存在')
 r=build(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant));a.out.parent.mkdir(parents=True,exist_ok=True);text=markdown(r)
 html=render(text,title=r['identity']['name']+'公司研究');payload=json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)
 a.out.write_text(payload,encoding='utf8');a.out.with_suffix('.md').write_text(text,encoding='utf8');a.out.with_suffix('.html').write_text(html,encoding='utf8')
