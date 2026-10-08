"""One explicit fund request; independent quote-series and report outcomes."""
import argparse,datetime as dt,json,re
from pathlib import Path
from fund_details import extract,markdown
from portable_collect import get
from fund_report_archive import run as archive
from report_manager_tenure import extract_archive as tenure_extract
from report_fee_evidence import extract_archive as fee_extract
from fund_report_industries import extract as industry_extract
from fund_investment_reconcile import extract as investment_extract,markdown as investment_markdown
from feeder_equity_exposure import build as exposure_build,markdown as exposure_markdown
from target_fund_link import extract as target_extract,attach_child,markdown as target_markdown
from research_brief_html import render as render_html
from collection_validation import day

def fee_context(details,report_fees):
 rows=[]
 clues=(details or {}).get('facts',{}).get('subscriptionClues',{})
 for key,label in [('providerOriginalRate','渠道申购原费率线索'),('providerDiscountedRate','渠道申购优惠费率线索')]:
  value=clues.get(key)
  if value is not None:
   rows.append(dict(label=label,value=value,unit='provider-raw-not-normalized',feeType='subscription-channel',sourceUrl=clues.get('sourceUrl'),retrievedAt=clues.get('retrievedAt'),effectiveVerified=False,limitations='渠道当前线索，单位、适用金额、份额及有效日期须另核验；不是管理费'))
 if report_fees:
  for label,item in report_fees.get('fees',{}).items():
   rows.append(dict(label='报告'+label,value=item.get('value'),unit=item.get('unit'),feeType='fund-recurring',sourceUrl=report_fees.get('sourceUrl'),reportDate=report_fees.get('reportDate'),publishedAt=report_fees.get('publishedAt'),effectiveVerified=item.get('currentEffectiveVerified') is True,evidence=item.get('evidence',[]),status=item.get('status'),limitations='报告期收费描述，不自动代表当前有效合同'))
 if report_fees:
  for share,item in report_fees.get('salesServiceFees',{}).items():
   rows.append(dict(label='报告'+share+'类销售服务费',shareClass=share,value=item.get('value'),unit=item.get('unit'),feeType='share-class-recurring',sourceUrl=report_fees.get('sourceUrl'),reportDate=report_fees.get('reportDate'),effectiveVerified=False,evidence=item.get('evidence',[]),status=item.get('status'),limitations='仅明确份额报告期年费率，不推广到其他份额或当前有效版本'))
 return dict(rows=rows,comparisonStatus='不同收费项目并列，不能直接判定数值冲突',limitations=['申购费按交易条件收取，管理及托管费通常在净值内计提，不能互相替代','费率线索未经单位与有效期核验时，不进入A/C成本测算','历史净值通常已扣经常性费用，不再次扣除'])

def presentation_details(details,report,tenure):
 view=dict(details);view['gaps']=list(details.get('gaps',[]))
 if report and report.get('status')=='副本身份及股票持仓勾稽完成' and report.get('holdings'):
  view['gaps']=[('渠道数据只提供代码线索；指定报告期股票明细已另行核验，见报告章节，债券及衍生品仍待核验' if x=='持仓股票/债券仅代码线索，缺报告日权重及合计核对' else x) for x in view['gaps']]
 if tenure and tenure.get('managers'):
  view['gaps']=[('指定报告期经理任职记录已另行取得；当前在管及完整历史产品关系仍需任职公告核验' if x=='经理任职起止、在管与历史产品清单需任职公告核验' else x) for x in view['gaps']]
 return view

