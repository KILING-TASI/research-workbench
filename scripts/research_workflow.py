"""Versioned research context, reproducible fund comparison and dependency audit."""
import datetime as dt
import hashlib
import json
import math
import re
from pathlib import Path
from collection_validation import unique_pairs,reject_constant,finite_json_float

SCHEMA = 1
ENGINE = 'research-workflow-1.0'
CONTEXT_FIELDS = ('baseCurrency','frequency','dividendTreatment','asOf','benchmark','riskFreeRate','annualization','missingData','timezone')
DEPENDENCIES = {
    'portfolio-contribution-review': {'baseCurrency','frequency','dividendTreatment','asOf','riskFreeRate','annualization','missingData'},
    'etf-closing-premium-review': {'baseCurrency','asOf','dividendTreatment'},
    'fund-comparison': {'baseCurrency','frequency','dividendTreatment','asOf','benchmark','annualization','missingData','timezone'},
    'portfolio-diagnostic': {'baseCurrency','asOf'},
    'holdings-snapshot-review': {'baseCurrency','asOf'},
    'company-financial-review': {'baseCurrency','asOf'},
    'macro-observation-review': {'baseCurrency','asOf','dividendTreatment'},
    'event-price-review': {'baseCurrency','asOf','dividendTreatment'},
    'report-reading-review': {'asOf'},
    'report-translation-review': {'asOf'},
    'company-scenario-review': {'baseCurrency','asOf'},
    'industry-scenario-review': {'asOf'},
    'exit-scenario-review': {'baseCurrency','asOf'},
    'fof-lookthrough-review': {'baseCurrency','asOf'},
    'portfolio-model-review': {'baseCurrency','asOf','frequency','dividendTreatment','annualization'}
}

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')

def digest(value):return hashlib.sha256(canonical(value)).hexdigest()

def file_digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)

def context(payload):
    if not isinstance(payload,dict):raise ValueError('参数上下文须为对象')
    unknown=set(payload)-set(CONTEXT_FIELDS)-{'sessionId','revision','type','schemaVersion','contextHash','changes','createdAt','parentHash'}
    if unknown:raise ValueError('未知上下文字段: '+','.join(sorted(unknown)))
    session=payload.get('sessionId')
    if not isinstance(session,str) or not re.fullmatch('[A-Za-z0-9_-]{1,80}',session):raise ValueError('sessionId格式错误')
    currency=payload.get('baseCurrency')
    if not isinstance(currency,str) or not re.fullmatch('[A-Z]{3}',currency):raise ValueError('币种须ISO三位大写代码')
    freq=payload.get('frequency')
    if freq not in ('trading_day','weekly','monthly'):raise ValueError('frequency不支持')
    if payload.get('dividendTreatment') not in ('reinvest','cash','price_only'):raise ValueError('分红口径不支持')
    dt.date.fromisoformat(payload['asOf'])
    benchmark=payload.get('benchmark')
    if benchmark is not None:
        if not isinstance(benchmark,dict) or benchmark.get('type') not in ('fund','index') or not isinstance(benchmark.get('code'),str) or not benchmark['code']:
            raise ValueError('基准须明确对象类型和代码')
        if not benchmark.get('basis'):raise ValueError('基准须明确价格或总收益口径')
    rate=payload.get('riskFreeRate')
    if isinstance(rate,bool) or not isinstance(rate,(int,float)) or not math.isfinite(rate):raise ValueError('无风险利率无效')
    annual=payload.get('annualization')
    if type(annual)!=int or annual<1 or annual>366:raise ValueError('annualization无效')
    if payload.get('missingData') not in ('common_dates','fail'):raise ValueError('缺失处理仅支持共同日期或失败')
    if payload.get('timezone') not in ('Asia/Shanghai','UTC'):raise ValueError('时区不支持')
    clean={k:payload[k] for k in CONTEXT_FIELDS}
    return {'type':'research-context','schemaVersion':SCHEMA,'sessionId':session,
            'revision':payload.get('revision',1),'parameters':clean,'contextHash':digest(clean),
            'createdAt':dt.datetime.now(dt.timezone.utc).isoformat()}

def revise(old,changes):
    if old.get('type')!='research-context':raise ValueError('原文件不是研究上下文')
    if not isinstance(changes,dict) or not changes:raise ValueError('变更不能为空')
    if set(changes)-set(CONTEXT_FIELDS):raise ValueError('不能修改sessionId或未知字段')
    before=old['parameters'];merged={**before,**changes,'sessionId':old['sessionId']}
    new=context(merged);new['revision']=old['revision']+1;new['parentHash']=old['contextHash']
    new['changes']=[{'field':k,'before':before[k],'after':new['parameters'][k]} for k in sorted(changes) if before[k]!=new['parameters'][k]]
    return new

def input_node(path,role):
    p=Path(path).resolve()
    return {'role':role,'path':str(p),'sha256':file_digest(p),'bytes':p.stat().st_size}

def code_node(name):
    p=Path(__file__).parent/name
    return {'module':name,'sha256':file_digest(p)}

