import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const require=createRequire(import.meta.url);
let modulePath;
try {modulePath=require.resolve('@oai/artifact-tool',{paths:process.env.ARTIFACT_NODE_MODULES?[process.env.ARTIFACT_NODE_MODULES]:[process.cwd()]});} catch {throw Error('Excel导出需要@oai/artifact-tool；Markdown导出不受影响');}
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(modulePath).href);
const [input,out]=process.argv.slice(2);if(!input||!out)throw Error('用法：node export_research_xlsx.mjs 快照结果.json 新文件.xlsx');
try {await fs.access(out);throw Error('输出已存在');}catch(e){if(e.code!=='ENOENT')throw e;}
const d=require('./strict_json.js').parse(await fs.readFile(input,'utf8'));
if(!d||typeof d!=='object'||typeof d.title!=='string'||!d.title.trim()||!Array.isArray(d.rows)||!Array.isArray(d.sources)||!Array.isArray(d.limitations)||!Array.isArray(d.userNotes)||typeof d.notice!=='string')throw Error('需research_outputs snapshot标准结果');
for(const rows of [d.rows,d.sources,d.userNotes])if(rows.some(row=>!Array.isArray(row)||row.length!==2||row.some(x=>x!==null&&typeof x!=='string'&&(typeof x!=='number'||!Number.isFinite(x)))))throw Error('研究导出须为两列文字、有限数值或空值');
if(d.limitations.some(x=>typeof x!=='string'))throw Error('研究限制须为文字数组');
const wb=Workbook.create();
const safe=x=>typeof x==='string'&&/^[=+\-@]/.test(x.trimStart())?"'"+x:x;
const specs=[['研究结果',[['项目','结果'],...d.rows]],['来源与说明',[['类别','内容'],['风险说明',d.notice],...d.sources.map(([a,b])=>[a,b]),...d.limitations.map(x=>['假设与限制',x]),...d.userNotes.map(([a,b])=>['用户笔记 '+a,b])]]];
for(const [name,rows] of specs){let s=wb.worksheets.add(name);s.showGridLines=false;s.getRange('A1').values=[[safe(d.title)]];s.getRange('A1').format.font={bold:true,size:14};for(let i=0;i<rows.length;i++)for(let j=0;j<2;j++)if(typeof rows[i][j]==='string')s.getCell(i+2,j).setNumberFormat('@');s.getRangeByIndexes(2,0,rows.length,2).values=rows.map(row=>row.map(safe));s.getRange('A3:B3').format.fill='#24364B';s.getRange('A3:B3').format.font={bold:true,color:'#FFFFFF'};let range=s.getRangeByIndexes(0,0,rows.length+2,2);range.format.wrapText=true;range.format.verticalAlignment='top';s.getRange('A:A').format.columnWidth=45;s.getRange('B:B').format.columnWidth=85;range.format.autofitRows();s.freezePanes.freezeRows(3);}
const inspected=await wb.inspect({kind:'table',range:'研究结果!A3:B8',include:'values,formulas',tableMaxRows:6,tableMaxCols:2,maxChars:1200});
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#NULL!',options:{useRegex:true,maxResults:20},maxChars:1200});
const scan=errors.ndjson.trim().split(/\r?\n/).filter(Boolean).map(line=>JSON.parse(line));
if(scan.length!==1||scan[0].kind!=='notice'||scan[0].message!=='Cell search matched 0 entries.')throw Error('Excel错误扫描未明确返回零匹配，停止导出');
if(process.env.RESEARCH_EXPORT_QA==='1'){for(const name of ['研究结果','来源与说明']){const preview=await wb.render({sheetName:name,range:'A1:B12',scale:1,format:'png'});await fs.writeFile(out+'.'+name+'.png',new Uint8Array(await preview.arrayBuffer()));}await fs.writeFile(out+'.inspect.json',JSON.stringify({table:inspected.ndjson,errors:errors.ndjson}));}
await (await SpreadsheetFile.exportXlsx(wb)).save(out);
console.log(JSON.stringify({output:out,sourceHash:d.sourceHash}));


