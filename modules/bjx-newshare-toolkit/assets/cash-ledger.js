'use strict';
// Browser money is exact to cents; interest rate accepts at most six decimal places.
(function(root){
// Self-contained browser copy of scripts/strict_json.js; parity is checked in tests.
function parsePlan(text){
 const raw=text.replace(/^\uFEFF/,'');const result=JSON.parse(raw);let i=0;
 const space=()=>{while(i<raw.length&&/\s/.test(raw[i]))i++;};
 function string(){const begin=i++;while(i<raw.length){if(raw[i]==='\\'){i+=2;continue;}if(raw[i++]==='"')break;}return JSON.parse(raw.slice(begin,i));}
 function value(depth){if(depth>128)throw Error('JSON nesting exceeds 128');space();const ch=raw[i];
  if(ch==='{'){i++;space();const keys=new Set();if(raw[i]==='}'){i++;return;}while(true){space();const key=string();if(keys.has(key))throw Error('Duplicate JSON property: '+key);keys.add(key);space();i++;value(depth+1);space();if(raw[i++]==='}')break;}return;}
  if(ch==='['){i++;space();if(raw[i]===']'){i++;return;}while(true){value(depth+1);space();if(raw[i++]===']')break;}return;}
  if(ch==='"'){string();return;}while(i<raw.length&&!/[\s,}\]]/.test(raw[i]))i++;
 }
 value(0);
 function finite(v){if(typeof v==='number'&&!Number.isFinite(v))throw Error('Non-finite JSON number');if(v&&typeof v==='object')for(const x of Object.values(v))finite(x);}
 finite(result);return result;
}

function run(spec){
 const day=s=>{if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(s))throw Error('日期须为YYYY-MM-DD');const n=Date.parse(s+'T00:00:00Z');if(!Number.isFinite(n)||new Date(n).toISOString().slice(0,10)!==s)throw Error('无效日期');return n/86400000};
 const fixed=(v,digits)=>{const s=String(v);if(typeof v==='boolean'||!new RegExp('^\\d+(?:\\.\\d{1,'+digits+'})?$').test(s))throw Error('金额须非负，精确到分；利率最多六位小数');const [a,b='']=s.split('.');return BigInt(a)*10n**BigInt(digits)+BigInt(b.padEnd(digits,'0'))};
 const fmt=v=>(v<0n?'-':'')+(v<0n?-v:v)/100n+'.'+String((v<0n?-v:v)%100n).padStart(2,'0');
 const start=day(spec.start),end=day(spec.end);if(end<start||end-start>3660)throw Error('观察期须在十年内');
 const capital=fixed(spec.capital,2),events=[],repos=[],seen=new Set();
 const key=(prefix,id)=>{if(typeof id!=='string'||!id.trim())throw Error('事件编号缺失');const k=prefix+id;if(seen.has(k))throw Error('事件编号重复');seen.add(k);return k};
 const add=(date,priority,id,kind,delta)=>{const n=day(date);if(n<start)throw Error('事件早于期初日期');events.push({date,n,priority,id,kind,delta})};
 for(const i of spec.issues||[]){const k=key('ipo:',i.id),a=day(i.applyDate),r=day(i.refundAvailableDate),s=day(i.saleAvailableDate);if(!(a<r&&r<=s))throw Error('申购、退款可用、卖出可用日期顺序有误');if(i.announcedRefundDate&&r<day(i.announcedRefundDate))throw Error('退款可用日早于公告退款日');const funds=fixed(i.subscriptionFunds,2),allocated=fixed(i.allocatedPrincipal,2),proceeds=fixed(i.saleNetProceeds,2);if(allocated>funds)throw Error('获配本金超过申购资金');add(i.applyDate,0,k,'subscription',-funds);add(i.refundAvailableDate,2,k,'refund',funds-allocated);add(i.saleAvailableDate,2,k,'sale',proceeds)}
 for(const r of spec.repos||[]){const k=key('repo:',r.id),trade=day(r.tradeDate),first=day(r.firstSettlementDate),maturity=day(r.maturitySettlementDate),available=day(r.availableDate);if(!(trade<=first&&first<maturity&&available>=trade))throw Error('回购日期顺序有误');if(!r.dateBasis||available<maturity&&!r.earlyAvailabilityEvidence)throw Error('回购日期或提前可用依据缺失');if(r.commission===undefined||r.commission===null)throw Error('回购佣金需明确填写，包括零假设');const principal=fixed(r.principal,2),rate=fixed(r.annualRatePct,6),fee=fixed(r.commission,2),days=maturity-first,denom=100000000n*365n,interest=(principal*rate*BigInt(days)*2n+denom)/(2n*denom);if(fee>principal+interest)throw Error('费用超过兑付金额');add(r.tradeDate,1,k,'repo-open',-principal-fee);add(r.availableDate,2,k,'repo-return',principal+interest);repos.push({id:r.id,actualAccrualDays:days,grossInterest:fmt(interest),commission:fmt(fee),netInterest:fmt(interest-fee),dateBasis:r.dateBasis})}
 events.sort((a,b)=>a.n-b.n||a.priority-b.priority||(a.id<b.id?-1:a.id>b.id?1:0)||(a.kind<b.kind?-1:a.kind>b.kind?1:0));let cash=capital,minimum=cash;const steps=[],unsettledEvents=[];
 for(const e of events){if(e.n>end){unsettledEvents.push({date:e.date,id:e.id,kind:e.kind,delta:fmt(e.delta)});continue}cash+=e.delta;if(cash<minimum)minimum=cash;steps.push({date:e.date,id:e.id,kind:e.kind,delta:fmt(e.delta),balance:fmt(cash),conflict:cash<0n})}
 return {mode:'explicit-date-scenario-not-account-verification',capital:fmt(capital),endCash:fmt(cash),minimumCash:fmt(minimum),additionalFundsRequired:fmt(minimum<0n?-minimum:0n),feasible:minimum>=0n,repos,steps,unsettledEvents};
}
root.BjxCashLedger={run,parsePlan};if(typeof module!=='undefined')module.exports=root.BjxCashLedger;
})(typeof globalThis!=='undefined'?globalThis:this);
