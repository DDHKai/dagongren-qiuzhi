import assert from 'node:assert/strict';
import {snapshotDocument} from './job_collector_dom.mjs';
import {companyLink} from './job_collector_core.mjs';
const own={innerText:'示例主体',href:'https://www.zhipin.com/gongsi/own.html',className:''};
const other={innerText:'推荐主体',href:'https://www.zhipin.com/gongsi/recommended.html',className:''};
function document(scoped=true){return {title:'示例',body:{innerText:'职位描述 公司基本信息'},querySelectorAll(selector){
 if(selector==='h2,h3,h4,p.title')return [{textContent:'公司基本信息',closest:()=>scoped?{querySelectorAll:()=>[own]}:null}];
 if(selector==='a[href]')return [own,other];return [];
}}}
const s=snapshotDocument(document(),{href:'https://www.zhipin.com/job_detail/sample.html'});
assert.equal(s.links.length,2);assert.equal(s.companyLinks.length,1);assert.equal(companyLink(s).href,own.href);
assert.equal(companyLink(snapshotDocument(document(false),{href:s.url})),null);
console.log('PASS DOM scope regression: p.title company heading, scoped links only, no recommendation fallback.');
