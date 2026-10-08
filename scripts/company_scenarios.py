"""Explicit-assumption company scenarios: FCFF DCF, relative multiples, simplified three statements."""
import argparse,datetime as dt,hashlib,json,math,statistics
from pathlib import Path
from urllib.parse import urlsplit
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant,finite_json_float

def load_json(text):
 return json.loads(text,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def date_value(x):
 if not isinstance(x,str):raise ValueError("日期须为YYYY-MM-DD文字")
 try:parsed=dt.date.fromisoformat(x)
 except ValueError as exc:raise ValueError("日期须为YYYY-MM-DD文字") from exc
 if parsed.isoformat()!=x:raise ValueError("日期须为YYYY-MM-DD文字")
 return x


def number(x):
 if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x):raise ValueError('需有限数值')
 return float(x)
def value(x,asof):
 if not isinstance(x,dict) or x.get('basis') not in ['source-statement','calculation','assumption']:raise ValueError('输入需明确来源陈述或假设')
 v=number(x['value'])
 if not isinstance(x.get('note'),str) or not x['note'].strip():raise ValueError('需说明参数含义或假设依据')
 if x['basis']!='assumption':
  source=x.get('sourceUrl');locator=x.get('locator')
  if not isinstance(source,str) or any(c.isspace() or ord(c)<32 or ord(c)==127 for c in source) or not isinstance(locator,str) or not locator.strip():raise ValueError('来源值需URL和原文定位')
  try:
   u=urlsplit(source);port=u.port
  except ValueError as exc:raise ValueError('来源URL无效') from exc
  if u.scheme!='https' or not u.hostname or u.username is not None or u.password is not None or port not in (None,443):raise ValueError('来源URL无效')
  published=date_value(x.get('publishedAt'))
  if published>asof:raise ValueError('来源发布日期晚于截止日')
 return v

def numeric_bindings(s):
 """Check declared numeric JSON anchors; this is not PDF original verification."""
 results=[]
 def visit(obj,path):
  if isinstance(obj,dict):
   binding=obj.get('numericBinding')
   if binding is not None:
    if obj.get('basis')=='assumption':raise ValueError('假设不能冒充历史数值绑定')
    candidates=[b for b in s.get('sourceFiles',[]) if b['path']==binding.get('path')]
    if len(candidates)!=1:raise ValueError('字段绑定需唯一已登记来源文件')
    source=Path(binding['path'])
    if source.suffix.lower()!='.json':raise ValueError('数值绑定仅支持JSON底稿；PDF需原文核验流程')
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=candidates[0]['sha256']:raise ValueError('字段来源文件哈希已变化')
    pointer=binding.get('pointer')
    if not isinstance(pointer,str) or not pointer.startswith('/'):raise ValueError('需明确JSON字段路径')
    target=load_json(raw.decode('utf-8-sig'));row_metadata=None
    try:
     for token in pointer[1:].split('/'):
      token=token.replace('~1','/').replace('~0','~')
      target=target[int(token)] if isinstance(target,list) else target[token]
      if isinstance(target,dict) and 'period' in target and 'publishedAt' in target:row_metadata=target
    except (KeyError,IndexError,ValueError,TypeError) as e:raise ValueError('来源数值字段不存在') from e
    if row_metadata is not None:
     for key in ['period','publishedAt']:
      observed=row_metadata[key]
      if not isinstance(observed,str):raise ValueError('绑定底稿行的日期格式无效')
      date_value(observed)
      if observed>s['asOf']:raise ValueError('绑定底稿行的报告期或发布日期晚于研究截止日')
     if obj.get('publishedAt')!=row_metadata['publishedAt']:raise ValueError('输入发布日期与绑定底稿行不一致')
     if obj.get('observationPeriod') is not None and obj['observationPeriod']!=row_metadata['period']:raise ValueError('输入报告期与绑定底稿行不一致')
    scale=number(binding.get('scale',1))
    if scale<=0:raise ValueError('金额缩放系数需为正')
    expected=number(target)*scale;actual=number(obj['value'])
    if not math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-8):raise ValueError('输入数值与来源字段不一致：'+path)
    results.append(dict(inputPath=path,sourcePath=str(source),pointer=pointer,scale=scale,status='numeric-json-anchor-matched',originalVerified=False,boundPeriod=row_metadata.get('period') if row_metadata else None,boundPublishedAt=row_metadata.get('publishedAt') if row_metadata else None))
   for k,v in obj.items():
    if k!='numericBinding':visit(v,path+'/'+k)
  elif isinstance(obj,list):
   for i,v in enumerate(obj):visit(v,path+'/'+str(i))
 visit(s,'')
 return results

