// Validate original JSON keys before using parsed research inputs.
'use strict';
function parse(text){
 const raw=text.replace(/^\uFEFF/,'');const result=JSON.parse(raw);let i=0;
 const space=()=>{while(i<raw.length&&/\s/.test(raw[i]))i++;};
 function string(){const begin=i++;while(i<raw.length){if(raw[i]==='\\'){i+=2;continue;}if(raw[i++]==='"')break;}return JSON.parse(raw.slice(begin,i));}
 function value(depth){if(depth>128)throw Error('JSON nesting exceeds 128');space();const ch=raw[i];
  if(ch==='{'){i++;space();const keys=new Set();if(raw[i]==='}'){i++;return;}while(true){space();const key=string();if(keys.has(key))throw Error('Duplicate JSON property: '+key);keys.add(key);space();i++;value(depth+1);space();if(raw[i++]==='}')break;}return;}
  if(ch==='['){i++;space();if(raw[i]===']'){i++;return;}while(true){value(depth+1);space();if(raw[i++]===']')break;}return;}
  if(ch==='"'){string();return;}while(i<raw.length&&!/[\s,}\]]/.test(raw[i]))i++;
 }
 value(0);
 function finite(v){if(typeof v==='number'&&!Number.isFinite(v))throw Error('Non-finite JSON number');if(v&&typeof v==='object')for(const x of Object.values(v))finite(x);}
 finite(result);return result;
}
module.exports={parse};
