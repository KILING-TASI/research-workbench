# SPDX-License-Identifier: MIT
"""Explicit forecast/actual, public meeting Q&A, hypothesis changes and portable engine index."""
from review_io import evidence,number,instant,day,digest,cli
UNITS={'元':1,'万元':10000,'亿元':100000000,'元/股':1}
BASIS=('entity','metric','periodStart','periodEnd','currency','scope','basis','profitAttribution','shareBasis')

def value(row):
    if row.get('unit') not in UNITS or row.get('currency')!='CNY':raise ValueError('金额单位/CNY口径不支持')
    if (row.get('metric')=='eps')!=(row['unit']=='元/股'):raise ValueError('每股与总金额不可混用')
    return number(row['value'])*UNITS[row['unit']]

def forecast_actual(spec):
    cutoff=spec['asOf'];instant(cutoff);forecast=spec['forecast'];first=spec['firstActual'];restated=spec.get('restatedActual')
    for row in [forecast,first]+([restated] if restated else []):
        if not evidence(row,cutoff):raise ValueError('本次资料晚于截止，不能配对')
        value(row)
        if any(row.get(k) is None for k in BASIS):raise ValueError('缺口径维度，保留不可比，不生成准确率')
        if day(row['periodStart'])>day(row['periodEnd']):raise ValueError('财务期间倒置')
    if any(first[k]!=forecast[k] for k in BASIS):raise ValueError('预测和实际口径不同')
    if instant(forecast['acquiredAt'])>=instant(first['acquiredAt']) or forecast['publishedDate']>=first['publishedDate']:raise ValueError('预测未在实际披露前取得，不能评价事前预测')
    if first.get('actualVersionRole')!='first-disclosure' or first['publishedDate']<=first['periodEnd']:raise ValueError('需明确期末之后的首次披露实际值，不将修订值改写首次')
    fv,av=value(forecast),value(first);rows=[['首次实际值（同口径元或元/股）',str(av)],['预测值',str(fv)],['预测减首次实际',str(fv-av)]]
    revision=None
    if restated:
        if any(restated[k]!=first[k] for k in BASIS) or restated.get('supersedesId')!=first.get('id') or not restated.get('revisionEvidence') or restated['publishedDate']<=first['publishedDate']:raise ValueError('重述关系、顺序或口径不明确')
        revision={'id':restated['id'],'differenceFromFirst':str(value(restated)-av),'forecastMinusRestated':str(fv-value(restated)),'evidence':restated['revisionEvidence']}
        rows.append(['重述减首次实际',revision['differenceFromFirst']])
    return {'conclusion':'首次实际和重述分别留存；误差只在声明口径一致且预测取得早于实际披露时计算。','forecastMinusFirstActual':str(fv-av),'absoluteErrorRatio':str(abs(fv-av)/abs(av)) if av!=0 else None,'restatement':revision,'sourceRecords':[forecast,first]+([restated] if restated else []),'humanRows':rows,'limitations':['仅一组声明记录，不代表机构准确率排名','取得及发布时间由底稿声明，未自动认证原文','零实际值不产生百分比误差，负实际值以绝对值作分母']}

def public_qa(spec):
    instant(spec['asOf']);ids=set();accepted=[];excluded=[]
    if not isinstance(spec['records'],list):raise ValueError('问答须列表')
    for row in spec['records']:
        if not isinstance(row,dict) or not row.get('id') or row['id'] in ids:raise ValueError('问答身份重复或缺失')
        ids.add(row['id'])
        if row.get('access')!='public' or row.get('meetingType') not in {'earnings-briefing','investor-relations-public'}:raise ValueError('仅公开业绩说明会/投资者关系公开记录；不接私人客户会议')
        if not isinstance(row.get('question'),str) or not row['question'].strip() or not isinstance(row.get('answer'),str) or not row['answer'].strip():raise ValueError('问题及回答不可缺失')
        if row.get('statementType') not in {'historical-claim','forward-looking','explanation'}:raise ValueError('回答须区分历史陈述、未来表述及解释')
        if evidence(row,spec['asOf']):accepted.append(row)
        else:excluded.append({'id':row['id'],'reason':'截止后取得或公布'})
    return {'conclusion':'按问题留存公开回答、定位与版本；管理层回答是来源陈述，未来表述未升级为已发生事实。','records':accepted,'excluded':excluded,'humanRows':[[r['question'],r['answer']+'（'+r['statementType']+'）'] for r in accepted],'limitations':['不自动理解原文或核实说话人','不收私人会议/客户档案；长原文转录权利另核','版本更正用新ID，历史报告不覆盖']}