def input_evidence_summary(s):
 entries=[]
 def visit(obj,path):
  if isinstance(obj,dict):
   if obj.get('basis') in ['source-statement','calculation','assumption'] and 'value' in obj:
    entries.append(dict(inputPath=path,basis=obj['basis'],note=obj.get('note'),numericAnchorDeclared='numericBinding' in obj,originalVerified=False,value=obj.get('value'),sourceUrl=obj.get('sourceUrl'),publishedAt=obj.get('publishedAt'),locator=obj.get('locator')))
   for k,v in obj.items():
    if k not in ['sourceFiles','numericBinding']:visit(v,path+'/'+k)
  elif isinstance(obj,list):
   for i,v in enumerate(obj):visit(v,path+'/'+str(i))
 visit(s,'')
 return dict(entries=entries,assumptionCount=sum(e['basis']=='assumption' for e in entries),sourceClaimCount=sum(e['basis']!='assumption' for e in entries),originalVerificationStatus='not-performed-by-scenario-model')

def context(s):
 if not isinstance(s,dict):raise ValueError('情景输入须为对象')
 date_value(s['asOf'])
 if not s.get('currency') or not s.get('unit') or not s.get('identity',{}).get('name'):raise ValueError('需公司名称、币种和金额单位')
 for binding in s.get('sourceFiles',[]):
  raw=Path(binding['path']).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=binding['sha256']:raise ValueError('输入来源文件哈希已变化')
  if Path(binding['path']).suffix.lower()=='.json':
   data=load_json(raw.decode('utf-8-sig'));code=data.get('code') if isinstance(data,dict) else None
   expected={r['code'] for r in s['companies']} if s.get('companies') else {s['identity'].get('code')}
   if code is not None and len(str(code))==6 and str(code).isdigit() and None not in expected and str(code) not in expected:raise ValueError('来源公司代码与本次对象不一致')
 numeric_bindings(s)
 return s['asOf']
def wacc(s,asof):
 vals={k:value(s[k],asof) for k in ['equityCost','debtCost','taxRate','equityWeight']}
 if not 0<=vals['taxRate']<1 or not 0<=vals['equityWeight']<=1 or min(vals['equityCost'],vals['debtCost'])<0:raise ValueError('资本成本或权重范围无效')
 return vals['equityWeight']*vals['equityCost']+(1-vals['equityWeight'])*vals['debtCost']*(1-vals['taxRate'])