def coverage_summary(result):
 report=result.get('report') or {}
 holdings=report.get('holdings')
 strict=report.get('status')=='副本身份及股票持仓勾稽完成'
 rows=[dict(domain='净值与渠道资料',status='已取得第三方资料' if result.get('details') else '未取得',scope='不代表官方原文或历史时点核验'),
       dict(domain='报告股票持仓',status='期末股票明细勾稽完成' if strict and holdings else '部分取得，核验未完成' if holdings else '未形成已核验股票表',scope='仅请求报告期的直接股票，不等于全部资产或当前持仓'),
       dict(domain='报告行业结构',status='金额勾稽完成' if result.get('reportIndustries') else '未形成已核验行业表',scope='行业分类规则版本和逐股映射另核验'),
       dict(domain='经理任职',status='已取得报告任职记录' if (result.get('managerTenure') or {}).get('managers') else '未取得任职记录',scope='不能据旧报告认定今天仍在管'),
       dict(domain='当前有效费率',status='尚未核验',scope='报告收费描述与渠道申购线索分别保留')]
 gaps=list(result.get('gaps',[]))
 for gap in report.get('gaps',[]):
  if gap not in gaps:gaps.append(gap)
 if result.get('feederEquityExposure'):
  rows.append(dict(domain='联接一层股票穿透',status='已核验股票路径合并完成',scope='仅股票部分；其他净资产及衍生品名义敞口未展开'))
 if result.get('fundInvestmentAccounting'):
  rows.append(dict(domain='基金投资会计核对',status=result['fundInvestmentAccounting']['status'],scope='仅基金投资金额与净资产比例，不等于全部资产穿透'))
 if result.get('targetFundLink'):
  rows.append(dict(domain='联接目标报告',status='同期间股票表已关联' if result['targetFundLink'].get('childReport') else '明确代码已取得，子报告待核验',scope='不代表父基金权重或完整穿透已核验'))
 for gap in (result.get('targetReport') or {}).get('gaps',[]):
  item='目标基金报告：'+gap
  if item not in gaps:gaps.append(item)
 return dict(rows=rows,gaps=gaps)

