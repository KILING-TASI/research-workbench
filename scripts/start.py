"""Small offline first-use gateway; delegates research to existing implementations."""
import argparse
import csv
import json
import os
import sys
import hashlib
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTINUABLE=('funds','snapshot','portfolio','compare','news','style','lookthrough','rebalance','bjx','allocation','cashflow','convertible')


def load_input(path):
    from collection_validation import unique_pairs, reject_constant, finite_json_float
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      object_pairs_hook=unique_pairs, parse_constant=reject_constant,
                      parse_float=finite_json_float)


def verify_continuation_input(previous,prior,path,filename):
    if path.is_symlink() or not path.resolve().is_relative_to(previous.resolve()):raise ValueError('旧输入路径异常，请显式提供新输入')
    expected=prior.get('savedInputSha256')
    origin='matched-request-hash'
    if expected is None:
        manifest=previous/'report-manifest.json';origin='matched-manifest-hash'
        if manifest.is_file():
            if manifest.is_symlink() or manifest.stat().st_size>1024*1024:raise ValueError('旧报告清单异常，请显式提供新输入')
            data=load_input(manifest)
            if isinstance(data,dict) and isinstance(data.get('files'),dict):expected=data['files'].get(filename)
    if expected is None:return 'legacy-no-registered-input-hash'
    if not isinstance(expected,str) or not re.fullmatch(r'[0-9a-f]{64}',expected):raise ValueError('旧输入摘要记录无效，请显式提供新 --input')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('已保存输入发生变化，不能当作原资料续算；如需使用改后的资料，请显式提供新 --input，旧报告保留不变')
    return origin


