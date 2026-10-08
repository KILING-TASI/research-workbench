"""Evidence-aware research entry points usable without opening the workbench."""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import sys
from urllib.parse import urlparse

def read(path):
    from collection_validation import reject_constant,finite_json_float
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('输入JSON存在重复字段：'+key)
            result[key]=value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def date(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('日期须为YYYY-MM-DD')
    return dt.date.fromisoformat(value)

def save(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError('输出文件已存在，首次研究依据不覆盖，请使用新文件名')
    with path.open('x', encoding='utf-8') as handle:
        json.dump(document, handle, ensure_ascii=False, indent=2, allow_nan=False)

def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def collect(workspace, kind, codes, as_of, refresh=False):
    date(as_of)
    workspace=Path(workspace).resolve()
    if kind not in ['stock','fund','etf'] or not isinstance(refresh,bool):raise ValueError('无效类型或刷新参数')
    if not codes or len(set(codes)) != len(codes) or any(not re.fullmatch(r'\d{6}', c) for c in codes):
        raise ValueError('证券代码须为不重复的六位数字')
    folder = {'stock': 'stock-market', 'fund': 'fund-market', 'etf': 'etf-sector-rotation'}[kind]
    assets = workspace / 'outputs' / folder / 'assets'
    universe_path = assets / ('market-official.json' if kind == 'etf' else 'data.json')
    detail_path = assets / {'stock':'research-data.json','fund':'detail-data.json','etf':'selection-data.json'}[kind]
    required_scripts = {'stock':['refresh_research.py','enrich_research.py','refresh_research_gaps.py'],'fund':['refresh_details.py'],'etf':['refresh_selection.py']}[kind]
    complete = universe_path.is_file() and detail_path.is_file()
    if refresh:complete = complete and all((assets.parent/'scripts'/name).is_file() for name in required_scripts)
    if not complete:
        from portable_collect import collect as portable
        return portable(workspace, kind, codes, as_of, refresh)
    universe = read(assets / ('market-official.json' if kind == 'etf' else 'data.json'))['rows']
    if not isinstance(universe,list) or any(not isinstance(r,dict) or not isinstance(r.get('code'),str) or not re.fullmatch(r'\d{6}',r['code']) for r in universe):raise ValueError('项目标的库须为六位代码对象列表')
    if len({r['code'] for r in universe})!=len(universe):raise ValueError('项目标的库代码重复，须核对身份，不能静默覆盖')
    by_code = {r['code']: r for r in universe}
    missing_codes = [c for c in codes if c not in by_code]
    if missing_codes:
        from portable_collect import collect as portable
        fallback = portable(workspace, kind, missing_codes, as_of, refresh)
        known_codes = [c for c in codes if c in by_code]
        if not known_codes:
            return fallback
        known = collect(workspace, kind, known_codes, as_of, refresh)
        merged = {row['code']:row for row in known['rows']+fallback['rows']}
        return {**known, 'mode':'project-with-standalone-fallback',
                'rows':[merged[c] for c in codes], 'standaloneFallbackCodes':missing_codes,
                'fallbackScope':'未收录标的使用独立入口逐项核对身份；基础资料范围和缺口按各行说明，不扩大为完整财报或公告覆盖'}
    runs = []
    if refresh:
        scripts = {'stock': ['refresh_research.py', 'enrich_research.py', 'refresh_research_gaps.py'],
                   'fund': ['refresh_details.py'], 'etf': ['refresh_selection.py']}[kind]
        for script in scripts:
            try:
                run = subprocess.run([sys.executable, str(assets.parent / 'scripts' / script), '--codes', ','.join(codes)],
                                     cwd=workspace, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
                runs.append({'script': script, 'exitCode': run.returncode, 'log': (run.stdout + run.stderr)[-3000:]})
                if run.returncode:
                    break
            except OSError as exc:
                runs.append({'script':script,'error':str(exc)})
                break
            except subprocess.TimeoutExpired:
                runs.append({'script': script, 'error': '超时，停止后续刷新，保留缓存'})
                break
    detail = read(assets / {'stock': 'research-data.json', 'fund': 'detail-data.json', 'etf': 'selection-data.json'}[kind])
    details = detail.get({'stock': 'stocks', 'fund': 'funds', 'etf': 'rows'}[kind], {})
    refresh_errors=[r for r in runs if r.get('error') or r.get('exitCode',0)!=0]
    rows = []
    for code in codes:
        item = details.get(code, {})
        history = [r for r in item.get('history', []) if date(r['date']) <= date(as_of)]
        financials = item.get('financials', {})
        facts = [r for r in financials.get('rows', []) if r.get('period') and r.get('publishedAt')
                 and r['period'] <= as_of and r['publishedAt'][:10] <= as_of]
        announcements = [r for r in item.get('announcements', []) if r.get('date') and r['date'] <= as_of]
        rows.append({'code': code, 'kind': kind, 'identity': {k: by_code[code].get(k) for k in ['code','name','type','industry','exchange','currency']}, 'marketObservation': by_code[code] if by_code[code].get('asOf') and by_code[code]['asOf']<=as_of else None, 'history': history,
                     'financials': facts, 'financialSource': financials.get('source'),
                     'announcements': announcements, 'quote': {k:item[k] for k in ['asOf','quoteAt','dayAmount','spread','source','bid','ask','avgAmount20','amountWindow'] if k in item} if kind == 'etf' and item.get('asOf') and item['asOf'] <= as_of else None,
                     'errors': refresh_errors or item.get('errors') or item.get('error'), 'cacheRetained':bool(refresh_errors), 'retrievedAt': item.get('retrievedAt') or item.get('historyUpdatedAt'),
                     'source': item.get('source'),
                     'historyBasis': 'nav-with-distributions' if kind == 'fund' else item.get('adjustment'),
                     'gaps': (['财务字段尚未逐项公告核验'] if kind == 'stock' else ['费用和基准覆盖须单独核实']),
                     'pointInTime': '按所属日和已知发布日过滤；当前修订数据不等于当时冻结快照'})
    return {'type': 'research-bundle', 'version': 1, 'asOf': as_of, 'refreshAttempted': refresh,
            'runs': runs, 'rows': rows, 'conclusion': '数据研究档案，不直接产生买卖结论'}

def collect_batch(workspace, document):
    from batch_collect import run
    return run(workspace, document, collect)


def series(history, as_of, basis):
    if basis not in ['nav-with-distributions', 'qfq', 'total-return']:
        raise ValueError('总收益比较需净值分红或明确复权口径')
    if not isinstance(history,list) or any(not isinstance(r,dict) or 'date' not in r for r in history):raise ValueError('历史须为含日期的观测列表')
    rows = sorted((r for r in history if date(r['date']) <= date(as_of)), key=lambda r: r['date'])
    if len({r['date'] for r in rows}) != len(rows):
        raise ValueError('历史日期重复')
    wealth, result = 1.0, {}
    previous = None
    for row in rows:
        value = row.get('nav') if basis == 'nav-with-distributions' else row.get('close')
        if not finite(value) or value <= 0:
            raise ValueError('无效净值或价格')
        cash = 0
        if row.get('distribution'):
            match = re.fullmatch(r'分红：每份派现金(\d+(?:\.\d+)?)元', row['distribution']) if isinstance(row['distribution'],str) else None
            if basis != 'nav-with-distributions' or not match:
                raise ValueError('分红或拆分口径不明')
            cash = float(match[1])
            if not finite(cash):raise ValueError('分红数值无效')
            if not finite(value+cash):raise ValueError('净值与分红合计溢出')
        if previous is not None:
            wealth *= (value + cash) / previous
            if not finite(wealth) or wealth<=0:raise ValueError('收益序列溢出或超出有效数值范围')
        result[row['date']] = wealth
        previous = value
    return result

def metrics(values):
    if len(values) < 2:
        raise ValueError('有效历史不足')
    if any(not finite(v) or v<=0 for v in values):raise ValueError('指标输入须为有限正数')
    returns = [b/a-1 for a, b in zip(values, values[1:])]
    if any(not finite(v) for v in returns):raise ValueError('收益指标溢出')
    peak, drawdown = values[0], 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = min(drawdown, value/peak-1)
    result={'totalReturnPct': (values[-1]/values[0]-1)*100, 'drawdownPct': drawdown*100,
            'annualizedVolPct': statistics.stdev(returns)*math.sqrt(252)*100 if len(returns) >= 120 else None,
            'observationCount': len(returns), 'annualizationAssumption': '交易日观测，252；不足120组不输出年化波动'}
    if any(v is not None and not finite(v) for k,v in result.items() if k.endswith('Pct')):raise ValueError('收益指标溢出')
    return result

def compare(document):
    cutoff=date(document['asOf']);requested_start=document.get('start')
    if requested_start is not None and date(requested_start)>cutoff:raise ValueError('比较起始日期晚于截止日')
    if len({r['code'] for r in document['rows']}) != len(document['rows']):
        raise ValueError('比较代码重复')
    if len(document['rows']) < 2:
        raise ValueError('至少两个标的，或一个标的加基准')
    groups = {r.get('comparisonGroup') for r in document['rows']}
    if None in groups or '' in groups or len(groups) != 1:
        raise ValueError('需明确同类/同指数比较组，不能混排')
    if any(row.get('currency') is not None and (not isinstance(row['currency'],str) or not re.fullmatch(r'[A-Z]{3}',row['currency'])) for row in document['rows']):raise ValueError('币种需三位大写代码')
    currencies={r.get('currency') for r in document['rows'] if r.get('currency')}
    if len(currencies)>1:raise ValueError('比较币种不一致，须先提供统一计价序列')
    dates = None
    all_series = []
    for row in document['rows']:
        history=row['history']
        if requested_start is not None:history=[h for h in history if date(h['date'])>=date(requested_start)]
        observed = series(history, document['asOf'], row['basis'])
        all_series.append(observed)
        dates = set(observed) if dates is None else dates & set(observed)
    dates = sorted(d for d in dates if requested_start is None or d>=requested_start)
    if len(dates) < 2:
        raise ValueError('没有共同可比区间')
    results = [{'code': row['code'], **metrics([observed[d] for d in dates])}
               for row, observed in zip(document['rows'], all_series)]
    benchmark = document.get('benchmarkCode')
    base = next((r for r in results if r['code'] == benchmark), None)
    if benchmark and base is None:
        raise ValueError('基准不在共同数据中')
    alignment=[]
    union_dates={d for observed in all_series for d in observed if dates[0]<=d<=dates[-1]}
    alignment_loss=len(union_dates)-len(dates)
    for row,input_row,observed in zip(results,document['rows'],all_series):
        within=[d for d in observed if dates[0]<=d<=dates[-1]]
        excluded=len(within)-len(dates)
        from observation_calendar import assess
        calendar_check=assess(sorted(observed),requested_start or min(observed),document['asOf'],input_row.get('calendar'),input_row.get('calendarMarket'))
        calendar_gap=input_row.get('calendar') is not None and calendar_check['status']!='dates-aligned'
        if input_row.get('frequency')!='trading_day' or alignment_loss:row['annualizedVolPct']=None
        row['volatilityUnavailableReason']=('共同日期排除了比较样本区间内观测，收益间隔不一致，未输出年化波动' if alignment_loss else '未声明交易日频率' if input_row.get('frequency')!='trading_day' else '共同收益观测不足120组' if row['observationCount']<120 else None)
        if calendar_gap:
            row['annualizedVolPct']=None
            row['volatilityUnavailableReason']='所提供日历存在观测缺口或适用性未确认，不能按完整交易日序列年化'
        input_dates=[h['date'] for h in input_row['history'] if date(h['date'])<=cutoff and (requested_start is None or h['date']>=requested_start)]
        alignment.append({'code':input_row['code'],'observationsWithinCommonWindow':len(within),'commonObservations':len(dates),'excludedObservations':excluded,'calendarCompleteness':'not-verified','inputWasReordered':input_dates!=sorted(input_dates)})
        alignment[-1]['calendarCheck']=calendar_check
        alignment[-1]['calendarCompleteness']=calendar_check['status']
        row['excessReturnPctPoints'] = row['totalReturnPct'] - base['totalReturnPct'] if base else None
    basis_note = '共同日期；共同日期之外的波动与低点未纳入，回撤仅基于对齐后观测；当前数据修订不构成点时回测'
    if any(row['basis'] == 'qfq' for row in document['rows']):
        basis_note += '；含前复权价格序列，只是价格变动代理，不等同总收益'
    return {'type': 'research-comparison', 'start': dates[0], 'end': dates[-1], 'rows': results,
            'currencyVerification':'input-declared-original-unverified' if all(row.get('currency') for row in document['rows']) else 'currency-missing-not-verified',
            'requestedStart':requested_start,'alignment':alignment,'basis': basis_note, 'groupVerification': '比较组为输入声明，需核验分类与指数', 'completeCompositeScore': False}

def evidence(record):
    required = ['securityCode', 'field', 'value', 'unit', 'currency', 'period', 'publishedAt',
                'statementScope', 'periodBasis', 'sourceUrl', 'documentPath', 'page', 'excerpt', 'reviewer']
    if any(record.get(k) is None or record.get(k) == '' for k in required):
        raise ValueError('缺少证券、数值、单位、日期、口径或原文核验字段')
    if not re.fullmatch(r'\d{6}', record['securityCode']) or not finite(record['value']):
        raise ValueError('证券代码或数值无效')
    for field in ['period', 'publishedAt']:
        date(record[field])
    if record['publishedAt'] < record['period'] or type(record['page']) is not int or record['page'] < 1:
        raise ValueError('公告日或页码无效')
    source = urlparse(record['sourceUrl'])
    if source.scheme != 'https' or not source.hostname or source.username or source.password or re.search(r'[\s\x00-\x1f\x7f]',record['sourceUrl']):
        raise ValueError('来源须为HTTPS原文链接')
    path = Path(record['documentPath'])
    blob = path.read_bytes()
    if not blob.startswith(b'%PDF-'):
        raise ValueError('原文文件不是PDF')
    return {**record, 'type':'financial-evidence-record', 'factorEligible':False, 'documentSha256': hashlib.sha256(blob).hexdigest(),
            'verification': '核验人员登记；程序仅检查证据完整性，不自动证明原文与数值一致',
            'recordedAt': dt.datetime.now(dt.timezone.utc).isoformat()}

def validate_predictions(document):
    accepted, rejected = [], []
    signatures={(r.get('unit'),r.get('modelVersion')) for r in document['rows']}
    if len(signatures)>1 or any(not u or not v for u,v in signatures):raise ValueError('误差比较须为同单位同模型版本')
    ids=[r.get('id') for r in document['rows']]
    if any(not i for i in ids) or len(set(ids))!=len(ids):raise ValueError('预测记录ID缺失或重复')
    for row in document['rows']:
        try:
            if not all(finite(row.get(k)) for k in ['prediction', 'actual']) or row['actual'] <= 0:
                raise ValueError('数值无效')
            if not row.get('frozenAt') or not row.get('actualPublishedAt'):
                raise ValueError('缺少冻结或实际发布时间')
            frozen = dt.datetime.fromisoformat(row['frozenAt']); published = dt.datetime.fromisoformat(row['actualPublishedAt'])
            if not frozen.tzinfo or not published.tzinfo or frozen >= published:
                raise ValueError('预测未在实际结果公开前冻结')
            if not row.get('inputMaxPublishedAt'):
                raise ValueError('缺少输入可得时间')
            input_time = dt.datetime.fromisoformat(row['inputMaxPublishedAt'])
            if not input_time.tzinfo or input_time > frozen:
                raise ValueError('输入含未来信息')
            accepted.append(row)
        except (ValueError, KeyError, TypeError) as error:
            rejected.append({'id': row.get('id'), 'reason': str(error)})
    errors = [abs(r['prediction']-r['actual']) for r in accepted]
    ordered = sorted(errors)
    return {'type': 'frozen-prediction-validation', 'accepted': len(accepted), 'rejected': rejected,
            'MAE': statistics.mean(errors) if errors else None,
            'P90AbsoluteError': ordered[math.ceil(.9*len(ordered))-1] if ordered else None,
            'maxAbsoluteError': max(errors) if errors else None,
            'underestimationRate': sum(r['prediction'] < r['actual'] for r in accepted)/len(accepted) if accepted else None,
            'modelProven': False, 'limitations': '冻结时间需外部证据核验；只评估给定样本，不自动调参，不证明投资策略有效'}

def portfolio(document):
    rows = document['holdings']
    date(document['asOf'])
    if not document.get('baseCurrency') or any(r.get('marketValueCurrency')!=document['baseCurrency'] for r in rows):raise ValueError('持仓市值须统一计价币种，先完成汇率换算')
    if not rows or len({r['code'] for r in rows}) != len(rows):
        raise ValueError('持仓为空或代码重复，请先合并')
    for row in rows:
        if not finite(row['marketValue']) or row['marketValue'] <= 0 or abs(row['marketValue']*100-round(row['marketValue']*100)) > 1e-5:
            raise ValueError('持仓市值须为正数且最多两位小数')
    total = sum(r['marketValue'] for r in rows)
    if not math.isfinite(total) or total*100>2**53-1:raise ValueError('持仓金额超出精确计算范围')
    exposure = {}
    result = []
    for row in rows:
        weight = row['marketValue']/total
        for field in ['assetClass', 'industry', 'currency']:
            key = field + ':' + (row.get(field) or '未知')
            exposure[key] = exposure.get(key, 0) + weight
        result.append({**row, 'weight': weight})
    shock = document.get('shocks', {})
    complete = all(r.get('assetClass') in shock and finite(shock[r['assetClass']]) and -100 <= shock[r['assetClass']] <= 100 for r in rows)
    loss = sum(r['marketValue']*shock[r['assetClass']]/100 for r in rows) if complete else None
    return {'type': 'actual-portfolio-diagnostic', 'asOf': document['asOf'], 'totalMarketValue': total,
            'rows': result, 'exposures': exposure, 'HHI': sum(r['weight']**2 for r in result),
            'stressPnL': loss, 'stressComplete': complete,
            'limitations': '输入市值、分类和压力假设由用户提供；未接入底层穿透、成本和交易约束，不输出买卖指令'}

def review(before, after):
    if before.get('type') != after.get('type'):
        raise ValueError('复查档案类型不同')
    def flatten(value, prefix=''):
        if isinstance(value, dict):
            return {k: v for key, child in value.items() for k, v in flatten(child, prefix+'.'+key).items()}
        if isinstance(value, list):
            result = {}
            seen = set()
            for index, child in enumerate(value):
                ident = (child.get('code') or child.get('id')) if isinstance(child, dict) else None
                key = str(ident or index)
                if key in seen:
                    raise ValueError('版本对照列表身份重复，无法唯一对齐：'+prefix+'['+key+']')
                seen.add(key)
                result.update(flatten(child, prefix+'['+key+']'))
            return result
        return {prefix: value}
    a, b = flatten(before), flatten(after)
    changes = [{'field': k, 'before': a.get(k), 'after': b.get(k)} for k in sorted(set(a)|set(b)) if a.get(k) != b.get(k)]
    return {'type': 'research-review', 'reviewedAt': dt.datetime.now(dt.timezone.utc).isoformat(),
            'beforeSha256': hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest(),
            'changes': changes, 'requiresJudgment': True, 'conclusion': '数据变化不自动等于原判断失效，需核对失效条件及反方证据'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path.cwd())
    parser.add_argument('--out', type=Path, required=True)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('collect'); p.add_argument('--kind', choices=['stock','fund','etf','bond','convertible','government-bond','credit-bond'], required=True)
    p.add_argument('--start',default='2000-01-01');p.add_argument('--market',choices=['0','1']);p.add_argument('--codes', required=True); p.add_argument('--as-of', required=True); p.add_argument('--refresh', action='store_true')
    for name in ['collect-batch', 'compare', 'evidence', 'validate', 'portfolio', 'replacement','context-create','context-revise','run-template','impact','template-diff','gap-analysis','knowledge-add','knowledge-show','cross-validate','cross-period-review','source-list','source-plan','source-collect','events','event-monitor','research-question']:
        p = sub.add_parser(name); p.add_argument('input', type=Path)
    p = sub.add_parser('search');p.add_argument('query');p.add_argument('--kind');p.add_argument('--online',action='store_true');p.add_argument('--limit',type=int,default=20)
    p = sub.add_parser('review'); p.add_argument('before', type=Path); p.add_argument('after', type=Path)
    args = parser.parse_args()
    if args.out.exists():raise ValueError('输出已存在，拒绝执行采集或覆盖')
    if args.command == 'search':
        from security_search import search
        result = search(args.workspace.resolve(),args.query,args.kind,args.online,args.limit)
    elif args.command == 'collect-batch':
        result = collect_batch(args.workspace.resolve(), read(args.input))
    elif args.command == 'collect':
        result = collect_batch(args.workspace.resolve(), {'asOf':args.as_of,'refresh':args.refresh,'requests':[{'kind':args.kind,'code':c,'start':args.start,**({'market':args.market} if args.market else {})} for c in args.codes.split(',')]})
    elif args.command=='research-question':
        from research_question import run as question_run
        result=question_run(read(args.input),args.workspace.resolve())
    elif args.command in ['events','event-monitor']:
        from event_research import run as event_run,monitor as event_monitor
        spec=read(args.input)
        result=event_run(spec,args.workspace.resolve()) if args.command=='events' else event_monitor(spec)
    elif args.command in ['source-list','source-plan','source-collect']:
        from source_registry import registry,plan,collect as source_collect
        spec=read(args.input)
        result=registry() if args.command=='source-list' else plan(spec) if args.command=='source-plan' else source_collect(spec,args.workspace.resolve(),collect_batch)
    elif args.command in ['context-create','context-revise','run-template','impact','template-diff']:
        from research_workflow import context,revise,run_template,impact,compare_results
        spec=read(args.input)
        if args.command=='context-create':result=context(spec)
        elif args.command=='context-revise':result=revise(read(spec['previousPath']),spec['changes'])
        elif args.command=='run-template':result=run_template(spec,args.workspace.resolve())
        elif args.command=='template-diff':result=compare_results(read(spec['beforePath']),read(spec['afterPath']))
        else:result=impact(read(spec['resultPath']),spec.get('newContextPath'),spec.get('replacements'))
    elif args.command == 'cross-period-review':
        from cross_period_review import review as period_review
        result=period_review(read(args.input))
    elif args.command in ['gap-analysis','knowledge-add','knowledge-show','cross-validate']:
        from research_evidence import gap_analysis,knowledge_add,knowledge_show,cross_validate
        spec=read(args.input)
        result={'gap-analysis':lambda:gap_analysis(spec),
                'knowledge-add':lambda:knowledge_add(spec,args.workspace.resolve()),
                'knowledge-show':lambda:knowledge_show(spec,args.workspace.resolve()),
                'cross-validate':lambda:cross_validate(spec,args.workspace.resolve())}[args.command]()
    elif args.command == 'review':
        result = review(read(args.before), read(args.after))
    elif args.command == 'replacement':
        from replacement_research import evaluate
        result = evaluate(read(args.input))
    else:
        result = {'compare': compare, 'evidence': evidence, 'validate': validate_predictions, 'portfolio': portfolio}[args.command](read(args.input))
    if args.command in ['template-diff','impact']:
        from research_workflow import version_comparison_markdown
        from research_brief_html import render
        md_path=args.out.with_suffix('.md');html_path=args.out.with_suffix('.html')
        if md_path.exists() or html_path.exists():raise FileExistsError('研究复查或版本对照报告已存在')
    save(args.out, result)
    if args.command in ['template-diff','impact']:
        if args.command=='impact':
            from research_workflow import impact_markdown
            md=impact_markdown(result)
        else:md=version_comparison_markdown(result)
        md_path.write_text(md,encoding='utf8');html_path.write_text(render(md,title='研究复查结果' if args.command=='impact' else '研究版本对照'),encoding='utf8')
    print(json.dumps({'output': str(args.out), 'type': result.get('type', 'evidence-record')}, ensure_ascii=False))

if __name__ == '__main__':
    main()
