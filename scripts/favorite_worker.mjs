// Local subprocess protocol. No message/attachment capability exists in this worker.
import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {runFavorite} from './favorite_driver.mjs';
const args=process.argv.slice(2);if(args.length!==4||args[0]!=='--request'||args[2]!=='--output')throw Error('Use --request PRIVATE_JSON --output NEW_PRIVATE_DIR');
const output=resolve(args[3]);await mkdir(output);let result;
try{const spec=JSON.parse((await readFile(args[1],'utf8')).replace(/^\uFEFF/,''));result=await runFavorite(spec,join(output,'attempt.json'))}
catch(e){result={status:'stopped',code:e.message,clickMayHaveOccurred:false}}
await writeFile(join(output,'result.json'),JSON.stringify(result,null,2),{flag:'wx'});
console.log(JSON.stringify({status:result.status,clickMayHaveOccurred:result.clickMayHaveOccurred||result.clicked||false}));
if(result.status==='stopped')process.exitCode=1;
