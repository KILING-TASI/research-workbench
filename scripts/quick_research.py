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
    aliases = {'基金代码':'code','资产代码':'code','代码':'code','基金名称':'name','资产名称':'name','名称':'name',
               '当前市值':'market_value','市值':'market_value','币种':'currency','资产类型':'asset_class','估值日期':'valuation_date'}
    columns = reader.fieldnames or []
    normalized = [aliases.get(column.strip(),column.strip()) for column in columns]
    required = {'code', 'name', 'market_value', 'currency', 'asset_class'}
    if len(set(normalized)) != len(normalized):
        raise ValueError('CSV列名重复或中英文列名指向同一字段，请只保留一列')
    if not columns or not required <= set(normalized):
        labels={'code':'代码','name':'名称','market_value':'当前市值','currency':'币种','asset_class':'资产类型'}
        missing='、'.join(labels[key] for key in sorted(required-set(normalized)))
        raise ValueError('持仓表缺少这些列：'+missing+'；不要将本金、份额或未标口径的“金额”当作当前市值')
    rows, seen, currencies = [], set(), set()
    from investment_intent import nonnegative
    for line, original in enumerate(reader, 2):
        source = {aliases.get(key.strip(),key.strip()) if isinstance(key,str) else key:value for key,value in original.items()}
        if None in source or any(source.get(key) is None for key in required):
            raise ValueError('CSV第'+str(line)+'行列数不一致')
        code, name = source['code'].strip(), source['name'].strip()
        currency = {'人民币':'CNY','美元':'USD','港币':'HKD'}.get(source['currency'].strip(),source['currency'].strip().upper())
        category = source['asset_class'].strip()
        category = {'基金':'fund','ETF':'etf','股票':'stock','债券':'bond','可转债':'convertible','现金':'cash','其他':'other'}.get(category,category)
        if not code or not name or not re.fullmatch(r'[A-Z]{3}', currency):
            raise ValueError('CSV代码、名称或币种无效；币种须如CNY')
        if category not in {'fund', 'etf', 'stock', 'bond', 'convertible', 'cash', 'other'}:
            raise ValueError('资产类型使用fund/etf/stock/bond/convertible/cash/other，不从名称推断')
        key = (currency, code)
        if key in seen:
            raise ValueError('持仓代码重复，请确认身份后合并，不自动合并A/C份额')
        seen.add(key); currencies.add(currency)
        amount = source['market_value'].strip()
        if re.search(r'[万元份]',amount):
            raise ValueError('CSV第'+str(line)+'行市值只填数字，使用币种基本单位；不要填“万”、份额或投入成本')
        if ',' in amount:
            if not re.fullmatch(r'[0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?',amount):
                raise ValueError('CSV第'+str(line)+'行金额千位分隔不规范；市值需用元等币种基本单位，不填“万”或份额')
            amount = amount.replace(',','')
        value = nonnegative(amount)
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
    share_groups={}
    for row in rows:
        if row['assetClass']!='fund':continue
        match=re.fullmatch(r'(.{4,}?)(?:\s*)[ABC]',row['name'])
        if match:share_groups.setdefault(match[1].strip(),[]).append(row)
    share_hints=[]
    for name,members in share_groups.items():
        if len(members)<2 or len({row['name'][-1] for row in members})<2:continue
        combined=sum((Decimal(row['marketValue']) for row in members),Decimal(0))
        share_hints.append({'nameStem':name,'codes':[row['code'] for row in members],
                            'marketValue':str(combined),'weightPct':str(combined/total*100),
                            'status':'name-based-share-class-clue-not-verified'})
    result = {'status':'partial', 'asOf':as_of, 'currency':currency, 'totalMarketValue':str(total),
              'columnMapping':dict(zip(columns,normalized)),
              'holdings':rows, 'assetClassValues':{k:str(v) for k,v in classes.items()},
              'shareClassClues':share_hints,
              'inputSha256':hashlib.sha256(raw).hexdigest(), 'sourceVerification':'user-declared-not-verified',
              'gaps':['未取得底层持仓与行业映射，不能判断是否重复押注赛道',
                      '未取得共同历史与交易记录，不能计算相关性、波动、最大回撤或个人收益',
                      '未提供资金用途及用户阈值，不给健康评分或自动建议仓位']}
    def cell(value):
        return str(value).replace('|','／').replace('\n',' ').replace('\r',' ')
    lead = '所给持仓合计'+format(total, '.2f')+' '+currency+'；最大一项是'+cell(largest['name'])+'，占'+format(Decimal(largest['weightPct']),'.2f')+'%。这是资金集中位置，不是风险贡献或超限判断。'
    if share_hints:lead+='另有'+str(len(share_hints))+'组可能的同产品份额，需先核查是否把不同份额当成了分散。'
    result['headline']=lead
    lines = ['# 我的持仓结构快照', '', '> '+lead, '', '当前只能回答“钱放在哪里”，尚不能判断组合是否健康、是否重复押注或适合个人目标。', '',
             '|持仓|代码|市值|占比|声明类型|估值日|', '|---|---|---:|---:|---|---|']
    for row in ordered:
        lines.append('|'+cell(row['name'])+'|'+cell(row['code'])+'|'+format(Decimal(row['marketValue']),'.2f')+'|'+format(Decimal(row['weightPct']),'.2f')+'%|'+row['assetClass']+'|'+str(row['valuationDate'] or '未提供')+'|')
    if share_hints:
        lines+=['','## 是否把不同份额当成了分散？','下列名称仅在末尾A/C等份额字母不同，可能属于同一产品。费用类别不同不必然带来风险分散；需核对官方产品关系和同一期持仓，不能仅凭名称认定底层相同。']
        for hint in share_hints:
            lines.append('- '+cell(hint['nameStem'])+'：'+', '.join(hint['codes'])+'声明市值合计'+format(Decimal(hint['marketValue']),'.2f')+' '+currency+'，占本次市值'+format(Decimal(hint['weightPct']),'.2f')+'%。此处只是这些账户项目金额相加，不是已核验的底层暴露。')
        lines.append('其他名称未命中不证明没有重复；简称、不同命名或不同产品的持仓重叠仍需要报告。')
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


