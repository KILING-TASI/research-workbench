"""Readable comparison of saved rebalance results; no new market data or advice."""
import argparse
import copy
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from datetime import date
from urllib.parse import urlparse, quote
from pathlib import Path
from collection_validation import unique_pairs, reject_constant
from research_brief_html import render


class CalculationError(ValueError):
    def __init__(self, details):
        self.technical_details=details[-8000:]
        reasons=[('资产日期必须完全一致','各资产的历史日期没有对齐；先按共同日期准备资料，不补造缺失价格。'),
                 ('权重必须非负且合计100%','组合权重需非负且合计100%；请核对输入权重。'),
                 ('需要来源、同币种和总收益口径共同历史','资料缺少来源、统一币种或总收益口径；先补齐这些声明。'),
                 ('最小佣金造成不连续目标','最低佣金使目标权重无法可靠求解；本次未输出近似成功结果。'),
                 ('成本过高，无法完成目标权重交易','输入成本下无法完成目标权重交易；请核对费用和交易规模。'),
                 ('日频间隔不满足年化要求','历史观察过于稀疏或存在较长缺口；不能直接按日频年化。'),
                 ('日期重复、乱序或超过截止日','历史日期重复、乱序或超出截止日；请先核对历史资料。')]
        reason=next((text for marker,text in reasons if marker in details),'计算条件尚未满足；请核对共同日期、总收益口径、组合权重与费用。')
        super().__init__('再平衡研究未完成：'+reason)


