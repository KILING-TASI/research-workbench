"""On-demand bounded source probes; validity, date lag and coverage stay separate."""
import argparse
import datetime as dt
import hashlib
import json
import re
import socket
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit

from collection_validation import day, market_rows, positive, unique_pairs, reject_constant
from cross_market_history import parse as parse_cross, history_url, mapped_symbol
from cross_market_quote import symbol
from portable_collect import named
from public_download import download
from research_brief_html import render
from stock_statements import select as select_financial
from observation_calendar import assess as calendar_assess,validate as validate_calendar,note as calendar_note

PROFILES = {
    'fund-nav': ('基金净值', 'fund.eastmoney.com', 14),
    'cn-history-eastmoney': ('沪深价格日线主源', 'push2his.eastmoney.com', 14),
    'cn-history-tencent': ('沪深价格日线备用源', 'web.ifzq.gtimg.cn', 14),
    'hk-us-history': ('港美股价格日线', 'web.ifzq.gtimg.cn', 14),
    'stock-financial-summary': ('股票财务摘要', 'datacenter.eastmoney.com', 210),
    'stock-announcements': ('股票公告目录', 'np-anotice-stock.eastmoney.com', 180),
}


def read_json(raw):
    return json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant)


def prepare(spec):
    if not isinstance(spec, dict) or set(spec) - {'asOf', 'requests', 'timeoutSeconds'}:
        raise ValueError('体检输入须为对象')
    cutoff = day(spec.get('asOf'))
    requests = spec.get('requests')
    timeout = spec.get('timeoutSeconds', 8)
    if not isinstance(requests, list) or not 1 <= len(requests) <= 12:
        raise ValueError('体检须指定1至12项请求')
    if type(timeout) is not int or not 1 <= timeout <= 20:
        raise ValueError('timeoutSeconds须为1至20秒整数')
    plans = []
    seen = set()
    for index, request in enumerate(requests):
        if not isinstance(request, dict) or set(request) - {'profile', 'code', 'market', 'start', 'maxLagDays','calendar'}:
            raise ValueError('请求字段不支持；不接收任意URL、凭据或可执行程序')
        profile, code = request.get('profile'), request.get('code')
        if not isinstance(profile,str) or profile not in PROFILES or not isinstance(code, str):
            raise ValueError('体检profile或证券代码无效')
        calendar=request.get('calendar')
        if calendar is not None and profile not in ('fund-nav','cn-history-eastmoney','cn-history-tencent','hk-us-history'):raise ValueError('本profile不使用交易日历')
        market = request.get('market')
        if profile == 'hk-us-history':
            if market not in ('HK', 'US'):
                raise ValueError('港美股须明确market=HK或US')
            sym = symbol(market, code)
        else:
            if not re.fullmatch(r'[0-9]{6}', code):
                raise ValueError('国内代码须为六位数字')
            sym = None
            if profile.startswith('cn-history-') and market not in ('0', '1'):
                raise ValueError('沪深历史须明确market=0或1，不猜交易所')
            if not profile.startswith('cn-history-') and market is not None:
                raise ValueError('本profile不使用market参数')
        default_window = 365 if profile == 'stock-financial-summary' else 180 if profile == 'stock-announcements' else 30
        start = request.get('start', (cutoff - dt.timedelta(days=default_window)).isoformat())
        start_day = day(start)
        if start_day >= cutoff:
            raise ValueError('起点须早于截止日')
        if calendar is not None:
            cal_market=('SSE' if market=='1' else 'SZSE' if market=='0' else market)
            validate_calendar(calendar,start,spec['asOf'],cal_market)
        if 'history' in profile and (cutoff - start_day).days > 60:
            raise ValueError('体检价格窗口最多60个自然日；完整采集请用研究入口')
        lag = request.get('maxLagDays', PROFILES[profile][2])
        if type(lag) is not int or not 0 <= lag <= 730:
            raise ValueError('maxLagDays须为0至730整数')
        key = (profile, code, market, start)
        if key in seen:
            raise ValueError('重复体检请求')
        seen.add(key)
        if profile == 'fund-nav':
            url = 'https://fund.eastmoney.com/pingzhongdata/' + code + '.js'
        elif profile == 'cn-history-eastmoney':
            url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get?' + urlencode(dict(
                secid=market + '.' + code, klt=101, fqt=0, beg=start.replace('-', ''),
                end=spec['asOf'].replace('-', ''), fields1='f1,f2,f3,f4,f5,f6',
                fields2='f51,f52,f53,f54,f55,f56,f57', lmt=100))
        elif profile in ('cn-history-tencent', 'hk-us-history'):
            sym = sym or ('sh' if market == '1' else 'sz') + code
            url = history_url(sym, start, spec['asOf'])
        elif profile == 'stock-financial-summary':
            url = 'https://datacenter.eastmoney.com/api/data/v1/get?' + urlencode(dict(
                reportName='RPT_F10_FINANCE_MAINFINADATA', columns='ALL',
                filter='(SECURITY_CODE="' + code + '")', pageSize=5, pageNumber=1,
                sortColumns='REPORT_DATE', sortTypes='-1'))
        else:
            url = 'https://np-anotice-stock.eastmoney.com/api/security/ann?' + urlencode(dict(
                sr=-1, page_size=5, page_index=1, ann_type='A', stock_list=code,
                begin_time=start, end_time=spec['asOf']))
        plans.append(dict(id='probe-' + str(index + 1), profile=profile, code=code,
                          market=market, start=start, asOf=spec['asOf'], maxLagDays=lag,
                          sourceUrl=url, querySymbol=sym, timeoutSeconds=timeout,calendar=calendar))
    return plans


