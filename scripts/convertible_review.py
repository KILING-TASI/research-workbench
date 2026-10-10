"""Deterministic convertible cash-flow scenarios; no option or trade advice."""
import argparse
import datetime as dt
import json
import math
import hashlib
from pathlib import Path
from collection_validation import unique_pairs, reject_constant, finite_json_float, day


def number(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name}须为有限数值')
    try:value=float(value)
    except OverflowError as error:raise ValueError(f'{name}超出可计算范围') from error
    if not math.isfinite(value):raise ValueError(f'{name}须为有限数值')
    if positive and value <= 0:
        raise ValueError(f'{name}须大于零')
    return float(value)


def checked_cashflows(cf):
    if not isinstance(cf,(list,tuple)) or not cf or len(cf)>1000:
        raise ValueError('需要明确的未来现金流')
    if any(not isinstance(row,(list,tuple)) or len(row)!=2 for row in cf):
        raise ValueError('现金流须为时间与金额的二元序列')
    return flows([{'year':row[0],'amount':row[1]} for row in cf])


def flows(rows):
    if not isinstance(rows, list) or not rows or len(rows) > 1000:
        raise ValueError('需要明确的未来现金流')
    if any(not isinstance(r,dict) for r in rows):
        raise ValueError('现金流每行须为对象')
    result = [(number(r['year'], 'year', True), number(r['amount'], 'amount', True)) for r in rows]
    if any(t > 100 for t,a in result):
        raise ValueError('基础诊断仅接受100年内的现金流')
    if any(b[0] <= a[0] for a, b in zip(result, result[1:])):
        raise ValueError('现金流时间须严格递增；同日金额先合并')
    return result


def present_value(cf, rate):
    # Log-rate avoids a root search arbitrarily limited to positive yields.
    cf=checked_cashflows(cf);rate=number(rate,'贴现收益率')
    if rate<=-1:raise ValueError('贴现收益率须大于-100%')
    x = math.log1p(rate)
    try:
        return math.fsum(amount * math.exp(-year * x) for year, amount in cf)
    except OverflowError:
        return math.inf


def yield_rate(cf, price):
    cf=checked_cashflows(cf);price=number(price,'全价',True)
    lo, hi = -1.0, 1.0
    def pv(x):
        try:
            return math.fsum(a * math.exp(-t*x) for t, a in cf)
        except OverflowError:
            return math.inf
    for _ in range(1024):
        if pv(lo)>=price:break
        lo *= 2
    else:raise ValueError('收益率无法在可表示区间内求解')
    for _ in range(1024):
        if pv(hi)<=price:break
        hi *= 2
    else:raise ValueError('收益率无法在可表示区间内求解')
    for _ in range(180):
        mid = (lo + hi) / 2
        if pv(mid) > price:
            lo = mid
        else:
            hi = mid
    try:
        result = math.expm1((lo + hi) / 2)
    except OverflowError as exc:
        raise ValueError('收益率超出可表示范围') from exc
    if result <= -1 or not math.isfinite(result):
        raise ValueError('收益率超出可表示范围')
    return result


def rolling_clause(rows, window, required, ratio, direction):
    if isinstance(window, bool) or not isinstance(window, int) or not 1 <= window <= 365:
        raise ValueError('window须为1至365的交易日数量')
    if isinstance(required, bool) or not isinstance(required, int) or not 1 <= required <= window:
        raise ValueError('required须在窗口范围内')
    ratio=number(ratio, 'ratio', True)
    if direction not in ('above', 'below'):
        raise ValueError('direction须为above或below，含等号')
    if not isinstance(rows,list) or not rows or len(rows) > 10000 or any(not isinstance(row,dict) for row in rows):
        raise ValueError('需要条款观察序列')
    hits, output, previous = [], [], None
    for row in rows:
        date = day(row['date'])
        if previous is not None and date <= previous:
            raise ValueError('观察日期须严格递增')
        previous = date
        stock = number(row['stockPrice'], 'stockPrice', True)
        conversion = number(row['conversionPrice'], 'conversionPrice', True)
        boundary=number(conversion*ratio,'条款价格线',True)
        hit = stock >= boundary if direction == 'above' else stock <= boundary
        hits.append(hit)
        recent = hits[-window:]
        output.append({'date':date.isoformat(), 'hits':sum(recent), 'observations':len(recent),
                       'status': 'insufficient-window' if len(recent)<window else
                       ('condition-met' if sum(recent)>=required else 'condition-not-met')})
    return output


