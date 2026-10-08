"""Join numeric calculations and archived report evidence without inventing causes."""
import argparse,hashlib,json,re,shutil,math
from decimal import Decimal
from pathlib import Path
from industry_financials import FIELDS,observation,applicability_notes,metadata_unit_warnings
from research_brief_html import render
from financial_source_binding import bound_archives,bound_originals,verify_financial_snapshot,comparability_warnings,income_basis_warnings,report_metadata_warnings
from research_report_reading import check_entry,underlying_source_assessment
from appraisal_contract import coverage as appraisal_coverage,validate_details
from profit_change_bridge import bridge as profit_bridge,paragraphs as bridge_paragraphs,detail_residual
from accounting_basis import validate as accounting_validate,paragraphs as accounting_paragraphs
from collection_validation import unique_pairs,reject_constant
TABLE_LABELS={'income':('合并利润表','母公司利润表'),'balance':('合并资产负债表','母公司资产负债表'),'cashflow':('合并现金流量表','母公司现金流量表')}
CHECK_FIELDS={'revenue':r'(?:其中：)?营业收入(?:合计)?','parentProfit':r'(?:1[.、])?归属于母公司(?:股东|所有者)的净利润.*','cost':r'(?:其中：)?营业成本','profit':r'(?:[一二三四五六七八九十]+、)?净利润.*','assets':r'资产(?:总计|合计)','liabilities':r'负债合计','operatingCash':r'经营活动产生的现金流量净额'}
CHECK_FIELDS.update({'receivables':r'应收账款','inventory':r'存货','salesExpense':r'销售费用',
                     'managementExpense':r'管理费用','researchExpense':r'研发费用','financeExpense':r'财务费用',
                     'capex':r'购建固定资产、无形资产和其他长期资产支付的现金'})

def quarter_period_caption(period):
 import datetime as dt
 day=dt.date.fromisoformat(period)
 starts={'03-31':'01-01','06-30':'04-01','09-30':'07-01','12-31':'10-01'}
 tail=period[5:]
 if tail not in starts:raise ValueError('单季期间需季度末日期')
 return '单季度计算区间：'+period[:4]+'-'+starts[tail]+'至'+period+'。半年或年度累计原文核对不替代相邻期差分输入核验。'

def checked_interpretation(entry,report):
 if not isinstance(entry,dict):raise ValueError('经营点评条目须为对象')
 if entry.get('basis') not in ['company-statement','research-explanation']:
  raise ValueError('经营点评须区分公司陈述与研究解释')
 questions=entry.get('followUp',[])
 if not isinstance(questions,list) or any(not isinstance(q,str) or not q.strip() for q in questions):
  raise ValueError('待核实问题须为非空文字列表')
 checked=check_entry(entry,{**report,'sha256':report['fileSha256']})
 checked['basis']=entry['basis']
 checked['followUp']=[q.strip() for q in questions]
 checked.update(validate_details(entry))
 if entry.get('conclusion') is not None:
  if not isinstance(entry['conclusion'],str) or not entry['conclusion'].strip() or len(entry['conclusion'])>180 or any(x in entry['conclusion'] for x in '\r\n<>'):
   raise ValueError('点评结论须为180字以内的单行文字')
  checked['conclusion']=entry['conclusion'].strip()
 if entry.get('title') is not None:
  if not isinstance(entry['title'],str) or not entry['title'].strip() or len(entry['title'])>80 or any(x in entry['title'] for x in '\r\n#[]<>'):
   raise ValueError('点评标题须为80字以内的单行文字')
  checked['title']=entry['title'].strip()
 return checked

def extreme_ratio_note(values):
 """Presentation warning only; preserve calculations and do not infer causes."""
 if any(value is not None and abs(value)>=10 for value in values):
  return '变动率绝对值达到或超过1000%，应结合基期绝对金额和正负方向解读；不能将其直接视为经营增速或现金质量改善。'
 return None

def sample_commentary(financial):
 lines=[quarter_period_caption(financial['period'])];groups=[]
 for g in financial['groups']:
  size=g['sampleSize'];entries=[]
  if type(size)!=int or size<1:raise ValueError('样本规模须为正整数')
  lines.append(g['group']+'：本次计算样本'+str(size)+'家，分类版本'+g['classificationVersion']+'，范围'+g['scope']+'，币种'+g['currency']+'。不同分类或报表范围分别比较，不合并为行业整体。')
  for key in ['revenue','parentProfit','operatingCash']:
   record=g.get('changes',{}).get(key,{}).get('yoy')
   if not record:continue
   valid=record['validCount'];missing=record['missingCount'];value=record['median']
   if type(valid)!=int or type(missing)!=int or valid<0 or missing<0:raise ValueError('有效缺失数量须为非负整数')
   if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):raise ValueError('样本中位数须为有限数或缺失')
   if (value is None)!=(valid==0):raise ValueError('中位数与有效样本数状态不一致')
   if valid+missing!=size or not 0<=valid<=size:raise ValueError('分组有效样本数与分组规模不一致')
   entry=dict(metric=key,period=financial['period'],comparison='yoy',median=value,validCount=valid,missingCount=missing,scope='declared-sample-only')
   if value is None:line='单季度'+FIELDS[key][2]+'同比资料不足，未计算样本中位数。'
   elif valid<2:line='单季度'+FIELDS[key][2]+'同比为'+format(value*100,'.2f')+'%，仅有1家公司有效，不能作横向比较。'
   else:line='单季度'+FIELDS[key][2]+'同比样本中位数为'+format(value*100,'.2f')+'%，有效'+str(valid)+'家。'
   if missing:line+='另有'+str(missing)+'家公司缺少该项比较数据，未计入中位数，也未按零处理。'
   note=extreme_ratio_note([value]);line+=(' '+note if note else '');lines.append(line);entry['text']=line;entries.append(entry)
  groups.append(dict(group=g['group'],classificationVersion=g['classificationVersion'],scope=g['scope'],currency=g['currency'],sampleSize=size,entries=entries))
 return lines,groups