def parsed(plan, raw, query_symbol):
    profile, code = plan['profile'], plan['code']
    start, end = plan['start'], plan['asOf']
    if profile == 'fund-nav':
        text = raw.decode('utf-8-sig')
        name = named(text, 'fS_name')
        if str(named(text, 'fS_code')) != code or not isinstance(name, str) or not name.strip():
            raise ValueError('基金代码或名称不一致')
        data = named(text, 'Data_netWorthTrend')
        if not isinstance(data, list):
            raise ValueError('净值序列结构变化')
        dates = []
        for row in data:
            if not isinstance(row, dict) or not positive(row.get('y')) or not positive(row.get('x')):
                raise ValueError('净值行或数值无效')
            date = dt.datetime.fromtimestamp(row['x'] / 1000, dt.timezone(dt.timedelta(hours=8))).date().isoformat()
            dates.append(date)
        if dates != sorted(set(dates)):
            raise ValueError('净值日期重复或乱序')
        selected = [d for d in dates if start <= d <= end]
        return dict(name=name.strip(), dates=selected, dateBasis='净值所属日', providerLatestDate=max(dates, default=None))
    payload = read_json(raw.decode('utf-8-sig'))
    if not isinstance(payload, dict):
        raise ValueError('接口顶层不是对象')
    if profile == 'hk-us-history':
        mapping = mapped_symbol(payload, plan['market'], code) if query_symbol == plan['querySymbol'] else None
        if mapping:
            return {'mappedSymbol': mapping}
        result = parse_cross(payload, plan['market'], code, start, end, query_symbol)
        return dict(name=result['name'], dates=[r['date'] for r in result['history']], dateBasis='价格所属日')
    if profile.startswith('cn-history-'):
        rows = []
        if profile == 'cn-history-eastmoney':
            data = payload.get('data')
            if not isinstance(data, dict) or data.get('code') != code or not isinstance(data.get('name'), str) or not data['name'].strip():
                raise ValueError('日线代码或名称不一致')
            lines = data.get('klines')
            if not isinstance(lines, list) or len(lines) >= 100:
                raise ValueError('日线结构异常或可能截断')
            for line in lines:
                if not isinstance(line, str) or len(line.split(',')) < 7:
                    raise ValueError('日线布局变化')
                pieces = line.split(',')
                rows.append(dict(zip(['date', 'open', 'close', 'high', 'low', 'volume', 'amount'],
                                     [pieces[0]] + [float(v) for v in pieces[1:7]])))
            name = data['name']
        else:
            data = (payload.get('data') or {}).get(query_symbol)
            if payload.get('code') != 0 or not isinstance(data, dict):
                raise ValueError('备用日线响应异常')
            quote = data.get('qt', {}).get(query_symbol, [])
            if len(quote) < 3 or quote[2] != code or not quote[1]:
                raise ValueError('备用日线证券身份不一致')
            lines = data.get('day')
            if not isinstance(lines, list) or len(lines) >= 640:
                raise ValueError('未复权日线缺失或可能截断')
            for pieces in lines:
                if not isinstance(pieces, list) or len(pieces) < 6:
                    raise ValueError('备用日线布局变化')
                rows.append(dict(zip(['date', 'open', 'close', 'high', 'low', 'volume'],
                                     [pieces[0]] + [float(v) for v in pieces[1:6]])))
            name = quote[1]
        if rows:
            market_rows('history', rows)
        if any(not start <= r['date'] <= end for r in rows):
            raise ValueError('返回价格日期越界')
        return dict(name=name, dates=[r['date'] for r in rows], dateBasis='价格所属日')
    if profile == 'stock-financial-summary':
        data = payload.get('result')
        if not isinstance(data, dict) or not isinstance(data.get('data'), list):
            raise ValueError('财务摘要结构变化')
        if len(data['data']) > 5:
            raise ValueError('财务样本超出请求上限')
        selected = select_financial(data['data'], code, start, end)
        market_rows('financials', selected) if selected else None
        return dict(dates=[r['period'] for r in selected], dateBasis='报告期末',
                    publishedDates=[r['publishedAt'] for r in selected])
    data = payload.get('data')
    if not isinstance(data, dict) or not isinstance(data.get('list'), list) or len(data['list']) > 5:
        raise ValueError('公告目录结构变化或超出样本上限')
    rows = []
    for item in data['list']:
        if not isinstance(item, dict) or not any(str(c.get('stock_code')) == code for c in item.get('codes', [])):
            raise ValueError('公告证券身份不一致')
        date = str(item.get('notice_date', ''))[:10]
        day(date)
        if not isinstance(item.get('title'), str) or not item['title'].strip() or not start <= date <= end:
            raise ValueError('公告标题或日期范围异常')
        rows.append(dict(id=item.get('art_code'), date=date))
    market_rows('announcements', rows) if rows else None
    return dict(dates=[r['date'] for r in rows], dateBasis='公告披露日')


