"""Compare archived site date labels to a declared same-site local cutoff."""
import argparse,json,hashlib,re
from pathlib import Path
from html.parser import HTMLParser
from datetime import datetime
from report_content_review import html_prose
from collection_validation import unique_pairs,reject_constant,day
FORMAT='%Y/%m/%d %H:%M'
class PubDates(HTMLParser):
    def __init__(self):super().__init__();self.values=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='meta' and any(key=='name' and value=='PubDate' for key,value in attrs):
            if len([key for key,value in attrs if key=='name'])!=1 or len([key for key,value in attrs if key=='content'])!=1:raise ValueError('PubDate属性重复或缺失')
            self.values.append(values.get('content'))

def local_time(value):
    if not isinstance(value,str):raise ValueError('站点时间须为文字')
    parsed=datetime.strptime(value,FORMAT)
    if parsed.strftime(FORMAT)!=value:raise ValueError('站点时间须为YYYY/MM/DD HH:MM')
    return parsed

def label_status(stamp,cutoff):
    published=local_time(stamp);point=local_time(cutoff)
    return 'marked-after-cutoff-exclude' if published>point else 'marked-not-after-cutoff-historical-availability-unproven'

def inspect(spec,base):
    if not isinstance(spec,dict):raise ValueError('披露时点请求须为对象')
    if spec.get('clockBasis')=='same-site-marked-local-date':return inspect_date(spec,base)
    if spec.get('clockBasis')!='same-site-marked-local-time':raise ValueError('须显式使用同站点标注当地时间，不自动换算时区')
    local_time(spec.get('siteLocalCutoff'))
    sources=spec.get('sources')
    if not isinstance(sources,list) or any(not isinstance(source,dict) for source in sources):raise ValueError('来源须为对象列表')
    for source in sources:
        if any(not isinstance(source.get(key),str) or not source[key].strip() for key in ['id','siteId','path','sha256']):raise ValueError('来源身份、路径与摘要须为非空文字')
    base=Path(base)
    if not sources or len({s['id'] for s in sources})!=len(sources):raise ValueError('来源为空或编号重复')
    if len({s['siteId'] for s in sources})!=1:raise ValueError('未确认时区的不同站点不能直接排序')
    rows=[]
    for source in sources:
        p=Path(source['path']);p=p if p.is_absolute() else base/p
        raw=p.read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if digest!=source['sha256']:raise ValueError('归档网页哈希变化')
        html=raw.decode('utf-8-sig');parser=PubDates();parser.feed(html)
        if len(parser.values)!=1:raise ValueError('PubDate缺失或歧义')
        stamp=parser.values[0]
        if stamp not in html_prose(html):raise ValueError('元数据时间未与正文提取文字中的时间对应（非视觉核验）')
        rows.append(dict(id=source['id'],path=str(p.resolve()),sha256=digest,dataPeriod=source.get('dataPeriod'),siteMarkedPublishedAt=stamp,siteIdentityStatus='input-declared-not-host-verified',status=label_status(stamp,spec['siteLocalCutoff']),scope='仅归档标注；非首次公开或实际可获得时间'))
    return dict(siteLocalCutoff=spec['siteLocalCutoff'],clockBasis=spec['clockBasis'],rows=rows,scope='晚于研究时点的站点标注来源排除；早于标注不证明历史可用，不做事件收益或因果归因')

def inspect_date(spec,base):
    day(spec.get('siteLocalCutoffDate'));cutoff=spec['siteLocalCutoffDate'];fmt=spec.get('metadataFormat')
    if fmt not in ('%Y-%m-%d %H:%M:%S','%Y/%m/%d %H:%M','%Y-%m-%d'):raise ValueError('日期级核对须明确支持的元数据格式')
    sources=spec.get('sources')
    if not isinstance(sources,list) or not sources or any(not isinstance(s,dict) for s in sources):raise ValueError('来源须为非空对象列表')
    for source in sources:
        if any(not isinstance(source.get(k),str) or not source[k].strip() for k in ['id','siteId','path','sha256']):raise ValueError('来源身份、路径及摘要须非空')
    if len({s['id'] for s in sources})!=len(sources) or len({s['siteId'] for s in sources})!=1:raise ValueError('来源须同站点且ID唯一')
    rows=[]
    for source in sources:
        p=Path(source['path']);p=p if p.is_absolute() else Path(base)/p;raw=p.read_bytes();sha=hashlib.sha256(raw).hexdigest()
        if sha!=source['sha256']:raise ValueError('归档网页哈希变化')
        text=raw.decode('utf-8-sig');parser=PubDates();parser.feed(text)
        if len(parser.values)!=1 or not isinstance(parser.values[0],str):raise ValueError('PubDate缺失或歧义')
        stamp=parser.values[0];parsed=datetime.strptime(stamp,fmt)
        if parsed.strftime(fmt)!=stamp:raise ValueError('元数据格式不符合声明')
        marked=parsed.date().isoformat();body=html_prose(text)
        if not re.search(r'(?:发布时间|发布日期)\s*[：:]\s*'+re.escape(marked)+r'(?![0-9])',body):raise ValueError('发布日期未与正文发布日期标签对应')
        state='marked-date-after-cutoff-exclude' if marked>cutoff else 'same-date-clock-unknown' if marked==cutoff else 'marked-date-before-cutoff-availability-unproven'
        rows.append(dict(id=source['id'],path=str(p.resolve()),sha256=sha,siteMarkedDate=marked,metadataOriginal=stamp,precision='date-only',status=state,exactClockVerified=False,siteIdentityStatus='input-declared-not-host-verified'))
    return dict(clockBasis='same-site-marked-local-date',siteLocalCutoffDate=cutoff,rows=rows,scope='仅同站日期标签对应；保留元数据原时刻，不认证正文精确时点、首次公开或历史可得；同日不排序')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('input');parser.add_argument('--out',required=True);args=parser.parse_args();p=Path(args.input).resolve();spec=json.loads(p.read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant);result=inspect(spec,p.parent)
    payload=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
    with Path(args.out).open('x',encoding='utf-8') as f:f.write(payload)
if __name__=='__main__':main()