def hypothesis_diff(spec):
    a,b=spec['before'],spec['after']
    if a['entityId']!=b['entityId'] or instant(a['asOf'])>=instant(b['asOf']):raise ValueError('假设主体相同且版本按先后排序')
    def index(doc):
        rows=doc['hypotheses'];out={}
        for r in rows:
            if not r.get('id') or r['id'] in out or not r.get('claim') or not r.get('invalidation'):raise ValueError('假设需唯一ID、判断与反证条件')
            out[r['id']]=r
        return out
    left,right=index(a),index(b);changes=[]
    for key in sorted(set(left)|set(right)):
        status='added' if key not in left else 'removed' if key not in right else 'changed' if left[key]!=right[key] else 'unchanged'
        changes.append({'id':key,'status':status,'before':left.get(key),'after':right.get(key)})
    return {'conclusion':'假设、依据或反证条件变化分别显示，旧版本继续保留；变化不自动证明判断失效。','beforeSha256':digest(a),'afterSha256':digest(b),'changes':changes,'humanRows':[[r['id'],r['status']] for r in changes],'limitations':['显式版本差异，不自动生成研究观点或事件归因']}

def archive_index(spec):
    entries=spec['entries'];ids=set();groups={};index=[]
    for row in entries:
        if not row.get('id') or row['id'] in ids:raise ValueError('引擎结果ID需唯一')
        ids.add(row['id'])
        for field in ('engine','engineVersion','inputSchema','methodVersion','entity','asOf','status','inputSha256','resultSha256'):
            if not isinstance(row.get(field),str) or not row[field]:raise ValueError('结果绑定缺字段：'+field)
        if row['status'] not in {'success','partial','failed','blocked'}:raise ValueError('引擎状态不支持')
        for key in ('inputSha256','resultSha256'):
            if len(row[key])!=64 or any(c not in '0123456789abcdef' for c in row[key]):raise ValueError('绑定摘要无效')
        for field,sha in [('input',row['inputSha256']),('result',row['resultSha256'])]:
            if digest(row[field])!=sha:raise ValueError('内嵌可迁移底稿摘要不符')
        groups.setdefault((row['entity'],row['asOf'],row['engine']),[]).append(row)
        index.append(row)
    conflicts=[{'entity':k[0],'asOf':k[1],'engine':k[2],'ids':[r['id'] for r in rs]} for k,rs in groups.items() if len({r['resultSha256'] for r in rs})>1]
    return {'conclusion':'各引擎按版本、输入和结果摘要登记；同主体同截止同引擎结果不同则并列显示，不替用户择优。','entries':index,'conflicts':conflicts,'humanRows':[[r['engine']+' '+r['engineVersion'],r['status']] for r in index],'limitations':['内嵌JSON可迁移，摘要不认证来源或引擎兼容性','失败/阻断结果同样保留，不能汇总成已完成','不同方法的差异不是事实矛盾，须逐项核对口径']}

if __name__=='__main__':raise SystemExit(cli({'forecast-actual':forecast_actual,'public-qa':public_qa,'hypothesis-diff':hypothesis_diff,'archive-index':archive_index},'研究资料复查与版本比较'))
