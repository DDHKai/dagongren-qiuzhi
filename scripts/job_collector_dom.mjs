// DOM-only snapshot expression shared by live collector and layout regression tests.
export function snapshotDocument(document,location){
 const links=els=>[...els].map(a=>({text:a.innerText,href:a.href,cls:a.className}));
 const heading=[...document.querySelectorAll('h2,h3,h4,p.title')].find(e=>e.textContent.trim()==='公司基本信息');
 const scope=heading?.closest('.sider-company');
 return {url:location.href,title:document.title,text:document.body.innerText,
  links:links(document.querySelectorAll('a[href]')),
  companyLinks:scope?links(scope.querySelectorAll('a[href]')):[]};
}
export const snapshotExpression='JSON.stringify(('+snapshotDocument.toString()+')(document,location))';
