"""Recalculate disclosed single-child scenarios; never infer whole-portfolio stress."""
import argparse,datetime,hashlib,json,re
from decimal import Decimal,InvalidOperation
from pathlib import Path
from collection_validation import day,unique_pairs,reject_constant

def numeric(value):
 if isinstance(value,bool):raise ValueError('数值不能为布尔值')
 try:n=Decimal(str(value))
 except InvalidOperation:raise ValueError('数值非法')
 if not n.is_finite():raise ValueError('数值须有限')
 return n

def parent_weight_evidence(evidence,period,weight,base):
 if evidence is None:return dict(status='input-declared-not-original-verified')
 if not isinstance(evidence,dict) or evidence.get('reportDate')!=period:raise ValueError('父权重证据须为同日报告对象')
 holding=numeric(evidence.get('holdingAmountCNY'));nav=numeric(evidence.get('parentNetAssetsCNY'))
 if holding<0 or nav<=0 or holding>nav:raise ValueError('父持仓金额或净资产无效')
 if abs(holding/nav-weight)>Decimal('1e-26'):raise ValueError('父权重与金额复算不一致')
 path=Path(base)/evidence['path'];raw=path.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=evidence.get('sha256'):raise ValueError('父权重原件哈希不一致')
 from pypdf import PdfReader
 doc=PdfReader(path);locators=evidence.get('locators');matched=set()
 if not isinstance(locators,list) or any(not isinstance(x,dict) for x in locators):raise ValueError('父权重原页证据须为对象数组')
 for loc in locators:
  page=loc.get('page');quote=loc.get('quote');field=loc.get('field')
  if type(page)!=int or not 1<=page<=len(doc.pages) or not isinstance(quote,str) or not quote.strip() or field not in ('holdingAmountCNY','parentNetAssetsCNY'):raise ValueError('父权重页码、引句或字段无效')
  compact=lambda s:re.sub(r'\s+','',s)
  if compact(quote) not in compact(doc.pages[page-1].extract_text() or ''):raise ValueError('父权重引句无法定位')
  values=[numeric(x.replace(',','')) for x in re.findall(r'(?<![\d.,])-?\d[\d,]*\.\d+(?![\d.])',compact(quote))]
  if (holding if field=='holdingAmountCNY' else nav) not in values:raise ValueError('父权重金额不在对应引句')
  matched.add(field)
 if matched!={'holdingAmountCNY','parentNetAssetsCNY'}:raise ValueError('父权重金额定位不完整')
 return dict(status='selected-amounts-located-weight-recomputed',reportDate=period,path=str(path.resolve()),sha256=evidence['sha256'],locators=locators,formula='holdingAmountCNY/parentNetAssetsCNY',scope='选定金额同日比值；报告身份与币种单位适用范围仍需独立核验')