def comparative_header_confirmed(lines,kind,period,parallel=False):
 """Require an ordered, explicitly labelled period header; never infer from row values."""
 year=int(period[:4])
 current=period;prior=str(year-1)+('-12-31' if kind=='balance' else period[4:])
 expected=[current,prior,current,prior] if parallel else [current,prior]
 for _,line in lines:
  compact=re.sub(r'\s+','',line)
  if kind=='balance':
   tokens=re.findall(r'(\d{4})年(\d{1,2})月(\d{1,2})日',compact)
   normalized=[f'{int(y):04d}-{int(m):02d}-{int(d):02d}' for y,m,d in tokens]
  else:
   tokens=re.findall(r'(\d{4})年(半年度|年度|1[—–-](?:\d{1,2})月)',compact)
   normalized=[]
   for y,suffix in tokens:
    m=6 if suffix=='半年度' else 12 if suffix=='年度' else int(re.search(r'\d+$',suffix[:-1]).group())
    last_day={3:31,6:30,9:30,12:31}.get(m)
    normalized.append(f'{int(y):04d}-{m:02d}-{last_day:02d}' if last_day else 'unsupported')
  if normalized==expected:return True
 # Bank flow tables explicitly label the six-month interval separately from the years.
 if kind!='balance' and period.endswith('-06-30'):
  for page,line in lines:
   if re.findall(r'(\d{4})年',line)==([str(year),str(year-1)]* (2 if parallel else 1)):
    if any(p==page and re.search(r'截至6月30日止(?:六|6)个月(?:期间)?',re.sub(r'\s+','',t)) for p,t in lines):return True
 # Some parallel tables put years and month/day labels on two consecutive header lines.
 if kind=='balance':
  for i,(page,line) in enumerate(lines[:-1]):
   years=re.findall(r'(\d{4})年',line)
   candidate=next(((p,t) for p,t in lines[i+1:i+4] if p==page and re.findall(r'\d{1,2}月\d{1,2}日',re.sub(r'\s+','',t))),None)
   if candidate is None:continue
   next_page,next_line=candidate
   dates=re.findall(r'(\d{1,2})月(\d{1,2})日',re.sub(r'\s+','',next_line))
   if page==next_page and years==[str(year),str(year-1)]*(2 if parallel else 1) and len(dates)==(4 if parallel else 2):
    if [f'{int(y):04d}-{int(m):02d}-{int(d):02d}' for y,(m,d) in zip(years,dates)]==expected:return True
 return False

