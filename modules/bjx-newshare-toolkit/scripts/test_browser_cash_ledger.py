from validation_resources import fixture_path
"""Execute pure browser ledger in Node and compare to independent Decimal engine."""
import json, subprocess, unittest
from copy import deepcopy
from pathlib import Path
from decimal import Decimal
from cash_repo_ledger import run

class BrowserLedger(unittest.TestCase):
 def test_cross_engine_money_and_conflicts(self):
  assets=Path(__file__).resolve().parents[1]/'assets'
  base=json.loads((assets/'cash-plan-example.json').read_text(encoding='utf-8'))
  cases=[base]
  conflict=deepcopy(base);conflict['repos'][0]['principal']='80000';cases.append(conflict)
  pending=deepcopy(base);pending['end']='2026-10-10';cases.append(pending)
  same=deepcopy(base);same['repos'][0].update(tradeDate='2026-10-12',firstSettlementDate='2026-10-12',principal='90000');cases.append(same)
  rounding=deepcopy(base);rounding['repos'][0].update(principal='365',annualRatePct='0.5',commission='0');cases.append(rounding)
  js="const fs=require('fs'),m=require(process.argv[1]);console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(m.run)))"
  actual=json.loads(subprocess.check_output(['node','-e',js,str(assets/'cash-ledger.js')],input=json.dumps(cases).encode()))
  for spec,result in zip(cases,actual):
   expected=run(spec)
   for key in ['endCash','minimumCash','additionalFundsRequired']:
    self.assertEqual(Decimal(expected[key]),Decimal(result[key]))
   self.assertEqual(expected['feasible'],result['feasible'])
   self.assertEqual(len(expected['unsettledEvents']),len(result['unsettledEvents']))
   for a,b in zip(expected['repos'],result['repos']):
    self.assertEqual(a['actualAccrualDays'],b['actualAccrualDays'])
    self.assertEqual(Decimal(a['grossInterest']),Decimal(b['grossInterest']))
 def test_markup_connected(self):
  assets=Path(__file__).resolve().parents[1]/'assets'
  text=fixture_path(assets,'bjx-panel.html').read_text(encoding='utf-8')
  self.assertEqual(text.count('id="ledgerFile"'),1)
  self.assertLess(text.index('src="cash-ledger.js"'),text.index('src="bjx-workbench.js"'))
  self.assertIn("$('ledgerFile').onchange",(assets/'bjx-workbench.js').read_text(encoding='utf-8'))
 def test_both_engines_reject_ambiguous_input(self):
  assets=Path(__file__).resolve().parents[1]/'assets'
  base=json.loads((assets/'cash-plan-example.json').read_text(encoding='utf-8'));cases=[]
  for key,value in [('capital','1.001'),('capital','1e5'),('start','20261001')]:
   s=deepcopy(base);s[key]=value;cases.append(s)
  for key,value in [('annualRatePct','1.1234567'),('id',''),('principal','100.001')]:
   s=deepcopy(base);s['repos'][0][key]=value;cases.append(s)
  for missing in [False,True]:
   s=deepcopy(base)
   if missing:s['repos'][0].pop('commission')
   else:s['repos'][0]['commission']=None
   cases.append(s)
  for s in cases:
   with self.assertRaises(ValueError):run(s)
  js="const fs=require('fs'),m=require(process.argv[1]);console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(s=>{try{m.run(s);return false}catch(e){return true}})))"
  actual=json.loads(subprocess.check_output(['node','-e',js,str(assets/'cash-ledger.js')],input=json.dumps(cases).encode()))
  self.assertEqual(actual,[True]*len(cases))
 def test_uploaded_json_rejects_duplicate_and_overflow_values(self):
  assets=Path(__file__).resolve().parents[1]/'assets'
  texts=['{"capital":"100","capital":"200"}','{"repos":[{"principal":"1","princ\\u0069pal":"2"}]}','{"rate":1e400}']
  js="const m=require(process.argv[1]),fs=require('fs');console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(t=>{try{m.parsePlan(t);return false}catch(e){return true}})))"
  self.assertEqual(json.loads(subprocess.check_output(['node','-e',js,str(assets/'cash-ledger.js')],input=json.dumps(texts).encode())),[True]*len(texts))
 def test_uploaded_normal_plan_and_browser_parser_parity(self):
  root=Path(__file__).resolve().parents[3];assets=Path(__file__).resolve().parents[1]/'assets'
  shared=(root/'scripts/strict_json.js').read_text(encoding='utf-8');expected=shared[shared.index('function parse(text)'):shared.index('module.exports=')].replace('function parse(text)','function parsePlan(text)',1)
  self.assertIn(expected,(assets/'cash-ledger.js').read_text(encoding='utf-8'))
  self.assertIn('BjxCashLedger.run(BjxCashLedger.parsePlan(text))',(assets/'bjx-workbench.js').read_text(encoding='utf-8'))
  js="const m=require(process.argv[1]),fs=require('fs');console.log(JSON.stringify(m.run(m.parsePlan(fs.readFileSync(process.argv[2],'utf8')))))"
  actual=json.loads(subprocess.check_output(['node','-e',js,str(assets/'cash-ledger.js'),str(assets/'cash-plan-example.json')]))
  base=json.loads((assets/'cash-plan-example.json').read_text(encoding='utf-8'));self.assertEqual(Decimal(actual['endCash']),Decimal(run(base)['endCash']))
 def test_only_latest_uploaded_file_can_publish(self):
  assets=Path(__file__).resolve().parents[1]/'assets';s=(assets/'bjx-workbench.js').read_text(encoding='utf-8')
  start=s.index('let ledgerImportVersion=0;');end=s.index('\n',s.index("$('ledgerFile').onchange",start));handler=s[start:end]
  harness="const elems={ledgerRows:{count:1,replaceChildren(){this.count=0}},ledgerExcluded:{textContent:'old'},ledgerSummary:{textContent:'old'},ledgerFile:{files:[]}},$=id=>elems[id],BjxCashLedger={parsePlan:JSON.parse,run:x=>x};function renderCashLedger(x){elems.ledgerSummary.textContent=x.label;elems.ledgerRows.count=1;}"
  scenario=";(async()=>{let resolve,reject;const old={size:10,text:()=>new Promise((a,b)=>{resolve=a;reject=b})},latest={size:10,text:async()=>JSON.stringify({label:'latest'})};elems.ledgerFile.files=[old];const pending=elems.ledgerFile.onchange();elems.ledgerFile.files=[latest];await elems.ledgerFile.onchange();if(process.argv[1]==='reject')reject(Error('old failed'));else resolve(JSON.stringify({label:'old'}));await pending;console.log(JSON.stringify({summary:elems.ledgerSummary.textContent,rows:elems.ledgerRows.count}));})().catch(e=>{console.error(e);process.exit(1)})"
  for mode in ['resolve','reject']:
   actual=json.loads(subprocess.check_output(['node','-e',harness+handler+scenario,mode]));self.assertEqual(actual,{'summary':'latest','rows':1})
 def test_pending_upload_cannot_replace_generated_cash_plans(self):
  assets=Path(__file__).resolve().parents[1]/'assets';s=(assets/'bjx-workbench.js').read_text(encoding='utf-8')
  start=s.index('let ledgerImportVersion=0;');end=s.index('\n',s.index("$('ledgerFile').onchange",start));upload=s[start:end]
  harness="const elems={ledgerRows:{replaceChildren(){}},ledgerExcluded:{textContent:''},ledgerSummary:{textContent:''},ledgerFile:{files:[]},annualCapital:{value:'100'},annualYear:{value:'2026'},repoRate:{value:'1'},repoUse:{value:'50'},ledgerAuto:{},ledgerRepo:{}},$=id=>elems[id],data={fetchedAt:'2026-10-06'},BjxCashLedger={parsePlan:JSON.parse,run:x=>x},BjxCashPlan={generate:()=>({ledger:{label:'auto'},sampleCount:0,plan:{issues:[]},excluded:[]})},BjxRepoPlan={schedule:()=>({ledger:{label:'repo'},plan:{repos:[]},incrementalEndCash:'0'})};function renderCashLedger(x){elems.ledgerSummary.textContent=x.label;}"
  for key,label in [('ledgerAuto','auto'),('ledgerRepo','repo')]:
   i=s.index("$('"+key+"').onclick");handler=s[i:s.index('\n',i)]
   for failure in [False,True]:
    finish="reject(Error('obsolete'))" if failure else "resolve(JSON.stringify({label:'old'}))"
    scenario=";(async()=>{let resolve,reject;elems.ledgerFile.files=[{size:10,text:()=>new Promise((a,b)=>{resolve=a;reject=b})}];const pending=elems.ledgerFile.onchange();elems."+key+".onclick();"+finish+";await pending;console.log(JSON.stringify({summary:elems.ledgerSummary.textContent}));})().catch(e=>{console.error(e);process.exit(1)})"
    result=json.loads(subprocess.check_output(['node','-e',harness+upload+handler+scenario]));self.assertEqual(result['summary'],label)
if __name__=='__main__':unittest.main()