def run_fund_comparison(manifest,workspace):
    from research_pipeline import collect_batch,compare
    if manifest.get('template')!='fund-comparison':raise ValueError('仅支持fund-comparison模板')
    ctx_path=Path(manifest['contextPath']);ctx=load(ctx_path)
    if ctx.get('type')!='research-context' or ctx.get('contextHash')!=digest(ctx.get('parameters')):raise ValueError('研究上下文损坏或曾被直接修改')
    params=ctx['parameters'];codes=manifest.get('codes')
    if not isinstance(codes,list) or not 2<=len(codes)<=10 or any(not isinstance(c,str) or not re.fullmatch(r'\d{6}',c) for c in codes) or len(set(codes))!=len(codes):
        raise ValueError('基金对比需要2至10个不同的六位代码')
    group=manifest.get('comparisonGroup')
    if not isinstance(group,str) or not group.strip():raise ValueError('须明确同类比较组')
    if params['dividendTreatment']!='reinvest':raise ValueError('基金模板目前仅支持可验证的现金分红再投口径')
    if params['frequency']!='trading_day':raise ValueError('基金模板目前只支持日度净值观察')
    if params['baseCurrency']!='CNY':raise ValueError('基金模板未接入外汇转换，仅支持CNY')
    if params['annualization']!=252:raise ValueError('当前基金比较引擎按252个交易日年化，参数须与计算一致')
    if params['missingData']!='common_dates':raise ValueError('基金模板目前仅支持共同日期比较；严格完整日历验收尚未接入')
    bench=params.get('benchmark')
    if bench and (bench['code'] not in codes or bench['basis']!='nav-with-distributions'):
        raise ValueError('基金基准须在候选内，且明确为净值含现金分红口径')
    nodes=[input_node(ctx_path,'context')]
    bundle_path=manifest.get('bundlePath')
    if bundle_path:
        bundle=load(bundle_path);nodes.append(input_node(bundle_path,'collected-bundle'))
    else:
        bundle=collect_batch(Path(workspace),{'asOf':params['asOf'],'refresh':manifest.get('refresh',False),
            'requests':[{'kind':'fund','code':c} for c in codes]})
        detail=Path(workspace)/'outputs/fund-market/assets/detail-data.json'
        catalog=Path(workspace)/'outputs/fund-market/assets/data.json'
        if detail.exists():nodes.append(input_node(detail,'project-fund-detail'))
        if catalog.exists():nodes.append(input_node(catalog,'project-fund-catalog'))
        if not detail.exists():
            for code in codes:
                cache=Path(workspace)/'research-data/fund'/(code+'.json')
                if cache.exists():nodes.append(input_node(cache,'portable-fund-cache'))
    if bundle.get('asOf')!=params['asOf']:raise ValueError('数据包截止日与研究上下文不符')
    rows=bundle.get('rows',[])
    if not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows):raise ValueError('数据包记录列表无效')
    collected={}
    for row in rows:
        if row.get('kind')!='fund':continue
        code=row.get('code')
        if code not in codes or code in collected:raise ValueError('数据包基金身份重复或不属于本次比较')
        collected[code]=row
    if len(collected)!=len(codes):raise ValueError('数据包缺少所需基金')
    prepared=[];gaps=[];source_nodes=[]
    for code in codes:
        r=collected[code];history=r.get('history') or []
        reported_currency=(r.get('identity') or {}).get('currency')
        if reported_currency and reported_currency!='CNY':raise ValueError(code+'币种与上下文不一致；尚无自动汇率换算')
        source=r.get('source') or r.get('financialSource') or None
        source_nodes.append({'code':code,'sourceUrl':source,'retrievedAt':r.get('retrievedAt'),
             'historySha256':digest(history),'historyCount':len(history),'collectionStatus':r.get('collectionStatus'),
             'sourceVerification':r.get('sourceVerification','not-verified')})
        if r.get('errors'):gaps.append({'code':code,'reason':'采集存在错误或使用旧缓存','detail':str(r['errors'])[:500]})
        if r.get('retrievedAt') and str(r['retrievedAt'])[:10]>params['asOf']:
            gaps.append({'code':code,'reason':'数据抓取晚于研究截止日；本次为事后研究，不能作为当时冻结输入'})
        if not history:gaps.append({'code':code,'reason':'净值历史缺失'});continue
        if not source:gaps.append({'code':code,'reason':'历史来源URL缺失'})
        prepared.append({'code':code,'comparisonGroup':group,'basis':'nav-with-distributions',
                         'frequency':'trading_day','currency':'CNY','history':history})
    result=None
    if len(prepared)==len(codes):
        try:result=compare({'asOf':params['asOf'],'rows':prepared,'benchmarkCode':bench['code'] if bench else None})
        except (ValueError,KeyError,TypeError) as exc:gaps.append({'scope':'comparison','reason':str(exc)})
    else:gaps.append({'scope':'comparison','reason':'至少一个基金缺少可计算净值'})
    status='calculated-with-gaps' if result and gaps else 'calculated' if result else 'needs-data'
    code_versions=[code_node(n) for n in ['research_pipeline.py','research_workflow.py','batch_collect.py','portable_collect.py']]
    metric_lineage=[]
    if result:
        by_source={s['code']:s for s in source_nodes}
        for row in result['rows']:
            for metric,value in row.items():
                if metric!='code':
                    metric_lineage.append({'output':row['code']+'.'+metric,'value':value,
                        'inputHistorySha256':by_source[row['code']]['historySha256'],
                        'commonDateSetSha256':digest([result['start'],result['end'],[s['historySha256'] for s in source_nodes]]),
                        'function':'research_pipeline.compare/metrics','parameters':{'asOf':params['asOf'],'annualization':252},
                        'codeSha256':code_versions[0]['sha256']})
    result_node={'id':'fund-comparison','function':'research_pipeline.compare','parameters':
        {'asOf':params['asOf'],'comparisonGroup':group,'benchmarkCode':bench['code'] if bench else None,
         'basis':'nav-with-distributions','frequency':'trading_day','annualization':252},
        'code':code_versions,
        'dependsOnFiles':[n['path'] for n in nodes],'dependsOnSources':[s['code'] for s in source_nodes],
        'outputSha256':digest(result) if result else None}
    output={'type':'research-template-result','schemaVersion':SCHEMA,'engineVersion':ENGINE,'template':'fund-comparison',
        'status':status,'contextSnapshot':ctx,'contextHash':ctx['contextHash'],
        'dataSnapshotSha256':digest(bundle),'result':result,'gaps':gaps,
        'lineage':{'files':nodes,'sources':source_nodes,'calculations':[result_node],'metrics':metric_lineage},
        'limits':['比较组由输入声明，未自动核验同类','第三方净值与分红信息未逐项原文核验',
          '历史计算不代表未来；参数变更需新结果文件，不覆盖原结论']}
    if manifest.get('previousResultPath'):
        output['previousResultImpact']=impact(load(manifest['previousResultPath']),str(ctx_path))
    return output

def run_portfolio_diagnostic(manifest):
    from research_pipeline import portfolio
    ctx_path=Path(manifest['contextPath']);holdings_path=Path(manifest['holdingsPath'])
    ctx=load(ctx_path)
    if ctx.get('type')!='research-context' or ctx.get('contextHash')!=digest(ctx.get('parameters')):raise ValueError('研究上下文损坏')
    supplied=load(holdings_path)
    if not isinstance(supplied,dict) or 'holdings' not in supplied:raise ValueError('缺少持仓')
    params=ctx['parameters']
    prepared={**supplied,'asOf':params['asOf'],'baseCurrency':params['baseCurrency']}
    result=portfolio(prepared)
    nodes=[input_node(ctx_path,'context'),input_node(holdings_path,'user-holdings-and-shocks')]
    versions=[code_node('research_pipeline.py'),code_node('research_workflow.py')]
    metrics=[{'output':k,'value':result.get(k),'inputSha256':nodes[1]['sha256'],
        'function':'research_pipeline.portfolio','codeSha256':versions[0]['sha256']}
        for k in ['totalMarketValue','HHI','stressPnL','stressComplete']]
    calc={'id':'portfolio-diagnostic','function':'research_pipeline.portfolio',
        'parameters':{'asOf':params['asOf'],'baseCurrency':params['baseCurrency']},
        'code':versions,'dependsOnFiles':[n['path'] for n in nodes],
        'outputSha256':digest(result)}
    output={'type':'research-template-result','schemaVersion':SCHEMA,'engineVersion':ENGINE,
        'template':'portfolio-diagnostic','status':'calculated' if result['stressComplete'] else 'calculated-with-gaps',
        'contextSnapshot':ctx,'contextHash':ctx['contextHash'],'result':result,
        'gaps':[] if result['stressComplete'] else [{'reason':'部分持仓类别缺少压力假设；组合损益留空'}],
        'lineage':{'files':nodes,'sources':[{'role':'user-supplied','verification':'not-verified'}],
                   'calculations':[calc],'metrics':metrics},
        'limits':['持仓金额、分类和情景冲击由使用者提供，未自动核验账户或穿透底层',
                  '一次冲击损益不等于未来回撤或投资操作建议']}
    if manifest.get('previousResultPath'):
        output['previousResultImpact']=impact(load(manifest['previousResultPath']),str(ctx_path))
    return output

def quarter_review_markdown(reviews,companies):
    names={c['code']:c['metadata'].get('name',c['code']) for c in companies}
    labels={'supported-inputs-matched':'输入已匹配','supported-inputs-matched-with-comparability-warning':'数值匹配，跨期口径待复核','not-verified':'输入尚未完整确认'}
    lines=['# 单季度计算依据','', '以下逐项说明本期单季及同比、环比基数的原文核验。仅覆盖七项支持字段，不代表全部财务科目或经营原因已确认。']
    indexed={r['code']:r for r in reviews}
    for code,name in names.items():
        lines+=['','## '+name]
        if code not in indexed:lines.append('本次未提供相邻期核验，不能把已完成计算视为输入已确认。');continue
        r=indexed[code]
        lines+=['','|指标|本期输入|同比基数|环比基数|','|---|---|---|---|']
        for field in r['fields']:
            lines.append('|'+field['label']+'|'+'|'.join(labels.get(field['parts'][part]['status'],'输入尚未完整确认') for part in ['current','yoy','qoq'])+'|')
            for part in field['parts'].values():
                for dep in part['dependencies']:
                    if dep['pages']:
                        links='、'.join('[第'+str(page)+'页](quarter-sources/'+code+'-'+dep['period']+'.pdf#page='+str(page)+')' for page in dep['pages'])
                        lines.append(field['label']+'：'+dep['period']+'原文'+links+'。')
        for warning in r.get('reportMetadataWarnings',[]):lines.append(warning['period']+'：'+warning['warning'])
        for warning in r.get('comparabilityWarnings',[]):lines.append(warning['period']+'：'+warning['warning'])
    return '\n'.join(lines)

