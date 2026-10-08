"""Isolated bundled BSE scenario adapter, preserving inputs for follow-up."""
import copy,json,subprocess,sys,tempfile
from decimal import Decimal,InvalidOperation
from pathlib import Path


def adjust(spec,budget=None):
    if not isinstance(spec,dict) or not isinstance(spec.get('allocation'),dict):raise ValueError('北交情景需明确发行与资金输入')
    result=copy.deepcopy(spec)
    if budget is not None:
        if isinstance(budget,bool):raise ValueError('预算不能为布尔值')
        try:value=Decimal(str(budget))
        except InvalidOperation as error:raise ValueError('预算须为人民币元金额') from error
        if not value.is_finite() or value<0 or value*100!=(value*100).to_integral_value():raise ValueError('预算须非负有限金额，最多两位小数，单位元')
        result['allocation']['budget']=str(value)
    return result


def publish(spec,out,budget=None):
    from collection_validation import unique_pairs,reject_constant
    out=Path(out)
    if out.exists():raise FileExistsError('输出已存在，请另存报告')
    spec=adjust(spec,budget)
    script=Path(__file__).resolve().parents[1]/'modules/bjx-newshare-toolkit/scripts/subscription_scenarios.py'
    with tempfile.TemporaryDirectory(prefix='bjx-scenarios-') as directory:
        source=Path(directory)/'input.json';source.write_text(json.dumps(spec,ensure_ascii=False,allow_nan=False),'utf-8')
        try:run=subprocess.run([sys.executable,str(script),str(source),'--out-dir',str(out)],capture_output=True,text=True,encoding='utf-8',timeout=60)
        except subprocess.TimeoutExpired as error:raise RuntimeError('北交情景计算超时，本次未认证成功结果') from error
        if run.returncode:raise ValueError('北交情景未完成：请核对公告价格与上限、资金日期、配售/涨跌幅情景依据及权重；没有自动放宽条件。')
    result=json.loads((out/'result.json').read_text('utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
    body=(out/'北交所资金与收益情景.md').read_text('utf-8')
    return result,body.split('\n')[2].removeprefix('> ')
