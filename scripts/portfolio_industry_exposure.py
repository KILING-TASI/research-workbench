"""Aggregate archived report industry amounts under explicit snapshot weights.

No stock classification, price conversion or missing-asset inference is performed.
"""
import argparse
import datetime
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from collection_validation import day,unique_pairs,reject_constant


def number(value, label):
    if isinstance(value,bool) or not isinstance(value,(int,float,str,Decimal)):
        raise ValueError(label + '须为有限非负数')
    try: result = Decimal(str(value))
    except InvalidOperation as exc: raise ValueError(label + '须为有限非负数') from exc
    if not result.is_finite() or result < 0:
        raise ValueError(label + '须为有限非负数')
    return result


def build(spec, base=Path('.')):
    if not isinstance(spec,dict):raise ValueError('行业敞口输入须为对象')
    date = spec.get('reportDate')
    day(date)
    assets = spec.get('assets')
    if not isinstance(assets, list) or not assets:
        raise ValueError('需提供持仓及静态权重')
    if any(not isinstance(x,dict) or 'allocation' not in x or 'code' not in x for x in assets):raise ValueError('持仓须含代码与静态权重')
    weights = [number(x['allocation'], '权重') for x in assets]
    if sum(weights) != 1:
        raise ValueError('静态组合权重合计须为1；现金等未解析资产也须显式登记')
    seen, merged, sources, missing = set(), {}, [], []
    for asset, weight in zip(assets, weights):
        code = asset['code']
        if not isinstance(code, str) or not code or code in seen:
            raise ValueError('标的代码为空或重复')
        seen.add(code)
        if not asset.get('industryReport'):
            reason = asset.get('missingReason')
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError('缺行业报告须明确缺失原因')
            missing.append(dict(code=code, allocation=str(weight), reason=reason))
            continue
        if not isinstance(asset['industryReport'],str) or not asset['industryReport'].strip():raise ValueError('行业报告路径须为文字')
        path = (base / asset['industryReport']).resolve()
        raw = path.read_bytes()
        report = json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
        if not isinstance(report,dict):raise ValueError('行业报告须为对象')
        if report.get('code') != code or report.get('reportDate') != date:
            raise ValueError('标的或报告期不一致，禁止混用快照')
        if report.get('currency') != 'CNY':
            raise ValueError('仅汇总已换算人民币的报告金额')
        nav = number(report['netAssetsCNY'], '净资产')
        equity = number(report['equityMarketValueCNY'], '股票总额')
        if not nav or equity > nav:
            raise ValueError('净资产须为正，股票超过净资产的杠杆情景不在本入口范围')
        sectors = report.get('sectors')
        if not isinstance(sectors,list) or any(not isinstance(s,dict) or 'marketValueCNY' not in s for s in sectors):raise ValueError('行业明细须为金额对象数组')
        if not sectors or sum(number(s['marketValueCNY'], '行业金额') for s in sectors) != equity:
            raise ValueError('行业明细未勾稽到股票总额')
        local = set()
        for sector in sectors:
            taxonomy = sector.get('taxonomy', report.get('taxonomy'))
            version = report.get('taxonomyVersion')
            key = sector['key']
            if not taxonomy or not version or not key or key in local:
                raise ValueError('行业分类、版本、代码缺失或重复')
            local.add(key)
            group = (taxonomy, version, key)
            item = merged.setdefault(group, dict(key=key, name=sector['name'], taxonomy=taxonomy,
                taxonomyVersion=version, portfolioNavWeight=Decimal(0), components=[]))
            if item['name'] != sector['name']:
                raise ValueError('同分类同代码行业名称冲突，须解释后再汇总')
            components=sector.get('components')
            if not isinstance(components,list) or any(not isinstance(r,dict) for r in components):raise ValueError('行业原文定位须为对象数组')
            locators = [r['locator'] for r in components if isinstance(r.get('locator'),str) and r['locator'].strip()]
            if not locators:
                raise ValueError('行业金额缺原文定位')
            amount = number(sector['marketValueCNY'], '行业金额')
            contribution = weight * amount / nav
            item['portfolioNavWeight'] += contribution
            item['components'].append(dict(code=code, allocation=str(weight), amountCNY=str(amount),
                netAssetsCNY=str(nav), contribution=str(contribution), locators=locators))
        sources.append(dict(code=code, path=str(path), sha256=hashlib.sha256(raw).hexdigest(),
            sourceSha256=report['sourceSha256'], allocation=str(weight), netAssetsCNY=str(nav)))
    sectors = []
    for item in merged.values():
        item['portfolioNavWeight'] = str(item['portfolioNavWeight'])
        sectors.append(item)
    known = sum((Decimal(s['portfolioNavWeight']) for s in sectors), Decimal(0))
    return dict(reportDate=date, currency='CNY', weighting='static-snapshot',
        formula='sum(allocation * industryMarketValueCNY / fundNetAssetsCNY)',
        sources=sources, sectors=sectors, knownEquityExposure=str(known),
        unclassifiedResidual=str(1-known), missingReports=missing,
        limits=['不同分类或版本分组保留，不跨口径排名；未核验版本仍不能认证可比性',
                '剩余资产保留未分类，不当作现金或零风险',
                '仅同日静态权重，不解释历史回撤或还原账户交易'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('input'); p.add_argument('--out', required=True)
    args = p.parse_args()
    source = Path(args.input)
    result = build(json.loads(source.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant), source.resolve().parent)
    with Path(args.out).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
