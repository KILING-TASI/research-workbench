'use strict';
const fs=require('fs');
const esc=x=>String(x??'待核验').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const value=x=>x&&typeof x==='object'&&'value'in x?x.value:x;
const fmt=x=>{x=value(x);return typeof x==='number'&&Number.isFinite(x)?x.toFixed(2):'待核验';};
const percent=x=>{x=value(x);return typeof x==='number'&&Number.isFinite(x)?x*100:null;};
function sourceUrl(raw){
 if(typeof raw!=='string'||/[\s\x00-\x1f\x7f]/.test(raw))throw Error('来源链接须为无凭据HTTP或HTTPS地址');
 let u;try{u=new URL(raw);}catch{throw Error('来源链接无效');}
 if(!['http:','https:'].includes(u.protocol)||!u.hostname||u.username||u.password)throw Error('来源链接须为无凭据HTTP或HTTPS地址');
 return raw;
}
function historicalJudgment(rows,name){
 const finite=x=>typeof x==='number'&&Number.isFinite(x);
 if(rows.length!==2||rows.some(r=>!finite(r.metrics?.CAGRPct)||!finite(r.metrics?.maximumDrawdownPct)||r.metrics.maximumDrawdownPct<0))return {conclusion:'现有资料不足以形成两只产品的收益与回撤取舍判断，应按已取得维度分别阅读。',tension:'历史收益与风险是否匹配，仍需可比数据支持。',positioning:'这里只交付已取得资料的研究比较，不构成完整产品评价。'};
 const [a,b]=rows,ar=a.metrics.CAGRPct,br=b.metrics.CAGRPct,ad=a.metrics.maximumDrawdownPct,bd=b.metrics.maximumDrawdownPct;
 let conclusion,tension;
 if(ar===br&&ad===bd){conclusion='两只产品在本区间的年化收益与最大回撤相同，不能由这两个指标分出优劣。';tension='需要基准、费用与持仓等其他证据才能进一步区分。';}
 else if((ar>=br&&ad<=bd)||(br>=ar&&bd<=ad)){const lead=ar>=br&&ad<=bd?a:b;conclusion=name(lead.code)+'在本区间的收益与最大回撤这两个维度上至少一项更好、另一项不差。';tension='历史结果领先是否具有持续性尚未验证，不能据此归因于经理能力。';}
 else {const higher=ar>br?a:b;conclusion=name(higher.code)+'的本区间年化收益更高，同时经历了更大的最大回撤；两者存在收益与风险的取舍，不能只按收益排序。';tension='较高历史收益伴随更深回撤，选择标准取决于研究关注的风险承受条件。';}
 return {conclusion,tension,positioning:'适用于共同区间的历史表现对照；完整评价还需结合基准、持仓、费用及经理任期。历史回撤不代表未来损失上限。'};
}
function build(r){
 if(r.type!=='integrated-fund-research')throw Error('需综合研究结果');
 for(const url of r.sources)sourceUrl(url);
 const history=r.sections.find(s=>s.result.comparisons)?.result,hold=r.sections.find(s=>s.result.pairs)?.result,contrib=r.sections.find(s=>s.result.type==='portfolio-return-risk-contributions')?.result;
 const rows=history?.comparisons||[],pairs=hold?.pairs||[];
 const names=r.subjectNames||{},name=code=>names[code]?names[code]+'（'+code+'）':code;
 const metricName=key=>({CAGRPct:'年化收益率',annualVolatilityPct:'年化波动率',maximumDrawdownPct:'最大回撤',Sharpe:'夏普比率',Sortino:'索提诺比率',Calmar:'卡玛比率'})[key]||'所列指标';
 const parameterText=params=>Object.entries(params||{}).map(([k,v])=>`${({riskFreeAnnualPct:'假设无风险年利率',frequency:'观察频率',returnBasis:'分红处理方式',units:'计量单位',classificationVersion:'分类版本'})[k]||'补充计算条件'}为${({daily:'日度',monthly:'月度',reinvest:'红利再投',CNY:'人民币'})[v]||String(v)}`).join('；');
 const facts=rows.map(a=>`${name(a.code)}在共同观察区间的年化收益为${fmt(a.metrics.CAGRPct)}%，最大回撤为${fmt(a.metrics.maximumDrawdownPct)}%。`);
 if(pairs.length)facts.push(`已披露股票结构存在差异：${pairs[0].a}与${pairs[0].b}的净资产重合为${fmt(pairs[0].navOverlapPct)}%，已披露股票归一化重合为${fmt(pairs[0].disclosedEquityNormalizedOverlapPct)}%。`);
 const judgment=historicalJudgment(rows,name),summary=judgment.conclusion;
 const table=(headers,data)=>`<div class="table-wrap"><table><thead><tr>${headers.map(x=>`<th>${esc(x)}</th>`).join('')}</tr></thead><tbody>${data.map(row=>`<tr>${row.map(x=>`<td>${esc(x)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
 const list=xs=>`<ul>${xs.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;
 const section=(n,title,text)=>`<section><div class="section-head"><span>${n}</span><h2>${title}</h2></div>${text}</section>`;
 const unavailable=text=>`<p class="muted">${esc(text)}</p>`;
 let body=`<header><div class="eyebrow">基金研究 · 综合评价与复盘</div><h1>${esc(r.title)}</h1><p class="meta">研究截止 ${esc(r.asOf)} · ${r.subjectCodes.map(esc).join(' / ')}</p></header><div class="notice">${esc(r.riskNotice)}</div>`;
 body+=section('01','核心观点',`<p class="lead">${esc(summary||'资料不足，暂不能形成综合判断。')}</p><p><strong>核心矛盾：</strong>${esc(judgment.tension)}</p><p><strong>判断依据：</strong>${esc(facts.join(' ')||'相关资料待补。')}</p><p><strong>研究定位：</strong>${esc(judgment.positioning)}</p><p>以上描述本次样本的历史结果和披露结构，不能据此判定哪只基金更值得买入，也不能将持仓差异直接解释为收益差异的原因。</p><div class="cards"><div><small>研究对象</small><strong>${rows.length||r.subjectCodes.length}只</strong></div><div><small>共同历史区间</small><strong class="date">${esc(history?history.alignment.start+' — '+history.alignment.end:'待补')}</strong></div><div><small>持仓报告期</small><strong class="date">${esc(hold?[...new Set(hold.funds.map(f=>f.reportDate))].join(' / '):'待补')}</strong></div></div>`);
 body+=section('02','业绩评价：收益与风险并看',history?`<p>采用相同观察日期比较，累计收益净值已包含基金运作费用。本次未提供合同基准与同风格完整样本，不判断同类竞争力或经理超额能力。</p>${table(['基金','年化收益%','年化波动%','最大回撤%','夏普'],rows.map(a=>[name(a.code),fmt(a.metrics.CAGRPct),fmt(a.metrics.annualVolatilityPct),fmt(a.metrics.maximumDrawdownPct),fmt(a.metrics.Sharpe)]))}<p class="muted">共同观察${history.alignment.observations}次；完整交易日历未核验。年化波动与夏普依赖观察频率及无风险利率假设。</p>`:unavailable('缺少净值序列与基准，业绩评价待补。'));
 body+=section('03','持仓结构：重叠与覆盖',hold?`${table(['基金','股票仓位%','披露覆盖%','等效持股数'],hold.funds.map(f=>[f.id,fmt(percent(f.equityWeight)),fmt(f.coveragePct),fmt(f.concentration.effectiveDisclosedNames)]))}${table(['基金组合','净资产重合%','披露股票结构重合%'],pairs.map(p=>[p.a+' / '+p.b,fmt(p.navOverlapPct),fmt(p.disclosedEquityNormalizedOverlapPct)]))}<p>净资产口径衡量已知共同股票占资产的程度；归一化口径衡量已披露股票结构的相似程度。等效持股数是集中度的换算结果，不能当作实际持股数量。未披露部分仍属未知。</p>`:unavailable('缺少原文持仓，不能判断行业集中或底层重合。'));
 body+=section('04','收益来源与风险贡献',contrib?`${table(['资产','收益贡献（百分点）','波动风险占比%','峰谷损失贡献（百分点）'],contrib.assets.map(a=>[a.code,fmt(a.returnContributionPp),fmt(a.riskSharePct),fmt(a.worstDrawdownContributionPp)]))}<p>此处是指定权重组合的资产贡献，不是基金经理行业配置或选股归因。按每观察期无成本恢复权重计算，未计滑点和手续费，与真实账户结果可能不同。</p>`:unavailable('未提供组合权重或可比历史序列，贡献分析待补。'));
 const depth=r.sections.map(x=>x.result).filter(x=>['manager-public-passages','disclosed-category-change','brinson-fachler-single-period','industry-attribution-gap','fund-asset-allocation','fund-disclosed-behavior','fund-holdings-style','fund-research-conditions'].includes(x.type));
 let depthBody='';for(const e of depth){depthBody+=`<h3>${esc(e.code)} · ${esc(e.type==='manager-public-passages'?'经理报告原文':e.type==='disclosed-category-change'?'多期分类变化':e.type==='fund-asset-allocation'?'资产仓位':e.type==='fund-disclosed-behavior'?'披露持仓变迁':e.type==='fund-holdings-style'?'持仓风格':e.type==='fund-research-conditions'?'资料条件核对':'行业归因')}</h3>`;
 if(e.sections)for(const sec of e.sections){depthBody+=`<h4>${esc(sec.kind==='outlook'?'展望（管理人自述）':'回顾（管理人自述）')}</h4>`;for(const x of sec.passages)depthBody+=`<p>${esc(x.text)}</p><p class="muted">PDF第${x.page}页，披露${esc(e.publishedAt)}</p>`;}
 if(e.type==='disclosed-category-change'&&e.pairs)for(const pair of e.pairs)depthBody+=`<p>${esc(pair.startReport)}至${esc(pair.endReport)}：${esc(pair.status)}</p>`+table(['类别','之前%','之后%','变化百分点'],pair.rows.map(x=>[x.category,fmt(x.beforePct),fmt(x.afterPct),fmt(x.changePp)]));
 if(e.type==='fund-asset-allocation')depthBody+=table(['报告期','披露仓位','未知%'],e.rows.map(x=>[x.reportDate,Object.entries(x.weights).map(([k,v])=>`${({aEquity:'A股',hkEquity:'港股',otherEquity:'其他权益',straightBonds:'普通债券',convertibles:'转债',cash:'现金',other:'其他',unknown:'未知'})[k]||k}:${fmt(percent(v))}%`).join(' / '),fmt(x.unknownPct)]));
 if(e.type==='fund-disclosed-behavior')depthBody+=table(['前后报告期','共同证券数','观察留存%','范围'],e.pairs.map(x=>[x.startReport+' / '+x.endReport,x.commonCount,fmt(x.observedRetentionPct),x.scopeMeaning]));
 if(e.type==='fund-holdings-style')depthBody+=table(['报告期','分类覆盖%','状态'],e.rows.map(x=>[x.reportDate,fmt(x.coveragePct),x.reason||x.status]));
 if(e.type==='fund-research-conditions')depthBody+=table(['条件','观察值','状态'],e.checks.map(x=>[x.field,fmt(x.value),x.status]));
 if(e.totals)depthBody+=table(['配置贡献','选择贡献','交互贡献','快照超额（百分点）'],[[fmt(e.totals.allocationPp),fmt(e.totals.selectionPp),fmt(e.totals.interactionPp),fmt(e.activeSnapshotReturnPp)]]);
 if(e.missingIndustries)depthBody+=unavailable('行业收益缺失：'+e.missingIndustries.join('、'));
 depthBody+=list(e.limitations||[]);}
 body+=section('05','风格、行业与经理观点',depthBody||unavailable('相关证据未取得，不能给出风格稳定、言行一致或择时能力评级。'));
 let supplemental='';
 for(const {result:e} of r.sections){
  if(e.type==='fund-evaluation-foundation'){
   supplemental+=`<h3>${esc(name(e.code))} · 产品定位</h3>`;
   for(const x of e.profile)supplemental+=`<p><strong>${esc(x.label)}：</strong>${esc(x.text)}</p><p class="muted">${esc(x.locator)}，披露于${esc(x.publishedAt)}</p>`;
   supplemental+='<h3>规模与持有人结构</h3>';
   for(const x of e.structure){supplemental+=`<p>截至${esc(x.reportDate)}，${x.netAssetsCNY==null?'净资产尚未取得':'净资产约'+fmt(x.netAssetsCNY/1e8)+'亿元'}。${x.netAssetsChangePct==null?'':'与上一份同口径报告相比变化'+fmt(x.netAssetsChangePct)+'%；这同时受到投资涨跌和申赎影响，不能直接视为资金流出。'}${x.institutionPct==null?'':'机构持有份额占比为'+fmt(x.institutionPct)+'%。'}${x.holderCount==null?'':'披露持有人共'+Number(x.holderCount).toLocaleString('zh-CN')+'户。'}</p>`;}
   supplemental+='<h3>经理任职期间的产品表现</h3>';
   for(const x of e.managerPeriods){supplemental+=`<p><strong>${esc(x.name)}</strong>：原文记录的任职开始日为${esc(x.reportedStart)}。${x.metrics?'本次能计算的区间为'+esc(x.actualStart)+'至'+esc(x.actualEnd)+'，区间收益为'+fmt(x.metrics.totalReturnPct)+'%，最大回撤为'+fmt(x.metrics.maximumDrawdownPct)+'%。':'目前没有足够的任职区间净值，暂不计算收益风险。'}${x.fullTenureCovered?'':'这些数据不代表已覆盖完整任职历史。'}${x.coManagementIntervals.length?'其中存在共同管理区间，不能将产品表现全部归给某一位经理。':''}</p>`;}
   supplemental+='<h3>距完整评价还缺哪些资料</h3>'+list(e.missing)+list(e.limitations);
  }
  if(e.type==='fund-series-quality'){
   const coverage=e.dateCompleteness?.dateCoveragePct;
   supplemental+=`<h3>${esc(name(e.code))} · 净值资料是否可靠</h3><p>本次检查了${e.observations}个净值记录。${e.findings.length?'发现'+e.findings.length+'处需要进一步核查的变化。':'在设定的检查范围内，未发现明显跳变或长时间连续不变的情况。'}${coverage==null?'由于尚未核对适用于该基金的完整交易日历，目前不能确认是否缺少交易日记录。':'已覆盖适用日历中'+fmt(coverage)+'%的观察日期。'}</p><p>这项检查用于发现资料问题，不能据此保证所有数据都准确。</p>`;
   if(e.findings.length)supplemental+=table(['需要核查的情况','时间','为什么需要核查'],e.findings.map(x=>[x.kind==='flat-run'?'净值连续不变':'净值变化较大',x.date||x.start+' — '+x.end,x.status]));
  }
  if(e.type==='fund-distribution-bases')supplemental+=`<h3>${esc(name(e.code))} · 分红怎样影响收益</h3><p>在这段历史中，假设将分红按除息日净值重新投入，区间收益为${fmt(e.reinvest.totalReturnPct)}%；如果保留分红、不再投入且现金不计利息，账户区间收益为${fmt(e.cashDividend.totalReturnPct)}%。二者的差别来自分红之后是否继续参与基金涨跌。再投是计算假设，不代表产品实际允许该方式；应收红利也不等于已经到账的可用资金。</p>`;
  if(e.type==='fund-multi-benchmark'){
   supplemental+=`<h3>${esc(name(e.code))} · 与不同参照相比</h3><p>下面比较基金与不同参照的历史表现。正的超额表示这段时间基金收益较高，负值表示较低；这不能单独证明经理能力。自定义参照不等于基金合同约定的业绩基准。</p>`+table(['比较参照','基金收益高出/低出（百分点）','年化跟踪误差%','信息比率'],e.benchmarks.map(x=>[x.name,fmt(x.excessTotalReturnPp),fmt(x.annualTrackingErrorPct),fmt(x.informationRatio)]));
   supplemental+='<p class="muted">跟踪误差描述基金与参照之间的历史收益差异有多大；信息比率描述这些差异是否带来了超额收益。参照来源、观察窗口和权重规则不同，结果也会不同。</p>';
  }
  if(e.type==='fund-research-snapshot-diff'){
   supplemental+=`<h3>与上次研究相比，哪些发生了变化</h3><p>比较${esc(e.beforeAsOf)}与${esc(e.afterAsOf)}的两次研究。${e.methodologyChanges.length?'两次使用的观察窗口或计算条件发生了变化，因此下表只展示数值，不把差额解释为可直接比较的变化。':'记录的计算口径一致，可以观察指标数值的变化，但不能直接解释为基金经理能力变化。'}</p>`+table(['基金与指标','上次结果','本次结果'],e.metrics.map(x=>{const parts=x.metric.split('.');return [name(parts[0])+' · '+metricName(parts.at(-1)),fmt(x.before),fmt(x.after)];}));
  }
  if(e.type==='fund-evidence-package'){
   supplemental+='<h3>逐项结论与证据</h3>';
   for(const c of e.conclusions){supplemental+=`<details><summary>${esc(c.text)} · ${esc(({'disclosed-fact':'原文披露',calculated:'计算结果',estimate:'假设估算',withheld:'暂不判断'})[c.grade])}</summary><p>${esc(c.coverage?'覆盖'+fmt(c.coverage.pct)+'%，'+c.coverage.meaning:'')}</p>`;
    for(const id of c.evidenceIds){const q=e.evidence.find(x=>x.id===id);supplemental+=`<p>${esc(q.field||q.id)}：${esc(q.value)} · ${esc(q.locator||'')} ${q.sourceUrl?`<a href="${esc(sourceUrl(q.sourceUrl)+(q.page?'#page='+q.page:''))}" target="_blank" rel="noopener">查看原文</a>`:''}</p>`;if(q.formula)supplemental+=`<p>公式：${esc(q.formula)}；参数：${esc(parameterText(q.parameters))}</p>`;}
    supplemental+=list(c.limitations)+'</details>';
   }
  }
  if(['fund-series-quality','fund-distribution-bases','fund-multi-benchmark','fund-research-snapshot-diff','fund-evidence-package'].includes(e.type))supplemental+=list(e.limitations||[]);
 }
 if(supplemental)body+=section('补充','数据口径、对标与可复查结论',supplemental);
 body+=`<div class="chapter">阶段复盘</div>`;
 const attribution=depth.filter(e=>e.type==='brinson-fachler-single-period'&&e.totals);
 const attributionRecap=attribution.length?'已取得'+attribution.length+'项单期Brinson快照归因，见行业归因表；不代表完整多期或真实交易归因。':'缺期初行业权重与行业收益，不能归因';
 const recapRows=[['期间表现如何',summary||'待补净值与持仓'],['资产贡献',contrib?'见资产贡献表，属于指定权重历史模拟':'待补组合权重与序列'],['行业配置与选股',attributionRecap],['风格变化或主动调仓','披露快照可比较变化；真实交易行为仍需交易证据'],['事前判断与结果偏差','没有事前冻结判断，不编造事后准确率']];
 body+=section('06','复盘：发生了什么，哪些可以解释',table(['复盘问题','本次证据与结论'],recapRows)+'<p>复盘将历史事实与原因假设分开。收益贡献可勾稽，不代表已经解释基金经理的决策过程；当前持仓也不能倒推全年操作。</p>');
 body+=section('07','风险与待核验事项',list([...r.conflicts,...r.missing,'历史回撤不是未来损失上限；低持仓重合不保证危机中的低相关','资料截止日与持仓报告期不同，快照不代表实时持仓']));
 body+=section('08','资料来源与阅读说明',`<ol>${r.sources.map((url,i)=>`<li><a href="${esc(url)}" target="_blank" rel="noopener">资料 ${i+1} · ${esc(new URL(url).hostname)}</a></li>`).join('')}</ol>${list(r.limitations)}<p class="muted">本报告参照机构研究报告的论证结构独立编排，不复制其正文、标识或评级体系。</p>`);
 const html=`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${esc(r.title)}</title><style>*{box-sizing:border-box}body{margin:0;background:#eef2f6;color:#24334a;font:15px/1.8 "Microsoft YaHei",sans-serif}.paper{max-width:1080px;margin:32px auto;background:white;padding:48px 60px;box-shadow:0 12px 40px #24334a0d}header{border-top:7px solid #1a5d85;padding-top:24px;border-bottom:1px solid #dce5eb;padding-bottom:20px}.eyebrow{color:#267292;font-size:13px;letter-spacing:2px}h1{font-size:30px;line-height:1.5;margin:12px 0;color:#17364b}.meta,.muted{color:#718094;font-size:13px}.notice{background:#fff7e9;border-left:3px solid #d6a14f;padding:13px 18px;margin:24px 0;font-size:13px}.section-head{display:flex;align-items:center;gap:12px}.section-head span{color:#217596;font-size:13px;font-weight:bold}.section-head h2{font-size:21px;color:#17364b}section{padding:12px 0 24px;border-bottom:1px solid #e7edf1}.lead{font-size:17px;line-height:1.9}.cards{display:grid;grid-template-columns:1fr 2fr 1.4fr;gap:14px;margin:24px 0}.cards div{padding:16px;background:#f4f8fa;border:1px solid #e1eaef}.cards small{display:block;color:#728496}.cards strong{font-size:24px;color:#1a5d85}.cards .date{font-size:15px}.table-wrap{overflow-x:auto;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:14px}th{background:#eaf2f6;color:#204e68;text-align:left}td,th{padding:12px 14px;border-bottom:1px solid #dde7ed}tr:nth-child(even){background:#f9fbfc}td:not(:first-child){font-variant-numeric:tabular-nums}.chapter{margin:36px 0 8px;color:#1a5d85;font-size:25px;font-weight:bold}a{color:#1a6e98}li{margin:7px 0}@media(max-width:700px){.paper{margin:0;padding:24px 20px}.cards{grid-template-columns:1fr}h1{font-size:25px}}@media print{body{background:white}.paper{box-shadow:none;margin:0;padding:16px}section{break-inside:avoid}a{color:inherit}}</style><main class="paper">${body}</main></html>`;
 return {html,summary,judgment};
}
module.exports={build,historicalJudgment};
if(require.main===module){const [input,out]=process.argv.slice(2);if(!input||!out||fs.existsSync(out))throw Error('需输入结果与新HTML路径');const r=require('./strict_json.js').parse(fs.readFileSync(input,'utf8').replace(/^\uFEFF/,''));fs.writeFileSync(out,build(r).html,{flag:'wx'});}
