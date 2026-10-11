# SPDX-License-Identifier: MIT
"""Question, evidence gate and specialist result in one reproducible company case."""
from copy import deepcopy
from decimal import Decimal
from evidence_status_review import review as evidence_review
from specialist_loader import call,LAST_PROVENANCE
from review_io import cli


def review(spec):
    if not isinstance(spec,dict) or not isinstance(spec.get('evidence'),dict) or not isinstance(spec.get('financialInput'),dict):raise ValueError('研究输入、资料状态和财报输入须为对象')
    if spec.get('inputSchema')!='company-cash-case/1' or not isinstance(spec.get('question'),str) or not spec['question'].strip():raise ValueError('需company-cash-case/1与明确研究问题')
    status=evidence_review(spec['evidence'])
    financial=deepcopy(spec['financialInput'])
    if spec['question']!=spec['evidence']['question'] or financial['asOf']!=spec['evidence']['asOfDate']:raise ValueError('研究问题或截止日期不一致')
    states={row['id']:row for row in status['records']}
    if set(states)!=set(financial['facts']):raise ValueError('每个财报输入须有唯一同名资料状态，不能绕过缺口')
    withheld=[]
    for metric,fact in financial['facts'].items():
        row=states[metric]
        if row['reviewStatus']!='available':
            financial['facts'][metric]=None;withheld.append(metric);continue
        if fact is None:raise ValueError('可用资料却无数值底稿')
        evidence=fact.get('evidence',{})
        if row['source']!=fact['source'] or row['publishedDate']!=fact['publishedAt'] or row['rawSourceSha256']!=evidence.get('documentSha256'):raise ValueError('状态记录与金额来源、日期或摘要不一致')
        if row['sourceVersion']!=fact.get('statementVersion') or row['dataDate']!=fact.get('period'):raise ValueError('状态记录与金额版本或观察期间不一致')
        if financial.get('exampleType')=='public-document-sample' and row['valueType']!='disclosed':raise ValueError('估算或代理不能作为已披露金额进入公开财报覆盖判断')
    result=call('financial','dividend_observation','calculate',financial)
    amounts=result['amounts'];cash=result['cashSurplus'];coverage=result['coverage']['declaredDividend']
    ratio=coverage.get('cashSurplusCoverage')
    def money(value):return '未知' if value is None else format(Decimal(value),',.2f')+' 元'
    cash_missing=set(withheld)&{'operatingCashFlow','capitalExpenditure','declaredDividend'}
    if cash_missing:conclusion='必要现金或分红资料尚有缺口，当前不能形成完整现金分红覆盖判断。'
    elif ratio is None:conclusion='当前未形成有效现金分红覆盖倍数；需检查现金资料及正的分红分母，已知金额仍单独保留。'
    else:
        answer='可覆盖所列声明分红' if Decimal(ratio)>=1 else '不足以覆盖所列声明分红'
        conclusion=f"在本次口径下，现金结余{answer}。经营现金流减所列资本开支为{money(cash)}，覆盖倍数{Decimal(ratio):.3f}；这不证明未来分红可持续或资金均可用于支付。"
        if withheld:conclusion+='补充利润资料存在缺口，相应利润判断保留未知。'
    if financial.get('exampleType')=='teaching-only':conclusion='教学金额，不是真实公司披露。'+conclusion
    return {'methodVersion':'company-cash-case/1','question':spec['question'],'conclusion':conclusion,'evidenceReview':status,'withheldMetrics':withheld,'specialistResult':result,'engineProvenance':LAST_PROVENANCE['financial'],'humanRows':[['研究问题',spec['question']],['资料缺口',','.join(withheld) or '本次声明资料均在截止内；原页状态另见计算结果'],['经营现金流减所列资本开支',money(cash)],['声明分红',money(amounts.get('declaredDividend'))],['现金覆盖倍数',format(Decimal(ratio),'.3f') if ratio is not None else '未知']],'limitations':['现金流、利润和分红各自期间及版本以底稿为准；实际支付可能属于不同年度','这里只扣所列购建长期资产现金，不涵盖全部收购、营运资金、借款、受限现金或资金需求','数值与来源状态分别核对；找到原页引句不等于整份报表语义认证','若融资、受限资金、资本开支或分红方案变化，需以新目录重新研究；旧结果不覆盖']}

if __name__=='__main__':raise SystemExit(cli({'review':review},'公司现金分红完整研究过程'))
