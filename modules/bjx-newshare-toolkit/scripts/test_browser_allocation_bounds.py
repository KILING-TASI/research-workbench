import json,shutil,subprocess,unittest
from pathlib import Path

@unittest.skipUnless(shutil.which('node'),'Node required')
class AllocationBounds(unittest.TestCase):
 def annual(self,changes):
  source=(Path(__file__).resolve().parents[1]/'assets/bjx-workbench.js').read_text(encoding='utf-8-sig')
  helpers=source[source.index('function decimal('):source.index('function ceil(')]+source[source.index('function nextSaleScenarioDate('):source.index('function stage(')]
  function=source[source.index('function annualReplay('):source.index('function drawChart(')]
  values=dict(commission='0',minFee='0',tax='0',slip='0',repoRate='0',repoUse='100');values.update(changes)
  row=dict(code='teaching',price=10,maxShares=100,minShares=100,ratePct=100,gainPct=10,applyDate='2026-09-01',refundDate='2026-09-03',listingDate='2026-09-04')
  row.update(changes.get('row',{}));values.pop('row',None)
  data=dict(fetchedAt='2026-10-06',annualRecords=[row],bseTradingCalendar=dict(year=2026,closedRanges=[]))
  script='const data='+json.dumps(data)+',values='+json.dumps(values)+',$=id=>({value:values[id]});'+helpers+function+";try{const result=annualReplay(1000,'2026');console.log(JSON.stringify({profit:result.profit}))}catch(e){console.log(JSON.stringify({error:e.message}))}"
  return json.loads(subprocess.check_output([shutil.which('node'),'-e',script],text=True,encoding='utf-8'))
 def test_annual_normal_case_preserved(self):
  self.assertEqual(self.annual({})['profit'],100)
 def test_annual_overflow_rejected(self):
  for change in [{'row':{'gainPct':1e308}},{'minFee':'1e308'},{'repoRate':'1e308'}]:
   with self.subTest(change=change):self.assertIn('安全计算范围',self.annual(change)['error'])
 def test_source_links_reject_active_schemes_and_credentials(self):
  source=(Path(__file__).resolve().parents[1]/'assets/bjx-workbench.js').read_text(encoding='utf-8-sig');helper=source[source.index('function safeSourceUrl('):source.index('function ceil(')]
  urls=['https://example.org/report.pdf','http://example.org/report.pdf','javascript:alert(1)','data:text/html,test','https://user:secret@example.org/report','https://example.org/ report']
  result=json.loads(subprocess.check_output([shutil.which('node'),'-e',helper+';console.log(JSON.stringify('+json.dumps(urls)+'.map(safeSourceUrl)));'],text=True,encoding='utf-8'));self.assertEqual(result,[True,True,False,False,False,False])
 def run_calc(self,changes):
  source=(Path(__file__).resolve().parents[1]/'assets/bjx-workbench.js').read_text(encoding='utf-8-sig')
  functions=source[source.index('function decimal('):source.index('const links=')]
  values=dict(price='17.37',budget='10000000',rate='0.0240816593',limit='765000',minimum='100',gain='10',commission='0',minFee='0',tax='0',slip='0');values.update(changes)
  script="const values="+json.dumps(values)+";const elements={};function element(){return {value:'',textContent:'',children:[],append(x){this.children.push(x)},replaceChildren(){this.children=[]}}};const $=id=>elements[id]||(elements[id]=Object.assign(element(),{value:values[id]??''})),document={createElement:element},money=x=>String(x);"+functions+";calc();console.log(JSON.stringify({message:$('allocationResult').textContent,rows:$('tierRows').children.length,status:$('tierStatus').textContent}));"
  return json.loads(subprocess.check_output([shutil.which('node'),'-e',script],text=True,encoding='utf-8'))
 def test_normal_case_keeps_allocation_and_tiers(self):
  result=self.run_calc({});self.assertEqual(result['rows'],5);self.assertIn('整手比例获配：100股',result['message'])
 def test_overflowing_budget_or_gain_clears_results(self):
  for change in [{'budget':'1'+'0'*350},{'gain':'1e308'},{'minFee':'1e308'}]:
   result=self.run_calc(change);self.assertEqual(result['rows'],0);self.assertIn('安全计算范围',result['message']);self.assertIn('未生成',result['status'])

if __name__=='__main__':unittest.main()
