"""Explicit reading scope and printed-table checks, never backtest replication."""
import re
from decimal import Decimal,InvalidOperation

def review_coverage(analysis,report):
 from research_report_reading import check_entry,compact
 if not isinstance(analysis,dict) or not isinstance(report,dict) or not isinstance(report.get('pages'),list):raise ValueError('阅读分析与报告页面结构无效')
 pages={}
 for page in report['pages']:
  if not isinstance(page,dict) or type(page.get('page'))!=int or page['page']<1 or not isinstance(page.get('text'),str):raise ValueError('报告页码及文本无效')
  if page['page'] in pages:raise ValueError('报告物理页重复，不可覆盖')
  pages[page['page']]=page['text']
 sections=[];tables=[];gaps=[]
 supplied=analysis.get('sectionReviews',[])
 if not isinstance(supplied,list):raise ValueError('章节阅读记录须为列表')
 seen=set()
 for section in supplied:
  if not isinstance(section,dict):raise ValueError('章节记录须为对象')
  title=section.get('title');start=section.get('startPage');end=section.get('endPage');state=section.get('status')
  if not isinstance(title,str) or not title.strip() or title in seen:raise ValueError('章节标题须非空且不重复')
  seen.add(title)
  if type(start)!=int or type(end)!=int or start not in pages or end not in pages or start>end:raise ValueError('章节页码范围无效')
  if state not in ['reviewed','pending']:raise ValueError('章节阅读状态无效')
  missing=[n for n in range(start,end+1) if n not in pages]
  if missing:raise ValueError('章节范围缺少物理页：'+','.join(map(str,missing)))
  refs=section.get('evidence',[])
  if not isinstance(refs,list) or any(not isinstance(r,dict) for r in refs):raise ValueError('章节依据须为对象列表')
  if not refs or any(type(r.get('page'))!=int or not start<=r['page']<=end for r in refs):raise ValueError('章节依据必须位于声明页码范围')
  checked=check_entry(dict(text=title,evidence=refs),report)
  if not isinstance(section.get('note'),str) or not section['note'].strip():raise ValueError('章节须说明阅读发现或待核查内容')
  sections.append(dict(title=title,startPage=start,endPage=end,status=state,note=section['note'],evidence=checked['evidence'],verificationScope='quotes-located; reading-completeness-user-declared'))
  empty=[n for n in range(start,end+1) if not pages[n].strip()]
  if empty:gaps.append('章节存在无可解析文本页，阅读完整性未确认：'+title+'；页'+','.join(map(str,empty)))
  if state=='pending':gaps.append('章节尚待阅读核查：'+title)
 checks=analysis.get('numericTableChecks',[])
 if not isinstance(checks,list):raise ValueError('数值表格核验须为列表')
 for row in checks:
  if not isinstance(row,dict):raise ValueError('表格核验记录须为对象')
  page=row.get('page');columns=row.get('columns');values=row.get('values');label=row.get('rowLabel');quote=row.get('rowQuote');heading=row.get('headingQuote')
  if type(page)!=int or page not in pages:raise ValueError('表格页码无效')
  if not isinstance(columns,list) or not columns or any(not isinstance(c,str) or not c.strip() for c in columns):raise ValueError('表格列名称须非空')
  groups=row.get('columnGroups');group_heading=row.get('groupHeadingQuote')
  if groups is None:
   if len(set(columns))!=len(columns):raise ValueError('重复列名须明确列分组与分组表头')
  else:
   if not isinstance(groups,list) or len(groups)!=len(columns) or any(not isinstance(g,str) or not g.strip() for g in groups):raise ValueError('列分组须逐列对应非空名称')
   if len(set(zip(groups,columns)))!=len(columns):raise ValueError('同组列名不能重复')
   blocks=[g for i,g in enumerate(groups) if i==0 or g!=groups[i-1]]
   if len(set(blocks))!=len(blocks):raise ValueError('每个列分组须连续，不支持交错布局')
   if not isinstance(group_heading,str) or len(compact(group_heading))<8:raise ValueError('需分组表头原文引句')
  if not isinstance(values,list) or len(values)!=len(columns) or any(isinstance(v,bool) for v in values):raise ValueError('表格数值须逐列对应')
  if not isinstance(label,str) or not label.strip() or not isinstance(quote,str) or not compact(quote).startswith(compact(label)):raise ValueError('表格行引句须以指标名称开始')
  checked=check_entry(dict(text=label,evidence=[dict(page=page,quote=heading),dict(page=page,quote=quote)]),report)
  title=row.get('tableTitle')
  if not isinstance(title,str) or len(compact(title))<8:raise ValueError('需明确表格标题，避免同页同名指标串表')
  page_text=compact(pages[page]);at=page_text.find(compact(title))
  if at<0:raise ValueError('表格标题无法在指定页定位')
  if page_text.count(compact(title))!=1:raise ValueError('同页表格标题重复，无法唯一定位')
  tail=page_text[at+len(compact(title)):];boundary=re.search(r'图表\d+[:：]',tail)
  block=tail[:boundary.start()] if boundary else tail
  hpos=block.find(compact(heading));rpos=block.find(compact(quote))
  if hpos<0 or rpos<hpos+len(compact(heading)):raise ValueError('列头与指标行不在同一标题后的表格范围，需人工复核')
  if groups is not None:
   gpos=block.find(compact(group_heading))
   if gpos<0 or gpos+len(compact(group_heading))>hpos:raise ValueError('分组表头须在同表列头之前')
   check_entry(dict(text=label,evidence=[dict(page=page,quote=group_heading)]),report)
   offset=0
   for group in blocks:
    at=compact(group_heading).find(compact(group),offset)
    if at<0:raise ValueError('分组顺序与表头不一致')
    offset=at+len(compact(group))
  head=compact(heading);offset=0
  for column in columns:
   at=head.find(compact(column),offset)
   if at<0:raise ValueError('表头引句未按声明顺序覆盖列名称')
   offset=at+len(compact(column))
  # Whitespace in PDF often separates adjacent positive decimals; retain it during numeric scanning.
  body=re.sub(r'^\s*'+re.escape(label)+r'\s*','',quote,count=1)
  tokens=re.findall(r'[-+]?\d+(?:,\d{3})*(?:\.\d+)?%?',body)
  if len(tokens)!=len(values):raise ValueError('行数值数量与列数不一致，复杂表格需人工核对')
  try:
   actual=[Decimal(t.rstrip('%').replace(',','')) for t in tokens];expected=[Decimal(str(v)) for v in values]
  except InvalidOperation:raise ValueError('表格数值无效')
  if any(not v.is_finite() for v in expected) or actual!=expected:raise ValueError('表格数值与原文行不一致')
  unit=row.get('unit')
  if unit not in ['percent','number']:raise ValueError('表格单位须为percent或number')
  if any(t.endswith('%')!=(unit=='percent') for t in tokens):raise ValueError('表格百分号与声明单位不一致')
  tables.append(dict(page=page,tableTitle=title,columns=columns,columnGroups=groups,groupHeadingQuote=group_heading if groups is not None else None,groupMappingStatus='declared-order-with-located-headings-not-coordinate-verified' if groups is not None else 'not-grouped',rowLabel=label,values=[str(v) for v in expected],unit=unit,evidence=checked['evidence'],status='printed-row-values-matched',limitations='仅核对印刷表格逐列数值；未重算回测、底层样本、交易成本或图中曲线'))
 return dict(sections=sections,numericTables=tables,gaps=gaps,scope='章节阅读范围为声明；引句和所列印刷数值已定位，图像曲线不自动解析')
