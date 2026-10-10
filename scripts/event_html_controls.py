"""Local display controls only; do not recompute or mutate frozen results."""
from html import escape

def table(headers,rows):
    head=''.join('<th scope="col">'+escape(x)+'</th>' for x in headers)
    body=''.join('<tr data-order="'+str(i)+'"><td>'+('</td><td>'.join(escape(str(x)) for x in row))+'</td></tr>' for i,row in enumerate(rows))
    return '<section><label>筛选当前结果 <input id="result-filter" type="search" placeholder="输入名称、状态或期间"></label> <label>排序 <select id="result-sort"><option value="original">原顺序</option><option value="name">首列名称</option></select></label><p id="result-count" aria-live="polite"></p><p>仅筛选、排序本页已保存结果，不重新计算，不更换研究情景，也不改变总量与未知部分。</p><div style="overflow:auto"><table id="result-table"><thead><tr>'+head+'</tr></thead><tbody>'+body+'</tbody></table></div></section>'+SCRIPT

SCRIPT="<script>\n(()=>{const q=document.getElementById('result-filter'),s=document.getElementById('result-sort'),t=document.querySelector('#result-table tbody'),rows=Array.from(t.rows);function update(){let count=0;rows.sort((a,b)=>s.value==='name'?a.cells[0].textContent.localeCompare(b.cells[0].textContent,'zh-CN'):Number(a.dataset.order)-Number(b.dataset.order));for(const row of rows){row.hidden=!row.textContent.toLowerCase().includes(q.value.trim().toLowerCase());if(!row.hidden)count++;t.appendChild(row);}document.getElementById('result-count').textContent='显示 '+count+' / '+rows.length+' 条';}q.addEventListener('input',update);s.addEventListener('change',update);update();})();\n</script>"
