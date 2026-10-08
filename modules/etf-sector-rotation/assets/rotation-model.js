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
