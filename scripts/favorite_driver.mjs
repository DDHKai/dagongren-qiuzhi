import {writeFile} from 'node:fs/promises';
import {snapshotExpression} from './job_collector_dom.mjs';
import {canonicalJob,checkPage,companyLink} from './job_collector_core.mjs';
import {accountProof,assertAccount,critical,controlDocument,clickDocument,accountDocument,favoriteState} from './favorite_core.mjs';
export async function connect(endpoint,tabId){
 const u=new URL(endpoint);if(u.protocol!=='http:'||u.hostname!=='127.0.0.1'||!u.port||u.username||u.password||u.pathname!=='/'||u.search||u.hash)throw Error('LOCAL_ENDPOINT_ONLY');
 const get=async path=>(await fetch(new URL(path,u),{signal:AbortSignal.timeout(5000)})).json();
 const [tabs,version]=await Promise.all([get('/json/list'),get('/json/version')]);
 const eligible=tabs.filter(t=>{try{return t.type==='page'&&new URL(t.url).origin==='https://www.zhipin.com'}catch{return false}});
 const tab=tabId?eligible.find(t=>t.id===tabId):eligible.length===1?eligible[0]:null;if(!tab)throw Error('SELECT_ONE_TEST_TAB');
 const socket=new URL(tab.webSocketDebuggerUrl);if(socket.protocol!=='ws:'||!['127.0.0.1','localhost'].includes(socket.hostname)||socket.username||socket.password)throw Error('LOCAL_SOCKET_ONLY');
 const ws=new WebSocket(socket),pending=new Map();let seq=0;
 await new Promise((res,rej)=>{const timer=setTimeout(()=>{ws.close();rej(Error('CONNECT_TIMEOUT'))},5000);ws.onopen=()=>{clearTimeout(timer);res()};ws.onerror=()=>{clearTimeout(timer);rej(Error('CONNECT_FAILED'))}});
 ws.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error('CDP_ERROR')):p.resolve(m.result)}};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP_TIMEOUT'))},15000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}))});
 const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,returnByValue:true});if(r.exceptionDetails)throw Error('DOM_OPERATION_FAILED');return r.result.value};
 const read=async()=>{const s=JSON.parse(await evaluate(snapshotExpression)),page=new URL(s.url);if(page.origin!=='https://www.zhipin.com'||page.username||page.password)throw Error('PLATFORM_DOMAIN_CHANGED');checkPage(s);return {...s,capturedAt:new Date().toISOString()}};
 const pause=()=>new Promise(r=>setTimeout(r,1200));
 const go=async(url,ready)=>{await call('Page.navigate',{url});for(let n=0;n<15;n++){await pause();const s=await read();if(ready(s))return s}throw Error('PAGE_INCOMPLETE')};
 const close=()=>{ws.close();for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('closed'))}pending.clear()};
 return {call,evaluate,read,go,pause,close,browser:version.webSocketDebuggerUrl,tabId:tab.id};
}
async function account(client,salt){
 await client.read();await client.go('https://www.zhipin.com/web/geek/account',s=>s.text.includes('账号与安全中心'));
 const expr='JSON.stringify(('+accountDocument.toString()+')(document))';let raw=JSON.parse(await client.evaluate(expr));
 if(!raw.phone){await client.evaluate(`(()=>{/* favorite-account-nav-v1 */const nodes=[...document.querySelectorAll('a,button,li,div,span')].filter(e=>e.children.length===0&&e.innerText.trim()==='账号管理');if(nodes.length!==1)throw Error('ACCOUNT_NAV_UNAVAILABLE');nodes[0].click();return true})()`);for(let n=0;n<8;n++){await client.pause();await client.read();raw=JSON.parse(await client.evaluate(expr));if(raw.phone)break}}
 return {proof:accountProof(raw,client.browser,salt),name:raw.name};
}
async function observe(client,spec){
 const target=canonicalJob(spec.jobId);if(target!==spec.jobId)throw Error('CANONICAL_JOB_ONLY');
 let source=await client.go(target,s=>{try{return canonicalJob(s.url)===target&&s.text.includes('职位描述')}catch{return false}});
 const link=companyLink(source);if(!link||new URL(link.href).pathname!==spec.companyId)throw Error('COMPANY_CHANGED');
 const companySource=await client.go(link.href,s=>s.text.includes('工商信息'));
 const companyUrl=new URL(companySource.url),company={id:companyUrl.pathname,source:companySource};if(companyUrl.origin!=='https://www.zhipin.com'||company.id!==spec.companyId)throw Error('COMPANY_CHANGED');
 source=await client.go(target,s=>{try{return canonicalJob(s.url)===target&&s.text.includes('职位描述')}catch{return false}});
 const again=companyLink(source);if(!again||new URL(again.href).pathname!==spec.companyId)throw Error('COMPANY_CHANGED');
 const controls=JSON.parse(await client.evaluate('JSON.stringify(('+controlDocument.toString()+')(document,'+JSON.stringify(spec.jobTitle)+'))'));
 return {schemaVersion:1,kind:'read-only-job-observation',collector:'favorite-driver-v1',job:{id:target,companyKey:company.id,source:{...source,url:target}},company,controls};
}
export async function runFavorite(spec,artifact){
 if(!['probe','prepare','execute','verify'].includes(spec.mode))throw Error('FAVORITE_ONLY');
 const client=await connect(spec.endpoint||'http://127.0.0.1:9333',spec.tabId);let clickMayHaveOccurred=false;
 try{
  const identity=await account(client,spec.salt);
  if(spec.mode==='probe')return {status:'account-observed',account:identity.proof,tabId:client.tabId};
  assertAccount(identity.proof,spec.expectedAccount);const before=await observe(client,spec),beforeCritical=critical(before,spec.jobTitle);
  if(spec.mode==='prepare')return {status:'prepared-not-clicked',account:identity.proof,observation:before,criticalHash:beforeCritical};
  if(spec.mode==='verify'){
   await client.call('Page.reload');await client.pause();const observation=await observe(client,spec);
   const finalAccount=await account(client,spec.salt);assertAccount(finalAccount.proof,spec.expectedAccount);
   if(critical(observation,spec.jobTitle)!==beforeCritical||favoriteState(observation.controls.control)!=='collected')throw Error('EXISTING_FAVORITE_NOT_CONFIRMED');
   return {status:'verified-existing-favorite',account:finalAccount.proof,observation,clicked:false,reloadConfirmed:true};
  }
  if(!spec.attemptId||!spec.taskId||beforeCritical!==spec.expectedCriticalHash)throw Error('EXECUTION_SCOPE_CHANGED');
  const nav=await client.evaluate(`document.querySelector('.nav-figure > a')?.innerText.trim().split('\\n')[0]||''`);if(nav!==identity.name)throw Error('ACCOUNT_CHANGED');
  if(!Number.isFinite(spec.validUntil)||Date.now()/1000>=spec.validUntil)throw Error('AUTHORIZATION_EXPIRED_BEFORE_CLICK');
  if(favoriteState(before.controls.control)==='collected')return {status:'already-favorite',account:identity.proof,observation:before,clicked:false};
  if(favoriteState(before.controls.control)!=='not-collected')throw Error('FAVORITE_CONTROL_UNVERIFIED');
  await writeFile(artifact,JSON.stringify({taskId:spec.taskId,attemptId:spec.attemptId,jobId:spec.jobId,beforeCritical,account:identity.proof,capturedAt:new Date().toISOString(),status:'about-to-request-one-favorite-click'},null,2),{flag:'wx'});
  clickMayHaveOccurred=true;
  await client.evaluate('('+clickDocument.toString()+')(document,'+JSON.stringify(spec.jobTitle)+','+JSON.stringify(before.controls.control)+')');
  for(let n=0;n<8;n++){await client.pause();const s=await client.read();if(canonicalJob(s.url)!==spec.jobId)throw Error('UNEXPECTED_NAVIGATION');const control=JSON.parse(await client.evaluate('JSON.stringify(('+controlDocument.toString()+')(document,'+JSON.stringify(spec.jobTitle)+'))'));if(control.favorite==='collected')break}
  await client.call('Page.reload');await client.pause();const after=await observe(client,spec);
  if(critical(after,spec.jobTitle)!==beforeCritical||favoriteState(after.controls.control)!=='collected')throw Error('FAVORITE_NOT_CONFIRMED_AFTER_RELOAD');
  const finalAccount=await account(client,spec.salt);assertAccount(finalAccount.proof,spec.expectedAccount);
  return {status:'confirmed-favorite',account:finalAccount.proof,observation:after,clicked:true,reloadConfirmed:true,taskId:spec.taskId,attemptId:spec.attemptId};
 }catch(e){return {status:'stopped',code:e.message,clickMayHaveOccurred}}
 finally{client.close()}
}
