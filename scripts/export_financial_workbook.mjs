import {statusText,comparabilityText} from './financial_status_labels.mjs';
import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const require=createRequire(import.meta.url);
let entry;try{entry=require.resolve('@oai/artifact-tool',{paths:process.env.ARTIFACT_NODE_MODULES?[process.env.ARTIFACT_NODE_MODULES]:[process.cwd()]});}catch{throw Error('Excel导出需要@oai/artifact-tool；其他报告不受影响');}
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(entry).href);
const [input,out]=process.argv.slice(2);if(!input||!out)throw Error('需输入JSON和新XLSX文件');
try{await fs.access(out);throw Error('输出已存在');}catch(e){if(e.code!=='ENOENT')throw e;}
const inputText=await fs.readFile(input,'utf8');const data=require('./strict_json.js').parse(inputText);
if(!data||typeof data!=='object'||!Array.isArray(data.rows)||!data.rows.length||!Array.isArray(data.companies)||!data.companies.length||!Array.isArray(data.groups)||!Array.isArray(data.sources)||!Array.isArray(data.limitations))throw Error('财务底稿需非空字段和公司及明确分组、来源、限制数组');
const identifiers=new Set();for(const row of data.rows){if(!row||typeof row!=='object'||typeof row.code!=='string'||typeof row.key!=='string'||identifiers.has(row.code+':'+row.key))throw Error('财务字段身份缺失或重复');identifiers.add(row.code+':'+row.key);for(const [key,size]of [['dates',6],['values',6],['calculate',3],['subtract',3],['expected',3]])if(!Array.isArray(row[key])||row[key].length!==size)throw Error('财务字段数组长度无效：'+key);if([...row.values,...row.expected].some(v=>v!==null&&(typeof v!=='number'||!Number.isFinite(v))))throw Error('财务数值须有限或留空');if([...row.calculate,...row.subtract].some(v=>typeof v!=='boolean'))throw Error('计算开关须为布尔值');}
async function verifyAssociatedInputs(){if(data.inputFileHashes===undefined)return;if(!data.inputFileHashes||typeof data.inputFileHashes!=='object'||Array.isArray(data.inputFileHashes))throw Error('关联输入摘要须为对象');for(const [p,hash] of Object.entries(data.inputFileHashes)){if(typeof hash!=='string'||!/^[a-f0-9]{64}$/.test(hash)||createHash('sha256').update(await fs.readFile(p)).digest('hex')!==hash)throw Error('关联输入文件已变化，须重新准备底稿');}}
await verifyAssociatedInputs();
const wb=Workbook.create();
const safe=x=>typeof x==='string'&&/^[\s]*[=+@-]/.test(x)?"'"+x:x;
const sameGroup=(metadata,group)=>['group','classificationVersion','scope','unit','currency','sectorType'].every(key=>(metadata[key]??null)===(group[key]??null));
const names=['财务概览','样本分组','季度底稿','原始字段','来源与覆盖'];const sheets=Object.fromEntries(names.map(n=>[n,wb.worksheets.add(n)]));
function setup(s,title,headers,widths){s.showGridLines=false;s.getRange('A2').values=[[title]];s.getRange('A2').format.font={size:14,bold:true};s.getRange('A3').values=[[data.period+'；累计转单季，资产负债为期末值；渠道原单位及声明范围见来源说明']];s.getRangeByIndexes(6,0,1,headers.length).values=[headers];s.getRangeByIndexes(6,0,1,headers.length).format={fill:'#24364B',font:{color:'#FFFFFF',bold:true,size:10}};for(let i=0;i<widths.length;i++)s.getRangeByIndexes(0,i,Math.max(12,data.rows.length+8),1).format.columnWidth=widths[i];s.getRange('A:A').setNumberFormat('@');s.freezePanes.freezeRows(7);}
setup(sheets['原始字段'],'财务原始字段',['代码','公司','指标','单位',...data.rows[0].dates.map((d,i)=>['本期原值 ','差分前值 ','上年同期原值 ','上年差分前值 ','上季原值 ','上季差分前值 '][i]+d)],[12,16,20,28,21,21,21,21,21,21]);
setup(sheets['季度底稿'],'季度财务计算',['代码','公司','指标','本季度/期末','上年同季/期末','上季/期末','同比','环比','计算说明'],[12,16,20,23,23,23,15,15,45]);
const index=new Map();const expected=[];
for(let i=0;i<data.rows.length;i++){
 const r=data.rows[i],row=i+8;index.set(r.code+':'+r.key,row);
 sheets['原始字段'].getRangeByIndexes(row-1,0,1,10).values=[[r.code,r.name,r.label,r.unit,...r.values].map(safe)];
 const s=sheets['季度底稿'];s.getRangeByIndexes(row-1,0,1,3).values=[[r.code,r.name,r.label].map(safe)];
 const pairs=[['E','F'],['G','H'],['I','J']];
 for(let j=0;j<3;j++){
  const [a,b]=pairs[j],refA="'原始字段'!"+a+row,refB="'原始字段'!"+b+row;
  const expr=r.calculate[j]?(r.subtract[j]?`=IF(COUNT(${refA},${refB})=2,${refA}-${refB},"")`:`=IF(ISNUMBER(${refA}),${refA},"")`):'=""';
  s.getCell(row-1,3+j).formulas=[[expr]];expected.push({cell:String.fromCharCode(68+j)+row,value:r.expected[j]});
 }
 s.getCell(row-1,6).formulas=[[`=IF(AND(ISNUMBER(D${row}),ISNUMBER(E${row}),E${row}>0),D${row}/E${row}-1,"")`]];
 s.getCell(row-1,7).formulas=[[`=IF(AND(ISNUMBER(D${row}),ISNUMBER(F${row}),F${row}>0),D${row}/F${row}-1,"")`]];
 s.getCell(row-1,8).values=[[(r.flow?'累计值相减；':'期末存量；')+(r.yoy.reason?'同比：'+r.yoy.reason+'；':'')+(r.qoq.reason?'环比：'+r.qoq.reason:'')]];
}
const n=data.rows.length+7;sheets['原始字段'].getRange(`E8:J${n}`).setNumberFormat('#,##0.00');sheets['季度底稿'].getRange(`D8:F${n}`).setNumberFormat('#,##0.00');sheets['季度底稿'].getRange(`G8:H${n}`).setNumberFormat('0.00%');
setup(sheets['财务概览'],'公司与样本财务比较',['公司','营业收入同比','归母净利润同比','净利润率','资产负债率'],[18,20,23,18,18]);
for(let i=0;i<data.companies.length;i++){
 const c=data.companies[i],r=i+8,rev=index.get(c.code+':revenue'),profit=index.get(c.code+':profit'),parent=index.get(c.code+':parentProfit'),assets=index.get(c.code+':assets'),debt=index.get(c.code+':liabilities');const s=sheets['财务概览'];s.getCell(r-1,0).values=[[safe(c.metadata.name||c.code)]];
 s.getCell(r-1,1).formulas=[[`=IF(ISNUMBER('季度底稿'!G${rev}),'季度底稿'!G${rev},"")`]];
 s.getCell(r-1,2).formulas=[[`=IF(ISNUMBER('季度底稿'!G${parent}),'季度底稿'!G${parent},"")`]];
 s.getCell(r-1,3).formulas=[[`=IF(AND(ISNUMBER('季度底稿'!D${profit}),ISNUMBER('季度底稿'!D${rev}),'季度底稿'!D${rev}>0),'季度底稿'!D${profit}/'季度底稿'!D${rev},"")`]];
 s.getCell(r-1,4).formulas=[[`=IF(AND(ISNUMBER('季度底稿'!D${debt}),ISNUMBER('季度底稿'!D${assets}),'季度底稿'!D${assets}>0),'季度底稿'!D${debt}/'季度底稿'!D${assets},"")`]];
}
sheets['财务概览'].getRange(`B8:E${data.companies.length+7}`).setNumberFormat('0.00%');
const chart=sheets['财务概览'].charts.add('bar',sheets['财务概览'].getRange(`A7:C${data.companies.length+7}`));chart.title='本季度收入与归母利润同比';chart.setPosition('G7','N22');chart.yAxis={numberFormatCode:'0.0%',numberFormatSourceLinked:false};
setup(sheets['样本分组'],'样本分组统计',['样本分组','样本家数','收入同比中位数','利润同比中位数','分类版本','收入有效家数','利润有效家数','报表范围','金额单位','币种','企业类型'],[18,13,20,20,24,14,14,17,32,12,18]);
let gr=7;const groupChecks=[];
for(const g of data.groups){gr++;const members=data.companies.map((c,i)=>({c,row:i+8})).filter(x=>sameGroup(x.c.metadata,g));const s=sheets['样本分组'];s.getRange(`A${gr}:B${gr}`).values=[[safe(g.group),g.sampleSize]];s.getCell(gr-1,4).values=[[safe(g.classificationVersion)]];for(const [col,source] of [['C','B'],['D','C']]){const refs=members.map(x=>"'财务概览'!"+source+x.row).join(',');s.getCell(gr-1,col==='C'?2:3).formulas=[[`=IF(COUNT(${refs})>0,MEDIAN(${refs}),"")`]];}s.getRange(`C${gr}:D${gr}`).setNumberFormat('0.00%');s.getRange(`F${gr}:G${gr}`).formulas=[[`=COUNT(${members.map(x=>"'财务概览'!B"+x.row).join(',')})`,`=COUNT(${members.map(x=>"'财务概览'!C"+x.row).join(',')})`]];s.getRange(`H${gr}:K${gr}`).values=[[(g.scope==='consolidated'?'合并报表':g.scope==='parent'?'母公司报表':g.scope),g.unit,g.currency,(g.sectorType==='general'?'一般企业':g.sectorType)].map(safe)];groupChecks.push({row:gr,group:g});}
setup(sheets['来源与覆盖'],'资料来源与财报覆盖',['公司/代码','项目','报告期/披露日','来源或说明','页码/核验','文件哈希'],[17,23,25,75,30,45]);
let sr=8;const sourceSheet=sheets['来源与覆盖'];
for(const c of data.coverage){const meta=c.metadata||{};sourceSheet.getRange(`A${sr}:F${sr}`).values=[[safe(c.code),'同期报告',meta.publishedAt||'',meta.url||'资料未取得',statusText(c.parseStatus)+'；数值需另核验'+(c.error?'；原因：'+c.error:''),c.fileSha256||''].map(safe)];sr++;}
for(const c of (data.originalChecks||[])){for(const x of [...c.checks,...(c.comparativeChecks||[])]){sourceSheet.getRange(`A${sr}:F${sr}`).values=[[safe(c.code),x.label+(x.column==='comparative'?'（比较列核验）':'（累计/期末核验）'),x.observationPeriod||data.period,(c.reportSource?.url||'')+(x.column==='comparative'?'；'+x.scope:''),statusText(x.status)+'；PDF页 '+x.original.map(v=>v.page).join(',')+(x.difference!==null?'；差额人民币 '+x.difference+' 元（数据源减原文）':''),c.reportHash||''].map(safe)];sr++;}}
for(const lim of data.limitations){sourceSheet.getRange(`A${sr}:F${sr}`).values=[['','口径与限制','',lim,'',''].map(safe)];sr++;}
for(const c of (data.originalChecks||[])){for(const entry of (c.interpretations||[])){for(const question of (entry.followUp||[])){const pages=[...new Set((entry.evidence||[]).map(e=>e.page))];sourceSheet.getRange(`A${sr}:F${sr}`).values=[[safe(c.code),'待核实研究问题',data.period,question,'引句定位于PDF页 '+pages.join(',')+'；问题尚未验证',c.reportHash||''].map(safe)];sr++;}}}
for(const c of (data.quarterOriginalChecks||[])){for(const f of c.fields){for(const [kind,p] of Object.entries(f.parts)){for(const d of p.dependencies){const binding=c.originalBindings.find(b=>b.period===d.period);const label={current:'本期单季/期末',yoy:'同比基数',qoq:'环比基数'}[kind];sourceSheet.getRange(`A${sr}:F${sr}`).values=[[safe(c.code),f.label+'（'+label+'输入核验）',d.period,'渠道原值 '+String(d.channelValue??'缺失')+'；'+c.scope,statusText(p.status)+'；'+statusText(d.status)+'；PDF页 '+d.pages.join(',')+(comparabilityText(p)?'；跨期提醒：'+comparabilityText(p):'')+(d.difference!==null?'；差额人民币 '+d.difference+' 元':''),binding?.sha256||''].map(safe)];sr++;}}}}
for(const src of data.sources){sourceSheet.getRange(`A${sr}:F${sr}`).values=[[safe(src.code),src.metric+' '+src.field,src.period+' / '+src.publishedAt,src.url||'',src.reason||'第三方字段',src.archiveSha256].map(safe)];sr++;}
for(const [name,s] of Object.entries(sheets)){const used=s.getUsedRange();used.format.font.name='Arial';used.format.wrapText=true;used.format.verticalAlignment='top';used.format.rowHeight=30;s.getRange('A2').format.rowHeight=24;s.getRange('A2').format.wrapText=false;s.getRange('A3').format.wrapText=false;s.getRange('A3').format.rowHeight=34;s.getRange('A3').format.font={italic:true,size:10};
 s.getRange('A4').values=[['本季同比为差分计算；跨期调整及未核验输入请查来源，不视为全部可比。']];s.getRange('A4').format.wrapText=false;s.getRange('A4').format.font={name:'Arial',size:10,color:'#8A5200'};s.getRange('A4').format.rowHeight=30;
}
// Source citations and hashes often wrap to three lines; preserve readable evidence.
sourceSheet.getRange(`A8:F${Math.max(8,sr-1)}`).format.rowHeight=64;
sourceSheet.getRange(`A8:F${Math.max(8,sr-1)}`).format.autofitRows();
sheets['样本分组'].getRange(`A8:K${Math.max(8,gr)}`).format.rowHeight=52;
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!',options:{useRegex:true,maxResults:20},maxChars:2000});
const scanLines=errors.ndjson.trim().split(/\r?\n/).filter(Boolean).map(line=>JSON.parse(line));if(scanLines.length!==1||scanLines[0].kind!=='notice'||scanLines[0].message!=='Cell search matched 0 entries.')throw Error('Excel错误扫描未明确返回零匹配，停止导出');
const calculated=sheets['季度底稿'].getRange(`D8:F${n}`).values;const differences=[];
for(let i=0;i<data.rows.length;i++)for(let j=0;j<3;j++){const got=calculated[i][j],want=data.rows[i].expected[j];if(want===null){if(got!==''&&got!==null)differences.push([i,j,got,want]);}else if(typeof got!=='number'||!Number.isFinite(got)||!Number.isFinite(want)||Math.abs(got-want)>Math.max(0.02,Math.abs(want)*1e-12))differences.push([i,j,got,want]);}
function checkFormula(label,got,want){if(want===null||want===undefined){if(got!==''&&got!==null)differences.push([label,got,want]);}else if(typeof got!=='number'||!Number.isFinite(got)||!Number.isFinite(want)||Math.abs(got-want)>Math.max(1e-12,Math.abs(want)*1e-12))differences.push([label,got,want]);}
const growthCalculated=sheets['季度底稿'].getRange(`G8:H${n}`).values;
for(let i=0;i<data.rows.length;i++){checkFormula(`growth-${i}-yoy`,growthCalculated[i][0],data.rows[i].yoy.value);checkFormula(`growth-${i}-qoq`,growthCalculated[i][1],data.rows[i].qoq.value);}
const summaryCalculated=sheets['财务概览'].getRange(`B8:E${data.companies.length+7}`).values;
for(let i=0;i<data.companies.length;i++){const c=data.companies[i];const wants=[c.metrics.revenue.yoy.value,c.metrics.parentProfit.yoy.value,c.ratios.netMargin,c.ratios.leverage];for(let j=0;j<4;j++)checkFormula(`summary-${c.code}-${j}`,summaryCalculated[i][j],wants[j]);}
for(const {row,group:g} of groupChecks){const got=sheets['样本分组'].getRange(`C${row}:G${row}`).values[0];checkFormula(`group-${row}-revenue`,got[0],g.changes.revenue.yoy.median);checkFormula(`group-${row}-profit`,got[1],g.changes.parentProfit.yoy.median);checkFormula(`group-${row}-revenue-count`,got[3],g.changes.revenue.yoy.validCount);checkFormula(`group-${row}-profit-count`,got[4],g.changes.parentProfit.yoy.validCount);}
if(differences.length)throw Error('Excel公式与Python口径不一致 '+JSON.stringify(differences));
const inspection=await wb.inspect({kind:'table',range:'财务概览!A7:E10',include:'values,formulas',tableMaxRows:4,tableMaxCols:5,maxChars:2500});
const qa={associatedInputCount:Object.keys(data.inputFileHashes||{}).length,associatedInputVerification:data.inputFileHashes?'hashes-rechecked-before-export':'not-declared',formulaDifferences:differences,quarterValueChecks:calculated.length*3,growthChecks:growthCalculated.length*2,summaryChecks:summaryCalculated.length*4,groupChecks:groupChecks.length*4,errorScan:errors.ndjson,summary:inspection.ndjson,inputSha256:createHash('sha256').update(inputText).digest('hex')};
if(process.env.RESEARCH_EXPORT_QA==='1'){for(const name of names){const range=name==='财务概览'?'A1:N23':name==='样本分组'?'A1:K12':name==='季度底稿'?'A1:I13':name==='原始字段'?'A1:J13':'A1:F14';const blob=await wb.render({sheetName:name,range,scale:1,format:'png'});await fs.writeFile(out+'.'+name+'.png',new Uint8Array(await blob.arrayBuffer()));}}
await verifyAssociatedInputs();await (await SpreadsheetFile.exportXlsx(wb)).save(out);qa.workbookSha256=createHash('sha256').update(await fs.readFile(out)).digest('hex');await fs.writeFile(out+'.qa.json',JSON.stringify(qa,null,2));console.log(JSON.stringify({output:out,rows:data.rows.length,formulaChecks:calculated.length*3+growthCalculated.length*2+summaryCalculated.length*4+groupChecks.length*4}));