def calculate(spec):
    if not isinstance(spec,dict):
        raise ValueError('输入须为对象')
    currency=spec.get('currency')
    if not isinstance(currency,str) or len(currency)!=3 or not currency.isascii() or not currency.isalpha() or not currency.isupper():
        raise ValueError('须明确三字母币种；价格与现金流须同币种、同面值单位')
    if not isinstance(spec.get('source'), str) or not spec['source'].strip():
        raise ValueError('须注明现金流、价格和条款的输入来源')
    cf = flows(spec['cashFlows'])
    price = number(spec['fullPrice'], '含应计利息的全价', True)
    face = number(spec['faceValue'], 'faceValue', True)
    stock = number(spec['stockPrice'], 'stockPrice', True)
    conversion = number(spec['conversionPrice'], 'conversionPrice', True)
    rate = number(spec['discountYield'], 'discountYield')
    if rate <= -1:
        raise ValueError('贴现收益率须大于-100%')
    floor = present_value(cf, rate)
    if not math.isfinite(floor) or floor <= 0:
        raise ValueError('纯债现值超出可计算范围')
    try:
        parity = face*stock/conversion
        pv_rows=[a*math.exp(-t*math.log1p(rate)) for t,a in cf]
        duration = math.fsum(t*p for (t,a),p in zip(cf,pv_rows))/floor/(1+rate)
        convexity = math.fsum(t*(t+1)*p for (t,a),p in zip(cf,pv_rows))/floor/(1+rate)**2
    except (OverflowError,ZeroDivisionError) as error:
        raise ValueError('输入造成敏感度超出可计算范围') from error
    if not all(math.isfinite(x) for x in (parity,duration,convexity)) or parity<=0:
        raise ValueError('输入造成敏感度或转股价值超出可计算范围')
    scenarios = [{'label':'持有到期并按约兑付', 'yieldPct':yield_rate(cf, price)*100}]
    exits=spec.get('exitScenarios', [])
    if not isinstance(exits,list) or len(exits)>30 or any(not isinstance(r,dict) for r in exits):
        raise ValueError('退出情景须为最多30项的对象列表')
    for row in exits:
        if not isinstance(row.get('label'),str) or not row['label'].strip() or '\n' in row['label'] or '\r' in row['label']:
            raise ValueError('退出情景名称须为非空单行文字')
        if row.get('eligibility') != 'confirmed' or not isinstance(row.get('basis'),str) or not row['basis'].strip():
            raise ValueError('退出情景须明确适用依据，未确认不能计算最差收益率')
        scenarios.append({'label':str(row['label']), 'yieldPct':yield_rate(flows(row['cashFlows']),price)*100,
                          'basis':row['basis']})
    result = {'source':spec['source'], 'currency':currency,'bondPresentValue':floor, 'conversionValue':parity,
              'bondPremiumPct':(price/floor-1)*100, 'conversionPremiumPct':(price/parity-1)*100,
              'modifiedDuration':duration, 'convexity':convexity, 'dv01':floor*duration*.0001,
              'yieldScenarios':scenarios, 'minimumSuppliedScenarioYieldPct':min(x['yieldPct'] for x in scenarios),
              'scope':'现金流情景与给定条款观察，不含转股期权、违约或完整最差收益定价'}
    if 'clause' in spec:
        clause = spec['clause']
        if not isinstance(clause,dict):raise ValueError('条款须为对象')
        if clause.get('tradingDaysComplete') is not True or not clause.get('basis'):
            raise ValueError('条款计数须确认交易日序列完整并提供条款依据')
        result['clauseObservations'] = rolling_clause(clause['observations'],clause['window'],
                                                     clause['required'],clause['ratio'],clause['direction'])
    if spec.get('exampleType') is not None:
        if spec['exampleType']!='teaching-only':raise ValueError('未知示例类型')
        result['exampleType']='teaching-only'
    for key,value in result.items():
        if isinstance(value,(int,float)):number(value,key)
    for row in scenarios:number(row['yieldPct'],'情景年化收益率')
    return result


