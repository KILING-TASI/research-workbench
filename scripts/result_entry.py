"""Human-facing result entry; does not upgrade evidence or research status."""
from pathlib import Path
import json
from urllib.parse import quote
from research_brief_html import render


def write_entry(directory, summary):
    directory=Path(directory)
    states={'passed':'本次任务结果已生成','partial':'已完成部分研究，请同时阅读资料限制',
            'blocked':'本次任务尚未完成','needs-clarification':'还需确认标的或补充资料',
            'data-unavailable':'本次未取得可用资料','unsupported':'当前入口不适用于这个问题'}
    lines=['# 本次研究结果','', '> '+states.get(summary['status'],'请核对本次完成范围'), '']
    if summary.get('headline'):
        lines+=['## 本次主要结论','', '> '+str(summary['headline']),'']
    lines+=[summary['message'],'']
    if summary.get('followupInterpretation'):
        lines+=['本次追问的处理：'+str(summary['followupInterpretation']),'']
    previous=summary.get('previousStudy')
    if isinstance(previous,dict):
        link=previous.get('entry')
        if isinstance(link,str) and not link.startswith('/') and ':' not in link and '\\' not in link and link.endswith('/打开这里.html'):
            lines+=['你选定的上次研究：[返回上次报告]('+quote(link,safe='/')+')。本次是否完成续算以结果状态为准，链接不代表数据已更新。','']
        elif link is None:
            lines+=['已选定上次研究作为资料来源，但入口位于另一磁盘，需从原结果目录打开。','']
    request_path=directory/'research-request.json'
    try:
        if request_path.is_file() and not request_path.is_symlink() and request_path.stat().st_size<=1024*1024:
            request=json.loads(request_path.read_text('utf-8'))
            start=request.get('start');end=request.get('asOf')
            from datetime import date
            dates=request.get('scenarioDates')
            if request.get('command')=='bjx' and isinstance(dates,dict) and all(isinstance(dates.get(k),str) and date.fromisoformat(dates[k]).isoformat()==dates[k] for k in ('applyDate','refundDate','saleSettlementDate')):
                lines+=['本次沿用的情景日期：申购'+dates['applyDate']+'；退款可用'+dates['refundDate']+'；卖出结算'+dates['saleSettlementDate']+'。这些是输入声明，不表示今天可申购，也不认证实际到账。','']
            if isinstance(start,str) and isinstance(end,str) and date.fromisoformat(start).isoformat()==start and date.fromisoformat(end).isoformat()==end and start<=end:
                lines+=['研究请求记录的区间：'+start+'至'+end+'。这是所选研究区间，不代表全部资料已经覆盖；报告生成日期也不等于数据更新日期。','']
    except (OSError,ValueError,AttributeError):pass
    lines+=['## 先读这里','']
    files=sorted(directory.rglob('*.html'))
    files=[p for p in files if 'raw' not in p.relative_to(directory).parts and p.name!='打开这里.html' and not p.is_symlink() and p.resolve().is_relative_to(directory.resolve())]
    files.sort(key=lambda p:('identity' in p.relative_to(directory).parts or 'identity-failed' in p.relative_to(directory).parts,p.relative_to(directory).as_posix()))
    primary=None;manifest=directory/'report-manifest.json'
    try:
        if manifest.is_file() and not manifest.is_symlink() and manifest.stat().st_size<=1024*1024:
            data=json.loads(manifest.read_text('utf-8'));name=data.get('primaryReport')
            if isinstance(name,str) and '/' not in name and '\\' not in name and ':' not in name and isinstance(data.get('files'),dict) and name in data['files'] and directory/name in files:primary=directory/name
    except (OSError,ValueError,AttributeError):pass
    if primary:
        lines+=['- [打开主报告：'+primary.stem.replace('[','').replace(']','')+']('+quote(primary.name,safe='')+')','']
        files.remove(primary)
        if files:lines+=['其他阅读材料：','']
    if files or primary:
        for path in files:
            link=quote(path.relative_to(directory).as_posix(),safe='/')
            lines.append('- ['+path.stem.replace('[','').replace(']','')+']('+link+')')
    elif (directory/'环境检查.md').exists():
        lines.append('- [环境检查](%E7%8E%AF%E5%A2%83%E6%A3%80%E6%9F%A5.md)')
    elif (directory/'下一步.md').exists():
        lines.append('- [失败原因与处理办法](%E4%B8%8B%E4%B8%80%E6%AD%A5.md)')
    else:
        lines.append('暂未生成可阅读报告；请先按下面的指引处理。')
    lines+=['','## 下一步','']+['- '+step for step in summary['nextSteps']]
    if summary.get('mode')=='teaching-demo' or summary.get('exampleType')=='teaching-only':
        lines+=['','**教学演示：不是你的真实持仓或真实基金评价。**']
    lines+=['','报告生成不等于资料完整或来源已核验；具体结论、范围及缺口以所列报告为准。']
    body='\n'.join(lines)
    (directory/'打开这里.md').write_text(body,'utf-8')
    (directory/'打开这里.html').write_text(render(body,'本次研究结果'),'utf-8')
