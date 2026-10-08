"""Portable readable HTML for this tool's simple Markdown briefs."""
import html,re
from urllib.parse import urlsplit

def safe_url(value):
 if not isinstance(value,str) or not value or re.search(r'[\s\x00-\x1f\x7f]',value):return False
 try:
  u=urlsplit(value);u.port
  if u.scheme=='https':return bool(u.hostname) and u.username is None and u.password is None
  return not u.scheme and not u.netloc and not value.startswith(('//','\\')) and '\\' not in value and ':' not in value
 except ValueError:return False

def table_cells(line):
 text=line.strip()
 if text.startswith('|'):text=text[1:]
 if text.endswith('|') and not text.endswith('\\|'):text=text[:-1]
 return [cell.strip().replace('\\|','|') for cell in re.split(r'(?<!\\)\|',text)]

def links(text):
 """Simple Markdown destinations with balanced parentheses, never truncated."""
 cursor=0
 while cursor<len(text):
  match=re.search(r'\[([^\]]+)\]\(',text[cursor:])
  if match is None:return
  start=cursor+match.start();dest=cursor+match.end();end=dest;depth=1
  while end<len(text) and depth:
   char=text[end]
   if char.isspace():break
   if char=='(':depth+=1
   elif char==')':depth-=1
   end+=1
  if depth==0:
   yield start,end,match[1],text[dest:end-1]
   cursor=end
  else:cursor=dest

def inline(text):
 def escaped(value):
  # Parse emphasis only inside escaped text, never inside generated link markup.
  return re.sub(r'\*\*([^*\n]+)\*\*',r'<strong>\1</strong>',html.escape(value))
 parts=[];pos=0
 for start,end,label,destination in links(text):
  if not safe_url(destination):continue
  parts.append(escaped(text[pos:start]));parts.append('<a href="'+html.escape(destination,quote=True)+'" target="_blank" rel="noopener noreferrer">'+escaped(label)+'</a>');pos=end
 parts.append(escaped(text[pos:]));return ''.join(parts)
