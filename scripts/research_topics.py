"""Dispatch bundled independent topics in isolated subprocesses; no external skills."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ROUTES={
 'bjx':('bjx-newshare-toolkit',{'research':'issuance_research.py','facts':'issuance_facts.py','evidence':'research_evidence.py','company':'company_research.py','review':'prediction_review.py','scenarios':'subscription_scenarios.py','annual':'annual_yield.py','cash-ledger':'cash_repo_ledger.py','standalone':'standalone.py'}),
 'macro':('macro-indicator',{'standalone':'standalone.py'}),
 'etf':('etf-sector-rotation',{'standalone':'standalone.py','replacement':'replacement_research.py','stress':'portfolio_stress.py'})}
def resolve(topic,action):
 if topic not in ROUTES or action not in ROUTES[topic][1]:raise ValueError('未接通的专题或动作；请查看 --list')
 module,actions=ROUTES[topic];path=ROOT/'modules'/module/'scripts'/actions[action]
 if not path.is_file():raise ValueError('主包专题脚本缺失：'+str(path))
 return path

def main(argv=None):
 p=argparse.ArgumentParser(description='主Skill内置专题入口；参数转交专题脚本，不联网刷新除非显式请求')
 p.add_argument('--timeout',type=int,default=600);p.add_argument('--list',action='store_true');p.add_argument('topic',nargs='?');p.add_argument('action',nargs='?');p.add_argument('args',nargs=argparse.REMAINDER);a=p.parse_args(argv)
 if not 1<=a.timeout<=3600:p.error('--timeout须为1..3600秒')
 if a.list:
  mapping={t:{k:str((ROOT/'modules'/m/'scripts'/v).relative_to(ROOT)) for k,v in actions.items()} for t,(m,actions) in ROUTES.items()}
  mapping['etf'].update({'rotation-review':'scripts/etf_rotation_bridge.py review','rotation-backtest':'scripts/etf_rotation_bridge.py backtest'})
  print(json.dumps(mapping,ensure_ascii=False,indent=2));return 0
 if a.topic=='etf' and a.action in ('rotation-review','rotation-backtest'):
  forwarded=a.args[1:] if a.args[:1]==['--'] else a.args
  try:return subprocess.run([sys.executable,str(ROOT/'scripts/etf_rotation_bridge.py'),'review' if a.action=='rotation-review' else 'backtest',*forwarded],timeout=a.timeout).returncode
  except (subprocess.TimeoutExpired,OSError) as exc:
   print('ETF专业入口未完成：'+str(exc),file=sys.stderr);return 2
 try:path=resolve(a.topic,a.action)
 except ValueError as exc:p.error(str(exc))
 forwarded=a.args[1:] if a.args[:1]==['--'] else a.args
 # Child module imports remain isolated from similarly named main modules.
 # Retain caller cwd so user's relative input/output paths retain their meaning.
 if not 1<=a.timeout<=3600:p.error('--timeout须为1..3600秒')
 try:return subprocess.run([sys.executable,str(path),*forwarded],check=False,timeout=a.timeout).returncode
 except (subprocess.TimeoutExpired,OSError) as exc:
  print(json.dumps({'status':'blocked','stage':'topic','error':type(exc).__name__,'message':'专题超时或无法启动；已保留此前输出，请核对后重试'},ensure_ascii=False),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