def run(code,period,asof,directory,fetch=get,report_runner=archive,tenure_runner=tenure_extract,fee_runner=fee_extract,target_link_runner=target_extract,target_report_runner=archive,investment_runner=investment_extract,exposure_runner=exposure_build):
 if not re.fullmatch(r'\d{6}',code):raise ValueError('六位基金代码')
 day(period);day(asof)
 if period>asof:raise ValueError('报告期晚于截止日')
 out=Path(directory)
 if out.exists():raise FileExistsError('输出目录已存在')
 out.mkdir(parents=True);r=dict(code=code,reportDate=period,asOf=asof,details=None,report=None,managerTenure=None,reportFees=None,reportIndustries=None,targetFundLink=None,targetReport=None,fundInvestmentAccounting=None,feederEquityExposure=None,gaps=[])
 try:
  raw=fetch('https://fund.eastmoney.com/pingzhongdata/'+code+'.js');details=extract(raw,code,asof,dt.datetime.now(dt.timezone.utc).isoformat());(out/'provider.js').write_text(raw,encoding='utf-8');r['details']=details
 except Exception as exc:r['gaps'].append('净值与基础资料未取得：'+type(exc).__name__+': '+str(exc))
 try:r['report']=report_runner(code,period,asof,out/'report',True)
 except Exception as exc:r['gaps'].append('报告未取得：'+type(exc).__name__+': '+str(exc))
 if r['report']:
  try:r['reportFees']=fee_runner(r['report'])
  except Exception as exc:r['gaps'].append('报告费率未提取：'+str(exc))
  try:
   r['managerTenure']=tenure_runner(r['report'])
   if not r['managerTenure']['managers']:r['gaps'].append('年报任职表未找到支持版式；不补造任职记录')
  except Exception as exc:r['gaps'].append('经理任职原文未提取：'+str(exc))
 if r['report'] and (r['report'].get('fundInvestmentDisclosure') or r['report'].get('hasCompleteFundInvestmentSection')):
  try:
   investment_report=dict(r['report']);meta=dict(investment_report['metadata']);manager=investment_report.get('managerNameEvidence') or {}
   if not meta.get('issuer') and manager.get('status')=='unique-original-manager-name':
    meta['issuer']=manager['name'];investment_report['metadata']=meta
   r['fundInvestmentAccounting']=investment_runner(investment_report)
  except Exception as exc:r['gaps'].append('基金投资会计核对未完成：'+str(exc))
 if r['report'] and r['report'].get('hasTargetFundSection'):
  try:
   link=target_link_runner(r['report']);r['targetFundLink']=link
   if link['target']['code']==code:raise ValueError('目标基金代码与父基金相同，停止关联')
   child=target_report_runner(link['target']['code'],period,asof,out/'target-report',True);r['targetReport']=child
   r['targetFundLink']=attach_child(link,child)
  except Exception as exc:r['gaps'].append('目标基金报告关联未完成：'+str(exc))
 r['feeContext']=fee_context(r['details'],r['reportFees'])
 if r['report'] and r['report'].get('status')=='副本身份及股票持仓勾稽完成' and r['report'].get('holdings'):
  try:
   report=r['report'];h=report['holdings'];metadata=dict(code=code,reportDate=period,publishedAt=report['metadata']['publishedAt'],sourceUrl=report['metadata']['sourceUrl'],netAssetsCNY=h['netAssetsCNY'],equityMarketValueCNY=h['equityMarketValueCNY'])
   industry=industry_extract(report['documentPath'],metadata)
   if industry['sourceSha256']!=report['sha256']:raise ValueError('行业表原文哈希与报告存档不一致')
   r['reportIndustries']=industry
  except Exception as exc:r['gaps'].append('行业表未核验：'+str(exc))
 if r['targetFundLink'] and r['targetFundLink'].get('childReport') and r['fundInvestmentAccounting']:
  try:r['feederEquityExposure']=exposure_runner(r)
  except Exception as exc:r['gaps'].append('一层股票穿透未完成：'+str(exc))
 r['coverageSummary']=coverage_summary(r)
 lines=['# 单基金研究档案','',f'基金{code}；资料截止日{asof}；请求报告期{period}。','']
 lines+=['## 资料取得与核验范围','| 研究内容 | 本次结果 | 适用范围 |','| --- | --- | --- |']
 for item in r['coverageSummary']['rows']:lines.append('| '+item['domain']+' | '+item['status']+' | '+item['scope']+' |')
 lines.append('')
 if r['details']:lines.append(markdown(presentation_details(r['details'],r['report'],r['managerTenure'])).replace('# ', '## ', 1))
 report=r['report']
 if report:
  lines+=['','## 定期报告依据',report['metadata']['title'],report['status'],f"送出日期{report['metadata']['publishedAt']}。",report['metadata']['sourceUrl']]
  scope=report.get('portfolioScopeEvidence',[])
  if scope:
   lines+=['','### 直接持仓与底层敞口']
   for item in scope:
    lines.append('PDF第'+str(item['page'])+'页：'+item['meaning'])
    if item['kind']=='no-direct-equity':lines.append(item['quote'])
   lines.append('基金投资与衍生品须分别核验和穿透；不能因为直接股票表为空，就把总权益敞口写成零。')
  investments=report.get('fundInvestmentDisclosure')
  if investments:
   lines+=['','### 报告披露的基金投资','仅前十名基金投资，不等于完整穿透；名称尚未关联到证券代码，比例为报告披露值。','| 子基金原文名称 | 管理人 | 披露占净资产 | PDF页码 |','| --- | --- | ---: | ---: |']
   for x in investments['rows']:lines.append('| '+x['name'].replace('|','／')+' | '+x['manager'].replace('|','／')+' | '+x['reportedWeightPct']+'% | '+str(x['page'])+' |')
   lines+=['']+['- '+x for x in investments['limitations']]
  h=report.get('holdings')
  if h:
   reconciliation=h.get('accountingReconciliation')
   if reconciliation and reconciliation.get('status')=='unresolved':
    lines += ['', '### 股票表与会计余额差异', f"股票明细及行业表合计为{float(reconciliation['portfolioEquityCNY']):,.2f}元，资产负债表股票余额为{float(reconciliation['accountingEquityCNY']):,.2f}元，两者相差{float(reconciliation['differenceCNY']):,.2f}元。", reconciliation['explanation'], '以下股票金额和比例使用行业表及股票明细口径，不代表会计余额已全部解释。']
    for ev in reconciliation.get('scopeNotes',[]):lines.append(f"PDF第{ev['page']}页：{ev['quote']}")
   lines+=[f"报告净资产{h['netAssetsCNY']:,.2f}元，股票市值{h['equityMarketValueCNY']:,.2f}元，股票占净资产{h['equityWeight']*100:.2f}%。",f"已提取{len(h['holdings'])}条股票持仓；这是报告期末快照，不是当前持仓。",'','| 股票 | 代码 | 报告权重 |','| --- | --- | ---: |']
   for x in h['holdings'][:10]:lines.append(f"| {x['name']} | {x['code']} | {x['weight']*100:.2f}% |")
  lines+=['']+['- '+g for g in report['gaps']]
 industries=r['reportIndustries']
 if industries:
  lines+=['','## 报告权益行业结构','分类口径：'+industries['taxonomy']+'；'+industries['taxonomyVersion']+'。','行业金额合计已与本次股票总额核对；这是基金权益部分汇总，不是逐股分类。','| 行业 | 占基金净资产 | 占已披露权益 |','| --- | ---: | ---: |']
  for sector in industries['sectors']:lines.append('| '+sector['name'].replace('|','／')+' | '+f"{sector['navWeight']*100:.2f}%"+' | '+f"{sector['equityWeight']*100:.2f}%"+' |')
  lines += ['',industries['note'],industries['sourceUrl']]
 fees=r['reportFees']
 if fees:
  lines+=['','## 报告费率依据','仅为报告中的收费描述，尚未核实当前有效合同。']
  for label,item in fees['fees'].items():
   lines.append(label+'：'+(str(item['value'])+'%/年' if item['value'] is not None else item['status']))
   for ev in item['evidence']:lines.append('PDF页'+str(ev['page'])+'：'+ev.get('context') or ev.get('quote') or '摘录未取得，需原页复核')
  lines += [fees['sourceUrl'],'净值收益通常已扣此类费用，不重复扣费。']
 context=r['feeContext']
 if context['rows']:
  lines+=['','## 收费项目与口径','渠道申购线索与报告管理、托管年费率分开理解；数值不同并不构成同字段冲突。','| 收费项目 | 资料值 | 单位口径 | 资料日期 |','| --- | --- | --- | --- |']
  for item in context['rows']:
   value=str(item['value']) if item['value'] is not None else '未取得或冲突'
   unit='供应商原始表示，未规范化' if item['unit']=='provider-raw-not-normalized' else '%/年' if item['unit']=='annual-pct' else '未明确'
   date=item.get('reportDate') or item.get('retrievedAt') or '获取日期未记录'
   lines.append('| '+item['label']+' | '+value.replace('|','／')+' | '+unit+' | '+date+' |')
  lines+=['']+['- '+x for x in context['limitations']]
 tenure=r['managerTenure']
 if tenure and tenure['managers']:
  lines+=['','## 报告中的经理任职依据','| 姓名 | 任职起点 | 离任日期 | 确认至 | 原文位置 |','| --- | --- | --- | --- | --- |']
  for m in tenure['managers']:
   lines.append(f"| {m['name']} | {m['start']} | {m['end'] or '未披露'} | {m['confirmedThrough']} | {m['locator']} |")
  lines += ['', '旧报告未披露离任不代表今天仍在管。证券从业年限与本基金任期分别理解。']
  for m in tenure['managers']:lines += ['',m['name']+'的报告职务原文：'+m['roleText'],m['sourceUrl']]
 if tenure and (tenure.get('assistantRecords') or tenure.get('ambiguousRoleRecords')):
  lines+=['','## 任职角色待区分记录','经理助理及角色不明确记录单列，不纳入基金经理任期评价。']
  for m in tenure.get('assistantRecords',[])+tenure.get('ambiguousRoleRecords',[]):lines += ['- '+m['name']+'：'+m['roleText']+'；'+m['locator']]
 if r['fundInvestmentAccounting']:lines+=['',investment_markdown(r['fundInvestmentAccounting']).replace('# ', '## ',1)]
 if r['targetFundLink']:lines+=['',target_markdown(r['targetFundLink']).replace('# ', '## ',1)]
 if r['feederEquityExposure']:lines+=['',exposure_markdown(r['feederEquityExposure']).replace('# ', '## ',1)]
 lines+=['','## 本次研究缺口']+['- '+g for g in r['coverageSummary']['gaps']]+['','净值指标与报告持仓日期不同，不能将报告快照用于精确还原整个历史区间收益。合同、最新费率、同类池及完整经理产品关系仍需另核验。']
 text='\n'.join(lines);html=render_html(text);serialized=json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False)
 (out/'result.json').write_text(serialized,encoding='utf-8');(out/'基金研究简报.md').write_text(text,encoding='utf-8');(out/'基金研究简报.html').write_text(html,encoding='utf-8');return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--code',required=True);p.add_argument('--period',required=True);p.add_argument('--as-of',required=True);p.add_argument('--out-dir',required=True);a=p.parse_args();run(a.code,a.period,a.as_of,a.out_dir)