def markdown(result):
    if result.get('type') != 'rebalance' or not isinstance(result.get('results'), list) or len(result['results']) < 2:
        raise ValueError('需要已保存的再平衡比较结果')
    rows = result['results']
    for row in rows:
        for key in ('totalReturnPct', 'maximumDrawdownPct', 'totalCost'):
            value = row.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('比较结果缺少有限指标')
        if row['totalCost'] < 0 or not 0 <= row['maximumDrawdownPct'] <= 100:
            raise ValueError('费用或回撤幅度超出范围')
    baselines = [row for row in rows if row.get('name') == '买入持有基线']
    if len(baselines) != 1:
        raise ValueError('需要唯一买入持有基线，不能默认第一行就是基线')
    baseline = baselines[0]
    differences=[(row['totalReturnPct']-baseline['totalReturnPct'],baseline['maximumDrawdownPct']-row['maximumDrawdownPct']) for row in rows if row is not baseline]
    epsilon=1e-8
    joint=sum(gain>epsilon and reduction>epsilon for gain,reduction in differences)
    if all(gain < -epsilon and reduction>epsilon for gain,reduction in differences):
        headline='本段历史里，本次再平衡方案都以部分收益换来了较低回撤；没有出现收益与回撤同时改善的方案。是否接受这个代价，取决于研究者的风险约束，而非收益排名。'
    elif joint:
        headline=f'本段历史里，有{joint}种输入方案同时提高了扣费后收益、降低了回撤幅度；这只是当前样本结果，不能据此确认未来有效或选出最优策略。'
    elif all(gain < -epsilon and reduction < -epsilon for gain,reduction in differences):
        headline='本段历史里，本次再平衡方案的收益都更低、回撤也更深；当前样本没有显示这些调整的收益或回撤优势。'
    elif all(abs(gain)<=epsilon and abs(reduction)<=epsilon for gain,reduction in differences):
        headline='本段历史里，本次方案未改变收益和回撤表现；调整频率不一定实际触发交易，需要查看执行记录与费用。'
    else:
        headline='本段历史里，本次方案没有同时提高收益并降低回撤的明确优势；收益、回撤和费用应分别对照，不能只凭一项排名判断调整价值。'
    lines = ['# 再平衡历史比较', '', '> '+headline, '',
             '这是保存结果的阅读版，不重新取数或计算。区间：'+str(result.get('start'))+'至'+str(result.get('end'))+'。', '',
             '|方案|扣费后收益%|最大回撤幅度%|累计扣费|', '|---|---:|---:|---:|']
    if isinstance(result.get('periodicRuleExplanation'),str):
        lines[6:6]=[result['periodicRuleExplanation'],'']
    scope=result.get('inputScopeNotes',[])
    if scope:
        if not isinstance(scope,list) or any(not isinstance(note,str) or not note.strip() for note in scope):
            raise ValueError('输入范围说明须为非空文字列表')
        lines[6:6]=['本次资料与执行范围（来自输入声明，尚非独立认证）：',*['- '+note for note in scope],'']
    for row in rows:
        name = str(row.get('name', '未命名')).replace('|', '／').replace('\n', ' ').replace('\r', ' ')
        lines.append(f"|{name}|{row['totalReturnPct']:.2f}|{row['maximumDrawdownPct']:.2f}|{row['totalCost']:.2f}|")
    lines += ['', '## 调整换来了什么']
    for row in rows:
        if row is baseline:
            continue
        gain = row['totalReturnPct']-baseline['totalReturnPct']
        reduction = baseline['maximumDrawdownPct']-row['maximumDrawdownPct']
        name = str(row.get('name','未命名')).replace('\n',' ').replace('\r',' ')
        lines.append(name+'相对买入持有，累计收益'+('提高' if gain>=0 else '降低')+f'{abs(gain):.2f}个百分点，最大回撤幅度'+('减少' if reduction>=0 else '增加')+f'{abs(reduction):.2f}个百分点。这是本段历史的取舍，不证明风险控制在其他区间同样有效。')
    currency = result.get('currency')
    lines += ['', '## 费用与执行的代价', '金额币种：'+currency+'，沿用原计算输入声明。' if isinstance(currency,str) and currency else '金额沿用原计算输入币种，本结果未单独登记币种，不能据此认定为人民币。']
    for row in rows:
        name = str(row.get('name', '未命名')).replace('\n', ' ').replace('\r', ' ')
        lines += ['', '### '+name]
        if isinstance(row.get('explanation'), str):
            lines.append(row['explanation'])
        else:
            lines.append('旧结果未保存费用解释；可读取累计扣费，但未补造分类费用或资金占比。')
        missed = row.get('missed', [])
        if isinstance(missed, list) and missed:
            lines.append(f'有{len(missed)}次计划执行因输入标记的不可成交情形跳过；未标记的限制不等于没有限制。')
    reference=result.get('zeroCostReference')
    if isinstance(reference,dict):
        lines += ['', '## 费用对期末财富的影响',
                  '零摩擦对照只把佣金、价差、滑点和方向税费置零，保留同一历史、权重与执行规则；不是实际可获得的免费交易。费用改变组合余额，也可能改变阈值触发和交易次数，因此期末差不等于累计扣费。',
                  '|方案|实际输入费用下期末金额|零摩擦假设期末金额|零摩擦减原方案期末金额|累计支付成本|', '|---|---:|---:|---:|---:|']
        for row in reference['comparisons']:
            name=str(row['name']).replace('|','／').replace('\n',' ').replace('\r',' ')
            lines.append(f"|{name}|{row['withCostsEndingValue']:.2f}|{row['zeroCostEndingValue']:.2f}|{row['terminalWealthDifference']:.2f}|{row['paidCosts']:.2f}|")
        lines.append('金额差为负时，也不能解释为费用有益；它可能来自阈值或路径改变。此处不拆分单项成本的因果贡献。')
    if isinstance(result.get('assets'),list):
        lines += ['', '## 历史数据来源']
        for asset in result['assets']:
            if isinstance(asset,dict):
                label=(str(asset.get('name') or '')+' '+str(asset.get('code','未登记代码'))).strip().replace('[','').replace(']','').replace('\n',' ').replace('\r',' ')
                url=asset.get('sourceUrl')
                parsed=urlparse(url) if isinstance(url,str) else None
                if parsed and parsed.scheme in ('http','https') and parsed.netloc:
                    lines.append('- ['+label+']('+quote(url,safe=':/?=&%#.-_~')+')')
                else:lines.append('- '+label+'：来源链接未登记或格式不支持')
    study=result.get('segmentStudy')
    if isinstance(study,dict):
        lines += ['', '## 分阶段是否仍然成立', '按指定日期拆分历史，两段各自从相同本金和权重重新起算；不是连续账户，也未证明参数在第二段开始前冻结，因此不称事前样本外验证。',
                  '|历史段|实际区间|买入持有收益%|定期方案收益%|定期方案回撤幅度%|', '|---|---|---:|---:|---:|']
        excess=[]
        for part in study['segments']:
            baseline=part['results'][0];periodic=part['results'][1]
            excess.append(periodic['totalReturnPct']-baseline['totalReturnPct'])
            lines.append(f"|{part['label']}|{part['start']}至{part['end']}|{baseline['totalReturnPct']:.2f}|{periodic['totalReturnPct']:.2f}|{periodic['maximumDrawdownPct']:.2f}|")
        if excess[0]*excess[1]<0:
            lines.append('定期方案相对买入持有的收益优势在两段间换了方向；整段结果掩盖了阶段差异，不能据此认定规则稳定有效。')
        else:
            lines.append('两段对照用于检查阶段差异；即便收益方向相同，也不足以证明未来稳定或排除事后选参。')
    lines += ['', '## 什么还不能下结论',
              '本报告只比较同一历史样本。没有独立样本外验证、参数敏感性和完整A股成交规则验收，不能据此确认策略有效或未来最优。',
              '累计扣费不是相对零成本路径的期末财富差，初始建仓成本未计；研究组合也不等于真实账户。',
              str(result.get('note', '原结果未提供方法说明。')), str(result.get('costBasis', '原结果未登记成本依据。'))]
    return '\n'.join(lines)


