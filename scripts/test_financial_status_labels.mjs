import assert from 'node:assert/strict';
import {statusText,comparabilityText} from './financial_status_labels.mjs';
for(const s of ['matched','difference','missing','source-missing','period-unconfirmed','column-ambiguous','unit-unconfirmed','ambiguous','parsed','not-found','parse-failed']){assert.ok(statusText(s));assert.ok(!statusText(s).includes(s));}
assert.match(statusText('unrecognised'),/尚未完成解释/);
console.log('财务状态中文说明检查通过');

assert.equal(comparabilityText({comparabilityWarnings:[]}),"");
assert.match(comparabilityText({comparabilityWarnings:[{period:"2025-06-30",page:9,warning:"比较列调整前后不同"}]}),/2025-06-30 PDF页 9：比较列调整前后不同/);
assert.throws(()=>comparabilityText({comparabilityWarnings:[{period:"2025-06-30",page:0,warning:"提醒"}]}));