def calculate(spec,base=Path('.')):
 if not isinstance(spec,dict) or not isinstance(spec.get('source'),dict):raise ValueError('情景及来源须为对象')
 if not isinstance(spec.get('scenarios'),list) or not spec['scenarios'] or any(not isinstance(s,dict) for s in spec['scenarios']):raise ValueError('需情景对象数组')
 locators=spec['source'].get('locators')
 if not isinstance(locators,list) or any(not isinstance(loc,dict) for loc in locators):raise ValueError('情景原页定位须为对象数组')
 period=day(spec.get('reportDate'));published=day(spec.get('publishedAt'))
 if published<period:raise ValueError('披露日期早于报告期')
 if spec.get('currency')!='CNY':raise ValueError('当前入口须统一人民币金额')
 nav=numeric(spec['childNetAssetsCNY']);weight=numeric(spec['parentWeight'])
 if nav<=0 or not 0<=weight<=1:raise ValueError('净资产或父权重非法')
 parent_binding=parent_weight_evidence(spec.get('parentWeightEvidence'),spec['reportDate'],weight,base)
 evidence=spec['source'];p=Path(base)/evidence['path'];raw=p.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=evidence['sha256']:raise ValueError('原件哈希不一致')
 from pypdf import PdfReader
 doc=PdfReader(p);bindings=[];matched_fields=set();shock_bindings={}
 for loc in evidence['locators']:
  page=loc['page'];quote=loc['quote']
  if isinstance(page,bool) or not isinstance(page,int) or not 1<=page<=len(doc.pages) or not isinstance(quote,str) or not quote.strip():raise ValueError('原页定位非法')
  compact=lambda s:re.sub(r'\s+','',s)
  if compact(quote) not in compact(doc.pages[page-1].extract_text() or ''):raise ValueError('引句不在原页')
  field=loc.get('field')
  if field is not None:
   if not isinstance(field,str):raise ValueError('金额定位字段须为文字')
   if field=='childNetAssetsCNY':expected=nav
   elif re.fullmatch(r'scenarios/\d+/navImpactCNY',field):
    index=int(field.split('/')[1])
    if index>=len(spec['scenarios']):raise ValueError('情景字段索引越界')
    expected=numeric(spec['scenarios'][index]['navImpactCNY'])
   else:raise ValueError('金额定位字段未知')
   amounts=[numeric(x.replace(',','')) for x in re.findall(r'(?<![\d.,])-?\d[\d,]*\.\d+(?![\d.])',compact(quote))]
   if expected not in amounts:raise ValueError('输入金额不在对应原文引句中')
   matched_fields.add(field)
   if field.startswith('scenarios/'):
    index=int(field.split('/')[1]);scenario=spec['scenarios'][index]
    matches=re.findall(r'利率(增加|上升|减少|下降|降低)(\d+(?:\.\d+)?)(%|个基点|基点)',compact(quote))
    if len(matches)==1:
     direction,magnitude,unit=matches[0];bp=numeric(magnitude)*(100 if unit=='%' else 1)*(1 if direction in ('增加','上升') else -1)
     keys=[k for k in ('parallelShiftBasisPoints','reportedRateChangeBasisPoints') if k in scenario]
     if len(keys)!=1 or bp!=numeric(scenario[keys[0]]):raise ValueError('冲击方向或基点与对应金额原文不一致')
     if keys[0]=='parallelShiftBasisPoints' and '平行' not in compact(quote):raise ValueError('原文未说明平行移动，不能扩写冲击范围')
     shock_bindings[index]=dict(page=page,quote=quote,rateChangeBasisPoints=str(bp),status='quote-located-unit-converted-not-model-certified')
  bindings.append(loc)
 if not bindings:raise ValueError('缺少原页定位')
 required={'childNetAssetsCNY'}|{'scenarios/'+str(i)+'/navImpactCNY' for i in range(len(spec['scenarios']))}
 if required-matched_fields:raise ValueError('净资产或情景金额缺少对应原页定位')
 if not isinstance(spec.get('assumptions'),list) or not spec['assumptions'] or any(not isinstance(x,str) or not x.strip() for x in spec['assumptions']):raise ValueError('须列明披露情景假设')
 rows=[]
 for s in spec['scenarios']:
  keys=[k for k in ('parallelShiftBasisPoints','reportedRateChangeBasisPoints') if k in s]
  if len(keys)!=1:raise ValueError('须明确且仅指定一种利率冲击口径')
  shock_key=keys[0];shock=numeric(s[shock_key]);impact=numeric(s['navImpactCNY'])
  if shock==0:raise ValueError('利率冲击不能为零')
  index=len(rows);binding=shock_bindings.get(index)
  rows.append(dict(shockDefinition=shock_key,shockVerification=binding['status'] if binding else 'input-declared-not-original-verified',shockEvidence=binding,rateChangeBasisPoints=str(shock),navImpactCNY=str(impact),childNAVImpactFraction=str(impact/nav),isolatedParentImpactFraction=str(weight*impact/nav)))
 if not rows:raise ValueError('缺少披露情景')
 return dict(parentWeightEvidence=parent_binding,type='disclosed-child-rate-scenario',reportDate=spec['reportDate'],publishedAt=spec['publishedAt'],childNetAssetsCNY=str(nav),parentWeight=str(weight),scenarios=rows,assumptions=spec['assumptions'],source=dict(path=str(p.resolve()),sha256=evidence['sha256'],locators=bindings),formulas=['子基金影响比例=披露影响金额/同日报表净资产','单项父基金静态影响=父持仓权重×子基金影响比例'],limitations=['原页引句与金额复算不认证经济模型或完整原文','冲击与父权重核验范围按各字段状态判断，不得称全部情景参数已核验','仅单个子基金静态情景，不代表FOF整体损失或未来走势','不同冲击幅度不线性外推；其他资产与管理操作未计入'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=calculate(json.loads(a.input.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant),a.input.resolve().parent)
 with a.out.open('x',encoding='utf-8') as f:json.dump(r,f,ensure_ascii=False,indent=2)