def dcf(s):
 asof=context(s)
 if s.get('cashFlowType','FCFF')!='FCFF' or any(c.get('cashFlowType','FCFF')!='FCFF' for c in s['cashFlows']):raise ValueError('本模式仅支持FCFF，股权现金流不能套用企业现金流折现')
 if bool(s.get('wacc'))==bool(s.get('discountRate')):raise ValueError('WACC参数和直接折现率二选一')
 rate=wacc(s['wacc'],asof) if s.get('wacc') else value(s['discountRate'],asof);g=value(s['terminalGrowth'],asof);netdebt=value(s['netDebt'],asof)
 if not 0<rate<1 or not -1<g<rate:raise ValueError('需0<折现率<1且-1<永续增长率<折现率')
 cfs=s['cashFlows']
 if not isinstance(cfs,list) or any(not isinstance(x,dict) or type(x.get('year')) is not int for x in cfs) or not 1<=len(cfs)<=30 or [x['year'] for x in cfs]!=list(range(1,len(cfs)+1)):raise ValueError('FCFF需连续第1至30年内年度序列')
 vals=[value(c,asof) for c in cfs]
 if vals[-1]<=0:raise ValueError('永续增长模型需最后一年正FCFF；负现金流需另建终值假设')
 n=len(vals)
 def cell(r,growth):
  if not 0<r<1 or not -1<growth<r:return dict(discountRate=r,growth=growth,status='invalid')
  pvs=[cf/(1+r)**(i+1) for i,cf in enumerate(vals)];terminal=vals[-1]*(1+growth)/(r-growth);pvterminal=terminal/(1+r)**n;enterprise=sum(pvs)+pvterminal
  return dict(discountRate=r,growth=growth,status='calculated',enterpriseValue=enterprise,equityValue=enterprise-netdebt,terminalValue=terminal,pvTerminal=pvterminal,pvCashFlows=pvs,terminalShare=pvterminal/enterprise if enterprise else None)
 base=cell(rate,g);base['equityValuePerShare']=None
 if s.get('shares'):
  shares=value(s['shares'],asof)
  if shares<=0:raise ValueError('股数需为正')
  # shares must be expressed in the same amount-scale as the declared monetary unit.
  if s['shares'].get('unitScale')!=s['unit']:raise ValueError('股数缩放需与金额单位一致，例如百万元对应百万股')
  base['equityValuePerShare']=base['equityValue']/shares
 grid=[cell(rate+dr,g+dg) for dr in [-.01,0,.01] for dg in [-.005,0,.005]]
 return dict(type='FCFF-DCF-scenario',base=base,sensitivity=grid,formulas=['WACC=E_weight*Ke+(1-E_weight)*Kd*(1-tax)','EV=sum(FCFF_t/(1+WACC)^t)+FCFF_n*(1+g)/(WACC-g)/(1+WACC)^n','Equity=EV-netDebt'],limitations=['用户提供FCFF、增长率与资本成本；模型未验证预测能实现','FCFF配WACC；不将股权现金流配WACC','年末折现、恒定资本成本；终值高度敏感','净债务口径须包括所需股权桥接调整；未提供的少数股权、非经营资产或稀释权利不会自动补齐','每股情景值不是目标价格、安全边际或买卖结论'])

def relative(s):
 asof=context(s);rows=s['companies']
 if not 2<=len(rows)<=50 or len({r['code'] for r in rows})!=len(rows):raise ValueError('需2至50家不重复公司')
 dates={r['valuationDate'] for r in rows};periods={r['financialPeriod'] for r in rows};definitions={r['definition'] for r in rows}
 if len(dates)!=1 or len(periods)!=1 or len(definitions)!=1:raise ValueError('估值日期、财务期间及口径需一致')
 for d in dates|periods:
  date_value(d)
  if d>asof:raise ValueError('对比日期越界')
 output=[]
 for r in rows:
  if r.get('currency',s['currency'])!=s['currency'] or r.get('unit',s['unit'])!=s['unit']:raise ValueError('样本币种或金额单位不一致')
  fields={k:value(r[k],asof) if r.get(k) is not None else None for k in ['marketCap','netProfit','equity','revenue','netDebt','EBITDA']}
  m,profit,equity,revenue=[fields[k] for k in ['marketCap','netProfit','equity','revenue']]
  if (m is not None and m<=0) or (revenue is not None and revenue<0):raise ValueError('市值需为正，收入不得为负')
  vals=dict(PE=m/profit if m is not None and profit is not None and profit>0 else None,PB=m/equity if m is not None and equity is not None and equity>0 else None,PS=m/revenue if m is not None and revenue is not None and revenue>0 else None,EV_EBITDA=None)
  if m is not None and fields['netDebt'] is not None and fields['EBITDA'] is not None and fields['EBITDA']>0:vals['EV_EBITDA']=(m+fields['netDebt'])/fields['EBITDA']
  output.append(dict(code=r['code'],name=r['name'],multiples=vals,gaps=[k for k,v in fields.items() if v is None]))
 medians={k:statistics.median(vs) if (vs:=[r['multiples'][k] for r in output if r['multiples'][k] is not None]) else None for k in ['PE','PB','PS','EV_EBITDA']}
 return dict(type='declared-peer-multiple-comparison',rows=output,medians=medians,valuationDate=next(iter(dates)),financialPeriod=next(iter(periods)),definition=next(iter(definitions)),limitations=['可比池为输入声明，不自动证明商业模式或会计口径确实可比','负利润、负净资产、非正EBITDA的对应倍数留空，不用绝对值修饰','市值、收入与利润必须同币种同金额单位；期间为用户明确口径','低于样本中位数不证明低估，不生成买卖建议'])