def run_company_financial_review(manifest):
    from company_financial_report import run as commentary
    from financial_source_binding import bound_archives
    ctx_path=Path(manifest['contextPath']);ctx=load(ctx_path)
    if ctx.get('type')!='research-context' or ctx.get('contextHash')!=digest(ctx.get('parameters')):raise ValueError('研究上下文损坏')
    link={k:manifest[k] for k in ['financialResult','originalResult','archives']}
    narrative_paths=[]
    for key in ['interpretations','comparisons']:
        path=Path(manifest[key+'Path']) if manifest.get(key+'Path') else None
        if path:
            value=load(path)
            if not isinstance(value,list):raise ValueError(key+'需列表')
            link[key]=value;narrative_paths.append((path,'research-'+key))
    fin=load(link['financialResult']);original=load(link['originalResult']);params=ctx['parameters']
    archives,_=bound_archives(fin,link['archives'])
    if fin['period']>params['asOf']:raise ValueError('财报期晚于研究截止日')
    for a in archives.values():
        if a['asOf']!=params['asOf']:raise ValueError('财务档案截止日与研究上下文不同，需重建计算')
    if original.get('asOf')!=params['asOf']:raise ValueError('原文归档截止日与研究上下文不同')
    if any(c['metadata']['currency']!=params['baseCurrency'] for c in fin['companies']):raise ValueError('财务币种与研究上下文不同，不自动汇兑')
    quarter_paths=manifest.get('quarterReviewResults',[])
    if not isinstance(quarter_paths,list) or len(quarter_paths)!=len(set(quarter_paths)):raise ValueError('多期核验结果须为不重复的文件列表')
    quarter_reviews=[];quarter_nodes=[];seen=set()
    if quarter_paths:
        from quarter_original_review import verified_saved_result
        companies={c['code']:c for c in fin['companies']}
        for path in quarter_paths:
            saved=load(path);code=saved.get('code')
            if code not in companies or code in seen:raise ValueError('多期核验公司重复或不属于研究样本')
            seen.add(code)
            reviewed=verified_saved_result(path,archives[code],companies[code]['metadata'],fin['period'])
            quarter_reviews.append(reviewed);quarter_nodes.append(input_node(Path(path),'quarter-original-review'))
            for original_path in reviewed['input']['originalResults']:quarter_nodes.append(input_node(Path(original_path),'quarter-original-archive'))
            for binding in reviewed['originalBindings']:quarter_nodes.append(input_node(Path(binding['path']),'quarter-original-pdf'))
    result=commentary(link,Path(manifest['outDir']))
    if quarter_paths:
        result['quarterInputReviews']=quarter_reviews
        import shutil
        from research_brief_html import render
        out=Path(manifest['outDir']);(out/'quarter-sources').mkdir()
        for reviewed in quarter_reviews:
            for binding in reviewed['originalBindings']:shutil.copy2(binding['path'],out/'quarter-sources'/(reviewed['code']+'-'+binding['period']+'.pdf'))
        text=quarter_review_markdown(quarter_reviews,fin['companies'])
        (out/'单季计算依据.md').write_text(text,encoding='utf8')
        (out/'单季计算依据.html').write_text(render(text,title='单季度计算依据'),encoding='utf8')
        result['quarterReviewReport']='单季计算依据.html'
        result['envelopeSha256']=digest({k:v for k,v in result.items() if k!='envelopeSha256'})
    paths=[(ctx_path,'context'),(Path(link['financialResult']),'quarter-financial'),(Path(link['originalResult']),'original-report-archive')]+[(Path(p),'financial-archive') for p in link['archives']]
    nodes=[input_node(p,role) for p,role in paths]+[input_node(Path(b['path']),'original-pdf') for b in result.get('originalBindings',[])]
    nodes.extend(input_node(path,role) for path,role in narrative_paths)
    nodes.extend(quarter_nodes)
    nodes=list({(n['role'],n['path']):n for n in nodes}.values())
    versions=[code_node(m) for m in ['research_workflow.py','company_financial_report.py','company_report_batch.py','financial_source_binding.py','industry_financials.py','research_report_reading.py','research_brief_html.py']]
    gaps=[dict(code=c['code'],reason=g) for c in result['companies'] for g in c['gaps']]
    if quarter_paths:
        versions.append(code_node('quarter_original_review.py'))
        for code in set(archives)-seen:gaps.append(dict(code=code,reason='本次未提供该公司的相邻期原文核验结果'))
        for reviewed in quarter_reviews:
            for field in reviewed['fields']:
                for part,entry in field['parts'].items():
                    if entry['status']!='supported-inputs-matched':
                        part_label={'current':'本期','yoy':'同比基数','qoq':'环比基数'}[part]
                        detail='跨期口径存在可比性提示' if entry['status']=='supported-inputs-matched-with-comparability-warning' else '相邻期输入尚未完整确认'
                        gaps.append(dict(code=reviewed['code'],reason=field['label']+'（'+part_label+'）：'+detail))
            gaps.extend(dict(code=reviewed['code'],reason=w['warning']) for w in reviewed.get('reportMetadataWarnings',[]))
    return dict(type='research-template-result',schemaVersion=SCHEMA,engineVersion=ENGINE,template='company-financial-review',status='calculated-with-gaps' if gaps else 'calculated',contextSnapshot=ctx,contextHash=ctx['contextHash'],result=result,gaps=gaps,lineage=dict(files=nodes,sources=[],metrics=[],calculations=[dict(id='company-financial-review',function='company_financial_report.run',parameters=dict(asOf=params['asOf'],baseCurrency=params['baseCurrency']),code=versions,dependsOnFiles=[n['path'] for n in nodes],outputSha256=digest(result))]),limits=['复用已取得财报数据；本模板不自动重新取数或导出Excel','核验限支持字段累计及期末值，非全部科目核验'])

def report_reading_gaps(result):
 gaps=[dict(reason='报告未精读：'+id) for id in result['unreadReports']]
 for analysis in result['analyses']:
  pending={ '待核查假设：'+entry['text'] for entry in analysis.get('assumptionTests',[]) }
  gaps.extend(dict(reason=g,reportId=analysis['reportId']) for g in analysis['gaps'] if g not in pending)
  gaps.extend(dict(reason='待核查假设：'+entry['text'],reportId=analysis['reportId'],invalidationSignal=entry['invalidationSignal'],requestedEvidence=entry['requestedEvidence'],evidence=entry['evidence'],status=entry['status']) for entry in analysis.get('assumptionTests',[]))
  gaps.extend(dict(reason='尽调问题尚未访谈或取证：'+q['question'],reportId=analysis['reportId'],respondent=q['respondent'],requestedEvidence=q['requestedEvidence'],status=q['status']) for q in analysis.get('dueDiligenceQuestions',[]))
 return gaps

