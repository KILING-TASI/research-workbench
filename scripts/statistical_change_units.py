"""Interpret prepared statistical tokens using explicitly supplied source legends."""
import argparse,hashlib,json,re
from decimal import Decimal
from pathlib import Path
KINDS=('percent','absolute','percentage-point')
def interpret(token,value_unit,legend,default_kind):
 if not isinstance(legend,dict) or any(not isinstance(k,str) or not k or v not in KINDS for k,v in legend.items()):raise ValueError('需明确原文符号与变动口径')
 if default_kind not in KINDS:raise ValueError('需明确无标记列的原文口径')
 if not isinstance(value_unit,str) or not value_unit.strip():raise ValueError('需指标原始单位')
 if token is None or token in ('','-','—'):return dict(raw=token,value=None,changeType=None,changeUnit=None,status='missing')
 if not isinstance(token,str):raise ValueError('变动原文须字符串')
 text=token.strip();marker=None
 for mark in sorted(legend,key=len,reverse=True):
  if text.endswith(mark):marker=mark;text=text[:-len(mark)].strip();break
 text=text.replace('−','-')
 if not re.fullmatch(r'[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?',text):raise ValueError('数值或标记存在歧义，不自动删除未知符号')
 number=Decimal(text.replace(',',''));kind=legend[marker] if marker else default_kind
 return dict(raw=token,value=str(number),marker=marker,changeType=kind,changeUnit=value_unit if kind=='absolute' else '%' if kind=='percent' else '百分点',status='interpreted-from-declared-legend')
def build(spec):
 p=Path(spec['sourceFile']);digest=hashlib.sha256(p.read_bytes()).hexdigest()
 if digest!=spec['sourceSha256']:raise ValueError('来源版本变化')
 if not isinstance(spec.get('legendLocator'),str) or not spec['legendLocator'].strip():raise ValueError('需表头与脚注原文位置')
 rows=[];seen=set()
 for item in spec['rows']:
  name=item.get('name')
  if not isinstance(name,str) or not name.strip() or name in seen:raise ValueError('指标名称为空或重复')
  seen.add(name)
  if not isinstance(item.get('locator'),str) or not item['locator'].strip():raise ValueError('需所选指标原文位置')
  rows.append(dict(name=name,locator=item['locator'],change=interpret(item['changeToken'],item['valueUnit'],spec['legend'],spec['defaultChangeKind'])))
 if not rows:raise ValueError('需所选指标')
 return dict(rows=rows,sourceFile=str(p.resolve()),sourceSha256=digest,legendLocator=spec['legendLocator'],legend=spec['legend'],defaultChangeKind=spec['defaultChangeKind'],originalTokensAutomaticallyVerified=False,scope='按已核读输入解释符号，不提供OCR或认证原文语义；绝对量、百分点和百分比不能互换，不生成因果判断。')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('input',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();spec=json.loads(a.input.read_text(encoding='utf-8-sig'));source=Path(spec['sourceFile']);spec['sourceFile']=str(source if source.is_absolute() else a.input.resolve().parent/source);result=build(spec);a.out.parent.mkdir(parents=True,exist_ok=True)
 with a.out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
