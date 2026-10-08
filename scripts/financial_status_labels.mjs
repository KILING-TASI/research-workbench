const labels={'supported-inputs-matched':'支持范围内的输入核对一致','supported-inputs-matched-with-comparability-warning':'数值一致，跨期口径待复核','failed':'解析失败','not-attempted':'尚未执行',matched:'核对一致',difference:'数值存在差异',missing:'字段未定位', 'source-missing':'数据源数值缺失', 'period-unconfirmed':'报告期间未确认', 'column-ambiguous':'数值列有歧义', 'unit-unconfirmed':'金额单位未确认',ambiguous:'同名字段有歧义',parsed:'已完成文本解析', 'not-found':'报告未取得', 'parse-failed':'文本解析失败',available:'资料已取得',verified:'已核验', 'not-verified':'尚未核验', 'insufficient':'资料不足'};
export function statusText(value){return labels[value]??'状态尚未完成解释，请核对资料说明';}

export function comparabilityText(part){
 const rows=part.comparabilityWarnings??[];
 if(!Array.isArray(rows))throw Error("跨期口径提醒须为数组");
 return rows.map(w=>{if(!w||typeof w.warning!=="string"||!w.warning.trim()||typeof w.period!=="string"||!Number.isInteger(w.page)||w.page<1)throw Error("跨期口径提醒缺少期间、页码或说明");return w.period+" PDF页 "+w.page+"："+w.warning;}).join("；");
}
