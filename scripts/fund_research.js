'use strict';
const api=require('./research_analytics.js');
const num=(v,n,min=0)=>{if(typeof v!=='number'||!Number.isFinite(v)||v<min)throw Error(n+'无效');return v;};
const day=v=>{if(typeof v!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(v)||!Number.isFinite(Date.parse(v+'T00:00:00Z'))||new Date(v+'T00:00:00Z').toISOString().slice(0,10)!==v)throw Error('日期无效');return v;};
const source=v=>{if(typeof v!=='string'||/[\s\x00-\x1f\x7f]/.test(v))throw Error('来源地址无效');let u;try{u=new URL(v);}catch(e){throw Error('来源地址无效');}if(!['http:','https:'].includes(u.protocol)||!u.hostname||u.username||u.password)throw Error('来源地址须为无凭据的HTTP或HTTPS地址');};
const notes={CAGRPct:'年化收益率（时间加权，几何年化）；总收益序列口径，非现金流加权，非未来预测',annualVolatilityPct:'历史收益波动幅度，不是最大亏损',maximumDrawdownPct:'本区间从高点至低点最大跌幅，不包括区间前高点',Sharpe:'相对所设无风险利率的单位波动超额收益，零波动留空',Sortino:'相对目标收益的单位下行风险收益，下行样本少时不稳定',Calmar:'历史年化收益除以最大回撤，窗口选择影响较大'};
function align(d){
 if(!d||typeof d!=='object'||Array.isArray(d))throw Error('历史输入须为对象');if(typeof d.currency!=='string'||!d.currency.trim())throw Error('需明确币种');
 day(d.asOf);if(d.start&&d.end&&day(d.start)>day(d.end))throw Error('研究起止日期顺序无效');if(!Array.isArray(d.assets)||!d.assets.length)throw Error('缺基金序列');
 const all=[...d.assets,...(d.reference?[d.reference]:[])];if(all.some(a=>!a||typeof a!=='object'||!Array.isArray(a.history)||!a.history.length))throw Error('每个标的需非空历史序列');
 if(new Set(all.map(a=>a.code)).size!==all.length)throw Error('代码重复，基准不可混用同一代码');
 for(const a of all){if(a.availableAt!=null&&day(a.availableAt)>d.asOf)throw Error('资料可得日超过研究截止日');if(a.dividendCalendarVerified!=null&&typeof a.dividendCalendarVerified!=='boolean')throw Error('分红日历核验声明须为布尔值');}
 for(const a of all){source(a.sourceUrl);if(!a.code||a.basis!=='total-return'||a.currency!==d.currency)throw Error('需唯一代码、同币种、总收益口径');let last='';for(const h of a.history||[]){day(h.date);if(h.date<=last||h.date>d.asOf)throw Error('日期重复乱序或晚于截止日');if(num(h.value,'净值')===0)throw Error('净值须正');last=h.date;}}
 let dates=all[0].history.map(h=>h.date).filter(t=>(!d.start||t>=day(d.start))&&(!d.end||t<=day(d.end)));
 const sets=all.map(a=>new Set(a.history.map(h=>h.date)));dates=dates.filter(t=>sets.every(s=>s.has(t)));if(dates.length<4)throw Error('共同区间至少四期观察，缺数据不填充');
 let benchmarkVersion=null;
 if(d.reference){
  const from=d.reference.validFrom==null?null:day(d.reference.validFrom),through=d.reference.validThrough==null?null:day(d.reference.validThrough);
  if(from&&through&&from>through)throw Error('基准有效期顺序无效');
  if(from&&dates[0]<from||through&&dates.at(-1)>through)throw Error('共同研究区间超出基准声明有效期，需分段基准，不得回填历史');
  benchmarkVersion={validFrom:from,validThrough:through,status:from||through?'declared-period-covers-window-not-externally-verified':'effective-period-not-declared'};
 }
 const selected=new Set(dates),rows=all.map(a=>({...a,history:a.history.filter(h=>selected.has(h.date))}));
 return {input:{...d,assets:rows.slice(0,d.assets.length).map(a=>({...a,weight:1/d.assets.length})),reference:d.reference?rows.at(-1):undefined},alignment:{start:dates[0],end:dates.at(-1),observations:dates.length,removed:all.map(a=>({code:a.code,removedObservations:a.history.length-dates.length})),calendarComplete:false,benchmarkVersion}};
}
function compare(d){
 const aligned=align(d),r=api.historical(aligned.input),keys=Object.keys(notes),median=xs=>{xs.sort((a,b)=>a-b);let k=Math.floor(xs.length/2);return xs.length%2?xs[k]:(xs[k-1]+xs[k])/2;};
 const comparisons=r.assets.map(a=>({code:a.code,metrics:Object.fromEntries(keys.map(k=>{let pool=r.assets.map(x=>x[k]).filter(Number.isFinite),m=pool.length?median(pool):null,v=a[k],direction=['annualVolatilityPct','maximumDrawdownPct'].includes(k)?'lower':'higher';return [k,{value:v,poolMedian:m,relation:v===null||m===null?'unknown':v===m?'equal':(direction==='lower'?v<m:v>m)?'above-pool-on-this-metric':'below-pool-on-this-metric',definition:notes[k]}];}))}));
 let events=(d.events||[]).map(e=>{day(e.publishedAt);source(e.sourceUrl);if(e.publishedAt>d.asOf||!d.assets.some(a=>a.code===e.code)||!e.title||!['confirmed','unverified'].includes(e.status))throw Error('事件主体日期或状态不符');return e;});
 return {type:'fund-comparison',riskNotice:'本金可能亏损，历史指标不代表未来，不构成投资建议',alignment:aligned.alignment,comparisons,correlation:{codes:r.codes,matrix:r.correlations},benchmark:d.reference?api.benchmarkStudy({...aligned.input,rollingObservations:Math.min(12,aligned.alignment.observations-1)}):null,events,limitations:['池内中位数只描述本次输入基金，不代表全市场同类；风格可比性需另核','现存基金池可能遗漏清盘产品，样本范围须注明','共同观察日计算不证明日频交易日完整；未自动填充缺失','相关性随时间变化，不能保证分散效果','基金总收益净值已含运作费用，不重复扣费']};
}
function feeStudy(d){
 day(d.asOf);if(d.basis!=='constant-gross-nav-cost-scenario')throw Error('费用测算仅支持明确恒定费前净值情景，不能再次扣历史净值运作费');
 const classes=d.classes;if(!Array.isArray(classes)||classes.length!==2||new Set(classes.map(c=>c.id)).size!==2)throw Error('需要两个不同份额类别');
 const lots=d.lots;if(!Array.isArray(lots)||!lots.length)throw Error('需逐笔投入');
 for(const l of lots){day(l.date);if(num(l.amount,'投入金额')<=0)throw Error('金额须正');}
 for(const c of classes){source(c.sourceUrl);day(c.observedAt);if(c.observedAt>d.asOf)throw Error('费率来源晚于截止日');for(const k of ['managementPct','custodyPct','salesServicePct','subscriptionPct'])if(num(c[k],k)>100)throw Error('费率须百分数');let prev=-1;for(const b of c.redemption||[]){if(!Number.isInteger(b.minDays)||b.minDays<0||b.minDays<=prev||num(b.ratePct,'赎回费')>100)throw Error('赎回阶梯须严格递增');prev=b.minDays;}if(c.redemption?.[0]?.minDays!==0)throw Error('赎回阶梯从0日开始');}
 const start=lots.reduce((a,l)=>a<l.date?a:l.date,lots[0].date),horizon=d.horizonDays??1095;if(!Number.isInteger(horizon)||horizon<1||horizon>7300)throw Error('期限1至7300日');
 const rows=[];for(let n=0;n<=horizon;n++){let date=new Date(Date.parse(start+'T00:00:00Z')+n*86400000).toISOString().slice(0,10),active=lots.filter(l=>l.date<=date);let paid=active.reduce((s,l)=>s+l.amount,0);let values=classes.map(c=>{let terminal=0,subscription=0,redemption=0,operating=0;for(const l of active){let age=(Date.parse(date)-Date.parse(l.date))/86400000,invested=l.amount/(1+c.subscriptionPct/100),annual=(c.managementPct+c.custodyPct+c.salesServicePct)/100,nav=invested*Math.exp(-annual*age/365),rate=c.redemption.filter(b=>b.minDays<=age).at(-1).ratePct/100;subscription+=l.amount-invested;operating+=invested-nav;redemption+=nav*rate;terminal+=nav*(1-rate);}return {id:c.id,terminal,cost:paid-terminal,subscription,operating,redemption};});let diff=values[0].cost-values[1].cost;rows.push({date,days:n,paid,classes:values,lowerCost:Math.abs(diff)<1e-8?'equal':diff<0?classes[0].id:classes[1].id});}
 const transitions=rows.filter((row,i)=>i&&row.lowerCost!==rows[i-1].lowerCost).map(row=>({day:row.days,date:row.date,lowerCost:row.lowerCost}));
 return {type:'share-class-cost-scenario',basis:d.basis,schedule:rows.filter(row=>row.days===0||row.days===horizon||(d.showDays||[30,90,180,365,730]).includes(row.days)),costPreferenceTransitions:transitions,limitations:['无收益恒定费前净值情景；非真实净值收益、非投资推荐','运作费以连续年率近似计提，未包括实际每日计提及税费差异','申购按外扣比例费，非分档或固定收费；折扣须输入','赎回按每笔份额持有日阶梯计费；同日投入假设可赎，产品限制未模拟','临界结果按整日检查，不保证唯一交点；费率变化需重新测算','现行费率仅用于假设区间，不冒充历史有效费率']};
}
function monitor(d){
 day(d.asOf);if(!Array.isArray(d.watchlist)||!d.watchlist.length||new Set(d.watchlist).size!==d.watchlist.length||d.watchlist.some(c=>typeof c!=='string'||!c.trim()))throw Error('自选代码须非空唯一');let seen={...(d.seen||{})},alerts=[],batch=new Set();
 for(const e of d.events||[]){if(!d.watchlist.includes(e.code))continue;source(e.sourceUrl);day(e.publishedAt);if(!e.id||!e.title||e.publishedAt>d.asOf||!['confirmed','unverified'].includes(e.status))throw Error('事件不完整');let key=e.code+':'+e.id,sig=JSON.stringify(e);if(batch.has(key))throw Error('同批事件编号重复，须先核对版本');batch.add(key);if(seen[key]!==sig)alerts.push({...e,change:seen[key]?'updated':'new',label:e.status==='confirmed'?'已确认来源信息':'未核实线索'});seen[key]=sig;}
 return {type:'fund-watchlist-diff',asOf:d.asOf,watchlist:d.watchlist,alerts,seen,limitations:['只检查输入的事件，不代表已自动抓取全部基金公告','按需执行差异识别，不是后台推送服务；需另设调度才持续运行','传闻保留未核实状态，不能据此断言经理离职']};
}
function simulate(d){
 const union=d.historyInput,aligned=align(union),codes=aligned.input.assets.map(a=>a.code);
 const view=weights=>{if(!weights||Object.keys(weights).some(k=>!codes.includes(k)))throw Error('权重含未知标的');let total=0;for(const w of Object.values(weights)){num(w,'权重');total+=w;}if(Math.abs(total-1)>1e-8)throw Error('权重合计须1，不隐含融资');
 const assets=aligned.input.assets.filter(a=>(weights[a.code]||0)>0).map(a=>({...a,weight:weights[a.code]}));const history=api.historical({...aligned.input,assets});
 let scenarios=(d.scenarios||[]).map(sc=>{if(!sc.name||!sc.shocksPct)throw Error('情景缺名称或冲击');let missing=assets.filter(a=>!Object.hasOwn(sc.shocksPct,a.code)).map(a=>a.code);if(missing.length)return {name:sc.name,returnPct:null,missing};let shock=0;for(const a of assets)shock+=a.weight*num(sc.shocksPct[a.code],'冲击',-100);return {name:sc.name,returnPct:shock,missing:[]};});
 return {weights,concentrationHHI:Object.values(weights).reduce((v,w)=>v+w*w,0),history,scenarios};};
 return {type:'portfolio-adjustment-scenario',alignment:aligned.alignment,before:view(d.beforeWeights),after:view(d.afterWeights),limitations:['历史比较使用新增/原有标的联合共同日期，样本可能缩短','标的权重集中度不是穿透后个股或行业集中度，底层资料需另接持仓分析','历史组合每观察期无费用恢复目标权重，不是实际成交回测','压力值是一次给定冲击损益，不是未来最大回撤','不执行交易或给出增减仓建议']};
}
function scan(d){
 if(!Array.isArray(d.codes)||!d.codes.length||d.codes.length>50||new Set(d.codes).size!==d.codes.length||d.codes.some(c=>typeof c!=='string'||!c))throw Error('批量需1至50个唯一代码');
 return {type:'fund-light-scan',cards:d.codes.map(code=>{let a=d.historyInput?.assets?.find(a=>a.code===code);if(!a)return {code,status:'missing',reason:'未取得历史序列'};try{let result=compare({...d.historyInput,assets:[a],reference:undefined,events:[]});return {code,status:'calculated',start:result.alignment.start,end:result.alignment.end,metrics:result.comparisons[0].metrics,sourceUrl:a.sourceUrl,risks:['历史指标不代表未来','未穿透持仓或核验全部公告']};}catch(e){return {code,status:'failed',reason:e.message};}}),limitations:['逐标的实际区间可能不同，不作为横向排名；对比须另取共同区间','仅处理已经取得的历史数据，缺失标的需先调用collect-batch','轻量扫描不运行公司深度研究、蒙特卡洛或全文公告分析']};
}
function contributions(d){
 const input=d.historyInput,aligned=align(input),weights=d.weights,codes=aligned.input.assets.map(a=>a.code);
 const evidenceStatus=aligned.input.assets.map(a=>({code:a.code,availableAt:a.availableAt??null,publicationStatus:a.availableAt?'input-declared-not-externally-verified':'missing',dividendStatus:a.dividendCalendarVerified===true?'input-declared-verified-not-independently-audited':'unverified'}));
 const evidenceGaps=evidenceStatus.flatMap(a=>[...(a.availableAt?[]:[a.code+'：资料可得日未登记，不能证明历史时点可取得']),...(a.dividendStatus==='unverified'?[a.code+'：分红拆分日历未登记核验，收益口径需复核']:[])]);
 if(!weights||Object.keys(weights).some(c=>!codes.includes(c))||codes.some(c=>!Object.hasOwn(weights,c)))throw Error('每个资产须有明确权重');
 let sum=0;for(const w of Object.values(weights))sum+=num(w,'权重');if(Math.abs(sum-1)>1e-8)throw Error('权重合计须1');
 const assets=aligned.input.assets.map(a=>({...a,weight:weights[a.code]})),h=api.historical({...aligned.input,assets}),cov=h.annualCovariance,w=assets.map(a=>a.weight),variance=w.reduce((v,x,i)=>v+x*w.reduce((n,y,j)=>n+y*cov[i][j],0),0),vol=Math.sqrt(Math.max(0,variance));
 let wealth=1,peak=1,peakIndex=0,lowIndex=0,maxDD=0,ddStart=0,path=[1],returns=assets.map(a=>a.history.slice(1).map((x,i)=>x.value/a.history[i].value-1)),cumulative=w.map(()=>0);
 for(let t=0;t<returns[0].length;t++){let pct=0;for(let i=0;i<w.length;i++){let add=wealth*w[i]*returns[i][t];cumulative[i]+=add;pct+=w[i]*returns[i][t];}wealth*=1+pct;path.push(wealth);if(wealth>peak){peak=wealth;peakIndex=t+1;}let dd=1-wealth/peak;if(dd>maxDD){maxDD=dd;ddStart=peakIndex;lowIndex=t+1;}}
 let episode=w.map(()=>0);for(let t=ddStart;t<lowIndex;t++)for(let i=0;i<w.length;i++)episode[i]+=path[t]/path[ddStart]*w[i]*returns[i][t];
 return {type:'portfolio-return-risk-contributions',evidenceStatus,evidenceGaps,alignment:aligned.alignment,totalReturnPct:(wealth-1)*100,annualVolatilityPct:vol*100,assets:assets.map((a,i)=>{let marginal=vol>0?cov[i].reduce((v,c,j)=>v+c*w[j],0)/vol:null,component=marginal===null?null:w[i]*marginal;return {code:a.code,weight:w[i],returnContributionPp:cumulative[i]*100,marginalVolatilityPct:marginal===null?null:marginal*100,volatilityContributionPp:component===null?null:component*100,riskSharePct:component===null?null:component/vol*100,worstDrawdownContributionPp:episode[i]*100,sourceUrl:a.sourceUrl};}),worstDrawdown:{start:assets[0].history[ddStart].date,end:assets[0].history[lowIndex].date,maximumDrawdownPct:maxDD*100},limitations:['收益贡献按每观察期无成本恢复权重的路径分解，非账户真实现金流','波动贡献按样本协方差计算，可为负；低相关不保证未来对冲','最大回撤区间贡献为同一组合高低点间路径分解，不加权单资产各自最大回撤','未计交易费及滑点；不同再平衡或资金流规则会改变贡献','协方差属于历史样本，不能当作未来风险预算保证']};
}
function finiteResult(v){if(typeof v==='number'&&!Number.isFinite(v))throw Error('计算结果含非有限数值，不能输出为有效研究结果');if(v&&typeof v==='object')for(const x of Object.values(v))finiteResult(x);}
const functions={compare,feeStudy,monitor,align,simulate,scan,contributions};module.exports=Object.fromEntries(Object.entries(functions).map(([key,fn])=>[key,d=>{const result=fn(d);finiteResult(result);return result;}]));
if(require.main===module){const fs=require('fs'),[kind,input,out]=process.argv.slice(2);if(!['compare','feeStudy','monitor','simulate','scan','contributions'].includes(kind)||!input||!out)throw Error('用法：node fund_research.js compare|feeStudy|monitor 输入.json 新结果.json');let raw=fs.readFileSync(input,'utf8').replace(/^\uFEFF/,'');let result=module.exports[kind](require('./strict_json.js').parse(raw));result.inputSha256=require('crypto').createHash('sha256').update(raw).digest('hex');fs.writeFileSync(out,JSON.stringify(result,null,2),{flag:'wx',encoding:'utf8'});}
