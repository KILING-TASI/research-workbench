'use strict';
const assert=require('assert'),fs=require('fs'),path=require('path'),os=require('os'),{spawnSync}=require('child_process');
const folder=fs.mkdtempSync(path.join(os.tmpdir(),'research-cli-')),input=path.join(folder,'input.json'),out=path.join(folder,'result.json'),cli=path.join(__dirname,'research_analytics_cli.js');
try{
 for(const cli of [path.join(__dirname,'research_analytics_cli.js'),path.join(__dirname,'../modules/etf-sector-rotation/scripts/research_analytics_cli.js')]){
 for(const text of ['{"amount":1,"amount":2}','{"amount":1e999}']){
  fs.writeFileSync(input,text);const result=spawnSync(process.execPath,[cli,'financial',input,out],{encoding:'utf8'});
  assert.notEqual(result.status,0);assert.ok(/Duplicate JSON property|Non-finite JSON number/.test(result.stderr));assert.ok(!fs.existsSync(out));
 }
 const financial={period:'2025年度',periodEnd:'2025-12-31',publishedAt:'2026-03-31',asOf:'2026-10-08',currency:'CNY',unit:'元',statementScope:'consolidated',periodBasis:'annual',current:{assets:100,liabilities:40,equity:60}};
 for(const sourceUrl of ['https://user:secret@example.org/report','https://example.org/ report','https://example.org/\nreport','file:///report',null]){
  fs.writeFileSync(input,JSON.stringify({...financial,sourceUrl}));
  const result=spawnSync(process.execPath,[cli,'financial',input,out],{encoding:'utf8'});
  assert.notEqual(result.status,0);assert.ok(!fs.existsSync(out));
 }
 fs.writeFileSync(input,JSON.stringify({...financial,sourceUrl:'https://example.org/report'}));
 const valid=spawnSync(process.execPath,[cli,'financial',input,out],{encoding:'utf8'});
 assert.equal(valid.status,0,valid.stderr);assert.equal(JSON.parse(fs.readFileSync(out,'utf8')).type,'financial');
 fs.unlinkSync(out);
 }
}finally{
 for(const file of [input,out])if(fs.existsSync(file))fs.unlinkSync(file);
 fs.rmdirSync(folder);
}
console.log('Analytics CLI rejects duplicate and overflowing inputs before output.');