def run(spec, out, fetcher=download):
    plans = prepare(spec)  # Validate the entire batch before network or creating output.
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'input.json').write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
    raw_folder = out / 'responses'
    raw_folder.mkdir()
    rows, blocked_hosts = [], set()
    checked_at = dt.datetime.now(dt.timezone.utc).isoformat()
    for plan in plans:
        row = {**plan, 'checkedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
               'status': 'not-attempted', 'endpointResponded': False, 'sampleValid': False,
               'coverageVerified': False, 'originalVerified': False, 'attempts': [],
               'freshness': {'status': 'unknown'}, 'elapsedSeconds': 0}
        host = urlsplit(plan['sourceUrl']).hostname
        if host in blocked_hosts:
            row.update(status='skipped-source-blocked', reason='同一来源已拒绝访问或限流，本轮停止该来源')
            rows.append(row)
            continue
        url, query_symbol = plan['sourceUrl'], plan['querySymbol']
        began = time.monotonic()
        try:
            for attempt in range(2):  # Only a documented US symbol mapping, no retry.
                raw = fetcher(url, limit=8 * 1024 * 1024, timeout=plan['timeoutSeconds'],
                              headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://fund.eastmoney.com/'})
                row['endpointResponded'] = True
                file = raw_folder / (plan['id'] + '-' + str(attempt + 1) + '.raw')
                file.write_bytes(raw)
                row['attempts'].append(dict(sourceUrl=url, responsePath=file.relative_to(out).as_posix(),
                                            responseSha256=hashlib.sha256(raw).hexdigest(), responseBytes=len(raw)))
                result = parsed(plan, raw, query_symbol)
                if result.get('mappedSymbol') and attempt == 0:
                    query_symbol = result['mappedSymbol']
                    url = history_url(query_symbol, plan['start'], plan['asOf'])
                    continue
                break
            dates = result.get('dates', [])
            if 'history' in plan['profile'] or plan['profile']=='fund-nav':
                cal_market='SSE' if plan['market']=='1' else 'SZSE' if plan['market']=='0' else plan['market']
                row['dateCompleteness']=calendar_assess(sorted(dates),plan['start'],plan['asOf'],plan['calendar'],cal_market)
            if not dates:
                row.update(status='empty-sample', reason='窗口内未取得有效样本；不能据此认定没有交易、财报或公告')
            else:
                latest = max(dates)
                lag = (day(plan['asOf']) - day(latest)).days
                row.update(status='observed', sampleValid=True, observations=len(dates),
                           actualStart=min(dates), actualEnd=latest, name=result.get('name'),
                           dateBasis=result['dateBasis'], providerLatestDate=result.get('providerLatestDate'),
                           latestPublishedAt=max(result.get('publishedDates', []), default=None),
                           freshness=dict(status='stale' if lag > plan['maxLagDays'] else 'within-threshold',
                                          referenceDate=plan['asOf'], lagCalendarDays=lag,
                                          maxLagDays=plan['maxLagDays'], calendarVerified=False),
                           reason='样本结构与证券代码检查通过，完整区间、真实性及交易日历未核验')
                if 'history' in plan['profile'] or plan['profile'] == 'fund-nav':
                    row['reason']+='；'+calendar_note(row['dateCompleteness'])
                    calendar_status=row['dateCompleteness']['status']
                    if calendar_status in ('dates-aligned','date-gaps'):
                        expected_latest=row['dateCompleteness']['lastExpectedDate']
                        if expected_latest is not None:
                            row['freshness']['referenceObservationDate']=expected_latest
                            row['freshness']['calendarApplicabilityConfirmed']=True
                            row['freshness']['status']='within-threshold' if latest>=expected_latest else row['freshness']['status']
                    row['minimumReturnObservationsMet'] = len(dates) >= 2
                    row['startGapCalendarDays'] = (day(min(dates)) - day(plan['start'])).days
                    if len(dates) < 2:
                        row['reason'] += '；窗口内仅1条观测，不能计算区间收益或波动'
        except HTTPError as exc:
            row.update(status='blocked' if exc.code in (401, 403, 429) else 'network-error',
                       endpointResponded=True, httpStatus=exc.code, reason='来源返回HTTP ' + str(exc.code))
            row['attempts'].append(dict(sourceUrl=url, httpStatus=exc.code, error='http-error'))
            if exc.code in (401, 403, 429):
                blocked_hosts.add(host)
        except (URLError, TimeoutError, socket.timeout, OSError) as exc:
            row.update(status='network-error', reason=type(exc).__name__ + '：' + str(exc))
            row['attempts'].append(dict(sourceUrl=url, error=type(exc).__name__))
        except (ValueError, TypeError, KeyError, OverflowError, AttributeError) as exc:
            row.update(status='invalid-sample', reason=type(exc).__name__ + '：' + str(exc))
        row['elapsedSeconds'] = round(time.monotonic() - began, 3)
        rows.append(row)
    alternatives = []
    for code, market, start in {(r['code'], r['market'], r['start']) for r in rows if r['profile'].startswith('cn-history-')}:
        candidates = [r for r in rows if r['code'] == code and r['market'] == market and r['start'] == start and r['profile'].startswith('cn-history-')]
        good = [r['profile'] for r in candidates if r['sampleValid'] and r['freshness']['status'] == 'within-threshold' and r.get('minimumReturnObservationsMet',False) and r.get('dateCompleteness',{}).get('status') not in ('date-gaps','calendar-applicability-unconfirmed')]
        if good:
            alternatives.append(dict(code=code, market=market, start=start, sampleUsableProfiles=sorted(good),
                                     note='仅本次同标的窗口的体检候选；研究取数仍需重新校验和保存实际来源'))
    status_counts = {state: sum(r['status'] == state for r in rows) for state in sorted({r['status'] for r in rows})}
    result = dict(type='research-source-health', version=1, asOf=spec['asOf'], checkedAt=checked_at,
                  status='samples-within-threshold' if all(r['sampleValid'] and r['freshness']['status'] == 'within-threshold' and r.get('minimumReturnObservationsMet', True) and r.get('dateCompleteness',{}).get('status') not in ('date-gaps','calendar-applicability-unconfirmed') for r in rows) else 'partial',
                  statusCounts=status_counts, rows=rows, alternatives=alternatives,
                  limitations=['仅用户主动触发，不调度或轮询；每项不重试，US代码明确映射最多追加一次请求',
                               '检查的是指定标的的小窗口样本，不代表全市场覆盖、长期可用率或数值真实性',
                               '未提供适用日历时，自然日间隔阈值不检测缺失交易日；提供日历时只核对所声明窗口和日期，不证明来源真实性',
                               '行情为未复权价格；财务为摘要；公告为目录，均不等于公告原文核验',
                               '未检查的源、数据域及未连接授权终端不标为通过；不改变研究缓存'])
    result['methodSha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (out / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    text = markdown(result)
    (out / '数据源体检.md').write_text(text, encoding='utf-8')
    (out / '数据源体检.html').write_text(render(text, title='数据源体检'), encoding='utf-8')
    return result


def markdown(result):
    lines = ['# 数据源体检', '', '检查参考日：' + result['asOf'] + '。本次共检查' + str(len(result['rows'])) + '项指定样本。', '',
             '| 数据 | 代码 | 本次结果 | 实际日期 | 日期间隔 |', '|---|---|---|---|---|']
    names = {'observed': '取得并通过样本结构检查', 'empty-sample': '窗口内样本为空', 'blocked': '拒绝访问或限流',
             'network-error': '网络请求未完成', 'invalid-sample': '样本或接口结构异常', 'skipped-source-blocked': '因同源拒绝而停止'}
    for row in result['rows']:
        fresh = row['freshness']
        lag = str(fresh['lagCalendarDays']) + '个自然日' if 'lagCalendarDays' in fresh else '未确认'
        if fresh.get('status') == 'stale':
            lag += '，超过本次阈值'
        elif fresh.get('status') == 'within-threshold':
            lag += '，在本次阈值内'
        lines.append('| ' + PROFILES[row['profile']][0] + ' | ' + row['code'] + ' | ' + names[row['status']] + ' | ' + row.get('actualEnd', '未取得') + ' | ' + lag + ' |')
    lines += ['', '## 结果说明', '']
    for row in result['rows']:
        lines += ['- ' + row['code'] + '：' + row['reason'] + '。[本次来源](' + row['sourceUrl'] + ')。']
        if row.get('dateCompleteness'):lines.append('- 日期覆盖：'+calendar_note(row['dateCompleteness']))
    if result['alternatives']:
        lines += ['', '## 本次可继续尝试的来源', '']
        for row in result['alternatives']:
            lines.append('- ' + row['code'] + '：' + '、'.join(PROFILES[p][0] for p in row['sampleUsableProfiles']) + '，仅适用于本次窗口。')
    return '\n'.join(lines + ['', '## 适用范围', ''] + ['- ' + s for s in result['limitations']])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--out-dir', type=Path, required=True)
    args = parser.parse_args()
    result = run(read_json(args.input.read_text(encoding='utf-8-sig')), args.out_dir)
    print(json.dumps({'status': result['status'], 'statusCounts': result['statusCounts'], 'output': str(args.out_dir)}, ensure_ascii=False))