def render(text,title='基金研究简报'):
 lines=text.splitlines();out=[];i=0;in_list=False;sections=[];body_seen=False;table_count=0
 def close_list():
  nonlocal in_list
  if in_list:out.append('</ul>');in_list=False
 while i<len(lines):
  fence=re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$',lines[i])
  if fence and (fence[1][0]!='`' or '`' not in fence[2]):
   # Examples are literal text, not conclusions, headings, links or tables.
   close_list();body_seen=True;marker=fence[1];code=[];i+=1
   while i<len(lines):
    end=re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$',lines[i])
    if end and end[1][0]==marker[0] and len(end[1])>=len(marker) and not end[2].strip():
     i+=1;break
    code.append(lines[i]);i+=1
   out.append('<pre class="example"><code>'+html.escape('\n'.join(code))+'</code></pre>');continue
  line=lines[i].strip()
  if not line:close_list();i+=1;continue
  if re.fullmatch(r'(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,}',line):
   close_list();body_seen=True;out.append('<hr>');i+=1;continue
  if line.startswith('|') and i+1<len(lines) and re.fullmatch(r'\s*\|(?:\s*:?-+:?\s*\|)+\s*',lines[i+1]):
   if len(table_cells(line))!=len(table_cells(lines[i+1])):raise ValueError('报告表头和分隔行列数不一致')
   body_seen=True;close_list();head=table_cells(line);alignment=table_cells(lines[i+1]);table_count+=1
   classes=['align-center' if a.startswith(':') and a.endswith(':') else 'align-right' if a.endswith(':') else '' for a in alignment]
   hint='table-hint-'+str(table_count)
   out.append('<p class="table-hint" id="'+hint+'">表格较宽时可横向滚动；键盘用户可选中表格后用左右方向键查看。</p><div class="table-wrap" tabindex="0" role="region" aria-label="数据表'+str(table_count)+'" aria-describedby="'+hint+'"><table><thead><tr>'+''.join('<th scope="col"'+(' class="'+classes[n]+'"' if classes[n] else '')+'>'+inline(x)+'</th>' for n,x in enumerate(head))+'</tr></thead><tbody>');i+=2
   while i<len(lines) and lines[i].strip().startswith('|'):
    cells=table_cells(lines[i])
    if len(cells)!=len(head):raise ValueError('报告表格列数不一致，停止渲染以免数字错列')
    out.append('<tr>'+''.join('<td'+(' class="'+classes[n]+'"' if classes[n] else '')+'>'+inline(x)+'</td>' for n,x in enumerate(cells))+'</tr>');i+=1
   out.append('</tbody></table></div>');continue
  if line.startswith('- '):
   body_seen=True
   if not in_list:out.append('<ul>');in_list=True
   out.append('<li>'+inline(line[2:])+'</li>');i+=1;continue
  close_list();m=re.match(r'^(#{1,4})\s+(.+)$',line)
  if m:
   if len(m[1])!=1:body_seen=True
   if len(m[1])==2:
    anchor='section-'+str(len(sections)+1);sections.append((anchor,m[2]));out.append('<span class="section-anchor" id="'+anchor+'"></span>')
   out.append('<h'+str(len(m[1]))+'>'+inline(m[2])+'</h'+str(len(m[1]))+'>')
  elif line.startswith('> '):body_seen=True;out.append('<p class="conclusion">'+inline(line[2:])+'</p>')
  elif not body_seen and re.fullmatch(r'\*\*[^\n]+\*\*',line):body_seen=True;out.append('<p class="conclusion">'+inline(line)+'</p>')
  elif line.startswith(('论据（','关键依据：')):body_seen=True;out.append('<p class="evidence">'+inline(line)+'</p>')
  elif line.startswith('https://') and not re.search(r'\s',line) and safe_url(line):body_seen=True;out.append('<p class="source"><a href="'+html.escape(line,quote=True)+'" target="_blank" rel="noopener noreferrer">查看资料来源</a></p>')
  else:body_seen=True;out.append('<p>'+inline(line)+'</p>')
  i+=1
 close_list()
 css='\n:root{--ink:#263449;--muted:#65758b;--blue:#285fc4;--line:#e1e7ef;--paper:#fff;--bg:#f4f6fa}\n*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.85 "Microsoft YaHei UI","PingFang SC",system-ui,sans-serif;-webkit-text-size-adjust:100%}\n.report-layout{max-width:1280px;margin:32px auto;display:grid;grid-template-columns:192px minmax(0,1fr);gap:24px;padding:0 24px}.report-layout.no-nav{grid-template-columns:1fr;max-width:1000px}.report-nav{position:sticky;top:28px;align-self:start;font-size:13px;max-height:calc(100vh - 56px);overflow-y:auto}.nav-title{font-size:12px;letter-spacing:.1em;color:var(--muted);margin:0 0 12px}.report-nav a{display:block;padding:7px 10px;border-left:2px solid transparent;text-decoration:none;color:var(--muted);line-height:1.6}.report-nav a:hover{color:var(--blue);background:#eaf0fa;border-color:var(--blue)}main{min-width:0;background:var(--paper);border:1px solid var(--line);border-radius:14px;padding:34px 40px;box-shadow:0 4px 20px #21345405}\nh1{font-size:28px;line-height:1.45;letter-spacing:-.02em;margin:0 0 20px;color:#17263e}h2{font-size:20px;line-height:1.5;margin:36px 0 14px;padding:0 0 10px;border-bottom:1px solid var(--line)}h3{font-size:16px;line-height:1.6;margin:22px 0 10px}p{margin:10px 0 16px}p,li{overflow-wrap:anywhere}ul{padding-left:22px;margin:12px 0 20px}li{padding:3px 0}a{color:var(--blue);text-underline-offset:3px}a:focus-visible{outline:3px solid #b9cdf2;outline-offset:3px;border-radius:3px}.section-anchor{display:block;scroll-margin-top:20px}.table-wrap{overflow-x:auto;margin:18px 0 24px;border:1px solid var(--line);border-radius:10px}table{border-collapse:collapse;width:100%;font-size:13px;line-height:1.7;font-variant-numeric:tabular-nums}th,td{padding:11px 13px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;overflow-wrap:normal;min-width:90px}th{background:#f0f4fa;color:#52637b;font-weight:600}tbody tr:last-child td{border-bottom:0}tbody tr:nth-child(even){background:#fafbfd}tbody tr:hover{background:#f1f5fb}.source{font-size:12px;color:var(--muted)}main>p:first-of-type:not(.conclusion){color:var(--muted);font-size:14px}\n@media(max-width:960px){.report-layout{grid-template-columns:1fr;max-width:940px;padding:0 20px}.report-nav{position:static;max-height:none;overflow:visible;display:flex;flex-wrap:wrap;gap:4px 8px}.nav-title{width:100%;margin-bottom:2px}.report-nav a{padding:5px 9px;border:1px solid var(--line);border-radius:6px;background:white}main{padding:28px}}\n@media(max-width:600px){.report-layout{margin:14px auto;padding:0 12px;gap:14px}main{padding:22px 18px;border-radius:10px}h1{font-size:23px}h2{font-size:18px;margin-top:28px}body{font-size:14px}.report-nav a{font-size:12px}th,td{padding:9px 10px}table{font-size:12px}}\n@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{@page{size:A4;margin:16mm}body{background:white;font-size:11pt}.report-layout{display:block;margin:0;padding:0;max-width:none}.report-nav{display:none}main{border:0;box-shadow:none;border-radius:0;padding:0}h1{font-size:21pt}h2{font-size:15pt;break-after:avoid}h3{break-after:avoid}thead{display:table-header-group}tr{break-inside:avoid}.table-wrap{overflow:visible;border-radius:0}table{font-size:9pt;table-layout:fixed}th,td{min-width:0;padding:6px;overflow-wrap:anywhere}a{color:inherit}tbody tr:hover{background:inherit}}\n'
 css+='hr{border:0;border-top:1px solid var(--line);margin:26px 0}h4{font-size:14px;font-weight:600;color:var(--muted);margin:26px 0 8px}p.conclusion{font-size:21px;line-height:1.55;font-weight:700;color:#17263e;margin:8px 0 14px;padding:16px 20px;background:#f0f5ff;border-left:4px solid var(--blue);border-radius:0 8px 8px 0}p.evidence{font-size:13px;line-height:1.8;color:#58677b;margin:10px 0 18px}@media(max-width:600px){p.conclusion{font-size:18px;padding:13px 15px}p.evidence{font-size:13px}}@media print{p.conclusion{font-size:14pt;break-inside:avoid}p.evidence{font-size:9pt}h4{break-after:avoid}}'
 css+='pre.example{padding:14px 16px;background:#f5f7fa;border:1px solid var(--line);border-radius:8px;overflow-x:auto;font-size:12px;line-height:1.7;white-space:pre}pre.example code{font-family:Consolas,"Liberation Mono",monospace}@media print{pre.example{white-space:pre-wrap;overflow-wrap:anywhere;font-size:9pt}}'
 css+='th.align-right,td.align-right{text-align:right}th.align-center,td.align-center{text-align:center}.table-wrap:focus-visible{outline:3px solid #b9cdf2;outline-offset:3px}.table-hint{font-size:12px;color:var(--muted);margin:14px 0 4px}.table-hint+.table-wrap{margin-top:4px}@media print{.table-hint{display:none}.table-hint+.table-wrap{margin-top:18px}}'
 nav='<nav class="report-nav" aria-label="报告目录"><p class="nav-title">报告目录</p>'+''.join('<a href="#'+anchor+'">'+html.escape(label)+'</a>' for anchor,label in sections)+'</nav>' if sections else ''
 return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>'+css+'</style></head><body><div class="report-layout'+(' no-nav' if not sections else '')+'">'+nav+'<main>'+''.join(out)+'</main></div></body></html>'
