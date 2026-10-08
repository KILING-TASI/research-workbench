"""Build dated, fixed-cohort ETF share tracking from official SSE observations."""
from pathlib import Path
import json,re
ROOT=Path(__file__).resolve().parents[1]
RULES=[('货币',r'货币|现金|日利|添富快线'),('债券',r'债|信用|国开'),('黄金商品',r'黄金|商品|豆粕'),('海外港股',r'港股|恒生|纳指|纳斯达克|标普|日经|德国|法国|美国|海外|全球|道琼斯'),('半导体',r'半导体|芯片|集成电路'),('医药医疗',r'医药|医疗|创新药|生物|疫苗'),('新能源',r'新能源|光伏|电池|锂|储能|风电|碳中和'),('工业制造',r'制造|机械|机器人|汽车|军工|国防|装备'),('资源能源',r'能源|煤炭|石油|有色|矿|钢铁|化工|材料'),('金融',r'银行|证券|券商|金融|保险'),('消费',r'消费|食品|饮料|酒|家电|农业|旅游|养殖'),('科技',r'科技|信息|软件|计算机|通信|人工智能|AI|数据|云计算'),('红利价值',r'红利|股息|价值|低波'),('科创',r'科创|双创'),('宽基',r'沪深300|300ETF|中证500|500ETF|1000ETF|2000ETF|A500|A50|上证50|50ETF|180ETF|创业板|深100|深证100|国证2000')]
def classify(name):
 return next((category for category,pattern in RULES if re.search(pattern,name)),'其他/未识别')
def build(write=True):
 path=ROOT/'assets/market-official.json';d=json.loads(path.read_text(encoding='utf8'))
 latest=max((r['asOf'] for r in d['rows'] if r.get('asOf')),default=None)
 if latest is None:return
 current={r['code']:r for r in d['rows'] if r.get('asOf')==latest and r['exchange']=='上交所'}
 observations={latest:{code:r['shares'] for code,r in current.items()}}
 for b in d.get('periodBaselines',{}).values():
  date=b.get('baselineDate')
  if date and date<latest and b.get('rows'):observations[date]={r['code']:r['shares'] for r in b['rows']}
 cohort=set(current)
 for rows in observations.values():cohort.intersection_update(rows)
 records={};categories={}
 for date,rows in sorted(observations.items()):
  aggregated={}
  for code in sorted(cohort):
   category=classify(current[code]['name']);categories[category]=category
   rec=aggregated.setdefault(category,{'shares':0,'count':0})
   rec['shares']+=rows[code]/1e8;rec['count']+=1
  for rec in aggregated.values():rec['shares']=round(rec['shares'],4)
  records[date]=aggregated
 out={'source':'https://www.sse.com.cn/assortment/fund/etf/list/scale/','retrievedAt':d['retrievedAt'],'records':records,'categories':categories,'cohortSize':len(cohort),'latestProducts':len(current),'coverage':'上交所固定产品观察池；深交所缺少所属日及历史，暂不纳入','verified':True,'note':'交易所份额按当前产品简称分组，每只产品只归入一个类别；各日固定相同代码集合，排除新成立及任一观测缺失的产品，分类不代表官方跟踪指数认定。'}
 if write:(ROOT/'assets/market-data.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
 return out
if __name__=='__main__':
 d=build();print(json.dumps({'latest':max(d['records']),'categories':len(d['categories']),'cohort':d['cohortSize'],'observations':len(d['records'])},ensure_ascii=True))
