"""Human-readable historical risk evidence; no trading recommendations."""
import argparse,json,hashlib
from pathlib import Path
from portfolio_stress import analyze
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant

def markdown(result,document):
 if any('name' in x and (not isinstance(x['name'],str) or not x['name'].strip()) for x in document['holdings']):raise ValueError('资产名称须为非空文字')
 h=result['historical'];codes=list(result['weights']);names={x['code']:x.get('name',x['code']) for x in document['holdings']};rolling=h['rolling'];tail=h['tail']
 names={code:name.replace('|','／').replace('\n',' ').replace('\r',' ') for code,name in names.items()}
 lines=['# 组合历史风险观察','', '> 同一组资产的相关性会随历史窗口变化，整段平均值不能替代分阶段检查。' if rolling else '> 本次仅计算指定历史窗口，尚未执行滚动观察。','', '本次按输入市值设定研究权重，组合路径方式在下文单列；不还原实际交易、申赎或持有收益。', '共同观察区间：'+str(h['intervalStart'])+'至'+str(h['intervalEnd'])+'，有效收益观察数'+str(h['observations'])+'。','']
 if rolling:
  if len(codes)==2:
   a,b=codes;valid=[r['correlations'][a][b] for r in rolling if r['correlations'][a][b] is not None]
   if valid:lines[2]='> '+names[a]+'与'+names[b]+'在滚动窗口中的相关性为'+format(min(valid),'.3f')+'至'+format(max(valid),'.3f')+'；本段历史的分散关系并非固定不变。'
  lines+=['## 分散关系是否稳定','|资产对|整段相关性|滚动最低|滚动最高|最后窗口|','|---|---:|---:|---:|---:|']
  for i,a in enumerate(codes):
   for b in codes[i+1:]:
    v=[r['correlations'][a][b] for r in rolling if r['correlations'][a][b] is not None]
    full=h['correlations'][a][b] if h['correlations'] else None;latest=rolling[-1]['correlations'][a][b]
    f=lambda x:format(x,'.3f') if x is not None else '未计算'
    lines.append('|'+names[a]+' / '+names[b]+'|'+f(full)+'|'+f(min(v) if v else None)+'|'+f(max(v) if v else None)+'|'+f(latest)+'|')
  lines+=['','滚动结果用于观察已发生的分散关系变化；最低和最高值是同一历史样本的描述，不是择时依据。零方差无法定义相关性，保留未计算。窗口跨越不同长短观察区间时，不称连续日频。','滚动窗口数：'+str(len(rolling))+'；最后窗口：'+rolling[-1]['start']+'至'+rolling[-1]['end']+'。协方差按观察区间计算，未年化。']
 elif h['rollingRequested']:lines.append('已请求滚动观察，但现有收益观察数不足以形成一个完整窗口。')
 lines+=['','## 历史较差区间说明']
 if tail['worstTailMeanReturnPct'] is None:lines.append('尾部样本不足，未输出尾部平均收益。现有收益观察'+str(tail['observations'])+'项，划入尾部'+str(tail['tailObservations'])+'项，至少需要'+str(tail['minimumTailObservations'])+'项尾部观测。')
 else:lines.append('按输入分位划定的'+str(tail['tailObservations'])+'个最差观察区间，组合平均收益为'+format(tail['worstTailMeanReturnPct'],'.2f')+'%。这是按固定输入权重形成的区间收益，不等同买入持有路径的尾部表现；不代表未来损失概率、最大回撤或可保证的损失上限。')
 path=h.get('portfolioPath',{'status':'not-requested'})
 if path['status']=='calculated-observed-path':
  lines[2]='> 本段组合历史收益为'+format(path['totalReturnPct'],'.2f')+'%，观察最大回撤为'+format(abs(path['maximumDrawdownPct']),'.2f')+'%；分散效果需要看组合共同路径，不能平均单只资产的最大回撤。'
  lines+=['','## 组合收益与回撤','本次路径采用：'+path['basis']+'。累计收益'+format(path['totalReturnPct'],'.2f')+'%，观察最大回撤幅度'+format(abs(path['maximumDrawdownPct']),'.2f')+'%。']
  if path['peakDate']:lines.append('最大回撤对应的高点日：'+path['peakDate']+'；低点日：'+path['troughDate']+'。')
  lines+=['这描述已发生的路径，不代表未来最大亏损，也不等同用户持有收益。相关性低或股票重叠低，本身不能证明组合风险低。']
 elif path['status']!='not-requested':lines+=['','## 组合收益与回撤','未计算：'+('共同收益区间存在断点，不能把遗漏时段拼接为完整路径。' if path['status']=='disconnected-observations' else '有效历史不足。')]
 lines+=['','## 口径与缺口',h['frequencyBasis'],'当前权重用于相关性及尾部观察；组合路径按上述指定方式计算。不含费用、真实动态交易和无法成交情形。','来源、复权与分红完整性来自输入声明，尚未独立确认完整交易日和现金分红；未补齐缺失价格。']
 for row in document['holdings']:lines.append('- '+names[row['code']]+'：'+row.get('sourceUrl','未提供历史来源'))
 lines+=['','## 预先指定窗口']
 for row in h['windows']:lines.append('- '+row['name']+'（'+row['start']+'至'+row['end']+'）：'+str(row['observations'])+'项观察，'+row['status']+'。尾部状态：'+('样本不足' if row['tail']['worstTailMeanReturnPct'] is None else '历史尾部已计算')+'。')
 if not h['windows']:lines.append('未指定危机窗口；本报告不声称完成危机复盘。')
 return '\n'.join(lines)
def publish(document,out):
 out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在')
 result=analyze(document);result['methodHashes']={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ['portfolio_stress.py','portfolio_history_report.py','collection_validation.py','research_brief_html.py']};body=markdown(result,document);markup=render(body,title='组合历史风险观察');raw=json.dumps(document,ensure_ascii=False,sort_keys=True,allow_nan=False);result['inputSha256']=hashlib.sha256(raw.encode()).hexdigest();out.mkdir(parents=True)
 (out/'input.json').write_text(raw,encoding='utf-8');(out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');(out/'组合历史风险观察.md').write_text(body,encoding='utf-8');(out/'组合历史风险观察.html').write_text(markup,encoding='utf-8');return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out-dir',required=True);a=p.parse_args();publish(json.loads(Path(a.input).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.out_dir)