def run_document_observation_review(manifest):
    ctx_path=Path(manifest['contextPath']);input_path=Path(manifest['inputPath']);ctx=load(ctx_path)
    if ctx.get('type')!='research-context' or ctx.get('contextHash')!=digest(ctx.get('parameters')):raise ValueError('研究上下文损坏')
    supplied=load(input_path);archive_path=Path(supplied['archive']);data=load(archive_path);params=ctx['parameters'];template=manifest['template']
    if data['asOf']!=params['asOf']:raise ValueError('资料截止日与研究上下文不同，需另建研究版本')
    nodes=[input_node(ctx_path,'context'),input_node(input_path,'review-input'),input_node(archive_path,'source-archive')]
    if template=='macro-observation-review':
        if params['dividendTreatment']!='price_only':raise ValueError('宏观资产观察仅价格变化，不能使用分红总收益上下文')
        if any(s['unit']!=params['baseCurrency'] for s in data['series'] if s['role']=='asset' and s['points']):raise ValueError('资产价格币种与上下文不同，不自动汇兑')
        from macro_asset_observation import build
        result=build(supplied,Path(manifest['outDir']))
        for b in result['sourceBindings']:
            if b['rawFile']:nodes.append(input_node(archive_path.parent/b['rawFile'],'raw-observations'))
        modules=['research_workflow.py','macro_asset_observation.py','eia_inventory_source.py','research_brief_html.py']
        gaps=[dict(reason='序列未取得：'+id) for id in result['missingSeries']]
        gaps += [dict(reason='共同历史不足：'+str(w['windowDays'])+'日窗口') for w in result['assetWindows'] if w['status']=='insufficient']
        gaps += [dict(reason='利率资产同窗口历史不足：'+str(w['observationIntervals'])+'个共同观测间隔',seriesIds=w['includedSeries']) for w in result.get('dailyRateAssetAlignment',[]) if w['status']=='insufficient-common-observations']
        gaps += [dict(reason='利率资产共同观测稀疏：'+str(w['observationIntervals'])+'个间隔',maximumCalendarGapDays=w['maximumCalendarGapDays'],seriesIds=w['includedSeries']) for w in result.get('dailyRateAssetAlignment',[]) if w.get('continuityStatus')=='sparse-observations-not-daily-window']
        gaps += [dict(reason='原始观测未完整核对：'+b['id']) for b in result['sourceBindings'] if b['status']!='raw-file-and-observations-matched']
        gaps += [dict(reason='逐点发布日期未核验：'+s['id']) for s in result['sources'] if not s.get('publicationDatesVerified')]
        gaps += [dict(reason='指标定义仅由输入声明：'+s['id'],seriesIds=[s['id']]) for s in result.get('seriesContracts',[]) if s['status']!='supported-definition-checked']
        for hypothesis in result.get('transmissionHypotheses',[]):
            gaps.append(dict(reason='传导假设尚未因果验证：'+hypothesis['mechanism'],factorIds=hypothesis['factorIds'],assetIds=hypothesis.get('assetIds',[])))
            factor_dates={o['latest']['date'] for o in hypothesis['observations']}
            for asset in hypothesis.get('assetObservations',[]):
                if factor_dates!={asset['latest']['date']}:gaps.append(dict(reason='假设引用的宏观与资产最新观测日期不同：'+asset['id'],assetDate=asset['latest']['date'],factorDates=sorted(factor_dates)))
        alignment=result.get('monthlyAlignment',{})
        if alignment.get('status')=='no-common-month':gaps.append(dict(reason='月度指标没有共同所属月，未合成同步观察'))
        gaps += [dict(reason='月度观测缺期：'+g['month']+'，缺少'+ '、'.join(g['missingSeries']),month=g['month'],seriesIds=g['missingSeries']) for g in alignment.get('monthGaps',[])]
    elif template=='report-translation-review':
        from report_translation import build
        result=build(supplied,Path(manifest['outDir']))
        selected=[r for r in data['reports'] if r['id']==result['reportId']]
        if len(selected)!=1:raise ValueError('译文原文记录不唯一')
        nodes.append(input_node(Path(selected[0]['pdfPath']),'original-pdf'))
        modules=['research_workflow.py','report_translation.py','research_report_reading.py','research_brief_html.py']
        gaps=[dict(reason='译文语义尚未独立核验，文字覆盖及数字一致不代表译意正确')]
        gaps += [dict(reason='尚未翻译的原文页',page=n) for n in result['missingPages']]
        gaps += [dict(reason='原文文字不足，需人工核对图片及扫描页',page=n) for n in result['lowTextPages']]
        gaps += [dict(reason=warning,page=p['page']) for p in result['pages'] for warning in p['numericWarnings']]
    elif data.get('type')=='policy-html-archive':
        from policy_original_reading import build
        result=build(supplied,Path(manifest['outDir']))
        nodes.append(input_node(Path(data['rawPath']),'original-policy-html'))
        modules=['research_workflow.py','policy_original_reading.py','research_report_reading.py','research_brief_html.py']
        gaps=[dict(reason=g) for g in result['gaps']]
    else:
        from research_report_reading import build
        result=build(supplied,Path(manifest['outDir']))
        used={a['reportId'] for a in result['analyses']}
        for report in data['reports']:
            if report['id'] in {f['reportId'] for f in result['sourceFiles']}:nodes.append(input_node(Path(report['pdfPath']),'original-pdf' if report['id'] in used else 'unread-original-pdf'))
        modules=['research_workflow.py','research_report_reading.py','report_reading_coverage.py','research_brief_html.py']
        if any('benchmarkReview' in a for a in result['analyses']):modules.append('report_benchmark_status.py')
        gaps=report_reading_gaps(result)
    versions=[code_node(m) for m in modules]
    return dict(type='research-template-result',schemaVersion=SCHEMA,engineVersion=ENGINE,template=template,status='calculated-with-gaps' if gaps else 'calculated',contextSnapshot=ctx,contextHash=ctx['contextHash'],result=result,gaps=gaps,lineage=dict(files=nodes,sources=[],metrics=[],calculations=[dict(id=template,function=modules[1]+'.build',parameters=params,code=versions,dependsOnFiles=[n['path'] for n in nodes],outputSha256=digest(result))]),limits=result['limitations'])

def run_scenario_review(manifest):
    ctx_path=Path(manifest['contextPath']);input_path=Path(manifest['inputPath']);ctx=load(ctx_path)
    if ctx.get('type')!='research-context' or ctx.get('contextHash')!=digest(ctx.get('parameters')):raise ValueError('研究上下文损坏')
    spec=load(input_path);params=ctx['parameters'];template=manifest['template'];mode=manifest['mode']
    allowed={'company-scenario-review':{'dcf','relative','forecast'},'industry-scenario-review':{'supply','concentration'},'exit-scenario-review':{'exit'}}
    if mode not in allowed[template]:raise ValueError('模型模式与研究模板不匹配')
    if spec['asOf']!=params['asOf']:raise ValueError('模型截止日与研究上下文不同')
    if template!='industry-scenario-review' and spec['currency']!=params['baseCurrency']:raise ValueError('模型币种与研究上下文不同，不自动汇兑')
    if template=='company-scenario-review':
        from company_scenarios import run
        module='company_scenarios.py'
    else:
        from industry_exit_scenarios import run
        module='industry_exit_scenarios.py'
    result=run(mode,spec,Path(manifest['outDir']))
    nodes=[input_node(ctx_path,'context'),input_node(input_path,'scenario-assumptions')]+[input_node(Path(b['path']),'scenario-source') for b in spec.get('sourceFiles',[])]
    versions=[code_node(m) for m in dict.fromkeys(['research_workflow.py',module,'company_scenarios.py','research_brief_html.py'])]
    gaps=[]
    def collect_gaps(obj,path='result'):
        if isinstance(obj,dict):
            for g in obj.get('gaps',[]):gaps.append(dict(location=path,reason=str(g)))
            if obj.get('annualizationStatus') not in [None,'calculated']:gaps.append(dict(location=path,reason='年化未计算：'+obj['annualizationStatus']))
            for k,v in obj.items():
                if k not in ['input','gaps']:collect_gaps(v,path+'.'+k)
        elif isinstance(obj,list):
            for i,v in enumerate(obj):collect_gaps(v,path+'['+str(i)+']')
    collect_gaps(result)
    if template=='company-scenario-review':
        for entry in result.get('inputEvidenceSummary',{}).get('entries',[]):
            if entry['basis']!='assumption':gaps.append(dict(location=entry['inputPath'],reason='来源数值或计算依据尚未在本估值流程中核验公告原文',numericAnchorDeclared=entry['numericAnchorDeclared'],originalVerified=False))
        if mode=='dcf' and result.get('cashFlowTypeBasis')=='FCFF-model-convention':gaps.append(dict(reason='现金流沿用FCFF模型约定，输入未明确声明编制类型'))
    if result.get('unknownShare',0)>0:gaps.append(dict(reason='市场份额未归属：'+str(result['unknownShare'])+'；集中度仅输出上下界'))
    if result.get('uncomputedYears'):gaps.append(dict(reason='未计算后续年份：'+str(result['uncomputedYears'])))
    return dict(type='research-template-result',schemaVersion=SCHEMA,engineVersion=ENGINE,template=template,status='scenario-calculated-with-gaps' if gaps else 'scenario-calculated',contextSnapshot=ctx,contextHash=ctx['contextHash'],result=result,gaps=gaps,lineage=dict(files=nodes,sources=[],metrics=[],calculations=[dict(id=template,function=module+'.run',parameters=dict(asOf=params['asOf'],mode=mode),code=versions,dependsOnFiles=[n['path'] for n in nodes],outputSha256=digest(result))]),limits=result.get('limitations',[])+['仅按提供资料与假设计算；计算完成不代表资料完整或未来结果已验证'])

