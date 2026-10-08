"""Human-readable comparison built from the existing common-date calculation."""
import argparse,json,tempfile,os,hashlib
from pathlib import Path
from research_pipeline import compare,read
from research_brief_html import render

def method_files():
 return [Path(__file__).with_name(name) for name in ['fund_comparison_brief.py','research_pipeline.py','research_brief_html.py','collection_validation.py','observation_calendar.py']]

def explain(document,result):
 rows=result['rows'];names={r['code']:str(r.get('name') or r['code']).replace('\n',' ') for r in document['rows']}
 facts=[]
 if len(rows)==2:
  first,second=rows;return_gap=first['totalReturnPct']-second['totalReturnPct'];drawdown_gap=abs(first['drawdownPct'])-abs(second['drawdownPct'])
  if return_gap>0 and drawdown_gap>0:judgment='前者历史收益更高，但回撤也更深，收益优势伴随更大的下跌体验。'
  elif return_gap>0 and drawdown_gap<0:judgment='前者在本区间收益与最大回撤两项指标上占优；这还不能证明经理能力或未来优势。'
  elif return_gap<0 and drawdown_gap<0:judgment='前者历史收益较低，但回撤较小，体现的是收益与下跌风险的取舍。'
  elif return_gap<0 and drawdown_gap>0:judgment='后者在本区间收益与最大回撤两项指标上占优；仍需核查基准、风格和持仓后解释原因。'
  else:judgment='收益或回撤指标接近，不能据这两项指标直接判断产品优劣。'
  judgment=judgment.replace('前者',names[first['code']]).replace('后者',names[second['code']])
  label='高于' if return_gap>0 else '低于' if return_gap<0 else '相同于'
  risk='大于' if drawdown_gap>0 else '小于' if drawdown_gap<0 else '等于'
  text=f"在{result['start']}至{result['end']}的共同区间，{names[first['code']]}累计收益为{first['totalReturnPct']:.2f}%，{names[second['code']]}为{second['totalReturnPct']:.2f}%；前者{label}后者{abs(return_gap):.2f}个百分点。前者历史最大回撤幅度{risk}后者{abs(drawdown_gap):.2f}个百分点。"
  facts.append(dict(type='calculated-history',conclusion=judgment,text=text,codes=[first['code'],second['code']],returnDifferencePctPoints=return_gap,drawdownMagnitudeDifferencePctPoints=drawdown_gap,metricRefs=['totalReturnPct','drawdownPct'],scope='共同日期历史，不代表风险调整后的能力或未来表现'))
 else:
  returns=[r['totalReturnPct'] for r in rows];drawdowns=[abs(r['drawdownPct']) for r in rows]
  best_return=max(returns);smallest_dd=min(drawdowns)
  leaders=[r['code'] for r in rows if r['totalReturnPct']==best_return];defensive=[r['code'] for r in rows if abs(r['drawdownPct'])==smallest_dd]
  if len(leaders)==len(defensive)==1 and leaders==defensive:
   judgment=names[leaders[0]]+'在本区间累计收益与最大回撤两项指标上同时占优，但不能据此认定全维度优胜或未来优势。'
  elif len(leaders)==len(defensive)==1:
   judgment=names[leaders[0]]+'的区间收益最高，'+names[defensive[0]]+'的历史回撤最小；两项优势分属不同产品，评价须明确收益与下跌风险的取舍。'
  else:judgment='收益领先或回撤最小的位置存在并列，本次不能选出唯一的两指标优胜者；仍需结合基准、风格与费用。'
  facts.append(dict(type='calculated-history',conclusion=judgment,returnLeaderCodes=leaders,smallestDrawdownCodes=defensive,text=f"本次{len(rows)}个标的共同区间收益介于{min(returns):.2f}%与{max(returns):.2f}%之间，最大回撤幅度介于{min(drawdowns):.2f}%与{max(drawdowns):.2f}%之间。",codes=[r['code'] for r in rows],metricRefs=['totalReturnPct','drawdownPct'],scope='仅输入研究池，不是全市场同类排名'))
 if any(r['annualizedVolPct'] is None for r in rows):
  facts.append(dict(type='calculation-limit',text='至少一个标的没有可比较的年化波动率，本次不能仅凭累计收益和最大回撤判断单位风险收益是否更高。',codes=[r['code'] for r in rows if r['annualizedVolPct'] is None],metricRefs=['annualizedVolPct']))
 else:
  facts.append(dict(type='interpretation-limit',text='收益、回撤与波动描述的是本段历史的不同侧面；更高累计收益不直接证明基金经理能力更强。',codes=[r['code'] for r in rows],metricRefs=['totalReturnPct','drawdownPct','annualizedVolPct']))
 return facts

