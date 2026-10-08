"""Account-based change decomposition, not economic or causal attribution."""
from decimal import Decimal
import math
from cash_flow_reconciliation import number as monetary_decimal
EXPENSES=('salesExpense','managementExpense','researchExpense','financeExpense')
REQUIRED=('revenue','cost','profit',*EXPENSES)
OTHER_ITEMS={'taxAndSurcharges':-1,'otherIncome':1,'investmentIncome':1,'fairValueIncome':1,
             'creditImpairment':1,'assetImpairment':1,'assetDisposalIncome':1,
             'nonOperatingIncome':1,'nonOperatingExpense':-1,'incomeTaxExpense':-1}
OTHER_LABELS=dict(zip(OTHER_ITEMS,('税金及附加','其他收益','投资收益','公允价值变动收益','信用减值损失',
                                '资产减值损失','资产处置收益','营业外收入','营业外支出','所得税费用')))

def detail_residual(result,items):
 """Selected additional accounts; document verification remains separate."""
 if result.get('status')!='calculated-with-unallocated-residual':raise ValueError('须先取得毛利及四费用桥接结果')
 if not isinstance(items,list) or not items:raise ValueError('须提供选定其他损益科目')
 seen=set();rows=[];missing=[]
 for item in items:
  if not isinstance(item,dict):raise ValueError('损益科目须为对象')
  key=item.get('key')
  if key not in OTHER_ITEMS or key in seen:raise ValueError('其他损益科目未知或重复，不重复计入毛利与四费用')
  seen.add(key);values=[]
  for side in ('current','prior'):
   value=item.get(side)
   if value is None:missing.append(key+':'+side);values.append(None);continue
   amount=monetary_decimal(value)
   values.append(amount)
  if None not in values:rows.append(dict(key=key,current=item['current'],prior=item['prior'],profitImpact=str((values[0]-values[1])*OTHER_ITEMS[key])))
 original=Decimal(result.get('unallocatedResidualDecimal',str(result['rows'][-2]['amount'])));allocated=sum((Decimal(r['profitImpact']) for r in rows),Decimal(0));residual=original-allocated
 return dict(status='selected-amounts-reconciled' if not missing and seen==set(OTHER_ITEMS) and residual==0 else 'partial-residual-detail',
             rows=rows,originalResidual=str(original),selectedImpactSum=str(allocated),remainingResidual=str(residual),
             missing=missing,unprovidedKeys=sorted(set(OTHER_ITEMS)-seen),originalVerified=False,semanticCertification=False,
             scope='同单位、同期间合并科目的选定金额拆分，符号保留；不认证完整经济归因、会计合规或全表覆盖')

def bridge(company):
 if not isinstance(company,dict) or not isinstance(company.get('metadata'),dict):raise ValueError('公司利润桥接须提供明确报表元数据')
 scope=company['metadata'].get('scope')
 if scope!='consolidated':
  return {'status':'not-applicable' if scope=='parent' else 'blocked','reason':'本入口只拆解明确的合并净利润；母公司或未声明范围不能标为合并归因'}
 basis=company['metadata'].get('comparisonBasis','same-quarter')
 if basis not in ('same-quarter','same-reporting-period'):raise ValueError('利润比较期间类型未知，不能推断为单季')
 comparison_label='本期单季与去年同季' if basis=='same-quarter' else '本报告期与上年同一报告期'
 if company['metadata'].get('sectorType')=='financial':
  return {'status':'not-applicable','reason':'金融企业不套用普通企业毛利与四项费用框架'}
 metrics=company['metrics'];missing=[];values={};inputs=[]
 for key in REQUIRED:
  m=metrics.get(key,{})
  for side,entry in [('current',m.get('current',{})),('prior',m.get('comparators',{}).get('yoy',{}))]:
   v=entry.get('value')
   if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):missing.append(key+':'+side)
   else:values[key,side]=Decimal(str(v))
   inputs.extend(dict(metric=key,side=side,**ref) for ref in entry.get('inputs',[]))
 if missing:return {'status':'blocked','reason':'必要科目或同期单季输入缺失，不按零补齐','missing':missing}
 for side in ['current','prior']:
  if values['revenue',side]<=0 or values['cost',side]<0:
   return {'status':'blocked','reason':'收入须为正、成本须为费用金额口径；不自动改负号'}
 nowgross=values['revenue','current']-values['cost','current'];oldgross=values['revenue','prior']-values['cost','prior']
 gross=nowgross-oldgross
 rows=[{'label':'毛利变化','amount':float(gross)}]
 allocated=gross
 for key in EXPENSES:
  amount=values[key,'prior']-values[key,'current'];allocated+=amount
  rows.append({'label':metrics[key]['label']+'变化对利润差额的会计影响','amount':float(amount)})
 net=values['profit','current']-values['profit','prior'];residual=net-allocated
 rows.append({'label':'其他未拆分项目净影响（含税费及其他损益）','amount':float(residual)})
 rows.append({'label':'合并净利润变化','amount':float(net)})
 return {'status':'calculated-with-unallocated-residual','comparisonBasis':basis,'comparisonLabel':comparison_label,'unallocatedResidualDecimal':str(residual),'rows':rows,'grossCurrent':float(nowgross),'grossPrior':float(oldgross),'reconciliationDifference':float(net-(allocated+residual)),'inputs':inputs,'unit':company['metadata']['unit'],'currency':company['metadata']['currency'],'scope':comparison_label+'；合并净利润，不是归母净利润归因','verification':'结构化档案计算；原文已核字段与未核费用分别说明，不自动升级为全部原文核验','limitations':['毛利变化不拆成销量、价格或业务组合；收入和毛利率只是会计关系，非经济因果','其他差额未分配到具体科目，不能据此声称完整利润桥接','财务费用可为负数，不自动取绝对值；不把净利润变化拆分为经理或公司能力评分']}
