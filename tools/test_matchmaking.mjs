// Run the pinned upstream tests with Windows-compatible ESM file URLs.
import fs from 'node:fs';
const directory=new URL('../service/cloudflare-matchmaking/upstream/',import.meta.url);
let source=fs.readFileSync(new URL('test.mjs',directory),'utf8');
source=source.replace('await import(copy)','await import(pathToFileURL(copy).href)');
source=source.replace('new URL("./worker.js", import.meta.url)',
    `new URL(${JSON.stringify(new URL('worker.js',directory).href)})`);
source='import { pathToFileURL } from "node:url";\n'+source;
await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
