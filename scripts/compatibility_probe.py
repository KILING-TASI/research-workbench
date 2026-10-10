"""Explicit trusted-source interface probes; not general package compatibility."""
import argparse,ast,json,sys,hashlib
from pathlib import Path
from specialist_loader import check,call,LAST_PROVENANCE

def version(folder):
    tree=ast.parse((folder/'__init__.py').read_bytes())
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in node.targets):return ast.literal_eval(node.value)
    return None

def probe(lookthrough,financial,portfolio):
    entries=[]
    for domain,root,module,names in [('lookthrough',lookthrough,'report_adapter',['issuer_order_values','legacy_domestic_rows','legacy_domestic_result']),('financial',financial,'original_compat',['verify']),('portfolio',portfolio,'observed_review',['review'])]:
        folder=root/('src/portfolio_engine' if domain=='portfolio' else 'cnlookthrough' if domain=='lookthrough' else 'cnreconcile')
        records=[check(domain,module,name,project_dir=root) for name in names]
        if not all(x['available'] for x in records):raise ValueError('所选版本缺少已登记接口：'+domain)
        entries.append(dict(domain=domain,softwareVersion=version(folder),interfaces=[module+'.'+name for name in names],methodIdentitySha256=records[0]['methodIdentitySha256'],methodFiles=records[0]['methodFiles'],scope='source declaration located; function execution probes below are limited'))
    groups=[[{'cells':['1','600000','教学A/H主体']}],[{'cells':['2','01988','教学A/H主体']}]]
    assert call('lookthrough','report_adapter','issuer_order_values',groups,[20,30],True,True,project_dir=lookthrough)==[50]
    rejected=False
    try:call('financial','original_compat','verify',{'schemaVersion':999},project_dir=financial)
    except ValueError as e:rejected='schema-1' in str(e)
    assert rejected
    reference=json.loads((portfolio/'examples/observed-review-reference.json').read_text('utf-8'));case=reference['cases'][0]
    observed=call('portfolio','observed_review','review',case['input'],project_dir=portfolio)['result']
    expected=dict(case['expected_result']);actual=dict(observed);a=actual.pop('xirrPct');b=expected.pop('xirrPct');assert actual==expected
    assert a==b or a is not None and b is not None and abs(a-b)<1e-10
    return dict(consumerVersion='0.1.0-beta.10',providers=entries,executionProbes=['explicit A/H ranking pair','unknown schema1 rejection','synthetic observed-account reference case'],status='limited-interface-probes-passed',limitations=['显式可信源码目录，不是从PyPI安装或全部依赖组合认证','函数定位不是实际PDF格式全覆盖；财报项只验证未知schema拒绝，完整正例另由固定提交CI检查','教学观察账户不是恢复真实账户；未列版本不能推定兼容'])

if __name__=='__main__':
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser();p.add_argument('--lookthrough',type=Path,required=True);p.add_argument('--financial',type=Path,required=True);p.add_argument('--portfolio',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    if a.out.exists():p.error('请用新输出文件')
    result=probe(a.lookthrough.resolve(),a.financial.resolve(),a.portfolio.resolve());a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
