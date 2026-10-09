"""Extract nine-column QDII or six-column domestic complete-equity tables.
Requires pdfplumber. Report identity, publication date and totals must be checked
against the original by the caller. Does not infer industry or current holdings.
"""
import argparse,datetime,hashlib,json,re
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse
import pdfplumber

def clean(s): return re.sub(r'\s+','',s or '')
def number(s):
    value=Decimal(clean(s).replace(',',''))
    if not value.is_finite():raise ValueError('原文金额或数量为非有限值')
    return value

def issuer_order_values(groups,values,declared,hk_scope):
    from specialist_loader import call
    return call('lookthrough','report_adapter','issuer_order_values',groups,values,declared,hk_scope)


def domestic_rows(doc):
    from specialist_loader import call
    return call('lookthrough','report_adapter','legacy_domestic_rows',doc)


def domestic_result(doc,raw,code,report_date,published_at,source_url,net_assets,equity_value):
    from specialist_loader import call
    return call('lookthrough','report_adapter','legacy_domestic_result',doc,raw,code,report_date,published_at,source_url,net_assets,equity_value)


def independent_ruiyuan(pdf,code,report_date,published_at,source_url,net_assets,equity_value,project_dir):
    import os,sys,subprocess,tempfile
    if code!='007119':raise ValueError('独立首版仅支持007119；其他产品请省略adapter-project-dir沿用内置入口')
    root=Path(project_dir).resolve();entry=root/'cnlookthrough/report_cli.py'
    if not entry.is_file() or not entry.resolve().is_relative_to(root):raise ValueError('须显式指定可信的已安装独立项目；不自动下载。省略参数可使用内置回退')
    with tempfile.TemporaryDirectory(prefix='holdings-adapter-') as temporary:
        output=Path(temporary)/'parsed.json'
        args=[sys.executable,'-m','cnlookthrough.report_cli',str(Path(pdf).resolve()),'--report-date',report_date,'--published-at',published_at,'--source-url',source_url,'--net-assets',str(net_assets),'--equity-value',str(equity_value),'--format','parsed','--out',str(output)]
        environment=dict(os.environ,PYTHONIOENCODING='utf-8');environment.pop('PYTHONPATH',None)
        try:done=subprocess.run(args,cwd=root,env=environment,capture_output=True,text=True,encoding='utf-8',timeout=180)
        except (OSError,subprocess.TimeoutExpired) as error:raise ValueError('独立适配未完成；未静默改用其他算法') from error
        if done.returncode or not output.is_file():raise ValueError('独立适配未完成：'+done.stderr[-1000:]+'；如需内置回退，请明确省略adapter-project-dir')
        from collection_validation import unique_pairs,reject_constant
        result=json.loads(output.read_text('utf-8'),object_pairs_hook=unique_pairs,parse_constant=reject_constant)
        if result.get('id')!=code or result.get('reportDate')!=report_date or result.get('sourceSha256')!=hashlib.sha256(Path(pdf).read_bytes()).hexdigest():raise ValueError('独立输出的身份/版本与本次输入不符')
        if result.get('adapterProfile')!='ruiyuan-growth-six-column-v1' or result.get('disclosureScope')!='completeEquity' or result.get('portfolioScope')!='fund-all-share-classes' or result.get('currency')!='CNY' or result.get('publishedAt')!=published_at:raise ValueError('独立输出接口或口径不等价，不能替代旧解析')
        if result.get('inputSchema')!='explicit-report-totals-v1' or result.get('rulesVersion')!='six-column-equity-1':raise ValueError('独立适配schema或规则版本未确认')
        try:totals_match=number(str(result.get('netAssetsCNY')))==number(str(net_assets)) and number(str(result.get('equityMarketValueCNY')))==number(str(equity_value))
        except ArithmeticError:raise ValueError('独立适配金额字段无效')
        if not totals_match:raise ValueError('独立适配净资产/权益总额与显式输入不符')
        result['engineSelection']={'engine':'cn-fund-lookthrough','inputSchema':'explicit-report-totals-v1','rulesVersion':'six-column-equity-1','methodFiles':{name:hashlib.sha256((root/'cnlookthrough'/name).read_bytes()).hexdigest() for name in ('report_adapter.py','report_cli.py','engine.py')}}
        return result

