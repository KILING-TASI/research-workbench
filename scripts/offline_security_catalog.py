"""Import caller-declared identity catalog without certifying issuer or freshness."""
import json, hashlib, datetime, re, uuid
from pathlib import Path
from collection_validation import unique_pairs, reject_constant

def prepare(input_path, workspace, as_of):
    path=Path(input_path)
    if not path.is_file() or path.stat().st_size>16*1024*1024:raise ValueError('身份目录须为不超过16MiB的本地JSON')
    raw=path.read_bytes();doc=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
    source=doc.get('sourceUrl');date=doc.get('asOf');rows=doc.get('rows')
    if not isinstance(source,str) or not source.startswith('https://'):raise ValueError('目录须声明HTTPS来源sourceUrl；声明不认证原发布者')
    datetime.date.fromisoformat(date);datetime.date.fromisoformat(as_of)
    if date>as_of:raise ValueError('目录日期晚于研究截止日，不能用于该研究')
    if not isinstance(rows,list) or not rows or len(rows)>20000:raise ValueError('目录须有1至20000条rows')
    clean=[];seen=set()
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('code'),str) or not re.fullmatch(r'[0-9]{6}',row['code']) or not isinstance(row.get('name'),str) or not row['name'].strip():raise ValueError('目录条目须有六位code、非空name')
        if row['code'] in seen:raise ValueError('目录代码重复，须先核对身份冲突')
        if row.get('exchange') not in ('SSE','SZSE','BSE'):raise ValueError('目录exchange须明确SSE/SZSE/BSE')
        seen.add(row['code']);clean.append(dict(code=row['code'],name=row['name'].strip(),exchange=row['exchange'],source=source,asOf=date))
    root=Path(workspace)/'research-data'/'identity-catalogs'/uuid.uuid4().hex
    target=root/'outputs'/'stock-market'/'assets';target.mkdir(parents=True)
    (target/'data.json').write_text(json.dumps(dict(rows=clean),ensure_ascii=False),encoding='utf-8')
    (root/'receipt.json').write_text(json.dumps(dict(sourcePath=str(path.resolve()),sha256=hashlib.sha256(raw).hexdigest(),sourceUrl=source,asOf=date,sourceVerified=False)),encoding='utf-8')
    return root
