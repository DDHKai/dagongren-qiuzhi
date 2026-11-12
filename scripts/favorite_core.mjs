// Pure favorite policy; no browser, messages, attachments or credentials.
import {createHash,createHmac} from 'node:crypto';
import {canonicalJob} from './job_collector_core.mjs';
export const digest=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
export function accountProof(raw,browser,salt){
 if(typeof salt!=='string'||salt.length<32||!raw?.name||!/^1[3-9]\d\*{3,}\d{2,4}$/.test(raw.phone)||!browser)throw Error('ACCOUNT_MARKER_UNAVAILABLE');
 const h=value=>createHmac('sha256',salt).update(value).digest('hex');
 return {fingerprint:h(JSON.stringify([raw.name.trim(),raw.phone])),browserFingerprint:h(browser),displayHint:raw.phone,method:'visible-masked-phone-and-nav-name-v1',capturedAt:new Date().toISOString()};
}
export function assertAccount(actual,expected){if(!expected||actual.fingerprint!==expected.fingerprint||actual.browserFingerprint!==expected.browserFingerprint)throw Error('ACCOUNT_OR_BROWSER_CHANGED')}
export function favoriteState(control){
 if(control?.kind==='explicit-favorite'&&['收藏','已收藏'].includes(control.label))return control.label==='已收藏'?'collected':'not-collected';
 if(control?.kind==='boss-interest'&&control.label==='取消感兴趣')return control.active===true?'collected':'unknown';
 if(control?.kind==='boss-interest'&&['感兴趣','已感兴趣'].includes(control.label))return control.label==='已感兴趣'?'collected':control.active===true?'unknown':'not-collected';
 return 'unknown';
}
export function critical(observation,title){
 const j=observation.job,c=observation.company;if(canonicalJob(j.id)!==j.id||j.id!==j.source.url||!c||c.id!==j.companyKey)throw Error('IDENTITY_UNVERIFIED');
 const text=j.source.text,start=text.indexOf(title),jd=text.indexOf('职位描述',start);
 if(start<0||jd<0)throw Error('DESCRIPTION_UNAVAILABLE');
 const end=Math.min(...['竞争力分析','BOSS 安全提示','更多职位','看过该职位的人还看了'].map(m=>text.indexOf(m,jd+1)).filter(p=>p>=0),text.length);
 const headerEnd=Math.min(...['取消感兴趣','取消收藏','已收藏','收藏','已感兴趣','感兴趣','立即沟通','继续沟通','职位描述'].map(m=>text.indexOf(m,start+title.length)).filter(p=>p>=0),jd);
 const ct=c.source.text,a=ct.indexOf('工作时间及福利'),b=a<0?0:Math.min(...['招聘Boss','企业服务热线','查看所有职位'].map(m=>ct.indexOf(m,a+1)).filter(p=>p>=0),ct.length);
 const normalize=s=>s.replace(/\s+/g,' ').trim();
 return digest({job:j.id,company:c.id,header:normalize(text.slice(start,headerEnd)),duties:normalize(text.slice(jd,end)),benefits:a<0?null:normalize(ct.slice(a,b))});
}
export function controlDocument(document,title){
 const scope=document.querySelector('.job-banner')||document.querySelector('.job-detail-header');
 if(!scope)return {favorite:'unknown',basis:'favorite-control-v1',control:null};
 const h=scope.querySelector('h1');if(!h||h.innerText.trim()!==title)return {favorite:'unknown',basis:'favorite-control-v1',control:null};
 const visible=e=>!!e.getClientRects().length&&!e.hasAttribute('disabled')&&e.getAttribute('aria-disabled')!=='true';
 const interest=[...scope.querySelectorAll('a.btn-interest,button.btn-interest')].filter(visible).filter(e=>['感兴趣','已感兴趣','取消感兴趣'].includes(e.innerText.trim()));
 const explicit=[...scope.querySelectorAll('a,button')].filter(visible).filter(e=>['收藏','已收藏'].includes(e.innerText.trim()));
 if(interest.length+explicit.length!==1)return {favorite:'unknown',basis:'favorite-control-v1',control:null};
 const e=interest[0]||explicit[0],label=e.innerText.trim(),kind=interest.length?'boss-interest':'explicit-favorite';
 const active=e.classList.contains('active');return {favorite:label==='取消感兴趣'?(active?'collected':'unknown'):label==='感兴趣'&&active?'unknown':['已感兴趣','已收藏'].includes(label)?'collected':'not-collected',basis:'favorite-control-v1',control:{kind,label,active},labels:[label]};
}
export function clickDocument(document,title,expected){
 // Re-resolve the exact current header immediately before one click. Never target communication.
 const scope=document.querySelector('.job-banner')||document.querySelector('.job-detail-header');
 if(!scope||scope.querySelector('h1')?.innerText.trim()!==title)throw Error('CLICK_IDENTITY_CHANGED');
 const nodes=[...scope.querySelectorAll('a,button')].filter(e=>e.getClientRects().length&&!e.hasAttribute('disabled')&&e.getAttribute('aria-disabled')!=='true').filter(e=>e.innerText.trim()===expected.label);
 if(nodes.length!==1||!['explicit-favorite','boss-interest'].includes(expected.kind)||expected.kind==='explicit-favorite'&&expected.label!=='收藏'||expected.kind==='boss-interest'&&(expected.label!=='感兴趣'||!nodes[0].classList.contains('btn-interest')||nodes[0].classList.contains('active')))throw Error('CLICK_CONTROL_CHANGED');
 nodes[0].click();return {clickRequested:true};
}
export function accountDocument(document){
 const name=document.querySelector('.nav-figure > a')?.innerText.trim().split('\n')[0]||'';
 const phones=[...new Set(document.body.innerText.match(/1[3-9]\d\*{3,}\d{2,4}/g)||[])];
 return {name,phone:phones.length===1?phones[0]:''};
}
