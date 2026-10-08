'use strict';
const fs=require('fs'),core=require('./research_analytics.js'),fund=require('./fund_research.js');
const notice='仅作客观研究，不构成投资建议；历史披露、收益和情景结果不代表未来。';
function concentration(items){const total=items.reduce((s,x)=>s+x.weight,0);const raw=items.reduce((s,x)=>s+x.weight*x.weight,0);const normalized=total>0?raw/(total*total):null;return {disclosedNAVWeight:total,navHHI:raw,disclosedEquityHHI:normalized,effectiveDisclosedNames:normalized>0?1/normalized:null,calculation:{inputs:items.map(x=>({code:x.code,market:x.market,weight:x.weight})),navDenominator:1,disclosedDenominator:total,formulas:{navHHI:"sum(weight^2)",disclosedEquityHHI:"sum(weight^2)/sum(weight)^2",effectiveDisclosedNames:"1/disclosedEquityHHI"},scope:"disclosed-securities-only; unknown-assets-excluded"}};}
function overlap(d){
 const r=core.holdingsStudy(d);const by=new Map(r.funds.map(f=>[f.id,f]));
 const pairs=r.pairs.map(p=>{const a=by.get(p.a),b=by.get(p.b);const same=p.observedOverlapWeight!=null;
  const normalized=same&&a.disclosedWeight>0&&b.disclosedWeight>0?p.common.reduce((s,x)=>s+Math.min(x.weightA/a.disclosedWeight,x.weightB/b.disclosedWeight),0):null;
  return {...p,navOverlapPct:same?p.observedOverlapWeight*100:null,disclosedEquityNormalizedOverlapPct:normalized===null?null:normalized*100,normalizationScope:'各基金已披露股票持仓内部归一化；不是全基金重合率',calculation:{denominatorA:a.disclosedWeight,denominatorB:b.disclosedWeight,navFormula:'sum(min(weightA,weightB))*100',normalizedFormula:'sum(min(weightA/denominatorA,weightB/denominatorB))*100',inputs:(p.common||[]).map(x=>({code:x.code,market:x.market,weightA:x.weightA,weightB:x.weightB})),periodsAligned:same}};});
 const funds=r.funds.map(f=>({...f,concentration:concentration(f.holdings)}));
 const positions=r.portfolio.positions;const c=concentration(positions);
 const commonSecurities=positions.map(x=>{const contributors=r.funds.filter(f=>f.holdings.some(h=>h.code===x.code&&h.shareClass===x.shareClass&&(h.securityNamespace||h.market)===(x.securityNamespace||x.market))).map(f=>({code:f.id,allocation:f.allocation,weight:f.holdings.find(h=>h.code===x.code&&h.shareClass===x.shareClass&&(h.securityNamespace||h.market)===(x.securityNamespace||x.market)).weight}));return {...x,contributors};}).filter(x=>x.contributors.length>1);
 return {type:'holdings-dual-basis',asOf:d.asOf,funds,pairs,portfolio:{...r.portfolio,concentration:c},commonSecurities,riskNotice:notice,limitations:[r.note,'归一化结果只描述已披露股票结构；未知仓位保留，不补零，不将其认定现金','有效持股数为1/HHI的等权等效数量，不是实际持股数；净资产HHI不包含未知资产','不统一ETF联接与母基金身份，递归穿透须先取得底层报告']};
}
function similar(d){
 const r=overlap(d.holdingsInput),target=r.funds.find(f=>f.id===d.targetCode);if(!target)throw Error('目标基金不在输入池');
 const rows=r.pairs.filter(p=>p.a===d.targetCode||p.b===d.targetCode).map(p=>({code:p.a===d.targetCode?p.b:p.a,navOverlapPct:p.navOverlapPct,disclosedEquityNormalizedOverlapPct:p.disclosedEquityNormalizedOverlapPct,reportDate:r.funds.find(f=>f.id===(p.a===d.targetCode?p.b:p.a)).reportDate,status:p.status}));
 for(const row of rows){const other=r.funds.find(f=>f.id===row.code),ids=new Set(other.holdings.map(h=>h.key)),targetIds=new Set(target.holdings.map(h=>h.key));row.differences={targetOnly:target.holdings.filter(h=>!ids.has(h.key)).sort((a,b)=>b.weight-a.weight).slice(0,5).map(h=>({name:h.name,code:h.code,market:h.market,navWeightPct:h.weight*100})),candidateOnly:other.holdings.filter(h=>!targetIds.has(h.key)).sort((a,b)=>b.weight-a.weight).slice(0,5).map(h=>({name:h.name,code:h.code,market:h.market,navWeightPct:h.weight*100})),targetCoveragePct:target.coveragePct,candidateCoveragePct:other.coveragePct,summary:row.disclosedEquityNormalizedOverlapPct==null?'报告期不同，暂不比较差异':`同报告期净资产重合${row.navOverlapPct.toFixed(2)}%；双方独有披露持仓单列，未披露部分无法判断`,unavailable:['分类及版本未核验，不判断行业或价值成长相似','未提供同口径费率，不声称费用差异']};}
 const ranking=rows.filter(x=>x.disclosedEquityNormalizedOverlapPct!=null).sort((a,b)=>b.disclosedEquityNormalizedOverlapPct-a.disclosedEquityNormalizedOverlapPct||a.code.localeCompare(b.code));
 return {type:'pool-holdings-similarity',targetCode:d.targetCode,ranking,excluded:rows.filter(x=>x.disclosedEquityNormalizedOverlapPct==null),sampleCount:r.funds.length,riskNotice:notice,limitations:['仅按同报告期已披露股票结构相似度排序，不是收益、风险、费率或产品替换推荐','不代表全市场相似基金搜索，未完成风格/行业联合相似模型','前十大结构相似可能与完整持仓不同，须结合披露覆盖率'],coverage:r.funds.map(f=>({code:f.id,coveragePct:f.coveragePct,disclosureScope:f.disclosureScope,sourceUrl:d.holdingsInput.funds.find(x=>x.id===f.id).sourceUrl}))};
}
function checkEvidenceConclusions(pkg){
 if(!Array.isArray(pkg.evidence)||!Array.isArray(pkg.conclusions))throw Error('证据包须提供证据与结论列表');
 const entries=new Map(),states=new Map(),parents=new Map(),pending=new Map();
 const statuses=['original-disclosed','derived','assumption','missing','conflict'];
 for(const e of pkg.evidence){
  if(!e||typeof e!=='object'||typeof e.id!=='string'||!e.id.trim()||entries.has(e.id)||!statuses.includes(e.status))throw Error('证据身份或状态无效');
  if(!pkg.subjectCodes.includes(e.code))throw Error('证据主体不在研究对象中');
  for(const key of ['disclosedAt','observedAt'])if(e[key]!=null){
   const value=e[key],date=new Date(value+'T00:00:00Z');
   if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value)||!Number.isFinite(date.getTime())||date.toISOString().slice(0,10)!==value||value>pkg.asOf)throw Error('证据日期无效或晚于截止日');
  }
  if(e.observedAt!=null&&e.disclosedAt!=null&&e.observedAt<e.disclosedAt)throw Error('证据取得日不能早于披露日');
  if(e.status==='original-disclosed'){
   if(typeof e.sourceUrl!=='string'||!/^https?:\/\//i.test(e.sourceUrl)||/[\s\x00-\x1f\x7f]/.test(e.sourceUrl)||typeof e.locator!=='string'||!e.locator.trim()||!e.disclosedAt)throw Error('披露证据须有来源、披露日与定位');
   let u;try{u=new URL(e.sourceUrl);}catch(error){throw Error('披露来源URL无效');}
   if(!u.hostname||u.username||u.password||!['','80','443'].includes(u.port))throw Error('披露来源URL无效');
  }
  if(!['missing','conflict'].includes(e.status)&&e.value==null)throw Error('有值证据未提供值');
  if(e.status==='missing'&&e.value!=null)throw Error('缺失证据不能填值');
  if(e.status==='conflict'&&(!Array.isArray(e.alternatives)||e.alternatives.length<2||e.alternatives.some(x=>!x||typeof x!=='object'||Array.isArray(x))))throw Error('冲突证据须保留候选对象');
  const inputs=e.inputEvidenceIds??[];
  if(e.status==='derived'&&(!e.formula||!inputs.length||!e.parameters||typeof e.parameters!=='object'||Array.isArray(e.parameters)||!Object.keys(e.parameters).length))throw Error('计算证据缺公式、输入或参数');
  if(!Array.isArray(inputs)||inputs.some(x=>typeof x!=='string'||!x.trim())||new Set(inputs).size!==inputs.length)throw Error('证据输入依赖无效');
  entries.set(e.id,e);states.set(e.id,new Set([e.status]));parents.set(e.id,[]);pending.set(e.id,inputs.length);
 }
 for(const e of entries.values())for(const id of e.inputEvidenceIds??[]){if(!entries.has(id))throw Error('计算输入证据不存在');parents.get(id).push(e.id);}
 const queue=[...entries.keys()].filter(id=>pending.get(id)===0);let done=0;
 for(let i=0;i<queue.length;i++){
  const id=queue[i];done++;
  for(const parent of parents.get(id)){
   for(const state of states.get(id))states.get(parent).add(state);
   pending.set(parent,pending.get(parent)-1);if(pending.get(parent)===0)queue.push(parent);
  }
 }
 if(done!==entries.size)throw Error('证据输入依赖循环');
 const ids=new Set();
 for(const c of pkg.conclusions){
  if(!c||typeof c.id!=='string'||!c.id.trim()||ids.has(c.id)||typeof c.text!=='string'||!c.text.trim())throw Error('结论身份或正文无效');ids.add(c.id);
  if(!['disclosed-fact','calculated','estimate','withheld'].includes(c.grade))throw Error('结论来源分级无效');
  if(!Array.isArray(c.evidenceIds)||!c.evidenceIds.length||new Set(c.evidenceIds).size!==c.evidenceIds.length||c.evidenceIds.some(id=>!entries.has(id)))throw Error('结论缺少已登记证据');
  if(!Array.isArray(c.limitations)||!c.limitations.length||c.limitations.some(x=>typeof x!=='string'||!x.trim()))throw Error('结论须说明限制');
  const inherited=new Set(c.evidenceIds.flatMap(id=>[...states.get(id)]));
  if(['disclosed-fact','calculated'].includes(c.grade)&&['assumption','missing','conflict'].some(x=>inherited.has(x)))throw Error('假设、缺失或冲突不能升级为确定结论');
  if(c.grade==='disclosed-fact'&&(inherited.size!==1||!inherited.has('original-disclosed')))throw Error('原文披露不能混入推算');
 }
 if(pkg.notes!==undefined&&!Array.isArray(pkg.notes))throw Error('笔记须为对象列表');
 for(const n of pkg.notes||[]){
  if(!n||typeof n!=='object'||Array.isArray(n)||typeof n.text!=='string'||!n.text.trim())throw Error('笔记须为非空文本');
  for(const key of ['evidenceIds','conclusionIds']){
   const refs=n[key]===undefined?[]:n[key];
   if(!Array.isArray(refs)||refs.some(x=>typeof x!=='string'||!x.trim())||new Set(refs).size!==refs.length)throw Error('笔记引用须为不重复的文本数组');
  }
  if(!(n.evidenceIds||[]).length&&!(n.conclusionIds||[]).length)throw Error('笔记须绑定证据或结论');
  if((n.evidenceIds||[]).some(id=>!entries.has(id))||(n.conclusionIds||[]).some(id=>!ids.has(id)))throw Error('笔记引用未登记证据或结论');
 }
}
function report(d){
 if(!d||typeof d!=='object'||Array.isArray(d)||typeof d.title!=='string'||!d.title.trim()||typeof d.asOf!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(d.asOf)||!Array.isArray(d.subjectCodes)||!d.subjectCodes.length)throw Error('需标题、截止日、主体代码');
 const cutoffDate=new Date(d.asOf+'T00:00:00Z');if(!Number.isFinite(cutoffDate.getTime())||cutoffDate.toISOString().slice(0,10)!==d.asOf)throw Error('截止日期无效');
 if(d.subjectCodes.some(c=>typeof c!=='string'||!/^\d{6}$/.test(c))||new Set(d.subjectCodes).size!==d.subjectCodes.length)throw Error('基金主体代码须六位且不重复');
 for(const key of ['depthResults','supplementaryResults'])if(d[key]!==undefined&&(!Array.isArray(d[key])||d[key].some(e=>!e||typeof e!=='object'||Array.isArray(e))))throw Error(key+'须为结果对象列表');
 const sections=[],missing=[],conflicts=[];let historical=null,holdings=null;
 if(d.historyInput){if(d.historyInput.asOf!==d.asOf)throw Error('历史截止日不一致');if(d.historyInput.assets.some(a=>!d.subjectCodes.includes(a.code)))throw Error('历史主体不一致');historical=fund.compare(d.historyInput);for(const code of d.subjectCodes)if(!d.historyInput.assets.some(a=>a.code===code))missing.push(code+'：历史净值未取得');sections.push({heading:'历史表现与共同区间',result:historical});}else missing.push('历史净值与比较基准');
 if(d.holdingsInput){if(d.holdingsInput.asOf!==d.asOf)throw Error('持仓截止日不一致');if(d.holdingsInput.funds.some(a=>!d.subjectCodes.includes(a.id)))throw Error('持仓主体不一致');holdings=overlap(d.holdingsInput);for(const code of d.subjectCodes)if(!d.holdingsInput.funds.some(a=>a.id===code))missing.push(code+'：持仓报告未取得');sections.push({heading:'持仓结构与重叠',result:holdings});if(new Set(holdings.funds.map(f=>f.reportDate)).size>1)conflicts.push('持仓报告期不同，不能合称同一时点持仓');}else missing.push('持仓报告与股票仓位');
 if(d.historyInput&&d.weights)sections.push({heading:'组合收益与风险贡献',result:fund.contributions({historyInput:d.historyInput,weights:d.weights})});
 const depth=d.depthResults||[];for(const e of depth){if(!d.subjectCodes.includes(e.code)||e.asOf!==d.asOf)throw Error('深度结果主体或截止日不一致');if(!['manager-public-passages','disclosed-category-change','brinson-fachler-single-period','industry-attribution-gap','fund-asset-allocation','fund-disclosed-behavior','fund-holdings-style','fund-research-conditions'].includes(e.type))throw Error('未知深度结果');sections.push({heading:e.type==='manager-public-passages'?'经理公开观点':e.type==='disclosed-category-change'?'披露分类变化':e.type==='fund-asset-allocation'?'资产配置':e.type==='fund-disclosed-behavior'?'披露持仓行为':e.type==='fund-holdings-style'?'持仓风格':e.type==='fund-research-conditions'?'研究条件检查':'行业归因',result:e});}
 const supplements=d.supplementaryResults||[];
 for(const e of supplements){
  const supported=['fund-series-quality','fund-distribution-bases','fund-multi-benchmark','fund-research-snapshot-diff','fund-evidence-package','fund-evaluation-foundation'];
  const subjects=e.subjectCodes||[e.code],cutoff=e.asOf||e.afterAsOf;
  if(!Array.isArray(subjects)||!subjects.length||subjects.some(c=>typeof c!=='string'||!/^\d{6}$/.test(c))||new Set(subjects).size!==subjects.length)throw Error('补充结果须有非空唯一基金主体代码');
  if(!supported.includes(e.type)||cutoff!==d.asOf||subjects.some(c=>!d.subjectCodes.includes(c)))throw Error('补充结果类型、主体或截止日不一致');
  if(e.type==='fund-evidence-package')checkEvidenceConclusions(e);
  const section={heading:({'fund-series-quality':'净值数据质量','fund-distribution-bases':'分红与拆分口径','fund-multi-benchmark':'多基准对标','fund-research-snapshot-diff':'研究快照变化','fund-evidence-package':'结论与证据','fund-evaluation-foundation':'产品定位、任职与持有人结构'})[e.type],result:e};
  if(e.type==='fund-evidence-package')sections.unshift(section);else sections.push(section);
 }
 for(const section of sections)for(const gap of section.result.evidenceGaps||[])missing.push(gap);
 const expected=[['manager-public-passages','经理公开观点及对应原文'],['disclosed-category-change','多期分类变化'],['brinson-fachler-single-period','行业收益及期初权重归因']];
 const required=d.requiredDepthTypes??[];
 if(!Array.isArray(required)||required.some(t=>!expected.some(([type])=>type===t))||new Set(required).size!==required.length)throw Error('requiredDepthTypes须为不重复的已支持研究类型');
 const notAssessed=[];
 for(const [type,label] of expected){
  const obtained=new Set(depth.filter(e=>e.type===type&&(type!=='manager-public-passages'||Array.isArray(e.sections)&&e.sections.length)).map(e=>e.code));
  if(d.subjectCodes.some(c=>!obtained.has(c))){
   if(required.includes(type))missing.push(label+'（本次问题需要，部分或全部对象未取得）');
   else notAssessed.push(label+'（本次未覆盖，不视为必须补齐）');
  }
 }
 notAssessed.push('合同风格约束与实际风格漂移综合评分（未据现有资料生成）');
 const supplementalSources=supplements.flatMap(e=>[e.sourceUrl,...(e.evidence||[]).map(x=>x.sourceUrl),...(e.benchmarks||[]).flatMap(b=>b.components.map(c=>c.sourceUrl)),...(e.sourceChanges?.before||[]),...(e.sourceChanges?.after||[])].filter(x=>typeof x==='string'&&/^https?:\/\//.test(x)));
 const sources=[...supplementalSources,...(d.historyInput?.assets||[]).map(a=>a.sourceUrl),...(d.historyInput?.reference?[d.historyInput.reference.sourceUrl]:[]),...(d.holdingsInput?.funds||[]).map(f=>f.sourceUrl)];
 return {type:'integrated-fund-research',title:d.title,asOf:d.asOf,subjectCodes:d.subjectCodes,subjectNames:d.subjectNames||{},sections,missing,notAssessed,conflicts,sources:[...new Set([...sources,...(d.depthResults||[]).flatMap(e=>e.sources?e.sources:e.sourceUrl?[e.sourceUrl]:e.pairs?e.pairs.flatMap(p=>p.sources):e.sectors?e.sectors.flatMap(x=>[x.sourceUrl,x.weightSourceUrl].filter(Boolean)):[])])],riskNotice:notice,limitations:['综合已有输入自动计算；不宣称任意基金完整深度研究','净值观察区间与持仓快照日期不同，不能据相关性直接认定持仓导致收益','没有交易流水，不推断真实买卖时点、择时能力或隐形交易能力'],summary:conflicts.length?'存在口径冲突，相关部分暂不合并解释':missing.length?'展示本次已取得资料；未取得部分保留缺口':'资料已汇总'};
}
function markdown(r){const lines=[`# ${r.title}`,r.riskNotice,`截止日期：${r.asOf}；对象：${r.subjectCodes.join('、')}`,r.summary];const cell=x=>String((x&&typeof x==='object'&&'value' in x?x.value:x)??'待核验').replace(/\|/g,'\\|').replace(/\r?\n/g,' ');
 for(const section of r.sections){lines.push(`\n## ${section.heading}`);const q=section.result;if(q.code)lines.push(`研究对象：${cell(q.code)}；报告日：${cell(q.reportDate??'未提供')}。`);
  if(q.comparisons){lines.push('| 标的 | 年化收益% | 最大回撤% | 夏普 |','|---|---:|---:|---:|');for(const a of q.comparisons)lines.push(`| ${cell(a.code)} | ${cell(a.metrics.CAGRPct)} | ${cell(a.metrics.maximumDrawdownPct)} | ${cell(a.metrics.Sharpe)} |`);lines.push(`共同区间：${q.alignment.start}至${q.alignment.end}，共同观察${q.alignment.observations}次；完整交易日历未核验。`);}
  if(q.pairs&&q.funds){lines.push('| 基金A | 基金B | 净资产重合% | 已披露股票结构重合% |','|---|---|---:|---:|');for(const p of q.pairs)lines.push(`| ${cell(p.a)} | ${cell(p.b)} | ${cell(p.navOverlapPct)} | ${cell(p.disclosedEquityNormalizedOverlapPct)} |`);for(const f of q.funds)lines.push(`${f.id}：报告期${f.reportDate}，股票披露覆盖${f.coveragePct}%，未知权益仓位${f.unknownEquityWeight*100}%。`);}
  if(q.type==='manager-public-passages'){lines.push('以下为管理人报告自述，尚需结合经营与持仓证据判断，不能当作已证实事实。');for(const item of q.sections||[]){lines.push(`### ${cell(item.heading)}`);for(const passage of item.passages||[])lines.push(`PDF页${cell(passage.page)}：${cell(passage.text)}`);}if(!(q.sections||[]).length)lines.push('未取得可用观点正文，不能据此评价经理判断。');}
  if(q.type==='disclosed-category-change'){for(const pair of q.pairs||[])lines.push(`${cell(pair.startReport)}至${cell(pair.endReport)}：${cell(pair.status)}；分类分布变化量${cell(pair.totalVariationPct)}%。权重变化不证明主动交易，也不直接证明价值或成长风格漂移。`);}
  if(q.type==='industry-attribution-gap')lines.push(`本次尚不能完成行业归因：${cell((q.missingInputs||q.missingIndustries||[]).join('；'))}。未取得或口径未确认的输入不按零处理。`);
  if(q.type==='brinson-fachler-single-period'){lines.push(`行业分类：${cell(q.industrySystem)}；版本：${cell(q.industryVersion)}。`);lines.push(`披露快照超额收益${cell(q.activeSnapshotReturnPp)}个百分点：行业配置${cell(q.totals?.allocationPp)}、行业内选股${cell(q.totals?.selectionPp)}、交互项${cell(q.totals?.interactionPp)}个百分点。仅解释固定披露权重，不等于真实交易归因或经理纯能力。`);if(q.informationTiming?.note)lines.push(cell(q.informationTiming.note));}
  if(q.type==='portfolio-return-risk-contributions'){lines.push('| 标的 | 收益贡献（百分点） | 波动风险占比% |','|---|---:|---:|');for(const a of q.assets)lines.push(`| ${cell(a.code)} | ${cell(a.returnContributionPp)} | ${cell(a.riskSharePct)} |`);}
  if(q.type==='fund-evaluation-foundation'){for(const x of q.profile)lines.push(`${cell(x.label)}：${cell(x.text)}。`);for(const x of q.structure)lines.push(`报告日${x.reportDate}：净资产${cell(x.netAssetsCNY)}元，机构占比${cell(x.institutionPct)}%；规模变化不能直接当申赎。`);for(const x of q.managerPeriods)lines.push(`${cell(x.name)}：${cell(x.actualStart||x.reportedStart)}至${cell(x.actualEnd||x.confirmedThrough)}，仅为产品区间表现。`);lines.push(...q.missing.map(x=>'- '+cell(x)));}
  if(q.type==='fund-series-quality')lines.push(`观测${q.observations}期；日期覆盖率：${cell(q.dateCompleteness?.dateCoveragePct)}%；核查线索${q.findings.length}项。无适用日历不打完整度分。`);
  if(q.type==='fund-distribution-bases')lines.push(`红利再投区间收益${cell(q.reinvest.totalReturnPct)}%；保留现金账户区间收益${cell(q.cashDividend.totalReturnPct)}%。`);
  if(q.type==='fund-multi-benchmark')for(const b of q.benchmarks)lines.push(`基准${cell(b.name)}：累计超额${cell(b.excessTotalReturnPp)}百分点；年化跟踪误差${cell(b.annualTrackingErrorPct)}%；合同状态${cell(b.contractBenchmarkStatus)}。`);
  if(q.type==='fund-research-snapshot-diff')for(const x of q.metrics)lines.push(`${cell(x.metric)}：${cell(x.before)} → ${cell(x.after)}；${cell(x.status)}。`);
  if(q.type==='fund-evidence-package')for(const c of q.conclusions)lines.push(`${({'disclosed-fact':'披露记录','calculated':'计算结果','estimate':'研究估算','withheld':'暂不判断'})[c.grade]}：${cell(c.text)}；证据：${c.evidenceIds.map(cell).join('、')}；局限：${c.limitations.map(cell).join('；')}。`);
  if(q.type==='fund-evidence-package'&&(q.notes||[]).length){lines.push('### 用户研究笔记');for(const n of q.notes)lines.push(`${cell(n.text)}（用户笔记；关联证据：${(n.evidenceIds||[]).map(cell).join('、')||'未绑定'}；关联结论：${(n.conclusionIds||[]).map(cell).join('、')||'未绑定'}）。用户笔记不作为已核实事实。`);}
  for(const lim of q.limitations||[])lines.push('- '+cell(lim));
 }
 lines.push('\n## 本次未评价的维度',...(r.notAssessed||[]).map(x=>'- '+x),'\n## 资料缺口',...r.missing.map(x=>'- '+x),'\n## 冲突',...(r.conflicts.length?r.conflicts:['未发现已检查的主体、截止日和报告期冲突；不代表全部数据已核验']).map(x=>'- '+x),'\n## 来源',...r.sources.map(x=>'- '+x),'\n## 分析边界',...r.limitations.map(x=>'- '+x));return lines.join('\n');}
function publishResult(output,result,text,linkFile=fs.linkSync){
 const path=require('path'),target=path.resolve(output),parent=path.dirname(target);
 const serialized=JSON.stringify(result,(key,value)=>{if(typeof value==='number'&&!Number.isFinite(value))throw Error('结果包含非有限数值');return value;},2);
 const payloads=text==null?[{target,body:serialized}]:[{target:target+'.md',body:text},{target,body:serialized}];
 if(payloads.some(x=>fs.existsSync(x.target)))throw Error('输出已存在');
 const stage=fs.mkdtempSync(path.join(parent,'.report-')),created=[],published=[],cleanupIssues=[];let primaryError=null;
 try{
  for(let i=0;i<payloads.length;i++){
   const row=payloads[i];row.stage=path.join(stage,'part-'+i);row.raw=Buffer.from(row.body,'utf8');
   const fd=fs.openSync(row.stage,'wx');created.push(row.stage);
   try{fs.writeFileSync(fd,row.raw);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  }
  for(const row of payloads){linkFile(row.stage,row.target);published.push(row);}
 }catch(error){
  primaryError=error;
  for(const row of published.reverse()){
   try{
    const actual=fs.lstatSync(row.target,{bigint:true}),owned=fs.lstatSync(row.stage,{bigint:true});
    if(!actual.isSymbolicLink()&&actual.dev===owned.dev&&actual.ino===owned.ino&&fs.readFileSync(row.target).equals(row.raw))fs.unlinkSync(row.target);
   }catch(cleanupError){if(cleanupError.code!=='ENOENT')error.cleanupIssue=cleanupError.message;}
  }
  throw error;
 }finally{
  for(const file of created){try{fs.unlinkSync(file);}catch(error){if(error.code!=='ENOENT')cleanupIssues.push({path:file,message:error.message});}}
  try{fs.rmdirSync(stage);}catch(error){if(error.code!=='ENOENT')cleanupIssues.push({path:stage,message:error.message});}
  if(primaryError&&cleanupIssues.length)primaryError.cleanupIssues=cleanupIssues;
 }
 return {publishedPaths:payloads.map(row=>row.target),cleanupIssues};
}
module.exports={overlap,similar,report,markdown,publishResult};
if(require.main===module){const [cmd,input,out]=process.argv.slice(2);if(!['overlap','similar','report'].includes(cmd)||!input||!out)throw Error('node scripts/fund_diagnostics.js overlap|similar|report INPUT.json NEW.json');if(fs.existsSync(out)||(cmd==='report'&&fs.existsSync(out+'.md')))throw Error('输出已存在');const d=require('./strict_json.js').parse(fs.readFileSync(input,'utf8')),r=module.exports[cmd](d),text=cmd==='report'?markdown(r):null,saved=publishResult(out,r,text);if(saved.cleanupIssues.length)process.stderr.write('报告已保存，但临时文件清理未完成：'+JSON.stringify(saved.cleanupIssues)+'\n');}

