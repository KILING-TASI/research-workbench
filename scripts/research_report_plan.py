"""Explicit single-subject report planning; not a data collector or all-topic report engine."""
import argparse,json,re,copy
from pathlib import Path
from collection_validation import day,unique_pairs,reject_constant
PROFILES={
 'company':{'title':'上市公司深度研究','kinds':['stock'],'references':['company-one-page.md','company-report-workflow.md','company-scenarios.md','announcements-events.md'],'sections':['公司与近况','业务分部','产销链与供应链','研发与竞争结构','财务与原文核验','已取得券商观点','催化条件与反证','盈利情景与估值','风险及跟踪'],'gaps':['券商观点仅来自已取得报告，不能代填最新推荐逻辑','预测需要显式假设，估值不转化成目标价或交易指令']},
 'fund':{'title':'场外基金深度研究','kinds':['fund'],'references':['fund-user-guide.md','compare-evaluate.md','holdings-portfolio.md'],'sections':['身份与份额','业绩与风险','基准与同类','经理及年报观点','持仓与集中度','份额与持有人','申赎及费率','风险和缺口'],'gaps':['经理全履历与全部历史产品不保证完整','申赎行为需实际披露，规模变动不能直接当净申赎']},
 'etf':{'title':'ETF一页纸研究','kinds':['etf'],'references':['compare-evaluate.md','etf-closing-premium.md','etf-share-flow.md','holdings-portfolio.md'],'sections':['产品与指数','规模与流动性','收益与回撤','跟踪质量','持仓及集中度','收盘折溢价','申赎与份额','风险及数据时点'],'gaps':['收盘折溢价不冒称实时IOPV','PDF、Word与分享链接按实际导出环境提供，不默认全部支持']},
 'industry':{'title':'产业与产业指数研究','kinds':['industry','concept','industry-index'],'references':['industry-financials.md','industry-exit-scenarios.md','research-report-reading.md'],'sections':['主题及分类版本','产业链','需求与供给','竞争与份额','行业财务样本','政策与风险','情景及跟踪'],'gaps':['无匹配时不把概念偷换成普通行业或指数','没有全行业成份库时仅报告指定样本，不称全行业']},
 'convertible':{'title':'单只可转债研究','kinds':['convertible'],'references':['query-screen.md','announcements-events.md'],'sections':['债券与正股身份','转股条款及公告','股性与债性','债底与信用假设','强赎回售下修','情景及退出约束','风险'],'gaps':['独立主包未接通完整转债含权定价与自动条款采集','债底模型不保证兑付，缺条款或主体资料不能出完整结论']},
 'futures':{'title':'单合约期货研究','kinds':['futures-contract'],'references':[],'sections':['合约及交割','盘面量仓','期限结构','期现基差','库存仓单','会员持仓','供需与宏观','条件情景与风险'],'gaps':['期货行情、基差、仓单与会员持仓采集未接通','不输出日内关键买卖价位、走势预测或完整F9报告承诺']},
 'issuer':{'title':'企业主体研究','kinds':['issuer'],'references':['company-one-page.md','announcements-events.md'],'sections':['主体及治理','业务与行业','财务和现金流','偿债及信用','发行定价依据','司法及ESG','风险及缺口'],'gaps':['主包不支持非上市企业完整资料自动采集','司法、ESG、评级及信用资料需有公开原件或用户提供，不能据空值判断安全']},
 'liquidity':{'title':'宏观资金面研究','kinds':['macro-liquidity'],'references':['macro-asset-observation.md'],'sections':['央行操作','银行间利率','政策利率','准备金与基础货币','政府债发行缴款','税期与跨季','存单与信用融资','境外利率汇率联动'],'gaps':['八维覆盖并不表示八维数据已取得；缺项不算资金面温度分','没有跨市场高频序列时不承诺实时资金面判断']}}
def plan(spec):
 if not isinstance(spec,dict):raise ValueError('研究请求须为对象')
 day(spec.get('asOf'));kind=spec.get('kind');subject=spec.get('subject')
 if not isinstance(kind,str) or not isinstance(subject,str) or not subject.strip():raise ValueError('需明确对象类型与研究主体')
 matches=[k for k,v in PROFILES.items() if kind in v['kinds']]
 if len(matches)!=1:raise ValueError('未知研究对象类型，不能猜测路由')
 profile=matches[0];question=spec.get('question','')
 if not isinstance(question,str):raise ValueError('question须为文字')
 for field in ['codes','subjects']:
  values=spec.get(field,[])
  if not isinstance(values,list) or any(not isinstance(v,str) or not v.strip() for v in values):raise ValueError(field+'须为非空文字数组')
  if len(values)!=len(set(values)):raise ValueError(field+'存在重复对象')
 chosen=spec.get('profile')
 if chosen is not None and chosen!=profile:raise ValueError('指定研究模板与对象类型冲突')
 explicit_many=any(len(spec.get(k,[]))>1 for k in ['codes','subjects'])
 screening=bool(re.search(r'筛选|批量',question))
 comparison=bool(re.search(r'多基金|多ETF|两只|多只|比较这|对比这|横向比较|横向对比',question,re.I))
 if explicit_many or screening or comparison:return {'status':'use-existing-multi-object-entry','reference':'query-screen.md' if screening else 'compare-evaluate.md','note':'此请求不强行进入单标的深研'}
 if any(spec.get(k) for k in ['codes','subjects']):return {'status':'needs-identity','profile':profile,'note':'单主体请使用code与subject明确身份，不忽略列表参数'}
 if profile=='fund' and re.search(r'ETF',question,re.I):return {'status':'needs-kind-confirmation','note':'ETF与场外基金身份冲突，请确认产品类型，不猜代码'}
 code=spec.get('code')
 if code is not None and not isinstance(code,str):raise ValueError('code须为文字，不猜测或转换证券身份')
 if profile in ['company','fund','etf','convertible'] and (not isinstance(code,str) or not code.strip()):return {'status':'needs-identity','profile':profile,'note':'先确认市场、证券代码及份额，不按名称猜身份'}
 item=copy.deepcopy(PROFILES[profile])
 return {'status':'planned-not-executed','profile':profile,'title':item['title'],'subject':subject.strip(),'code':code,'asOf':spec['asOf'],'sections':item['sections'],'references':item['references'],'dataGaps':item['gaps'],'dataGapStatus':'capability-limitations-not-subject-acquisition-audit','sectionEvidenceStatus':[{'section':section,'status':'not-acquired-or-reviewed-by-this-planner','nextStep':'确认已有资料及来源、所属日与披露日；缺资料按对应参考入口补取，核验后再建立判断'} for section in item['sections']],'externalInterfaces':{'mx_and_MQL':'not-connected'},'workflow':['身份与时点','取数及覆盖','原文和口径','计算或阅读','自然语言报告','来源与缺口'],'outputContract':'先给发现和依据；事实、解释、假设分开；缺项留空。规划成功不表示研究完成。'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input');p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out)
 if out.exists():raise FileExistsError('输出已存在，请保留旧规划')
 spec=json.loads(Path(a.input).read_text(encoding='utf-8-sig'),object_pairs_hook=unique_pairs,parse_constant=reject_constant);result=plan(spec);out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
