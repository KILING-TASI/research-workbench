'use strict';
const assert=require('node:assert/strict'),api=require('./research_analytics.js');
const dates=['2026-01-01','2026-01-02','2026-01-05','2026-01-06','2026-01-07','2026-01-08'];
function input(){return {asOf:dates.at(-1),frequency:'daily',currency:'CNY',riskFreeAnnualPct:0,capital:100000,everyObservations:1,thresholdsPct:[3,5],costs:{commissionPct:.03,minimumCommission:5,spreadBps:4,slippageBps:2},assets:[{code:'A',weight:.5,currency:'CNY',basis:'total-return',sourceUrl:'https://example.org/A',history:dates.map((date,i)=>({date,value:[100,130,120,140,125,150][i]}))},{code:'B',weight:.5,currency:'CNY',basis:'total-return',sourceUrl:'https://example.org/B',history:dates.map(date=>({date,value:100}))}]};}
let cases=0;function test(f){f();cases++;}
test(()=>{let r=api.rebalance(input()),tr=r.results[1].trades;assert.ok(tr.length);for(let t of tr){assert.ok(t.signalDate<t.date);assert.ok(Math.abs(t.costLegs.reduce((s,x)=>s+x.totalCost,0)-t.cost)<1e-6);assert.ok(Math.abs(t.preValue-t.postValue-t.cost)<1e-5);}});
test(()=>{let d=input();d.costsByCode={A:{sellTaxPct:.1,buyTaxPct:.02},B:{minimumCommission:7}};let r=api.rebalance(d);for(let t of r.results[1].trades)for(let leg of t.costLegs){if(leg.code==='A'&&leg.direction!=='none')assert.ok(Math.abs(leg.tax-leg.grossAmount*(leg.direction==='sell'?.1:.02)/100)<1e-7);if(leg.code==='B'&&leg.direction!=='none')assert.ok(leg.commission>=7);}});
test(()=>{let d=input();d.blockedDates=[{date:dates[2],code:'A'}];let r=api.rebalance(d);assert.ok(r.results[1].missed.some(x=>x.date===dates[2]));assert.ok(!r.results[1].trades.some(x=>x.date===dates[2]));});
test(()=>{let d=input();d.costsByCode={C:{sellTaxPct:.1}};assert.throws(()=>api.rebalance(d));});
test(()=>{let d=input();d.costsByCode={A:{slippageBps:-1}};assert.throws(()=>api.rebalance(d));});
test(()=>{let d=input();d.costsByCode={A:{minimumFee:2}};assert.throws(()=>api.rebalance(d));});
test(()=>{let d=input();d.costsByCode={A:{sellTaxPct:100}};assert.throws(()=>api.rebalance(d));});
test(()=>{let d=input();d.costs={commissionPct:0,minimumCommission:0,spreadBps:0,slippageBps:0};let r=api.rebalance(d);assert.equal(r.results[1].totalCost,0);assert.equal(r.costProfiles[0].sellTaxPct,0);assert.ok(r.costBasis.includes('按零假设'));});
process.stdout.write(JSON.stringify({passed:true,cases}));
