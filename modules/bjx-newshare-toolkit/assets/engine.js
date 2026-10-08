const Engine=(()=>{
 const unit=100, day=d=>Date.parse(d+'T00:00:00Z')/86400000;
 const iso=n=>new Date(n*86400000).toISOString().slice(0,10);
 const finite=n=>typeof n==='number'&&Number.isFinite(n);
 function threshold(price,rate,max){
  if(!(finite(price)&&price>0&&finite(rate)&&rate>0&&rate<=100))return null;
  const shares=100*Math.ceil(100/rate-1e-10);
  return {shares,hands:shares/100,funds:shares*price,reachable:finite(max)&&shares<=max};
 }
 function allocation(stock,budget,rate=stock.ratePct,gain=stock.gainPct,fee=0.1,continuous=false){
  if(!(finite(stock.price)&&stock.price>0&&finite(stock.maxShares)&&stock.maxShares>=100&&finite(rate)&&rate>=0&&rate<=100&&finite(gain)&&gain>=-100&&finite(budget)&&budget>=0&&finite(fee)&&fee>=0&&fee<=100))return null;
  let shares=100*Math.floor(Math.min(budget/stock.price,stock.maxShares)/100+1e-10);
  if(shares<(stock.minShares||100))shares=0;
  const reference=shares*rate/100;
  const allotted=continuous?reference:100*Math.floor(reference/100+1e-10);
  const principal=allotted*stock.price,profit=principal*(gain/100-(1+gain/100)*fee/100);
  return {shares,reference,allotted,principal,profit,frozen:shares*stock.price};
 }
 function backtest(records,budget,year,today,fee=0.1,continuous=false){
  const start=year+'-01-01',end=today<year+'-12-31'?today:year+'-12-31';
  let cash=budget,profit=0,allotted=0,participated=0,missing=0,insufficient=0,events=[],ledger=[];
  const scope=records.filter(s=>s.applyDate>=start&&s.applyDate<=end).sort((a,b)=>a.applyDate.localeCompare(b.applyDate)||a.code.localeCompare(b.code));
  for(const s of scope){
   if(!s.refundDate||!s.listingDate||s.listingDate>end||s.refundDate<s.applyDate||s.refundDate>s.listingDate||s.listingDate<s.applyDate||!allocation(s,budget,s.ratePct,s.gainPct,fee,continuous)){missing++;continue;}
   const now=day(s.applyDate);
   events.sort((a,b)=>a.date-b.date);
   while(events.length&&events[0].date<=now){const e=events.shift();cash+=e.money;}
   const a=allocation(s,Math.max(0,Math.min(budget,cash)),s.ratePct,s.gainPct,fee,continuous);
   if(!a.shares){insufficient++;continue;}
   cash-=a.frozen;
   events.push({date:day(s.refundDate),money:a.frozen-a.principal});
   events.push({date:day(s.listingDate)+1,money:a.principal+Math.min(0,a.profit)});
   profit+=a.profit;allotted+=a.allotted;participated++;
   ledger.push({...a,code:s.code,name:s.name,date:s.applyDate,release:iso(day(s.listingDate)+1)});
  }
  const days=Math.max(1,day(end)-day(start)+1);
  return {profit,allotted,participated,missing,insufficient,total:scope.length,days,annual:budget?profit/budget*365/days*100:0,returnPct:budget?profit/budget*100:0,ledger,end};
 }
 function scenarios(records,stock,today,size=20){
  const cutoff=stock.applyDate&&stock.applyDate<today?stock.applyDate:today;
  const samples=records.filter(x=>x.code!==stock.code&&x.listingDate&&x.listingDate<cutoff&&x.applyDate>='2021-11-15'&&finite(x.ratePct)&&x.ratePct>0&&x.ratePct<=100).sort((a,b)=>b.listingDate.localeCompare(a.listingDate)).slice(0,size);
  const rates=samples.map(x=>x.ratePct).sort((a,b)=>a-b);
  const quantile=p=>{if(!rates.length)return null;const index=(rates.length-1)*p,lo=Math.floor(index);return rates[lo]+(rates[Math.ceil(index)]-rates[lo])*(index-lo);};
  return {samples,cutoff,optimistic:quantile(.75),baseline:quantile(.5),pessimistic:quantile(.25)};
 }
 function funding(stock,budget,rate){
  if(!finite(budget)||budget<0||!finite(stock.price)||stock.price<=0||!finite(rate)||rate<0||rate>100)return {top:null,target:null,state:'unknown',gap:null,surplus:null};
  const top=stock.price>0&&finite(stock.maxShares)&&stock.maxShares>=100?Math.floor(stock.maxShares/100)*100*stock.price:null;
  const target=threshold(stock.price,rate,stock.maxShares);
  const state=!top?'unknown':rate===0?'unreachable':!target?'unknown':!target.reachable?'unreachable':budget<target.funds?'short':'enough';
  return {top,target,state,gap:target?Math.max(0,target.funds-budget):null,surplus:target?Math.max(0,budget-target.funds):null};
 }
 function validateModel(records,today,limit=60){
  const keys=['optimistic','baseline','pessimistic'];
  const eligible=records.filter(s=>s.applyDate&&s.applyDate<=today&&s.applyDate>='2021-11-15'&&finite(s.ratePct)&&s.ratePct>0&&s.ratePct<=100&&finite(s.price)&&s.price>0&&finite(s.maxShares)&&s.maxShares>=100).sort((a,b)=>b.applyDate.localeCompare(a.applyDate));
  const rows=[];let excluded=0;
  for(const s of eligible){const w=scenarios(records,s,s.applyDate,20);if(w.samples.length<20){excluded++;continue;}const actual=threshold(s.price,s.ratePct,s.maxShares),predictions={};for(const key of keys){const predicted=threshold(s.price,w[key],s.maxShares);predictions[key]={ratePct:w[key],funds:predicted.funds,errorPct:(predicted.funds/actual.funds-1)*100,underfunded:predicted.funds<actual.funds,withinLimit:predicted.reachable};}rows.push({code:s.code,name:s.name,applyDate:s.applyDate,actualRatePct:s.ratePct,actualFunds:actual.funds,actualWithinLimit:actual.reachable,predictions});}
  const recent=rows.slice(0,limit),quantile=(values,p)=>{if(!values.length)return null;const a=[...values].sort((x,y)=>x-y),i=(a.length-1)*p;return a[Math.floor(i)]+(a[Math.ceil(i)]-a[Math.floor(i)])*(i-Math.floor(i));};
  const summary={};for(const key of keys){const x=recent.map(row=>row.predictions[key]);summary[key]={count:x.length,underfundedPct:x.length?x.filter(v=>v.underfunded).length/x.length*100:null,meanAbsErrorPct:x.length?x.reduce((n,v)=>n+Math.abs(v.errorPct),0)/x.length:null,medianAbsErrorPct:quantile(x.map(v=>Math.abs(v.errorPct)),.5),p90AbsErrorPct:quantile(x.map(v=>Math.abs(v.errorPct)),.9),withinLimitCount:x.filter(v=>v.withinLimit).length};}
  return {mode:'历史数据重建验证，非已保存的事前预测',window:20,evaluatedAt:today,count:recent.length,available:rows.length,excludedForInsufficientWindow:excluded,from:recent.at(-1)?.applyDate??null,to:recent[0]?.applyDate??null,summary,rows:recent};
 }
 return {threshold,allocation,backtest,day,iso,finite,scenarios,funding,validateModel};
})();
if(typeof module!=='undefined')module.exports=Engine;