def fof_review_markdown(result,spec):
    labels={'stock':'股票','bond':'债券','cash':'现金','other':'其他已分类资产'}
    lines=['# FOF持仓穿透简报','',spec['root']+'；资料截止日：'+spec['asOf']+'。',
           '本次可识别底层资产占原始组合的'+format(result['knownWeight']*100,'.2f')+'%，未知部分为'+format(result['unknownWeight']*100,'.2f')+'%。未知部分未当作现金，也未将已知部分放大到100%。',
           '比例使用输入声明的持仓权重，不是账户核验。各层报告期可能不同，本结果不能视为当前实时持仓。',
           '', '## 已知大类敞口','', '|资产类别|占原始组合|','|---|---:|']
    for kind,label in labels.items():lines.append('|'+label+'|'+format(result['assetExposure'][kind]*100,'.4f')+'%|')
    lines+=['','## 待补资料与未知仓位','', '|穿透路径|占原始组合|原因|','|---|---:|---|']
    for row in result['unknown']:lines.append('|'+ ' → '.join(row['path'])+'|'+format(row['weight']*100,'.4f')+'%|'+row['reason']+'|')
    if not result['unknown']:lines.append('本次输入未产生未知路径；仍需核验资料完整性及持仓口径。')
    lines+=['','## 报告来源与时点','', '|代码|报告期|披露日|登记来源|','|---|---|---|---|']
    for code,node in spec['nodes'].items():
        lines.append('|'+code+'|'+node['reportDate']+'|'+node['publishedAt']+'|'+node['sourceUrl']+'|')
    if result.get('sourceFiles'):
        lines+=['','## 本次留存的来源副本','以下副本与登记哈希一致；尚未确认每份文件与穿透节点的对应关系，不表示逐行原文核验完成。']
        for i,source in enumerate(result['sourceFiles'],1):lines.append('- [来源副本'+str(i)+']('+source['relativePath']+')；文件哈希：'+source['sha256'])
    lines+=['','## 本次局限','来源和权重按输入登记。文件哈希一致不代表重新完成原文核验，也不证明官方发布网页或版本仍有效。',*result['limitations']]
    return '\n'.join(lines)

def copy_fof_sources(bindings,out):
    records=[]
    for i,binding in enumerate(bindings,1):
        source=Path(binding['path']);raw=source.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=binding['sha256']:raise ValueError('穿透来源文件在交付前已变化')
        suffix=source.suffix.lower() if source.suffix.lower() in ['.pdf','.json','.csv','.txt'] else '.bin'
        rel='sources/source-'+str(i)+suffix
        target=out/rel;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        records.append(dict(relativePath=rel,sha256=binding['sha256'],verification='file-hash-matched-not-original-verified'))
    return records

def run_fof_review(manifest):
    from research_extensions import fof
    ctx_path=Path(manifest['contextPath']);input_path=Path(manifest['inputPath'])
    ctx=load(ctx_path)
    if ctx.get('type')!='research-context' or ctx.get('contextHash')!=digest(ctx.get('parameters')):raise ValueError('研究上下文损坏')
    spec=load(input_path);params=ctx['parameters']
    if spec['asOf']!=params['asOf'] or spec['currency']!=params['baseCurrency']:raise ValueError('穿透截止日或币种与研究上下文不同')
    nodes=[input_node(ctx_path,'context'),input_node(input_path,'disclosed-holdings-input')]
    for binding in spec.get('sourceFiles',[]):
        node=input_node(binding['path'],'declared-report-source')
        if node['sha256']!=binding['sha256']:raise ValueError('穿透来源文件哈希变化')
        nodes.append(node)
    result=fof(spec)
    result['rootFund']=spec['root']
    totals={kind:sum(row['weight'] for row in result['paths'] if row['kind']==kind) for kind in ['stock','bond','cash','other']}
    result['assetExposure']=totals;result['unknownWeight']=sum(row['weight'] for row in result['unknown'])
    result['knownWeight']=sum(totals.values())
    sources=[dict(node=key,sourceUrl=n['sourceUrl'],reportDate=n['reportDate'],publishedAt=n['publishedAt'],verification='input-declared-not-reverified') for key,n in spec['nodes'].items()]
    if manifest.get('outDir'):
        from research_brief_html import render
        out=Path(manifest['outDir']);out.mkdir(parents=True,exist_ok=False)
        result['sourceFiles']=copy_fof_sources(spec.get('sourceFiles',[]),out)
        text=fof_review_markdown(result,spec)
        (out/'FOF持仓穿透简报.md').write_text(text,'utf-8')
        (out/'FOF持仓穿透简报.html').write_text(render(text,title='FOF持仓穿透简报'),'utf-8')
    versions=[code_node(name) for name in ['research_workflow.py','research_extensions.py','portfolio_models.py','research_brief_html.py']]
    gaps=[dict(reason=row['reason'],path=row['path'],weight=row['weight']) for row in result['unknown']]
    return dict(type='research-template-result',schemaVersion=SCHEMA,engineVersion=ENGINE,template='fof-lookthrough-review',status='calculated-with-gaps' if gaps else 'calculated',contextSnapshot=ctx,contextHash=ctx['contextHash'],result=result,gaps=gaps,lineage=dict(files=nodes,sources=sources,metrics=[],calculations=[dict(id='fof-lookthrough-review',function='research_extensions.fof',parameters=dict(asOf=params['asOf'],baseCurrency=params['baseCurrency']),code=versions,dependsOnFiles=[n['path'] for n in nodes],outputSha256=digest(result))]),limits=result['limitations']+['来源文件哈希绑定不等于重新核验原文；未提供文件时仅留存声明来源','未知仓位不归类为现金，不按已知部分重新归一化'])

def run_portfolio_model_review(manifest):
    from portfolio_models import optimize,simulate
    from research_extensions import crisis
    ctx_path=Path(manifest['contextPath']);input_path=Path(manifest['inputPath']);ctx=load(ctx_path)
    if ctx.get('type')!='research-context' or ctx.get('contextHash')!=digest(ctx.get('parameters')):raise ValueError('研究上下文损坏')
    spec=load(input_path);params=ctx['parameters'];mode=manifest['mode']
    if mode not in ['optimize','simulate','crisis']:raise ValueError('不支持的组合模型')
    if spec['asOf']!=params['asOf'] or spec['currency']!=params['baseCurrency']:raise ValueError('模型截止日或币种与研究上下文不同')
    frequency={'daily':'trading_day','monthly':'monthly'}.get(spec['frequency'])
    if frequency!=params['frequency'] or params['annualization']!=({'daily':252,'monthly':12}.get(spec['frequency'])):raise ValueError('模型频率或年化因子与研究上下文不同')
    if params['dividendTreatment']!='reinvest':raise ValueError('组合模型要求总收益再投口径，不能混用价格或现金分红序列')
    nodes=[input_node(ctx_path,'context'),input_node(input_path,'portfolio-model-input')]
    for binding in spec.get('sourceFiles',[]):
        node=input_node(binding['path'],'declared-history-source')
        if node['sha256']!=binding['sha256']:raise ValueError('历史来源文件哈希变化')
        nodes.append(node)
    result={'optimize':optimize,'simulate':simulate,'crisis':crisis}[mode](spec)
    sources=[dict(code=a['code'],sourceUrl=a['sourceUrl'],basis=a['basis'],verification='input-declared-not-reverified') for a in spec['assets']]
    versions=[code_node(name) for name in ['research_workflow.py','portfolio_models.py','research_extensions.py']]
    return dict(type='research-template-result',schemaVersion=SCHEMA,engineVersion=ENGINE,template='portfolio-model-review',status='scenario-calculated',contextSnapshot=ctx,contextHash=ctx['contextHash'],result=result,gaps=[dict(reason='总收益及分红处理按输入声明，本模板未重新核验原文或复权过程')],lineage=dict(files=nodes,sources=sources,metrics=[],calculations=[dict(id='portfolio-model-review',function=('research_extensions.crisis' if mode=='crisis' else 'portfolio_models.'+mode),parameters=dict(asOf=params['asOf'],mode=mode,frequency=frequency,annualization=params['annualization']),code=versions,dependsOnFiles=[n['path'] for n in nodes],outputSha256=digest(result))]),limits=result['limitations']+['登记来源文件不证明输入序列与源文件逐点一致；历史数据质量须另行核对'])

