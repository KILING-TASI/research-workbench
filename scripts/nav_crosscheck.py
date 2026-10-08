"""Compare explicitly sourced NAV observations without certifying full history."""
import argparse
import hashlib
import json
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from urllib.parse import urlsplit
import re


from collection_validation import unique_pairs,reject_constant,finite_json_float

def load_json(text):
 return json.loads(text,object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def iso_day(value):
 if not isinstance(value,str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}',value):raise ValueError('日期须为YYYY-MM-DD')
 return date.fromisoformat(value)

def amount(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?', value):
        raise ValueError('净值须为十进制字符串')
    result = Decimal(value)
    if not result.is_finite() or result <= 0:
        raise ValueError('净值须为有限正数')
    return result


def compare(spec):
    code = spec['code']
    if not isinstance(code, str) or len(code) != 6 or not code.isascii() or not code.isdigit():
        raise ValueError('需六位基金代码')
    asof = iso_day(spec['asOf'])
    sources = spec['sources']
    if not isinstance(sources, list) or len(sources) != 2:
        raise ValueError('须提供两份来源观察')
    tables = []
    for source in sources:
        parsed = urlsplit(source['url'])
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('来源须为有效HTTPS地址')
        if source['code'] != code or source.get('basis') != 'unit-nav':
            raise ValueError('代码或净值口径不一致')
        if not source.get('retrievedAt') or not source.get('observations'):
            raise ValueError('需取得时间和观察值')
        table = {}
        for row in source['observations']:
            d = iso_day(row['date'])
            if d.isoformat() != row['date'] or d > asof or row['date'] in table:
                raise ValueError('日期重复、无效或超过截止日')
            quote = row.get('excerpt', '')
            nav = amount(row['nav'])
            nav_pattern = r'(?<![0-9.])' + re.escape(row['nav']) + r'(?![0-9.%eE])'
            if not isinstance(quote, str) or row['date'] not in quote or not re.search(nav_pattern, quote):
                raise ValueError('须保留含日期和净值的来源摘录')
            table[row['date']] = nav
        tables.append(table)
    common = sorted(tables[0].keys() & tables[1].keys())
    rows = [dict(date=d, first=str(tables[0][d]), second=str(tables[1][d]),
                 difference=str(tables[0][d]-tables[1][d]),
                 matched=tables[0][d] == tables[1][d]) for d in common]
    return dict(code=code, asOf=spec['asOf'], basis='unit-nav',
                status='no-common-observations' if not rows else
                ('selected-observations-match' if all(r['matched'] for r in rows) else 'selected-observations-conflict'),
                rows=rows, matchedCount=sum(r['matched'] for r in rows), comparedCount=len(rows),
                unmatchedDates=[sorted(t.keys()-set(common)) for t in tables],
                sources=sources, fullHistoryVerified=False, dividendCompletenessVerified=False,
                sourceAuthenticityCertified=False,
                limitations=['仅核对所提供日期的单位净值，不核验全区间收益、分红或交易日完整性',
                             '来源摘录由调用者取得；字符串匹配不证明网页真实性或来源独立性',
                             '官网和第三方相同值可能共享底层来源，不等于两次独立估值'])


def resolve_period_paths(spec, base_dir):
    """Resolve archive references against the task file, without changing hashes."""
    result = dict(spec)
    for key in ('unitNavFile', 'pdfFile'):
        value = result.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError('净值与原文路径须为非空字符串')
        path = Path(value)
        result[key] = str(path if path.is_absolute() else Path(base_dir) / path)
    return result


def compare_period_return(spec):
    """Check one no-distribution reporting period against archived unit NAVs."""
    from pypdf import PdfReader
    if not re.fullmatch(r'[0-9]{6}',str(spec.get('code',''))) or not re.fullmatch(r'[A-Z]',spec.get('shareClass','')):
        raise ValueError('需六位基金代码和明确份额类别')
    paths = {k: Path(spec[k]) for k in ('unitNavFile', 'pdfFile')}
    for key, path in paths.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != spec[key+'Sha256']:
            raise ValueError('净值或原文文件版本改变')
    history = load_json(paths['unitNavFile'].read_text(encoding='utf-8'))
    if history.get('code') != spec['code'] or history.get('historyBasis') != 'nav-with-distributions':
        raise ValueError('代码或单位净值来源口径不匹配')
    start, end = iso_day(spec['periodStart']), iso_day(spec['periodEnd'])
    if start > end or iso_day(spec['baselineDate']) != start-timedelta(days=1):
        raise ValueError('基期须为报告期开始前一日，缺值不得向后替代')
    reader = PdfReader(paths['pdfFile'])
    clean = lambda x: re.sub(r'\s+', '', x)
    for key in ('periodEvidence', 'performanceEvidence', 'noDistributionEvidence'):
        item = spec[key]
        if type(item.get('page')) is not int or not 1 <= item['page'] <= len(reader.pages):
            raise ValueError('原文物理页码无效')
        if not item.get('quote') or clean(item['quote']) not in clean(reader.pages[item['page']-1].extract_text() or ''):
            raise ValueError('选定原文摘录未匹配')
    period = clean(spec['periodEvidence']['quote'])
    date_pattern = lambda d: f'{d.year}年(?:{d.month}|{d.month:02d})月(?:{d.day}|{d.day:02d})日'
    short_end = rf'(?<![年\d])(?:{end.month}|{end.month:02d})月(?:{end.day}|{end.day:02d})日'
    if not re.search(date_pattern(start), period) or not (re.search(date_pattern(end),period) or start.year == end.year and re.search(short_end,period)):
        raise ValueError('报告期间未在选定声明中匹配')
    performance = clean(spec['performanceEvidence']['quote'])
    if not isinstance(spec['reportedReturnPct'],str):raise ValueError('披露收益须为十进制字符串')
    reported = Decimal(spec['reportedReturnPct'])
    return_pattern = (re.escape(spec['shareClass']) + r'(?:类)?份额净值增长率(?:为|是|[:：])?'
                      + re.escape(spec['reportedReturnPct']) + r'%')
    if not reported.is_finite() or '基准' in performance or not re.search(return_pattern, performance):
        raise ValueError('须定位相同份额的净值增长率，不是基准表现')
    declaration=clean(spec['noDistributionEvidence']['quote'])
    if '本报告期' not in declaration or not re.search(r'未(?:实施|进行)(?:利润|收益)分配|不存在利润分配',declaration):
        raise ValueError('当前仅核对原文明示本期未分配的区间')
    table = {}
    for item in history['history']:
        if spec['baselineDate'] <= item['date'] <= spec['periodEnd']:
            iso_day(item['date'])
            if item['date'] in table:
                raise ValueError('净值日期重复')
            table[item['date']] = item
            if spec['baselineDate'] < item['date'] and item.get('distribution'):
                raise ValueError('净值来源出现分红事件，与未分配声明冲突')
    if spec['baselineDate'] not in table or spec['periodEnd'] not in table:
        raise ValueError('期初基准或期末净值缺失，不插值、不换日期')
    first = amount(str(table[spec['baselineDate']]['nav']))
    last = amount(str(table[spec['periodEnd']]['nav']))
    computed = (last/first-1)*100
    rounded = computed.quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
    return dict(code=spec['code'], shareClass=spec['shareClass'], periodStart=spec['periodStart'],
        periodEnd=spec['periodEnd'], baselineDate=spec['baselineDate'], baselineNav=str(first), endNav=str(last),
        formula='(endUnitNav / baselineUnitNav - 1) * 100; 本期原文明示未分配',
        computedReturnPct=str(computed), computedRoundedPct=str(rounded), reportedReturnPct=str(reported),
        differencePp=str(computed-reported), status='selected-period-rounded-match' if rounded == reported else 'selected-period-conflict',
        evidence={k:spec[k] for k in ('periodEvidence','performanceEvidence','noDistributionEvidence')},
        sourceHashes={k:spec[k+'Sha256'] for k in paths}, fullHistoryVerified=False,
        sourceAuthenticityCertified=False, limitations=['仅核对指定报告期、份额及两个端点，不验证全历史净值或交易日历',
        '未分配来自已取得报告声明，不认证官方网页及其他报告期',
        '显示精度内一致不证明真实账户收益、经理能力或经济归因'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('input'); p.add_argument('--out', required=True)
    p.add_argument('--mode', choices=['observations','period-return'], default='observations')
    a = p.parse_args(); raw = Path(a.input).read_bytes()
    spec = load_json(raw.decode('utf-8'))
    if a.mode == 'period-return':
        spec = resolve_period_paths(spec, Path(a.input).resolve().parent)
    result = (compare_period_return if a.mode == 'period-return' else compare)(spec)
    result['inputSha256'] = hashlib.sha256(raw).hexdigest()
    with Path(a.out).open('x', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
