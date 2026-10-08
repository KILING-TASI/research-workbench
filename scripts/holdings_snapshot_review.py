"""Revalidate fund PDF holdings before dual-basis analysis; no account claims."""
import argparse,json,hashlib,shutil,subprocess
from pathlib import Path
from fof_reports import inspect_and_parse
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant,finite_json_float

def read_json(path):
 return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def security_label(fund,security):
 key=lambda row:(row.get('securityNamespace') or row.get('market'),row.get('code'),row.get('shareClass'))
 matches=[h for h in fund['holdings'] if key(h)==key(security)]
 if len(matches)!=1:raise ValueError('证券展示身份匹配不唯一，不能按代码猜名称')
 row=matches[0]
 markets={'SSE':'上海','SZSE':'深圳','BSE':'北京','HKEX':'香港','NASDAQ':'纳斯达克','NYSE':'纽约',
          'CN-exchange-unresolved':'境内股票，交易所待核','HK-exchange-unresolved':'香港股票，交易所待核','US-exchange-unresolved':'美国股票，交易所待核'}
 label=str(row['name'])+'（'+markets.get(row['market'],row['market'])+'，'+str(row['code'])
 if row.get('shareClass')!='ordinary':label+='，'+str(row.get('shareClass'))
 return (label+'）').replace('|','／')