def checked_fund_history(text, code, start, as_of, retrieved):
    from portable_collect import named
    from fund_details import extract
    from research_pipeline import series
    info=extract(text,code,as_of,retrieved);history=[];available=[]
    for point in named(text,'Data_netWorthTrend') or []:
        observed=dt.datetime.fromtimestamp(point['x']/1000,dt.timezone(dt.timedelta(hours=8))).date().isoformat()
        if observed<=as_of:available.append(observed)
        if start<=observed<=as_of:history.append({'date':observed,'nav':point['y'],'distribution':point.get('unitMoney') or ''})
    coverage=('；原响应截至请求截止日的记录范围为'+min(available)+'至'+max(available)+'，不代表期间完整或最新' if available else '；原响应没有请求截止日前的净值记录')
    if len(history)<2:raise ValueError('请求区间历史不足'+coverage)
    if (day(history[0]['date'])-day(start)).days>7 or (day(as_of)-day(history[-1]['date'])).days>7:
        raise ValueError('区间边界超过7个日历日未覆盖；可能涉及节假日或资料缺口，不能据此断言停更。当前区间实际记录为'+history[0]['date']+'至'+history[-1]['date']+'；需确认成立日、适用日历或区间，而非自动缩短'+coverage)
    series(history,as_of,'nav-with-distributions')
    return info,history


