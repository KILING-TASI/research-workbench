'use strict';
const assert=require('node:assert/strict'),api=require('./fund_research.js');
const fund=(code,values,dates=['2026-01-31','2026-02-28','2026-03-31','2026-04-30'])=>({code,currency:'CNY',basis:'total-return',sourceUrl:'https://example.org/'+code,history:dates.map((date,i)=>({date,value:values[i]}))});
const input={asOf:'2026-04-30',frequency:'monthly',currency:'CNY',riskFreeAnnualPct:0,assets:[fund('A',[100,110,99,108.9]),fund('B',[100,110,99,108.9])]};
let r=api.compare(input);assert.ok(Math.abs(r.correlation.matrix[0][1]-1)<1e-12);assert.equal(r.comparisons[0].metrics.maximumDrawdownPct.relation,'equal');
const versioned=structuredClone(input);versioned.reference=fund('REF',[100,101,102,103]);
versioned.reference.role='declared-benchmark';versioned.reference.definition='教学基准，不是真实合同基准';
assert.equal(api.compare(versioned).alignment.benchmarkVersion.status,'effective-period-not-declared');
versioned.reference.validFrom='2026-03-01';assert.throws(()=>api.compare(versioned),/需分段基准/);
versioned.reference.validFrom='2026-01-01';versioned.reference.validThrough='2026-03-31';assert.throws(()=>api.compare(versioned),/需分段基准/);
versioned.reference.validThrough='2026-04-30';assert.equal(api.compare(versioned).alignment.benchmarkVersion.status,'declared-period-covers-window-not-externally-verified');
versioned.reference.validThrough='2025-12-31';assert.throws(()=>api.compare(versioned),/有效期顺序/);
const extended=structuredClone(input);extended.assets[0].history.unshift({date:'2025-12-31',value:100});r=api.compare(extended);assert.equal(r.alignment.start,'2026-01-31');assert.equal(r.alignment.removed[0].removedObservations,1);
const broken=structuredClone(input);broken.assets[0].history.splice(1,1);assert.throws(()=>api.compare(broken));
const invalid=structuredClone(extended);invalid.assets[0].history[0].value=-10;assert.throws(()=>api.compare(invalid));
const flat=structuredClone(input);flat.assets[1]=fund('B',[100,100,100,100]);assert.equal(api.compare(flat).correlation.matrix[0][1],null);
const cls=(id,subscriptionPct,salesServicePct)=>({id,sourceUrl:'https://example.org/fees',observedAt:'2026-01-01',subscriptionPct,salesServicePct,managementPct:0,custodyPct:0,redemption:[{minDays:0,ratePct:0}]});
const f={asOf:'2026-01-01',basis:'constant-gross-nav-cost-scenario',classes:[cls('A',1,0),cls('C',0,1)],lots:[{date:'2026-01-01',amount:10000}],horizonDays:730};
r=api.feeStudy(f);assert.equal(r.schedule[0].lowerCost,'C');assert.equal(r.costPreferenceTransitions[0].day,364);assert.equal(r.schedule.at(-1).lowerCost,'A');
const step=structuredClone(f);step.classes[0].redemption=[{minDays:0,ratePct:1.5},{minDays:7,ratePct:0}];step.horizonDays=10;r=api.feeStudy(step);assert.ok(r.schedule[0].classes[0].redemption>0);assert.throws(()=>api.feeStudy({...f,basis:'net-nav'}));
const dca=structuredClone(f);dca.lots.push({date:'2026-07-01',amount:10000});assert.equal(api.feeStudy(dca).schedule.at(-1).paid,20000);
const event={id:'e1',code:'A',title:'经理变更公告',publishedAt:'2026-01-01',sourceUrl:'https://example.org/e',status:'confirmed'};
let m=api.monitor({asOf:'2026-01-01',watchlist:['A'],events:[event]});assert.equal(m.alerts.length,1);assert.equal(api.monitor({asOf:'2026-01-01',watchlist:['A'],events:[event],seen:m.seen}).alerts.length,0);assert.equal(api.monitor({asOf:'2026-01-01',watchlist:['A'],events:[{...event,status:'unverified',title:'离职传闻'}],seen:m.seen}).alerts[0].label,'未核实线索');
console.log('Fund research checks passed: alignment, gaps, invalid data, correlation, zero variance, fee transition, redemption, DCA, no double fee, monitor dedup and rumor status.');

const sim=api.simulate({historyInput:input,beforeWeights:{A:.5,B:.5},afterWeights:{A:1,B:0},scenarios:[{name:'压力',shocksPct:{A:-20,B:-10}}]});assert.equal(sim.before.scenarios[0].returnPct,-15);assert.equal(sim.after.scenarios[0].returnPct,-20);assert.equal(sim.before.concentrationHHI,.5);assert.equal(sim.after.concentrationHHI,1);assert.throws(()=>api.simulate({historyInput:input,beforeWeights:{A:1.1},afterWeights:{A:1}}));assert.equal(api.scan({codes:['A','missing'],historyInput:input}).cards[1].status,'missing');console.log('Adjustment scenario and light scan checks passed.');

const ctr=api.contributions({historyInput:input,weights:{A:.5,B:.5}});assert.ok(Math.abs(ctr.assets.reduce((v,x)=>v+x.returnContributionPp,0)-ctr.totalReturnPct)<1e-10);assert.ok(Math.abs(ctr.assets.reduce((v,x)=>v+x.volatilityContributionPp,0)-ctr.annualVolatilityPct)<1e-10);assert.ok(Math.abs(ctr.assets.reduce((v,x)=>v+x.worstDrawdownContributionPp,0)+ctr.worstDrawdown.maximumDrawdownPct)<1e-10);assert.ok(Math.abs(ctr.assets[0].riskSharePct-50)<1e-10);console.log('Return, volatility and common drawdown path contribution checks passed.');


const sparseDaily=structuredClone(input);sparseDaily.frequency='daily';assert.throws(()=>api.contributions({historyInput:sparseDaily,weights:{A:.5,B:.5}}),/日频间隔/);console.log('Sparse daily annualization blocked.');

const provenance=api.contributions({historyInput:input,weights:{A:.5,B:.5}});assert.equal(provenance.evidenceGaps.length,4);const futureAvailable=structuredClone(input);futureAvailable.assets[0].availableAt='2026-05-01';assert.throws(()=>api.contributions({historyInput:futureAvailable,weights:{A:.5,B:.5}}),/资料可得日/);futureAvailable.assets[0].availableAt='2026-04-30';futureAvailable.assets[0].dividendCalendarVerified='true';assert.throws(()=>api.compare(futureAvailable),/布尔值/);console.log('Contribution evidence gaps and future availability checks passed.');

assert.throws(()=>api.compare({...input,currency:undefined}),/币种/);
const unsafeSource=structuredClone(input);unsafeSource.assets[0].sourceUrl='https://user:secret@example.org/data';assert.throws(()=>api.compare(unsafeSource),/无凭据/);
assert.throws(()=>api.compare({...input,assets:[{code:'empty'}]}),/非空历史序列/);
assert.throws(()=>api.feeStudy({...f,horizonDays:0}),/期限/);
const hugeLots=structuredClone(f);hugeLots.horizonDays=1;hugeLots.lots=[{date:'2026-01-01',amount:1e308},{date:'2026-01-01',amount:1e308}];assert.throws(()=>api.feeStudy(hugeLots),/非有限/);