def report(document):
 result=compare(document)
 result['findings']=explain(document,result)
 result['researchLevel']='historical-comparison'
 result['gapImpacts']=[
  {'missingData':'合同基准与同类身份核验','impact':'只能比较输入池的历史表现，不能区分市场暴露与经理能力，也不能当同类排名。','nextStep':'取得同期间合同基准、比较组定义与相应收益序列。'},
  {'missingData':'同报告期持仓、经理任期及有效费率','impact':'不能解释收益差异来源，不能完成产品替换或全维度评价。','nextStep':'按研究区间补持仓原文、任期变更与费率公告，再分别核验。'}]

 names={row['code']:str(row.get('name') or '名称未确认').replace('|','\\|').replace('\n',' ') for row in document['rows']}
 lines=['# 基金同区间表现比较','']
 if document.get('exampleType')=='teaching-only-not-real-funds':
  lines+=['**教学演示：以下净值为虚构样本，不是真实基金、实时数据或投资评价。**','']
 for finding in result['findings']:
  if finding.get('conclusion'):lines+=['> '+finding['conclusion'],'','论据（共同区间计算）：'+finding['text']]
  else:lines.append(finding['text'])
 lines+=['',f"实际共同区间：{result['start']}至{result['end']}。请求起点：{result.get('requestedStart') or '未指定'}。",'','|基金代码|累计收益|最大回撤|年化波动|共同收益观察数|','|---|---:|---:|---:|---:|']
 for row in result['rows']:
  vol=f"{row['annualizedVolPct']:.2f}%" if row['annualizedVolPct'] is not None else '未计算'
  lines.append(f"|{names[row['code']]}（{row['code']}）|{row['totalReturnPct']:.2f}%|{row['drawdownPct']:.2f}%|{vol}|{row['observationCount']}|")
 lines+=['','## 如何理解结果','累计收益反映共同区间内的变化；最大回撤只包括对齐后的观测，不代表完整持有路径。年化波动按252个交易日假设计算，资料频率或共同日期不满足条件时留空。','','## 口径与资料缺口',result['basis'],'比较组由输入声明，未独立核验为同类；本报告不提供同类排名。']
 for row in document['rows']:
  basis=row['basis'];lines.append('- '+row['code']+'：'+('单位净值加已取得现金分红，按红利再投处理。分红记录完整性未独立核验。' if basis=='nav-with-distributions' else '输入口径为'+str(basis)+'，需单独核验复权与事件记录。'))
  if row.get('source'):lines.append('  资料来源：'+str(row['source']))
 for row in result['rows']:
  if row.get('volatilityUnavailableReason'):lines.append('- '+row['code']+'年化波动未计算：'+row['volatilityUnavailableReason'])
 for alignment in result['alignment']:
  if alignment.get('inputWasReordered'):lines.append('- '+alignment['code']+'输入观测未按日期排列，计算前已按日期排序；保留原输入快照，排序不证明数据正确。')
  from observation_calendar import note
  lines.append('- '+alignment['code']+'：共同区间内原序列有'+str(alignment['observationsWithinCommonWindow'])+'条观测，参与比较'+str(alignment['commonObservations'])+'条，因日期对齐排除'+str(alignment['excludedObservations'])+'条。'+note(alignment['calendarCheck']))
 for row in document['rows']:
  if row.get('retrievedAt'):lines.append('- '+row['code']+'资料获取时间：'+str(row['retrievedAt'])+'。获取时间不等于净值所属日。')
 lines+=['币种声明不等于币种原文核验；未取得合同基准、持仓、规模、费率及经理任职资料时，不能输出完整基金评价。']
 for gap in result['gapImpacts']:lines+=['','**缺口影响**：'+gap['missingData']+'。'+gap['impact']+' 下一步：'+gap['nextStep']]
 lines+=['','## 哪些资料最能解释差异','若要进一步解释收益差异，先取得相同期间的合同基准和持仓报告：基准用于判断市场暴露，持仓用于核查行业与个股集中度。随后再结合经理任期、有效费率和分红记录。没有这些依据，本报告只确认共同区间表现差异，不给出选股能力或替换结论。']
 return result,'\n'.join(lines)

def publish(document,out):
 out=Path(out)
 if out.exists():raise FileExistsError('输出目录已存在，请另存快照')
 result,text=report(document);out.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='.comparison-',dir=out.parent) as directory:
  stage=Path(directory)
  (stage/'input.json').write_text(json.dumps(document,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
  (stage/'比较结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
  (stage/'基金比较说明.md').write_text(text,'utf-8');(stage/'基金比较说明.html').write_text(render(text,'基金同区间表现比较'),'utf-8')
  methods=method_files()
  manifest={'schemaVersion':1,'artifactType':'fund-comparison','inputSha256':hashlib.sha256((stage/'input.json').read_bytes()).hexdigest(),'methodSha256':hashlib.sha256(b''.join(p.read_bytes() for p in methods)).hexdigest(),'methodFiles':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in methods},'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()},'sourceVerification':'not-verified','visualReview':'not-performed'}
  (stage/'report-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
  if out.exists():raise FileExistsError('输出目录已存在，请另存快照')
  os.rename(stage,out)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out-dir',required=True);a=p.parse_args();publish(read(a.input),a.out_dir)