def fund_codes(codes, start, as_of, group, out, fetch=None, reuse_from=None, allow_online=True):
    from portable_collect import get
    from fund_comparison_brief import publish
    if day(start) >= day(as_of):
        raise ValueError('基金比較起点须早于截止日')
    if not isinstance(codes,list) or not 2 <= len(codes) <= 10 or len(set(codes)) != len(codes) or any(not re.fullmatch(r'[0-9]{6}', code) for code in codes):
        raise ValueError('需要2至10个不同的六位基金或ETF代码；本入口比较公开净值，不是ETF交易行情')
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
            text=None
            if reuse_from:
                try:
                    from collection_validation import unique_pairs,reject_constant,finite_json_float,timestamp
                    previous=Path(reuse_from).resolve();path=(previous/'raw'/(code+'.txt')).resolve()
                    if not path.is_relative_to(previous):raise ValueError('复用原响应指向指定目录外')
                    if path.stat().st_size>16*1024*1024:raise ValueError('复用原响应超过16MiB限制')
                    metadata=json.loads((previous/'collection.json').read_text('utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)[code]
                    candidate=path.read_text('utf-8');timestamp(metadata['retrievedAt'])
                    if metadata['status'] not in ('collected','failed') or metadata['sourceUrl']!=url or hashlib.sha256(candidate.encode()).hexdigest()!=metadata['sha256']:raise ValueError('复用资料身份、状态或摘要不一致')
                    checked_fund_history(candidate,code,start,as_of,metadata['retrievedAt'])
                    text=candidate;record.update(retrievedAt=metadata['retrievedAt'],reused=True,previousCollectionStatus=metadata['status'])
                except (OSError,ValueError,TypeError,KeyError) as error:record['reuseError']=str(error)
            if text is None:
                if not allow_online:raise ValueError(('旧资料未通过本次检查：'+record['reuseError'] if record.get('reuseError') else '没有可复用资料')+'；未启用联网，不发起下载')
                text = fetch(url);record['reused']=False
            (rawdir/(code+'.txt')).write_text(text,'utf-8')
            record['sha256'] = hashlib.sha256(text.encode('utf-8')).hexdigest()
            info,history = checked_fund_history(text,code,start,as_of,record['retrievedAt'])
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
        lines=['# 基金比较还差哪些资料','',
               '本次未生成比较结论：'+str(len(codes)-len(failed))+'只取得可用区间资料，'+str(len(failed))+'只未完成。已取得资料保留，不删除失败对象后缩小比较池。','',
               '请求区间：'+start+'至'+as_of+'。','','## 各只基金的情况']
        for code in codes:
            record=collection[code]
            if record['status']=='collected':
                lines+=['','### '+code,'本次区间资料可用，已保留'+str(record['observations'])+'条观测。接续时可复用，不必重取。']
            else:
                reason=str(record.get('error') or '未取得有效响应').replace('\n',' ').replace('\r',' ')
                if '没有可复用资料' in reason:
                    action='如需主动取新资料，接续时加--online；也可提供已取得的净值输入使用compare入口。'
                elif '区间边界' in reason or '历史不足' in reason:
                    action='先确认基金成立日、请求区间及是否停更；有依据后修改日期，不自动缩短区间。'
                else:action='确认代码和网络条件后，接续时启用联网重试本项；已经可用的其他基金资料会继续复用。'
                lines+=['','### '+code,'未完成原因：'+reason,'','下一步：'+action]
        lines+=['','已保留的原响应只是取得的资料，不代表来源或分红完整性已认证。旧报告与输入不覆盖；新尝试另存结果。']
        body='\n'.join(lines)
        (out/'基金资料未完成.md').write_text(body,'utf-8')
        (out/'基金资料未完成.html').write_text(render(body,'基金比较还差哪些资料'),'utf-8')
        return {'status':'blocked','message':'部分基金未取得可用历史，保留原响应与失败原因，未缩小比较池。',
                'nextSteps':['打开基金资料未完成.html，查看各只基金的处理方法。','同一入口使用--continue-from本结果目录及新的--out-dir；需补下载时显式加--online。'], 'failedCodes':failed}
    document={'asOf':as_of,'start':start,'rows':rows}
    comparison=publish(document,out/'comparison')
    return {'status':'partial','message':'基金共同区间比较报告已生成；完整产品评价尚未完成。',
            'headline':next((finding['conclusion'] for finding in comparison['findings'] if finding.get('conclusion')),None),
            'nextSteps':['打开comparison中的基金比较说明.html。','不同风格与未知币种不视为同类；基准、持仓、经理和分红完整性另核。'],
            'sourceVerification':'not-verified', 'currencyVerification':'not-verified', 'requestedCodes':codes}
