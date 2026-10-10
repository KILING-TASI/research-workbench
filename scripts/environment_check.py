"""Read-only standalone dependency check; does not install or fetch anything."""
import argparse,datetime as dt,importlib.util,json,shutil,subprocess,sys
from pathlib import Path
from export_runtime import component_environment

ENTRY_CHECKS = {
 'demo': (None, []), 'compare': (None, []), 'news': (None, []), 'snapshot': (None, []),
 'cashflow': (('portfolio','observed_review','review'), []),
 'fund-report-six-column': (('lookthrough','report_adapter','legacy_domestic_result'), ['pdfplumber']),
 'original-schema1': (('financial','original_compat','verify'), ['pdfplumber']),
}

def inspect_entry(entry):
 if entry not in ENTRY_CHECKS:raise ValueError('未登记此具体入口的轻量检查；不要据此判断其他研究不可用')
 interface,components=ENTRY_CHECKS[entry]
 rows=[dict(component='python-runtime',label='Python运行版本',available=sys.version_info >= (3,11),
            features=[entry],status='要求Python 3.11及以上；版本满足不等于研究通过')]
 for name in components:
  try:present=importlib.util.find_spec(name) is not None
  except (ValueError,ImportError):present=False
  rows.append(dict(component=name,label=name,available=present,features=[entry],
                   status='组件可定位，尚未实跑' if present else '此入口需要的组件缺失',
                   installCommand=None if present else 'python -m pip install '+name,
                   nextStep=None if present else '仅按本次入口安装该第三方组件；这不等于安装了专业包'))
 specialist=None
 if interface:
  from specialist_loader import check
  specialist=check(*interface)
  rows.append(dict(component=specialist['provider'],label=specialist['distribution'],
                   available=specialist['available'],features=[entry],status=specialist['message']))
 return dict(checkedAt=dt.datetime.now(dt.timezone.utc).isoformat(),pythonVersion=sys.version.split()[0],
             entry=entry,dependencies=rows,specialistDependency=specialist,
             available=all(row['available'] for row in rows),dataStatus='not-checked',
             limitations=['只检查本次指定入口的软件；缺项不阻断其他研究',
                          '不执行专业代码、不安装、不联网；可定位不等于实际计算通过',
                          '资料来源、日期与缺口尚未检查，不能把资料未知写成缺软件'])

