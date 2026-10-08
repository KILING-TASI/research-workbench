'use strict';
const assert=require('node:assert/strict');
const {build}=require('./fund_report_presentation.js');
const base=sections=>({type:'integrated-fund-research',title:'资料比较',asOf:'2026-10-08',subjectCodes:['000001'],sections:sections.map(result=>({result})),riskNotice:'历史观察',sources:[],limitations:[],conflicts:[],missing:[]});
const holdings=weight=>({funds:[{id:'000001',reportDate:'2026-06-30',equityWeight:weight,coveragePct:150,concentration:{effectiveDisclosedNames:null}}],pairs:[]});
for(const weight of [null,undefined,'0',false]){
 const html=build(base([holdings(weight)])).html;
 assert.ok(html.includes('<td>000001</td><td>待核验</td><td>150.00</td>'));
 assert.ok(!html.includes('<td>000001</td><td>0.00</td>'));
}
assert.ok(build(base([holdings(0)])).html.includes('<td>000001</td><td>0.00</td>'));
const allocation={type:'fund-asset-allocation',code:'000001',rows:[{reportDate:'2026-06-30',weights:{cash:null},unknownPct:null}],limitations:[]};
assert.ok(build(base([allocation])).html.includes('现金:待核验%'));
const attribution={type:'brinson-fachler-single-period',code:'000001',totals:{allocationPp:1,selectionPp:2,interactionPp:0},activeSnapshotReturnPp:3,limitations:['只含快照']};
const known=build(base([attribution])).html;
assert.ok(known.includes('已取得1项单期Brinson快照归因'));
assert.ok(!known.includes('缺期初行业权重与行业收益，不能归因'));
assert.ok(build(base([])).html.includes('缺期初行业权重与行业收益，不能归因'));
for(const url of ['javascript:alert(1)','ftp://example.org/a','https://user:secret@example.org/a','https://example.org/ a']){
 const spec=base([]);spec.sources=[url];assert.throws(()=>build(spec),/来源链接/);
}
const safe=base([]);safe.sources=['https://example.org/report'];assert.ok(build(safe).html.includes('href="https://example.org/report"'));
const evidence={type:'fund-evidence-package',conclusions:[{text:'示例',grade:'disclosed-fact',evidenceIds:['e'],limitations:[]}],evidence:[{id:'e',sourceUrl:'javascript:alert(1)'}],limitations:[]};
assert.throws(()=>build(base([evidence])),/来源链接/);
console.log('基金报告缺值、覆盖披露、归因状态与安全链接回归通过');
