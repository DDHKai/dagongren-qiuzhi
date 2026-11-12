// Synthetic CDP protocol fixture; no browser or real platform is contacted.
import http from 'node:http';
import {createHash} from 'node:crypto';
import {spawn} from 'node:child_process';
import {mkdtemp,mkdir,writeFile,readFile} from 'node:fs/promises';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const root=fileURLToPath(new URL('../',import.meta.url));await mkdir(join(root,'data/test-tmp'),{recursive:true});const dir=await mkdtemp(join(root,'data/test-tmp/cdp-fixture-'));
let mode='happy',current='https://www.zhipin.com/web/geek/jobs',navigations=0;let commands=[];const sockets=new Set();
const jobs=[1,2,3].map(i=>({text:'样例岗位'+i,href:'https://www.zhipin.com/job_detail/fake'+i+'.html',cls:'job-name'}));
function snapshot(){
 if(mode==='security')return {url:current,text:'请完成验证',links:[],companyLinks:[]};
 if(mode==='login')return {url:current,text:'登录/注册',links:[],companyLinks:[]};
 if(current.includes('/job_detail/')){let i=Number(current.match(/fake(\d)/)[1]);return {url:current,title:'样例岗位',text:'职位描述 样例岗位'+i+' 公司基本信息',links:[],companyLinks:[{href:'https://www.zhipin.com/gongsi/'+(i===3?'b':'a')+'.html',text:'样例主体'}]}}
 if(current.includes('/gongsi/'))return {url:current,title:'样例公司',text:'工商信息',links:[],companyLinks:[]};
 return {url:current,title:'列表',text:'示例列表',links:jobs,companyLinks:[]};
}
function frame(text){const b=Buffer.from(text);if(b.length<126)return Buffer.concat([Buffer.from([129,b.length]),b]);const h=Buffer.alloc(4);h[0]=129;h[1]=126;h.writeUInt16BE(b.length,2);return Buffer.concat([h,b])}
const server=http.createServer((req,res)=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify([{id:'test-tab',type:'page',url:'https://www.zhipin.com/web/geek/jobs',webSocketDebuggerUrl:'ws://127.0.0.1:'+server.address().port+'/ws'}]))});
server.on('upgrade',(req,socket)=>{
 sockets.add(socket);socket.on('close',()=>sockets.delete(socket));socket.on('error',()=>{});
 const key=createHash('sha1').update(req.headers['sec-websocket-key']+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest('base64');
 socket.write('HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+key+'\r\n\r\n');
 let pending=Buffer.alloc(0);
 socket.on('data',chunk=>{pending=Buffer.concat([pending,chunk]);while(pending.length>=2){const opcode=pending[0]&15;let len=pending[1]&127,offset=2;if(len===126){if(pending.length<4)return;len=pending.readUInt16BE(2);offset=4}if(len===127){socket.destroy();return}const masked=!!(pending[1]&128),need=offset+(masked?4:0)+len;if(pending.length<need)return;const mask=masked?pending.subarray(offset,offset+4):null;if(masked)offset+=4;const body=Buffer.from(pending.subarray(offset,offset+len));pending=pending.subarray(need);if(mask)for(let i=0;i<body.length;i++)body[i]^=mask[i%4];if(opcode===8){socket.end(Buffer.from([136,0]));return}if(opcode!==1)continue;
  const message=JSON.parse(body.toString());commands.push(message);let result={};
  if(message.method==='Page.navigate'){navigations++;if(mode==='disconnect'){socket.destroy();return}current=message.params.url}
  if(message.method==='Runtime.evaluate')result={result:{value:JSON.stringify(message.params.expression.includes('exact-label-in-job-header-only')?{favorite:'not-collected',labels:['收藏'],basis:'exact-label-in-job-header-only'}:snapshot())}};
  socket.write(frame(JSON.stringify({id:message.id,result})));
 }});
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const config=join(dir,'config.json'),output=join(dir,'happy');await writeFile(config,JSON.stringify({city:'101210100',queries:['示例'],targetCompanies:2,maxJobDetails:5,delayMs:1200}));
async function run(out){return await new Promise((resolve,reject)=>{const p=spawn(process.execPath,[join(root,'scripts/collect_jobs.mjs'),'--config',config,'--output',out,'--endpoint','http://127.0.0.1:'+server.address().port],{windowsHide:true,stdio:'ignore'});const t=setTimeout(()=>{p.kill();reject(Error('collector test timeout'))},45000);p.on('exit',code=>{clearTimeout(t);resolve(code)})})}
try{
 assert.equal(await run(output),0);let s=JSON.parse(await readFile(join(output,'checkpoint.json')));assert.equal(s.jobs.length,3);assert.equal(s.companies.length,2);assert.equal(s.review,'pending');
 const before=navigations;assert.equal(await run(output),0);assert.equal(navigations,before);s=JSON.parse(await readFile(join(output,'checkpoint.json')));assert.equal(s.jobs.length,3);
 for(const kind of ['security','login','disconnect']){mode=kind;const before=navigations,out=join(dir,kind);assert.notEqual(await run(out),0);const state=JSON.parse(await readFile(join(out,'checkpoint.json')));assert.equal(state.jobs.length,0);assert.match(state.status,/paused:/);if(kind!=='disconnect')assert.equal(navigations,before)}
 async function observe(out){return await new Promise((resolve,reject)=>{const p=spawn(process.execPath,[join(root,'scripts/observe_job.mjs'),'--job',jobs[0].href,'--output',out,'--endpoint','http://127.0.0.1:'+server.address().port],{windowsHide:true,stdio:'ignore'});const t=setTimeout(()=>{p.kill();reject(Error('observer timeout'))},30000);p.on('exit',code=>{clearTimeout(t);resolve(code)})})}
 mode='happy';current='https://www.zhipin.com/web/geek/jobs';commands=[];
 const observed=join(dir,'read-only');assert.equal(await observe(observed),0);const observation=JSON.parse(await readFile(join(observed,'observation.json')));
 assert.equal(observation.kind,'read-only-job-observation');assert.equal(observation.job.id,jobs[0].href);assert.equal(observation.company.id,'/gongsi/a.html');
 assert.ok(commands.every(c=>['Page.navigate','Runtime.evaluate'].includes(c.method)));assert.ok(commands.every(c=>!c.params.expression||!c.params.expression.includes('.click(')));
 mode='login';commands=[];assert.notEqual(await observe(join(dir,'read-only-login')),0);assert.ok(commands.every(c=>c.method!=='Page.navigate'));
 console.log('PASS read-only job refresh protocol: scoped identity, no input/click commands, pre-navigation login stop. Synthetic fixture only.');
 console.log('PASS synthetic CDP orchestration: 3 jobs/2 companies, resume dedupe, pre-navigation login/security stop, disconnect checkpoint. Not live platform validation.');
}finally{for(const s of sockets)s.destroy();await new Promise(r=>server.close(r))}
