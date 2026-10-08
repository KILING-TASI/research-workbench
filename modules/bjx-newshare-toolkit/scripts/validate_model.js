// Explicit legacy historical review only; never create first-frozen predictions.
const fs=require('node:fs'),E=require('../assets/engine.js');
const data=JSON.parse(fs.readFileSync(0,'utf8'));
const today=data.fetchedAt.slice(0,10),validation=E.validateModel(data.records,today);
validation.frozenChecks=[];
validation.freezeStatus='not-verified-no-new-captures';
validation.reviewBoundary='历史回放只记录偏差，不作为模型调优或预测能力改善依据；既有档案不认证事前冻结。';
process.stdout.write(JSON.stringify({modelValidation:validation,predictionArchive:data.predictionArchive||[]}));
