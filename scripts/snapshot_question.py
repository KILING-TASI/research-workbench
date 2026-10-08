"""Explain money concentration from declared market values; do not infer risk exposure."""
from decimal import Decimal

def answer(snapshot):
    rows=sorted(snapshot['holdings'],key=lambda r:Decimal(r['marketValue']),reverse=True)
    total=Decimal(snapshot['totalMarketValue']);top=rows[:3]
    combined=sum((Decimal(r['marketValue']) for r in top),Decimal(0));share=combined/total*100
    def name(row):return str(row['name']).replace('\n',' ').replace('|','／')
    count=len(top);largest=rows[0]
    conclusion='这份持仓表中，金额最大的是'+name(largest)+'，它占'+f"{Decimal(largest['weightPct']):.2f}%"+'；'+('全部'+str(count)+'项' if len(rows)<=3 else '最大的'+str(count)+'项')+'合计占'+f'{share:.2f}%'+ '。这是金额集中位置，还不能说风险也按这个比例分布。'
    clues=snapshot.get('shareClassClues',[])
    if clues:conclusion+='另有'+str(len(clues))+'组名称提示可能是同一产品的不同份额，不能仅凭代码不同就当作分散。'
    missing=[r['code'] for r in rows if not r.get('valuationDate')]
    data={'questionType':'money-concentration','conclusion':conclusion,'currency':snapshot['currency'],'topCodes':[r['code'] for r in top],'topValue':str(combined),'topWeightPct':str(share),'missingValuationDateCodes':missing,'sourceVerification':snapshot['sourceVerification'],'scope':'declared-market-values; not underlying exposure or risk contribution'}
    body='# 我的钱主要集中在哪里\n\n> '+conclusion+'\n\n'
    body+='所给市值合计'+f'{total:.2f}'+' '+snapshot['currency']+'。本次沿用持仓表，未刷新价格或认证账户；所给项目不保证覆盖全部账户资产。\n\n'
    body+='|资金最多的项目|市值|占组合金额|\n|---|---:|---:|\n'
    for r in top:body+='|'+name(r)+'|'+f"{Decimal(r['marketValue']):.2f}"+'|'+f"{Decimal(r['weightPct']):.2f}%"+'|\n'
    if clues:
        body+='\n## 哪些项目可能只是不同份额？\n\n'
        for clue in clues:body+='- '+str(clue['nameStem']).replace('\n',' ')+'：相关项目合计占'+f"{Decimal(clue['weightPct']):.2f}%"+'。这是名称线索，需核对官方份额关系；没有自动合并，也没有认定底层完全相同。\n'
    body+='\n## 现在还不能下什么结论？\n\n市值集中不等于风险集中：一个基金可以分散投资，多只基金也可能押注同一行业。还没有底层持仓和共同历史，不能回答行业重复、相关性或风险贡献。\n\n'
    if missing:body+='有'+str(len(missing))+'项未提供估值日期；这些金额不能冒充当前市值。研究截止日只是本次整理口径。\n\n'
    body+='如果只想查重复押注，下一步最有用的是同一期底层持仓；如果想判断集中度是否适合自己，先说明资金用途和自己的上限。这里没有替你设置“健康分”或默认仓位标准。完整项目与声明口径见持仓结构报告。\n'
    return data,body
