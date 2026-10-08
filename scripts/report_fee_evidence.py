"""Period-report fee statements, never automatically current legal fees."""
import hashlib,json,re
from pathlib import Path
import pdfplumber
from verify_original import compact

def sales_service_statements(pages):
 """Extract explicit share-class clauses, never related-party amounts."""
 result={}
 for share in ('A','C'):
  matches=[]
  prefix=r'(?:本基金)?'+share+r'类基金份额'
  patterns=[prefix+r'(?:的)?(?:年)?销售服务费(?:的)?(?:年费率为|费率为|按前一日'+share+r'类基金份额的基金资产净值的)(\d+(?:\.\d+)?)%(?:的年费率计提)?']
  for page,text in pages:
   normalized=compact(text)
   for pattern in patterns:
    for m in re.finditer(pattern,normalized):
     rate=float(m[1])
     if rate>100:raise ValueError('销售服务费率超过100%，需复核原文')
     # A bare percentage is accepted only with an explicit annual-rate clause.
     if '年' not in m[0]:continue
     matches.append(dict(annualRatePct=rate,page=page,quote=m[0]))
   for m in re.finditer(prefix+r'不收取销售服务费',normalized):
    matches.append(dict(annualRatePct=0.0,page=page,quote=m[0]))
  values={m['annualRatePct'] for m in matches}
  result[share]=dict(value=next(iter(values)) if len(values)==1 else None,status='报告原文单一费率' if len(values)==1 else '多费率冲突，需核对期间/条件' if values else '未匹配明确份额年费率原文',evidence=matches,unit='annual-pct',currentEffectiveVerified=False)
 return result

def statements(pages):
 result={}
 for label in ['管理费','托管费']:
  matches=[]
  patterns=[r'(?:本基金的|基金)'+label+r'按前一日基金资产净值的?(\d+(?:\.\d+)?)%的?年费率计提',r'本基金年'+label+r'率为(\d+(?:\.\d+)?)%']
  if label=='管理费':patterns.append(r'(?:基金)?管理人报酬按前一日基金资产净值的?(\d+(?:\.\d+)?)%的?年费率计提')
  for number,text in pages:
   normalized=compact(text)
   for pattern in patterns:
    for m in re.finditer(pattern,normalized):
     rate=float(m[1])
     if rate>100:raise ValueError('费率超过100%，需复核原文')
     matches.append(dict(annualRatePct=rate,page=number,quote=m[0],context=normalized[max(0,m.start()-120):m.end()+120]))
  if label=='托管费':
   for number,text in pages:
    normalized=compact(text)
    for m in re.finditer(r'支付基金托管人的托管费按前一日基金资产净值的?(\d+(?:\.\d+)?)%的?年费率计提',normalized):
     rate=float(m[1])
     if rate>100:raise ValueError('费率超过100%，需复核原文')
     matches.append(dict(annualRatePct=rate,page=number,quote=m[0],context=normalized[max(0,m.start()-120):m.end()+120]))
  values={m['annualRatePct'] for m in matches}
  result[label]=dict(value=next(iter(values)) if len(values)==1 else None,status='报告原文单一费率' if len(values)==1 else '多费率冲突，需核对期间/条件' if values else '未匹配明确费率原文',evidence=matches,unit='annual-pct',currentEffectiveVerified=False)
 return result

def extract_archive(r,base_dir=None):
 if r['status'] not in ('副本身份已匹配','副本身份及股票持仓勾稽完成','股票明细与行业表勾稽完成，会计差额待核验'):raise ValueError('报告身份未核验')
 path=Path(r['documentPath'])
 if base_dir is not None and not path.is_absolute():path=Path(base_dir)/path
 raw=path.read_bytes()
 if hashlib.sha256(raw).hexdigest()!=r['sha256']:raise ValueError('PDF哈希变化')
 with pdfplumber.open(path) as doc:pages=[(n,p.extract_text() or '') for n,p in enumerate(doc.pages,1)]
 fees=statements(pages)
 result=dict(reportDate=r['reportDate'],publishedAt=r['metadata']['publishedAt'],sourceUrl=r['metadata']['sourceUrl'],sourceSha256=r['sha256'],fees=fees,salesServiceFees=sales_service_statements(pages))
 result['limitations']=['仅报告明确措辞的管理/托管及A/C销售服务年费率，不代表当前有效合同','减免、期间变更、其他份额或分档收费可能不适配，不推断缺失值','申购、赎回费需份额与最新有效文件，未从总费用反推费率','净值通常已扣经常性费用，历史净值收益不重复扣除']
 return result
