const assert=require('node:assert/strict'),{historicalJudgment:j}=require('./fund_report_presentation.js');
const row=(code,r,d)=>({code,metrics:{CAGRPct:r,maximumDrawdownPct:d}}),name=x=>x;
assert.ok(j([row('A',10,20),row('B',5,10)],name).conclusion.includes('取舍'));
assert.ok(j([row('A',10,10),row('B',5,20)],name).conclusion.includes('至少一项更好'));
assert.ok(j([row('A',10,10),row('B',10,10)],name).conclusion.includes('相同'));
assert.ok(j([row('A',null,10),row('B',5,20)],name).conclusion.includes('不足'));
assert.ok(j([row('A',10,-1),row('B',5,20)],name).conclusion.includes('不足'));
assert.ok(j([row('A',-10,10),row('B',-5,20)],name).conclusion.includes('B'));
console.log('6 historical judgment cases passed');
