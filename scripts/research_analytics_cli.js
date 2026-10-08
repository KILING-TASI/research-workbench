'use strict';
const fs=require('fs'),api=require('./research_analytics.js');
const [kind,input,out]=process.argv.slice(2);
if(kind==='template'){if(!input||!out)throw Error('用法：node research_analytics_cli.js template 类型 新模板.json');fs.writeFileSync(out,JSON.stringify(api.inputTemplate(input),null,2),{encoding:'utf8',flag:'wx'});process.exit(0);}
if(!['fundProfitStudy','holdingsChange','industryStudy','benchmarkStudy','fundInvestorStudy','rollingRisk','drawdownStudy','holdingsStudy','researchAudit','historical','shock','bond','financial','correlationStudy','rebalance','bondResearch','convertibleTerms'].includes(kind)||!input||!out)throw Error('用法：node research_analytics_cli.js 类型 输入.json 新结果.json');
const raw=fs.readFileSync(input,'utf8').replace(/^\uFEFF/,'');const result=api[kind](require('./strict_json.js').parse(raw));result.inputSha256=require('crypto').createHash('sha256').update(raw).digest('hex');const serialized=JSON.stringify(result,(key,value)=>{if(typeof value==='number'&&!Number.isFinite(value))throw Error('研究结果包含非有限数值');return value;},2);fs.writeFileSync(out,serialized,{encoding:'utf8',flag:'wx'});
