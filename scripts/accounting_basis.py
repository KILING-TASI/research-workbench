"""Bind declared accounting/audit context to actual report quotes."""
from research_report_reading import check_entry
import re
STATES={'unknown':'本期审计或审阅状态尚未确认','audited':'原文声明本期已审计','reviewed':'原文声明本期已审阅；不称审计意见','unaudited':'原文声明本期未经审计'}
def validate(context,report):
 if not isinstance(context,dict) or not isinstance(report,dict):raise ValueError('会计依据与报告须为对象')
 state=context.get('auditStatus','unknown')
 if not isinstance(state,str) or state not in STATES:raise ValueError('审计状态无效')
 framework=context.get('framework')
 if framework is not None and (not isinstance(framework,str) or not framework.strip()):raise ValueError('编制基础须为非空文字')
 refs=context.get('evidence',[])
 if not isinstance(refs,list) or any(not isinstance(x,dict) or type(x.get('page'))!=int or x['page']<1 or not isinstance(x.get('quote'),str) for x in refs):raise ValueError('会计依据须为物理页码与引句对象数组')
 if (state!='unknown' or framework) and not refs:raise ValueError('会计或审计声明需要原文依据')
 if refs:
  checked=check_entry(dict(text='会计与审计依据',evidence=refs),{**report,'sha256':report['fileSha256']})
  refs=checked['evidence']
 if state!='unknown':
  text='；'.join(re.sub(r'\s+','',x['quote']) for x in refs)
  negative=bool(re.search(r'未经[^。；]{0,80}审计|尚未审计|未审计',text))
  positive=bool(re.search(r'已经审计|已审计|经[^。；]{0,80}审计',text)) and not negative
  reviewed=bool(re.search(r'已审阅|已经审阅|经[^。；]{0,80}审阅',text)) and not bool(re.search(r'未经[^。；]{0,80}审阅|未审阅',text))
  if not {'unaudited':negative,'audited':positive,'reviewed':reviewed}[state]:raise ValueError('引句未明确支持所声明的审计/审阅状态；请保留unknown或补充本期直接声明')
 return dict(auditStatus=state,framework=framework,evidence=refs,status='quote-located-awaiting-applicability-review' if refs else 'not-reviewed')
def paragraphs(context):
 if not context:return ['### 会计与审计依据','本次尚未核对报告编制基础、具体会计政策及本期审计或审阅状态；数值一致与会计处理合规分别判断。']
 return ['### 会计与审计依据',STATES[context['auditStatus']]+'。'+('编制基础：'+context['framework']+'。' if context.get('framework') else '报告编制基础尚未确认。'),'依据PDF物理第'+'、'.join(str(x) for x in sorted({e['page'] for e in context['evidence']}))+'页；引句定位不自动核实审计状态分类，须结合原文语义复查。','以上为原文声明定位，具体规则适用性和会计处理仍需核对；本工具不出具审计意见。']