def original_checks(archive,report,period,column="current"):
 if column not in ["current","comparative"]:raise ValueError("核验列无效")
 if report is None:report=dict(parseStatus='not-registered',error='本次没有该公司原文记录')
 if not isinstance(report,dict):raise ValueError('原文记录须为对象或明确缺失')
 if report.get('parseStatus')!='parsed':
  return [dict(metric=key,label=FIELDS[key][2],status='original-unavailable',column=column,
               observationPeriod=None,expectedCumulativeOrStock=None,original=[],
               reason='原文尚未解析：'+str(report.get('error') or report.get('parseStatus') or '状态未登记')) for key in CHECK_FIELDS]
 if archive['code']!=report['code'] or period!=report['period']:raise ValueError('原文与财务证券或期间不匹配')
 if report['asOf']>archive['asOf']:raise ValueError('原文截止日晚于财务截止日')
 sections={};found={};parallel=set()
 for kind,(start,end) in TABLE_LABELS.items():
  active=False;lines=[]
  for p in report['pages']:
   for line in p['text'].splitlines():
    compact=re.sub(r'\s+','',line)
    if re.fullmatch(r'(?:\d+[、.．])?(?:未经审计|经审计)?'+start,compact):active=True;found[kind]=True
    if active and re.fullmatch(r'(?:\d+[、.．])?(?:未经审计|经审计)?'+end.replace('母公司','(?:母公司|公司)?'),compact):active=False
    if active:lines.append((p['page'],line))
  if not lines:
   suffix={'income':'利润表','balance':'资产负债表','cashflow':'现金流量表'}[kind]
   selected=[]
   for p in report['pages']:
    compact=re.sub(r'\s+','',p['text'])
    title=any(re.fullmatch(r'(?:\d{4}年(?:半年度|年度))?合并及公司'+suffix+r'(?:[（(]续[）)])?',re.sub(r'\s+','',line)) for line in p['text'].splitlines())
    years=next((re.findall(r'(\d{4})年',line) for line in p['text'].splitlines() if len(re.findall(r'(\d{4})年',line))==4),[])
    if title and ('合并合并公司公司' in compact or '本集团本行' in compact) and years[:4]==[period[:4],str(int(period[:4])-1),period[:4],str(int(period[:4])-1)]:selected.extend((p['page'],line) for line in p['text'].splitlines())
   if selected:lines=selected;parallel.add(kind)
  sections[kind]=lines
 checks=[]
 for key,pattern in CHECK_FIELDS.items():
  kind,field,_,_=FIELDS[key];expected_period=period if column=='current' else str(int(period[:4])-1)+('-12-31' if kind=='balance' else period[4:]);expected,reason,refs=observation(archive,kind,expected_period,field);rows=[];column_conflicts=[]
  lines=sections[kind];units={m.group(1) for _,line in lines for m in re.finditer(r'单位[：:](元|千元|万元)(?:币种|$)',re.sub(r'\s+','',line))}
  units|={m.group(1) for _,line in lines for m in re.finditer(r'货币单位均以人民币(百万元|千元|万元|元)列示',re.sub(r'\s+','',line))}
  if kind in parallel:units|={m.group(1) for _,line in lines for m in re.finditer(r'金额单位(?:均)?为人民币(百万元|千元|万元|元)[）)]',re.sub(r'\s+','',line))}
  unit=next(iter(units)) if len(units)==1 else None;scale={'元':Decimal(1),'千元':Decimal(1000),'万元':Decimal(10000),'百万元':Decimal(1000000)}.get(unit)
  currencies={re.split(r'审计类型[：:]',m.group(1),maxsplit=1)[0] for _,line in lines for m in re.finditer(r'币种[：:]\s*([^\s]+)',line)}
  if currencies and currencies!={'人民币'}:unit=None;scale=None
  header_confirmed=(column=='current' and kind not in parallel) or comparative_header_confirmed(lines,kind,period,kind in parallel)
  has_note_column=any('项目附注' in re.sub(r'\s+','',line) for _,line in lines)
  for i,(page,line) in enumerate(lines):
   if has_note_column:line=re.sub(r'(?<!\S)\d+[（(]\d+[）)](?:[（(][a-z\d]+[）)])?(?=\s|$)','',line)
   if has_note_column:line=re.sub(r'(?<!\S)[一二三四五六七八九十]+[（(]\d+[）)](?:[（(]\d+[）)])?(?=\s|$)','',line)
   if has_note_column:line=re.sub(r'(?<!\S)[一二三四五六七八九十]+、[（(]\d+[）)](?=\s|$)','',line)
   line=re.sub(r'(?<!\w)[一二三四五六七八九十]+[、.]?\d+(?:[（(]\d+[）)])?(?:[（(][a-z][）)])?(?:,)?(?=\s|$)','',line)
   if kind in parallel:line=re.sub(r'[一二三四五六七八九十]+[（(]\d+[）)](?:[（(][a-z][）)])?(?:,)?','',line)
   if i+1<len(lines) and lines[i+1][0]==page and not re.search(r'\d[\d,]*\.\d{2}',line) and re.fullmatch(pattern,re.sub(r'\s+','',line)) and re.fullmatch(r'\s*-?\d[\d,]*(?:\.\d+)?\s+-?\d[\d,]*(?:\.\d+)?\s*',lines[i+1][1]):line+=' '+lines[i+1][1]
   if kind in parallel and re.fullmatch(pattern,re.sub(r'\s+','',line)) and i+1<len(lines) and lines[i+1][0]==page:
    following=re.sub(r'[（(]附注[一二三四五六七八九十]+[、,]\d+[）)]','',lines[i+1][1])
    if len(re.findall(r'-?\d[\d,]*',following))==4:line+=' '+following
   line=re.sub(r'(?<=\s)\d+[（(][a-z][）)](?=\s)','',line)
   number_pattern=r'(?<![\w.、])-?\d[\d,]*(?:\.\d+)?(?![\w.])'
   numbers=list(re.finditer(number_pattern,line))
   # Some PDFs wrap the comparative amount onto its own adjacent line.
   # Join only a recognized complete label, explicit two-period header and
   # decimal amount; never cross pages or borrow a named next row.
   if len(numbers)==1 and kind not in parallel and comparative_header_confirmed(lines,kind,period):
    prefix=re.sub(r'\s+','',line[:numbers[0].start()])
    if re.fullmatch(pattern,prefix) and re.fullmatch(r'-?\d[\d,]*\.\d{2}',numbers[0].group()) and i+1<len(lines) and lines[i+1][0]==page and re.fullmatch(r'\s*-?\d[\d,]*\.\d{2}\s*',lines[i+1][1]):
     line+=' '+lines[i+1][1];numbers=list(re.finditer(number_pattern,line))
   if len(numbers)<2:continue
   label=re.sub(r'\s+','',line[:numbers[0].start()])
   if kind in parallel:label=label.rstrip('(')
   label=re.sub(r'[一二三四五六七八九十]+[、.]?\d+(?:[（(]\d+[）)])?$','',label)
   # A complete amount row may precede the remaining words of its label.
   # Require a full known label after adding at most two text-only lines.
   if label and not re.fullmatch(pattern,label):
    extended=label
    for offset in (1,2):
     if i+offset>=len(lines) or lines[i+offset][0]!=page:break
     continuation=re.sub(r'\s+','',lines[i+offset][1])
     if not continuation or re.search(r'\d',continuation):break
     extended+=continuation
     if re.fullmatch(pattern,extended):label=extended;break
   # Wrapped ownership labels must remain distinct from total net profit.
   if kind=='income' and label.startswith('净利润') and i>0 and lines[i-1][0]==page:
    prefix=re.sub(r'\s+','',lines[i-1][1])
    if re.fullmatch(r'(?:1[.、])?归属于母公司(?:股东|所有者)的',prefix):label=prefix+label
   if not label and i>0 and i+1<len(lines) and lines[i-1][0]==page and lines[i+1][0]==page:
    before=re.sub(r'\s+','',lines[i-1][1]);after=re.sub(r'\s+','',lines[i+1][1])
    if not re.fullmatch(pattern,before) and re.fullmatch(pattern,before+after):label=before+after
   bank_parent=kind in parallel and key=='parentProfit' and label=='母公司股东' and i>0 and re.sub(r'\s+','',lines[i-1][1])=='净利润归属于：'
   bank_owner=key=='parentProfit' and label=='本行股东的净利润' and any('银行' in str(r['raw'].get('ORG_TYPE','')) for r in archive['tables']['income']['rows'])
   if re.fullmatch(pattern,label) or bank_parent or bank_owner:
    value_index=1 if kind not in parallel and has_note_column and len(numbers)>=3 and re.fullmatch(r'\d+',numbers[0].group()) else 0
    if kind in parallel or comparative_header_confirmed(lines,kind,period):
     if len(numbers)-value_index!=(4 if kind in parallel and not bank_parent else 2):
      column_conflicts.append(dict(page=page,label=label,numericColumnCount=len(numbers)-value_index));continue
    if column=='comparative':value_index+=1
    if value_index>=len(numbers) or not header_confirmed:continue
    raw=Decimal(numbers[value_index].group().replace(',',''));precision=Decimal(10)**raw.as_tuple().exponent
    if kind in parallel and numbers[value_index].start()>0 and line[numbers[value_index].start()-1]=='(' and line[numbers[value_index].end():].startswith(')'):raw=-raw
    negative_presentation=False
    if key=='cost' and raw<0 and kind not in parallel:
     # Require a consistent signed expense presentation, not a sign inferred from the expected value.
     expense_labels=['营业总成本','销售费用','管理费用'];confirmed=[]
     for expense_label in expense_labels:
      candidates=[]
      for _,context in lines:
       if re.match(r'\s*(?:[一二三四五六七八九十]+[、.])?'+expense_label+r'\s',context):
        values=re.findall(r'(?<![\w.])-\d[\d,]*(?:\.\d+)?(?![\w.])',context)
        if len(values)==2:candidates.append(values)
      confirmed.append(len(candidates)==1)
     negative_presentation=all(confirmed)
    deduction=key=='cost' and raw<0 and (kind in parallel or negative_presentation)
    normalized=abs(raw) if deduction else raw
    rows.append(dict(columnBasis=('comparative-consolidated' if column=='comparative' else 'current-consolidated-ownership-of-two' if bank_parent else 'first-current-consolidated-of-four' if kind in parallel else 'current-consolidated'),signBasis='expense-magnitude-from-signed-expense-presentation' if negative_presentation else 'expense-magnitude-from-parenthesized-deduction' if deduction else 'as-disclosed',page=page,label=label,reportedValue=str(raw),reportedUnit=unit,convertedValueCNY=str(normalized*scale) if scale else None,roundingToleranceCNY=str(max(Decimal('0.02'),precision*scale/2)) if scale else None))
  repeated_consistent=key=='profit' and len(rows)>1 and len({r['page'] for r in rows})==len(rows) and len({r['convertedValueCNY'] for r in rows})==1 and unit=='百万元' and any('银行' in str(r['raw'].get('ORG_TYPE','')) for r in archive['tables']['income']['rows'])
  status='missing';difference=None
  if reason:status='source-missing'
  elif not header_confirmed:status='period-unconfirmed'
  elif column_conflicts:status='column-ambiguous'
  elif not unit:status='unit-unconfirmed'
  elif len(rows)>1 and not repeated_consistent:status='ambiguous'
  elif len(rows)==1 or repeated_consistent:
   difference=str(Decimal(str(expected))-Decimal(rows[0]['convertedValueCNY']));status='matched' if abs(Decimal(difference))<=Decimal(rows[0]['roundingToleranceCNY']) else 'difference'
  checks.append(dict(repeatedConsistentDisclosure=repeated_consistent,column=column,observationPeriod=expected_period,columnConflicts=column_conflicts,metric=key,label=FIELDS[key][2],status=status,expectedCumulativeOrStock=expected,original=rows,difference=difference,scope=('合并报表比较列：资产负债表为上年末，利润及现金流为去年同期累计；不代表单季度同比基数全部核验' if column=='comparative' else '合并报表当前列；明确单位元/千元/万元/百万元换算人民币元，按披露精度比较；利润和现金流为报告累计'),inputs=refs))
 return checks

