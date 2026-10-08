"""Repeat an annual scenario from saved inputs without fetching new assumptions."""
import argparse,json,subprocess,sys,tempfile
from decimal import Decimal,InvalidOperation
from pathlib import Path
from collection_validation import unique_pairs,reject_constant,finite_json_float
from research_brief_html import render

def comparison(previous,current):
    if previous.get('status')=='blocked-eligibility' or current.get('status')=='blocked-eligibility':return '权限条件未确认，不进行前后收益比较。\n'
    before=previous['scenarios']['neutral'];after=current['scenarios']['neutral']
    delta=after['annualNet']-before['annualNet'];points=(after['annualCumulativeRate']-before['annualCumulativeRate'])*100
    text=f"在同一组中性假设下，年度净收益由{before['annualNet']:,.2f}元变为{after['annualNet']:,.2f}元，变化{delta:+,.2f}元；年度累计收益率变化{points:+.2f}个百分点。不是新增市场预测。\n\n"
    text+='|项目|原资金规模|新资金规模|\n|---|---:|---:|\n'
    text+=f"|全部客户资金|{previous['capital']:,.2f}元|{current['capital']:,.2f}元|\n|可用资金|{previous['availableCapital']:,.2f}元|{current['availableCapital']:,.2f}元|\n"
    for label,key,unit in [('中性模拟申购额','subscriptionAmount','元'),('期望比例获配手数','expectedHands','手'),('每只资金成本','fundCost','元')]:
        text+=f"|{label}|{before['atAvailableCap'][key]:,.2f}{unit}|{after['atAvailableCap'][key]:,.2f}{unit}|\n"
    unused=current['availableCapital']-after['atAvailableCap']['subscriptionAmount']
    text+=f'\n新规模下中性情景有{unused:,.2f}元可用资金未进入模拟申购额，可能来自申购上限或整手取整。收益率分母仍是全部客户资金，未加入闲置资金的回购收入；不能把这张表当作全账户总收益。\n'
    text+='\n前后均按当前计算版本重算原输入，避免旧结果的口径变化混入本金变化；保留旧报告。本次仅比例获配，余股未知，也未验证全年资金窗口能否重复参与。\n'
    return text

def repeat(previous,out,capital):
    previous=Path(previous).resolve();out=Path(out)
    if out.exists():raise FileExistsError('请使用新的报告目录，不覆盖旧报告')
    source=(previous/'input.json').resolve()
    if not source.is_relative_to(previous) or source.stat().st_size>1024*1024:raise ValueError('上次输入路径或大小异常')
    spec=json.loads(source.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
    if not isinstance(spec,dict) or not isinstance(spec.get('scenarios'),dict) or 's_capital' not in spec:raise ValueError('请选择北交年度情景报告，不能复用其他研究输入')
    if isinstance(capital,bool):raise ValueError('资金规模不能是布尔值')
    try:value=Decimal(str(capital))
    except InvalidOperation as error:raise ValueError('资金规模需为人民币元') from error
    if not value.is_finite() or value<=0 or value*100!=(value*100).to_integral_value():raise ValueError('资金规模需为正数，最多两位小数')
    original=dict(spec);old=spec['s_capital'];spec['s_capital']=str(value)
    script=Path(__file__).resolve().parents[1]/'modules/bjx-newshare-toolkit/scripts/annual_yield.py'
    with tempfile.TemporaryDirectory(prefix='bjx-annual-followup-') as directory:
        original_path=Path(directory)/'original.json';original_path.write_text(json.dumps(original,ensure_ascii=False,allow_nan=False),'utf-8')
        original_out=Path(directory)/'original-result'
        prior_run=subprocess.run([sys.executable,str(script),str(original_path),'--out-dir',str(original_out)],capture_output=True,text=True,encoding='utf-8',timeout=60)
        if prior_run.returncode:raise ValueError('旧输入不能按当前口径重算，未强行比较资金变化')
        previous_result=json.loads((original_out/'result.json').read_text('utf-8'))
        path=Path(directory)/'input.json';path.write_text(json.dumps(spec,ensure_ascii=False,allow_nan=False),'utf-8')
        run=subprocess.run([sys.executable,str(script),str(path),'--out-dir',str(out)],capture_output=True,text=True,encoding='utf-8',timeout=60)
        if run.returncode:raise ValueError('重算未完成，请核对可用资金、权限及原先参数；未放宽条件')
    result=json.loads((out/'result.json').read_text('utf-8'))
    note=f'# 本次资金规模调整\n\n资金规模从{old}元改为{value}元。市场假设、费用、资料日期、权限声明和在途资金沿用原输入，没有取得最新市场或账户资料。\n\n'
    if result['status']=='blocked-eligibility':note+='权限条件尚未确认，本次没有计算收益。\n'
    else:note+=comparison(previous_result,result)
    (out/'资金调整说明.md').write_text(note,'utf-8')
    (out/'资金调整说明.html').write_text(render(note,'资金调整前后对照'),'utf-8')
    manifest=out/'report-manifest.json';data=json.loads(manifest.read_text('utf-8'));data['files']['资金调整说明.md']=None;data['files']['资金调整说明.html']=None;manifest.write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
    return result

if __name__=='__main__':
    from cli_text import configure
    configure()
    parser=argparse.ArgumentParser();parser.add_argument('--continue-from',required=True);parser.add_argument('--capital',required=True);parser.add_argument('--out-dir',required=True);args=parser.parse_args()
    repeat(args.continue_from,args.out_dir,args.capital)
