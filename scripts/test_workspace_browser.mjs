// Optional real Chrome smoke test using CDP and synthetic data only.
import {spawn,spawnSync} from 'node:child_process';
import {mkdtemp,mkdir,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
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
 const made=spawnSync(python,['-c',"import sys;from zipfile import ZipFile;z=ZipFile(sys.argv[1],'w');z.writestr('word/document.xml','<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\"><w:body><w:p><w:r><w:t>Example Company</w:t></w:r></w:p><w:p><w:r><w:t>Example reports</w:t></w:r></w:p></w:body></w:document>');z.close()",docx],{windowsHide:true});
 assert.equal(made.status,0);
 const doc2=await call('DOM.getDocument');const upload2=await call('DOM.querySelector',{nodeId:doc2.root.nodeId,selector:'#file'});
 await call('DOM.setFileInputFiles',{nodeId:upload2.nodeId,files:[docx]});await evaluate("document.getElementById('upload').click()");
 for(let i=0;i<100;i++){if(await evaluate("!document.getElementById('mappingSection').hidden && document.getElementById('units').textContent.includes('Example Company')"))break;await pause(100)}
 assert.equal(await evaluate("document.getElementById('mappingSection').hidden"),false);
 await evaluate("document.getElementById('addExperience').click();document.querySelector('#experiences select').value='u1';document.querySelector('#experiences textarea').value='Example Company';[...document.querySelectorAll('#experiences button')].find(b=>b.textContent==='加入公司引用').click()");
 await evaluate("document.querySelectorAll('#experiences select')[3].value='u2';document.querySelectorAll('#experiences textarea')[3].value='Example reports';[...document.querySelectorAll('#experiences button')].find(b=>b.textContent==='加入职责内容引用').click();document.getElementById('reviewed').checked=true;document.getElementById('save').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.querySelectorAll('#facts input').length===1 && document.getElementById('facts').textContent.includes('Example reports')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('facts').textContent.includes('Example reports')"));
 assert.equal(await evaluate("document.querySelectorAll('#facts input:checked').length"),0);
 const market=join(dir,'synthetic-market.json');
 await writeFile(market,JSON.stringify({status:'synthetic-only',targetCompanies:100,companies:[],jobs:[{id:'https://www.zhipin.com/job_detail/synthetic.html',companyKey:null,source:{url:'https://www.zhipin.com/job_detail/synthetic.html',title:'「示例岗位招聘」_示例公司',text:'示例岗位 20-30K\n杭州 3-5年 大专\n感兴趣\n职位描述\n双休\n竞争力分析',capturedAt:'synthetic'}}]}));
 const dom3=await call('DOM.getDocument');const marketNode=await call('DOM.querySelector',{nodeId:dom3.root.nodeId,selector:'#marketFile'});
 await call('DOM.setFileInputFiles',{nodeId:marketNode.nodeId,files:[market]});
 await evaluate("document.getElementById('screenCity').value='杭州';document.getElementById('screenSalary').value='18';document.getElementById('screenWeekend').checked=true;document.getElementById('screenEducation').value='大专';document.getElementById('screenConfirmed').checked=true;document.getElementById('screen').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('marketReport').textContent.includes('值得核实（1）')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('marketReport').textContent.includes('薪资：未确认')"));
 const caseId=await evaluate('current.id');await call('Page.reload');await pause(600);
 await evaluate("document.getElementById('cases').value="+JSON.stringify(caseId)+";document.getElementById('load').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.getElementById('marketReport').textContent.includes('值得核实（1）')"))break;await pause(100)}
 assert.ok(await evaluate("document.getElementById('marketReport').textContent.includes('值得核实（1）')"));
 await call('Page.reload');await pause(500);await evaluate("document.getElementById('load').click()");
 for(let i=0;i<100;i++){if(await evaluate("document.querySelectorAll('#facts input:disabled').length===1"))break;await pause(100)}
 assert.equal(await evaluate("document.querySelectorAll('#facts input:disabled').length"),1);
 assert.equal(await evaluate("document.documentElement.scrollWidth>innerWidth"),false);
 const shot=await call('Page.captureScreenshot',{format:'png'});await writeFile(join(dir,'workspace.png'),Buffer.from(shot.data,'base64'));
 console.log('PASS real Chrome: TXT/DOCX intake review, persistence, explicit-policy prescreen, unknown fixed pay, saved report reload, no horizontal overflow.');
 console.log('Synthetic test artifacts: '+dir);
}finally{if(ws)ws.close();for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('closed'))}browser.kill();server.kill()}