def original_check_description(check):
 comparative=check.get('column')=='comparative'
 labels={
  'original-unavailable':'原文未就绪，尚未执行字段原文核对；不判断公司未披露',
  'matched':'数据源数值与原文'+('比较列' if comparative else '本期列')+'在披露精度内一致',
  'difference':'数据源数值与原文存在差异，需复核重述、期间及口径',
  'missing':'未定位到可核验的字段行',
  'source-missing':'数据源未提供该项数值，无法完成交叉核验',
  'period-unconfirmed':'未明确确认数值列对应的报告期间，未采用该列',
  'column-ambiguous':'数值列数量与表头不一致，未选择核验值',
  'unit-unconfirmed':'未确认唯一金额单位，未换算核验',
  'ambiguous':'原文存在同名字段多行，保留歧义'}
 status=check['status']
 if status not in labels:raise ValueError('未知原文核验状态：'+status)
 text=labels[status]
 if any(row.get('signBasis')=='expense-magnitude-from-signed-expense-presentation' for row in check.get('original',[])):
  text+='；原文采用负数扣减式列示，费用行共同支持该版式，按费用金额比较并保留原始负号'
 if check.get('repeatedConsistentDisclosure'):text+='；银行利润表跨页重复披露数值一致，已保留全部页码'
 if check.get('difference') is not None:text+='，差额人民币'+check['difference']+'元（数据源减原文）'
 return text