def publish(result, out):
    out = Path(out)
    if out.exists():
        raise FileExistsError('请使用新的报告目录')
    body = markdown(result)
    files = {'再平衡历史比较.md': body, '再平衡历史比较.html': render(body, title='再平衡历史比较'),
             'result.json': json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2)}
    manifest = {'files': {name: hashlib.sha256(text.encode('utf-8')).hexdigest() for name, text in files.items()}}
    out.mkdir(parents=True)
    for name, text in files.items():
        (out/name).write_text(text, encoding='utf-8')
    (out/'report-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')


def adjust_input(document, options=None):
    if not isinstance(document,dict):raise ValueError('再平衡输入须为对象')
    document=copy.deepcopy(document)
    options=options or {}
    allowed={'everyObservations','periodicRule','validationSplit','costCounterfactual','commissionPct','minimumCommission','spreadBps','slippageBps'}
    if not isinstance(options,dict) or set(options)-allowed:
        raise ValueError('再平衡修改参数不受支持')
    if 'everyObservations' in options and options.get('periodicRule')=='month-change':
        raise ValueError('观察期频率与月初信号规则不能同时指定')
    if 'everyObservations' in options:
        document['periodicRule']='every-observations'
    for key,value in options.items():
        if key=='costCounterfactual':
            if not isinstance(value,bool):raise ValueError('零摩擦对照参数须为布尔值')
            document[key]=value
            continue
        if key=='validationSplit':
            if not isinstance(value,str) or date.fromisoformat(value).isoformat()!=value:raise ValueError('分段日期须为YYYY-MM-DD')
            document[key]=value
            continue
        if key=='periodicRule':
            if value not in ('every-observations','month-change'):raise ValueError('定期规则不支持')
            document[key]=value
            continue
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:
            raise ValueError('修改参数必须为非负有限数字')
        if key=='everyObservations':
            if not isinstance(value,int) or value<1:raise ValueError('频率须为正整数观察期，不是日历月')
            document[key]=value
        else:
            if not isinstance(document.get('costs'),dict):raise ValueError('先提供明确完整费用输入，不以缺项为零')
            profiles=document.get('costsByCode',{})
            if not isinstance(profiles,dict):raise ValueError('逐资产费用须为对象')
            if any(isinstance(profile,dict) and key in profile for profile in profiles.values()):
                raise ValueError('存在同字段逐资产费用，不能用统一修改隐式覆盖；请明确新费用输入')
            document['costs'][key]=value
    return document


