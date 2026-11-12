// Optional real Chrome smoke test using CDP and synthetic data only.
import {spawn,spawnSync} from 'node:child_process';
import {mkdtemp,mkdir,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../',import.meta.url));
const parent=join(root,'data/test-tmp');await mkdir(parent,{recursive:true});
const dir=await mkdtemp(join(parent,'browser workspace '));
const python=process.env.DAGONGREN_TEST_PYTHON||'python';
const chrome=process.env.DAGONGREN_TEST_CHROME;
if(!chrome)throw Error('Set DAGONGREN_TEST_CHROME to installed Chrome executable');
const server=spawn(python,[join(root,'scripts/desktop_launcher.py'),'--workspace','--no-browser','--data',join(dir,'private')],{cwd:root,windowsHide:true,stdio:['ignore','pipe','pipe']});
const url=await new Promise((res,rej)=>{let s='';const timer=setTimeout(()=>rej(Error('server timeout')),15000);server.stdout.on('data',b=>{s+=b;const m=s.match(/http:\/\/127\.0\.0\.1:\d+/);if(m){clearTimeout(timer);res(m[0])}});server.on('exit',()=>{clearTimeout(timer);rej(Error('server exited'))})});
const browser=spawn(chrome,['--headless=new','--remote-debugging-port=0','--user-data-dir='+join(dir,'chrome'),'--no-first-run','--no-default-browser-check','about:blank'],{windowsHide:true,stdio:'ignore'});
let ws;const pending=new Map();let seq=0;
const pause=ms=>new Promise(r=>setTimeout(r,ms));
try{
 let port;
 for(let i=0;i<100;i++){try{port=Number((await readFile(join(dir,'chrome/DevToolsActivePort'),'utf8')).split('\n')[0]);break}catch{}await pause(100)}
 assert.ok(port,'Chrome CDP started');
 const tabs=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
 ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);
 await new Promise((res,rej)=>{ws.onopen=res;ws.onerror=rej});
 ws.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}};
 function call(method,params={}){return new Promise((resolve,reject)=>{let id=++seq;const timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP timeout'))},15000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}))})}
 async function evaluate(expression){const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error('Browser expression failed');return r.result.value}
 await call('Page.navigate',{url});
 for(let i=0;i<50;i++){if(await evaluate("!!document.getElementById('file')"))break;await pause(100)}
 const file=join(dir,'synthetic.txt');await writeFile(file,'示例任务一\n示例任务二');
 await call('DOM.enable');const dom=await call('DOM.getDocument');const node=await call('DOM.querySelector',{nodeId:dom.root.nodeId,selector:'#file'});
 await call('DOM.setFileInputFiles',{nodeId:node.nodeId,files:[file]});
 await evaluate("document.getElementById('must').value='双休';document.getElementById('upload').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.querySelectorAll('#facts input').length===2"))break;await pause(100)}
 assert.equal(await evaluate("document.querySelectorAll('#facts input').length"),2);
 assert.equal(await evaluate("document.querySelectorAll('#facts input:checked').length"),0);
 await evaluate("document.getElementById('reviewed').checked=true;document.getElementById('save').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('version').textContent.includes('版本 2')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('version').textContent.includes('版本 2')"));
 await evaluate("document.querySelector('#facts input').checked=true;document.getElementById('confirm').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.querySelectorAll('#facts input:disabled').length===1"))break;await pause(100)}
 assert.equal(await evaluate("document.querySelectorAll('#facts input:disabled').length"),1);
 const docx=join(dir,'synthetic.docx');
 const made=spawnSync(python,['-c',"import sys;from zipfile import ZipFile;z=ZipFile(sys.argv[1],'w');z.writestr('word/document.xml','<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body><w:p><w:r><w:t>Example Company</w:t></w:r></w:p><w:p><w:r><w:t>Example reports 自动化</w:t></w:r></w:p></w:body></w:document>');z.close()",docx],{windowsHide:true});
 assert.equal(made.status,0);
 const doc2=await call('DOM.getDocument');const upload2=await call('DOM.querySelector',{nodeId:doc2.root.nodeId,selector:'#file'});
 await call('DOM.setFileInputFiles',{nodeId:upload2.nodeId,files:[docx]});await evaluate("document.getElementById('upload').click()");
 for(let i=0;i<100;i++){if(await evaluate("!document.getElementById('mappingSection').hidden && document.getElementById('units').textContent.includes('Example Company')"))break;await pause(100)}
 assert.equal(await evaluate("document.getElementById('mappingSection').hidden"),false);
 await evaluate("document.getElementById('addExperience').click();document.querySelector('#experiences select').value='u1';document.querySelector('#experiences textarea').value='Example Company';[...document.querySelectorAll('#experiences button')].find(b=>b.textContent==='加入公司引用').click()");
 await evaluate("document.querySelectorAll('#experiences select')[3].value='u2';document.querySelectorAll('#experiences textarea')[3].value='Example reports 自动化';[...document.querySelectorAll('#experiences button')].find(b=>b.textContent==='加入职责内容引用').click();document.getElementById('reviewed').checked=true;document.getElementById('save').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.querySelectorAll('#facts input').length===1 && document.getElementById('facts').textContent.includes('Example reports')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('facts').textContent.includes('Example reports')"));
 assert.equal(await evaluate("document.querySelectorAll('#facts input:checked').length"),0);
 const market=join(dir,'synthetic-market.json');
 await writeFile(market,JSON.stringify({status:'synthetic-only',targetCompanies:100,companies:[{id:'/gongsi/synthetic.html',source:{url:'https://www.zhipin.com/gongsi/synthetic.html',title:'示例公司',text:'公司简介\n示例公司'}}],jobs:[{id:'https://www.zhipin.com/job_detail/synthetic.html',companyKey:'/gongsi/synthetic.html',source:{url:'https://www.zhipin.com/job_detail/synthetic.html',title:'「示例岗位招聘」_示例公司',text:'示例岗位 20-30K\n杭州 3-5年 大专\n感兴趣\n职位描述\n负责Example reports及自动化报表整理\n双休\n竞争力分析',capturedAt:'synthetic'}}]}));
 const dom3=await call('DOM.getDocument');const marketNode=await call('DOM.querySelector',{nodeId:dom3.root.nodeId,selector:'#marketFile'});
 await call('DOM.setFileInputFiles',{nodeId:marketNode.nodeId,files:[market]});
 await evaluate("document.getElementById('screenCity').value='杭州';document.getElementById('screenSalary').value='18';document.getElementById('screenWeekend').checked=true;document.getElementById('screenEducation').value='大专';document.getElementById('screenConfirmed').checked=true;document.getElementById('screen').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('marketReport').textContent.includes('值得核实（1）')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('marketReport').textContent.includes('薪资：未确认')"));
 const caseId=await evaluate('current.id');await call('Page.reload');await pause(600);
 await evaluate("document.getElementById('cases').value="+JSON.stringify(caseId)+";document.getElementById('load').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('marketReport').textContent.includes('值得核实（1）')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('marketReport').textContent.includes('值得核实（1）')"));
 await evaluate("document.getElementById('generateAbility').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.querySelectorAll('.abilityDecision').length===1"))break;await pause(100)}
 assert.equal(await evaluate("document.querySelector('.abilityDecision').value"),'unreviewed');
 assert.equal(await evaluate("document.querySelector('.abilityFacts option').disabled"),true);
 await evaluate("document.querySelector('#facts input').checked=true;document.getElementById('confirm').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('abilityStatus').textContent.includes('证据已变化')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('saveAbility').disabled"));
 await evaluate("document.getElementById('generateAbility').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.querySelector('.abilityFacts option')?.disabled===false && !document.getElementById('saveAbility').disabled"))break;await pause(100)}
 await evaluate("document.querySelector('.abilityDecision').value='supported';document.querySelector('.abilityFacts option').selected=true;document.querySelector('.abilityReason').value='合成用例：任务原文有交集，仅验证人工复核保存流程';document.getElementById('abilityConfirmed').checked=true;document.getElementById('saveAbility').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('abilityStatus').textContent.includes('已人工复核')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('abilityStatus').textContent.includes('已人工复核')"));
 assert.equal(await evaluate("document.querySelectorAll('#abilityDirections select').length"),1);
 await evaluate("document.querySelector('#abilityDirections select').value='not-want';document.getElementById('saveDirections').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('status').textContent.includes('不自动更改长期画像')"))break;await pause(100)}
 assert.equal(await evaluate("current.abilityReport.feedbackScope"),'current-report-only-not-long-term-profile');
 await call('Page.reload');await pause(500);await evaluate("document.getElementById('cases').value="+JSON.stringify(caseId)+";document.getElementById('load').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.querySelectorAll('#facts input:disabled').length===1"))break;await pause(100)}
 assert.equal(await evaluate("document.querySelectorAll('#facts input:disabled').length"),1);
 assert.equal(await evaluate("document.getElementById('researchCompany').options.length"),1);
 await evaluate("document.getElementById('companyContext').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('companyText').textContent.includes('示例公司')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('companyText').textContent.includes('示例公司')"));
 await evaluate("document.getElementById('captureFinance').click()");
 for(let i=0;i<100;i++){if(await evaluate("current.researchReport?.companyGrowth==='unknown'"))break;await pause(100)}
 assert.equal(await evaluate("current.researchReport.automaticScore"),null);
 await call('Page.reload');await pause(500);await evaluate("document.getElementById('cases').value="+JSON.stringify(caseId)+";document.getElementById('load').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('researchStatus').textContent.includes('未上市或身份待核实')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('researchStatus').textContent.includes('未上市或身份待核实')"));
 assert.equal(await evaluate("document.documentElement.scrollWidth>innerWidth"),false);
 const shot=await call('Page.captureScreenshot',{format:'png'});await writeFile(join(dir,'workspace.png'),Buffer.from(shot.data,'base64'));
 await evaluate("document.getElementById('researchMode').value='official';document.getElementById('researchMode').dispatchEvent(new Event('change'));document.getElementById('captureFinance').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('status').textContent.includes('确认官方请求')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('status').textContent.includes('确认官方请求')"));
 assert.equal(await evaluate("current.researchReports.length"),1);
 await evaluate("document.getElementById('researchMode').value='unknown';document.getElementById('researchMode').dispatchEvent(new Event('change'));document.getElementById('researchCompany').scrollIntoView()");
 const financeShot=await call('Page.captureScreenshot',{format:'png'});await writeFile(join(dir,'company-research.png'),Buffer.from(financeShot.data,'base64'));

 await evaluate("document.getElementById('generateResult').click()");
 for(let i=0;i<100;i++){if(await evaluate("current.resultReport?.jobs.length===1"))break;await pause(100)}
 assert.equal(await evaluate("current.resultSummary.counts.preferred"),0);
 assert.equal(await evaluate("current.resultReport.coverage.actualCompanies"),1);
 assert.ok(await evaluate("document.getElementById('resultRows').textContent.includes('示例公司')"));
 await evaluate("document.querySelector('#resultRows select').value='reserve';document.querySelector('#resultRows textarea').value='合成测试：任务相交，固定薪资待确认';[...document.querySelectorAll('#resultRows button')].find(b=>b.textContent==='确认并保存本轮选择').click()");
 for(let i=0;i<100;i++){if(await evaluate("current.resultSummary.counts.reserve===1"))break;await pause(100)}
 assert.equal(await evaluate("current.resultSummary.counts.reserve"),1);
 await call('Page.reload');await pause(500);await evaluate("document.getElementById('cases').value="+JSON.stringify(caseId)+";document.getElementById('load').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.querySelector('#resultRows select')?.value==='reserve'"))break;await pause(100)}
 assert.equal(await evaluate("document.querySelector('#resultRows select').value"),'reserve');
 await evaluate("document.querySelector('#actionChoices input[value=\"favorite-manual\"]').checked=true;document.getElementById('authorizeActions').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('status').textContent.includes('动作范围')"))break;await pause(100)}
 assert.equal(await evaluate("current.actionTasks.length"),0);
 await evaluate("document.getElementById('actionAuthorizationConfirmed').checked=true;document.getElementById('authorizeActions').click()");
 for(let i=0;i<100;i++){if(await evaluate("current.actionTasks.length===1"))break;await pause(100)}
 assert.equal(await evaluate("current.actionTasks[0].state"),'authorized');assert.equal(await evaluate("current.actionTasks[0].systemExecuted"),false);
 const observationData=JSON.parse(await readFile(market,'utf8'));
 function observeFixture(collected){const j=structuredClone(observationData.jobs[0]),company=structuredClone(observationData.companies[0]);j.source.capturedAt=company.source.capturedAt=new Date().toISOString();j.source.text=j.source.text.replace('感兴趣',(collected?'已收藏':'收藏')+'\n感兴趣');return {schemaVersion:1,kind:'read-only-job-observation',job:j,company,controls:{favorite:collected?'collected':'not-collected',labels:[collected?'已收藏':'收藏'],basis:'exact-label-in-job-header-only'}}}
 const observationFile=join(dir,'synthetic-observation.json');await writeFile(observationFile,JSON.stringify(observeFixture(false)));
 async function uploadObservation(){const dom=await call('DOM.getDocument'),node=await call('DOM.querySelector',{nodeId:dom.root.nodeId,selector:'#actionObservation'});await call('DOM.setFileInputFiles',{nodeId:node.nodeId,files:[observationFile]})}
 await uploadObservation();await evaluate("document.getElementById('actionObservationReviewed').checked=true;[...document.querySelectorAll('#actionTasks button')].find(b=>b.textContent==='导入刷新并开始人工接管').click()");
 for(let i=0;i<100;i++){if(await evaluate("current.actionTasks[0].state==='awaiting-user-action'"))break;await pause(100)}
 assert.equal(await evaluate("current.actionTasks[0].state"),'awaiting-user-action');
 await pause(30);await writeFile(observationFile,JSON.stringify(observeFixture(true)));await uploadObservation();
 await evaluate("document.getElementById('actionObservationReviewed').checked=true;[...document.querySelectorAll('#actionTasks button')].find(b=>b.textContent==='导入操作后新观察').click()");
 for(let i=0;i<100;i++){if(await evaluate("current.actionTasks[0].state==='observed-favorite'"))break;await pause(100)}
 assert.equal(await evaluate("current.actionTasks[0].state"),'observed-favorite');assert.equal(await evaluate("current.actionTasks[0].messageSent"),'not-verified');
 await call('Page.reload');await pause(500);await evaluate("document.getElementById('cases').value="+JSON.stringify(caseId)+";document.getElementById('load').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('actionTasks').textContent.includes('已观察到平台收藏状态')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('actionTasks').textContent.includes('非本系统点击')"));
 await evaluate("document.querySelector('#actionTasks section').scrollIntoView()");
 const actionShot=await call('Page.captureScreenshot',{format:'png'});await writeFile(join(dir,'action-ledger.png'),Buffer.from(actionShot.data,'base64'));
 const downloadDir=join(dir,'downloads');await mkdir(downloadDir);await call('Browser.setDownloadBehavior',{behavior:'allow',downloadPath:downloadDir});
 await evaluate("document.getElementById('exportResultJson').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('status').textContent.includes('私人导出范围')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('status').textContent.includes('私人导出范围')"));
 await evaluate("document.getElementById('privateExportConfirmed').checked=true;document.getElementById('exportResultJson').click()");
 let exported;
 for(let i=0;i<100;i++){try{exported=JSON.parse(await readFile(join(downloadDir,'private-job-report.json'),'utf8'));break}catch{}await pause(100)}
 assert.equal(exported.jobs[0].selection.bucket,'reserve');assert.equal(exported.totalScore,null);
 assert.equal(exported.actionObservations[0].systemExecuted,false);assert.equal(exported.actionObservations[0].messageSent,'not-verified');
 await evaluate("document.getElementById('exportResultHtml').click()");
 let exportedHtml;
 for(let i=0;i<100;i++){try{exportedHtml=await readFile(join(downloadDir,'private-job-report.html'),'utf8');break}catch{}await pause(100)}
 assert.ok(exportedHtml.includes('该强调的真实经历'));assert.ok(exportedHtml.includes('Example reports'));
 await evaluate("document.getElementById('resultsSection').scrollIntoView()");
 const resultShot=await call('Page.captureScreenshot',{format:'png'});await writeFile(join(dir,'result-workspace.png'),Buffer.from(resultShot.data,'base64'));
 await evaluate("document.getElementById('generateAbility').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('exportResultJson').disabled"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('exportResultJson').disabled"));
 await call('Page.navigate',{url:pathToFileURL(join(downloadDir,'private-job-report.html')).href});await pause(500);
 assert.equal(await evaluate("document.querySelectorAll('article').length"),1);
 assert.equal(await evaluate("document.documentElement.scrollWidth>innerWidth"),false);
 const exportShot=await call('Page.captureScreenshot',{format:'png'});await writeFile(join(dir,'result-export.png'),Buffer.from(exportShot.data,'base64'));
 console.log('PASS real Chrome: resume/market/review, result selection, scoped manual authorization/observations/reload, no system-execution claim, private JSON/HTML downloads and stale-result blocking.');
 console.log('Synthetic test artifacts: '+dir);
}finally{if(ws)ws.close();for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('closed'))}browser.kill();server.kill()}
