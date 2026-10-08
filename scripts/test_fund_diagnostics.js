const assert=require('assert'),a=require('./fund_diagnostics.js');
const f=(id,weights)=>({id,allocation:.5,currency:'CNY',reportDate:'2026-06-30',publishedAt:'2026-08-30',sourceUrl:'https://example.org/'+id,locator:'page1',disclosureScope:'top10',equityWeight:.8,holdings:weights.map(([code,weight])=>({market:'SZSE',name:code,code,shareClass:'ordinary',weight,industry:'科技'}))});
const d={asOf:'2026-10-03',currency:'CNY',industrySystem:'test',industryVersion:'1',funds:[f('000001',[['300001',.2],['300002',.2]]),f('000002',[['300001',.1],['300003',.1]])]};
const r=a.overlap(d);assert.equal(r.pairs[0].navOverlapPct,10);assert.equal(r.pairs[0].disclosedEquityNormalizedOverlapPct,50);assert.equal(r.funds[0].concentration.effectiveDisclosedNames,2);assert.equal(r.commonSecurities.length,1);assert.ok(r.portfolio.unknownEquityWeight>0);
assert.equal(a.similar({targetCode:'000001',holdingsInput:d}).ranking[0].code,'000002');const mixed=JSON.parse(JSON.stringify(d));mixed.funds[1].reportDate='2026-03-31';assert.equal(a.similar({targetCode:'000001',holdingsInput:mixed}).ranking.length,0);
const report=a.report({asOf:d.asOf,title:'研究',subjectCodes:['000001','000002'],holdingsInput:d});assert.ok(report.missing.includes('历史净值与比较基准'));assert.ok(a.markdown(report).includes('资料缺口'));assert.throws(()=>a.report({asOf:d.asOf,title:'研究',subjectCodes:['000001'],holdingsInput:d}));
console.log('Dual basis, coverage, common names, pool scope, period conflict and report gap checks passed.');

assert.equal(r.pairs[0].calculation.denominatorA,.4);assert.equal(r.pairs[0].calculation.denominatorB,.2);assert.equal(r.funds[0].concentration.calculation.inputs.length,2);assert.equal(r.funds[0].concentration.calculation.disclosedDenominator,.4);assert.equal(a.overlap(mixed).pairs[0].calculation.periodsAligned,false);

const category=a.report({asOf:d.asOf,title:'分类研究',subjectCodes:['000001'],depthResults:[{type:'disclosed-category-change',code:'000001',asOf:d.asOf,pairs:[{startReport:'2025-12-31',endReport:'2026-06-30',status:'不可比',totalVariationPct:null,sources:[]}],limitations:[]}]});
assert.ok(a.markdown(category).includes('权重变化不证明主动交易'));
const passages=a.report({asOf:d.asOf,title:'观点研究',subjectCodes:['000001'],depthResults:[{type:'manager-public-passages',code:'000001',asOf:d.asOf,sections:[{heading:'管理人展望',passages:[{page:12,text:'仅为管理人自述'}]}],limitations:[]}]});
assert.ok(a.markdown(passages).includes('PDF页12'));assert.ok(a.markdown(passages).includes('不能当作已证实事实'));

assert.ok(a.markdown(passages).includes('研究对象：000001'));assert.ok(passages.summary.includes('本次已取得资料'));

for(const invalid of [null,{title:' ',asOf:'2026-10-07',subjectCodes:['000001']},{title:'报告',asOf:'2026-02-30',subjectCodes:['000001']},{title:'报告',asOf:'2026-10-07',subjectCodes:['000001','000001']},{title:'报告',asOf:'2026-10-07',subjectCodes:['000001'],depthResults:[null]},{title:'报告',asOf:'2026-10-07',subjectCodes:['000001'],supplementaryResults:{}}])assert.throws(()=>a.report(invalid));

const partialSubjects=a.report({asOf:d.asOf,title:'部分资料',subjectCodes:['000001','000002','000003'],holdingsInput:d});
assert.ok(partialSubjects.missing.includes('000003：持仓报告未取得'));assert.equal(partialSubjects.sections[0].result.funds.length,2);