def run_event_price_review(manifest):
    cp=Path(manifest['contextPath']);ip=Path(manifest['inputPath']);ctx=load(cp)
    if ctx.get('type')!='research-context' or ctx.get('contextHash')!=digest(ctx.get('parameters')):raise ValueError('研究上下文损坏')
    params=ctx['parameters'];spec=load(ip);archive=Path(spec['archive']);data=load(archive)
    if data['asOf']!=params['asOf']:raise ValueError('事件价格资料截止日与上下文不一致')
    if params['dividendTreatment']!='price_only':raise ValueError('事件价格复盘只支持价格口径')
    selected={spec['assetId'],spec['comparisonId']}
    if any(s['unit']!=params['baseCurrency'] for s in data['series'] if s['id'] in selected):raise ValueError('事件对照币种与上下文不一致')
    from event_price_review import run
    result=run(spec,Path(manifest['outDir']))
    nodes=[input_node(cp,'context'),input_node(ip,'event-price-input'),input_node(archive,'price-archive')]
    for binding in result['sourceBindings']:
        if binding['rawFile']:nodes.append(input_node(archive.parent/binding['rawFile'],'raw-observations'))
    gaps=[dict(reason='事件日期、首次公开时点及来源身份尚未原文核验')]
    gaps += [dict(reason='所选资产原始观测未逐点核对：'+b['id']) for b in result['sourceBindings'] if b['id'] in selected and b['status']!='raw-file-and-observations-matched']
    for asset in data['series']:
        if asset['id'] in selected:
            gaps.append(dict(reason='分红、复权和同步定价时刻未核验：'+asset['id'],assetId=asset['id']))
            if not asset.get('calendarVerified'):gaps.append(dict(reason='资产完整交易日历未核验：'+asset['id'],assetId=asset['id']))
    for row in result['windows']:
        for side in ['before','after']:
            window=row[side]
            if window and window.get('continuityStatus')=='sparse-observations-not-daily-window':gaps.append(dict(reason='事件窗口为稀疏观测：'+str(row['observationIntervals'])+'间隔/'+side,maximumCalendarGapDays=window['maximumCalendarGapDays']))
    gaps += [dict(reason='事件窗口历史不足：'+str(w['observationIntervals'])+'个观测间隔') for w in result['windows'] if w['status']!='both-sides-available']
    versions=[code_node(m) for m in ['research_workflow.py','event_price_review.py','macro_asset_observation.py','research_brief_html.py']]
    return dict(type='research-template-result',schemaVersion=SCHEMA,engineVersion=ENGINE,template='event-price-review',status='calculated-with-gaps',contextSnapshot=ctx,contextHash=ctx['contextHash'],result=result,gaps=gaps,lineage=dict(files=nodes,sources=[],metrics=[],calculations=[dict(id='event-price-review',function='event_price_review.run',parameters=params,code=versions,dependsOnFiles=[n['path'] for n in nodes],outputSha256=digest(result))]),limits=result['limitations'])

def run_holdings_snapshot_review(manifest):
    cp=Path(manifest['contextPath']);ip=Path(manifest['inputPath']);ctx=load(cp)
    if ctx.get('type')!='research-context' or ctx.get('contextHash')!=digest(ctx.get('parameters')):raise ValueError('研究上下文损坏')
    spec=load(ip);hp=Path(spec['holdingsPath']);data=load(hp);params=ctx['parameters']
    if data['asOf']!=params['asOf']:raise ValueError('持仓研究截止日与上下文不同')
    if data['currency']!=params['baseCurrency']:raise ValueError('持仓计价币种与上下文不同，不自动汇兑')
    from holdings_snapshot_review import run
    result=run(spec,Path(manifest['outDir']),manifest.get('node'))
    nodes=[input_node(cp,'context'),input_node(ip,'holdings-review-input'),input_node(hp,'declared-allocation-and-reconciled-holdings')]
    for b in result['originalBindings']:
        nodes.extend([input_node(b['archivePath'],'fund-report-archive'),input_node(b['documentPath'],'original-fund-pdf')])
    modules=['research_workflow.py','holdings_snapshot_review.py','fof_reports.py','fund_report_holdings.py','verify_original.py','fund_diagnostics.js','research_analytics.js','fund_research.js','research_brief_html.py']
    gaps=[dict(reason='第三方PDF副本未核验官方发布网页'),dict(reason='配置权重由输入声明，非账户验证；非股票资产未穿透')]
    if len({f['reportDate'] for f in result['funds']})>1:gaps.append(dict(reason='报告期不同，相关重叠值未计算'))
    return dict(type='research-template-result',schemaVersion=SCHEMA,engineVersion=ENGINE,template='holdings-snapshot-review',status='calculated-with-gaps',contextSnapshot=ctx,contextHash=ctx['contextHash'],result=result,gaps=gaps,lineage=dict(files=nodes,sources=[],metrics=[],calculations=[dict(id='holdings-snapshot-review',function='holdings_snapshot_review.run',parameters=params,code=[code_node(m) for m in modules],dependsOnFiles=[n['path'] for n in nodes],outputSha256=digest(result))]),limits=result['limitations'])

def run_etf_closing_premium_review(manifest):
    from etf_closing_premium import run
    cp=Path(manifest['contextPath']);ip=Path(manifest['inputPath']);ctx=load(cp)
    if ctx.get('type')!='research-context' or ctx.get('contextHash')!=digest(ctx.get('parameters')):raise ValueError('研究上下文损坏')
    spec=load(ip);params=ctx['parameters']
    if spec['end']!=params['asOf']:raise ValueError('收盘净值对照截止日与上下文不同')
    if params['baseCurrency']!='CNY' or params['dividendTreatment']!='price_only':raise ValueError('收盘净值对照采用人民币价格口径，不能混用总收益或其他币种')
    result=run(spec,manifest['outDir'])
    nodes=[input_node(cp,'context'),input_node(ip,'etf-premium-input')]+[input_node(s['path'],s['role']) for s in result['sourceFiles']]
    gaps=[dict(reason=limit) for limit in result['limitations']]
    if result['missingNavDates']:gaps.append(dict(reason='部分价格日期缺少单位净值',dates=result['missingNavDates']))
    if not result['history']:gaps.append(dict(reason='没有共同日期，未计算收盘偏离'))
    versions=[code_node(m) for m in ['research_workflow.py','etf_closing_premium.py','portable_collect.py','research_brief_html.py']]
    return dict(type='research-template-result',schemaVersion=SCHEMA,engineVersion=ENGINE,template='etf-closing-premium-review',status='calculated-with-gaps' if result['history'] else 'missing',contextSnapshot=ctx,contextHash=ctx['contextHash'],result=result,gaps=gaps,lineage=dict(files=nodes,sources=[],metrics=[],calculations=[dict(id='etf-closing-premium-review',function='etf_closing_premium.run',parameters=params,code=versions,dependsOnFiles=[n['path'] for n in nodes],outputSha256=digest(result))]),limits=result['limitations'])

def run_portfolio_contribution_review(manifest):
    import shutil,subprocess
    cp=Path(manifest['contextPath']);ip=Path(manifest['inputPath']);ctx=load(cp)
    if ctx.get('type')!='research-context' or ctx.get('contextHash')!=digest(ctx.get('parameters')):raise ValueError('研究上下文损坏')
    spec=load(ip);history=spec['historyInput'];params=ctx['parameters']
    frequency={'trading_day':'daily','monthly':'monthly'}.get(params['frequency'])
    if not frequency or history['frequency']!=frequency or params['annualization']!={'daily':252,'monthly':12}[frequency]:raise ValueError('组合贡献频率或年化口径与上下文不同')
    if history['asOf']!=params['asOf'] or history['currency']!=params['baseCurrency'] or history['riskFreeAnnualPct']!=params['riskFreeRate']:raise ValueError('组合贡献日期、币种或无风险利率与上下文不同')
    if params['dividendTreatment']!='reinvest' or params['missingData']!='common_dates':raise ValueError('组合贡献要求明确红利再投与共同日期，不能改写其他口径')
    runtime=manifest.get('node') or shutil.which('node')
    if not runtime:raise ValueError('缺少Node运行时，尚未计算组合贡献')
    engine=Path(__file__).with_name('fund_research.js')
    process=subprocess.run([runtime,'-e',"process.stdout.write(JSON.stringify(require(process.argv[1]).contributions(JSON.parse(require('fs').readFileSync(0,'utf8')))));",str(engine.resolve())],input=json.dumps(spec,ensure_ascii=False),capture_output=True,text=True,encoding='utf8',timeout=60)
    if process.returncode:raise ValueError('组合贡献计算未完成：'+process.stderr[:1500])
    result=json.loads(process.stdout);nodes=[input_node(cp,'context'),input_node(ip,'portfolio-contribution-input')]
    gaps=[dict(reason=g) for g in result['evidenceGaps']]
    gaps.append(dict(reason='输入历史序列未与来源原始文件逐点核对；共同日期不证明完整交易日历'))
    versions=[code_node(m) for m in ['research_workflow.py','fund_research.js','research_analytics.js']]
    return dict(type='research-template-result',schemaVersion=SCHEMA,engineVersion=ENGINE,template='portfolio-contribution-review',status='calculated-with-gaps',contextSnapshot=ctx,contextHash=ctx['contextHash'],result=result,gaps=gaps,lineage=dict(files=nodes,sources=[dict(code=a['code'],sourceUrl=a['sourceUrl'],verification='input-declared') for a in history['assets']],metrics=[],calculations=[dict(id='portfolio-contribution-review',function='fund_research.contributions',parameters=params,code=versions,dependsOnFiles=[n['path'] for n in nodes],outputSha256=digest(result))]),limits=result['limitations'])

