"""Historical scheduled contributions, event accounting and comparable plans."""
import argparse,bisect,calendar,json,math
from datetime import date,timedelta
from pathlib import Path
from fund_series_tools import day,num,source,NOTICE

def schedule(start,end,frequency,engine_project_dir=None):
    from specialist_loader import call
    return call('portfolio','scheduled_cash','schedule',start,end,frequency,project_dir=engine_project_dir)

def xirr(flows,engine_project_dir=None):
    from specialist_loader import call
    return call('portfolio','scheduled_cash','xirr',flows,project_dir=engine_project_dir)

def calculate(s,engine_project_dir=None):
    from specialist_loader import call
    return call('portfolio','scheduled_cash','calculate',s,project_dir=engine_project_dir)

def markdown(r):
    status='本次仅按输入者的完整核验声明计算，程序未独立核验原文或事件完整性。' if r['eventCoverage']=='verified-complete' else '本次依赖分红、拆分事件完整性假设；结果不属于已核验的实际定投收益。'
    lines=['# 历史定投方案对比', '**结果口径：'+status+'**','',f"基金{r['code']}；{r['start']}至{r['requestedEnd']}，估值日{r['valuationDate']}。",'','|方案|总投入|期末资产|累计收益率|资金加权年化|期数|','|---|---:|---:|---:|---:|---:|']
    for p in r['plans']:
        annual='无法计算' if p['xirrPct'] is None else f"{p['xirrPct']:.2f}%"
        lines.append(f"|{p['name'].replace('|','/')}|{p['totalContribution']:.2f}|{p['endingTotalAssets']:.2f}|{p['cumulativeReturnPct']:.2f}%|{annual}|{p['periods']}|")
    if r['distributionPolicyStatus']=='not-fully-declared':lines+=['','分红方式未完整登记：再投方案仅是理论假设，不能据此确认产品允许红利再投资。']
    missing_fees=[p['name'] for p in r['plans'] if 'subscriptionFeePct' not in p['parameters']]
    if missing_fees:lines+=['','申购费率未声明的方案：'+'、'.join(missing_fees)+'。本次按零申购费假设计算，不代表渠道实际免费或费用后到手收益。']
    lines+=['',f"期末估值距请求截止日{r['valuationAgeDays']}个日历日；此间价格变化未计入。"]
    for p in r['plans']:
        if p['pendingReinvestment']:
            lines.append(f"{p['name']}期末仍有{sum(x['cashEntitlement'] for x in p['pendingReinvestment']):.2f}元分红权益等待再投，已计入期末资产，但不是可用现金或已确认份额。")
        if p['scheduleDelays']:
            lines.append(f"{p['name']}有{len(p['scheduleDelays'])}次日期顺延，最长{max(x['calendarDays'] for x in p['scheduleDelays'])}个日历日；不能据此确认只是正常休市，需核查缺失净值。")
    lines+=['','累计收益率是盈亏除以总投入；资金加权年化考虑每笔投入日期。两者不能混用。','事件依据：'+r['eventEvidence'],'']+['- '+x for x in r['limitations']]+['',r['riskNotice']]
    return '\n'.join(lines)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('input',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    r=calculate(json.loads(a.input.read_text(encoding='utf-8-sig')))
    if a.out.exists() or a.out.with_suffix('.md').exists():raise ValueError('输出已存在')
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8');a.out.with_suffix('.md').write_text(markdown(r),encoding='utf8')