def forecast_scope(s):
 declared=s.get('companyType')
 if declared is not None and declared not in ['nonfinancial','bank','insurance','securities','financial']:raise ValueError('companyType须明确为非金融或金融行业类别')
 if declared in ['bank','insurance','securities','financial']:raise ValueError('普通企业三表情景不适用于银行、保险、证券等金融行业')
 types=set()
 for binding in s.get('sourceFiles',[]):
  p=Path(binding['path'])
  if p.suffix.lower()!='.json':continue
  data=load_json(p.read_text(encoding='utf-8-sig'))
  if not isinstance(data,dict):continue
  for table in data.get('tables',{}).values():
   for row in table.get('rows',[]):
    kind=row.get('raw',{}).get('ORG_TYPE')
    if isinstance(kind,str):types.add(kind)
 if any(any(k in kind for k in ['银行','保险','证券','金融']) for kind in types):raise ValueError('绑定底稿标识为金融行业，不能套用普通企业三表情景')
 return dict(declaredCompanyType=declared,providerOrgTypes=sorted(types),status='nonfinancial-input-declared' if declared=='nonfinancial' else 'financial-type-not-detected-not-independent-verified',scope='仅检查明确行业声明和登记底稿类别；缺少类别不证明公司属于非金融行业')

def debt_scope_review(s,asof):
 scope=s.get('debtScope')
 if scope is None:return dict(status='not-declared',components=[],excluded=[],scope='未登记债务构成，模型债务不视为全部有息负债或到期本息')
 if not isinstance(scope,dict) or not isinstance(scope.get('components'),list) or not scope['components']:raise ValueError('债务范围需非空构成清单')
 names=[];parts=[]
 for item in scope['components']:
  if not isinstance(item,dict) or not isinstance(item.get('name'),str) or not item['name'].strip():raise ValueError('债务项目名称须为非空文字')
  names.append(item['name'].strip());amount=value(item,asof)
  if amount<0:raise ValueError('债务构成金额不得为负')
  parts.append(dict(name=names[-1],value=amount,basis=item['basis']))
 excluded=scope.get('excluded',[])
 if not isinstance(excluded,list) or any(not isinstance(x,str) or not x.strip() for x in excluded):raise ValueError('排除债务项目须文字列表')
 excluded=[x.strip() for x in excluded]
 if len(names)!=len(set(names)) or len(excluded)!=len(set(excluded)) or set(names)&set(excluded):raise ValueError('债务构成重复或与排除项冲突')
 total=math.fsum(x['value'] for x in parts);declared=value(s['opening']['debt'],asof)
 if not math.isfinite(total) or not math.isclose(total,declared,rel_tol=1e-10,abs_tol=1e-8):raise ValueError('债务构成合计与模型期初债务不一致')
 return dict(status='declared-components-matched-not-complete',components=parts,excluded=excluded,total=total,scope='仅所列构成金额合计，不证明完整债务、未来到期或利息口径')

