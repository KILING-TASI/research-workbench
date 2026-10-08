const assert=require('assert'),{parse}=require('./strict_json.js');
for(const raw of ['{"code":1,"code":2}','{"nested":{"weight":1,"weight":2}}','{"a":1,"\\u0061":2}','{"v":1e999}'])assert.throws(()=>parse(raw));
assert.deepStrictEqual(parse('{"a":"quoted \\"text\\"","items":[{"x":1},{"x":2}],"value":null}'),{a:'quoted "text"',items:[{x:1},{x:2}],value:null});
assert.deepStrictEqual(parse('\uFEFF{"s":"a,b}\\\\c","n":-1.2e-3}'),{s:'a,b}\\c',n:-.0012});
console.log('Strict JSON keys, escaped duplicates, nested objects and finite values passed');