const basic=a.report({asOf:d.asOf,title:'持仓研究',subjectCodes:['000001','000002'],holdingsInput:d});
assert.ok(!basic.missing.some(x=>x.includes('期初权重归因')));
assert.ok(basic.notAssessed.some(x=>x.includes('期初权重归因')));
assert.ok(!basic.missing.some(x=>x.includes('漂移综合评分')));
const attribution=a.report({asOf:d.asOf,title:'归因研究',subjectCodes:['000001','000002'],holdingsInput:d,requiredDepthTypes:['brinson-fachler-single-period']});
assert.ok(attribution.missing.some(x=>x.includes('期初权重归因')&&x.includes('本次问题需要')));
assert.ok(!attribution.notAssessed.some(x=>x.includes('期初权重归因')));
const managerRequired=a.report({asOf:d.asOf,title:'经理研究',subjectCodes:['000001'],requiredDepthTypes:['manager-public-passages'],depthResults:[{type:'manager-public-passages',code:'000001',asOf:d.asOf,sections:[],limitations:[]}]});
assert.ok(managerRequired.missing.some(x=>x.includes('经理公开观点')));
for(const required of [null,'brinson-fachler-single-period',['unknown'],['manager-public-passages','manager-public-passages']]) {
 if(required===null)continue;
 assert.throws(()=>a.report({asOf:d.asOf,title:'研究',subjectCodes:['000001'],requiredDepthTypes:required}));
}
console.log('Requested analysis gaps are separate from unassessed optional dimensions.');

const packaged=a.report({asOf:d.asOf,title:'判断优先',subjectCodes:['000001','000002'],holdingsInput:d,supplementaryResults:[{type:'fund-evidence-package',subjectCodes:['000001','000002'],asOf:d.asOf,evidence:[{id:'e',code:'000001',status:'original-disclosed',value:.1,sourceUrl:'https://example.org/source',disclosedAt:d.asOf,locator:'p1'}],conclusions:[{id:'c',grade:'calculated',text:'证券重复有限，风险驱动仍需核查',evidenceIds:['e'],limitations:['仅披露快照']}]}]});
assert.equal(packaged.sections[0].heading,'结论与证据');
const prose=a.markdown(packaged);
assert.ok(prose.indexOf('证券重复有限，风险驱动仍需核查')<prose.indexOf('## 持仓结构与重叠'));
assert.ok(prose.includes('仅披露快照'));
console.log('Existing evidence conclusions precede metric tables.');

function evidenceInput(pkg){return {asOf:d.asOf,title:'证据报告',subjectCodes:['000001','000002'],supplementaryResults:[pkg]};}
const template={type:'fund-evidence-package',subjectCodes:['000001','000002'],asOf:d.asOf,evidence:[{id:'original',code:'000001',status:'original-disclosed',value:1,sourceUrl:'https://example.org/source',disclosedAt:d.asOf,locator:'p1'},{id:'calc',code:'000001',status:'derived',value:1,formula:'original * scale',parameters:{scale:1},inputEvidenceIds:['original']}],conclusions:[{id:'result',grade:'calculated',text:'仅计算已知部分',evidenceIds:['calc'],limitations:['输入范围有限']}]};
assert.ok(a.markdown(a.report(evidenceInput(template))).includes('计算结果：'));
const withNotes=JSON.parse(JSON.stringify(template));withNotes.notes=[{text:'关注下一期现金兑现',conclusionIds:['result']}];
const noteProse=a.markdown(a.report(evidenceInput(withNotes)));
assert.ok(noteProse.includes('关注下一期现金兑现'));assert.ok(noteProse.includes('用户笔记不作为已核实事实'));assert.ok(noteProse.includes('关联结论：result'));
for(const note of [{text:'记录',conclusionIds:'result'},{text:'记录',conclusionIds:['unknown']},{text:1,conclusionIds:['result']},{text:'记录',evidenceIds:null},{text:'记录',conclusionIds:['result','result']},{text:'记录'}]){
 const invalid=JSON.parse(JSON.stringify(template));invalid.notes=[note];assert.throws(()=>a.report(evidenceInput(invalid)),/笔记/);
}
for(const mutate of [
 p=>p.conclusions[0].evidenceIds=['absent'],
 p=>p.evidence.push({...p.evidence[0]}),
 p=>p.evidence[0].code='999999',
 p=>p.evidence[0].inputEvidenceIds=['calc'],
 p=>p.evidence[0].status='missing',
 p=>p.evidence[0].status='assumption',
 p=>p.evidence[0].status='conflict',
 p=>p.conclusions[0].grade='disclosed-fact',
 p=>p.conclusions[0].limitations=[]
]){const value=JSON.parse(JSON.stringify(template));mutate(value);assert.throws(()=>a.report(evidenceInput(value)));}
const estimated=JSON.parse(JSON.stringify(template));estimated.evidence[0].status='assumption';estimated.conclusions[0].grade='estimate';assert.ok(a.markdown(a.report(evidenceInput(estimated))).includes('研究估算：'));
console.log('Evidence dependencies and uncertainty grades checked before presentation.');

for(const mutate of [p=>delete p.evidence[0].value,p=>delete p.evidence[1].formula,p=>p.evidence[1].parameters={}]){const value=JSON.parse(JSON.stringify(template));mutate(value);assert.throws(()=>a.report(evidenceInput(value)));}
const contradictory=JSON.parse(JSON.stringify(template));contradictory.evidence[0].status='conflict';contradictory.evidence[0].alternatives=[{value:1},{value:2}];assert.throws(()=>a.report(evidenceInput(contradictory)));contradictory.conclusions[0].grade='estimate';assert.ok(a.markdown(a.report(evidenceInput(contradictory))).includes('研究估算：'));

