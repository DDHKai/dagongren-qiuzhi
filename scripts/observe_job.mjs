// Read-only refresh. Does not click favorite/contact, send text or upload attachments.
import {writeFile,mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {canonicalJob,checkPage,companyLink} from './job_collector_core.mjs';
import {snapshotExpression} from './job_collector_dom.mjs';
const options={},args=process.argv.slice(2);for(let i=0;i<args.length;i+=2){if(!['--job','--output','--endpoint','--tab-id'].includes(args[i])||!args[i+1])throw Error('Use --job URL --output NEW_PRIVATE_DIR [--endpoint LOCAL_URL] [--tab-id ID]');options[args[i]]=args[i+1]}
if(!options['--job']||!options['--output'])throw Error('JOB_AND_NEW_OUTPUT_REQUIRED');
const target=canonicalJob(options['--job']);if(target!==options['--job'])throw Error('CANONICAL_JOB_ONLY');
const endpoint=new URL(options['--endpoint']||'http://127.0.0.1:9333');if(endpoint.origin!==`http://127.0.0.1:${endpoint.port}`||endpoint.pathname!=='/'||endpoint.search||endpoint.hash||endpoint.username||endpoint.password)throw Error('LOCAL_ENDPOINT_ONLY');
const dir=resolve(options['--output']);await mkdir(dir);let ws,seq=0;const pending=new Map();
async function save(name,value){await writeFile(join(dir,name),JSON.stringify(value,null,2),{flag:'wx'})}
function call(method,params={}){return new Promise((resolve,reject)=>{const id=++seq,timer=setTimeout(()=>{pending.delete(id);reject(Error('CDP_TIMEOUT'))},15000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}))})}
async function read(){const r=await call('Runtime.evaluate',{expression:snapshotExpression,returnByValue:true});if(r.exceptionDetails)throw Error('READ_FAILED');const s=JSON.parse(r.result.value);checkPage(s);return {...s,capturedAt:new Date().toISOString()}}
const pause=()=>new Promise(r=>setTimeout(r,1200));
async function go(url,ready){await call('Page.navigate',{url});for(let i=0;i<15;i++){await pause();const s=await read();if(ready(s))return s}throw Error('PAGE_INCOMPLETE')}
try{
 const tabs=await(await fetch(new URL('/json/list',endpoint),{signal:AbortSignal.timeout(5000)})).json();
 const eligible=tabs.filter(t=>t.type==='page'&&new URL(t.url).origin==='https://www.zhipin.com');const tab=options['--tab-id']?eligible.find(t=>t.id===options['--tab-id']):eligible.length===1?eligible[0]:null;
 if(!tab)throw Error('SELECT_ONE_LOGGED_IN_ZHIPIN_TEST_TAB');
 const socket=new URL(tab.webSocketDebuggerUrl);if(socket.protocol!=='ws:'||!['localhost','127.0.0.1'].includes(socket.hostname)||socket.username||socket.password)throw Error('LOCAL_SOCKET_ONLY');
 ws=new WebSocket(socket);await new Promise((res,rej)=>{const t=setTimeout(()=>{try{ws.close()}catch{}rej(Error('CONNECT_TIMEOUT'))},5000);ws.onopen=()=>{clearTimeout(t);res()};ws.onerror=()=>{clearTimeout(t);rej(Error('CONNECT_FAILED'))}});
 ws.onmessage=e=>{const m=JSON.parse(e.data),p=pending.get(m.id);if(p){clearTimeout(p.timer);pending.delete(m.id);m.error?p.reject(Error('CDP_ERROR')):p.resolve(m.result)}};
 ws.onclose=()=>{for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('CDP_CLOSED'))}pending.clear()};
 await read();let source=await go(target,s=>s.url.split('?')[0]===target&&s.text.includes('职位描述'));
 const link=companyLink(source);let company=null;
 if(link){const s=await go(link.href,s=>s.text.includes('工商信息'));if(new URL(s.url).pathname===new URL(link.href).pathname)company={id:new URL(link.href).pathname,source:s}}
 source=await go(target,s=>s.url.split('?')[0]===target&&s.text.includes('职位描述'));
 const finalLink=companyLink(source);if(!finalLink||!company||new URL(finalLink.href).pathname!==company.id)throw Error('COMPANY_IDENTITY_UNVERIFIED');
 const readControls=`JSON.stringify((()=>{const scope=document.querySelector('.job-banner')||document.querySelector('.job-detail-header');if(!scope)return {favorite:'unknown',basis:'no-verified-header-scope'};const labels=[...scope.querySelectorAll('a,button')].map(e=>e.innerText.trim());const yes=labels.filter(x=>x==='已收藏'),no=labels.filter(x=>x==='收藏');return {favorite:yes.length===1&&!no.length?'collected':no.length===1&&!yes.length?'not-collected':'unknown',labels,basis:'exact-label-in-job-header-only'};})())`;
 const controls=await call('Runtime.evaluate',{expression:readControls,returnByValue:true});if(controls.exceptionDetails)throw Error('CONTROL_READ_FAILED');
 const observation={schemaVersion:1,kind:'read-only-job-observation',collector:'observe_job.mjs',job:{id:target,companyKey:company.id,source:{...source,url:target}},company,controls:JSON.parse(controls.result.value),limitations:['收藏状态只在识别到唯一头部按钮时披露，否则未知。','没有点击、消息、附件或投递动作。','沟通入口或聊天页不证明消息已发送。']};
 await save('observation.json',observation);console.log(JSON.stringify({status:'read-only-observation-saved',favorite:observation.controls.favorite,systemExecuted:false}));
}catch(e){await save('status.json',{status:'refresh-unavailable',code:e.message,systemExecuted:false});throw e}
finally{if(ws)ws.close();for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('closed'))}pending.clear()}
