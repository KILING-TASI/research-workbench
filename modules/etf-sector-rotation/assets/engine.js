(function(root){
'use strict';
const finite=n=>typeof n==='number'&&Number.isFinite(n),dims=['fundamental','capital','technical','news'];
const presets={equal:[25,25,25,25],recovery:[35,20,15,30],overheat:[20,35,30,15],stagflation:[15,20,35,30],recession:[30,15,20,35]};
function redistribute(weights,index,value){
 if(!Number.isInteger(index)||index<0||index>3)throw Error('权重维度须为0至3的整数');
 if(!Array.isArray(weights)||weights.length!==4||weights.some(x=>!finite(x)||x<0))throw Error('权重无效');
 value=Math.min(100,Math.max(0,Number(value)));if(!finite(value))throw Error('权重无效');
 const sum=weights.reduce((a,b,i)=>a+(i===index?0:b),0),remaining=100-value;
 const next=weights.map((w,i)=>i===index?value:sum?remaining*w/sum:remaining/3);
 const last=next.findIndex((_,i)=>i!==index);next[last]+=100-next.reduce((a,b)=>a+b,0);return next;
}
function percentile(value,values,invert=false){
 const a=values.filter(finite);if(!finite(value)||a.length<3)return null;
 const lower=a.filter(v=>v<value).length,equal=a.filter(v=>v===value).length;
 const score=(lower+(equal-1)/2)/(a.length-1)*100;
 return invert?100-score:score;
}
const day=s=>{if(typeof s!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(s))return NaN;const t=Date.parse(s+'T00:00:00Z');return finite(t)&&new Date(t).toISOString().slice(0,10)===s?t/86400000:NaN;};
function news(events,sector,date){
 let impact=0;const items=[];
 for(const e of events||[]){
  if(e.verified!==true||!e.sectors?.includes(sector)||!/^https:\/\//.test(e.url||'')||!['major','normal'].includes(e.level)||![1,-1].includes(e.direction))continue;
  const age=day(date)-day(e.date);if(!finite(age)||age<0)continue;
  const contribution=e.direction*(e.level==='major'?20:10)*Math.max(0,1-age/7);
  impact+=contribution;items.push({...e,age,contribution});
 }
 return {score:Math.max(0,Math.min(100,50+impact)),items};
}
function calculate(snapshot,weights,date){
 if(weights.length!==4||weights.some(w=>!finite(w)||w<0)||Math.abs(weights.reduce((a,b)=>a+b,0)-100)>1e-6)throw Error('四维权重须合计100');
 const active=snapshot.sectors.filter(s=>!s.stale&&s.date===snapshot.date);
 const proxyCount=active.filter(s=>s.proxy).length,proxyBasis=proxyCount>active.length/2;
 const usable=active.filter(s=>Boolean(s.proxy)===proxyBasis);
 const keys=['earnings','roe','valuation','flow','trend','ma','volume'];
 const pools=Object.fromEntries(keys.map(k=>[k,usable.map(s=>s.raw?.[k]).filter(finite)]));
 return snapshot.sectors.map(s=>{
  const eligible=!s.stale&&s.date===snapshot.date&&Boolean(s.proxy)===proxyBasis,raw=s.raw||{};
  const indicator=Object.fromEntries(keys.map(k=>[k,eligible?percentile(raw[k],pools[k],k==='valuation'):null]));
  const avg=names=>names.every(k=>finite(indicator[k]))?names.reduce((a,k)=>a+indicator[k],0)/names.length:null;
  const n=news(snapshot.events,s.id,date);
  const scores={fundamental:avg(['earnings','roe','valuation']),capital:indicator.flow,technical:avg(['trend','ma','volume']),news:eligible?n.score:null};
  const complete=dims.every(k=>finite(scores[k]));
  const total=complete?dims.reduce((a,k,i)=>a+scores[k]*weights[i]/100,0):null;
  return {...s,indicator,scores,total,events:n.items,modelStatus:complete?'可用数据评分（资金面缺北向指标）':'数据不足，不参与排名'};
 }).sort((a,b)=>(b.total??-Infinity)-(a.total??-Infinity)||a.name.localeCompare(b.name,'zh-CN')).map((s,i)=>({...s,rank:finite(s.total)?i+1:null}));
}
function chooseFunds(funds,date){
 const specs=[['sizeYi',.25,false],['avgAmountYi',.30,false],['trackingErrorPct',.20,true],['feePct',.15,true],['age',.10,false]];
 const a=funds.map(f=>({...f,age:finite(day(f.inceptionDate))?(day(date)-day(f.inceptionDate))/365.25:null}));
 const active=a.filter(f=>!f.stale);
 // Compare the same observed factors across both candidates, never missing-as-zero.
 const common=specs.filter(([k])=>active.length>=2&&active.every(f=>finite(f[k])));
 const coverage=common.reduce((x,s)=>x+s[1],0);
 return a.map(f=>{
  const score=!f.stale&&coverage>=.6?common.reduce((sum,[k,w,inverse])=>{
   const values=active.map(x=>x[k]),min=Math.min(...values),max=Math.max(...values);
   const p=max===min?50:(f[k]-min)/(max-min)*100;
   return sum+(inverse?100-p:p)*w/coverage;
  },0):null;
  return {...f,selectionScore:score,selectionCoverage:coverage,selectionFactors:common.map(s=>s[0])};
 }).sort((a,b)=>(b.selectionScore??-Infinity)-(a.selectionScore??-Infinity)||a.code.localeCompare(b.code));
}
function allocate(rows,selected){
 const chosen=rows.filter(s=>selected.includes(s.id)&&finite(s.total)&&s.total>0).slice(0,3);
 if(!chosen.length)return [];
 const total=chosen.reduce((a,s)=>a+s.total,0);
 // At least three sectors are needed for a 40% cap; fewer retain cash.
 let remaining=100,pending=chosen.map(s=>({...s,allocation:0}));
 for(let round=0;round<4&&pending.length;round++){
  const sum=pending.reduce((a,s)=>a+s.total,0),capped=pending.filter(s=>remaining*s.total/sum>40);
  if(!capped.length){pending.forEach(s=>s.allocation=remaining*s.total/sum);remaining=0;break;}
  capped.forEach(s=>{s.allocation=40;remaining-=40;});pending=pending.filter(s=>!capped.includes(s));
 }
 if(chosen.length<3)chosen.forEach(s=>{s.allocation=Math.min(40,100*s.total/total);});
 else chosen.forEach(s=>{const x=pending.find(p=>p.id===s.id);s.allocation=x?.allocation??40;});
 return chosen.map(s=>({id:s.id,name:s.name,pct:s.allocation}));
}
const api={finite,dims,presets,redistribute,percentile,day,news,calculate,chooseFunds,allocate};
root.ETFEngine=api;if(typeof module!=='undefined')module.exports=api;
})(typeof globalThis!=='undefined'?globalThis:this);

/* Transparent research baseline; no historical performance claim. */

const ETFRotationModel=(()=>{
 const config=Object.freeze({lookback:20,rebalanceDays:5,minHoldDays:9,rankGap:0.10,maxSwaps:1});
 function validPrices(p,n){return Array.isArray(p)&&p.length>=n&&p.slice(-n).every(x=>Number.isFinite(x)&&x>0);}
 function rank(rows){
  // Rows must be one point-in-time industry ETF per index, on an aligned trading calendar.
  const valid=rows.filter(r=>r.eligible===true&&r.type==='industry'&&r.symbol&&r.index&&validPrices(r.closes,21));
  if(new Set(valid.map(r=>r.index)).size!==valid.length||new Set(valid.map(r=>r.symbol)).size!==valid.length)throw Error('重复ETF或指数映射');
  const out=valid.map(r=>({symbol:r.symbol,momentum:r.closes.at(-1)/r.closes.at(-21)-1}));
  if(out.length<2)return [];
  return out.map(r=>{const less=out.filter(x=>x.momentum<r.momentum).length,equal=out.filter(x=>x.momentum===r.momentum).length;return {...r,rank01:(less+(equal-1)/2)/(out.length-1)};}).sort((a,b)=>b.rank01-a.rank01||a.symbol.localeCompare(b.symbol));
 }
 function exposure(closes){
  if(!validPrices(closes,26))return {ready:false,volatility:null,target:null};
  function vol(end){const prices=closes.slice(end-21,end),returns=prices.slice(1).map((p,i)=>p/prices[i]-1),mean=returns.reduce((a,b)=>a+b,0)/20;return Math.sqrt(returns.reduce((a,b)=>a+(b-mean)**2,0)/19)*Math.sqrt(252)*100;}
  const v=(vol(closes.length)+vol(closes.length-5))/2;
  return {ready:true,volatility:v,target:v>=40?.1:v>=30?.4:v>=25?.7:1,effective:'next_trading_day'};
 }
 function mayReplace({holdingRank,candidateRank,heldTradingDays,isRebalance,swaps=0}){
  return isRebalance===true&&Number.isInteger(swaps)&&swaps>=0&&swaps<config.maxSwaps&&Number.isInteger(heldTradingDays)&&heldTradingDays>=config.minHoldDays&&Number.isFinite(holdingRank)&&Number.isFinite(candidateRank)&&holdingRank>=0&&holdingRank<=1&&candidateRank>=0&&candidateRank<=1&&candidateRank-holdingRank>=config.rankGap-1e-12;
 }
 return {config,rank,exposure,mayReplace};
})();