def checked_comparisons(rows,reports,codes):
 if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows):raise ValueError('样本对照须为对象列表')
 result=[]
 for row in rows:
  ids=row.get('codes',[])
  if not isinstance(ids,list) or any(not isinstance(code,str) or not code.strip() for code in ids):raise ValueError('样本对照代码须为文字列表')
  if len(ids)<2 or len(ids)!=len(set(ids)) or not set(ids)<=codes:
   raise ValueError('样本对照需至少两家不重复的本次公司')
  if row.get('kind') not in ['agreement','difference','not-comparable']:
   raise ValueError('样本对照类型无效')
  if row.get('basis')!='research-explanation':
   raise ValueError('跨公司对照须标记研究解释，不当作公司直接陈述')
  refs=row.get('evidence',[])
  if not isinstance(refs,list) or any(not isinstance(x,dict) for x in refs):raise ValueError('样本依据须为对象列表')
  if {x.get('code') for x in refs}!=set(ids):
   raise ValueError('样本对照须引用每家参与公司的原文')
  checked=[]
  for ref in refs:
   report=reports[ref['code']]
   if report.get('parseStatus')!='parsed':raise ValueError('样本对照需要可解析原文')
   entry=check_entry(dict(text=row['text'],evidence=[ref]),{**report,'sha256':report['fileSha256']})
   checked.append(dict(code=ref['code'],**entry['evidence'][0]))
  result.append(dict(text=row['text'],kind=row['kind'],basis=row['basis'],codes=ids,evidence=checked,status='quote-located-not-causal-proof',underlyingSourceAssessment=underlying_source_assessment(ids,row.get('underlyingSources'))))
 return result

def report_index(original):
 rows=original.get('companies') if isinstance(original,dict) else None
 if not isinstance(rows,list):raise ValueError('原文结果须包含公司记录列表')
 result={}
 for row in rows:
  if not isinstance(row,dict) or not isinstance(row.get('code'),str) or not row['code'].strip():raise ValueError('原文公司记录缺明确证券代码')
  if row['code'] in result:raise ValueError('原文公司记录重复：'+row['code']+'；须先确认版本，不按顺序覆盖')
  result[row['code']]=row
 return result

def checked_profit_detail(company,row,base):
 for key,value in [('code',company['code']),('period',company['period']),('unit',company['metadata']['unit']),('currency',company['metadata']['currency']),('basis','consolidated-quarter')]:
  if row.get(key)!=value:raise ValueError('其他损益明细口径不一致：'+key)
 if company['metadata'].get('scope')!='consolidated':raise ValueError('其他损益明细只用于合并利润口径')
 return detail_residual(base,row.get('items'))

def resolve_input_paths(spec,base_dir):
 result=dict(spec)
 def resolve(value):
  if not isinstance(value,str) or not value.strip():raise ValueError('输入文件引用须为明确路径')
  path=Path(value)
  return str(path if path.is_absolute() else Path(base_dir)/path)
 for key in ('financialResult','originalResult'):result[key]=resolve(spec[key])
 for key in ('archives','quarterReviewResults'):
  if key in spec:
   if not isinstance(spec[key],list):raise ValueError('输入文件引用须为路径列表：'+key)
   result[key]=[resolve(path) for path in spec[key]]
 return result

def load_quarter_reviews(paths,financial,archives):
 if not isinstance(paths,list) or any(not isinstance(p,str) or not p.strip() for p in paths) or len(paths)!=len(set(paths)):raise ValueError('单季核验结果须为不重复的路径列表')
 from quarter_original_review import verified_saved_result
 companies={c['code']:c for c in financial['companies']};reviews={}
 for path in paths:
  saved=json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
  code=saved.get('code') if isinstance(saved,dict) else None
  if code not in companies or code in reviews:raise ValueError('单季核验主体重复或不在本次样本')
  reviews[code]=verified_saved_result(path,archives[code],companies[code]['metadata'],financial['period'])
 return reviews

