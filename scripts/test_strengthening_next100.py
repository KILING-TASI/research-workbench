"""100 explicitly enumerated contract checks; synthetic, not 100 live-market validations."""
import copy,json,unittest
from company_one_page import build,markdown
from research_report_plan import plan
from research_brief_html import safe_url,render
from collection_validation import day,market_rows,unique_pairs,reject_constant
BASE={'asOf':'2026-09-30','identity':{'name':'测试主体','market':'CN','code':'000333'}}
ITEM={'text':'有来源的陈述','observedAt':'2026-06-30','publishedAt':'2026-08-29','sourceUrl':'https://example.org/report.pdf','locator':'PDF第7页','basis':'source-statement'}
CASES=[]
def add(group,label,fn):CASES.append((group,label,fn))
def company(field,value):
 s=copy.deepcopy(BASE);s[field]=value;return build(s)
def entry(field,value,section='financial'):
 s=copy.deepcopy(BASE);i=copy.deepcopy(ITEM);i[field]=value;s[section]=[i];return build(s)
def bad(fn):
 try:fn()
 except ValueError:return
 raise AssertionError('invalid input accepted')
def eq(a,b):
 if a!=b:raise AssertionError(str(a)+' != '+str(b))
for label,change in [('root-list',[]),('root-null',None),('identity-list',{'identity':[]}),('identity-null',{'identity':None}),('name-number',{'identity':{'name':1,'code':'000333','market':'CN'}}),('name-blank',{'identity':{'name':' ','code':'000333','market':'CN'}}),('code-number',{'identity':{'name':'测试','code':333,'market':'CN'}}),('code-blank',{'identity':{'name':'测试','code':' ','market':'CN'}}),('market-unknown',{'identity':{'name':'测试','code':'000333','market':'XX'}}),('flag-string',{'deepResearch':'false'})]:
 def run(change=change):
  s=copy.deepcopy(BASE);s.update(change) if isinstance(change,dict) else None;bad(lambda:build(s if isinstance(change,dict) else change))
 add('identity',label,run)
for v in ['2026-9-30','2026-02-30','2026-13-01','2026-00-01','2026-09-00','2026-09-31','20260930','2026-09-30T00:00:00',None,True]:add('date',repr(v),lambda v=v:bad(lambda:day(v)))
for v in ['http://example.org/a','https://user:pw@example.org/a','https://example.org:bad/a','https://example.org:99999/a','https://example.org/ a','https://example.org/\t','https://example.org/\x00','//example.org/a','file:///report.pdf',None]:add('source',repr(v),lambda v=v:bad(lambda:entry('sourceUrl',v)))
for field,value in [('locator',[]),('locator',{}),('locator',' '),('locator',True),('unit',[]),('unit',{}),('unit',' '),('unit',1),('value',True),('value',float('inf'))]:
 def run(field=field,value=value):
  s=copy.deepcopy(BASE);i=copy.deepcopy(ITEM);i.update(value=1,unit='元');i[field]=value;s['financial']=[i];bad(lambda:build(s))
 add('locator-unit',field+repr(value),run)
for field,value in [('basis','source-statement'),('basis','research-explanation'),('assumptions',[]),('assumptions','需求'),('assumptions',[None]),('assumptions',[' ']),('targetPeriod','2026-09-30'),('targetPeriod','2025-12-31'),('targetPeriod',None),('targetPeriod','2027-02-30')]:
 def run(field=field,value=value):
  s=copy.deepcopy(BASE);i=copy.deepcopy(ITEM);i.update(basis='assumption',assumptions=['需求不变'],targetPeriod='2027-12-31');i[field]=value;s['forecast']=[i];bad(lambda:build(s))
 add('forecast',field+repr(value),run)
P={'asOf':'2026-09-30','kind':'stock','subject':'测试','code':'000333'}
for label,extra,expected in [('peer-context',{'question':'对比同行解释公司估值'},'planned-not-executed'),('supplier-context',{'question':'分析两家公司客户关系','kind':'stock'},'planned-not-executed'),('two-etf',{'kind':'etf','question':'两只ETF对比'},'use-existing-multi-object-entry'),('screen',{'question':'筛选公司'},'use-existing-multi-object-entry'),('batch',{'question':'批量诊断'},'use-existing-multi-object-entry'),('explicit-many',{'codes':['000333','600519']},'use-existing-multi-object-entry'),('single-list',{'codes':['000333']},'needs-identity'),('fund-etf',{'kind':'fund','question':'ETF一页纸'},'needs-kind-confirmation'),('missing-code',{'code':None},'needs-identity'),('industry',{'kind':'concept','question':'概念产业研究'},'planned-not-executed')]:
 def run(extra=extra,expected=expected):s=dict(P,**extra);eq(plan(s)['status'],expected)
 add('routing',label,run)
for v in ['javascript:alert(1)','data:text/html,x','//evil.example/a','https://example.org:bad','https://example.org:99999','https://u:p@example.org','https://example.org/\t','https://example.org/ a','C:/secret','\\server/share']:add('html-link',repr(v),lambda v=v:eq(safe_url(v),False))
ROW={'date':'2026-09-01','open':10,'close':11,'high':12,'low':9,'volume':100,'amount':1000}
for field,value in [('open',True),('close',0),('high',8),('low',13),('volume',-1),('amount',float('nan')),('date','2026-02-30'),('open',float('inf')),('volume','100'),('amount',False)]:
 def run(field=field,value=value):r=dict(ROW);r[field]=value;bad(lambda:market_rows('history',[r]))
 add('market-integrity',field+repr(value),run)
for raw in ['{"a":1,"a":2}','{"x":{"a":1,"a":2}}','{"v":NaN}','{"v":Infinity}','{"v":-Infinity}','{"a":null,"a":0}','{"a":true,"a":false}','{"x":[{"a":1,"a":2}]}','{"v":0,"v":1}','{"a":{"x":1},"a":{"x":2}}']:add('json-contract',raw,lambda raw=raw:bad(lambda:json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant)))
for label,extra in [('codes-string',{'codes':'000333'}),('codes-null',{'codes':None}),('codes-empty-item',{'codes':['']}),('codes-number',{'codes':[333]}),('codes-duplicate',{'codes':['000333','000333']}),('subjects-string',{'subjects':'测试'}),('subjects-number',{'subjects':[1]}),('subjects-blank',{'subjects':[' ']}),('subjects-duplicate',{'subjects':['测试','测试']}),('profile-conflict-multi',{'codes':['000333','600519'],'profile':'fund'})]:add('request-integrity',label,lambda extra=extra:bad(lambda:plan(dict(P,**extra))))
assert len(CASES)==100
class Tests(unittest.TestCase):pass
for n,(group,label,fn) in enumerate(CASES,1):
 def test(self,fn=fn):fn()
 test.__doc__=group+' / '+label
 setattr(Tests,'test_'+str(n).zfill(3)+'_'+group.replace('-','_'),test)
if __name__=='__main__':unittest.main()