def calculate(document):
    runtime=shutil.which('node')
    if not runtime:
        raise RuntimeError('再平衡计算需要Node.js；安装并加入PATH后可复用本次输入重试')
    raw=json.dumps(document,ensure_ascii=False,allow_nan=False,indent=2)
    with tempfile.TemporaryDirectory(prefix='rebalance-') as directory:
        source=Path(directory)/'input.json';target=Path(directory)/'result.json'
        source.write_text(raw,encoding='utf-8')
        try:
            run=subprocess.run([runtime,str(Path(__file__).with_name('research_analytics_cli.js')),'rebalance',str(source),str(target)],capture_output=True,text=True,encoding='utf-8',timeout=60)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError('再平衡计算超时，未发布研究结果') from error
        if run.returncode:
            raise CalculationError(run.stderr)
        result=json.loads(target.read_text('utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
    return result


def split_documents(document):
    split=document.get('validationSplit')
    if not isinstance(split,str) or date.fromisoformat(split).isoformat()!=split:raise ValueError('分段日期须为YYYY-MM-DD')
    assets=document.get('assets',[])
    if not assets:raise ValueError('分段需要历史资产')
    dates=[row['date'] for row in assets[0]['history']]
    if split not in dates:raise ValueError('分段日期须对应共同历史观察日，不自动移动日期')
    position=dates.index(split)
    if position<3 or len(dates)-position<4:raise ValueError('前后各段至少需要四个价格观察值；不足时不强行分段')
    segments=[]
    for label,start,end in [('前段',0,position+1),('后段',position,len(dates))]:
        part=copy.deepcopy(document);part.pop('validationSplit',None)
        for asset in part['assets']:asset['history']=asset['history'][start:end]
        segments.append((label,part))
    return segments


def publish_input(document, out, options=None):
    """Calculate saved declared assumptions with the existing engine, then publish."""
    if Path(out).exists():raise FileExistsError('请使用新的报告目录')
    document=adjust_input(document,options)
    names={}
    for asset in document.get('assets',[]):
        if isinstance(asset,dict) and 'name' in asset:
            name=asset['name']
            if not isinstance(name,str) or not name.strip() or len(name)>200:raise ValueError('产品名称须为1至200字符非空文字')
            names[asset.get('code')]=name.strip()
    scope=document.get('scopeNotes',[])
    if not isinstance(scope,list) or len(scope)>20 or any(not isinstance(note,str) or not note.strip() or len(note)>2000 for note in scope):
        raise ValueError('研究范围说明须为最多20项非空文字，每项最多2000字符')
    if 'costCounterfactual' in document and not isinstance(document['costCounterfactual'],bool):
        raise ValueError('零摩擦对照参数须为布尔值')
    result=calculate(document)
    if document.get('costCounterfactual'):
        zero=zero_cost_input(document)
        zero_result=calculate(zero)
        matched={row['name']:row for row in zero_result['results']}
        comparisons=[{'name':row['name'],'withCostsEndingValue':row['endingValue'],
                      'zeroCostEndingValue':matched[row['name']]['endingValue'],
                      'terminalWealthDifference':matched[row['name']]['endingValue']-row['endingValue'],
                      'paidCosts':row['totalCost'],'withCostTradeCount':row['tradeCount'],
                      'zeroCostTradeCount':matched[row['name']]['tradeCount']} for row in result['results']]
        result['zeroCostReference']={'type':'same-rule-zero-friction-counterfactual','comparisons':comparisons,'result':zero_result}
    for asset in result['assets']:
        if asset['code'] in names:asset['name']=names[asset['code']]
    if 'validationSplit' in document:
        segments=[]
        for label,part in split_documents(document):
            calculated=calculate(part);calculated['label']=label;segments.append(calculated)
        result['segmentStudy']={'status':'retrospective-split-not-prospective-validation','splitDate':document['validationSplit'],'segments':segments}
    result['inputScopeNotes']=scope
    publish(result,out)
    raw=json.dumps(document,ensure_ascii=False,allow_nan=False,indent=2)
    (Path(out)/'input.json').write_text(raw,encoding='utf-8')
    return result


def zero_cost_input(document):
    zero=copy.deepcopy(document)
    fields=('commissionPct','minimumCommission','spreadBps','slippageBps','buyTaxPct','sellTaxPct')
    zero['costs']={key:0 for key in fields}
    zero['costsByCode']={code:{key:0 for key in fields} for code in document.get('costsByCode',{})}
    zero.pop('costCounterfactual',None)
    return zero


def followup(current, current_input, previous):
    """Compare saved periodic experiments only when all other inputs match."""
    previous=Path(previous).resolve()
    loaded={}
    for name in ('input.json','result.json'):
        source=(previous/name).resolve()
        if not source.is_relative_to(previous) or source.stat().st_size>16*1024*1024:
            raise ValueError('旧输入或结果路径、大小异常')
        raw=source.read_bytes().decode('utf-8-sig')
        loaded[name]=json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=reject_constant)
        if name=='input.json':input_hash=hashlib.sha256(raw.encode('utf-8')).hexdigest()
    old=loaded['result.json'];old_input=loaded['input.json']
    if not isinstance(old_input,dict) or not isinstance(current_input,dict):raise ValueError('前后输入须为对象')
    if not isinstance(old,dict) or old.get('inputSha256')!=input_hash:
        return '# 调整前后比较\n\n旧结果没有匹配当前保存输入的哈希，未作数值对照；本次报告仍可独立阅读。'
    markdown(old)
    adjustable={'everyObservations','periodicRule','costs','costsByCode'}
    unchanged=lambda value:{key:item for key,item in value.items() if key not in adjustable|{'validationSplit','costCounterfactual'}}
    if unchanged(old_input)!=unchanged(current_input):
        return '# 调整前后比较\n\n历史、标的、权重、本金或其他计算条件发生变化，未将收益差解释为费用或频率调整效果。请分别阅读两次研究。'
    def periodic(value):
        candidates=[row for row in value['results'] if row.get('name') in ('定期再平衡','月初信号再平衡')]
        if len(candidates)!=1:raise ValueError('没有唯一可比较的定期方案')
        return candidates[0]
    before=periodic(old);after=periodic(current)
    change=after['totalReturnPct']-before['totalReturnPct']
    reduction=before['maximumDrawdownPct']-after['maximumDrawdownPct']
    fee=after['totalCost']-before['totalCost']
    changed=[key for key in adjustable if old_input.get(key)!=current_input.get(key)]
    summary='本次没有修改费用与频率输入；重算差异不应自动解释为策略改善。' if not changed else '同一历史与组合条件下，本次修改了费用或频率；下面展示两次定期方案的取舍。'
    def schedule(value):
        if value.get('periodicRule')=='month-change':return '月初观察日形成信号'
        return '每'+str(value.get('everyObservations',12))+'个观察期形成信号'
    parameters=['|参数|上次|本次|','|---|---|---|', '|频率|'+schedule(old_input)+'|'+schedule(current_input)+'|']
    for key,label in [('commissionPct','统一佣金%'),('minimumCommission','每腿最低佣金'),('spreadBps','全价差bp'),('slippageBps','每腿滑点bp')]:
        parameters.append('|'+label+'|'+str(old_input.get('costs',{}).get(key,'未登记'))+'|'+str(current_input.get('costs',{}).get(key,'未登记'))+'|')
    return '\n'.join(['# 调整前后比较','', '> '+summary,'',
        '相对上次定期方案，累计收益'+('提高' if change>=0 else '降低')+f'{abs(change):.2f}个百分点，最大回撤幅度'+('减少' if reduction>=0 else '增加')+f'{abs(reduction):.2f}个百分点；累计模型扣费'+('增加' if fee>=0 else '减少')+f'{abs(fee):.2f}。','',
        '费用和频率同时改变时，不能把全部差异归因于其中一个因素。结果来自保存的研究输入，不等于真实账户或未来改善。','',
        *parameters,'','若有逐资产费用，统一费用表不能代替逐资产成本底稿。'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('result')
    parser.add_argument('--out-dir', required=True)
    args = parser.parse_args()
    source = Path(args.result)
    if source.stat().st_size > 16*1024*1024:
        raise ValueError('结果文件超过阅读入口大小限制')
    publish(json.loads(source.read_text('utf-8-sig'), object_pairs_hook=unique_pairs, parse_constant=reject_constant), args.out_dir)
