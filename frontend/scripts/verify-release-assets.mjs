import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
const root=new URL('../',import.meta.url);
const manifest=JSON.parse(readFileSync(new URL('release-assets.json',root),'utf8'));
for(const [path,expected] of Object.entries(manifest)){
  const actual=createHash('sha256').update(readFileSync(new URL(path,root))).digest('hex');
  if(actual!==expected)throw new Error(`Release asset changed: ${path}. Review lineage and version before updating its frozen hash.`);
}
console.log(`Verified ${Object.keys(manifest).length} frozen release assets.`);
