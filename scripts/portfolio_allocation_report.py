"""Readable comparison of existing historical allocation candidates."""
import argparse,json,copy
from pathlib import Path
from datetime import datetime,timezone
from portfolio_models import optimize,number
from research_brief_html import render
from collection_validation import unique_pairs,reject_constant,finite_json_float

def publish(spec,out):
    out=Path(out)
    if out.exists():raise FileExistsError('请另存新的配置研究目录')
    notes=spec.get('scopeNotes',[]) if isinstance(spec,dict) else []
    if not isinstance(notes,list) or len(notes)>20 or any(not isinstance(note,str) or not note.strip() or len(note)>2000 for note in notes):raise ValueError('范围说明须为最多20条非空文字')
    result=optimize(spec);baseline=result['equalWeightBaseline'];minimum=result['minimumVariance'];erc=result['riskParityCandidate']
    if spec.get('exampleType') is not None:
        if spec['exampleType']!='teaching-only':raise ValueError('示例标记仅支持teaching-only')
        result['exampleType']='teaching-only'
    windows=spec.get('sensitivityWindows',[])
    if not isinstance(windows,list) or len(windows)>8 or any(isinstance(n,bool) or not isinstance(n,int) or not 24<=n<=5000 for n in windows) or len(set(windows))!=len(windows):raise ValueError('窗口敏感性须最多8个唯一整数，每个24至5000个收益观察')
    sensitivity=[]
    for length in windows:
        if length>result['observations']:
            sensitivity.append({'windowObservations':length,'status':'insufficient-history','availableObservations':result['observations']});continue
        part=copy.deepcopy(spec);part.pop('sensitivityWindows',None)
        for asset in part['assets']:asset['history']=asset['history'][-(length+1):]
        tested=optimize(part)
        sensitivity.append({'windowObservations':length,'status':'calculated-historical-window','sampleStart':tested['sampleStart'],'sampleEnd':tested['sampleEnd'],'minimumVariance':tested['minimumVariance'],'riskParityCandidate':tested['riskParityCandidate']})
    result['windowSensitivity']=sensitivity
    delta=baseline['annualizedVolatilityPct']-minimum['annualizedVolatilityPct']
    body=f"# 组合配置候选比较\n\n> 本样本中，最小方差候选的历史年化波动率比等权低{delta:.2f}个百分点；这只是样本内风险差异，尚不能证明未来收益或样本外价值。\n\n## 方法怎样取舍\n\n等权不估计收益或风险来决定权重；最小方差按本窗口协方差降低估计波动；风险平价尝试让各资产的波动风险贡献相等。三者都不保证最大亏损，也不是交易权重建议。\n\n观察区间{result['sampleStart']}至{result['sampleEnd']}，{result['observations']}个收益观察；输入频率{ {'daily':'日频','monthly':'月频'}[spec['frequency']] }，币种{spec['currency']}，单资产下限{spec.get('minWeight',0)*100:.1f}%、上限{spec.get('maxWeight',1)*100:.1f}%。\n\n"
    states={'calculated-candidate':'本候选通过上下限检查','constraints-not-met':'违反输入权重上下限，不能作为满足约束的方案','not-converged':'未收敛，不输出权重','not-calculated-non-positive-definite':'协方差严格正定条件不足，不输出权重'}
    old_opening=f'本样本中，最小方差候选的历史年化波动率比等权低{delta:.2f}个百分点；这只是样本内风险差异，尚不能证明未来收益或样本外价值。'
    movement=('低' if delta>=0 else '高')+format(abs(delta),'.2f')+'个百分点'
    body=body.replace(old_opening,'按这段历史和你给的限制来算，最低波动方案的年化波动比平均分配'+movement+'。这是这段历史里的差别，还不能说明以后会更稳或赚得更多。',1)
    body=body.replace('等权不估计收益或风险来决定权重；最小方差按本窗口协方差降低估计波动；风险平价尝试让各资产的波动风险贡献相等。','等权就是每只分一样多的钱；最小方差是根据这段历史，找出估计波动较低的搭配；风险平价则尽量让每只资产承担相近的波动风险。',1)
    largest=max(range(len(minimum['weights'])),key=lambda i:minimum['weights'][i])
    dominant=str(spec['assets'][largest].get('name',result['codes'][largest])).replace('|','／').replace('\n',' ')
    effective=1/sum(weight*weight for weight in minimum['weights'])
    body+=f"最低估计波动候选把{minimum['weights'][largest]*100:.1f}%资金分配给{dominant}，资金权重集中度等效数量约{effective:.2f}只。低估计波动与资金集中可以同时存在；这个数量不识别基金底层重叠，也不是独立风险来源数。\n\n"
    body+='风险平价状态：'+states[erc['status']]+'。\n\n|资产|等权|最小方差|风险平价候选|ERC估计风险贡献占比|\n|---|---:|---:|---:|---:|\n'
    for i,asset in enumerate(spec['assets']):
        name=str(asset.get('name',asset['code'])).replace('|','／').replace('\n',' ')
        weight='未输出' if erc['weights'] is None else f"{erc['weights'][i]*100:.2f}%"
        contribution='未计算' if not erc.get('riskContributionShares') else f"{erc['riskContributionShares'][i]*100:.2f}%"
        body+=f"|{name}（{asset['code']}）|{baseline['weights'][i]*100:.2f}%|{minimum['weights'][i]*100:.2f}%|{weight}|{contribution}|\n"
    body+='\n风险平价均衡的是当前协方差下的波动风险贡献，而不是资金权重、行业敞口或最坏损失。候选不合格时，贡献数字仅作诊断；没有据此推荐调仓。\n'
    concentration=minimum['riskConcentration']
    value=concentration['effectiveRiskContributors']
    if value is not None:
        body+=f'\n最低波动候选的风险贡献集中度，等效约{value:.2f}项。它与资金权重的等效数量{effective:.2f}不同：钱分得开，不代表波动风险也分得开。两者都不是独立风险来源数。\n'
    else:body+='\n本候选存在负风险贡献或零方差，风险集中度等效数量不作解释。\n'
    diagnostic=result['covarianceDiagnostics']
    def condition_text(value):return '无穷或无法定义' if value is None else format(value,'.3g')
    body+='\n协方差条件数：样本'+condition_text(diagnostic['sampleConditionNumber'])+'，用于计算的矩阵'+condition_text(diagnostic['estimatedConditionNumber'])+'。条件数很大时，小幅估计变化可能放大权重变化，不能据此认定数据错误。\n'
    for warning in diagnostic['warnings']:body+='\n'+warning+'\n'
    body+='\n## 风险主要来自谁\n\n|资产|等权波动风险贡献占比|最小方差波动风险贡献占比|\n|---|---:|---:|\n'
    for i,asset in enumerate(spec['assets']):
        name=str(asset.get('name',asset['code'])).replace('|','／').replace('\n',' ')
        def share(candidate):return '无法定义' if candidate['riskContributionShares'] is None else format(candidate['riskContributionShares'][i]*100,'.2f')+'%'
        body+='|'+name+'|'+share(baseline)+'|'+share(minimum)+'|\n'
    body+='\n这是给定协方差下的波动贡献，可能为负或超过100%，不能解释为亏损概率或最大回撤贡献；零方差时留空。负贡献可能反映模型中的对冲作用，不据此认定资产安全。\n'
    if minimum['riskContributionShares'] is not None:
        top=max(range(len(result['codes'])),key=lambda i:minimum['riskContributionShares'][i])
        body+='\n最小方差候选中，'+str(spec['assets'][top].get('name',result['codes'][top]))+'的波动贡献最大，约'+format(minimum['riskContributionShares'][top]*100,'.1f')+'%。风险集中要结合此占比和底层持仓判断，不能只数产品数量。\n'
    body+='\n## 估计风险与基线\n\n'
    body+=f"等权历史年化波动{baseline['annualizedVolatilityPct']:.2f}%，最小方差{minimum['annualizedVolatilityPct']:.2f}%。"
    if erc.get('annualizedVolatilityPct') is not None:body+=f"风险平价候选{erc['annualizedVolatilityPct']:.2f}%，即使未通过上限仍仅作候选诊断，不采用该权重。"
    body+='\n\n## 资料及未完成条件\n\n协方差目前是未收缩的样本估计；尚未完成本方案要求的收缩估计、类别上下限、最大分散度、观点输入、回撤预算与样本外检验。因此这不是完整配置决策引擎。未含实际成交和费用。\n'
    if notes:
        body+='\n本次输入特别说明：\n'+''.join('\n- '+note for note in notes)+'\n'
        result['scopeNotes']=notes
    if result.get('covarianceShrinkage'):
        detail=result['covarianceShrinkage']
        description=('自动Ledoit–Wolf常相关收缩，估计强度' if detail['method']=='ledoit-wolf-constant-correlation' else '显式常相关收缩，声明强度')+format(detail['intensity'],'.4f')+'；仍需验证样本适用性；'
        body=body.replace('协方差目前是未收缩的样本估计；',description)
        if detail['method']=='ledoit-wolf-constant-correlation':body=body.replace('尚未完成本方案要求的收缩估计、','尚未完成本方案要求的').replace('尚未完成本方案要求的自动收缩估计、','尚未完成本方案要求的')
    if sensitivity:
        body+='\n\n## 换一个历史窗口会怎样\n\n窗口为最后N个收益观察，不保证完整交易日；固定同一截止日和其他参数，窗口互相重叠，不是样本外检验。\n'
        for item in sensitivity:
            if item['status']=='insufficient-history':body+=f"\n- {item['windowObservations']}个收益观察：现有仅{item['availableObservations']}个，不计算、不补齐。"
            else:
                weights='、'.join(code+' '+format(weight*100,'.1f')+'%' for code,weight in zip(result['codes'],item['minimumVariance']['weights']))
                body+=f"\n- {item['windowObservations']}个收益观察（{item['sampleStart']}至{item['sampleEnd']}）：最小方差权重{weights}；历史估计波动{item['minimumVariance']['annualizedVolatilityPct']:.2f}%。"
        body+='\n\n权重随窗口明显变化说明对历史估计敏感，不能据某个窗口数字最好便认定未来配置更好。'
    for asset in spec['assets']:body+='\n- '+asset['code']+'：[历史来源]('+asset['sourceUrl']+')'
    body+='\n\n基准：等权。风险平价只检验数值残差及输入上下限，不能将收敛理解为投资可靠。总回报完整性与日频交易日完整性尚未独立认证。历史不代表未来，不构成投资建议。'
    if result.get('exampleType')=='teaching-only':body=body.replace('# 组合配置候选比较\n','# 组合配置候选比较\n\n**教学数据：虚构资产与模拟序列，不是真实基金、持仓或市场预测。**\n',1)
    if result.get('classConstraints') is not None:
        body=body.replace('尚未完成本方案要求的收缩估计、类别上下限、最大分散度','尚未完成本方案要求的自动收缩估计、最大分散度')
        body+='\n\n## 本次类别约束\n\n最小方差已按声明类别求解；等权与风险平价只作比较并检查合规性，未通过者不能采用。历史前沿各点也采用同一类别约束，历史均值不当作未来预期。\n'
        for label,limit in result['classConstraints'].items():body+=f"\n- {label}：下限{limit['min']*100:.1f}%、上限{limit['max']*100:.1f}%，最小方差结果{minimum['classWeights'][label]*100:.1f}%。"
        body+='\n\n等权基线：'+('违反类别约束，仅作不合格对照。' if baseline['status']=='constraints-not-met' else '通过类别约束检查。')
        body=body.replace('历史年化波动率比等权低'+format(delta,'.2f')+'个百分点','历史年化波动率与等权差额（等权减本候选）为'+format(delta,'.2f')+'个百分点')
    out.mkdir(parents=True)
    files={'input.json':json.dumps(spec,ensure_ascii=False,allow_nan=False,indent=2),'result.json':json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2),'组合配置候选比较.md':body,'组合配置候选比较.html':render(body,'组合配置候选比较')}
    for name,text in files.items():(out/name).write_text(text,'utf-8')
    request={'command':'allocation','codes':result['codes'],'names':[str(asset.get('name',asset['code'])) for asset in spec['assets']],'start':result['sampleStart'],'asOf':result['sampleEnd']}
    (out/'research-request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),'utf-8')
    files['research-request.json']=None
    (out/'report-manifest.json').write_text(json.dumps({'files':{name:None for name in files},'primaryReport':'组合配置候选比较.html','savedAt':datetime.now(timezone.utc).isoformat()},ensure_ascii=False,indent=2),'utf-8')
    return result

def replay(previous,out,max_weight=None):
    root=Path(previous).resolve();source=(root/'input.json').resolve()
    if not source.is_relative_to(root) or source.stat().st_size>16*1024*1024:raise ValueError('旧输入路径或大小异常')
    spec=json.loads(source.read_bytes().decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
    try:original=optimize(spec)
    except ValueError:original=None
    if max_weight is not None:spec['maxWeight']=number(max_weight)
    # Recompute all candidates; do not inherit a previously claimed optimum.
    result=publish(spec,out)
    note='沿用原资料日期、历史、币种与范围说明；本次未联网更新。'+('仅按明确要求改动单资产上限。' if max_weight is not None else '沿用全部输入参数，按当前计算版本重算。')
    if original is None:
        text='# 本次配置追问\n\n'+note+'\n\n旧输入在当前约束下未能完成计算，本次修改后已独立生成候选；没有旧可行方案，不做前后数值比较。'
        (Path(out)/'复用说明.md').write_text(text,'utf-8');(Path(out)/'复用说明.html').write_text(render(text,'配置追问说明'),'utf-8')
        manifest=Path(out)/'report-manifest.json';data=json.loads(manifest.read_text('utf-8'));data['files'].update({'复用说明.md':None,'复用说明.html':None});manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
        return result
    old=original['minimumVariance'];new=result['minimumVariance']
    difference=new['annualizedVolatilityPct']-old['annualizedVolatilityPct']
    text='# 本次配置追问\n\n> 按同一计算版本与历史重算，新约束下最小方差估计波动变化'+format(difference,'+.2f')+'个百分点；这不是未来风险变化或交易效果。\n\n'+note+'\n\n|资产|原最小方差候选|新最小方差候选|权重变化|\n|---|---:|---:|---:|\n'
    for code,before,after in zip(result['codes'],old['weights'],new['weights']):text+=f'|{code}|{before*100:.2f}%|{after*100:.2f}%|{(after-before)*100:+.2f}个百分点|\n'
    text+='\n新约束可能减少资金集中，也可能提高本样本估计波动；不能仅因权重更均匀就认定更安全。旧结果未被覆盖，前后按当前版本重算原输入，未把方法变化混作约束效果。尚未证明未来风险、收益或账户可执行。'
    (Path(out)/'复用说明.md').write_text(text,'utf-8')
    (Path(out)/'复用说明.html').write_text(render(text,'配置约束前后对照'),'utf-8')
    manifest=Path(out)/'report-manifest.json';data=json.loads(manifest.read_text('utf-8'));data['files']['复用说明.md']=None;data['files']['复用说明.html']=None;manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
    return result

def explain_failure(error,out,spec=None):
    out=Path(out)
    if out.exists():return
    body='# 配置研究需要补充条件\n\n> 本次未得到满足输入条件的配置，没有生成可采用权重。\n\n问题：'+str(error)+'\n\n## 怎样继续\n\n核对资产分类、上下限是否冲突，以及资产池是否缺少要求的类别。例如资产池全部是权益产品，却要求权益总占比低于100%，且不允许现金或新增资产，就没有可行配置。\n\n请明确修改约束，或补充有依据的其他资产及历史；工具不会自动放宽条件、加入虚构现金资产或补造历史。若是资料格式问题，修正后另存新的研究目录。旧报告保留。\n\n本次未完成配置评价，不构成投资建议。'
    out.mkdir(parents=True)
    (out/'下一步.md').write_text(body,'utf-8');(out/'下一步.html').write_text(render(body,'配置研究下一步'),'utf-8')
    (out/'start-result.json').write_text(json.dumps({'status':'blocked','message':str(error),'savedAt':datetime.now(timezone.utc).isoformat()},ensure_ascii=False),'utf-8')
    # An explicit failure entry supports retrieval without pretending a research report exists.
    (out/'打开这里.html').write_text(render(body,'配置研究下一步'),'utf-8')
    if isinstance(spec,dict):
        try:raw=json.dumps(spec,ensure_ascii=False,allow_nan=False,indent=2)
        except (ValueError,TypeError):return
        if len(raw.encode('utf-8'))<=16*1024*1024:(out/'input.json').write_text(raw,'utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input',type=Path,nargs='?');parser.add_argument('--continue-from',type=Path);parser.add_argument('--max-weight',type=float);parser.add_argument('--out-dir',required=True);args=parser.parse_args()
    if bool(args.input)==bool(args.continue_from):parser.error('输入文件或旧报告二选一')
    try:
        if args.continue_from:replay(args.continue_from,args.out_dir,args.max_weight)
        else:
            spec=json.loads(args.input.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
            if args.max_weight is not None:spec['maxWeight']=number(args.max_weight)
            publish(spec,args.out_dir)
    except (ValueError,KeyError,TypeError) as error:
        retained=None
        try:
            path=args.input or args.continue_from/'input.json'
            if path.stat().st_size<=16*1024*1024:
                retained=json.loads(path.read_bytes().decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
                if args.max_weight is not None and isinstance(retained,dict):retained['maxWeight']=number(args.max_weight)
        except (OSError,ValueError,TypeError):pass
        explain_failure(error,args.out_dir,retained)
        parser.exit(1,'配置未完成，请查看新目录中的下一步.html；未放宽约束。\n')
