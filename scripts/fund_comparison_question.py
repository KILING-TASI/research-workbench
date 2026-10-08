"""Answer bounded historical risk questions using the same comparison calculation."""
from fund_comparison_brief import report
import hashlib,json
from pathlib import Path

ANSWER_FILES=('风险追问.json','风险追问.md','风险追问.html')

def register(directory,saved_at):
    root=Path(directory)
    methods=json.loads((root/'comparison/report-manifest.json').read_text('utf-8'))['methodFiles']
    methods[Path(__file__).name]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest={'artifactType':'fund-risk-question','primaryReport':'风险追问.html','savedAt':saved_at,
              'inputSha256':hashlib.sha256((root/'comparison/input.json').read_bytes()).hexdigest(),
              'files':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ANSWER_FILES},
              'methodFiles':methods,'sourceVerification':'not-verified','visualReview':'not-performed'}
    (root/'report-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')

def verify_saved(directory,manifest):
    root=Path(directory).resolve();issues=[]
    if not isinstance(manifest.get('files'),dict) or set(manifest['files'])!=set(ANSWER_FILES):return ['追问文件登记不完整']
    for name in ANSWER_FILES+('comparison/input.json',):
        path=root/name
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root) or path.stat().st_size>16*1024*1024:
            issues.append('追问文件缺失或路径异常：'+name);continue
        expected=manifest.get('inputSha256') if name=='comparison/input.json' else manifest['files'][name]
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:issues.append('保存后内容发生变化：'+name)
    return issues

def answer(document,kind):
    if kind not in ('stability','volatility','drawdown'):raise ValueError('不支持的比较追问')
    result=report(document)[0];rows=result['rows']
    names={r['code']:str(r.get('name') or r['code']).replace('\n',' ').replace('|','／') for r in document['rows']}
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
    body='# 哪只更稳，要分开看\n\n> '+conclusion+'\n\n'
    body+='本次仅回答'+result['start']+'至'+result['end']+'共同历史区间的问题，保留上次标的与参数，不更新资料。\n\n'
    body+='|标的|日常波动（年化）|最深下跌（最大回撤）|\n|---|---:|---:|\n'
    for r in rows:
        value='未计算' if r.get('annualizedVolPct') is None else f"{r['annualizedVolPct']:.2f}%"
        body+='|'+names[r['code']]+'|'+value+'|'+f"{r['drawdownPct']:.2f}%"+'|\n'
    body+='\n日常波动描述涨跌起伏，最大回撤描述从高点到低点的最深跌幅；两者不是同一件事。年化波动沿用原报告的频率与年化假设。\n\n'
    body+='缺少合同基准、持仓与完整分红核验时，不能解释全部风险来源。持有体验还受买入日期、资金用途、费用与个人承受能力影响；本回答不是买卖建议，也不是未来风险保证。资料来源和计算口径见本次完整比较报告。\n'
    return data,body
