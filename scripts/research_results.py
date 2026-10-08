"""List quick-entry results in an explicitly selected folder, without networking."""
import argparse
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote
from research_brief_html import render
from collection_validation import unique_pairs, reject_constant, finite_json_float


def matches(query,text):
    return not query or all(term.casefold() in text.casefold() for term in query.split())


def report_summary(text):
    visible=[];fenced=False
    for line in text.splitlines():
        if line.lstrip().startswith(('```','~~~')):fenced=not fenced;visible.append('');continue
        if not fenced:visible.append(line)
    text='\n'.join(visible)
    quoted=next((line[2:].strip() for line in visible if line.startswith('> ') and line[2:].strip()),None)
    if quoted:return quoted[:600],'explicit-report-summary'
    # Show original opening prose, never infer an evaluation from a table or data.
    for block in text.split('\n\n'):
        lines=[line.strip() for line in block.splitlines() if line.strip()]
        if not lines or any(line.startswith(('#','|','```','- ','* ','![','<')) for line in lines):continue
        return ' '.join(lines)[:600],'opening-prose-not-inferred-conclusion'
    return None,None

def publish(folder, output, query=None, limit=None):
    folder=Path(folder).resolve();output=Path(output).absolute()
    if not folder.is_dir():raise ValueError('请指定已有研究结果父目录')
    if output.exists() or output.with_suffix('.html').exists():raise ValueError('索引输出已存在，请使用新文件名')
    if output.suffix!='.md':raise ValueError('索引输出文件使用.md后缀')
    if query is not None and (not isinstance(query,str) or not query.strip()):raise ValueError('检索词不能为空')
    if limit is not None and (isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=1000):raise ValueError('结果数量须为1至1000整数')
    rows=[]
    for directory in sorted(folder.iterdir()):
        if not directory.is_dir() or directory.is_symlink():continue
        record=directory/'start-result.json'
        manifest_mode=not record.is_file()
        if manifest_mode:record=directory/'report-manifest.json'
        if not record.is_file():continue
        try:
            if record.is_symlink() or record.stat().st_size>1024*1024:raise ValueError('记录路径或大小异常')
            data=json.loads(record.read_text('utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
            direct_entry=None
            if manifest_mode:
                if not isinstance(data,dict) or not isinstance(data.get('files'),dict):raise ValueError('报告清单缺少文件登记')
                candidates=[]
                for name in data['files']:
                    if not isinstance(name,str) or '/' in name or '\\' in name or ':' in name:continue
                    path=directory/name
                    if path.suffix.lower() in ('.html','.md') and path.is_file() and not path.is_symlink():candidates.append(path)
                if not candidates:raise ValueError('清单中没有可读取的本目录报告')
                candidates.sort(key=lambda path:(path.suffix.lower()!='.html',path.name))
                primary=data.get('primaryReport')
                if primary is not None:
                    if not isinstance(primary,str) or '/' in primary or '\\' in primary or ':' in primary or directory/primary not in candidates:raise ValueError('指定主报告不在有效报告清单内')
                    direct_entry=directory/primary
                else:direct_entry=candidates[0]
                headline=None;headline_kind=None
                paired=direct_entry.with_suffix('.md')
                markdown=paired if paired in candidates else next((path for path in candidates if path.suffix.lower()=='.md'),None)
                if markdown and markdown.stat().st_size<=1024*1024:
                    headline,headline_kind=report_summary(markdown.read_text('utf-8-sig'))
                saved_at=data.get('savedAt');followup=data.get('followup')
                data={'status':'已登记报告，未重新验收','message':'可直接打开'+direct_entry.stem+'；登记不代表完整研究或视觉验收。','headline':headline,'headlineKind':headline_kind,'savedAt':saved_at}
                if followup=='bjx-annual':data['followup']='bjx-annual'
            if not isinstance(data,dict) or not isinstance(data.get('status'),str) or not isinstance(data.get('message'),str):raise ValueError('结果记录缺少状态或说明')
            answer_manifest=directory/'report-manifest.json'
            if answer_manifest.is_file() and not answer_manifest.is_symlink() and answer_manifest.stat().st_size<=1024*1024:
                declared=json.loads(answer_manifest.read_text('utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
                if isinstance(declared,dict) and declared.get('artifactType')=='fund-risk-question':
                    from fund_comparison_question import verify_saved
                    issues=verify_saved(directory,declared)
                    if issues:
                        data=dict(data,status='记录需要复查',message='；'.join(issues)+'。未把旧结论继续展示为当前回答。',headline=None)
                    else:
                        answer_data=json.loads((directory/'风险追问.json').read_text('utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
                        if not isinstance(answer_data,dict) or not isinstance(answer_data.get('conclusion'),str):raise ValueError('追问记录缺少文字结论')
                        data=dict(data,headline=answer_data.get('conclusion'))
            entry=direct_entry or directory/'打开这里.html'
            available=entry.is_file() and not entry.is_symlink()
            request_path=directory/'research-request.json';period=None;period_kind='research-window';subjects=[];request={}
            if request_path.is_file() and not request_path.is_symlink() and request_path.stat().st_size<=1024*1024:
                try:
                    request=json.loads(request_path.read_text('utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
                    if isinstance(request,dict) and isinstance(request.get('start'),str) and isinstance(request.get('asOf'),str):period=request['start']+'至'+request['asOf']
                    if isinstance(request,dict) and request.get('command')=='bjx':
                        from datetime import date
                        dates=request.get('scenarioDates')
                        try:dates_valid=isinstance(dates,dict) and all(isinstance(dates.get(k),str) and date.fromisoformat(dates[k]).isoformat()==dates[k] for k in ('applyDate','refundDate','saleSettlementDate'))
                        except ValueError:dates_valid=False
                        if dates_valid:
                            period='申购'+dates['applyDate']+'；退款可用'+dates['refundDate']+'；卖出结算'+dates['saleSettlementDate'];period_kind='scenario-dates'
                    if isinstance(request,dict):
                        for key in ('names','resolvedNames','codes'):
                            if isinstance(request.get(key),list):subjects.extend(value for value in request[key] if isinstance(value,str))
                        if request.get('command')=='snapshot' and not request.get('names'):
                            import hashlib
                            old_result=directory/'result.json';old_csv=directory/'input.csv'
                            if all(p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(directory.resolve()) and p.stat().st_size<=16*1024*1024 for p in (old_result,old_csv)):
                                old=json.loads(old_result.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
                                if isinstance(old,dict) and old.get('inputSha256')==hashlib.sha256(old_csv.read_bytes()).hexdigest() and isinstance(old.get('holdings'),list):
                                    for holding in old['holdings']:
                                        if isinstance(holding,dict):
                                            subjects.extend(holding[k] for k in ('name','code') if isinstance(holding.get(k),str))
                        if request.get('command')=='funds' and not request.get('resolvedNames'):
                            old_input=directory/'comparison'/'input.json'
                            if old_input.is_file() and not old_input.is_symlink() and old_input.resolve().is_relative_to(directory.resolve()) and old_input.stat().st_size<=16*1024*1024:
                                old=json.loads(old_input.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)
                                if isinstance(old,dict) and isinstance(old.get('rows'),list):
                                    subjects.extend(r['name'] for r in old['rows'] if isinstance(r,dict) and (not isinstance(request.get('codes'),list) or r.get('code') in request['codes']) and isinstance(r.get('name'),str))
                except (OSError,ValueError):pass
            if isinstance(request,dict):
                from start import CONTINUABLE,verify_continuation_input
                if request.get('command') in CONTINUABLE and request['command']!='funds':
                    filename='input.csv' if request['command']=='snapshot' else 'input.json'
                    try:verify_continuation_input(directory,request,directory/filename,filename)
                    except (OSError,ValueError,TypeError) as error:
                        data=dict(data,status='记录需要复查',message='保存输入需复查：'+str(error)+'。未继续展示旧摘要。',headline=None)
            row={'name':directory.name,'status':data['status'],'message':data['message'],'headline':data.get('headline') if isinstance(data.get('headline'),str) else None,'period':period,'subjects':subjects,'entry':entry if available else None}
            row['periodKind']=period_kind
            row['subjectIdentity']='user-declared-not-verified' if isinstance(request,dict) and request.get('command')=='snapshot' else None
            row['headlineKind']=data.get('headlineKind')
            previous=data.get('previousStudy');row['hasPreviousStudy']=isinstance(previous,dict) and previous.get('scope')=='explicitly-selected-previous-result-not-refreshed'
            row['independentEngine']=None
            if isinstance(request,dict) and request.get('command')=='independent' and request.get('engine') in ('financial','lookthrough'):row['independentEngine']=request['engine']
            row['followup']=data.get('followup')
            row['savedAt']=None;row['savedTimestamp']=None
            try:
                value=data.get('savedAt')
                timestamp=datetime.fromisoformat(value.replace('Z','+00:00')) if isinstance(value,str) else None
                if timestamp is not None and timestamp.tzinfo is not None and timestamp<=datetime.now(timezone.utc):
                    row['savedAt']=timestamp.isoformat();row['savedTimestamp']=timestamp.timestamp()
            except (ValueError,OverflowError):pass
            search_text=' '.join(str(row.get(key) or '') for key in ('name','message','headline','period'))+' '+' '.join(subjects)
            if matches(query,search_text):rows.append(row)
        except (OSError,ValueError,TypeError) as error:
            if matches(query,directory.name):rows.append({'name':directory.name,'status':'记录不可读取','message':str(error),'entry':None})
    rows.sort(key=lambda row:(row.get('savedTimestamp') is None,-(row.get('savedTimestamp') or 0),row['name']))
    matched=len(rows)
    if limit is not None:rows=rows[:limit]
    body='# 我的研究结果\n\n从下列入口继续查看报告、资料限制与下一步。本页只读取指定目录的直接子目录，不联网、不改旧报告。\n\n有留存时间的记录由新到旧排列；旧记录缺时间排在其后，不从文件修改时间推断研究新旧。留存时间不代表数据已更新。\n'
    if limit is not None:body+=f'\n找到{matched}条匹配记录，本页显示前{len(rows)}条；这不是筛选研究质量或最新行情。\n'
    for row in rows:
        label=row['name'].replace('[','').replace(']','').replace('\n',' ')
        states={'partial':'已完成部分研究','passed':'本次结果已生成','blocked':'尚未完成，需要处理资料或输入','needs-clarification':'需要确认标的或资料'}
        body+='\n## '+label+'\n\n状态：'+states.get(row['status'],row['status'])+'\n\n'+row['message']+'\n'
        if row.get('subjects'):body+='\n'+('持仓项目（用户声明，未核验身份）：' if row.get('subjectIdentity')=='user-declared-not-verified' else '研究标的：')+'、'.join(dict.fromkeys(row['subjects']))+'\n'
        if row.get('headline'):body+='\n'+('正文开头摘录：' if row.get('headlineKind')=='opening-prose-not-inferred-conclusion' else '主要结论：')+row['headline']+'\n'
        if row.get('hasPreviousStudy'):body+='\n本次关联了上次研究，入口内可返回来源报告；是否完成续算以本条状态为准，不代表数据已更新。\n'
        if row.get('period'):body+='\n'+('原情景资金日期（输入声明）：' if row.get('periodKind')=='scenario-dates' else '研究区间：')+row['period']+('。不表示今天可申购或实际到账。' if row.get('periodKind')=='scenario-dates' else '')+'\n'
        if row.get('followup')=='bjx-annual':body+='\n可以接着问：“沿用这份年度情景，把资金改为……元。”市场和权限声明仍需确认是否适用，新报告不会自动更新资料。\n'
        if row.get('independentEngine'):body+='\n可以接着问：“沿用这份资料继续核对”或“我补充新资料，再看结论是否改变”。旧输入改动需明确提供新输入；不自动安装工具或刷新资料。\n'
        saved=row.get('savedAt')
        displayed=datetime.fromisoformat(saved).astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S 北京时间') if saved else '旧记录未登记，无法按留存日期判断新旧'
        body+='\n记录留存时间：'+displayed+'\n'
        if row['entry']:
            import os
            try:destination=Path(os.path.relpath(row['entry'],output.parent)).as_posix()
            except ValueError:destination=None
            if destination:body+='\n['+('打开旧记录，仅供复查' if row['status']=='记录需要复查' else '打开报告与下一步')+']('+quote(destination,safe='/')+')\n'
            else:body+='\n报告入口位于另一磁盘，请从结果目录打开。\n'
        else:body+='\n尚无有效阅读入口，请查看该目录中的失败记录。\n'
    if not rows:body+='\n没有找到简明入口记录或带报告清单的结果；这不代表目录中没有其他报告。\n'
    body+='\n此页不重新验收报告、不认证数据最新；没有结果记录或报告清单的历史研究暂不包含。\n'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(body,'utf-8');output.with_suffix('.html').write_text(render(body,'我的研究结果'),'utf-8')
    return rows


if __name__=='__main__':
    from cli_text import configure
    configure()
    parser=argparse.ArgumentParser(description='找回指定目录中的简明入口研究结果；不联网')
    parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--query',help='按已登记基金名称、代码、目录名、结论或区间检索')
    parser.add_argument('--limit',type=int,help='仅展示前几条记录；缺留存日期的旧报告无法判断最近')
    args=parser.parse_args();rows=publish(args.folder,args.out,args.query,args.limit)
    print('已整理研究结果：'+str(len(rows)))
