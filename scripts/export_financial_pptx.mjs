import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
export function wrap(text,max=88){
 const lines=[];let line='',units=0;
 for(const c of text.match(/PDF第\d+页|[+-]?[A-Za-z0-9][A-Za-z0-9.,%/_-]*|./gu)??[]){const n=[...c].reduce((sum,x)=>sum+(x.charCodeAt(0)>255?2:1),0);const closing=/^[，。；：！？）】、]/u.test(c);if(units+n>max&&line&&!closing){lines.push(line);line='';units=0;}line+=c;units+=n;}
 if(line)lines.push(line);return lines;
}
export function plan(markdown){
 if(typeof markdown!=='string')throw Error('报告正文须为文字');
 const slides=[];let title='公司与行业财报点评',heading=title,current=null;
 const start=()=>{current={title:heading,paragraphs:[],citations:[]};slides.push(current);};
 for(const raw of markdown.split(/\r?\n/)){
  const line=raw.trim();if(!line)continue;
  if(/^(?:```|~~~)/.test(line))throw Error('暂不处理Markdown代码块，不能将其静默改写为正文');
  if(line.startsWith('|'))throw Error('暂不处理 Markdown 表格，不能静默丢弃表格');
  const h=line.match(/^(#{1,3})\s+(.+)/);
  if(h){if(h[1].length===1){title=h[2];heading=title;}else heading=h[2];current=null;continue;}
  const citations=[...line.matchAll(/\[([^\]]+)\]\(([^)]+)\)/g)].map(m=>({label:m[1],target:m[2]}));
  const text=line.replace(/^[-*]\s+/,'').replace(/\[([^\]]+)\]\(([^)]+)\)/g,'$1').replaceAll('**','');
  const lines=wrap(text);
  for(let i=0;i<lines.length;i+=13){
   const part=lines.slice(i,i+13);
   const used=current?.paragraphs.reduce((n,p)=>n+p.lines.length+1,0)??0;
   if(!current||used+part.length>14)start();
   current.paragraphs.push({text:part.join('\n'),lines:part});current.citations.push(...citations);
  }
 }
 if(!slides.length)throw Error('正文没有可导出的内容');return {title,slides};
}
export async function build(spec){
 if(!spec||typeof spec!=='object'||typeof spec.markdownPath!=='string'||typeof spec.outDir!=='string')throw Error('需明确正文路径与新输出目录');
 const source=path.resolve(spec.markdownPath),out=path.resolve(spec.outDir);const raw=await fs.readFile(source);
 if(hash(raw)!==spec.markdownSha256)throw Error('报告正文哈希变化');
 if(typeof spec.fontFamily!=='string'||!spec.fontFamily.trim())throw Error('需明确fontFamily并确认目标环境字体');
 const planned=plan(raw.toString('utf8').replace(/^\uFEFF/,''));const references=new Map();
 for(const slide of planned.slides)for(const cite of slide.citations){
  if(/^https?:\/\//.test(cite.target)){const url=new URL(cite.target);if(url.username||url.password||/\s/.test(cite.target))throw Error('远程引用须为无凭据链接');continue;}
  if(/^[a-z]+:/i.test(cite.target))throw Error('不支持的引用协议');
  const relative=cite.target.split('#')[0],file=path.resolve(path.dirname(source),relative);
  const rel=path.relative(path.dirname(source),file);if(rel.startsWith('..')||path.isAbsolute(rel))throw Error('引用必须位于报告目录内');
  const realRoot=await fs.realpath(path.dirname(source)),realFile=await fs.realpath(file),realRelative=path.relative(realRoot,realFile);if(realRelative.startsWith('..')||path.isAbsolute(realRelative))throw Error('引用实际文件越出报告目录');
  references.set(relative,{file,bytes:await fs.readFile(file)});
 }
 const require=createRequire(import.meta.url);let entry;
 try{entry=require.resolve('@oai/artifact-tool',{paths:process.env.ARTIFACT_NODE_MODULES?[process.env.ARTIFACT_NODE_MODULES]:[process.cwd()]});}catch{throw Error('需可用的演示文稿组件，可通过ARTIFACT_NODE_MODULES指定目录');}
 const {Presentation,PresentationFile}=await import(pathToFileURL(entry).href);
 await fs.mkdir(out,{recursive:false});
 for(const [name,ref]of references){const dest=path.join(out,name);await fs.mkdir(path.dirname(dest),{recursive:true});await fs.writeFile(dest,ref.bytes);}
 const presentation=Presentation.create({slideSize:{width:1280,height:720}});const family=spec.fontFamily.trim();
 function box(slide,text,left,top,width,height,size,color,bold=false){const s=slide.shapes.add({geometry:'textbox',position:{left,top,width,height},fill:'none',line:{fill:'none',width:0}});s.text=text;s.text.style={typeface:family,fontSize:size,color,bold,autoFit:'none'};return s;}
 for(let i=0;i<planned.slides.length;i++){
  const p=planned.slides[i],slide=presentation.slides.add();slide.background.fill='#FFFFFF';
  box(slide,p.title,64,40,1152,70,36,'#162C42',true);let y=140;
  for(const para of p.paragraphs){const height=para.lines.length*30+10;box(slide,para.text,64,y,1152,height,22,'#24364B');y+=height+12;}
  box(slide,'公开资料研究  资料缺口及口径限制见正文',64,660,1020,26,15,'#637386');box(slide,String(i+1)+' / '+planned.slides.length,1120,660,96,26,15,'#637386');
  slide.speakerNotes.textFrame.setText(p.citations.map(c=>c.label+' '+c.target).join('\n')+'\n正文来源 SHA256 '+spec.markdownSha256+'\n本导出保留已存正文，不新增核验或投资结论。');
 }
 const candidate=path.join(out,'candidate.pptx');await(await PresentationFile.exportPptx(presentation)).save(candidate);
 for(let i=0;i<presentation.slides.items.length;i++){const slide=presentation.slides.items[i],png=await presentation.export({slide,format:'png',scale:1});await fs.writeFile(path.join(out,'slide-'+(i+1)+'.png'),new Uint8Array(await png.arrayBuffer()));}
 const result={format:'pptx',outputFile:path.basename(candidate),outputSha256:hash(await fs.readFile(candidate)),candidate,slides:planned.slides.length,markdownSha256:spec.markdownSha256,fontFamily:family,paragraphs:planned.slides.map(s=>s.paragraphs.map(p=>p.text)),references:[...references].map(([name,r])=>({path:name,sha256:hash(r.bytes)})),status:'candidate-requires-visual-and-package-validation',limitations:['仅转换已存正文，不新增核验','暂不处理Markdown表格','尚需检查可编辑文字、排版和来源，不能因保存成功称已交付']};
 await fs.writeFile(path.join(out,'export-result.json'),JSON.stringify(result,null,2));return result;
}
if(process.argv[1]&&pathToFileURL(path.resolve(process.argv[1])).href===import.meta.url){const spec=JSON.parse(await fs.readFile(process.argv[2],'utf8'));console.log(JSON.stringify(await build(spec)));}
