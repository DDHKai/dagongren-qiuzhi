// Pure collector policy helpers. No browser/network actions.
import {createHash} from 'node:crypto';
export function canonicalJob(url){const u=new URL(url);if(u.protocol!=='https:'||u.hostname!=='www.zhipin.com'||!/^\/job_detail\/[^/]+\.html$/.test(u.pathname))throw Error('INVALID_JOB_URL');return u.origin+u.pathname}
export function validateConfig(c){
 if(!c||!/^\d{9}$/.test(c.city)||!Array.isArray(c.queries)||!c.queries.length||c.queries.some(q=>typeof q!=='string'||!q.trim()))throw Error('INVALID_CONFIG');
 for(const [k,min,max] of [['targetCompanies',1,1000],['maxJobDetails',1,2000],['delayMs',1200,30000]])if(!Number.isInteger(c[k])||c[k]<min||c[k]>max)throw Error('INVALID_CONFIG_'+k);
 return c;
}
export function configHash(c){return createHash('sha256').update(JSON.stringify(validateConfig(c))).digest('hex')}
export function checkpoint(c){return {schemaVersion:1,configHash:configHash(c),status:'pending',jobs:[],companies:[],failures:[],searches:[],attemptedJobs:[],review:'pending'}}
export function ensureResume(saved,c){if(saved.schemaVersion!==1||saved.configHash!==configHash(c))throw Error('CONFIG_CHANGED_USE_NEW_OUTPUT');return saved}
export function checkPage(s){if(/环境存在异常|安全验证|访问过于频繁|请完成验证/.test(s.text))throw Error('PLATFORM_CHECK_STOP');if(/登录查看完整内容|请登录后查看|登录\/注册/.test(s.text))throw Error('LOGIN_REQUIRED_STOP')}
export function companyLink(job){
 // Only explicitly scoped company-section links are eligible; never arbitrary recommendations.
 const links=(job.companyLinks||[]).filter(l=>{try{const u=new URL(l.href);return u.hostname==='www.zhipin.com'&&u.protocol==='https:'&&/^\/gongsi\/[^/]+\.html$/.test(u.pathname)&&l.text.trim()&&!/查看|收起/.test(l.text)}catch{return false}});
 const unique=[...new Map(links.map(l=>[new URL(l.href).pathname,l])).values()];
 return unique.length===1?unique[0]:null;
}
export function addJob(saved,job,company=null){
 const id=canonicalJob(job.url);
 if(saved.jobs.some(j=>j.id===id))return false;
 const link=companyLink(job);
 let companyKey=null;
 if(link&&company&&new URL(company.url).origin==='https://www.zhipin.com'&&new URL(company.url).pathname===new URL(link.href).pathname&&company.text.includes('工商信息')){
  companyKey=new URL(link.href).pathname;
  if(!saved.companies.some(c=>c.id===companyKey))saved.companies.push({id:companyKey,source:company,identityStatus:'platform-company-section-not-legal-verification'});
 }
 saved.jobs.push({id,companyKey,source:job,identityStatus:companyKey?'platform-linked':'unknown-do-not-borrow-recommended-company',review:'pending'});return true;
}
