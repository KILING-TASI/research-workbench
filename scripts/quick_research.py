"""Thin practical adapters: user holdings CSV and explicit fund-code comparison."""
import csv
import datetime as dt
import hashlib
import io
import json
import re
from decimal import Decimal
from pathlib import Path
from collection_validation import day
from research_brief_html import render


def snapshot(input_path, out, as_of):
    cutoff = day(as_of)
    raw = Path(input_path).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), strict=True)
    required = {'code', 'name', 'market_value', 'currency', 'asset_class'}
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or not required <= set(reader.fieldnames):
        raise ValueError('CSV需要唯一列名：code,name,market_value,currency,asset_class；可加valuation_date')
    rows, seen, currencies = [], set(), set()
    from investment_intent import nonnegative
    for line, source in enumerate(reader, 2):
        if None in source or any(source.get(key) is None for key in required):
            raise ValueError('CSV第'+str(line)+'行列数不一致')
        code, name = source['code'].strip(), source['name'].strip()
        currency, category = source['currency'].strip(), source['asset_class'].strip()
        if not code or not name or not re.fullmatch(r'[A-Z]{3}', currency):
            raise ValueError('CSV代码、名称或币种无效；币种须如CNY')
        if category not in {'fund', 'etf', 'stock', 'bond', 'convertible', 'cash', 'other'}:
            raise ValueError('资产类型使用fund/etf/stock/bond/convertible/cash/other，不从名称推断')
        key = (currency, code)
        if key in seen:
            raise ValueError('持仓代码重复，请确认身份后合并，不自动合并A/C份额')
        seen.add(key); currencies.add(currency)
        value = nonnegative(source['market_value'])
        valuation = (source.get('valuation_date') or '').strip()
        if valuation and day(valuation) > cutoff:
            raise ValueError('持仓估值日不能晚于截止日')
        rows.append({'code':code, 'name':name, 'marketValue':str(value), 'currency':currency,
                     'assetClass':category, 'valuationDate':valuation or None})
        if len(rows) > 1000:
            raise ValueError('快速快照最多1000条持仓')
    if len(currencies) != 1:
        raise ValueError('持仓需为单一币种；混币种请先提供有来源的换算，不直接相加')
    total = sum((Decimal(row['marketValue']) for row in rows), Decimal(0))
    if total <= 0:
        raise ValueError('需有正数持仓市值')
    for row in rows:
        row['weightPct'] = str(Decimal(row['marketValue']) / total * 100)
    ordered = sorted(rows, key=lambda row:Decimal(row['marketValue']), reverse=True)
    classes = {}
    for row in rows:
        classes[row['assetClass']] = classes.get(row['assetClass'], Decimal(0)) + Decimal(row['marketValue'])
    largest = ordered[0]
    currency = next(iter(currencies))
    result = {'status':'partial', 'asOf':as_of, 'currency':currency, 'totalMarketValue':str(total),
              'holdings':rows, 'assetClassValues':{k:str(v) for k,v in classes.items()},
              'inputSha256':hashlib.sha256(raw).hexdigest(), 'sourceVerification':'user-declared-not-verified',
              'gaps':['未取得底层持仓与行业映射，不能判断是否重复押注赛道',
                      '未取得共同历史与交易记录，不能计算相关性、波动、最大回撤或个人收益',
                      '未提供资金用途及用户阈值，不给健康评分或自动建议仓位']}
    def cell(value):
        return str(value).replace('|','／').replace('\n',' ').replace('\r',' ')
    lead = '所给持仓合计'+format(total, '.2f')+' '+currency+'；最大一项是'+cell(largest['name'])+'，占'+format(Decimal(largest['weightPct']),'.2f')+'%。这是资金集中位置，不是风险贡献或超限判断。'
    lines = ['# 我的持仓结构快照', '', '> '+lead, '', '当前只能回答“钱放在哪里”，尚不能判断组合是否健康、是否重复押注或适合个人目标。', '',
             '|持仓|代码|市值|占比|声明类型|估值日|', '|---|---|---:|---:|---|---|']
    for row in ordered:
        lines.append('|'+cell(row['name'])+'|'+cell(row['code'])+'|'+format(Decimal(row['marketValue']),'.2f')+'|'+format(Decimal(row['weightPct']),'.2f')+'%|'+row['assetClass']+'|'+str(row['valuationDate'] or '未提供')+'|')
    lines += ['', '## 哪些判断现在还不能做', *['- '+gap for gap in result['gaps']], '', '## 下一步最有用的资料',
              '先补相同披露期的基金/ETF底层持仓与共同历史序列，再检查重叠、行业与共同回撤。现金需求和集中度上限由用户确认，不替用户设定。', '',
              '代码、类型与市值来自CSV声明；未认证实际账户。估值日仅核对不晚于截止日，不保证时效。类型标签不等于穿透后的大类资产暴露；A/C份额是不同代码，但可能是同一底层组合。',
              '此快照用于资料整理与研究，不提供买卖指令或收益保证。']
    out = Path(out); out.mkdir()
    (out/'input.csv').write_bytes(raw)
    (out/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
    body = '\n'.join(lines)
    (out/'持仓结构.md').write_text(body, 'utf-8')
    (out/'持仓结构.html').write_text(render(body, '我的持仓结构快照'), 'utf-8')
    return result


def fund_codes(codes, start, as_of, group, out, fetch=None):
    from portable_collect import get, named
    from fund_details import extract
    from fund_comparison_brief import publish
    from research_pipeline import series
    if day(start) >= day(as_of):
        raise ValueError('基金比較起点须早于截止日')
    if not isinstance(codes,list) or not 2 <= len(codes) <= 10 or len(set(codes)) != len(codes) or any(not re.fullmatch(r'[0-9]{6}', code) for code in codes):
        raise ValueError('需要2至10个不同的六位场外基金代码；ETF请用ETF入口')
    if not isinstance(group,str) or not group.strip():
        raise ValueError('须声明比较池名称；这不认证为同类基金')
    out = Path(out); out.mkdir()
    rawdir = out/'raw'; rawdir.mkdir()
    rows, collection = [], {}
    fetch = fetch or get
    for code in codes:
        url = 'https://fund.eastmoney.com/pingzhongdata/'+code+'.js'
        record = {'sourceUrl':url, 'status':'failed', 'retrievedAt':dt.datetime.now(dt.timezone.utc).isoformat()}
        try:
            text = fetch(url)
            (rawdir/(code+'.txt')).write_text(text,'utf-8')
            record['sha256'] = hashlib.sha256(text.encode('utf-8')).hexdigest()
            info = extract(text,code,as_of,record['retrievedAt'])
            history = []
            for point in named(text,'Data_netWorthTrend') or []:
                observed = dt.datetime.fromtimestamp(point['x']/1000,dt.timezone(dt.timedelta(hours=8))).date().isoformat()
                if start <= observed <= as_of:
                    history.append({'date':observed,'nav':point['y'],'distribution':point.get('unitMoney') or ''})
            if len(history)<2:
                raise ValueError('请求区间历史不足')
            if (day(history[0]['date'])-day(start)).days>7 or (day(as_of)-day(history[-1]['date'])).days>7:
                raise ValueError('区间边界超过7个日历日未覆盖；需确认成立日、停更或区间，而非自动缩短')
            series(history,as_of,'nav-with-distributions')
            rows.append({'code':code,'name':info['name'],'comparisonGroup':group.strip(),
                         'basis':'nav-with-distributions','frequency':'trading_day','history':history,
                         'source':url,'retrievedAt':record['retrievedAt']})
            record['status']='collected';record['observations']=len(history)
        except (OSError,ValueError,TypeError,KeyError,OverflowError) as error:
            record['error']=str(error)
        collection[code]=record
    (out/'collection.json').write_text(json.dumps(collection,ensure_ascii=False,indent=2),'utf-8')
    failed = [code for code in codes if collection[code]['status']!='collected']
    if failed:
        return {'status':'blocked','message':'部分基金未取得可用历史，保留原响应与失败原因，未缩小比较池。',
                'nextSteps':['阅读collection.json中各代码失败原因；确认代码、区间，或提供已取得净值。'], 'failedCodes':failed}
    document={'asOf':as_of,'start':start,'rows':rows}
    publish(document,out/'comparison')
    return {'status':'partial','message':'基金共同区间比较报告已生成；完整产品评价尚未完成。',
            'nextSteps':['打开comparison中的基金比较说明.html。','不同风格与未知币种不视为同类；基准、持仓、经理和分红完整性另核。'],
            'sourceVerification':'not-verified', 'currencyVerification':'not-verified', 'requestedCodes':codes}
