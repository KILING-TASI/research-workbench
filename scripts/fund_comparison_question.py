"""Answer bounded historical return and risk questions using the same comparison calculation."""
from fund_comparison_brief import report
import hashlib,json
from pathlib import Path

ANSWER_FILES=('风险追问.json','风险追问.md','风险追问.html')
PERFORMANCE_FILES=('收益追问.json','收益追问.md','收益追问.html')

def register(directory,saved_at,performance=False):
    root=Path(directory)
    files=PERFORMANCE_FILES if performance else ANSWER_FILES
    methods=json.loads((root/'comparison/report-manifest.json').read_text('utf-8'))['methodFiles']
    methods[Path(__file__).name]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest={'artifactType':'fund-performance-question' if performance else 'fund-risk-question','primaryReport':files[2],'savedAt':saved_at,
              'inputSha256':hashlib.sha256((root/'comparison/input.json').read_bytes()).hexdigest(),
              'files':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files},
              'methodFiles':methods,'sourceVerification':'not-verified','visualReview':'not-performed'}
    (root/'report-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')

def verify_saved(directory,manifest):
    root=Path(directory).resolve();issues=[]
    files=PERFORMANCE_FILES if manifest.get('artifactType')=='fund-performance-question' else ANSWER_FILES
    if not isinstance(manifest.get('files'),dict) or set(manifest['files'])!=set(files):return ['追问文件登记不完整']
    for name in files+('comparison/input.json',):
        path=root/name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size>16*1024*1024:
            issues.append('追问文件缺失或路径异常：'+name);continue
        expected=manifest.get('inputSha256') if name=='comparison/input.json' else manifest['files'][name]
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:issues.append('保存后内容发生变化：'+name)
    return issues

def answer(document,kind):
    if kind not in ('stability','volatility','drawdown','return','return-risk'):raise ValueError('不支持的比较追问')
    return answer_from_result(document,kind,report(document)[0])