def execute(command, destination, input_path=None, example='compare', question=None, as_of=None, online=False, codes=None, start=None, group=None, names=None, reuse_from=None, continue_from=None, rebalance_options=None, budget=None, check_entry=None):
    """Publish a complete result or a useful failure, without replacing user files."""
    destination = Path(destination)
    if destination.exists():
        return {'status': 'blocked', 'failureKind': 'output-exists',
                'message': '输出目录已有内容，本次没有覆盖。',
                'nextSteps': ['换一个尚不存在的 --out-dir 目录后重新运行。']}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.first-use-', dir=destination.parent) as temporary:
        stage = Path(temporary) / 'result'
        request=None;input_reuse=None
        try:
            if check_entry is not None and command!='doctor':raise ValueError('--for-entry 只用于doctor，不为其他研究设置总门槛')
            if rebalance_options and command!='rebalance':raise ValueError('再平衡参数仅适用于rebalance')
            if budget is not None and command!='bjx':raise ValueError('预算修改仅适用于北交情景入口')
            if continue_from:
                if command not in CONTINUABLE:raise ValueError('当前入口不支持保存请求接续')
                previous=Path(continue_from).resolve()
                request_path=(previous/'research-request.json').resolve()
                if not request_path.is_relative_to(previous) or request_path.stat().st_size>1024*1024:raise ValueError('上次请求记录路径或大小异常')
                prior=load_input(request_path)
                if not isinstance(prior,dict) or prior.get('command')!=command:raise ValueError('上次研究类型与当前入口不一致')
                if command=='funds':
                    if not codes and not names:
                        codes=prior.get('codes');names=prior.get('names')
                    start=start or prior.get('start');as_of=as_of or prior.get('asOf')
                    group=group if group is not None else prior.get('group')
                    reuse_from=reuse_from or previous
                else:
                    if not input_path:
                        filename='input.csv' if command=='snapshot' else 'input.json'
                        input_path=(previous/filename).resolve()
                        if not input_path.is_relative_to(previous):raise ValueError('旧输入指向结果目录外，请显式提供输入')
                        input_reuse=verify_continuation_input(previous,prior,input_path,filename)
                    else:input_reuse='explicit-new-input'
                    if command=='snapshot':as_of=as_of or prior.get('asOf')
            if sys.version_info < (3, 11):
                raise RuntimeError('此入口需要 Python 3.11 或更高版本')
            if command == 'doctor':
                from environment_check import inspect, markdown
                result = inspect(entry=check_entry) if check_entry else inspect()
                stage.mkdir()
                (stage / 'environment.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), 'utf-8')
                (stage / '环境检查.md').write_text(markdown(result), 'utf-8')
                summary = {'status': 'passed', 'mode': 'environment-check',
                           'message': '环境检查完成；未联网，未安装组件。',
                           'nextSteps': ['先运行 demo；缺少可选组件不妨碍标准库离线示例。']}
                if check_entry:
                    summary['checkedEntry']=check_entry
                    summary['message']='本次入口的软件检查已完成；尚未计算或核验资料。'
                    dependency=result.get('specialistDependency')
                    summary['nextSteps']=(dependency['nextSteps'] if dependency and not dependency['available'] else
                                          ['只处理本次入口所列缺项；软件可定位后仍需核对资料并实跑。'])
            elif command == 'ask':
                from research_question import run
                from research_brief_html import render
                if not question or not as_of:
                    raise ValueError('ask 需要 --question 和 --as-of；支持单家A股近一或三个月公告')
                spec = {'question': question, 'asOf': as_of, 'market': 'CN', 'onlineSearch': online, 'refresh': online}
                result = run(spec, stage)
                archive_file = Path(result['archivePath'])
                result['archivePath'] = str((destination.resolve() / archive_file.resolve().relative_to(stage.resolve())).resolve())
                archive_file.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), 'utf-8')
                (stage / '研究结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), 'utf-8')
                (stage / '研究结果.md').write_text(result['answer'], 'utf-8')
                (stage / '研究结果.html').write_text(render(result['answer'], 'A股公告变化研究'), 'utf-8')
                summary = {'status': result['status'], 'mode': 'announcement-research',
                           'message': '公告研究已留存，当前状态：' + result['status'],
                           'sourceVerification': 'not-verified', 'visualReview': 'not-performed',
                           'nextSteps': result['nextSteps']}
            elif command == 'snapshot':
                from quick_research import snapshot
                if not input_path or not as_of:
                    raise ValueError('snapshot 需要 --input 持仓CSV 与 --as-of 截止日')
                request={'command':'snapshot','asOf':as_of}
                result = snapshot(input_path, stage, as_of)
                request['names']=[row['name'] for row in result['holdings']]
                request['codes']=[row['code'] for row in result['holdings']]
                request['subjectIdentity']='user-declared-not-verified'
                summary = {'status':result['status'], 'mode':'holdings-snapshot',
                           'headline':result.get('headline'),
                           'message':'持仓结构报告已生成；底层风险与完整诊断尚未完成。',
                           'nextSteps':['打开持仓结构.html。','再提供底层持仓、历史序列与资金用途；不从名称猜行业或替用户设限。']}
            elif command == 'rebalance':
                from rebalance_brief import publish_input, markdown
                if not input_path:raise ValueError('再平衡需要已对齐历史与明确费用输入；AI复用既有资料准备，不从持仓金额猜历史')
                request={'command':'rebalance'}
                result=publish_input(load_input(input_path),stage,rebalance_options)
                request.update(codes=[a['code'] for a in result['assets']],start=result['start'],asOf=result['end'])
                request['names']=[a['name'] for a in result['assets'] if a.get('name')]
                summary={'status':'partial','mode':'rebalance-research','headline':markdown(result).split('\n')[2].removeprefix('> '),
                         'message':'再平衡历史比较已生成；真实成交规则与样本外验证尚未完成。',
                         'nextSteps':['打开再平衡历史比较.html，查看收益、回撤和费用的取舍。']}
                if continue_from:
                    from rebalance_brief import followup
                    from research_brief_html import render
                    try:
                        body=followup(result,load_input(stage/'input.json'),continue_from)
                    except (OSError,ValueError,TypeError,KeyError):
                        body='# 调整前后比较\n\n旧输入或结果暂不能可靠读取，未做前后数值比较；本次研究已独立完成。'
                    (stage/'调整前后比较.md').write_text(body,'utf-8')
                    (stage/'调整前后比较.html').write_text(render(body,'调整前后比较'),'utf-8')
                    summary['nextSteps'].append('追问对照见调整前后比较.html；不同历史或组合条件不强作参数归因。')
            elif command == 'bjx':
                from bjx_scenario_gateway import publish
                if not input_path:raise ValueError('北交情景需要已确认的发行资料及情景输入，由AI复用资料准备')
                request={'command':'bjx'}
                result,headline=publish(load_input(input_path),stage,budget)
                request.update(codes=[result['code']])
                allocation=load_input(stage/'input.json')['allocation']
                request['scenarioDates']={key:allocation[key] for key in ('applyDate','refundDate','saleSettlementDate')}
                summary={'status':'partial','mode':'bjx-joint-scenarios','headline':headline,
                         'message':'北交资金与收益情景已生成；余股、实际配售和卖出价格仍未确定。',
                         'nextSteps':['打开北交所资金与收益情景.html；先看比例整手、费用与资金日期，再核对公告依据。']}
                if result.get('exampleType')=='teaching-only':
                    summary['exampleType']='teaching-only'
                    summary['message']='北交教学情景已生成；不是真实新股或账户测算。'
            elif command == 'portfolio':
                from portfolio_history_report import publish
                if not input_path:
                    raise ValueError('portfolio 需要 --input 已有组合历史输入JSON')
                request={'command':'portfolio'}
                portfolio_result=publish(load_input(input_path), stage)
                request=load_input(stage/'research-request.json')
                summary = {'status':'partial','mode':'historical-portfolio',
                           'headline':portfolio_result.get('headline'),
                           'message':'组合历史报告已生成；不等于真实账户收益或未来风险。',
                           'nextSteps':['打开组合历史风险观察.html；查看共同路径、收益贡献、相关性与资料限制。']}
            elif command=='convertible':
                request={'command':'convertible'}
                from convertible_review import publish
                if not input_path:raise ValueError('可转债诊断需要已核现金流、全价和转股价，由AI准备或沿用旧报告')
                result=publish(load_input(input_path),stage)
                summary={'status':'partial','mode':'convertible-cashflow-review',
                         'headline':'按给定现金流，税前到期年化收益率为'+format(result['yieldScenarios'][0]['yieldPct'],'.2f')+'%。',
                         'message':'可转债基础诊断已生成；完整条款核验与含权定价尚未完成。',
                         'nextSteps':['打开可转债基础诊断.html，查看到期收益、转股溢价和条款条件限制。']}
                if result.get('exampleType')=='teaching-only':summary['exampleType']='teaching-only'
            elif command=='cashflow':
                request={'command':'cashflow'}
                from portfolio_cashflow_review import publish
                if not input_path:raise ValueError('出入金复盘需要已取得的现金流前后估值，由AI准备；不能从期末截图猜历史')
                document=load_input(input_path)
                from specialist_loader import require
                dependency=require('portfolio','observed_review','review')
                result=publish(document,stage);request=load_input(stage/'research-request.json')
                headline=result['headline']
                summary={'status':'partial','mode':'cashflow-observed-review','headline':headline,'message':'出入金与收益观察已生成；完整性仅为声明，不认证账户或实际到账。','nextSteps':['打开组合出入金与收益观察.html，核对估值、投入取出、币种单位和期末假设变现。']}
                summary['dependencyCheck']=dependency
                if result.get('exampleType')=='teaching-only':summary['exampleType']='teaching-only'
            elif command=='allocation':
                request={'command':'allocation'}
                from portfolio_allocation_report import publish
                if not input_path:raise ValueError('配置研究需要已有对齐历史与明确约束，由AI准备或沿用旧报告')
                result=publish(load_input(input_path),stage)
                request=load_input(stage/'research-request.json')
                summary={'status':'partial','mode':'allocation-candidate-review','headline':'配置候选已生成；仅历史风险比较，不等于完整回撤预算或交易方案。','message':'查看等权、最小方差与风险平价候选的约束和取舍。','nextSteps':['打开组合配置候选比较.html；核对类别、上下限、资料日期与未完成条件。']}
                if result.get('exampleType')=='teaching-only':summary['exampleType']='teaching-only'
            elif command in ('style','lookthrough'):
                if not input_path:raise ValueError('此研究需要已取得且明确对齐的输入资料')
                request={'command':command};document=load_input(input_path)
                if command=='style':
                    from returns_style import publish
                    result=publish(document,stage)
                    request.update(codes=[result['fundCode']]+result['benchmarkCodes'],start=result['start'],asOf=document['asOf'])
                    request['names']=[name for name in [result.get('fundName')]+result.get('benchmarkNames',[]) if name]
                    headline='选定基准对本段收益波动的解释度为'+format(result['fullSample']['rSquaredVariance']*100,'.2f')+'%；拟合关系不是持仓比例或违规判断。'
                else:
                    from research_extensions import publish_fof
                    result=publish_fof(document,stage)
                    request.update(codes=list(document['nodes']),asOf=document['asOf'])
                    concentration=result['equityConcentration'] or {}
                    headline=('已映射股票集中度相当于'+format(float(concentration['effectiveIssuerCount']),'.2f')+'个等权主体，仅描述已知部分。' if concentration.get('effectiveIssuerCount') is not None else '公司层面的有效持仓尚不能判断；可先观察已知证券集中度，并补充发行人关系。')
                summary={'status':'partial','mode':command+'-observation','headline':headline,'message':'已生成'+('收益风格' if command=='style' else '组合穿透与冗余')+'说明；实际持仓、身份与适用范围仍按报告缺口核查。',
                         'nextSteps':['打开所列主报告，先看结论、覆盖范围与下一步。'],'sourceVerification':'not-verified','visualReview':'not-performed'}
            elif command == 'funds':
                from quick_research import fund_codes
                if not online and not reuse_from:
                    raise ValueError('funds 需要主动启用 --online；已有净值文件请使用 compare')
                if not start or not as_of:
                    raise ValueError('funds 需要 --start 和 --as-of 明确历史区间')
                if group is None:group='用户指定比较池（未核验同类）'
                if not isinstance(group,str) or not group.strip():raise ValueError('比较池名称不能为空；也可省略 --group')
                request={'command':'funds','codes':codes,'names':names,'start':start,'asOf':as_of,'group':group}
                identity=None
                if names:
                    if codes:raise ValueError('名称与代码不能同时指定；请确认一种输入')
                    from fund_name_resolver import resolve
                    identity_directory=Path(temporary)/'identity'
                    identity=resolve(names,identity_directory,online=online,reuse_from=reuse_from)
                    if identity['status']=='resolved':codes=identity['codes']
                    else:
                        stage.mkdir()
                        summary={'status':'needs-clarification','message':'基金名称需要确认，候选已留存，尚未开始净值下载。',
                                 'nextSteps':['打开名称确认报告，确认完整名称与A/C等份额后，用明确代码继续。']}
                if identity is None or identity['status']=='resolved':
                    summary = fund_codes(codes, start, as_of, group, stage,reuse_from=reuse_from,allow_online=online)
                    comparison_input=stage/'comparison'/'input.json'
                    if comparison_input.is_file():
                        compared=load_input(comparison_input)
                        request['resolvedNames']=[row['name'] for row in compared.get('rows',[]) if isinstance(row,dict) and row.get('code') in codes and isinstance(row.get('name'),str)]
                        if continue_from:
                            from fund_comparison_followup import build
                            from research_brief_html import render
                            try:
                                followup,body=build(continue_from,compared)
                                (stage/'追问对照.json').write_text(json.dumps(followup,ensure_ascii=False,indent=2,allow_nan=False),'utf-8')
                            except (OSError,ValueError,TypeError,KeyError):
                                body='# 本次追问对照\n\n本次比较已独立完成，但旧输入或留痕不完整，未做可靠的前后对照。请读本次主报告；旧报告未覆盖。'
                            (stage/'追问对照.md').write_text(body,'utf-8');(stage/'追问对照.html').write_text(render(body,'基金比较追问对照'),'utf-8')
                            summary['nextSteps'].append('追问对照.html说明区间、口径与结论变化；不把差别写成产品改善。')
                if identity:os.rename(identity_directory,stage/'identity')
                summary['mode']='fund-code-comparison'
            else:
                mode = example if command == 'demo' else command
                if mode not in ('compare', 'news'):
                    raise ValueError('当前快速入口支持 compare 和 news')
                example_file = 'comparison-example.json' if mode == 'compare' else 'news-example.json'
                selected = ROOT / 'references/examples' / example_file if command == 'demo' else input_path
                if not selected:
                    raise ValueError('正式研究需要 --input 输入文件；首次试用请运行 demo')
                document = load_input(selected)
                if command!='demo':request={'command':command}
                headline=None
                if mode == 'compare':
                    from fund_comparison_brief import publish
                    comparison=publish(document, stage)
                    headline=next((finding['conclusion'] for finding in comparison['findings'] if finding.get('conclusion')),None)
                else:
                    from retail_research import run
                    wrapper=run(document, stage)
                    if wrapper['result'].get('type')=='retail-event-exposure':
                        observation=wrapper['result']
                        headline=('已识别直接关联持仓，占声明组合'+observation['relatedWeightPct']+'%；关联市值不是预计损失。' if observation['relatedHoldings'] else '尚未确认直接持仓关联，不能据此认为消息无影响；底层与影响路径仍需核查。')
                summary = {'status': 'passed' if command=='demo' else 'partial', 'mode': 'teaching-demo' if command == 'demo' else 'user-input-research',
                           'headline':headline,
                           'message': '已生成自然语言报告与输入底稿。',
                           'sourceVerification': 'not-verified', 'visualReview': 'not-performed',
                           'nextSteps': ['打开输出目录中的 HTML 或 Markdown 报告。',
                                         '教学示例不是实际基金或账户；正式研究请提供真实输入。'] if command == 'demo' else
                                        ['阅读报告中的结论、口径与缺口；来源真实性仍需核验。']}
        except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError, ArithmeticError, csv.Error) as error:
            from specialist_loader import SpecialistUnavailableError
            if isinstance(error,SpecialistUnavailableError):
                dependency=error.dependency_record
                kind,steps='missing-dependency',(dependency['nextSteps'] if dependency else
                    ['使用含本次迁移接口的兼容专业包，或按安装说明设置可信项目目录；不自动安装。'])
            elif isinstance(error, ImportError):
                kind, steps = 'missing-dependency', ['运行 doctor 查看当前依赖。', '按 references/standalone-install.md 安装本次功能需要的组件。']
            elif isinstance(error, FileNotFoundError):
                kind, steps = 'missing-input', ['确认 --input 文件存在；相对路径以当前终端目录为起点。', '首次试用可改用 demo，无须准备输入。']
            else:
                kind, steps = 'invalid-input-or-runtime', ['核对输入格式与日期、净值、分红口径。', '先运行 demo 区分输入问题和运行环境问题。']
                if command=='snapshot':
                    steps=['核对持仓表的代码、名称、当前市值、币种和资产类型；支持明确中文列名。',
                           '市值填币种基本单位的数字；不把本金、份额或“万”当市值，日期用YYYY-MM-DD。']
                elif command=='rebalance':
                    steps=['核对共同历史日期、币种、总收益口径、权重和显式费用。',
                           'AI按已说明的问题调整输入后另存重试；不猜缺失价格，也不自动放宽约束。']
                elif command=='cashflow':
                    steps=['核对币种、金额单位、日期以及每笔出入金前后估值；未知现金流不能按零处理。',
                           '补齐并确认新版记录后另存重试；不能仅修改完整性声明来绕过数据缺口。']
                    if '外部现金流完整' in str(error):
                        steps[0]='先补齐并核对本区间全部外部转入、取出及前后估值；资料不完整时暂不计算收益。'
            summary = {'status': 'blocked', 'failureKind': kind, 'message': str(error), 'nextSteps': steps}
            if isinstance(error,SpecialistUnavailableError):
                summary['message']='这项测算需要的兼容专业工具尚未就绪；其他研究可以继续。'
                if error.dependency_record:summary['dependencyCheck']=error.dependency_record
            if isinstance(error,ImportError):
                component=getattr(error,'name',None)
                if isinstance(component,str) and component.split('.')[0]=='numpy':summary['message']='配置与矩阵计算需要的组件还没准备好，这次没有算出结果。已经提供的资料会保留，补齐环境后可以接着算。'
                else:summary['message']='这项研究需要的组件暂时没能加载，所以这次还没有算出结果。先检查运行环境，补齐后可以继续。'
            # Remove partial artifacts by leaving their temporary directory unpublished.
            failure_stage = Path(temporary) / 'failure'
            failure_stage.mkdir()
            if isinstance(error,ImportError):(failure_stage/'环境诊断.txt').write_text(str(error),'utf-8')
            if command=='rebalance' and isinstance(getattr(error,'technical_details',None),str):
                (failure_stage/'计算诊断.txt').write_text(error.technical_details,'utf-8')
            if command in ('rebalance','bjx','allocation','cashflow','convertible') and input_path:
                try:
                    source=Path(input_path)
                    if source.stat().st_size<=16*1024*1024:
                        document=load_input(source)
                        try:
                            if command=='bjx':
                                from bjx_scenario_gateway import adjust
                                document=adjust(document,budget)
                            elif command=='rebalance':
                                from rebalance_brief import adjust_input
                                document=adjust_input(document,rebalance_options)
                        except (ValueError,TypeError):pass
                        (failure_stage/'input.json').write_text(json.dumps(document,ensure_ascii=False,allow_nan=False,indent=2),'utf-8')
                except (OSError,ValueError,TypeError):pass
            if command=='funds':
                retained=[]
                for name in ('raw','collection.json'):
                    source=stage/name
                    if source.exists() and source.resolve().is_relative_to(Path(temporary).resolve()):
                        os.rename(source,failure_stage/name);retained.append(name)
                identity_source=Path(temporary)/'identity'
                if identity_source.exists():
                    os.rename(identity_source,failure_stage/'identity-failed');retained.append('identity-failed')
                if retained:
                    summary['retainedArtifacts']=retained
                    steps.append('已取得的原响应保留在本结果目录，可核对失败原因；未把它们认证为成功研究。')
            stage = failure_stage
            (stage / '下一步.md').write_text('# 本次研究尚未完成\n\n' + summary['message'] + '\n\n' +
                                            '\n'.join('- ' + step for step in steps), 'utf-8')
        from result_entry import write_entry
        if continue_from:
            previous=Path(continue_from).resolve();entry=previous/'打开这里.html'
            if entry.is_file() and not entry.is_symlink() and entry.resolve().is_relative_to(previous):
                try:
                    relative=os.path.relpath(entry,destination)
                    summary['previousStudy']={'entry':Path(relative).as_posix(),'scope':'explicitly-selected-previous-result-not-refreshed'}
                except ValueError:
                    summary['previousStudy']={'entry':None,'scope':'previous-result-on-another-drive'}
        if request:
            saved_input=stage/('input.csv' if command=='snapshot' else 'input.json')
            if saved_input.is_file():request['savedInputSha256']=hashlib.sha256(saved_input.read_bytes()).hexdigest()
            (stage/'research-request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),'utf-8')
            manifest=stage/'report-manifest.json'
            if manifest.is_file():
                registered=load_input(manifest)
                if isinstance(registered,dict) and isinstance(registered.get('files'),dict) and isinstance(registered['files'].get('research-request.json'),str):
                    registered['files']['research-request.json']=hashlib.sha256((stage/'research-request.json').read_bytes()).hexdigest()
                    manifest.write_text(json.dumps(registered,ensure_ascii=False,indent=2),'utf-8')
            summary['nextSteps'].append('接着本次研究：同一入口指定 --continue-from 本结果目录，并使用新的 --out-dir。'+('可修改日期；旧资料不足时显式增加 --online。' if command=='funds' else '更新持仓或历史数据需用 --input 提供新资料；复用不会自动更新价格。'))
        if input_reuse:summary['inputReuseVerification']=input_reuse
        write_entry(stage,summary)
        summary['savedAt']=datetime.now(timezone.utc).isoformat(timespec='seconds')
        (stage / 'start-result.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), 'utf-8')
        if destination.exists():
            raise FileExistsError('输出目录在运行期间被创建，本次未覆盖')
        os.rename(stage, destination)
    return summary


def main():
    parser = argparse.ArgumentParser(description='快速研究入口；ask或funds显式 --online 才联网，不自动安装依赖。')
    parser.add_argument('command', choices=['demo', 'doctor', 'compare', 'news', 'ask', 'snapshot', 'portfolio', 'funds','style','lookthrough','rebalance','bjx','allocation','cashflow','convertible'])
    parser.add_argument('--input', type=Path)
    parser.add_argument('--example', choices=['compare', 'news'], default='compare')
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--for-entry',choices=['demo','compare','news','snapshot','cashflow','fund-report-six-column','original-schema1'],help='doctor：只检查这一个入口的软件，不检查数据或安装组件')
    parser.add_argument('--question', help='ask：单家A股近一或三个月公告问题')
    parser.add_argument('--as-of', help='ask：研究截止日 YYYY-MM-DD')
    parser.add_argument('--online', action='store_true', help='ask/funds：主动取数；funds复用时只补不可用资料')
    parser.add_argument('--codes', nargs='+', help='funds：2至10个六位场外基金代码')
    parser.add_argument('--names',nargs='+',help='funds：2至10个完整基金名称，歧义时给候选')
    parser.add_argument('--reuse-from',type=Path,help='funds：复用旧输出的原响应；另建新输出，不修改旧报告')
    parser.add_argument('--continue-from',type=Path,help='常用输入研究沿用上次请求或输入；不自动更新资料')
    parser.add_argument('--start', help='funds：历史起点 YYYY-MM-DD')
    parser.add_argument('--group', help='funds：可选比较池名称，不代表同类认证')
    parser.add_argument('--budget',help='bjx：明确新的人民币元预算，复用其他输入，不自动顶格')
    parser.add_argument('--every-observations',type=int,help='rebalance：每几个观察期触发；不是日历月')
    parser.add_argument('--rebalance-schedule',choices=['every-observations','month-change'],help='rebalance：观察期或新月份首个观察日形成信号，下一观察日执行')
    parser.add_argument('--split-date',help='rebalance：指定共同观察日做历史前后段比较，非事前样本外认证')
    parser.add_argument('--cost-reference',action=argparse.BooleanOptionalAction,default=None,help='rebalance：同规则零摩擦对照，区分支付成本与期末财富差')
    parser.add_argument('--commission-pct',type=float,help='rebalance：统一佣金百分数，0.03表示0.03%%')
    parser.add_argument('--minimum-commission',type=float,help='rebalance：每腿最低佣金，输入币种金额')
    parser.add_argument('--spread-bps',type=float,help='rebalance：全价差bp，每腿计一半')
    parser.add_argument('--slippage-bps',type=float,help='rebalance：每腿滑点bp')
    args = parser.parse_args()
    if args.for_entry and args.command!='doctor':parser.error('--for-entry只用于doctor')
    if args.command == 'demo' and args.input:
        parser.error('demo 使用教学输入；真实输入请用 compare 或 news')
    if args.command not in ('ask','funds') and args.online:
        parser.error('--online 仅用于 ask 或 funds')
    if args.command != 'ask' and args.question:
        parser.error('--question 仅用于 ask')
    if args.command not in ('ask','funds','snapshot') and args.as_of:
        parser.error('--as-of 用于 ask、funds 或 snapshot')
    if args.command != 'funds' and (args.codes or args.names or args.start or args.group or args.reuse_from):
        parser.error('--codes、--names、--start、--group、--reuse-from 仅用于 funds')
    if args.continue_from and args.command not in CONTINUABLE:
        parser.error('当前入口不支持 --continue-from')
    if args.command == 'ask' and args.input:
        parser.error('ask 使用问题参数；已有消息文件请用 news')
    if args.command == 'funds' and args.input:
        parser.error('funds 使用代码取数；已有净值文件请用 compare')
    options={key:value for key,value in [('everyObservations',args.every_observations),('commissionPct',args.commission_pct),('minimumCommission',args.minimum_commission),('spreadBps',args.spread_bps),('slippageBps',args.slippage_bps)] if value is not None}
    if args.rebalance_schedule:options['periodicRule']=args.rebalance_schedule
    if args.split_date:options['validationSplit']=args.split_date
    if args.cost_reference is not None:options['costCounterfactual']=args.cost_reference
    if options and args.command!='rebalance':parser.error('频率和费用参数仅用于rebalance')
    if args.budget is not None and args.command!='bjx':parser.error('--budget仅用于bjx情景')
    result = execute(args.command, args.out_dir, args.input, args.example, args.question, args.as_of, args.online, args.codes, args.start, args.group,args.names,args.reuse_from,args.continue_from,options,args.budget,check_entry=args.for_entry)
    print(result['message'])
    for step in result['nextSteps']:
        print('- ' + step)
    print('结果目录：' + str(args.out_dir.resolve()))
    if result.get('failureKind')!='output-exists' and (args.out_dir/'打开这里.html').is_file():
        print('先打开：' + str((args.out_dir/'打开这里.html').resolve()))
    return 0 if result['status'] in ('passed', 'partial') else 2


if __name__ == '__main__':
    from cli_text import configure
    configure()
    raise SystemExit(main())
