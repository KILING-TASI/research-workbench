const assert=require('node:assert/strict'),E=require('../assets/engine.js');
const rows=Array.from({length:25},(_,i)=>({code:String(i),name:'Test',applyDate:E.iso(E.day('2025-01-01')+i*10),listingDate:E.iso(E.day('2025-01-02')+i*10),price:10,maxShares:1e6,ratePct:.1}));
const v=E.validateModel(rows,'2026-10-01');assert.equal(v.count,5);assert.equal(v.summary.baseline.meanAbsErrorPct,0);assert.equal(v.summary.pessimistic.underfundedPct,0);
rows[24].ratePct=.05;const changed=E.validateModel(rows,'2026-10-01').rows[0];assert.equal(changed.predictions.baseline.ratePct,.1);assert.equal(changed.predictions.baseline.errorPct,-50);assert(changed.predictions.baseline.underfunded);
console.log('Validation: history cutoffs, zero-error baseline and underfunding checks passed');