def inspect(node=None,artifact_node_modules=None,entry=None):
 if entry is not None:return inspect_entry(entry)
 config_error=None
 try:export_env=component_environment(artifact_node_modules)
 except ValueError as exc:export_env=None;config_error=str(exc)
 rows=[]
 for name,label,features in [('pdfplumber','PDF文字与表格提取',['报告持仓','原文身份核对','经理任职表','文件费率','存货单元格坐标核验','基金资产负债表提取']),('numpy','矩阵与随机模拟',['有效前沿','最小方差组合','蒙特卡洛']),('xlrd','历史Excel原表解析',['申万股票行业记录XLS']),('openpyxl','Excel工作簿解析与指定导出入口',['申万新版行业代码表XLSX','明确使用openpyxl的导出；不替代财务底稿专用组件']),('pypdf','PDF文档读取',['研究资料库','北交原文提取','存货原文文字核验','报告证据PDF物理页引句验收','FOF关联原件结构检查','基金资产负债表来源结构检查','披露利率情景原页核对','资产池桥接份额与来源核对']),('pypdfium2','PDF页面渲染',['PDF视觉验收']),('docx','Word文档导出',['公司行业DOCX报告']),('pandas','专题数据处理',['ETF项目刷新'])]:
  try:present=importlib.util.find_spec(name) is not None
  except (ValueError,ImportError):present=False
  install_name='python-docx' if name=='docx' else name
  rows.append(dict(component=name,label=label,available=present,features=features,status='依赖可找到，尚未证明实际计算通过' if present else '依赖缺失，相关功能暂不可运行',nextStep=None if present else '仅当本次任务需要时安装；安装后重新检查并实跑对应入口',installCommand=None if present else 'python -m pip install '+install_name))
 node=node or shutil.which('node');version=None;reason=None
 if node:
  try:version=subprocess.run([node,'--version'],capture_output=True,text=True,timeout=5,check=True).stdout.strip()
  except Exception as exc:reason=type(exc).__name__+': '+str(exc)
 if version:
  try:
   if int(version.lstrip('v').split('.')[0])<20:reason='要求Node.js 20及以上'
  except ValueError:reason='无法确认Node.js版本'
 elif node and not reason:
  reason='Node.js未返回版本，运行时尚未确认'
 rows.append(dict(component='node',label='JavaScript计算入口',available=bool(node) and not reason,version=version,features=['基金比较','费用与组合JavaScript工具'],status=reason or ('运行时可调用' if node else '运行时缺失')))
 artifact=False;artifact_reason='财务Excel组件配置无效：'+config_error if config_error else 'Node运行时不可调用，未检查财务Excel导出组件'
 if node and not reason and export_env is not None:
  try:
   probe="const {createRequire}=require('node:module');const r=createRequire(process.cwd()+'/__dependency_probe__.js');try{r.resolve('@oai/artifact-tool',{paths:process.env.ARTIFACT_NODE_MODULES?[process.env.ARTIFACT_NODE_MODULES]:[process.cwd()]});process.stdout.write(JSON.stringify({found:true}));}catch{process.stdout.write(JSON.stringify({found:false}));}"
   checked=subprocess.run([node,'-e',probe],capture_output=True,text=True,timeout=5,check=True,env=export_env)
   data=json.loads(checked.stdout)
   if not isinstance(data,dict) or type(data.get('found')) is not bool:raise ValueError('组件检查返回格式无效')
   artifact=data['found'];artifact_reason='导出组件可定位，尚未验证加载、公式计算或排版' if artifact else '财务Excel导出组件缺失；HTML和JSON研究不受影响'
  except Exception as exc:artifact_reason='财务Excel导出组件未确认：'+type(exc).__name__+': '+str(exc)
 rows.append(dict(component='@oai/artifact-tool',label='财务Excel导出组件',available=artifact,features=['财务分析Excel底稿'],status=artifact_reason))
 rows.append(dict(component='python-runtime',label='Python运行版本',available=sys.version_info >= (3,11),features=['全部Python入口'],status='要求Python 3.11及以上；版本满足不等于业务验收'))
 rows.append(dict(component='ppt-font',label='PPT字体',available=False,features=['PPT排版'],status='需显式指定fontFamily并在目标环境确认字体、视觉验收；内置OCR不提供'))
 return dict(checkedAt=dt.datetime.now(dt.timezone.utc).isoformat(),pythonVersion=sys.version.split()[0],dependencies=rows,standardLibraryRoutes=['名称候选目录','基金公开文件目录','港美股价格历史','基金净值与条件筛选'],limitations=['仅检查当前环境，不证明数据来源可访问或标的完整覆盖','不安装组件、不修改环境、不发起网络请求','组件可找到不代表PDF版式、模型或业务验收通过','工作台及作者项目数据库不属于独立运行依赖'])

def markdown(r):
 lines=['# 独立运行环境检查','', 'Python '+r['pythonVersion'],
        '仅检查入口 '+r['entry']+'；资料状态未核，不影响其他入口。' if r.get('entry') else '基础取数、目录与历史筛选使用Python标准库；网络可用性尚未检查。','']
 for row in r['dependencies']:
  lines.append('- '+row['label']+'：'+row['status']+'。涉及：'+'、'.join(row['features'])+'。')
  if row.get('installCommand'):lines.append('  按需安装：`'+row['installCommand']+'`。'+row['nextStep']+'。')
 if r.get('specialistDependency'):lines+=['']+r['specialistDependency']['nextSteps']
 lines+=['']+r['limitations'];return '\n'.join(lines)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--node');p.add_argument('--artifact-node-modules');p.add_argument('--entry',choices=sorted(ENTRY_CHECKS));a=p.parse_args()
 if a.out.exists() or a.out.with_suffix('.md').exists():raise FileExistsError('输出已存在')
 r=inspect(a.node,a.artifact_node_modules,a.entry);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');a.out.with_suffix('.md').write_text(markdown(r),encoding='utf-8')