const fs=require('fs'),path=require('path'),os=require('os');
const outputFolder=fs.mkdtempSync(path.join(os.tmpdir(),'fund-output-test-'));
try {
 const out=path.join(outputFolder,'result.json');
 a.publishResult(out,{ok:true},'正文');assert.equal(fs.readFileSync(out+'.md','utf8'),'正文');
 assert.throws(()=>a.publishResult(out,{changed:true},'覆盖'));assert.deepEqual(JSON.parse(fs.readFileSync(out,'utf8')),{ok:true});
 const invalid=path.join(outputFolder,'invalid.json');assert.throws(()=>a.publishResult(invalid,{value:Infinity},'正文'));assert.ok(!fs.existsSync(invalid));
 const failed=path.join(outputFolder,'failed.json');let count=0;
 assert.throws(()=>a.publishResult(failed,{ok:true},'正文',(from,to)=>{if(++count===2)throw Object.assign(new Error('第二产物失败'),{code:'EACCES'});fs.linkSync(from,to);}));
 assert.ok(!fs.existsSync(failed));assert.ok(!fs.existsSync(failed+'.md'));
 const racing=path.join(outputFolder,'racing.json');count=0;
 assert.throws(()=>a.publishResult(racing,{ok:true},'正文',(from,to)=>{if(++count===2)fs.writeFileSync(to,'其他进程的结果',{flag:'wx'});fs.linkSync(from,to);}));
 assert.equal(fs.readFileSync(racing,'utf8'),'其他进程的结果');assert.ok(!fs.existsSync(racing+'.md'));
 assert.ok(!fs.readdirSync(outputFolder).some(x=>x.startsWith('.report-')));
 const originalRmdir=fs.rmdirSync;let retained=[];
 fs.rmdirSync=function(dir,...args){if(path.basename(dir).startsWith('.report-')){retained.push(dir);throw Object.assign(new Error('模拟暂存目录清理失败'),{code:'EACCES'});}return originalRmdir.call(fs,dir,...args);};
 try{
  const clean=path.join(outputFolder,'cleanup.json'),saved=a.publishResult(clean,{ok:true},'已保存');
  assert.equal(saved.cleanupIssues.length,1);assert.equal(fs.readFileSync(clean+'.md','utf8'),'已保存');assert.deepEqual(JSON.parse(fs.readFileSync(clean,'utf8')),{ok:true});
  const primary=path.join(outputFolder,'primary.json');
  assert.throws(()=>a.publishResult(primary,{ok:true},'正文',()=>{throw new Error('原始发布失败');}),error=>error.message==='原始发布失败'&&error.cleanupIssues.length===1);
 }finally{fs.rmdirSync=originalRmdir;for(const dir of retained)originalRmdir.call(fs,dir);}
} finally {
 // Only the fixed filenames created by this test are removed; never recurse.
 for(const name of ['result.json','result.json.md','racing.json','cleanup.json','cleanup.json.md']){const file=path.join(outputFolder,name);if(fs.existsSync(file))fs.unlinkSync(file);}
 fs.rmdirSync(outputFolder);
}
console.log('Failed publication rolls back only unchanged files from this run; competing output is preserved.');

for(const date of ['2026-10-04','2026-02-30','']){const value=JSON.parse(JSON.stringify(template));value.evidence[0].observedAt=date;assert.throws(()=>a.report(evidenceInput(value)));}
const sameDay=JSON.parse(JSON.stringify(template));sameDay.evidence[0].observedAt=d.asOf;a.report(evidenceInput(sameDay));
const premature=JSON.parse(JSON.stringify(template));premature.evidence[0].observedAt='2026-01-01';assert.throws(()=>a.report(evidenceInput(premature)),/不能早于披露日/);
console.log('Nested evidence dates obey the same cutoff as the report.');

for(const subjects of [[],['000001','000001'],['999999'],[' '],'000001',[null]]){
 const value=JSON.parse(JSON.stringify(template));value.subjectCodes=subjects;
 assert.throws(()=>a.report(evidenceInput(value)),/主体/);
}
const singleSubject=JSON.parse(JSON.stringify(template));singleSubject.subjectCodes=['000001'];a.report(evidenceInput(singleSubject));

for(const mutate of [p=>delete p.evidence[0].sourceUrl,p=>p.evidence[0].locator=' ',p=>delete p.evidence[0].disclosedAt,p=>p.evidence[0].sourceUrl='https://user:password@example.org/report']){const value=JSON.parse(JSON.stringify(template));mutate(value);assert.throws(()=>a.report(evidenceInput(value)));}
