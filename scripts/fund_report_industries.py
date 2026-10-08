"""Extract report-native equity industry aggregates; never assign stock industries.

Caller must verify report identity, dates and NAV/equity totals from the original.
Only interim/annual GICS 7.3/8.3 and domestic A-S 7.2/8.2 layouts are supported. Requires pdfplumber.
"""
import argparse, datetime, hashlib, json, re
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit
import pdfplumber
from collection_validation import unique_pairs, reject_constant, finite_json_float

def clean(value):
    return re.sub(r'\s+', '', value or '')

def amount(value):
    result = Decimal(clean(value).replace(',', ''))
    if not result.is_finite():raise ValueError('行业金额与比例须为有限数值')
    return result

def international_taxonomy(text):
    if 'GICS' in text:return 'GICS'
    if '国际通用行业分类标准' in text:return 'report-native-international'
    return None

def mixed_result(document,pdf,metadata,nav,equity):
 rows=[];totals={};active=None;finished=False;scope_text=[];empty_hk=None
 for number,page in enumerate(document.pages,1):
  text=page.extract_text() or ''
  cn=page.search(r'(?m)^[78]\.2\.1\s*报告期末按行业分类的境内股票投资组合\s*$')
  hk=page.search(r'(?m)^[78]\.2\.2\s*报告期末按行业分类的港股通投资股票投资组合\s*$')
  end=page.search(r'(?m)^[78]\.3\s*期末按[^\n]*所有股票投资明细\s*$')
  if cn:active='CN';top=cn[0]['top']
  else:top=0
  if not active:continue
  scope_text.append(text)
  for table in page.find_tables():
   if table.bbox[3]<=top or end and table.bbox[1]>=end[0]['top']:continue
   if hk and table.bbox[1]>=hk[0]['top']:active='HK'
   for original in table.extract():
    c=[clean(x) for x in original if clean(x)]
    if len(c)==3 and c[0]=='合计':
     if active in totals:raise ValueError('混合行业分表合计重复')
     totals[active]=amount(c[1]);continue
    if active=='CN':
     if len(c)!=4 or not re.fullmatch('[A-S]',c[0]):continue
     key,name,value,shown=c
    else:
     if len(c)!=3 or c[0] in ['行业类别','合计'] or not (re.fullmatch(r'[\d,.]+',c[1]) or c[1]=='-'):continue
     key,name,value,shown=c[0],c[0],c[1],c[2]
    empty=value==shown=='-'
    if (value=='-')!=(shown=='-'):raise ValueError('行业金额与比例缺失不一致')
    v=Decimal(0) if empty else amount(value);pct=Decimal(0) if empty else amount(shown)
    if not v.is_finite() or not pct.is_finite() or v<0 or abs(v/nav*100-pct)>Decimal('.00501'):raise ValueError('混合行业比例与净资产不符')
    rows.append(dict(market=active,key=key,name=name,marketValueCNY=str(v),reportedWeightPct=str(pct),reportedEmpty=empty,locator='PDF页'+str(number),tableBBox=list(table.bbox),originalCells=original))
  if hk:
   active='HK'
   section_text=re.split(r'(?m)^[78]\.2\.2\s*报告期末按行业分类的港股通投资股票投资组合\s*$',text,maxsplit=1)[1]
   section_text=re.split(r'(?m)^[78]\.3\s*期末按[^\n]*所有股票投资明细\s*$',section_text,maxsplit=1)[0].strip()
   if re.fullmatch(r'无[。.]?',section_text):empty_hk=dict(locator='PDF页'+str(number),quote=section_text,meaning='原文明确无港股通股票持仓')
  if end:finished=True;break
 if empty_hk is not None:
  if 'HK' in totals or any(r['market']=='HK' for r in rows):raise ValueError('无港股声明与港股表冲突')
  totals['HK']=Decimal(0)
 if not finished or set(totals)!={'CN','HK'} or sum(totals.values())!=equity:raise ValueError('混合行业分表合计未核对')
 if [r['key'] for r in rows if r['market']=='CN']!=list('ABCDEFGHIJKLMNOPQRS'):raise ValueError('境内A-S行业不完整')
 hkrows=[r for r in rows if r['market']=='HK']
 if (not hkrows and empty_hk is None) or len({r['key'] for r in hkrows})!=len(hkrows):raise ValueError('港股行业缺失或重复')
 if hkrows and not any('GICS' in text for text in scope_text):raise ValueError('港股行业未确认GICS口径')
 for market in ['CN','HK']:
  if sum((Decimal(r['marketValueCNY']) for r in rows if r['market']==market),Decimal(0))!=totals[market]:raise ValueError('分市场行业明细合计不符')
 sectors=[]
 for r in rows:
  v=Decimal(r['marketValueCNY']);prefix='境内' if r['market']=='CN' else '港股GICS'
  sectors.append(dict(key=r['market']+':'+r['key'],name=prefix+'：'+r['name'],taxonomy='report-native-A-S' if r['market']=='CN' else 'GICS',isUnclassified='未分类' in r['name'],components=[r],marketValueCNY=str(v),navWeight=float(v/nav),equityWeight=float(v/equity)))
 return dict(**metadata,currency='CNY',taxonomy='report-native-A-S' if empty_hk else 'mixed-report-native-A-S-and-GICS',emptyMarketEvidence=empty_hk,taxonomyVersion='原报告未核验具体分类规则版本',sourceSha256=hashlib.sha256(Path(pdf).read_bytes()).hexdigest(),sectors=sectors,componentTotalsCNY=[str(totals[m]) for m in ['CN','HK']],note='境内A-S与港股GICS分别保留，不跨口径合并行业或计算集中度；这是期末行业汇总，不是逐股分类。')