def answer_from_result(document,kind,result):
    rows=result['rows']
    names={r['code']:str(r.get('name') or r['code']).replace('\n',' ').replace('|','／') for r in document['rows']}
    if kind=='return-risk':
        performance,performance_body=answer_from_result(document,'return',result)
        risk,risk_body=answer_from_result(document,'stability',result)
        overlap=set(performance['highestReturnCodes']) & set(risk['smallestDrawdownCodes']) & set(risk['lowestVolatilityCodes'])
        if risk['missingVolatilityCodes']:judgment='资料还不足以完整比较“收益更好又更稳”：存在波动率缺值，不能排除这些标的后选赢家。'
        elif overlap:judgment='在本段历史的区间收益、最大回撤与年化波动三项中，'+ '、'.join(names[c] for c in performance['highestReturnCodes'] if c in overlap)+'同时处在最优位置；这仍不是完整产品评价。'
        else:judgment='这段历史没有一只在收益、回撤和波动三项上同时领先，需要分开看收益与风险的取舍。'
        return_names='、'.join(names[c] for c in performance['highestReturnCodes'])
        calm_names='、'.join(names[c] for c in risk['lowestVolatilityCodes']) if not risk['missingVolatilityCodes'] else '资料不足，暂不完整排名'
        drawdown_names='、'.join(names[c] for c in risk['smallestDrawdownCodes'])
        conclusion=judgment+'收益较高：'+return_names+'；波动较小：'+calm_names+'；回撤较小：'+drawdown_names+'。这里只比较三项历史指标，不代表未来或个人适合程度。'
        data={'questionType':kind,'conclusion':conclusion,'start':result['start'],'end':result['end'],'jointLeaderCodes':sorted(overlap),'returnAnswer':performance,'riskAnswer':risk,'scope':'three historical metrics; not full suitability or future ranking'}
        body='# 收益和风险一起看'+chr(10)*2+'> '+conclusion+chr(10)*2+'## 收益怎么看'+chr(10)*2+performance_body.split(chr(10)*2,1)[1]+chr(10)*2+'## 风险怎么看'+chr(10)*2+risk_body.split(chr(10)*2,1)[1]
        return data,body
    if kind=='return':
        maximum=max(r['totalReturnPct'] for r in rows)
        winners=[r['code'] for r in rows if r['totalReturnPct']==maximum]
        label='、'.join(names[c] for c in winners)
        if maximum<0:conclusion=label+'在这段历史里亏得较少，收益率为'+f'{maximum:.2f}%'+'；比较池全部亏损，不能说它“赚得最多”。'
        elif maximum==0:conclusion=label+'的区间收益最高，为0.00%；它没有盈利，其余标的收益不高于零。'
        else:conclusion=label+'的区间收益'+('并列最高' if len(winners)>1 else '最高')+'，为'+f'{maximum:+.2f}%'+'。'
        if len(winners)==1:
            leader=next(row for row in rows if row['code']==winners[0])
            shallowest=min(abs(row['drawdownPct']) for row in rows)
            if abs(leader['drawdownPct'])>shallowest:
                conclusion+='但它的最大回撤幅度为'+f"{abs(leader['drawdownPct']):.2f}%"+'，比比较池中最小的'+f'{shallowest:.2f}%'+'更深。'
            if all(row.get('annualizedVolPct') is not None for row in rows):
                calmest=min(row['annualizedVolPct'] for row in rows)
                if leader['annualizedVolPct']>calmest:
                    conclusion+='它的年化波动为'+f"{leader['annualizedVolPct']:.2f}%"+'，高于比较池中最小的'+f'{calmest:.2f}%'+'。'
        conclusion+='收益最高不等于风险最低，也不说明未来会继续领先。'
        data={'questionType':kind,'conclusion':conclusion,'start':result['start'],'end':result['end'],'highestReturnCodes':winners,'rows':rows,'scope':'saved-common-history; not account profit or complete evaluation'}
        body='# 哪只收益更好\n\n> '+conclusion+'\n\n本次比较'+result['start']+'至'+result['end']+'共同历史区间，沿用保存资料，不更新行情。\n\n|标的|区间收益|最大回撤|\n|---|---:|---:|\n'
        for row in rows:body+='|'+names[row['code']]+'|'+f"{row['totalReturnPct']:+.2f}%"+'|'+f"{row['drawdownPct']:.2f}%"+'|\n'
        if result.get('requestedStart') and result['requestedStart']!=result['start']:
            body+='原请求起点为'+str(result['requestedStart'])+'，可比较数据实际从'+result['start']+'开始；不据此猜测日期差异的原因。'+chr(10)+chr(10)
        body+='\n这些是原净值序列及其分红口径下的历史结果，不是你的个人持有收益；费用、币种、分红完整性与资料缺口沿用完整比较报告说明。没有基准与归因资料，不能据此判断经理能力。本回答不构成买卖建议。\n'
        return data,body
    dd=min(abs(r['drawdownPct']) for r in rows)
    defensive=[r['code'] for r in rows if abs(r['drawdownPct'])==dd]
    missing=[r['code'] for r in rows if r.get('annualizedVolPct') is None]
    calm=[]
    if not missing:
        vol=min(r['annualizedVolPct'] for r in rows)
        calm=[r['code'] for r in rows if r['annualizedVolPct']==vol]
    def label(codes):return '、'.join(names[c] for c in codes)
    drawdown=label(defensive)+'的区间最大回撤幅度'+('并列最小' if len(defensive)>1 else '最小')+'，为'+f'{dd:.2f}%'+ '。'
    volatility=('缺少可比较的年化波动：'+label(missing)+'；不排除这些标的后给整个池排名。' if missing else label(calm)+'的年化波动'+('并列最小' if len(calm)>1 else '最小')+'，为'+f'{vol:.2f}%'+'。')
    if kind=='drawdown':conclusion=drawdown+'这只说明本段历史最深的下跌较小，不等于未来更安全。'
    elif kind=='volatility':conclusion=volatility+'日常涨跌较小不等于不会出现较深回撤。'
    elif missing:conclusion=drawdown+'但'+volatility+'目前不能完整回答“哪只更稳”。'
    elif set(calm)!=set(defensive):conclusion='“更稳”在这里有两种答案：'+volatility+drawdown+'两项指向不同，不能给出统一的稳健排名。'
    else:conclusion=volatility+drawdown+'在这两项历史指标上较稳，但还不是完整风险评价。'
    data={'questionType':kind,'conclusion':conclusion,'start':result['start'],'end':result['end'],'smallestDrawdownCodes':defensive,'lowestVolatilityCodes':calm,'missingVolatilityCodes':missing,
          'rows':[{k:r.get(k) for k in ('code','drawdownPct','annualizedVolPct','observationCount')} for r in rows],
          'scope':'saved-common-history; not future risk or personal suitability'}
    title={'stability':'哪只更稳，要分开看','volatility':'哪只日常波动更小','drawdown':'哪只历史回撤更小'}[kind]
    body='# '+title+'\n\n> '+conclusion+'\n\n'
    body+='本次仅回答'+result['start']+'至'+result['end']+'共同历史区间的问题，保留上次标的与参数，不更新资料。\n\n'
    if result.get('requestedStart') and result['requestedStart']!=result['start']:
        body+='原请求起点为'+str(result['requestedStart'])+'，可比较数据实际从'+result['start']+'开始；不据此猜测日期差异的原因。'+chr(10)+chr(10)
    body+='|标的|日常波动（年化）|最深下跌（最大回撤）|\n|---|---:|---:|\n'
    for r in rows:
        value='未计算' if r.get('annualizedVolPct') is None else f"{r['annualizedVolPct']:.2f}%"
        body+='|'+names[r['code']]+'|'+value+'|'+f"{r['drawdownPct']:.2f}%"+'|\n'
    body+='\n日常波动描述涨跌起伏，最大回撤描述从高点到低点的最深跌幅；两者不是同一件事。年化波动沿用原报告的频率与年化假设。\n\n'
    body+='缺少合同基准、持仓与完整分红核验时，不能解释全部风险来源。持有体验还受买入日期、资金用途、费用与个人承受能力影响；本回答不是买卖建议，也不是未来风险保证。资料来源和计算口径见本次完整比较报告。\n'
    return data,body