def run(spec,out,node=None,base_dir=None):
 out=Path(out)
 if out.exists():raise ValueError('输出目录已存在')
 def input_reference(value):
  p=Path(value)
  return Path(base_dir)/p if base_dir is not None and not p.is_absolute() else p
 input_path=input_reference(spec['holdingsPath']);data=read_json(input_path)
 reports=spec['reportPaths']
 if not isinstance(reports,dict) or set(reports)!={f['id'] for f in data['funds']}:raise ValueError('报告映射须覆盖全部基金且无额外标的')
 bindings=[]
 for fund in data['funds']:
  archive=input_reference(reports[fund['id']]);r=read_json(archive);pdf=Path(r['documentPath'])
  if not pdf.is_absolute():pdf=archive.parent/pdf
  metadata=r.get('metadata')
  if not isinstance(metadata,dict):raise ValueError('报告记录缺元数据：须补标题、送出日期与来源链接')
  missing=[key for key in ('title','publishedAt','sourceUrl') if not isinstance(metadata.get(key),str) or not metadata[key].strip()]
  if missing:raise ValueError('报告记录缺必需资料：'+','.join(missing)+'；补齐后再核对原文，不猜测')
  if r['code']!=fund['id'] or r['reportDate']!=fund['reportDate'] or r['asOf']!=data['asOf']:raise ValueError('报告身份或截止日不同')
  sha=hashlib.sha256(pdf.read_bytes()).hexdigest()
  if sha!=r['sha256'] or sha!=fund['sourceSha256'] or r['metadata']['sourceUrl']!=fund['sourceUrl']:raise ValueError('原文哈希或来源不一致')
  parsed=inspect_and_parse(pdf,r['code'],r['reportDate'],r['metadata'])
  def rows(h):
   fields=['securityNamespace','code','name','weight','marketValueCNY','quantity','market','shareClass','locator','components']
   return sorted(json.dumps({k:x.get(k) for k in fields},ensure_ascii=False,sort_keys=True) for x in h['holdings'])
  if rows(parsed)!=rows(fund) or any(parsed.get(k)!=fund.get(k) for k in ['equityWeight','netAssetsCNY','equityMarketValueCNY','publishedAt','disclosureScope','portfolioScope']):raise ValueError('输入持仓与重新解析原文不一致')
  bindings.append(dict(code=fund['id'],archivePath=str(archive.resolve()),documentPath=str(pdf.resolve()),pdfSha256=sha,status='identity-and-equity-table-reparsed-matched'))
 runtime=node or shutil.which('node')
 if not runtime:raise ValueError('缺少Node运行时，已核验原文但尚未计算重叠')
 engine=Path(__file__).with_name('fund_diagnostics.js')
 process=subprocess.run([runtime,'-e',"const f=require(process.argv[1]);process.stdout.write(JSON.stringify(f.overlap(JSON.parse(require('fs').readFileSync(0,'utf8')))));",str(engine.resolve())],input=json.dumps(data,ensure_ascii=False),capture_output=True,text=True,encoding='utf-8',timeout=60)
 if process.returncode:raise ValueError('持仓计算失败：'+process.stderr[-1200:])
 result=json.loads(process.stdout);result['originalBindings']=bindings;result['limitations']+=['配置权重是输入假设，不是账户资产核验','行业标签和分类版本若由输入提供，不属于本次股票原文核验','已重新解析PDF副本，但官方发布网页身份仍未核验']
 lines=['# 基金持仓对照','', '按同报告期的股票披露比较，非当前持仓或全资产重叠。']
 for pair in result['pairs']:
  if pair['navOverlapPct'] is None:lines.append(pair['a']+'与'+pair['b']+'报告期不同，不直接比较。');continue
  lines.append(pair['a']+'与'+pair['b']+'：净资产口径重叠'+format(pair['navOverlapPct'],'.2f')+'%，已披露股票内部归一化重叠'+format(pair['disclosedEquityNormalizedOverlapPct'],'.2f')+'%。两者分母不同。')
 lines+=['','## 股票覆盖与未展开部分']
 for f in result['funds']:
  lines.append(f['id']+'：报告期'+f['reportDate']+'，已披露股票覆盖权益仓位'+format(f['coveragePct'],'.2f')+'%；股票占基金净资产'+format(f['equityWeight'],'.2%')+'，非股票部分'+format(f['nonEquityWeight'],'.2%')+'尚未展开，不能称为现金。')
 for pair in result['pairs']:
  if pair['navOverlapPct'] is None:continue
  lines+=['','## '+pair['a']+'与'+pair['b']+'的主要共同证券','按共同权重较小值排序，只展示前10条；完整明细保留在研究结果中。','','| 证券 | '+pair['a']+'净资产权重 | '+pair['b']+'净资产权重 | 较小权重 |','|---|---:|---:|---:|']
  displayed_fund=next(f for f in data['funds'] if f['id']==pair['a'])
  for h in sorted(pair['common'],key=lambda h:-h['overlapWeight'])[:10]:
   label=security_label(displayed_fund,h)
   lines.append('| '+label+' | '+format(h['weightA'],'.2%')+' | '+format(h['weightB'],'.2%')+' | '+format(h['overlapWeight'],'.2%')+' |')
 lines+=['','## 原文与披露范围','分享时请保留整个目录，原文入口依赖随附的PDF副本。']
 prepared=[]
 for b in bindings:
  raw=Path(b['documentPath']).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=b['pdfSha256']:raise ValueError('交付前原文发生变化')
  prepared.append(raw)
 out.mkdir(parents=True);(out/'sources').mkdir();source_files=[]
 for i,b in enumerate(bindings,1):
  raw=prepared[i-1]
  relative='sources/report-'+str(i)+'.pdf';(out/relative).write_bytes(raw)
  source_files.append(dict(code=b['code'],relativePath=relative,sha256=b['pdfSha256']))
  lines.append('['+b['code']+'报告原文]('+relative+')：已核对副本身份、股票明细及分母；不是当前持仓或官方发布网页认证。')
 result['sourceFiles']=source_files
 lines+=['','## 资料局限',*result['limitations']]
 (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');(out/'持仓对照.md').write_text('\n'.join(lines),encoding='utf-8');(out/'持仓对照.html').write_text(render('\n'.join(lines),title='基金持仓对照'),encoding='utf-8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out-dir',required=True,type=Path);p.add_argument('--node');a=p.parse_args();run(read_json(a.input),a.out_dir,a.node,base_dir=a.input.resolve().parent)
