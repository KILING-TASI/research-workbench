"""Deterministic common follow-up phrases; not a general natural-language planner."""
import argparse,calendar,hashlib,json,re,tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from start import execute,CONTINUABLE
from collection_validation import unique_pairs,reject_constant,finite_json_float


def plan(previous,question):
    root=Path(previous).resolve();path=root/'research-request.json'
    if path.is_symlink() or not path.is_file() or path.stat().st_size>1024*1024:raise ValueError('旧请求缺失或路径异常，不能猜研究类型')
    request=json.loads(path.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
    if not isinstance(request,dict) or request.get('command') not in CONTINUABLE:raise ValueError('旧报告没有可接续入口')
    if not isinstance(question,str) or not question.strip() or len(question)>1000:raise ValueError('追问须为非空简短文字')
    normalized=re.sub(r'[\s，,。!?！？]','',question)
    result={'command':request['command'],'previousRequestSha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'question':question,'online':False,'changes':{},'status':'ready','message':'沿用原参数与保存资料重算，不更新行情或公告。'}
    if normalized in ('继续','继续研究','重算','重新核对','沿用原资料重算','用原参数重算'):return result
    # Full matching prevents an extra request (budget, fees, different products) being silently dropped.
    reduced=re.sub(r'^(?:(?:请|帮我|沿用(?:上一份|上次|这份|旧报告|原报告)(?:资料|报告)?|把(?:区间|时间)(?:改成|改为)|只看|改看|看|比较))*','',normalized)
    end=request.get('asOf')
    if request['command']=='rebalance' and reduced in ('改成按月再平衡','按月再平衡','每月再平衡'):
        result.update(changes={'rebalance_options':{'periodicRule':'month-change'}},message='本次采用月初有数据观察日收盘形成信号、下一观察日收盘执行，沿用原历史与费用；不是每月末即时成交，不更新行情。')
        return result
    if request['command']=='cashflow' and reduced in ('我到底赚了多少','赚了多少','剔除本金后赚了多少','账户增长是不是收益'):
        result.update(questionType='cashflow-profit',message='沿用已声明的估值和完整出入金记录，分开解释账户变动、本金进出与损益；不认证真实账单，不更新资料。')
        return result
    if request['command']=='portfolio' and reduced in ('谁在拖累组合','谁拖累了组合','哪项拖累最大','收益主要靠谁','谁在拉动收益'):
        focus='gain' if reduced in ('收益主要靠谁','谁在拉动收益') else 'drag'
        result.update(questionType='portfolio-'+focus,message='沿用原组合历史路径回答收益贡献，不改权重、日期或价格，不视为真实账户损益。')
        return result
    if request['command']=='snapshot' and reduced in ('钱集中在哪','钱集中在哪里','我的钱主要集中在哪','我的钱主要集中在哪里','资金集中在哪'):
        result.update(questionType='money-concentration',message='沿用持仓表回答金额集中位置；不更新市值，不把金额占比当作风险贡献。')
        return result
    if request['command']=='bjx':
        phrase=re.sub(r'[\s。!?！？]','',question)
        match=re.fullmatch(r'(?:请|帮我)?(?:沿用(?:上一份|上次|这份|旧报告|原报告)(?:资料|报告)?[,，]?)?(?:把)?(?:资金|本金|预算)(?:改为|改成|调整为)((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(万元|元)',phrase)
        if match:
            digits=match[1].replace(',','')
            if len(digits.replace('.',''))>22:raise ValueError('金额过长，请明确常规人民币金额；未执行')
            value=Decimal(digits)*(Decimal(10000) if match[2]=='万元' else Decimal(1))
            if value*100!=(value*100).to_integral_value():raise ValueError('换算成人民币元后最多两位小数；未执行')
            result['changes']={'budget':format(value,'f')}
            result['message']='只将单只发行情景的预算改为'+format(value,'f')+'元，沿用原日期和配售/涨跌幅假设；不是年度收益预测，资金可用性与权限需另确认。'
            return result
    if request['command']!='funds':
        result.update(status='needs-clarification',message='这项研究的参数改动需按原入口明确处理，尚未执行；保留旧资料。');return result
    questions={'哪只更稳':'stability','哪个更稳':'stability','哪只风险更低':'stability','哪只波动更小':'volatility','哪只回撤更小':'drawdown'}
    if reduced in questions:
        result['questionType']=questions[reduced]
        result['message']='沿用原区间与保存资料回答历史风险问题，日常波动和最大回撤分开解释；不更新资料。'
        return result
    if not isinstance(end,str) or date.fromisoformat(end).isoformat()!=end:raise ValueError('上次截止日缺失或无效，不能猜“最近”的基准日')
    anchor=date.fromisoformat(end)
    months=None
    if reduced in ('近一年','最近一年','过去一年'):months=12
    elif reduced in ('近半年','最近半年','过去半年'):months=6
    elif reduced in ('近三个月','最近三个月','过去三个月'):months=3
    else:
        match=re.fullmatch(r'(?:近|最近|过去)(\d{1,2})个月',reduced)
        if match:
            months=int(match[1])
            if not 1<=months<=60:raise ValueError('月份须为1至60，未执行')
    if months is not None:
        index=anchor.year*12+anchor.month-1-months;year,month=divmod(index,12);month+=1
        beginning=date(year,month,min(anchor.day,calendar.monthrange(year,month)[1])).isoformat()
        result['changes']={'start':beginning}
        result['message']='只修改起点为'+beginning+'，截止日仍是原报告的'+end+'，不是今天；资料不自动更新。'
        return result
    explicit=re.fullmatch(r'(\d{4}-\d{2}-\d{2})(?:到|至|~)(\d{4}-\d{2}-\d{2})',reduced)
    year_match=re.fullmatch(r'(\d{4})年',reduced)
    if explicit:
        beginning,ending=explicit.groups()
        if date.fromisoformat(beginning).isoformat()!=beginning or date.fromisoformat(ending).isoformat()!=ending or beginning>=ending:raise ValueError('明确日期区间无效，未执行')
    elif year_match:
        year=int(year_match[1]);beginning=date(year,1,1).isoformat();ending=min(end,date(year,12,31).isoformat())
        if beginning>=ending:raise ValueError('该年份不在原研究截止日之前，需明确新截止日与资料')
    else:
        result.update(status='needs-clarification',message='尚未执行：这句话包含未明确支持的参数变化。请确认具体区间或保留原参数；不会忽略预算、费用或换标的要求。');return result
    result['changes']={'start':beginning,'as_of':ending}
    result['message']='使用明确区间'+beginning+'至'+ending+'，旧资料不足时保留缺口，不自动联网。'
    return result


def run(previous,question,out):
    prepared=plan(previous,question)
    if prepared['status']!='ready':return prepared
    result=execute(prepared['command'],out,continue_from=previous,online=False,**prepared['changes'])
    if prepared['command']=='rebalance' and prepared['changes'].get('rebalance_options',{}).get('periodicRule')=='month-change' and result.get('status')=='partial':
        try:old=json.loads((Path(previous)/'input.json').read_text('utf-8'))
        except (OSError,ValueError):old={}
        if old.get('periodicRule')=='month-change':prepared['message']='旧输入已经采用月初观察日信号、下一观察日执行规则；本次沿用该规则重算，没有改变频率或费用，也没有更新行情。'
    result['followupInterpretation']=prepared['message']
    directory=Path(out)
    if directory.is_dir() and result.get('failureKind')!='output-exists' and (directory/'start-result.json').is_file():
        (directory/'追问解释.json').write_text(json.dumps(prepared,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
        note='# 这句话如何沿用资料\n\n'+prepared['message']+'\n\n研究完成范围见打开这里.html；这里解释参数处理，不是投资结论。\n'
        from research_brief_html import render
        (directory/'追问解释.md').write_text(note,'utf-8');(directory/'追问解释.html').write_text(render(note,'追问如何沿用资料'),'utf-8')
        if prepared.get('questionType') and (directory/'comparison/input.json').is_file():
            from fund_comparison_question import answer
            document=json.loads((directory/'comparison/input.json').read_text('utf-8'))
            data,body=answer(document,prepared['questionType'])
            (directory/'风险追问.json').write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
            (directory/'风险追问.md').write_text(body,'utf-8');(directory/'风险追问.html').write_text(render(body,'基金风险追问'),'utf-8')
            result['headline']=data['conclusion']
            result['nextSteps'].insert(0,'先打开风险追问.html，它直接回答本次问题；完整资料范围见比较报告。')
            from fund_comparison_question import register
            register(directory,result.get('savedAt'))
        elif prepared.get('questionType') in ('portfolio-drag','portfolio-gain') and (directory/'result.json').is_file():
            from portfolio_history_report import contribution_question
            data,body=contribution_question(json.loads((directory/'result.json').read_text('utf-8')),json.loads((directory/'input.json').read_text('utf-8')),prepared['questionType'].split('-')[1])
            for suffix,value in [('json',json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)),('md',body),('html',render(body,'组合收益追问'))]:
                (directory/('组合收益追问.'+suffix)).write_text(value,'utf-8')
            result['headline']=data['conclusion'];result['nextSteps'].insert(0,'先打开组合收益追问.html；收益贡献不是个人损益或交易指令。')
            manifest=json.loads((directory/'report-manifest.json').read_text('utf-8'))
            manifest['primaryReport']='组合收益追问.html'
            manifest['files'].update({name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in ('组合收益追问.json','组合收益追问.md','组合收益追问.html')})
            (directory/'report-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
        elif prepared.get('questionType')=='money-concentration' and (directory/'result.json').is_file():
            from snapshot_question import answer
            data,body=answer(json.loads((directory/'result.json').read_text('utf-8')))
            for suffix,value in [('json',json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)),('md',body),('html',render(body,'持仓金额追问'))]:
                (directory/('持仓追问.'+suffix)).write_text(value,'utf-8')
            result['headline']=data['conclusion'];result['nextSteps'].insert(0,'先打开持仓追问.html，查看资金集中位置与目前不能判断的风险。')
            manifest={'artifactType':'snapshot-question','primaryReport':'持仓追问.html','savedAt':result.get('savedAt'),'inputSha256':hashlib.sha256((directory/'input.csv').read_bytes()).hexdigest(),'files':{name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in ('持仓追问.json','持仓追问.md','持仓追问.html')},'sourceVerification':'user-declared-not-verified','visualReview':'not-performed'}
            manifest['methodFiles']={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('snapshot_question.py','quick_research.py','research_brief_html.py')}
            (directory/'report-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),'utf-8')
        (directory/'start-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
        from result_entry import write_entry
        write_entry(directory,result)
    return result


def run_from_search(folder,query,question,out):
    """Only a single matching saved record is selected; never choose the first hit."""
    if not isinstance(query,str) or not query.strip():raise ValueError('请给出查找旧报告的名称、代码或关键词')
    from research_results import publish
    with tempfile.TemporaryDirectory(prefix='research-search-') as temporary:
        rows=publish(Path(folder),Path(temporary)/'查找.md',query=query)
    if len(rows)!=1:
        return {'status':'needs-clarification','message':('找到多份匹配报告，请明确要沿用哪份；尚未开始续算。' if rows else '没有找到匹配报告，请确认目录或关键词；尚未开始续算。'),
                'matches':[{'name':r['name'],'period':r.get('period'),'status':r['status']} for r in rows]}
    row=rows[0];entry=row.get('entry')
    if entry is None:
        return {'status':'needs-clarification','message':'匹配记录没有有效阅读入口，请先处理旧报告的资料或输入问题；尚未续算。'}
    previous=Path(entry).parent
    if not (previous/'research-request.json').is_file():
        return {'status':'needs-clarification','message':'找到了旧报告，但缺少接续请求记录。请明确原参数；不会从报告正文猜输入。'}
    return run(previous,question,out)


if __name__=='__main__':
    from cli_text import configure
    configure()
    p=argparse.ArgumentParser(description='沿用明确旧报告处理常用追问，不是任意问题自动规划')
    source=p.add_mutually_exclusive_group(required=True)
    source.add_argument('--previous');source.add_argument('--folder');p.add_argument('--query')
    p.add_argument('--question',required=True);p.add_argument('--out-dir',required=True);a=p.parse_args()
    if a.folder and not a.query:p.error('--folder需要--query，避免默认选择最新或第一份')
    if a.previous and a.query:p.error('--query只用于--folder查找')
    try:
        result=run_from_search(a.folder,a.query,a.question,a.out_dir) if a.folder else run(a.previous,a.question,a.out_dir)
        print(result.get('followupInterpretation') or result.get('message','请查看结果状态'))
        for candidate in result.get('matches',[]):print(candidate['name']+' · '+str(candidate.get('period') or '区间未登记'))
        if result['status'] in ('needs-clarification','blocked'):raise SystemExit(2)
    except (ValueError,OSError,KeyError,TypeError) as error:p.exit(2,str(error)+'\n')