def forecast(s):
 asof=context(s);scope_review=forecast_scope(s);debt_review=debt_scope_review(s,asof);base=s['opening'];b={k:value(base[k],asof) for k in ['revenue','cash','receivables','inventory','fixedAssets','otherAssets','payables','debt','otherLiabilities','equity']}
 if min(b.values())<0 or b['revenue']<=0:raise ValueError('基础值须非负，收入需为正')
 def difference(x):return x['cash']+x['receivables']+x['inventory']+x['fixedAssets']+x['otherAssets']-x['payables']-x['debt']-x['otherLiabilities']-x['equity']
 if abs(difference(b))>max(1,abs(b['equity']))*1e-8:raise ValueError('期初资产负债表不平；不自动塞入其他科目配平')
 years=s['years']
 if not isinstance(years,list) or any(not isinstance(y,dict) or type(y.get('year')) is not int for y in years) or not 1<=len(years)<=5 or [y['year'] for y in years]!=list(range(1,len(years)+1)):raise ValueError('需连续1至5年年度情景')
 results=[]
 for row in years:
  a={k:value(row[k],asof) for k in ['revenueGrowth','grossMargin','opexRate','taxRate','depreciationRate','capexRate','DSO','DIO','DPO','interestRate','netBorrowing','payoutRate']}
  if a['revenueGrowth']<=-1 or any(not 0<=a[k]<=1 for k in ['grossMargin','opexRate','taxRate','depreciationRate','capexRate','interestRate','payoutRate']) or any(not 0<=a[k]<=730 for k in ['DSO','DIO','DPO']):raise ValueError('经营假设范围无效')
  revenue=b['revenue']*(1+a['revenueGrowth']);cost=revenue*(1-a['grossMargin']);opex=revenue*a['opexRate'];dep=b['fixedAssets']*a['depreciationRate'];capex=revenue*a['capexRate'];debt=b['debt']+a['netBorrowing']
  if debt<0:raise ValueError('净还款超过现有债务')
  interest=(b['debt']+debt)/2*a['interestRate'];ebit=revenue-cost-opex-dep;pretax=ebit-interest;tax=max(pretax,0)*a['taxRate'];profit=pretax-tax;dividends=max(profit,0)*a['payoutRate']
  ar=revenue/365*a['DSO'];inv=cost/365*a['DIO'];ap=cost/365*a['DPO'];dnwc=(ar-b['receivables'])+(inv-b['inventory'])-(ap-b['payables']);cfo=profit+dep-dnwc;cfi=-capex;cff=a['netBorrowing']-dividends;cash=b['cash']+cfo+cfi+cff
  end=dict(revenue=revenue,cash=cash,receivables=ar,inventory=inv,fixedAssets=b['fixedAssets']+capex-dep,otherAssets=b['otherAssets'],payables=ap,debt=debt,otherLiabilities=b['otherLiabilities'],equity=b['equity']+profit-dividends)
  results.append(dict(year=row['year'],income=dict(revenue=revenue,costExDepreciation=cost,opexExDepreciation=opex,depreciation=dep,EBIT=ebit,interest=interest,pretaxProfit=pretax,tax=tax,netProfit=profit),cashflow=dict(operating=cfo,investing=cfi,financing=cff,netChange=cfo+cfi+cff,dividends=dividends,deltaNWC=dnwc),balance=end,balanceDifference=difference(end),fundingGap=max(-cash,0),status='unfunded-cash-deficit' if cash<0 else 'scenario-calculated',FCFF=ebit*(1-a['taxRate'])+dep-capex-dnwc))
  if cash<0:break
  b=end
 return dict(type='simplified-linked-statement-scenario',modelScopeReview=scope_review,debtScopeReview=debt_review,years=results,uncomputedYears=[x['year'] for x in years if x['year']>results[-1]['year']],limitations=['普通非金融公司简化情景，非完整会计科目或自动盈利预测','毛利及费用率均为不含折旧口径；折旧=期初固定资产×折旧率，未计当期新增折旧','应收按收入、存货及应付按不含折旧成本，以365日转换；其他资产负债固定','利息按年均债务计算；不计现金利息、汇兑、少数股权、递延税、减值或并购','负税前利润不计所得税；FCFF税盾按给定税率假设，亏损期税盾可实现性需另核','资金缺口明确显示并停止后续年份，不自动借款或配平','情景值不能称作一致预期、确定盈利或未来最优经营方案'])