def run_template(manifest,workspace):
    if manifest.get('template')=='portfolio-contribution-review':result=run_portfolio_contribution_review(manifest)
    elif manifest.get('template')=='etf-closing-premium-review':result=run_etf_closing_premium_review(manifest)
    elif manifest.get('template')=='holdings-snapshot-review':result=run_holdings_snapshot_review(manifest)
    elif manifest.get('template')=='event-price-review':result=run_event_price_review(manifest)
    elif manifest.get('template')=='fund-comparison':result=run_fund_comparison(manifest,workspace)
    elif manifest.get('template')=='portfolio-diagnostic':result=run_portfolio_diagnostic(manifest)
    elif manifest.get('template')=='fof-lookthrough-review':result=run_fof_review(manifest)
    elif manifest.get('template')=='portfolio-model-review':result=run_portfolio_model_review(manifest)
    elif manifest.get('template')=='company-financial-review':result=run_company_financial_review(manifest)
    elif manifest.get('template') in ['macro-observation-review','report-reading-review','report-translation-review']:result=run_document_observation_review(manifest)
    elif manifest.get('template') in ['company-scenario-review','industry-scenario-review','exit-scenario-review']:result=run_scenario_review(manifest)
    else:raise ValueError('未知研究模板')
    result['envelopeSha256']=digest(result)
    return result

def validate_template_result(item):
    if item.get('type')!='research-template-result':raise ValueError('需要研究模板结果')
    if item.get('envelopeSha256') and item['envelopeSha256']!=digest({k:v for k,v in item.items() if k!='envelopeSha256'}):raise ValueError('研究封装摘要不一致，状态、缺口或研究内容已变化')
    ctx=item.get('contextSnapshot',{})
    if not isinstance(ctx.get('parameters'),dict) or ctx.get('contextHash')!=digest(ctx.get('parameters')) or item.get('contextHash')!=ctx.get('contextHash'):raise ValueError('研究上下文哈希不一致，不能复核')
    calculations=item.get('lineage',{}).get('calculations',[])
    if not calculations:raise ValueError('缺少计算记录，不能确认版本可比')
    registered_codes={};registered_files={}
    for calc in calculations:
        if not calc.get('outputSha256') or calc['outputSha256']!=digest(item['result']):raise ValueError('研究结果与保存计算摘要不一致，不能复核')
        if not calc.get('code'):raise ValueError('缺少方法版本记录，不能确认版本可比')
        for code in calc['code']:
            module=code.get('module');sha=code.get('sha256')
            if not module or not sha:raise ValueError('方法版本记录不完整')
            if module in registered_codes and registered_codes[module]!=sha:raise ValueError('同一方法存在冲突版本，不能静默覆盖')
            registered_codes[module]=sha
    for node in item.get('lineage',{}).get('files',[]):
        key=(node.get('role'),node.get('path'));sha=node.get('sha256')
        if not all(key) or not sha:raise ValueError('来源文件版本记录不完整')
        if key in registered_files and registered_files[key]!=sha:raise ValueError('同一来源存在冲突版本，不能静默覆盖')
        registered_files[key]=sha

def impact(old,new_context_path=None,replacements=None):
    validate_template_result(old)
    replacements=replacements or {}
    if not isinstance(replacements,dict):raise ValueError('replacements须为路径映射')
    registered_paths={node['path'] for node in old['lineage']['files']}
    if set(replacements)-registered_paths:raise ValueError('替换清单包含未登记的来源路径，不能静默忽略')
    reasons=[];changed=[]
    if new_context_path:
        new=load(new_context_path)
        if new.get('type')!='research-context' or new.get('contextHash')!=digest(new.get('parameters')):raise ValueError('新上下文无效')
        before=old['contextSnapshot']['parameters'];after=new['parameters']
        changed=[k for k in CONTEXT_FIELDS if before[k]!=after[k]]
        for k in changed:
            if k in DEPENDENCIES.get(old['template'],set()):reasons.append({'type':'parameter','field':k,'before':before[k],'after':after[k]})
    for node in old['lineage']['files']:
        oldpath=node['path'];path=Path(replacements.get(oldpath,oldpath))
        if not path.exists():reasons.append({'type':'file-missing','role':node['role'],'path':str(path)});continue
        current=file_digest(path)
        if current!=node['sha256']:reasons.append({'type':'file-changed','role':node['role'],'path':str(path),'before':node['sha256'],'after':current})
    for calc in old['lineage']['calculations']:
        for code in calc['code']:
            path=Path(__file__).parent/code['module']
            if not path.exists() or file_digest(path)!=code['sha256']:
                reasons.append({'type':'code-changed','module':code['module']})
    # Unregistered upstream revisions cannot be detected from a fixed snapshot alone.
    return {'type':'research-impact','priorResultStatus':old['status'],'impactStatus':'stale' if reasons else 'unchanged-for-registered-dependencies',
        'changedParameters':changed,'affectedResults':[old['template']] if reasons else [],'reasons':reasons,
        'snapshotIntegrity':'envelope-and-calculation-digests-matched' if old.get('envelopeSha256') else 'calculation-digest-matched; envelope-not-recorded',
        'limitation':'只检测登记的本地输入、参数及代码；远程源变化须先重新采集并作为新输入登记。摘要是本地一致性校验，不是来源真实性认证或数字签名。'}