def run(spec,out,base_dir=None):
 if base_dir is not None:spec=resolve_input_paths(spec,base_dir)
 out=Path(out)
 if out.exists():raise FileExistsError('输出已存在')
 input_bytes={key:Path(spec[key]).read_bytes() for key in ['financialResult','originalResult']}
 financial=json.loads(input_bytes['financialResult'].decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant);original=json.loads(input_bytes['originalResult'].decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant);reports=report_index(original)
 profit_details={}
 for row in spec.get('profitResidualDetails',[]):
  if not isinstance(row,dict) or row.get('code') in profit_details or row.get('code') not in {c['code'] for c in financial['companies']}:raise ValueError('其他损益明细主体重复或不在本次样本')
  profit_details[row['code']]=row
 original_bindings=bound_originals(original,spec['originalResult'])
 archives,archive_hashes=bound_archives(financial,spec['archives'])
 verify_financial_snapshot(financial,archives)
 quarter_reviews=load_quarter_reviews(spec.get('quarterReviewResults',[]),financial,archives)
 interpretations={}
 for supplied in spec.get('interpretations',[]):
  code=supplied['code']
  if code in interpretations or code not in {c['code'] for c in financial['companies']}:raise ValueError('经营点评公司重复或不在本次计算样本')
  report=reports.get(code)
  if not report or report.get('parseStatus')!='parsed':raise ValueError('经营点评需要可解析同期原文')
  entries=[]
  for entry in supplied['entries']:
   entries.append(checked_interpretation(entry,report))
  interpretations[code]=entries

 accounting_contexts={}
 for context in spec.get('accountingContexts',[]):
  code=context.get('code')
  if code in accounting_contexts or code not in {c['code'] for c in financial['companies']}:raise ValueError('会计依据主体重复或不在本次样本')
  report=reports.get(code)
  if not report or report.get('parseStatus')!='parsed':raise ValueError('会计依据需可解析报告')
  accounting_contexts[code]=accounting_validate(context,report)
 comparisons=checked_comparisons(spec.get('comparisons',[]),reports,{c['code'] for c in financial['companies']})
 source_links={b['code']:'sources/'+b['code']+'.pdf' for b in original_bindings}
 def page_links(code,pages):
  return '、'.join('[PDF第'+str(page)+'页]('+source_links[code]+'#page='+str(page)+')' for page in pages)
 lines=['# 公司与行业财报点评','', '报告期截至'+financial['period']+'。以下评价基于指定公司资料，不等于完整行业覆盖或未来盈利预测。']
 items=[]
 coverage=financial.get('coverage',{});failures=financial.get('failures',[])
 lines+=['本次请求'+str(coverage.get('requested','未登记'))+'家公司，完成财务计算'+str(len(financial['companies']))+'家，未完成'+str(len(failures))+'家；分组统计仅使用完成计算且该项有效的样本。']
 for failure in failures:lines.append('未完成公司 '+failure['code']+'：'+failure['reason']+'。未纳入本次分组统计。')
 for c in financial['companies']:
  report=reports.get(c['code']);checks=original_checks(archives[c['code']],report,c['period']);item=dict(code=c['code'],checks=checks,reportHash=report.get('fileSha256') if report else None,reportSource=report.get('metadata') if report else None,evidence=report.get('evidence',{}) if report else {},gaps=list(c.get('gaps',[])))
  item['metadata']=dict(c['metadata']);item['metadataBasis']='input-declared-original-verification-separate'
  scope_label={'consolidated':'合并报表','parent':'母公司报表'}.get(c['metadata']['scope'],c['metadata']['scope'])
  lines+=['','## '+c['metadata'].get('name',c['code']),'计算口径：'+c['metadata']['currency']+'，金额单位为'+c['metadata']['unit']+'，'+scope_label+'。原文核对结果见附录；未确认的口径单列。']
  for warning in metadata_unit_warnings(c['metadata']):
   if warning not in item['gaps']:item['gaps'].append(warning)
   lines.append(warning)
  item['comparativeChecks']=original_checks(archives[c['code']],report,c['period'],column='comparative')
  item['reportMetadataWarnings']=report_metadata_warnings(report)
  item['gaps']+=item['reportMetadataWarnings'];lines+=item['reportMetadataWarnings']
  item['incomeBasisWarnings']=income_basis_warnings(archives[c['code']],c['period'])
  for warning in item['incomeBasisWarnings']:lines.append('收入口径提示：'+warning['warning'])
  item['comparabilityWarnings']=comparability_warnings(report)
  for warning in item['comparabilityWarnings']:
   lines.append('跨期口径提示：'+warning['warning']+'（'+page_links(c['code'],[warning['page']])+'）。');item['gaps'].append(warning['warning'])
  item['interpretations']=interpretations.get(c['code'],[])
  item['gaps'] += list(dict.fromkeys('待核实问题：'+q for entry in item['interpretations'] for q in entry.get('followUp',[])))
  item['researchStatus']='evidence-backed-appraisal' if item['interpretations'] else 'data-review-only'
  item['appraisalCoverage']=appraisal_coverage(item['interpretations'])
  if item['interpretations']:
   lines+=['','### 研究判断与经营评价','以下依据本报告期原文；累计期间说明不自动解释单季度差分。引句定位不证明因果判断正确。']
   for entry in sorted(item['interpretations'],key=lambda e:0 if e.get('role')=='overall' else 1):
    if entry.get('title'):lines+=['','#### '+entry['title'],'']
    if entry.get('conclusion'):lines+=['> '+entry['conclusion'],'']
    if entry.get('coreTension'):lines.append('核心矛盾：'+entry['coreTension'])
    if entry.get('judgmentBoundary'):lines.append('判断范围：'+entry['judgmentBoundary'])
    basis='公司在报告中的陈述' if entry['basis']=='company-statement' else '研究解释（需复核）'
    pages=page_links(c['code'],sorted({e['page'] for e in entry['evidence']}));lines.append(('论据（'+basis+'）：' if entry.get('conclusion') else basis+'：')+entry['text']+'（原文'+pages+'）。')
    if entry.get('alternatives'):lines.append('其他可能解释：'+'；'.join(x.rstrip('。；;') for x in entry['alternatives'])+'。这些解释尚未被逐一排除。')
    if entry.get('positioning'):lines.append('研究定位：'+entry['positioning'])
    if entry.get('invalidationSignal'):lines.append('改变判断的条件：'+entry['invalidationSignal'])
    if entry.get('followUp'):
     lines+=['','待核实问题（尚未取得验证结论）：','']+['- '+q for q in entry['followUp']]+['']

  else:
   lines+=['','### 研究判断尚未完成','本次仅完成财务变化整理与原文核对，尚无有原文依据的经营评价。不能把核验通过当作投资逻辑已经成立。']

  lines+=['','### 单季度财务变化',quarter_period_caption(c['period'])]
  item['quarterOriginalChecks']=quarter_reviews.get(c['code'])
  if item['quarterOriginalChecks']:
   lines+=['','#### 单季计算输入核验','以下逐项核对本期、同比及环比所用累计输入；数值匹配不证明重述、会计政策或合并范围完全可比。']
   labels={'supported-inputs-matched':'所需输入数值已匹配','supported-inputs-matched-with-comparability-warning':'数值匹配，跨期口径仍待复核','not-verified':'所需输入尚未完整核验'}
   for field in item['quarterOriginalChecks']['fields']:
    lines.append(field['label']+'：'+'；'.join(label+' '+labels[part['status']] for label,part in [('本期',field['parts']['current']),('同比基数',field['parts']['yoy']),('环比基数',field['parts']['qoq'])])+'。')
    refs=[];bound_periods={b['period'] for b in item['quarterOriginalChecks']['originalBindings']}
    for part in field['parts'].values():
     for dep in part['dependencies']:
      if dep['period'] in bound_periods:
       refs.extend('['+dep['period']+'原文第'+str(page)+'页](sources/'+c['code']+'-'+dep['period']+'.pdf#page='+str(page)+')' for page in dep['pages'])
    if refs:lines.append('输入原页：'+'、'.join(dict.fromkeys(refs))+'。')
   for warning in item['quarterOriginalChecks']['comparabilityWarnings']:lines.append(warning['period']+'跨期口径提示：'+warning['warning'])
   for warning in item['quarterOriginalChecks']['reportMetadataWarnings']:lines.append(warning['period']+'：'+warning['warning'])
  else:lines.append('本次未关联相邻期输入核验结果；以下单季变化不据本期原文匹配认定全部输入已获原文确认。')
  for key in ['revenue','parentProfit','operatingCash']:
   m=c['metrics'][key];current=m['current']['value'];y=m['yoy'];q=m['qoq'];lines.append(m['label']+'本季度为'+(format(current,',.2f')+'（'+c['metadata']['unit']+'）' if current is not None else '缺失')+'。同比'+(format(y['value']*100,'.2f')+'%' if y['value'] is not None else y['reason'])+'，环比'+(format(q['value']*100,'.2f')+'%' if q['value'] is not None else q['reason'])+'。')
  ratio_note=extreme_ratio_note([c['metrics'][key][kind]['value'] for key in ['revenue','parentProfit','operatingCash'] for kind in ['yoy','qoq']])
  if ratio_note:lines.append(ratio_note)
  lines+=applicability_notes(c)+c['signals']
  item['accountingContext']=accounting_contexts.get(c['code'])
  lines+=['']+accounting_paragraphs(item['accountingContext'])
  item['profitChangeBridge']=profit_bridge(c)
  item['profitResidualDetail']=checked_profit_detail(c,profit_details[c['code']],item['profitChangeBridge']) if c['code'] in profit_details else None
  lines+=['']+bridge_paragraphs(item['profitChangeBridge'],item['profitResidualDetail'])
  if not report or report.get('parseStatus')!='parsed':
   lines+=['','### 原文核验尚未完成','原文未就绪，字段原文核对尚未执行。已有计算不等于公告原文已确认，也不说明公司没有披露；需补取得与解析记录后再核验。']
  if report and report.get('parseStatus')=='parsed':
   lines+=['','### 原文核对附录']
   meta=report.get('metadata',{});lines.append('同期报告已获取并匹配证券代码与报告期。'+('[报告原文]('+meta['url']+')' if meta.get('url') else '来源为用户提供文件。'))
   lines.append('下面核对的是本报告期累计/期末原值，不是由相邻报告差分得到的单季值；单季计算依赖其他期数据，不能据此声称所有计算已获原文确认。')
   for x in checks:
    pages=page_links(c['code'],[r['page'] for r in x['original']])
    lines.append(x['label']+'：'+original_check_description(x)+('，'+pages if pages else '')+'。')
    if x['status']!='matched':item['gaps'].append(x['label']+'本期列未通过核验：'+original_check_description(x))
   lines+=['','### 比较列核验','资产负债表比较上年末，利润与现金流比较去年同期累计；这不等于单季度同比的全部输入均已核验。']
   for x in item['comparativeChecks']:
    pages=page_links(c['code'],[r['page'] for r in x['original']]);lines.append(x['label']+'（'+x['observationPeriod']+'）：'+original_check_description(x)+('，'+pages if pages else '')+'。')
    if x['status']!='matched':item['gaps'].append(x['label']+'比较列未通过核验：'+original_check_description(x))
   for category,hits in item['evidence'].items():
    if hits:lines.append(category+'：原文线索见PDF第'+'、'.join(str(n) for n in sorted({h['page'] for h in hits}))+'页，内容与本季数字的因果关系仍需研究员结合上下文确认。')
    else:item['gaps'].append(category+'未取得有效文本线索')
  else:lines.append('同期报告未完成文本解析，不生成订单、供需或未来展望。');item['gaps'].append('原文缺失或解析未完成')
  items.append(item)
 lines+=['','## 样本比较与待核实问题']
 comparison_lines,group_commentary=sample_commentary(financial);lines+=comparison_lines
 if comparisons:
  lines+=['','### 经营与风险对照','以下为有原文依据的研究解释，不代表行业共识或已验证因果关系。']
  for row in comparisons:
   refs='、'.join(ref['code']+' '+page_links(ref['code'],[ref['page']]) for ref in row['evidence'])
   lines.append(row['text']+'（'+refs+'）。')
   if row.get('underlyingSourceAssessment'):
    u=row['underlyingSourceAssessment'];lines.append(u['note']+('共同登记来源：'+'、'.join(u['sharedDeclaredSources'])+'。' if u['sharedDeclaredSources'] else '')+'原始数据来源尚未外部核验。')
 lines+=['经营评价区分公司陈述与研究解释；原文引句可定位，不等于因果关系已得到证明。收入增长来自量、价、并购或产品结构的比例，未取得充分证据时不作判断。行业展望应作为另有证据支持的假设，不由本报告自动生成。','','## 资料缺口']
 gap_lines=[c['code']+'：'+gap.rstrip('。')+'。' for c in items for gap in c['gaps']]
 lines+=gap_lines or ['本次支持字段未登记额外取数缺口；不代表完整报表、业务因果、估值或所有比较口径已经核验。研究范围及未验证问题仍以上文为准。']
 quarter_files=[]
 for code,review in quarter_reviews.items():
  for binding in review['originalBindings']:
   quarter_files.append(dict(code=code,period=binding['period'],path='sources/'+code+'-'+binding['period']+'.pdf',originalPath=binding['path'],sha256=binding['sha256']))
 result=dict(coverage=coverage,failures=failures,period=financial['period'],companies=items,groupCommentary=group_commentary,comparisons=comparisons,quarterSourceFiles=quarter_files,sourceFiles=[dict(code=b['code'],path=source_links[b['code']],sha256=b['sha256']) for b in original_bindings],archiveHashes=archive_hashes,originalBindings=original_bindings,inputHashes={k:hashlib.sha256(input_bytes[k]).hexdigest() for k in ['financialResult','originalResult']},limitations=financial['limitations']);result['envelopeSha256']=hashlib.sha256(json.dumps(result,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf8')).hexdigest()
 snapshots=[]
 for binding in original_bindings:
  raw=Path(binding['path']).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=binding['sha256']:raise ValueError('交付前原PDF变化，需重新核验')
  snapshots.append((source_links[binding['code']],raw))
 for binding in quarter_files:
  raw=Path(binding['originalPath']).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=binding['sha256']:raise ValueError('交付前相邻期PDF变化，需重新核验')
  snapshots.append((binding['path'],raw))
 for key,raw in input_bytes.items():
  if Path(spec[key]).read_bytes()!=raw:raise ValueError('交付前输入档案变化，需重新计算')
 text='\n'.join(lines);html=render(text,title='公司与行业财报点评');payload=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
 out.mkdir(parents=True);(out/'sources').mkdir()
 for path,raw in snapshots:(out/path).write_bytes(raw)
 (out/'公司与行业点评.md').write_text(text,encoding='utf8');(out/'公司与行业点评.html').write_text(html,encoding='utf8');(out/'result.json').write_text(payload,encoding='utf8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();run(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.out_dir,base_dir=a.input.resolve().parent)