def scenario_judgment(mode,r):
 """Explain calculated scenario consequences without inventing valuation or causal evidence."""
 if mode=='dcf':
  base=r['base'];valid=[c for c in r['sensitivity'] if c['status']=='calculated']
  spread=max(c['equityValue'] for c in valid)-min(c['equityValue'] for c in valid)
  conclusion='给定现金流假设下，企业折现值不足以覆盖所填净债务。' if base['equityValue']<0 else '给定现金流与净债务假设可得到股权情景值，但尚不能判断当前价格是否有吸引力。'
  return [conclusion,f"九组参数中有{len(valid)}组可计算，股权情景值的最大与最小差额为{spread:,.2f}（沿用报告金额单位）。这是两项参数变化下的敏感性范围，不是置信区间或未来价格区间。",'核心问题是预测现金流能否兑现，以及终值和股权桥接是否合理。若经营资料不支持现金流、资本成本或永续增长假设，应重建情景；本计算没有替代这些验证。']
 if mode=='forecast':
  deficit=next((y for y in r['years'] if y['fundingGap']>0),None)
  if deficit:
   return [f"按所填假设，第{deficit['year']}年出现{deficit['fundingGap']:,.2f}的模型融资缺口，现有情景尚不能作为资金闭合的经营方案。",'利润增长和资金足够是两个问题；需先核现金可用性、回款与资本开支，再明确融资假设。后续年度已停止，不把未计算年份当作零。']
  return ['所计算年度未出现模型现金赤字，但这只说明简化假设下资金闭合，不证明现实偿债安全。','核心问题是利润是否能在回款、库存和资本开支约束下转成可用现金。若实际账期、受限资金或到期付款与输入不同，应重新计算；三表平衡本身不证明假设合理。']
 rows=r['rows'];coverage={k:sum(x['multiples'][k] is not None for x in rows) for k in ['PE','PB','PS','EV_EBITDA']}
 return ['本次只能比较指定样本在声明口径下的倍数，不能仅凭低于中位数认定低估。','各倍数有效样本数：'+ '、'.join(k+' '+str(v)+'/'+str(len(rows)) for k,v in coverage.items())+'。不同倍数的有效样本可能不同，中位数不代表全行业。','判断差异是否有意义，还需验证业务、增长、资本结构与会计口径可比；若这些前提不成立，应调整比较池，而非直接形成价值结论。']

