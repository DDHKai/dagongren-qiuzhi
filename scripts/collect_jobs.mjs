// Generic, bounded UI navigation through an existing isolated Chrome session.
import {readFile,writeFile,mkdir,rename} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {validateConfig,checkpoint,ensureResume,checkPage,companyLink,addJob,canonicalJob} from './job_collector_core.mjs';
import {snapshotExpression} from './job_collector_dom.mjs';
const args=process.argv.slice(2),options={};for(let i=0;i<args.length;i+=2){if(!['--config','--output','--endpoint','--tab-id'].includes(args[i])||!args[i+1])throw Error('Usage: --config JSON --output PRIVATE_DIR [--endpoint http://127.0.0.1:PORT] [--tab-id ID]');options[args[i]]=args[i+1]}
if(!options['--config']||!options['--output'])throw Error('CONFIG_AND_OUTPUT_REQUIRED');
const cfg=validateConfig(JSON.parse((await readFile(options['--config'],'utf8')).replace(/^\uFEFF/,'')));
const endpoint=new URL(options['--endpoint']||'http://127.0.0.1:9333');
if(endpoint.protocol!=='http:'||endpoint.hostname!=='127.0.0.1'||endpoint.username||endpoint.password||endpoint.pathname!=='/')throw Error('LOCAL_ENDPOINT_ONLY');
const dir=resolve(options['--output']);await mkdir(dir,{recursive:true});const file=join(dir,'checkpoint.json');
let saved;try{saved=ensureResume(JSON.parse(await readFile(file,'utf8')),cfg)}catch(e){if(e.code==='ENOENT')saved=checkpoint(cfg);else throw e}
async function save(){await writeFile(file+'.tmp',JSON.stringify(saved,null,2));await rename(file+'.tmp',file)}
let tabs;
try{tabs=await(await fetch(new URL('/json/list',endpoint),{signal:AbortSignal.timeout(5000)})).json()}
catch{saved.status='needs-local-isolated-chrome';await save();throw Error('LOCAL_CHROME_UNAVAILABLE')}
const eligible=tabs.filter(t=>t.type==='page'&&(()=>{try{return new URL(t.url).hostname==='www.zhipin.com'}catch{return false}})());
const tab=options['--tab-id']?eligible.find(t=>t.id===options['--tab-id']):eligible.length===1?eligible[0]:null;
if(!tab){saved.status='needs-explicit-zhipin-tab-or-login';await save();throw Error('SELECT_ONE_ZHIPIN_TEST_TAB')}
const socketUrl=new URL(tab.webSocketDebuggerUrl);if(!['127.0.0.1','localhost'].includes(socketUrl.hostname)||socketUrl.protocol!=='ws:')throw Error('LOCAL_WEBSOCKET_ONLY');
const ws=new WebSocket(socketUrl),waiting=new Map();let seq=0;
try{await new Promise((res,rej)=>{const t=setTimeout(()=>{try{ws.close()}catch{}rej(Error('CDP_CONNECT_TIMEOUT'))},5000);ws.onopen=()=>{clearTimeout(t);res()};ws.onerror=()=>{clearTimeout(t);rej(Error('CDP_CONNECT_ERROR'))}})}
catch(e){saved.status='paused:'+e.message;await save();try{ws.close()}catch{}throw e}
ws.onmessage=e=>{const m=JSON.parse(e.data),p=waiting.get(m.id);if(p){clearTimeout(p.timer);waiting.delete(m.id);m.error?p.reject(Error('CDP_COMMAND_ERROR')):p.resolve(m.result)}};
ws.onclose=()=>{for(const p of waiting.values()){clearTimeout(p.timer);p.reject(Error('CDP_CLOSED'))}waiting.clear()};
const call=(method,params={})=>new Promise((resolve,reject)=>{let id=++seq;const timer=setTimeout(()=>{waiting.delete(id);reject(Error('CDP_TIMEOUT'))},15000);waiting.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}))});
const pause=()=>new Promise(r=>setTimeout(r,cfg.delayMs));
async function read(){const r=await call('Runtime.evaluate',{expression:snapshotExpression,returnByValue:true});const s=JSON.parse(r.result.value);checkPage(s);return {...s,capturedAt:new Date().toISOString()}}
async function go(url,ready){await call('Page.navigate',{url});for(let i=0;i<12;i++){await pause();const s=await read();if(ready(s))return s}throw Error('PAGE_INCOMPLETE')}
try{
 await read(); // Check an existing verification/login wall BEFORE any navigation.
 saved.status='collecting';await save();
 for(const query of cfg.queries){
  if(saved.companies.length>=cfg.targetCompanies||saved.attemptedJobs.length>=cfg.maxJobDetails)break;
  const search=await go('https://www.zhipin.com/web/geek/jobs?city='+cfg.city+'&query='+encodeURIComponent(query),s=>s.links.some(l=>l.cls==='job-name'));
  saved.searches.push({query,...search});await save();
  for(const link of search.links.filter(l=>l.cls==='job-name')){
   if(saved.companies.length>=cfg.targetCompanies||saved.attemptedJobs.length>=cfg.maxJobDetails)break;
   let id;try{id=canonicalJob(link.href)}catch{continue}
   if(saved.jobs.some(j=>j.id===id))continue;
   if(!saved.attemptedJobs.includes(id))saved.attemptedJobs.push(id);else continue;
   await save();
   try{
    const job=await go(link.href,s=>s.text.includes('职位描述')&&s.text.includes(link.text));
    const cl=companyLink(job);let company=null;
    if(cl)company=await go(cl.href,s=>s.text.includes('工商信息'));
    addJob(saved,job,company);await save();
    console.log(JSON.stringify({jobs:saved.jobs.length,platformCompanies:saved.companies.length,review:'pending'}));
   }catch(e){saved.failures.push({jobId:id,code:e.message});if(/STOP|CLOSED|TIMEOUT/.test(e.message))saved.attemptedJobs=saved.attemptedJobs.filter(x=>x!==id);await save();if(/STOP|CLOSED|TIMEOUT/.test(e.message))throw e}
  }
 }
 saved.status=saved.companies.length>=cfg.targetCompanies?'coverage-reached-review-pending':'bounded-search-finished-coverage-insufficient';await save();
}catch(e){saved.status='paused:'+e.message;await save();throw e}finally{ws.close()}
console.log(JSON.stringify({status:saved.status,companies:saved.companies.length,jobs:saved.jobs.length,review:'pending'}));