def extract(pdf,code,report_date,published_at,source_url,net_assets,equity_value,adapter_project_dir=None):
    if adapter_project_dir is not None:return independent_ruiyuan(pdf,code,report_date,published_at,source_url,net_assets,equity_value,adapter_project_dir)
    if not re.fullmatch(r'\d{6}',code): raise ValueError('基金代码须为六位数字')
    if datetime.date.fromisoformat(report_date)>datetime.date.fromisoformat(published_at): raise ValueError('发布日期早于报告日')
    if urlparse(source_url).scheme!='https': raise ValueError('需HTTPS原文地址')
    net_assets,equity_value=Decimal(str(net_assets)),Decimal(str(equity_value))
    if net_assets<=0 or equity_value<0 or equity_value>net_assets: raise ValueError('净资产或股票总额不合法')
    raw=Path(pdf).read_bytes(); rows=[]; started=False; finished=False
    with pdfplumber.open(pdf) as doc:
        texts=[p.extract_text() or '' for p in doc.pages]
        alltext='\n'.join(texts)
        if code not in alltext or '中期报告' not in alltext and '年度报告' not in alltext: raise ValueError('代码/报告类型未在原文中找到')
        rd=datetime.date.fromisoformat(report_date)
        # Some managers print leading zeroes in month/day.
        if not re.search(rf'{rd.year}年0?{rd.month}月0?{rd.day}日',clean(alltext)): raise ValueError('报告日未在原文找到')
        if re.search(r'^(?:[78]\.3(?:\.[12])?\s*)?(?:报告)?期末按.*所有股票投资明细',alltext,re.M):
            return domestic_result(doc,raw,code,report_date,published_at,source_url,net_assets,equity_value)
        for page_no,(page,text) in enumerate(zip(doc.pages,texts),1):
            normalized=clean(text)
            if re.search(r'^[78]\.4\s*期末按',text,re.M) and '所有权益投资明细' in normalized: started=True
            if not started or finished: continue
            for table in page.extract_tables():
                for cells in table:
                    if len(cells)!=9: continue
                    c=[clean(x) for x in cells]
                    if c[0].isdigit() and re.fullmatch(r'(?:\d+(?:CH|HK)|[A-Z][A-Z0-9./-]*US)',c[3]):
                        rows.append({'rank':int(c[0]),'cells':c,'reportedCode':c[3],'pages':[page_no]})
                    elif not c[0] and rows and re.fullmatch(r'(?:\d+(?:CH|HK)|[A-Z][A-Z0-9./-]*US)',c[3]) and c[6] and c[7] and c[8]:
                        # Merged issuer/rank cells may cover separate A/H securities.
                        if c[1] or c[2]: raise ValueError('无序号新证券却有独立公司名称，不能推断同发行人')
                        previous=rows[-1]
                        c[0]=str(previous['rank']);c[1]=previous['cells'][1];c[2]=previous['cells'][2]
                        if c[3]==previous['cells'][3]: raise ValueError('合并序号证券重复')
                        rows.append({'rank':previous['rank'],'cells':c,'pages':[page_no],'sharedIssuerRank':True})
                    elif not c[0] and rows and any(c) and not c[3] and not c[7] and not c[8]:
                        for i in range(1,9): rows[-1]['cells'][i]+=c[i]
                        rows[-1]['pages'].append(page_no)
            if rows and re.search(r'^[78]\.5\s*报告期内权益投资组合的重大变动',text,re.M): finished=True
    if not started or not finished or not rows: raise ValueError('未找到完整7.4权益表至7.5边界；此版仅支持九列QDII布局')
    if rows[0]['rank']!=1: raise ValueError('排名未从1开始')
    for previous,current in zip(rows,rows[1:]):
        delta=current['rank']-previous['rank']
        if delta!=1 and not (delta==0 and current.get('sharedIssuerRank')): raise ValueError('排名不连续，可能漏行或误识别')
    total=sum((number(r['cells'][7]) for r in rows),Decimal(0))
    if total!=equity_value: raise ValueError(f'权益市值合计不一致：{total} vs {equity_value}')
    holdings=[];security_keys=set()
    for r in rows:
        c=r['cells'];m=re.fullmatch(r'(\d+)(CH|HK)|([A-Z][A-Z0-9./-]*)(US)',c[3]);code_value,region=(m.group(1),m.group(2)) if m.group(1) else (m.group(3),m.group(4))
        market=('NASDAQ' if '纳斯达' in c[4] else 'NYSE' if '纽约' in c[4] else 'US-exchange-unresolved') if region=='US' else 'HKEX' if region=='HK' else 'SSE' if '上海' in c[4] else 'SZSE' if '深圳' in c[4] else 'BSE' if '北京' in c[4] else None
        if not market: raise ValueError('交易市场无法识别')
        security=code_value if region=='US' else code_value.zfill(5 if region=='HK' else 6)
        security_key=(region,security)
        if security_key in security_keys: raise ValueError('完整权益表证券重复，不能重复计入金额')
        security_keys.add(security_key)
        mv=number(c[7]);weight=mv/net_assets;shown=number(c[8]);quantity=number(c[6])
        if mv<0 or quantity<0:raise ValueError('权益市值或股数为负，须复核')
        if abs(weight*100-shown)>Decimal('.00501'): raise ValueError(f'{security}权重与公允价值不匹配')
        holdings.append({'market':market,'securityNamespace':'US-equity' if region=='US' else 'HK-equity' if region=='HK' else 'CN-equity','code':security,'shareClass':'ordinary','name':c[2],'weight':float(weight),'quantity':int(quantity) if quantity==quantity.to_integral_value() else float(quantity),'marketValueCNY':float(mv),'reportedWeightPct':float(shown),'industry':'','locator':'PDF页'+','.join(map(str,sorted(set(r['pages'])))),'rank':r['rank']})
    return {'id':code,'allocation':1,'currency':'CNY','reportDate':report_date,'publishedAt':published_at,'sourceUrl':source_url,'locator':'中报§7.4/年报§8.4完整权益明细；金额为人民币','disclosureScope':'completeEquity','equityWeight':float(equity_value/net_assets),'netAssetsCNY':float(net_assets),'equityMarketValueCNY':float(equity_value),'holdings':holdings,'portfolioScope':'fund-all-share-classes','sourceSha256':hashlib.sha256(raw).hexdigest(),'parserVersion':'complete-equity-9','verification':'逐行权重与金额勾稽、连续序号及权益合计通过；输入身份/日期/总额仍需原文人工核验','limitations':['仅报告日股票快照，不是当前持仓或交易流水','行业未分类，不输出行业集中度结论','权重用人民币市值/净资产，保留报告中0.00%的非零小额持仓']}

def main():
    p=argparse.ArgumentParser();p.add_argument('pdf');p.add_argument('--code',required=True);p.add_argument('--report-date',required=True);p.add_argument('--published-at',required=True);p.add_argument('--source-url',required=True);p.add_argument('--net-assets',required=True);p.add_argument('--equity-value',required=True);p.add_argument('--out',required=True);p.add_argument('--adapter-project-dir',help='可选：可信独立持仓适配项目目录，仅限定007119；默认保留内置流程');a=p.parse_args()
    out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise FileExistsError('输出文件已存在，请使用新文件名；首次依据不覆盖')
    result=extract(a.pdf,a.code,a.report_date,a.published_at,a.source_url,a.net_assets,a.equity_value,adapter_project_dir=a.adapter_project_dir)
    with out.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False)
    print(f'Extracted {len(result["holdings"])} equities; amount reconciled; source archived separately')
if __name__=='__main__': main()



