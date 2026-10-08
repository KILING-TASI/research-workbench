"""Check declared research coverage; never certify semantic or causal correctness."""
ROLES = ('overall','business','earnings','cash','risk','falsification')

def coverage(entries):
    if not isinstance(entries,list) or any(not isinstance(entry,dict) for entry in entries):raise ValueError('评价记录须为对象列表')
    text=lambda value:isinstance(value,str) and bool(value.strip())
    roles={entry.get('role') for entry in entries if entry.get('basis')=='research-explanation' and isinstance(entry.get('role'),str) and entry['role'] in ROLES}
    missing=[role for role in ROLES if role not in roles]
    questions=[]
    for entry in entries:
        if entry.get('basis')!='research-explanation':continue
        if not text(entry.get('conclusion')):questions.append('研究解释缺少一句话结论')
        alternatives=entry.get('alternatives')
        if entry.get('role') in ('earnings','business') and (not isinstance(alternatives,list) or not alternatives or any(not text(value) for value in alternatives)):
            questions.append('经营或利润解释尚未列出竞争解释')
        if entry.get('role')=='falsification' and not text(entry.get('invalidationSignal')):
            questions.append('尚未写明改变判断的条件')
    return dict(status='covered-awaiting-semantic-review' if entries and not missing and not questions else 'partial' if entries else 'data-only',
                coveredRoles=[role for role in ROLES if role in roles],missingRoles=missing,
                issues=list(dict.fromkeys(questions)),scope='仅核对评价结构与原文引句是否齐备，不证明解释正确或投资判断完整')

def validate_details(entry):
    if not isinstance(entry,dict):raise ValueError('评价条目须为对象')
    result={}
    for key in ('coreTension','positioning','judgmentBoundary'):
        if key in entry:
            value=entry[key]
            if not isinstance(value,str) or not value.strip() or len(value)>360 or any(x in value for x in '\r\n<>'):
                raise ValueError(key+'须为360字以内单行文字')
            result[key]=value.strip()
    if 'role' in entry:
        if entry['role'] not in (*ROLES,'valuation'):raise ValueError('评价role无效')
        result['role']=entry['role']
    if 'alternatives' in entry:
        value=entry['alternatives']
        if not isinstance(value,list) or any(not isinstance(x,str) or not x.strip() for x in value):raise ValueError('竞争解释须为非空文字列表')
        result['alternatives']=[x.strip() for x in value]
    if 'invalidationSignal' in entry:
        value=entry['invalidationSignal']
        if not isinstance(value,str) or not value.strip():raise ValueError('反证条件须为非空文字')
        result['invalidationSignal']=value.strip()
    return result
