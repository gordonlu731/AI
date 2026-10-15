// Dependency-free local server for the prebuilt, fully offline application.
import {createServer} from 'node:http';
import {createReadStream} from 'node:fs';
import {stat} from 'node:fs/promises';
import {resolve,extname,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../dist/',import.meta.url));
const port=Number(process.env.PORT||4173);
if(!Number.isInteger(port)||port<1||port>65535)throw new Error('PORT must be an integer from 1 to 65535.');
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.wasm':'application/wasm','.json':'application/json'};
const server=createServer(async(req,res)=> {
  try {
    const url=new URL(req.url,'http://localhost');
    const pathname=decodeURIComponent(url.pathname);
    const file=resolve(root,`.${pathname==='/'?'/index.html':pathname}`);
    if(!file.startsWith(resolve(root)+sep)){res.writeHead(403);res.end('Forbidden');return;}
    const info=await stat(file);
    if(!info.isFile())throw new Error('Not a file');
    res.writeHead(200,{'Content-Type':mime[extname(file)]||'application/octet-stream','Content-Length':info.size,'Cache-Control':'no-cache','X-Content-Type-Options':'nosniff'});
    if(req.method==='HEAD'){res.end();return;}
    createReadStream(file).pipe(res);
  } catch {res.writeHead(404,{'Content-Type':'text/plain'});res.end('File not found. Run npm run build if dist is missing.');}
});
server.on('error',error=>{console.error(`Cannot start local server: ${error.message}`);process.exitCode=1;});
server.listen(port,'127.0.0.1',()=>console.log(`\nTHE BELLWORKS\nOpen Chrome at http://127.0.0.1:${port}\nAll assets are local. Internet access is not required.\nPress Ctrl+C to stop.\n`));
