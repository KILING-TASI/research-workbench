"""Comparable observed returns; no reconstructed accounts or causal attribution."""
import argparse
import json
from pathlib import Path
from portfolio_cashflow_review import calculate as account_returns, number
from research_brief_html import render


def calculate(spec):
    if not isinstance(spec, dict):
        raise ValueError('输入须为对象')
    if set(spec) - {'inputSchema', 'methodVersion', 'exampleType', 'account', 'comparisonBasis', 'product', 'benchmark', 'effectEvidence'}:
        raise ValueError('未知输入字段，不能忽略后继续计算')
    if 'inputSchema' in spec and spec['inputSchema'] != 'account-benchmark-observation-v1':
        raise ValueError('未知输入schema，须显式转换')
    if 'methodVersion' in spec and spec['methodVersion'] != 'account-benchmark-observation-1':
        raise ValueError('方法版本不支持，不能静默改用本轮方法')
    if spec.get('exampleType') != 'teaching-only':
        raise ValueError('本批入口仅验收教学输入，未恢复真实账户验收')
    account = spec['account']
    observed = account_returns(account)
    basis = spec['comparisonBasis']
    if basis.get('dividends') not in ('reinvested', 'cash-included'):
        raise ValueError('须声明分红再投或现金分红计入总资产')
    if not isinstance(basis.get('benchmarkVersion'), str) or not basis['benchmarkVersion'].strip():
        raise ValueError('基准版本缺失')
    rows = []
    for kind in ('product', 'benchmark'):
        item = spec[kind]
        for key, expected in [('start', observed['start']), ('end', observed['end']),
                              ('currency', account['currency']), ('dividends', basis['dividends'])]:
            if item.get(key) != expected:
                raise ValueError('比较口径不一致：' + key)
        if not isinstance(item.get('source'), str) or not item['source'].strip():
            raise ValueError('比较序列须保留来源')
        if kind == 'benchmark' and item.get('version') != basis['benchmarkVersion']:
            raise ValueError('基准版本不一致')
        series = item['totalValueSeries']
        if not isinstance(series, list) or not 2 <= len(series) <= 20000:
            raise ValueError('总回报序列不足')
        from datetime import date
        days = [x['date'] for x in series]
        if any(date.fromisoformat(d).isoformat() != d for d in days) or days != sorted(set(days)):
            raise ValueError('日期重复或乱序')
        if days[0] != observed['start'] or days[-1] != observed['end']:
            raise ValueError('序列未覆盖共同区间')
        values = [number(x['value']) for x in series]
        if any(x <= 0 for x in values):
            raise ValueError('总回报序列须为正数')
        cumulative = number((values[-1] / values[0] - 1) * 100)
        rows.append(dict(kind=kind, cumulativeReturnPct=cumulative,
                         source=item['source']))
    if account.get('dividends') != basis['dividends']:
        raise ValueError('账户分红口径不一致')
    effects = []
    for name in ('allocation', 'holdingStart', 'cash'):
        # Narrative evidence is preserved, not accepted as quantified attribution.
        evidence = spec.get('effectEvidence', {}).get(name)
        if evidence is not None and (not isinstance(evidence, str) or not evidence.strip()):
            raise ValueError('影响线索须为明确文字；缺资料留空')
        effects.append(dict(effect=name, status='provided-not-independently-verified' if evidence else 'unknown',
                            evidence=evidence or None, contributionPct=None))
    difference = observed['twrPct'] - rows[1]['cumulativeReturnPct']
    return dict(type='account-benchmark-observation', inputSchema='account-benchmark-observation-v1',
                methodVersion='account-benchmark-observation-1', start=observed['start'], end=observed['end'],
                currency=account['currency'], dividends=basis['dividends'], benchmarkVersion=basis['benchmarkVersion'],
                accountCumulativeTwrPct=observed['twrPct'], accountAnnualizedXirrPct=observed['xirrPct'],
                comparisons=rows, accountMinusBenchmarkPercentagePoints=difference, effects=effects,
                accountMinusProductPercentagePoints=observed['twrPct'] - rows[0]['cumulativeReturnPct'],
                conclusion=f'在相同区间和声明口径下，账户累计收益比基准高{difference:.2f}个百分点。' if difference >= 0 else
                f'在相同区间和声明口径下，账户累计收益比基准低{abs(difference):.2f}个百分点。',
                limitations=['只比较已提供的观察记录；完整性和分红口径是声明，未认证账单',
                             '累计TWR与年化XIRR分别列示，不直接相减；差异不证明择时或配置能力',
                             '没有配置路径、买入起点与现金记录时，影响原因保持未知；不从期末截图重建账户'])


def publish(spec, out):
    result = calculate(spec)
    out = Path(out)
    if out.exists():
        raise FileExistsError('请另存新目录')
    text = '# 账户与基准差异观察\n\n**教学输入，不是真实账户验收。**\n\n' + result['conclusion']
    annualized = '未知或无法唯一求解' if result['accountAnnualizedXirrPct'] is None else '%.2f%%' % result['accountAnnualizedXirrPct']
    text += '\n\n账户累计TWR为%.2f%%；账户资金加权年化XIRR为%s。一个看区间表现，一个考虑出入金时点，不能直接相减。' % (result['accountCumulativeTwrPct'], annualized)
    for row in result['comparisons']:
        label = '产品' if row['kind'] == 'product' else '基准'
        text += '\n\n%s累计收益：%.2f%%。来源：%s。' % (label, row['cumulativeReturnPct'], row['source'])
    text += '\n\n账户与产品相差%.2f个百分点。账户可能包含其他资产或现金，这个差距不是产品回报的归因结论。' % result['accountMinusProductPercentagePoints']
    text += '\n\n## 为什么有差异\n\n'
    names = {'allocation': '配置', 'holdingStart': '持有起点', 'cash': '现金'}
    for row in result['effects']:
        text += names[row['effect']] + '影响：' + (str(row['evidence']) + '（仅为输入提供的线索，尚未量化核验）' if row['evidence'] else '资料不足，不能判断') + '。\n\n'
    text += '## 口径与限制\n\n' + f"{result['start']}至{result['end']}，{result['currency']}，分红{result['dividends']}，基准版本{result['benchmarkVersion']}。\n\n" + '\n\n'.join(result['limitations']) + '\n\n不构成投资建议。'
    out.mkdir(parents=True)
    for name, content in [('input.json', json.dumps(spec, ensure_ascii=False, indent=2)),
                          ('result.json', json.dumps(result, ensure_ascii=False, indent=2)),
                          ('报告.md', text), ('报告.html', render(text, '账户与基准差异观察'))]:
        (out / name).write_text(content, encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    parser.add_argument('--out-dir', required=True)
    args = parser.parse_args()
    from collection_validation import unique_pairs, reject_constant, finite_json_float
    publish(json.loads(args.input.read_text('utf-8-sig'), object_pairs_hook=unique_pairs,
                       parse_constant=reject_constant, parse_float=finite_json_float), args.out_dir)
