"""Discover, archive and parse same-period child reports; keep unresolved exposures unknown."""
import argparse,datetime as dt,hashlib,json,re,urllib.request,unicodedata
from pathlib import Path
from urllib.parse import urlencode,urlparse
from decimal import Decimal
import math
from collection_validation import unique_pairs,reject_constant

def load_json(text):
 return json.loads(text,object_pairs_hook=unique_pairs,parse_constant=reject_constant)

import pdfplumber
from verify_original import compact,dates_in
from market_collect import atomic

def download(url):
    from public_download import download as fetch_public
    return fetch_public(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://fundf10.eastmoney.com/'})

def normalized_year_title(title):
    return unicodedata.normalize("NFKC", title).translate(str.maketrans("〇零一二三四五六七八九", "00123456789"))

def period_title_matches(title,year,suffix):
    text=compact(normalized_year_title(title))
    return bool(re.search(r'(?<!\d)'+re.escape(year)+r'(?:年)?'+re.escape(suffix),text))

def discover(code,period,asof):
    year=period[:4];suffix='年度报告' if period.endswith('12-31') else '中期报告' if period.endswith('06-30') else None
    if not suffix:raise ValueError('完整持仓目前仅关联年报/中报，不用季报前十大代替')
    candidates=[]
    for page in range(1,11):
        url='https://api.fund.eastmoney.com/f10/JJGG?'+urlencode(dict(fundcode=code,pageIndex=page,pageSize=100,type=3))
        data=load_json(download(url));items=data.get('Data')
        if not isinstance(items,list):raise ValueError('报告目录接口结构异常')
        for x in items:
            title=x.get('TITLE','');published=str(x.get('PUBLISHDATE',''))[:10]
            if str(x.get('FUNDCODE'))!=code:raise ValueError('报告目录代码不一致')
            if period_title_matches(title,year,suffix) and not re.search('摘要|英文',title) and period<=published<=asof:
                candidates.append({'title':title,'publishedAt':published,'id':x['ID'],'discoveryUrl':url})
        if len(items)<100 or (items and str(items[-1].get('PUBLISHDATE',''))[:4]<year):break
    if len(candidates)!=1:raise ValueError('同报告期候选数量为'+str(len(candidates))+'，缺失或修订冲突需复核')
    candidate=candidates[0]
    url='https://np-cnotice-stock.eastmoney.com/api/content/ann?'+urlencode(dict(art_code=candidate['id'],client_source='web',page_index=1))
    detail=load_json(download(url)).get('data') or {}
    if detail.get('art_code')!=candidate['id']:raise ValueError('公告详情ID不一致')
    attachment=detail.get('attach_url')
    if not attachment:raise ValueError('公告未返回附件地址，禁止猜测PDF')
    return {**candidate,'sourceUrl':attachment,'detailUrl':url,'provenance':'third-party-report-copy'}

def industry_equity_evidence(path):
    """Keep index/active industry subtotals distinct; never add a parent total twice."""
    totals={};evidence=[];notes=[];active=False;section=None
    with pdfplumber.open(path) as doc:
        for page_no,page in enumerate(doc.pages,1):
            text=page.extract_text() or ''
            generic=page.search(r'(?m)^[78]\.2(?:\.1)?\s*报告期末按行业分类的(?:境内)?股票投资组合\s*$')
            indexed=page.search(r'(?m)^[78]\.2\.1\s*(?:期末指数投资|指数投资期末)按行业分类的境内股票投资组合\s*$')
            managed=page.search(r'(?m)^[78]\.2\.2\s*(?:期末积极投资|积极投资期末)按行业分类(?:的)?境内股票投资组合\s*$')
            headers=sorted([(x['top'],'allEquity') for x in generic]+[(x['top'],'indexInvestment') for x in indexed]+[(x['top'],'activeInvestment') for x in managed])
            ends=page.search(r'(?m)^[78]\.3(?:\.1)?\s*期末按[^\n]*所有股票投资明细\s*$')
            if headers or active or '§7投资组合报告' in compact(text) or '§8投资组合报告' in compact(text):
                for match in re.finditer(r'注[：:][^。]{0,100}可退替代款[^。]{0,100}估值增值[^。]{0,100}。',compact(text)):
                    notes.append({'page':page_no,'quote':match.group(0)})
            if headers:active=True
            if not active:continue
            for table in sorted(page.find_tables(),key=lambda x:x.bbox[1]):
                if ends and table.bbox[1]>=ends[0]['top']:continue
                applicable=[(top,label) for top,label in headers if top<table.bbox[1]]
                table_section=applicable[-1][1] if applicable else section
                if table_section is None:continue
                for row in table.extract():
                    if not row or '合计' not in [compact(c) for c in row]:continue
                    numbers=[Decimal(compact(c).replace(',','')) for c in row if re.fullmatch(r'\d{1,3}(?:,\d{3})+\.\d{2}',compact(c))]
                    if len(numbers)!=1:raise ValueError('行业合计金额未唯一确认')
                    totals.setdefault(table_section,set()).add(numbers[0]);evidence.append({'page':page_no,'row':row,'tableBBox':list(table.bbox),'segment':table_section})
            if headers:section=headers[-1][1]
            if ends:break
    if not notes or any(len(values)!=1 for values in totals.values()):raise ValueError('行业表合计或可退替代款口径说明未唯一确认')
    if set(totals)=={'allEquity'}:value=next(iter(totals['allEquity']))
    elif set(totals)=={'indexInvestment','activeInvestment'}:value=sum((next(iter(values)) for values in totals.values()),Decimal(0))
    else:raise ValueError('行业指数/积极分表缺失或与总表混用，不合并')
    return value,evidence,notes

def both_stock_balance_columns_empty(row):
    """Require two explicit empty amount columns, not a missing/blank extraction."""
    tokens=[compact(x) for x in row[1:] if compact(x)]
    tokens=[x for x in tokens if not re.fullmatch(r'\d+\.\d+\.\d+(?:\.\d+)?',x)]
    return len(tokens)==2 and all(x in ('-','－','—') for x in tokens)

class NonEquityScope(ValueError):
    """Original declares no stocks; other assets remain unparsed."""
    def __init__(self,page):
        self.page=page
        super().__init__('PDF页'+str(page)+'原文明示期末未持有股票；当前股票穿透入口不适配其非股票资产，不能当作零风险或现金')

def explicit_empty_complete_stock_section(text):
    """Only a complete stock section bounded by the same chapter's changes section."""
    normalized=compact(text)
    for chapter in ('7','8'):
        start=re.search(re.escape(chapter)+r'\.3(?:报告)?期末按公允价值占基金资产净值比例大小排序的所有股票投资明细',normalized)
        if not start:continue
        remaining=normalized[start.end():]
        end=re.search(re.escape(chapter)+r'\.4报告期内股票投资组合的重大变动',remaining)
        if end and remaining[:end.start()] in ('无。','无','注：无。','注:无。'):return True
    return False

def inspect_and_parse(path,code,period,metadata):
    with pdfplumber.open(path) as doc:
        raw_front='\n'.join(p.extract_text() or '' for p in doc.pages[:12])
        front=compact(raw_front)
        if not re.search(r'(?<!\d)'+re.escape(code)+r'(?!\d)',raw_front):raise ValueError('报告前12页未找到子基金代码，份额共用关系未确认')
        if compact(normalized_year_title(metadata['title'])) not in normalized_year_title(front) or period not in dates_in(front):raise ValueError('报告标题/报告期不一致')
        if metadata['publishedAt'] not in dates_in(doc.pages[0].extract_text() or ''):raise ValueError('报告送出日期与目录不一致')
        for pno,page in enumerate(doc.pages,1):
            no_stocks=re.search(r'本基金本报告期末未持有股票(?:资产)?。',compact(page.extract_text() or ''))
            if no_stocks or explicit_empty_complete_stock_section(page.extract_text() or ''):
                raise NonEquityScope(pno)
        values={'nav':set(),'equity':set()};locators=[];empty_stock_page=None;in_balance=False;unit_confirmed=False;pending_balance_page=None;pending_balance_date=False
        for pno,p in enumerate(doc.pages,1):
            text=compact(p.extract_text())
            starts=p.search(r'(?m)^(?:[67]\.1\s*)?资产负债表\s*$')
            if starts:pending_balance_page=pno;pending_balance_date=period in dates_in(text)
            current_date=period in dates_in(text)
            adjacent_date=pending_balance_page is not None and pno-pending_balance_page<=1 and pending_balance_date
            header_ready=('单位：人民币元' in text or '单位:人民币元' in text) and (current_date or adjacent_date)
            if pending_balance_page is not None and pno-pending_balance_page<=1 and header_ready:
                in_balance=True
                unit_confirmed=True
            if pending_balance_page is not None and pno-pending_balance_page>1 and not in_balance:pending_balance_page=None
            if not in_balance:continue
            ends=p.search(r'(?m)^(?:[67]\.2\s*)?利润表\s*$')
            for table in p.find_tables():
                if ends and table.bbox[1]>=ends[0]['top']:continue
                if starts and table.bbox[3]<=starts[0]['top']:continue
                for row in table.extract():
                    if not row:continue
                    label=compact(row[0]);key='nav' if label in ['净资产合计','所有者权益合计'] else 'equity' if label=='其中：股票投资' else None
                    if key is None:continue
                    # Only financial statement pages explicitly denominated in RMB yuan.
                    if not unit_confirmed:continue
                    if key=='equity' and both_stock_balance_columns_empty(row):empty_stock_page=pno
                    nums=[]
                    for c in row[1:]:
                        token=compact(c).replace(',','')
                        if re.fullmatch(r'-?\d+\.\d{2}',token):nums.append(Decimal(token))
                    if nums:values[key].add(nums[0]);locators.append({'page':pno,'row':row,'field':key})
            if ends:break
    if not values['equity'] and empty_stock_page is not None:raise NonEquityScope(empty_stock_page)
    if any(len(v)!=1 for v in values.values()):raise ValueError('当前期净资产/股票总额缺失或歧义，需要补充报表定位；不猜分母')
    nav=next(iter(values['nav']));equity=next(iter(values['equity']))
    from fund_report_holdings import extract
    try:
        result=extract(path,code,period,metadata['publishedAt'],metadata['sourceUrl'],nav,equity)
    except ValueError as primary_error:
        try:
            portfolio,evidence,notes=industry_equity_evidence(path)
            result=extract(path,code,period,metadata['publishedAt'],metadata['sourceUrl'],nav,portfolio)
        except ValueError as fallback_error:
            raise ValueError('会计股票口径解析失败：'+str(primary_error)+'；行业口径复核失败：'+str(fallback_error)) from fallback_error
        result['accountingReconciliation']={'status':'unresolved','accountingEquityCNY':str(equity),'portfolioEquityCNY':str(portfolio),'differenceCNY':str(equity-portfolio),'industryEvidence':evidence,'scopeNotes':notes,'explanation':'股票明细与行业表合计一致；与会计余额的差额尚未逐项解释，不能仅凭口径注释认定差额原因。'}
    result['autoDenominatorEvidence']=locators
    result['sourceVerification']='report-copy-identity-and-reconciliation-not-official-web-verification'
    return result

def archive_parser_method(base,sources):
    """Keep parser and source-review code; not a full dependency environment archive."""
    method_sha=hashlib.sha256(b''.join(sources.values())).hexdigest()
    folder=Path(base)/'methods'/method_sha
    folder.mkdir(parents=True,exist_ok=True)
    for name,raw in sources.items():
        target=folder/name
        if target.exists():
            if target.read_bytes()!=raw:raise ValueError('解析方法档案内容改变，停止使用该档案')
        else:
            with target.open('xb') as stream:stream.write(raw)
    return method_sha

def run(fof,workspace,asof,uploads=None,online=False,limit=100,start_index=0):
    if not isinstance(fof,dict) or not isinstance(fof.get('holdings'),list):raise ValueError('父基金须提供持仓对象列表')
    codes=[]
    for h in fof['holdings']:
        if not isinstance(h,dict) or not isinstance(h.get('code'),str) or not re.fullmatch(r'[0-9]{6}',h['code']):raise ValueError('子基金代码须为六位数字')
        codes.append(h['code'])
        w=h.get('weight')
        if w is not None and (isinstance(w,bool) or not isinstance(w,(float,int)) or not math.isfinite(w) or not 0<=w<=1):raise ValueError('父持仓权重须有限且在0至1；未知可留空')
    if len(codes)!=len(set(codes)):raise ValueError('子基金重复，不能重复穿透')
    period=fof['reportDate']
    for value,label in [(period,'报告期'),(asof,'研究截止日')]:
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):raise ValueError(label+'须为YYYY-MM-DD日历日期')
        try:dt.date.fromisoformat(value)
        except ValueError as exc:raise ValueError(label+'不是有效日历日期') from exc
    if period>asof:raise ValueError('报告期晚于截止日')
    uploads=uploads or [];mapped={}
    for item in uploads:
        key=(item['code'],item['reportDate'])
        if key in mapped:raise ValueError('上传报告代码与期间重复')
        mapped[key]=item
    if type(limit)!=int or not 1<=limit<=500:raise ValueError('limit须为1至500')
    if type(start_index)!=int or not 0<=start_index<=len(fof['holdings']):raise ValueError('start_index须为父持仓范围内的非负整数')
    import fund_report_holdings
    import pdf_structure_review
    sources={'fof_reports.py':Path(__file__).read_bytes(),'fund_report_holdings.py':Path(fund_report_holdings.__file__).read_bytes(),'pdf_structure_review.py':Path(pdf_structure_review.__file__).read_bytes()}
    base=Path(workspace)/'fof-report-library';base.mkdir(parents=True,exist_ok=True)
    method_sha=archive_parser_method(base,sources)
    results=[];nodes={};seen=set()
    for position,h in enumerate(fof['holdings']):
        code=h['code']
        if not re.fullmatch(r'\d{6}',code) or code in seen:raise ValueError('子基金代码非法或重复')
        seen.add(code);record={'code':code,'name':h.get('name'),'reportDate':period,'fofWeight':h.get('weight'),'status':'missing'}
        folder=base/code/period
        try:
            if not start_index<=position<start_index+limit:raise ValueError('本批范围之外，待续采或合并已取得结果')
            upload=mapped.get((code,period));cached=folder/'source.json'
            if upload:
                metadata={k:upload[k] for k in ['title','publishedAt','sourceUrl']}
                metadata['provenance']='user-supplied-pdf';raw=Path(upload['path']).read_bytes()
            elif cached.exists():
                metadata=load_json(cached.read_text(encoding='utf-8'))
                if not isinstance(metadata,dict) or not isinstance(metadata.get('filename'),str) or not re.fullmatch(r'[a-f0-9]{64}\.pdf',metadata['filename']):raise ValueError('报告库文件名无效，不能引用目录外文件')
                if metadata.get('code')!=code or metadata.get('reportDate')!=period:raise ValueError('报告库身份或期间不一致')
                raw=(folder/metadata['filename']).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=metadata['sha256']:raise ValueError('报告库哈希变化')
            elif online:
                metadata=discover(code,period,asof);raw=download(metadata['sourceUrl'])
            else:raise ValueError('本地无报告；可启用online或提供uploads')
            published=metadata.get('publishedAt')
            if not isinstance(published,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',published):raise ValueError('报告发布日期须为YYYY-MM-DD日历日期')
            try:dt.date.fromisoformat(published)
            except ValueError as exc:raise ValueError('报告发布日期不是有效日历日期') from exc
            if not period<=published<=asof:raise ValueError('报告发布时点越界')
            if not raw.startswith(b'%PDF'):raise ValueError('附件不是PDF')
            digest=hashlib.sha256(raw).hexdigest();folder.mkdir(parents=True,exist_ok=True)
            path=folder/(digest+'.pdf')
            if not path.exists():path.write_bytes(raw)
            metadata.update(sha256=digest,filename=path.name,code=code,reportDate=period)
            atomic(folder/'source.json',metadata)
            record.update(status='downloaded-unparsed',documentPath=str(path),metadata=metadata,parserMethodSha256=method_sha)
            from pdf_structure_review import review
            source_review=review(path);record['sourceStructureReview']=source_review
            parsed=inspect_and_parse(path,code,period,metadata)
            parsed['parserMethodSha256']=method_sha
            parsed_path=folder/(digest+'-'+method_sha[:16]+'-equity.json')
            if parsed_path.exists():
                if load_json(parsed_path.read_text(encoding='utf-8'))!=parsed:raise ValueError('同原件同方法结果改变，保留旧解析并复核')
            else:atomic(parsed_path,parsed)
            if source_review['reviewRequired']:
                record.update(scopeStatus='source-structure-review-required',parsedPath=str(parsed_path),holdingsCount=len(parsed['holdings']))
                raise ValueError('原件结构需复核，股票金额已提取但不纳入已确认FOF子节点')
            if parsed.get('accountingReconciliation',{}).get('status')=='unresolved':
                record.update(scopeStatus='accounting-reconciliation-required',parsedPath=str(parsed_path),holdingsCount=len(parsed['holdings']),accountingReconciliation=parsed['accountingReconciliation'])
                raise ValueError('股票表已核对但会计差额未解释，暂不进入FOF自动穿透')
            nodes[code]={'currency':'CNY','reportDate':period,'publishedAt':metadata['publishedAt'],'sourceUrl':metadata['sourceUrl'],
                'holdings':[{'id':x['securityNamespace']+':'+x['code'],'kind':'stock','weight':x['weight']} for x in parsed['holdings']]}
            record.update(status='parsed-equity',holdingsCount=len(parsed['holdings']),parsedPath=str(parsed_path),parserMethodSha256=method_sha)
        except NonEquityScope as exc:
            record.update(reason=str(exc),scopeStatus='non-equity-analysis-required',noStockDisclosurePage=exc.page,nextResearchScope=['bond','repo','bank-and-other-assets','liabilities'],scopeLimitation='未解析完整非股票资产，不当现金或零风险')
        except Exception as exc:record['reason']=type(exc).__name__+': '+str(exc)
        results.append(record)
        atomic(base/'latest-progress.json',{'asOf':asof,'reportDate':period,'rows':results})
    missing=[r for r in results if r['status']!='parsed-equity']
    result={'type':'fof-child-report-linking','asOf':asof,'reportDate':period,'rows':results,'nodes':nodes,'pendingReports':missing,
        'batch':{'startIndex':start_index,'limit':limit,'selectedCount':len(fof['holdings'][start_index:start_index+limit]),'totalParentHoldings':len(fof['holdings'])},
        'counts':{'requested':len(results),'parsed':len(nodes),'pending':len(missing)},
        'limitations':['自动解析当前仅完整股票持仓布局，债券/黄金/嵌套FOF报告可能仅入库待适配','第三方副本或用户文件不自动标为官方原文核验','非股票及缺失子基金权重继续未知；MOM未公开内部持仓不可生成']}
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('fof');p.add_argument('--workspace',required=True);p.add_argument('--as-of',required=True);p.add_argument('--uploads');p.add_argument('--online',action='store_true');p.add_argument('--limit',type=int,default=100);p.add_argument('--start-index',type=int,default=0);p.add_argument('--out',required=True);a=p.parse_args()
    if Path(a.out).exists():raise FileExistsError('输出已存在')
    result=run(load_json(Path(a.fof).read_text(encoding='utf-8-sig')),a.workspace,a.as_of,load_json(Path(a.uploads).read_text(encoding='utf-8-sig')) if a.uploads else None,a.online,a.limit,a.start_index)
    atomic(Path(a.out),result)

