'use strict';
(function(root){
function generate(source,overlays,calendar,capital,start,end){
 const dec=value=>{const s=String(value);const m=/^(-?)(\d+)(?:\.(\d+))?$/.exec(s);if(!m)throw Error('不支持的数字格式');return [BigInt((m[1]||'')+m[2]+(m[3]||'')),10n**BigInt((m[3]||'').length)]};
 const cents=v=>{const [n,d]=dec(v);if(n<0n||n*100n%d)throw Error('金额须非负且精确到分');return n*100n/d};
 const fmt=n=>(n/100n)+'.'+String(n%100n).padStart(2,'0');
 const day=s=>{if(!/^\d{4}-\d{2}-\d{2}$/.test(s))throw Error('日期格式错误');const n=Date.parse(s+'T00:00:00Z');if(!Number.isFinite(n)||new Date(n).toISOString().slice(0,10)!==s)throw Error('日期无效');return n};
 const open=s=>{const d=new Date(day(s));if(d.getUTCFullYear()!==calendar.year)throw Error('日期超出已核验日历');return d.getUTCDay()!==0&&d.getUTCDay()!==6&&!calendar.closedRanges.some(([a,b])=>s>=a&&s<=b)};
 const next=s=>{let n=day(s);for(let i=0;i<20;i++){n+=86400000;const v=new Date(n).toISOString().slice(0,10);if(open(v))return v}throw Error('交易日历窗口不足')};
 if(!calendar||Number(start.slice(0,4))!==calendar.year||Number(end.slice(0,4))!==calendar.year||day(end)<day(start))throw Error('研究区间超出已核验日历');
 if(end>source.fetchedAt.slice(0,10))throw Error('历史测算不能超过缓存日期');
 const opening=cents(capital);if(opening<=0n)throw Error('本金须大于零');let cash=opening,pending=[];const issues=[],excluded=[];
 const rows=source.records.filter(r=>r.applyDate&&r.applyDate>=start&&r.applyDate<=end).sort((a,b)=>a.applyDate.localeCompare(b.applyDate)||a.code.localeCompare(b.code));
 for(const raw of rows){const r={...raw,...(overlays.records||{})[raw.code]};try{
  if(['price','maxShares','ratePct','gainPct','refundDate','listingDate'].some(k=>r[k]==null))throw Error('必要数值或日期缺失');
  const price=cents(r.price),[rn,rd]=dec(r.ratePct),[gn,gd]=dec(r.gainPct),limit=BigInt(r.maxShares),minimum=BigInt(r.minShares||100);
  if(price<=0n||rn<=0n||rn>100n*rd||gn< -100n*gd||limit%100n||minimum%100n||minimum<=0n||minimum>limit)throw Error('价格、配售率、整手或涨跌幅无效');
  if(!open(r.applyDate))throw Error('申购日不是日历交易日');const refund=open(r.refundDate)?r.refundDate:next(r.refundDate),sale=next(r.listingDate);
  if(!(r.applyDate<refund&&refund<=sale))throw Error('退款与卖出日期次序冲突');if(sale>end)throw Error('卖出款可用日在观察期之后');
  for(const x of pending.filter(x=>x.date<r.applyDate))cash+=x.amount;pending=pending.filter(x=>x.date>=r.applyDate);
  let shares=cash/(price*100n)*100n;if(shares>limit)shares=limit;if(shares<minimum)throw Error('冻结后可用资金不足');
  const allocated=shares*rn/(rd*10000n)*100n,subscribed=shares*price,principal=allocated*price,den=100n*gd,proceeds=(principal*(den+gn)*2n+den)/(2n*den);
  cash-=subscribed;pending.push({date:refund,amount:subscribed-principal},{date:sale,amount:proceeds});issues.push({id:r.code,applyDate:r.applyDate,announcedRefundDate:r.refundDate,refundAvailableDate:refund,saleAvailableDate:sale,subscriptionFunds:fmt(subscribed),allocatedPrincipal:fmt(principal),saleNetProceeds:fmt(proceeds),subscriptionShares:String(shares),allocatedWholeLotShares:String(allocated),dateBasis:'公告退款顺延交易日、首日收盘卖出后下一交易日可用的情景；未核验账户',feeAssumption:'zero fees, gross proceeds only'});
 }catch(e){excluded.push({code:r.code,reason:e.message})}}
 const plan={capital:fmt(opening),start,end,issues,repos:[],mode:'historical-explicit-date-scenario',sourceFetchedAt:source.fetchedAt,accountAvailabilityVerified:false,limitations:['历史实际配售率和涨跌幅不是预测','同日先申购后释放，整手获配不含零股','首日收盘卖出、零费用假设']};
 return {plan,excluded,sampleCount:rows.length,ledger:root.BjxCashLedger.run(plan)};
}
root.BjxCashPlan={generate};if(typeof module!=='undefined')module.exports={generate};
})(typeof globalThis!=='undefined'?globalThis:this);
