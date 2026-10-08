"""Evidence-declared equivalence of security identifiers, not issuer or fund edges."""
import copy
from buy_side_thesis import timing,locate
from collection_validation import day

def normalize(spec):
    cutoff=day(spec['asOf']);records=spec.get('records');links=spec.get('links',[])
    if not isinstance(records,list) or not isinstance(links,list) or len(records)>10000 or len(links)>20000:raise ValueError('证券记录或关系数量无效')
    identities={}
    for record in records:
        if not isinstance(record,dict) or any(not isinstance(record.get(key),str) or not record[key].strip() for key in ('id','market','currency','assetClass','shareClass')):raise ValueError('证券记录须明确id、market、currency、assetClass、shareClass')
        if record['id'] in identities:raise ValueError('证券记录id重复')
        identities[record['id']]=record
    parents={key:key for key in identities}
    def find(key):
        while key!=parents[key]:parents[key]=parents[parents[key]];key=parents[key]
        return key
    applied=[];excluded=[]
    for link in links:
        if not isinstance(link,dict) or link.get('relation')!='same-security':raise ValueError('只能合并same-security；发行人及基金投资关系另行处理')
        left=link.get('left');right=link.get('right')
        if left not in identities or right not in identities or left==right:raise ValueError('别名关系引用未知或相同id')
        for key in ('source','publishedAt','acquiredAt'):
            if not isinstance(link.get(key),str) or not link[key].strip():raise ValueError('别名关系缺少'+key)
        checked=timing(link,cutoff)
        if checked['reasons'] or checked['effectiveStatus']=='not-yet-effective':
            excluded.append({'link':copy.deepcopy(link),'reason':'关系时点不适用','timing':checked});continue
        if any(identities[left][key]!=identities[right][key] for key in ('market','currency','assetClass','shareClass')):raise ValueError('同证券关系的市场、币种、类型或份额类别冲突')
        if any('unresolved' in identities[left][key].lower() or 'unknown' in identities[left][key].lower() for key in ('market','currency','assetClass','shareClass')):
            excluded.append({'link':copy.deepcopy(link),'reason':'关键身份属性未明确，不据别名关系消除未知'});continue
        location=locate({'kind':'original','locator':link.get('locator')})
        if location['status']=='quote-not-found':
            excluded.append({'link':copy.deepcopy(link),'reason':'关系引句未匹配','location':location});continue
        a,b=find(left),find(right)
        if a!=b:parents[max(a,b)]=min(a,b)
        applied.append({'link':copy.deepcopy(link),'location':location,'timing':checked})
    groups={}
    for key in identities:groups.setdefault(find(key),[]).append(key)
    return {'type':'security-alias-normalization','asOf':spec['asOf'],'canonicalIds':{key:find(key) for key in identities},
            'groups':[{'canonicalId':key,'aliases':sorted(values)} for key,values in sorted(groups.items())],
            'appliedLinks':applied,'excludedLinks':excluded,
            'limitations':['等价依据来自输入和其原文定位层次，不自动认证证券主数据','不按相似名称、代码前缀或不同市场相同ticker自动合并','同证券合并不代表公司控制关系，基金投资边不能用union-find合并','标准化标识不删除持仓项目，不自动抵销金额或更新价格']}