def extract(pdf, metadata):
    nav = Decimal(str(metadata['netAssetsCNY']))
    equity = Decimal(str(metadata['equityMarketValueCNY']))
    if not nav.is_finite() or not equity.is_finite() or nav <= 0 or equity <= 0:
        raise ValueError('净资产和权益总额须为正')
    for key in ('reportDate', 'publishedAt'):
        if not isinstance(metadata[key],str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',metadata[key]):
            raise ValueError('报告及披露日期须为YYYY-MM-DD')
    report = datetime.date.fromisoformat(metadata['reportDate'])
    publication = datetime.date.fromisoformat(metadata['publishedAt'])
    source=metadata['sourceUrl']
    if not isinstance(source,str) or re.search(r'[\s\x00-\x1f\x7f]',source):raise ValueError('原文地址无效')
    url=urlsplit(source)
    try:port=url.port
    except ValueError:raise ValueError('原文地址无效')
    if publication < report or url.scheme not in ('https', 'http') or not url.hostname or url.username is not None or url.password is not None or port not in (None,80,443):
        raise ValueError('发布日期或原文地址无效')
    rows, totals = [], []
    started = finished = False
    scheme = None
    section = 0
    with pdfplumber.open(pdf) as document:
        if any(re.search(r'(?m)^[78]\.2\.1\s*报告期末按行业分类的境内股票投资组合\s*$',p.extract_text() or '') for p in document.pages) and any(re.search(r'(?m)^[78]\.2\.2\s*报告期末按行业分类的港股通投资股票投资组合\s*$',p.extract_text() or '') for p in document.pages):
            return mixed_result(document,pdf,metadata,nav,equity)
        for page_no, page in enumerate(document.pages, 1):
            text = page.extract_text() or ''
            if not started:
                if re.search(r'^[78]\.3\s*期末按行业分类的权益投资组合\s*$', text, re.M) and international_taxonomy(''.join(p.extract_text() or '' for p in document.pages[page_no-1:page_no+1])):
                    scheme, started = international_taxonomy(''.join(p.extract_text() or '' for p in document.pages[page_no-1:page_no+1])), True
                elif re.search(r'^[78]\.2\s*报告期末按行业分类的股票投资组合\s*$', text, re.M):
                    scheme, started = 'report-native-A-S', True
            if not started or finished:
                continue
            start_pattern = r'[78]\.3\s*期末按行业分类' if scheme in ('GICS','report-native-international') else r'[78]\.2\s*[^\n]*行业分类'
            starts = page.search(start_pattern)
            start_top = starts[0]['top'] if starts and not rows else 0
            end_pattern = r'[78]\.4\s*期末按[^\n]*所有权益投资明细' if scheme in ('GICS','report-native-international') else r'[78]\.3\s*期末按[^\n]*所有股票投资明细'
            ends = page.search(end_pattern)
            end_top = ends[0]['top'] if ends else float('inf')
            for table in page.find_tables():
                if table.bbox[3] < start_top or table.bbox[1] >= end_top:
                    continue
                for cells in table.extract():
                    c = [clean(x) for x in cells if clean(x)]
                    is_total = len(c) == 3 and c[0] == '合计'
                    if is_total:
                        totals.append(amount(c[1]))
                        continue
                    if scheme in ('GICS','report-native-international'):
                        if len(c) != 3 or c[0] in ('行业类别', '国家（地区）'):
                            continue
                        key, name, value, shown = c[0], c[0], c[1], c[2]
                        if not (re.fullmatch(r'[\d,.]+', value) or value == '-'):
                            continue
                    else:
                        if len(c) != 4 or not re.fullmatch('[A-S]', c[0]):
                            continue
                        key, name, value, shown = c
                        if key == 'A':
                            section += 1
                    empty = value == '-' and shown == '-'
                    if (value == '-') != (shown == '-'):
                        raise ValueError('行业金额与权重缺失不一致')
                    market_value = Decimal(0) if empty else amount(value)
                    displayed = Decimal(0) if empty else amount(shown)
                    if market_value < 0 or abs(market_value / nav * 100 - displayed) > Decimal('.00501'):
                        raise ValueError(name + '行业权重与净资产分母不一致')
                    rows.append({'key': key, 'name': name, 'section': section,
                                 'marketValueCNY': str(market_value),
                                 'reportedWeightPct': str(displayed), 'reportedEmpty': empty,
                                 'isUnclassified': '未分类' in name,
                                 'locator': 'PDF页' + str(page_no)})
            if ends:
                finished = True
    if not started or not finished or not rows:
        raise ValueError('行业表起止边界未完整取得')
    expected = 1 if scheme in ('GICS','report-native-international') else section
    if not totals or len(totals) != expected or sum(totals) != equity:
        raise ValueError('行业分表合计未与权益总额逐分核对')
    if sum(Decimal(r['marketValueCNY']) for r in rows) != equity:
        raise ValueError('行业明细未与权益总额逐分核对')
    for segment in range(1, section+1):
        if [r['key'] for r in rows if r['section'] == segment] != list('ABCDEFGHIJKLMNOPQRS'):
            raise ValueError('A-S行业顺序不完整或重复')
    if scheme in ('GICS','report-native-international') and len({r['key'] for r in rows}) != len(rows):
        raise ValueError('GICS行业重复')
    merged = {}
    for row in rows:
        item = merged.setdefault(row['key'], {'key': row['key'], 'name': row['name'], 'isUnclassified': row['isUnclassified'], 'components': [], '_amount': Decimal(0)})
        if item['name'] != row['name']:
            raise ValueError('行业代码跨分表名称冲突')
        item['_amount'] += Decimal(row['marketValueCNY'])
        item['components'].append(row)
    sectors = []
    for item in merged.values():
        value = item.pop('_amount')
        item.update(marketValueCNY=str(value), navWeight=float(value/nav), equityWeight=float(value/equity))
        sectors.append(item)
    return {**metadata, 'currency': 'CNY', 'taxonomy': scheme,
            'taxonomyVersion': '原报告未核验具体分类规则版本',
            'sourceSha256': hashlib.sha256(Path(pdf).read_bytes()).hexdigest(),
            'sectors': sectors, 'componentTotalsCNY': [str(t) for t in totals],
            'note': '基金整体权益行业汇总；不是逐股分类，不是当前持仓。不同分类口径不得合并排名。'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pdf'); parser.add_argument('--metadata', required=True); parser.add_argument('--out', required=True)
    args = parser.parse_args()
    if Path(args.out).exists():
        raise SystemExit('输出已存在，禁止覆盖旧依据')
    result = extract(args.pdf, json.loads(Path(args.metadata).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant,parse_float=finite_json_float))
    with Path(args.out).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2,allow_nan=False)