def run(mode,s,out):
 r={'dcf':dcf,'relative':relative,'forecast':forecast}[mode](s);r.update(identity=s['identity'],asOf=s['asOf'],currency=s['currency'],unit=s['unit'],input=s,inputSha256=hashlib.sha256(json.dumps(s,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),codeSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 r['numericBindingChecks']=numeric_bindings(s)
 r['inputEvidenceSummary']=input_evidence_summary(s)
 r['cashFlowTypeBasis']='explicit-input' if s.get('cashFlowType') else 'FCFF-model-convention' if mode=='dcf' else None
 def finite(obj):
  if isinstance(obj,(int,float)) and not isinstance(obj,bool) and not math.isfinite(obj):raise ValueError('计算结果溢出，需检查金额尺度或参数')
  if isinstance(obj,dict):
   for v in obj.values():finite(v)
  elif isinstance(obj,list):
   for v in obj:finite(v)
 finite(r)
 out=Path(out);out.mkdir(parents=True,exist_ok=False);lines=['# '+s['identity']['name']+' · 经营与估值情景','',s['asOf']+'；'+s['currency']+'；金额单位：'+s['unit']+'。结果依赖所列假设，不是盈利承诺或目标价。']
 lines+=['','## 先看结论',*scenario_judgment(mode,r)]
 if mode=='dcf':
  b=r['base'];lines+=['','## 折现情景',f"给定折现率{b['discountRate']:.2%}、永续增长率{b['growth']:.2%}，企业情景折现值{b['enterpriseValue']:,.2f}，净债务调整后的股权情景值{b['equityValue']:,.2f}。",'终值现值占企业情景值：'+(f"{b['terminalShare']:.1%}" if b['terminalShare'] is not None else '无法计算')+'；该比例体现结果对终值假设的依赖。','下表展示敏感性结果，完整数值保留在底稿JSON；改变折现率或增长率会改变结果，无效组合留空。']
  if b['equityValuePerShare'] is not None:lines.append(f"给定股数下，每股股权情景值为{b['equityValuePerShare']:,.2f}；不是目标价，稀释与股权桥接仍需核对。")
  if b['equityValue']<0:lines.append('本情景中净债务调整后的股权值为负，表示所给现金流与桥接假设下企业折现值不足以覆盖净债务；不能解释为股票存在负交易价格。')
  lines += ['','### 折现率与永续增长率敏感性','金额单位沿用本报告；仅改变两项假设，其他输入保持一致。','|折现率|永续增长率|企业情景值|股权情景值|','|---|---|---:|---:|']
  for cell in r['sensitivity']:
   values=[f"{cell[k]:,.2f}" for k in ['enterpriseValue','equityValue']] if cell['status']=='calculated' else ['未计算','未计算']
   lines.append(f"|{cell['discountRate']:.2%}|{cell['growth']:.2%}|"+'|'.join(values)+'|')
  if any(c['status']=='invalid' for c in r['sensitivity']):lines.append('未计算项不满足折现率和永续增长率条件，保留空缺，不当作零。')
 elif mode=='forecast':
  lines.append('本模型限普通非金融企业；行业类别检查不等于完整业务适用性核验。银行、保险、证券等需专门模型。')
  debt_review=r['debtScopeReview']
  lines+=['','### 债务范围',debt_review['scope']]
  if debt_review['components']:lines.append('本次纳入：'+'、'.join(x['name'] for x in debt_review['components'])+'。')
  if debt_review['excluded']:lines.append('明确未纳入：'+'、'.join(debt_review['excluded'])+'；资金和利息结论受此限制。')
  lines+=['','## 年度经营情景','|情景年|收入|净利润|期末现金|融资缺口|三表差额|','|---|---:|---:|---:|---:|---:|']
  for y in r['years']:lines.append('|'+str(y['year'])+'|'+ '|'.join(f'{v:,.2f}' for v in [y['income']['revenue'],y['income']['netProfit'],y['balance']['cash'],y['fundingGap'],y['balanceDifference']])+'|')
  if r['uncomputedYears']:lines.append('出现资金缺口，后续年度停止计算；需明确融资方案后重新建情景。')
  lines += ['','### 利润表联动','|情景年|营业利润（EBIT）|利息|税前利润|所得税|净利润|','|---|---:|---:|---:|---:|---:|']
  for y in r['years']:lines.append('|'+str(y['year'])+'|'+'|'.join(f"{y['income'][k]:,.2f}" for k in ['EBIT','interest','pretaxProfit','tax','netProfit'])+'|')
  lines += ['','### 现金流与企业自由现金流','|情景年|经营现金流|投资现金流|融资现金流|现金净变动|FCFF|','|---|---:|---:|---:|---:|---:|']
  for y in r['years']:lines.append('|'+str(y['year'])+'|'+'|'.join(f"{y['cashflow'][k]:,.2f}" for k in ['operating','investing','financing','netChange'])+f"|{y['FCFF']:,.2f}|")
  lines += ['FCFF与经营现金流口径不同；FCFF税盾按给定税率假设，亏损期可实现性仍需核对。','','### 资产负债联动','|情景年|资产合计|负债合计|权益|期末现金|三表差额|','|---|---:|---:|---:|---:|---:|']
  for y in r['years']:
   balance=y['balance'];assets=sum(balance[k] for k in ['cash','receivables','inventory','fixedAssets','otherAssets']);liabilities=sum(balance[k] for k in ['payables','debt','otherLiabilities'])
   lines.append('|'+str(y['year'])+'|'+'|'.join(f'{v:,.2f}' for v in [assets,liabilities,balance['equity'],balance['cash'],y['balanceDifference']])+'|')

 else:
  lines+=['','## 指定样本倍数',f"估值日期：{r['valuationDate']}；财务期间：{r['financialPeriod']}。口径：{r['definition']}。",'|公司|PE|PB|PS|EV/EBITDA|','|---|---:|---:|---:|---:|']
  for row in r['rows']:
   lines.append('|'+row['name']+'|'+ '|'.join('未计算' if v is None else f'{v:.2f}' for v in row['multiples'].values())+'|')
  for row in r['rows']:
   if 'marketCap' in row['gaps']:lines.append(row['name']+'：市值未取得，不能计算市场估值倍数。')
  for company in s['companies']:
   cap=company.get('marketCap')
   if cap is not None:lines.append(company['name']+'市值依据：'+cap['note']+'；[查看来源]('+cap.get('sourceUrl','')+')。')
 lines+=['','## 数值核对范围',f"本次有{len(r['numericBindingChecks'])}项输入与登记JSON底稿的具体字段及缩放系数核对一致。该核对不代表公告原文已核验；未绑定的输入仍按来源陈述或假设处理。"]
 summary=r['inputEvidenceSummary']
 lines += [f"输入包含{summary['sourceClaimCount']}项来源陈述或计算归并，以及{summary['assumptionCount']}项明确假设。模型没有执行公告原文核验。",'', '### 历史与归并输入依据','|含义及口径|来源等级|报告期|披露日期|底稿字段核对|','|---|---|---|---|---|']
 def table_text(text):return str(text or '未提供').replace('|',r'\|').replace('\n',' ').replace('\r',' ')
 for e in summary['entries']:
  if e['basis']=='assumption':continue
  basis='来源陈述' if e['basis']=='source-statement' else '计算归并'
  anchor='已匹配登记JSON字段，非原文核验' if e['numericAnchorDeclared'] else '未绑定具体底稿字段'
  note=table_text(e['note']);source=e.get('sourceUrl')
  if source:note+=' [查看来源]('+source+')'
  bound=next((x for x in r['numericBindingChecks'] if x['inputPath']==e['inputPath']),{})
  lines.append('|'+note+'|'+basis+'|'+table_text(bound.get('boundPeriod'))+'|'+table_text(e.get('publishedAt'))+'|'+anchor+'|')
 if not summary['sourceClaimCount']:lines.append('|本次没有历史来源输入|全部为假设|不适用|不适用|不适用|')
 if mode=='dcf':lines.append('现金流按FCFF口径计算；'+('输入已明确声明该类型。' if s.get('cashFlowType') else '本次沿用FCFF模型约定，仍需确认现金流编制口径。'))
 notes=[]
 def assumptions(obj):
  if isinstance(obj,dict):
   if obj.get('basis')=='assumption' and obj.get('note') not in notes:notes.append(obj['note'])
   for v in obj.values():assumptions(v)
  elif isinstance(obj,list):
   for v in obj:assumptions(v)
 assumptions(s)
 lines+=['','## 本次明确采用的假设',*['- '+n for n in notes],'','## 假设与资料依据','完整输入、来源条目和公式保留在同目录result.json；来源陈述未自动升级为原文已核验。','','## 口径与局限',*r['limitations']];md='\n'.join(lines)
 payload=json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False);html=render(md,title='经营与估值情景')
 (out/'经营与估值情景.md').write_text(md,encoding='utf8');(out/'经营与估值情景.html').write_text(html,encoding='utf8');(out/'result.json').write_text(payload,encoding='utf8');return r
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['dcf','relative','forecast']);p.add_argument('input',type=Path);p.add_argument('--out-dir',type=Path,required=True);a=p.parse_args();run(a.mode,load_json(a.input.read_text(encoding='utf-8-sig')),a.out_dir)
