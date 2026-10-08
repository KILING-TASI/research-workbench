"""Explain a follow-up comparison without attributing window changes to performance improvement."""
import hashlib,json
from pathlib import Path
from collection_validation import unique_pairs,reject_constant,finite_json_float
from fund_comparison_brief import report


def read(path):
    p=Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size>16*1024*1024:raise ValueError('旧比较文件路径或大小异常')
    return json.loads(p.read_text('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float)


def build(previous,new_document):
    root=Path(previous).resolve();directory=root/'comparison'
    if not directory.resolve().is_relative_to(root):raise ValueError('旧比较目录越界')
    source=directory/'input.json';manifest=read(directory/'report-manifest.json')
    if source.is_symlink() or source.resolve().parent!=directory.resolve():raise ValueError('旧比较输入越界')
    if manifest.get('inputSha256')!=hashlib.sha256(source.read_bytes()).hexdigest():raise ValueError('旧比较输入已改变，不能静默对照')
    old=read(source);before=report(old)[0];after=report(new_document)[0]
    old_rows={r['code']:r for r in old['rows']};new_rows={r['code']:r for r in new_document['rows']}
    findings_before=before['findings'];findings_after=after['findings']
    old_judgement=next((f['conclusion'] for f in findings_before if f.get('conclusion')),None)
    new_judgement=next((f['conclusion'] for f in findings_after if f.get('conclusion')),None)
    body='# 这次追问，结论怎样变了\n\n'
    if new_judgement:body+='> '+new_judgement+'\n\n'
    body+=f"原比较实际覆盖{before['start']}至{before['end']}；本次覆盖{after['start']}至{after['end']}。两份结果都按当前计算方法重算，不直接拿旧版数值混比。\n\n"
    if old_judgement:body+='原区间判断：'+old_judgement+'\n\n'
    reason=None
    if set(old_rows)!=set(new_rows):reason='比较对象变了，不能把结论变化单独归因于日期或产品表现。'
    elif any(old_rows[c].get(k)!=new_rows[c].get(k) for c in old_rows for k in ('basis','currency','frequency','comparisonGroup')):
        reason='币种、收益口径、频率或比较池声明变了，前后数值不作直接差分。'
    else:
        for c in old_rows:
            def values(row):return {h['date']:(h.get('nav'),h.get('close'),h.get('distribution')) for h in row['history']}
            left,right=values(old_rows[c]),values(new_rows[c])
            common_start=max(before['start'],after['start']);common_end=min(before['end'],after['end'])
            if {d for d in left if common_start<=d<=common_end}!={d for d in right if common_start<=d<=common_end}:
                reason='重叠区间的观察日期不一致，可能有缺期或补采，不能只按起点变化拆解收益。';break
            if any(left[d]!=right[d] for d in left.keys()&right.keys()):reason='重叠日期的原始数值或分红记录变了，结论变化不只有区间因素。';break
    if reason:
        body+=reason+'本次报告独立完成，未将前后差别写成改善。\n'
    else:
        body+='对象和已记录口径一致，重叠日期的输入也一致。换观察区间会改变收益起点和回撤路径，不能把数字变大或变小理解成基金本身变好了。\n\n'
        earlier={r['code']:r for r in before['rows']}
        interval_explanations=[]
        if before['end']==after['end'] and before['start']<after['start']:
            for r in after['rows']:
                old_r=earlier[r['code']]
                old_growth=1+old_r['totalReturnPct']/100
                new_growth=1+r['totalReturnPct']/100
                if old_growth<=0 or new_growth<=0:continue
                excluded=(old_growth/new_growth-1)*100
                name=str(new_rows[r['code']].get('name') or r['code']).replace('|','／').replace('\n',' ')
                change='由盈利变成亏损' if old_r['totalReturnPct']>0 and r['totalReturnPct']<0 else '由亏损变成盈利' if old_r['totalReturnPct']<0 and r['totalReturnPct']>0 else '累计收益随观察起点改变'
                body+=name+'：'+change+'。两个起点之间（'+before['start']+'至'+after['start']+'）的已记录序列累计收益约为'+f'{excluded:.2f}%'+ '，后面一段为'+f"{r['totalReturnPct']:.2f}%"+'。较长区间把两段合在一起，不能把它当作最近一年的表现。\n\n'
                interval_explanations.append({'code':r['code'],'start':before['start'],'end':after['start'],'returnPct':excluded})
        else:
            interval_explanations=[]
        if interval_explanations:
            body+='两段收益按复利连接：较长区间增长倍数＝前段增长倍数×后段增长倍数；不是把两个收益率直接相减。这里沿用已记录分红口径，仍不是完整产品评价。\n\n'
        body+='|产品|原区间收益|本区间收益|原区间最大回撤|本区间最大回撤|\n|---|---:|---:|---:|---:|\n'
        for r in after['rows']:
            old_r=earlier[r['code']];name=str(new_rows[r['code']].get('name') or r['code']).replace('|','／').replace('\n',' ')
            body+=f"|{name}|{old_r['totalReturnPct']:.2f}%|{r['totalReturnPct']:.2f}%|{old_r['drawdownPct']:.2f}%|{r['drawdownPct']:.2f}%|\n"
        recoveries={r['code']:r for r in before['recoveryObservations']}
        for observation in after['recoveryObservations']:
            earlier_observation=recoveries[observation['code']]
            if observation.get('peakDate') and observation.get('peakDate')==earlier_observation.get('peakDate') and observation.get('troughDate')==earlier_observation.get('troughDate'):
                name=str(new_rows[observation['code']].get('name') or observation['code'])
                body+='\n'+name+'的最深回撤仍发生在'+observation['peakDate']+'至'+observation['troughDate']+'，这段下跌仍包含在新窗口内，所以缩短区间没有去掉这次回撤。\n'
    body+='\n资料来源、完整分红、合同基准、持仓和费用仍按各报告缺口核查。区间比较不回答应该买哪只，也不证明未来表现。旧输入与报告没有覆盖；这里只保存输入对照，不认证全部原文资料。\n'
    return {'status':'not-directly-comparable' if reason else 'same-context-window-review','before':before,'after':after,'reason':reason,'intervalExplanations':[] if reason else interval_explanations},body
