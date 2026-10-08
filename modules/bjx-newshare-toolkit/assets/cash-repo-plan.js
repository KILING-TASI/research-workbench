'use strict';
(function(root){
function schedule(plan,calendar,annualRate,utilization=80,commission=0,lotFunds=1000){
 const ratio=v=>{const s=String(v);if(!/^\d+(\.\d{1,6})?$/.test(s))throw Error('非负参数最多六位小数');const [a,b='']=s.split('.');return [BigInt(a+b),10n**BigInt(b.length)]};
 const cents=v=>{const [n,d]=ratio(v);if(n*100n%d)throw Error('金额须精确到分');return n*100n/d};
 const fmt=v=>(v<0n?'-':'')+((v<0n?-v:v)/100n)+'.'+String((v<0n?-v:v)%100n).padStart(2,'0');
 const open=s=>{const d=new Date(s+'T00:00:00Z');if(d.getUTCFullYear()!==calendar.year)throw Error('日历覆盖不足');return d.getUTCDay()!==0&&d.getUTCDay()!==6&&!calendar.closedRanges.some(([a,b])=>s>=a&&s<=b)};
 const next=s=>{let n=Date.parse(s+'T00:00:00Z');for(let i=0;i<20;i++){n+=86400000;const v=new Date(n).toISOString().slice(0,10);if(open(v))return v}throw Error('日历覆盖不足')};
 if(plan.repos?.length)throw Error('基础计划已有回购，请单独导入');ratio(annualRate);const [un,ud]=ratio(utilization),fee=cents(commission),lot=cents(lotFunds);if(un>100n*ud||lot<=0n)throw Error('利用率须为0至100%，金额档位须大于0');
 if(plan.issues!==undefined&&!Array.isArray(plan.issues)||plan.repos!==undefined&&!Array.isArray(plan.repos))throw Error('申购与回购记录须为数组');
 const result=JSON.parse(JSON.stringify(plan));result.issues=result.issues||[];result.repos=[];
 const baseline=root.BjxCashLedger.run(result);if(!baseline.feasible)throw Error('基础计划已有资金缺口');let ledger=baseline;const skipped=[],applies=result.issues.map(i=>i.applyDate).sort();
 for(let n=Date.parse(plan.start+'T00:00:00Z');n<=Date.parse(plan.end+'T00:00:00Z');n+=86400000){const date=new Date(n).toISOString().slice(0,10);if(!open(date)||!un)continue;let first,maturity;try{first=next(date);maturity=next(first)}catch(e){skipped.push({date,reason:e.message});continue}const upcoming=applies.find(d=>d>date);if(maturity>plan.end||upcoming&&maturity>=upcoming)continue;
  let available=cents(plan.capital)-fee;for(const e of ledger.steps){if(e.date<date)available+=e.delta.startsWith('-')?-cents(e.delta.slice(1)):cents(e.delta);else if(e.date===date&&e.delta.startsWith('-'))available-=cents(e.delta.slice(1))}
  if(available<=0n)continue;const principal=available*un/(100n*ud*lot)*lot;if(principal<=0n)continue;
  result.repos.push({id:'idle-'+date,tradeDate:date,firstSettlementDate:first,maturitySettlementDate:maturity,availableDate:maturity,principal:fmt(principal),annualRatePct:String(annualRate),commission:fmt(fee),dateBasis:'固定结算情景：首次结算为下一交易日，到期及可用为再下一交易日；不是券商实际条款'});const trial=root.BjxCashLedger.run(result);if(!trial.feasible){result.repos.pop();skipped.push({date,reason:'后续资金冲突'});continue}ledger=trial;
 }
 result.repoScenario={annualRatePct:String(annualRate),utilizationPct:String(utilization),commissionPerOrder:String(commission),lotFunds:String(lotFunds),accountAvailabilityVerified:false,tradeTermsVerified:false,note:'固定基础申购量；回购本金可能含已结算利息；结算日期及金额档位为情景假设'};
 return {plan:result,ledger,baselineEndCash:baseline.endCash,incrementalEndCash:fmt(cents(ledger.endCash)-cents(baseline.endCash)),skipped};
}
root.BjxRepoPlan={schedule};if(typeof module!=='undefined')module.exports={schedule};
})(typeof globalThis!=='undefined'?globalThis:this);