def paragraphs(result,detail=None):
 if result['status'] in ['blocked','not-applicable']:return ['利润变化拆解未执行：'+result['reason']+'。']
 unit=result['unit'];scale=100000000 if unit=='元' else 1;display='亿元' if unit=='元' else unit
 lines=['### 利润变化的会计拆解',result.get('comparisonLabel','本期单季与去年同季')+'比较，采用合并净利润。费用科目尚未逐项原文核验，下面只说明已绑定结构化档案中的会计变化。','']
 net=result['rows'][-1]['amount'];gross=result['rows'][0]['amount'];fees=sum(row['amount'] for row in result['rows'][1:5]);other=result['rows'][5]['amount']
 lines.append('> 合并净利润'+('增加' if net>=0 else '减少')+format(abs(net)/scale,'.2f')+display+'；毛利变化贡献'+format(gross/scale,'+.2f')+display+'，四项费用合计影响'+format(fees/scale,'+.2f')+display+'，其余'+format(other/scale,'+.2f')+display+('的选定明细见下文。' if detail else '尚未逐项解释。'))
 lines.append('')
 for row in result['rows']:lines.append('- '+row['label']+'：'+format(row['amount']/scale,'+.2f')+display+'。')
 if detail:
  lines+=['','所选其他损益的会计影响合计'+format(Decimal(detail['selectedImpactSum'])/Decimal(scale),'+.2f')+display+'，剩余未分配金额'+format(Decimal(detail['remainingResidual'])/Decimal(scale),'+.2f')+display+'。金额勾稽不证明经营原因或原文已核。']
  if detail['missing'] or detail['unprovidedKeys']:lines.append('部分其他损益科目缺资料，保留剩余金额，不按零补齐。')
  gaps=[OTHER_LABELS[key]+'（未提供）' for key in detail['unprovidedKeys']]
  for entry in detail['missing']:
   key,side=entry.split(':',1)
   label=('本期单季' if side=='current' else '去年同季') if result.get('comparisonBasis','same-quarter')=='same-quarter' else ('本报告期' if side=='current' else '上年同一报告期')
   gaps.append(OTHER_LABELS[key]+'（'+label+'缺金额）')
  if gaps:lines.append('待补资料：'+'、'.join(gaps)+'。这些缺项阻断其他损益金额的完整分配，不据此推断该科目为零或未披露。')
  lines.append('其他损益输入及逐项符号保留在底稿；不将减值直接认定为核销，不将公允价值收益直接当现金。')
 else:lines+=['','毛利增加与四项费用变化仅解释部分利润差额；其他项目单列，仍需补充税费、减值和其他损益。']
 lines.append('该拆解不能证明增长来自销量、提价或竞争优势。')
 return lines