def publish(spec, out):
    result = calculate(spec)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    y = result['yieldScenarios'][0]['yieldPct']
    judgement = ('持有到期未必能收回当前买入成本。' if y < -1e-10 else '按输入现金流持有到期有正收益，但前提是按约兑付。' if y>1e-10 else '按输入现金流持有到期大致持平，尚未扣除费用与税。')
    text = f'# 可转债基础诊断\n\n{judgement} 税前到期年化收益率为{y:.2f}%。这不包含转股带来的收益，也不保证发行人兑付。\n\n'
    if result.get('exampleType')=='teaching-only':text+='本页为教学假设，不是真实标的或报价。\n\n'
    text+=f'金额币种：{result["currency"]}；价格与全部现金流按同一面值单位比较。\n\n'
    text += f"当前转股价值为{result['conversionValue']:.2f}，转股溢价率为{result['conversionPremiumPct']:.2f}%。这说明转债价格与即时转股价值的距离，不能单凭溢价判断贵便宜。\n\n"
    text += f"按给定贴现收益率计算，纯债现值为{result['bondPresentValue']:.2f}。它是模型估值，不是保本线；信用恶化时也会下降。\n\n"
    text += '## 退出情景\n\n| 情景 | 税前年化收益率 |\n|---|---:|\n'
    text += ''.join(f"| {s['label'].replace('|','/')} | {s['yieldPct']:.2f}% |\n" for s in result['yieldScenarios'])
    text += '\n仅比较已提供且确认适用的现金流，不声称涵盖全部回售、强赎或最差退出结果。\n'
    if 'clauseObservations' in result:
        row = result['clauseObservations'][-1]
        state={'insufficient-window':'窗口资料尚不完整','condition-met':'价格条件已满足','condition-not-met':'价格条件尚未满足'}[row['status']]
        text += f"\n最新窗口有{row['observations']}个观察日，其中{row['hits']}天满足价格条件。{state}。条件满足不等于发行人决定执行，仍需核对公告、适用期间与其他条件。\n"
    text += '\n## 本次还不能判断什么\n\n不含期权价值、信用违约概率、税后收益、实时流动性和买卖建议。交易日完整性由输入声明，尚未联网核验。\n\n来源：'+spec['source']+'\n'
    (out/'可转债基础诊断.md').write_text(text,encoding='utf-8')
    from research_brief_html import render
    (out/'可转债基础诊断.html').write_text(render(text,'可转债基础诊断'),encoding='utf-8')
    for name,value in [('input.json',spec),('result.json',result)]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (out/'research-request.json').write_text(json.dumps({'command':'convertible'},ensure_ascii=False),encoding='utf-8')
    (out/'report-manifest.json').write_text(json.dumps({'primaryReport':'可转债基础诊断.html',
        'savedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'files':{name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in ['可转债基础诊断.html','可转债基础诊断.md','input.json','result.json','research-request.json']}},ensure_ascii=False),encoding='utf-8')
    return result


if __name__ == '__main__':
    import sys
    from cli_text import configure
    configure()
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('--out-dir',required=True)
    args=parser.parse_args()
    try:
        p=Path(args.input)
        if p.stat().st_size>16*1024*1024:raise ValueError('输入文件过大')
        result=publish(json.loads(p.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float),args.out_dir)
        print('已生成可转债现金流与给定条款的基础诊断。',file=sys.stderr)
        print('结果目录：'+str(Path(args.out_dir).resolve()),file=sys.stderr)
        print('先打开：'+str((Path(args.out_dir)/'可转债基础诊断.html').resolve()),file=sys.stderr)
        print('也可阅读同目录的可转债基础诊断.md。',file=sys.stderr)
        if result.get('exampleType')=='teaching-only':print('本次为教学假设，不是真实标的或报价。',file=sys.stderr)
    except FileExistsError:
        parser.exit(1,'输出目录已经存在，请换一个新名字；旧报告没有覆盖。\n')
    except FileNotFoundError:
        parser.exit(1,'找不到输入文件，请核对命令中的第一个文件路径。\n')
    except OSError:
        parser.exit(1,'文件读取或写入未完成，请检查目录及读写权限。\n')
    except (ValueError,KeyError,TypeError):
        parser.exit(1,'输入未通过检查，请核对 fullPrice、faceValue、currency、cashFlows 的时间与金额及条款字段；可对照 references/examples/convertible-review-example.json。\n')
