"""Distinguish an explicitly absent report benchmark from missing extraction."""
import re

def inspect(pages):
 if not isinstance(pages,list):raise ValueError("基准原文页面须为列表")
 evidence=[];seen=set()
 for page in pages:
  if not isinstance(page,dict) or type(page.get("page"))!=int or page["page"]<1 or not isinstance(page.get("text"),str):raise ValueError("基准原文页面结构无效")
  if page["page"] in seen:raise ValueError("基准原文物理页重复")
  seen.add(page["page"])
 for page in pages:
  lines=page['text'].splitlines()
  for i,line in enumerate(lines):
   compact=re.sub(r'\s+','',line)
   if re.fullmatch(r'(?:业绩比较基准)?本基金(?:无|未规定|未设定)业绩比较基准[。.]?',compact) or re.fullmatch(r'注[：:]本基金(?:未规定|未设定)业绩比较基准[。.]?',compact):
    evidence.append(dict(page=page['page'],quote=line,status='explicitly-not-defined'))
   elif compact.startswith('业绩比较基准'):
    if compact in ['业绩比较基准','业绩比较基准：','业绩比较基准:'] and i+1<len(lines):
     following=re.sub(r'\s+','',lines[i+1])
     if '%' in following and ('指数' in following or '收益率' in following):line=line+'\n'+lines[i+1];compact=re.sub(r'\s+','',line)
    value=re.sub(r'^业绩比较基准[：:]?','',compact)
    # Numeric benchmark formula is a locator, not a parsed/validated return series.
    if '%' in value and ('指数' in value or '收益率' in value):evidence.append(dict(page=page['page'],quote=line,formulaText=value,status='formula-located-not-verified'))
 statuses={r['status'] for r in evidence}
 formulas={r['formulaText'] for r in evidence if r['status']=='formula-located-not-verified'}
 status='conflicting-report-statements' if len(statuses)>1 or len(formulas)>1 else next(iter(statuses)) if statuses else 'not-located'
 return dict(status=status,evidence=evidence,distinctLocatedFormulaCount=len(formulas),formulaComparisonScope='文字差异待复核，不自动判断经济等价、适用份额或有效版本',benchmarkReturns=None,limitation='仅原文段落定位，不证明合同版本有效性；报告未设基准时不套用指数。用户自定义基准须另声明，不能称合同基准。')