def compare_results(before,after):
 """Compare registered research versions without treating model changes as economics."""
 for item in [before,after]:validate_template_result(item)
 parameters=[dict(field=k,before=before['contextSnapshot']['parameters'].get(k),after=after['contextSnapshot']['parameters'].get(k)) for k in CONTEXT_FIELDS if before['contextSnapshot']['parameters'].get(k)!=after['contextSnapshot']['parameters'].get(k)]
 def codes(item):return {c['module']:c['sha256'] for calc in item['lineage']['calculations'] for c in calc['code']}
 oldcodes,newcodes=codes(before),codes(after)
 code_changes=[m for m in sorted(set(oldcodes)|set(newcodes)) if oldcodes.get(m)!=newcodes.get(m)]
 def inputs(item):return {(x['role'],x['path']):x['sha256'] for x in item['lineage']['files']}
 oldfiles,newfiles=inputs(before),inputs(after)
 input_changes=[dict(role=k[0],path=k[1],before=oldfiles.get(k),after=newfiles.get(k)) for k in sorted(set(oldfiles)|set(newfiles)) if oldfiles.get(k)!=newfiles.get(k)]
 def subjects(value,template):
  found=set()
  if isinstance(value,dict):
   if template=='fof-lookthrough-review' and isinstance(value.get('rootFund'),str):found.add('rootFund:'+value['rootFund'])
   if template=='macro-observation-review' and isinstance(value.get('seriesContracts'),list):
    found.update('series:'+x['role']+':'+x['id'] for x in value['seriesContracts'] if isinstance(x,dict) and isinstance(x.get('id'),str) and x.get('role') in ['macro','asset'])
  def walk(obj):
   if isinstance(obj,dict):
    if obj.get('type')=='policy-original-reading' and isinstance(obj.get('sourceUrl'),str):found.add('policy-source:'+obj['sourceUrl'])
    for key in ['code','reportId','assetId','comparisonId','portfolioId']:
     if isinstance(obj.get(key),str):found.add(key+':'+obj[key])
    if isinstance(obj.get('firms'),list):
     found.update('firm:'+x['id'] for x in obj['firms'] if isinstance(x,dict) and isinstance(x.get('id'),str))
    for v in obj.values():walk(v)
   elif isinstance(obj,list):
    for v in obj:walk(v)
  walk(value);return sorted(found)
 oldsubjects,newsubjects=subjects(before['result'],before['template']),subjects(after['result'],after['template'])
 def conventions(item):
  values={}
  for company in item['result'].get('companies',[]) if isinstance(item['result'],dict) else []:
   if not isinstance(company,dict) or not isinstance(company.get('code'),str):continue
   meta=company.get('metadata',{})
   if not isinstance(meta,dict):continue
   for field in ['classificationVersion','scope','currency','unit','sectorType']:
    if field in meta:values[(company['code'],field)]=meta[field]
  return values
 oldconventions,newconventions=conventions(before),conventions(after)
 def convention_state(k):
  old_known=oldconventions.get(k) not in (None,'')
  new_known=newconventions.get(k) not in (None,'')
  if not old_known and new_known:return 'record-added'
  if old_known and not new_known:return 'record-missing'
  if old_known and new_known:return 'value-changed'
  return 'unknown-record-change'
 convention_changes=[dict(code=k[0],field=k[1],before=oldconventions.get(k),after=newconventions.get(k),changeType=convention_state(k)) for k in sorted(set(oldconventions)|set(newconventions)) if oldconventions.get(k)!=newconventions.get(k)]
 convention_gaps=[]
 for side,item,values in [('before',before,oldconventions),('after',after,newconventions)]:
  if item['template']!='company-financial-review':continue
  companies=item['result'].get('companies',[]) if isinstance(item['result'],dict) else []
  for company in companies:
   if not isinstance(company,dict) or not isinstance(company.get('code'),str):continue
   for field in ['classificationVersion','scope','currency','unit','sectorType']:
    value=values.get((company['code'],field))
    if not isinstance(value,str) or not value.strip():convention_gaps.append(dict(version=side,code=company['code'],field=field))
 same_template=before['template']==after['template']
 blockers=[]
 if not same_template:blockers.append('研究模板不同')
 if oldsubjects!=newsubjects:blockers.append('研究对象不同')
 if not oldsubjects or not newsubjects:blockers.append('未取得足够研究对象标识，不能确认直接可比')
 if parameters:blockers.append('研究参数或口径发生变化')
 if code_changes:blockers.append('计算或报告代码版本发生变化')
 if convention_gaps:blockers.append('公司研究关键口径记录不完整')
 if any(x['changeType']=='value-changed' for x in convention_changes):blockers.append('已登记公司口径值发生变化')
 if any(x['changeType']!='value-changed' for x in convention_changes):blockers.append('公司口径记录补充或缺失，尚不能确认一致')
 return dict(type='research-version-comparison',beforeTemplate=before['template'],afterTemplate=after['template'],beforeSubjects=oldsubjects,afterSubjects=newsubjects,parameterChanges=parameters,conventionChanges=convention_changes,conventionGaps=convention_gaps,codeChanges=code_changes,inputChanges=input_changes,resultChanged=digest(before['result'])!=digest(after['result']),directlyComparable=not blockers,comparisonBlockers=blockers,limitations=['文件变更不自动判定真实经营变化，需查看原文及指标口径','本比较列版本变化，不以列表位置配对公司或资产，不自动计算跨版本指标差值','不自动检测远程公告更正；需先取得并登记新资料','未登记的行业分类或单位口径不能据此视为已核验'])


def version_comparison_markdown(result):
 labels={'baseCurrency':'币种','frequency':'频率','dividendTreatment':'分红处理','asOf':'资料截止日','benchmark':'基准','riskFreeRate':'无风险利率','annualization':'年化因子','missingData':'缺失值处理','timezone':'时区'}
 lines=['# 研究版本对照','']
 lines.append('两次研究的登记口径与对象一致，可以进一步逐项核对指标。' if result['directlyComparable'] else '两次研究不能直接比较：'+'；'.join(result['comparisonBlockers'])+'。')
 lines+=['','## 变化说明']
 if result['parameterChanges']:
  for row in result['parameterChanges']:lines.append(labels.get(row['field'],row['field'])+'发生变化，应先确认口径后再比较结果。')
 else:lines.append('登记的研究参数没有变化。')
 for row in result.get('conventionGaps',[]):
  label={'classificationVersion':'行业分类版本','scope':'报表范围','currency':'币种','unit':'金额单位','sectorType':'公司类别'}[row['field']]
  lines.append(('旧版' if row['version']=='before' else '新版')+'的'+row['code']+'缺少有效'+label+'记录，不能将两版均缺失当作口径一致。')
 for row in result.get('conventionChanges',[]):
  label={'classificationVersion':'行业分类版本','scope':'报表范围','currency':'币种','unit':'金额单位','sectorType':'公司类别'}.get(row['field'],'公司口径')
  state=row.get('changeType','value-changed')
  if state=='record-added':lines.append(row['code']+'的'+label+'在新版补充记录；旧版未记录，不能据此认定实际口径改变。')
  elif state=='record-missing':lines.append(row['code']+'的'+label+'在新版缺少记录，暂不能确认两版一致。')
  elif state=='unknown-record-change':lines.append(row['code']+'的'+label+'记录仍不充分，需核实后再比较。')
  else:lines.append(row['code']+'的'+label+'登记值不同，应确认口径后再比较。')
 lines.append('计算或报告方法版本发生变化，差异不能直接解释为市场或经营变化。' if result['codeChanges'] else '登记的方法版本没有变化。')
 lines.append('登记的资料文件发生变化或替换，需要复核新旧来源。' if result['inputChanges'] else '登记的资料文件没有变化。')
 lines.append('研究结果内容发生变化，但本次尚未判断哪些属于真实业务变化。' if result['resultChanged'] else '研究结果内容一致。')
 lines+=['','## 对比范围',*result['limitations']]
 return '\n\n'.join(lines)

def impact_markdown(result):
 labels={'baseCurrency':'币种','frequency':'频率','dividendTreatment':'分红处理','asOf':'资料截止日','benchmark':'基准','riskFreeRate':'无风险利率','annualization':'年化因子','missingData':'缺失值处理','timezone':'时区'}
 lines=['# 研究复查结果','']
 if result['impactStatus']=='stale':lines.append('已登记的资料、参数或方法发生变化，相关研究需要重新核对后使用。')
 else:lines.append('已登记的本地依赖未发现变化；这不代表远程公告或政策仍是最新版本。')
 if result['snapshotIntegrity']=='envelope-and-calculation-digests-matched':lines.append('保存的研究内容、状态及缺口清单与记录摘要一致。')
 else:lines.append('此历史记录仅有计算结果摘要，未记录整体状态和缺口清单摘要；不能认定这些汇总信息已完整校验。')
 lines+=['','## 需要复查的变化']
 files=sum(r['type']=='file-changed' for r in result['reasons']);missing=sum(r['type']=='file-missing' for r in result['reasons']);methods=sum(r['type']=='code-changed' for r in result['reasons'])
 if files:lines.append(str(files)+'份登记资料文件已变化。应查看新旧原文与口径，文件变化本身不证明经营事实改变。')
 if missing:lines.append(str(missing)+'份登记资料无法在本地找到。应恢复或重新获取来源后复核。')
 if methods:lines.append('研究方法或报告生成版本变化。应重新运行，不能将结果差异直接解释为市场变化。')
 for r in result['reasons']:
  if r['type']=='parameter':lines.append('研究参数“'+labels.get(r['field'],'其他研究口径')+'”发生变化，需先对齐口径。')
 if not result['reasons']:lines.append('未发现已登记依赖的变化。')
 lines+=['','## 复查范围',result['limitation']]
 return '\n\n'.join(lines)
